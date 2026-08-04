#!/usr/bin/env python3
"""Copertura: quanta parte di un trace vendor il port tocca.

Non e' un confronto posizionale — quello lo fa compare.py e richiede che le due
sequenze siano allineabili, cosa che sull'init non e' vera perche' b43 e il
driver proprietario ordinano le fasi in modo diverso. Questo misura una cosa piu'
grezza e piu' utile all'inizio: **quali registri e quali celle di tabella** il
vendore scrive e il port no, e viceversa.

Il "viceversa" e' la meta' che conta di piu': se il port scrive qualcosa che il
vendore non tocca, quello e' un sospetto immediato.

    ./coverage.py ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded \\
                  trace.full.out --range 132 26100
"""

import argparse
import re
import signal
from collections import Counter

RE_LINE = re.compile(r'^\s*(?:[\d.]+\s+)?(?:#(\d+)\s+)?cpu\d+\s+(\S+)\s*(.*)$')
PHY_PORT_REGS = {0x72, 0x73, 0x74}   # indirizzo/dati delle table-op, non contenuto


def load(path, lo=None, hi=None, values=None):
    """Conta i registri e le celle toccate; se `values` e' un dict, ci mette il
    PRIMO valore scritto su ciascun registro, che serve al confronto --values."""
    regs, tbls = Counter(), Counter()
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_LINE.match(line.rstrip('\n'))
        if not m:
            continue
        seq = int(m.group(1)) if m.group(1) else 0
        if lo is not None and seq and not (lo <= seq <= hi):
            continue
        op = m.group(2)
        kv = dict(re.findall(r'(\w+)=(\S+)', m.group(3)))

        def num(key):
            try:
                return int(kv.get(key, '0'), 0)
            except ValueError:
                return 0

        if op in ('PHY.WR', 'PHY.MOD', 'PHY.AND', 'PHY.OR'):
            addr = num('addr')
            if addr not in PHY_PORT_REGS:
                regs[('phy', addr)] += 1
                if values is not None and op == 'PHY.WR':
                    values.setdefault(('phy', addr), num('val'))
        elif op in ('RAD.WR', 'RAD.MOD', 'RAD.AND', 'RAD.OR'):
            regs[('rad', num('addr'))] += 1
            if values is not None and op == 'RAD.WR':
                values.setdefault(('rad', num('addr')), num('val'))
        elif op == 'OBJ.WR':
            # Gli offset della object memory NON sono confrontabili fra i due
            # lati: b43 espone un offset in BYTE nella regione SHARED e lo
            # divide per 4 dentro b43_shm_write16(), il tracer del vendore
            # registra l'argomento di write_objmem16(), che e' un indirizzo di
            # parola con un selettore di spazio diverso (0x10000 contro
            # B43_SHM_SHARED = 1). Confrontarli produce solo rumore, quindi si
            # contano e non si confrontano.
            regs[('obj', num('addr'))] += 1
        elif op == 'TBL.WR':
            # Una table-op di lunghezza N copre N celle: contarla come una sola
            # sottostima il port, che scrive in bulk dove il vendore scrive
            # cella per cella. Il confronto e' fra insiemi di celle toccate.
            tid, off, ln = num('id'), num('off'), max(1, num('len'))
            for i in range(ln):
                tbls[(tid, off + i)] += 1
    return regs, tbls


def fmt_reg(key):
    kind, addr = key
    return '%s%03x' % ({'phy': 'p', 'rad': 'r', 'obj': 'o'}[kind], addr)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('vendor')
    ap.add_argument('port')
    ap.add_argument('--range', nargs=2, type=int, metavar=('DA', 'A'),
                    help='limita il trace vendor a questi numeri di record')
    ap.add_argument('--details', action='store_true',
                    help='elenca registri e celle mancanti')
    ap.add_argument('--values', action='store_true',
                    help='confronta anche il PRIMO valore scritto su ogni '
                         'registro toccato da entrambi. Trova la differenza che '
                         'la sola presenza non vede: stesso registro, valore '
                         'diverso. Attenzione ai falsi positivi, i due lati '
                         'ordinano le fasi in modo diverso e il primo valore '
                         'puo\' venire da una fase diversa.')
    args = ap.parse_args()

    lo, hi = args.range if args.range else (None, None)
    vv, pv = ({}, {}) if args.values else (None, None)
    vr, vt = load(args.vendor, lo, hi, vv)
    pr, pt = load(args.port, values=pv)

    miss_r = {k: c for k, c in vr.items() if k not in pr}
    miss_t = {k: c for k, c in vt.items() if k not in pt}
    extra_r = {k: c for k, c in pr.items() if k not in vr}
    extra_t = {k: c for k, c in pt.items() if k not in vt}

    # Per classe, non aggregato: le OBJ (SHM) le scrive quasi tutte il core b43,
    # non phy_n.c, quindi mescolarle alle PHY nasconde il dato che interessa.
    for kind, label in (('phy', 'PHY '), ('rad', 'radio')):
        vk = {k: c for k, c in vr.items() if k[0] == kind}
        pk = {k: c for k, c in pr.items() if k[0] == kind}
        mk = {k: c for k, c in vk.items() if k not in pk}
        print('registri %-5s vendore %3d, port %3d, coperti %3d (%3.0f%%), mancanti %3d'
              % (label, len(vk), len(pk), len(vk) - len(mk),
                 100.0 * (len(vk) - len(mk)) / max(1, len(vk)), len(mk)))
    vo = len([k for k in vr if k[0] == 'obj'])
    po = len([k for k in pr if k[0] == 'obj'])
    print('SHM          vendore %3d offset, port %3d: fuori dal confronto, '
          'encoding diversi' % (vo, po))
    print('celle tab.   vendore %3d, port %3d, coperte %3d (%.0f%%), mancanti %3d'
          % (len(vt), len(pt), len(vt) - len(miss_t),
             100.0 * (len(vt) - len(miss_t)) / max(1, len(vt)), len(miss_t)))

    # La object memory esce dal confronto: encoding diversi, vedi sopra.
    extra_r = {k: c for k, c in extra_r.items() if k[0] != 'obj'}
    miss_r = {k: c for k, c in miss_r.items() if k[0] != 'obj'}

    if extra_r or extra_t:
        print('\nDA GUARDARE: il port tocca roba che il vendore non tocca')
        if extra_r:
            print('  registri: %s' % ' '.join(fmt_reg(k) for k in sorted(extra_r)))
        if extra_t:
            print('  celle:    %s' % ' '.join('tbl%d+0x%x' % k for k in sorted(extra_t)))
    else:
        print('\nil port non tocca nulla che il vendore non tocchi')

    per_tbl = Counter()
    for (tid, _), _ in miss_t.items():
        per_tbl[tid] += 1
    if per_tbl:
        print('\ncelle mancanti per tabella: %s'
              % ' '.join('tbl%d x%d' % kv for kv in
                         sorted(per_tbl.items(), key=lambda kv: -kv[1])))

    if args.values:
        both = sorted(set(vv) & set(pv))
        diff = [(k, vv[k], pv[k]) for k in both if vv[k] != pv[k]]
        print('\nvalori: %d registri scritti da entrambi, %d col primo valore '
              'diverso' % (len(both), len(diff)))
        for k, a, b in diff:
            print('  %-6s vendore 0x%04x   port 0x%04x' % (fmt_reg(k), a, b))

    if args.details:
        print('\nregistri mancanti: %s'
              % ' '.join(fmt_reg(k) for k in sorted(miss_r)))


if __name__ == '__main__':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
