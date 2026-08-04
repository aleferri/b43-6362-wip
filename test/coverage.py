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


def load(path, lo=None, hi=None):
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
        elif op in ('RAD.WR', 'RAD.MOD', 'RAD.AND', 'RAD.OR'):
            regs[('rad', num('addr'))] += 1
        elif op == 'OBJ.WR':
            regs[('obj', num('addr'))] += 1
        elif op == 'TBL.WR':
            tbls[(num('id'), num('off'))] += 1
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
    args = ap.parse_args()

    lo, hi = args.range if args.range else (None, None)
    vr, vt = load(args.vendor, lo, hi)
    pr, pt = load(args.port)

    miss_r = {k: c for k, c in vr.items() if k not in pr}
    miss_t = {k: c for k, c in vt.items() if k not in pt}
    extra_r = {k: c for k, c in pr.items() if k not in vr}
    extra_t = {k: c for k, c in pt.items() if k not in vt}

    # Per classe, non aggregato: le OBJ (SHM) le scrive quasi tutte il core b43,
    # non phy_n.c, quindi mescolarle alle PHY nasconde il dato che interessa.
    for kind, label in (('phy', 'PHY '), ('rad', 'radio'), ('obj', 'SHM ')):
        vk = {k: c for k, c in vr.items() if k[0] == kind}
        pk = {k: c for k, c in pr.items() if k[0] == kind}
        mk = {k: c for k, c in vk.items() if k not in pk}
        print('registri %-5s vendore %3d, port %3d, coperti %3d (%3.0f%%), mancanti %3d'
              % (label, len(vk), len(pk), len(vk) - len(mk),
                 100.0 * (len(vk) - len(mk)) / max(1, len(vk)), len(mk)))
    print('celle tab.   vendore %3d, port %3d, coperte %3d (%.0f%%), mancanti %3d'
          % (len(vt), len(pt), len(vt) - len(miss_t),
             100.0 * (len(vt) - len(miss_t)) / max(1, len(vt)), len(miss_t)))

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

    if args.details:
        print('\nregistri mancanti: %s'
              % ' '.join(fmt_reg(k) for k in sorted(miss_r)))


if __name__ == '__main__':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
