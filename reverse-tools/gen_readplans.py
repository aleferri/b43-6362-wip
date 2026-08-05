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


def emit(plans, name, source, reads, matched, out):
    p = out.write
    p('/* SPDX-License-Identifier: GPL-2.0\n'
      ' *\n'
      ' * GENERATO da reverse-tools/gen_readplans.py: non modificare a mano.\n'
      ' *   sorgente: %s\n'
      ' *   read con RETVAL appaiato: %d su %d\n'
      ' *   indirizzi con un piano: %d\n'
      ' *\n'
      ' * Per ogni indirizzo, i valori che l\'hardware ha restituito e il numero di\n'
      ' * record della cattura da cui ciascuno viene. Il numero di record serve a\n'
      ' * servire le read del port in ordine di cattura invece che a srotolare una\n'
      ' * coda: il port ne fa meno del vendore, e senza la posizione ogni fase che\n'
      ' * dipende da una lettura calcola su valori di un\'altra fase.\n'
      ' */\n' % (source, matched, reads, len(plans)))
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

    p('\nstatic inline void b43_test_load_readplans(void)\n{\n')
    for (kind, addr), sym in names.items():
        fn = {'phy': 'b43_test_plan_phy_reads',
              'radio': 'b43_test_plan_radio_reads',
              'mmio': 'b43_test_plan_mmio_reads'}[kind]
        p('\t%s(0x%04x, %s, %s_rec, ARRAY_SIZE_TEST(%s));\n'
          % (fn, addr, sym, sym, sym))
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
    emit(plans, args.name, args.trace.split('/')[-1], reads, matched, sys.stdout)
    print('%d piani, %d/%d read appaiate' % (len(plans), matched, reads),
          file=sys.stderr)


if __name__ == '__main__':
    main()
