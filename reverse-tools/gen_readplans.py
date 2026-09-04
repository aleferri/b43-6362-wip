#!/usr/bin/env python3
"""Costruisce i piani di lettura dell'harness dai RETVAL di una cattura.

Nell'harness le read senza piano ritornano il mirror, cioe' l'ultima cosa scritta
lì: i loop di calibrazione e i poll fanno un giro e finiscono, e i rami guidati
dallo stato dell'hardware non si imboccano mai. I valori veri ci sono, nella
cattura: ogni read del tracer e' seguita da un RETVAL col valore che l'hardware
ha restituito.

Questo li estrae e li emette come header C. Il piano e' **per indirizzo, in
ordine di arrivo**: la i-esima lettura di 0x2a4 ottiene il valore della i-esima
lettura di 0x2a4 nella cattura. Non e' l'ordine globale, che il port non segue
comunque perche' ordina le fasi in modo diverso; per i poll e i loop di cal, che
leggono lo stesso registro piu' volte di fila, e' esattamente quello che serve.

    ./gen_readplans.py ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded \\
        --range 132 26100 --name init > ../test/readplans_init.h
"""

import argparse
import re
import sys
from collections import OrderedDict

RE_LINE = re.compile(r'^\s*(?:[\d.]+\s+)?#(\d+)\s+cpu\d+\s+(\S+)\s*(.*)$')

KINDS = {'PHY.RD': 'phy', 'RAD.RD': 'radio', 'MMIO.RD': 'mmio'}

# 0x72, 0x73 e 0x74 sono la porta di accesso alle tabelle (indirizzo, dati bassi,
# dati alti). Rigiocare lì i valori della cattura non riproduce niente: nel port
# quelle read servono a leggere una tabella, e il valore giusto e' quello che la
# tabella contiene, non quello che il vendore aveva letto da un'altra tabella in
# un altro momento. Lasciate fuori, le gestisce il mirror.
TABLE_PORT = {0x72, 0x73, 0x74}

# I registri di comando la cui fine il sorgente del vendore legge DUE volte, e
# b43 una. Non si deduce dalla cattura, e ci ho provato: una regola generale
# "togli la coda duplicata di ogni poll" tocca anche 0x21a e 0x219, che nella
# seconda cal RSSI sono otto campionamenti uguali di fila e non un poll, e
# affamerebbe il loro piano di 416 voci. L'informazione e' semantica e va
# dichiarata qui, una riga per registro, con la ragione.
#
# PHY 0x129 (IQEST_CMD): il riferimento fa SPINWAIT sul bit di start
# (brcmsmac phy_n.c:26050) e poi lo riguarda nell'if che apre la lettura degli
# accumulatori (26056), quindi il valore con lo start spento compare due volte in
# ogni gruppo -- verificato, 8 gruppi su 8 in up-ch1. b43_nphy_rx_iq_est() legge
# una volta sola, e quella lettura gli serve sia da test d'uscita sia da guardia.
# La voce di troppo resta in coda e se la prende la chiamata dopo, che esce al
# primo giro: 65 letture in 8 chiamate con forme 5 1 5 1 4 1 47 1, e 47 op
# spostate nel buco a #17913.
#
# PHY 0x0c0 (IQLOCAL_CMD) NON e' nella lista e non ci va: i suoi 24 gruppi
# finiscono con il valore che cambia una volta sola (0x8434 0x8434 0x8434 0x434),
# quindi b43 e il vendore ne fanno lo stesso numero.
POLL_DOUBLE_TAIL = {('phy', 0x129)}

# Due letture della stessa cella a meno di questo numero di record sono lo stesso
# poll. Piu' lontane sono due punti diversi del flusso che leggono lo stesso
# registro, e la coda duplicata di uno non e' la coda dell'altro.
POLL_GAP = 4


def drop_double_tails(plans):
    """Toglie la voce terminale duplicata dai poll dichiarati in POLL_DOUBLE_TAIL."""
    for key in list(plans):
        if key not in POLL_DOUBLE_TAIL:
            continue
        vals = plans[key]
        groups = [[vals[0]]]
        for prev, cur in zip(vals, vals[1:]):
            if cur[0] - prev[0] <= POLL_GAP:
                groups[-1].append(cur)
            else:
                groups.append([cur])
        out = []
        for g in groups:
            n = 1
            while n < len(g) and g[-1 - n][1] == g[-1][1]:
                n += 1
            out.extend(g[:len(g) - (n - 1)] if n > 1 else g)
        plans[key] = out
    return plans


def cell_plans(path, lo, hi):
    """I piani per CELLA di tabella, dalle sole celle che li meritano.

    Le riletture che il mirror per porta non puo' riprodurre le trova
    trace_tables.hw_written(); di quelle si tengono solo le celle il cui valore
    CAMBIA fra una read e l'altra, perche' sono le sole scritte dall'hardware
    dentro la finestra - i risultati del motore di calibrazione. Le altre hanno
    valore fisso e sono stato da prima della finestra: quello e' lavoro del seed,
    e servirlo da un piano vorrebbe dire srotolare una coda dove basta un valore.

    La logica sta in trace_tables e non qui: e' la stessa misura che
    `trace_tables.py --hw-written` stampa, e due copie divergono.
    """
    import trace_tables as tt

    records = tt.parse(path)
    if lo is not None:
        records = [r for r in records if lo <= r['seq'] <= hi]

    # hw_written() decide QUALI celle meritano un piano; il contenuto e' un'altra
    # cosa e va preso intero. Mettere nel piano le sole riletture divergenti
    # sfasa la coda: la prima read del port prenderebbe la prima divergenza
    # invece del primo valore, e il resto a scalare.
    scelte = set()
    for (tid, off), c in tt.hw_written(records).items():
        if len(set(c['vals'])) > 1:
            scelte.add((tid, off))

    tutte = {}
    for t in sorted(tt.collect_reads(records), key=lambda t: t['seq']):
        if t['id'] is None or t['off'] is None:
            continue
        for k, val in enumerate(t['values']):
            key = (t['id'], t['off'] + k)
            if key in scelte and val is not None:
                tutte.setdefault(key, []).append(val)

    return OrderedDict((k, tutte[k]) for k in sorted(tutte))


def collect(path, lo, hi, max_len, skip=()):
    pending = {}          # seq del record di read -> (kind, addr)
    plans = OrderedDict()  # (kind, addr) -> [(record, valore)]
    reads = 0
    matched = 0

    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_LINE.match(line.rstrip('\n'))
        if not m:
            continue
        seq = int(m.group(1))
        op = m.group(2)
        kv = dict(re.findall(r'(\w+)=(\S+)', m.group(3)))

        if lo is not None and not (lo <= seq <= hi):
            continue
        if any(a <= seq <= b for a, b in skip):
            continue

        if op in KINDS:
            try:
                addr = int(kv.get('addr', ''), 0)
            except ValueError:
                continue
            if KINDS[op] == 'phy' and addr in TABLE_PORT:
                continue
            pending[seq] = (KINDS[op], addr)
            reads += 1
        elif op == 'RETVAL':
            ref = kv.get('for', '').lstrip('#')
            try:
                ref = int(ref)
                val = int(kv.get('val', '0'), 0)
            except ValueError:
                continue
            key = pending.pop(ref, None)
            if key is None:
                continue
            matched += 1
            vals = plans.setdefault(key, [])
            if len(vals) < max_len:
                vals.append((ref, val & 0xFFFF))

    return plans, reads, matched


def emit(plans, name, source, argv, reads, matched, out, cells=None):
    p = out.write
    p('/* SPDX-License-Identifier: GPL-2.0\n'
      ' *\n'
      ' * GENERATO da reverse-tools/gen_readplans.py: non modificare a mano.\n'
      ' *   sorgente: %s\n'
      ' *   invocazione: %s\n'
      ' *   read con RETVAL appaiato: %d su %d\n'
      ' *   indirizzi con un piano: %d\n'
      ' *\n'
      ' * Per ogni indirizzo, i valori che l\'hardware ha restituito e il numero di\n'
      ' * record della cattura da cui ciascuno viene. Il numero di record serve a\n'
      ' * servire le read del port in ordine di cattura invece che a srotolare una\n'
      ' * coda: il port ne fa meno del vendore, e senza la posizione ogni fase che\n'
      ' * dipende da una lettura calcola su valori di un\'altra fase.\n'
      ' *\n'
      ' * In coda i piani per CELLA di tabella, per le sole celle che l\'hardware\n'
      ' * scrive dentro la finestra: quelle il cursore non ce l\'hanno, perche\'\n'
      ' * la risposta giusta e\' la n-esima che il vendore ha letto da quella\n'
      ' * cella e non dipende dall\'ordine fra celle diverse.\n'
      ' *   celle con un piano: %d\n'
      ' */\n' % (source, argv, matched, reads, len(plans),
                    len(cells or {})))
    p('#ifndef _READPLANS_%s_H\n#define _READPLANS_%s_H\n\n'
      % (name.upper(), name.upper()))
    p('#include "test_harness.h"\n\n')

    names = {}
    for i, ((kind, addr), vals) in enumerate(plans.items()):
        sym = 'plan_%s_%s_%03x' % (name, kind, addr)
        names[(kind, addr)] = sym
        p('static const u16 %s[] = {' % sym)
        for j, (_, v) in enumerate(vals):
            p('%s0x%04x,' % ('\n\t' if j % 8 == 0 else ' ', v))
        p('\n};\n')
        p('static const u32 %s_rec[] = {' % sym)
        for j, (r, _) in enumerate(vals):
            p('%s%d,' % ('\n\t' if j % 8 == 0 else ' ', r))
        p('\n};\n')

    cnames = {}
    for (tid, off), vals in (cells or {}).items():
        sym = 'plan_%s_cell_%02x_%03x' % (name, tid, off)
        cnames[(tid, off)] = sym
        p('static const u16 %s[] = {' % sym)
        for j, v in enumerate(vals):
            p('%s0x%04x,' % ('\n\t' if j % 8 == 0 else ' ', v))
        p('\n};\n')

    p('\nstatic inline void b43_test_load_readplans_%s(void)\n{\n' % name)
    for (kind, addr), sym in names.items():
        fn = {'phy': 'b43_test_plan_phy_reads',
              'radio': 'b43_test_plan_radio_reads',
              'mmio': 'b43_test_plan_mmio_reads'}[kind]
        p('\t%s(0x%04x, %s, %s_rec, ARRAY_SIZE_TEST(%s));\n'
          % (fn, addr, sym, sym, sym))
    for (tid, off), sym in cnames.items():
        p('\tb43_test_plan_table_cell(%d, 0x%03x, %s, ARRAY_SIZE_TEST(%s));\n'
          % (tid, off, sym, sym))
    p('}\n\n#endif\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('trace')
    ap.add_argument('--range', nargs=2, type=int, metavar=('DA', 'A'))
    ap.add_argument('--name', default='init')
    ap.add_argument('--skip', nargs=2, type=int, action='append', default=[],
                    metavar=('DA', 'A'),
                    help='intervallo di record da NON mettere nel piano, '
                         'ripetibile. Il piano e\' una FIFO per indirizzo: le '
                         'letture di una fase che il port non esegue vanno '
                         'escluse, o le consuma lui e da li\' in poi legge i '
                         'valori del giro sbagliato.')
    ap.add_argument('--max-len', type=int, default=64,
                    help='valori per indirizzo (i poll ne hanno migliaia)')
    args = ap.parse_args()

    lo, hi = args.range if args.range else (None, None)
    plans, reads, matched = collect(args.trace, lo, hi, args.max_len,
                                   [tuple(x) for x in args.skip])
    if not plans:
        sys.exit('nessuna read con RETVAL appaiato: e\' il trace giusto?')
    plans = drop_double_tails(plans)
    cells = cell_plans(args.trace, lo, hi)
    argv = 'gen_readplans.py ' + ' '.join(sys.argv[1:])
    emit(plans, args.name, args.trace.split('/')[-1], argv, reads, matched,
         sys.stdout, cells)
    print('%d piani per indirizzo, %d/%d read appaiate, %d piani per cella'
          % (len(plans), matched, reads, len(cells)), file=sys.stderr)


if __name__ == '__main__':
    main()
