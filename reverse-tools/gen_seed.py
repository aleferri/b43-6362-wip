#!/usr/bin/env python3
"""Lo stato dell'hardware all'ingresso della finestra, preso dalla cattura.

La finestra che si misura e' una: da dove comincia `switch_channel` a dove il MAC
viene abilitato e trasmette. Quel blocco legge registri che ha programmato
qualcun altro prima di lui -- `op_init` e `rfkill` -- e senza quei valori le sue
letture cadono sullo specchio dell'harness, che li' non sa niente.

Questo strumento guarda **solo i record che precedono la finestra** e ne ricava,
per ogni indirizzo, l'ultimo valore noto. Il confine e' quello che rende i seed
onesti: si semina cio' che la finestra non puo' sapere, non cio' che deve
calcolare. Se si seminasse anche lo stato prodotto dentro la finestra, un
registro che il port programma sbagliato tornerebbe giusto per magia e la misura
non direbbe piu' niente.

Per i REGISTRI si guarda solo prima della finestra. Per le celle di tabella il
confine e' per forza diverso, perche' il download statico che le riempie e'
avvenuto in un boot precedente e prima di `--before` non c'e' niente da guardare:
vedi `table_cells()`, che spiega quale condizione tiene onesta la regola.

Tre fonti, in ordine di quando si presentano:

  - le write, `RAD.WR` / `PHY.WR` / `MMIO.WR`: il valore e' quello scritto;
  - le mod, `RAD.MOD` / `PHY.MOD` / le forme `(set X)` e `(clr X)`: si applicano
    al valore che si sta seguendo, e se non se ne sta seguendo nessuno la mod
    dice solo dei bit che tocca, quindi si tiene quello che si sa;
  - i `RETVAL` di una read: dicono lo stato meglio di qualunque inferenza, e
    vincono su quello che si era dedotto.

    ./reverse-tools/gen_seed.py router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded \\
        --before 132 --until 26100 --name up > test/seed_up.h
"""

import argparse
import re
import sys

REC = re.compile(r'^\s*[\d.]+\s+#(\d+)\s+\S+\s+(\S+)\s+(.*)$')
ADDR = re.compile(r'addr=(0x[0-9a-fA-F]+)')
VAL = re.compile(r'val=(0x[0-9a-fA-F]+)')
MASK = re.compile(r'mask=(0x[0-9a-fA-F]+)')
SET = re.compile(r'\(set (0x[0-9a-fA-F]+)\)')
CLR = re.compile(r'\(clr (0x[0-9a-fA-F]+)\)')
RETVAL = re.compile(r'for=#(\d+)\s+val=(0x[0-9a-fA-F]+)')

SPACES = {'PHY': 'phy', 'RAD': 'radio'}


def parse(path, before):
    """Lo stato per spazio, e la read in attesa del proprio RETVAL.

    Due categorie, e la seconda serve quanto la prima. `state` e' cio' che
    op_init e rfkill hanno programmato, cioe' i record prima del confine.
    La seconda e' cio' il cui **primo accesso nella cattura e' una read**: quel
    valore nessuno l'ha scritto, quindi e' lo stato che il chip ha dal reset, e la
    finestra non puo' averlo ne' saperlo. Il criterio non e' "mai scritto":
    0x17d la cal la scrive, ma la scrive DOPO averla letta, e il primo valore e'
    comunque un default. Le due atten del coupler, 0x17d e 0x19d a 0xaa, sono
    esattamente questo: non stanno in r2057_rev8_init, nessuno dei due driver le
    scrive, e senza di loro la cal PAPD ripristina uno zero.
    """
    state = {'phy': {}, 'radio': {}}
    written = {'phy': set(), 'radio': set()}
    virgin = {'phy': set(), 'radio': set()}
    first_ret = {'phy': {}, 'radio': {}}
    pending = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        m = REC.match(line)
        if not m:
            continue
        rec, op, rest = int(m.group(1)), m.group(2), m.group(3)

        if op == 'RETVAL':
            r = RETVAL.search(rest)
            if r and int(r.group(1)) in pending:
                space, addr, inside = pending.pop(int(r.group(1)))
                v = int(r.group(2), 16) & 0xffff
                if not inside:
                    state[space][addr] = v
                first_ret[space].setdefault(addr, v)
            continue
            # Le read che restano aperte oltre il confine non servono: il loro
            # RETVAL parla di uno stato che la finestra ha gia' cambiato.
            break

        kind, _, what = op.partition('.')
        space = SPACES.get(kind)
        if space is None:
            continue
        a = ADDR.search(rest)
        if not a:
            continue
        addr = int(a.group(1), 16)

        inside = rec >= before
        if what == 'RD':
            if addr not in written[space]:
                virgin[space].add(addr)
            pending[rec] = (space, addr, inside)
            continue
        written[space].add(addr)
        if inside:
            continue

        if what == 'WR':
            v = VAL.search(rest)
            if v:
                state[space][addr] = int(v.group(1), 16) & 0xffff
        elif what in ('MOD', 'OR', 'AND'):
            cur = state[space].get(addr)
            if cur is None:
                continue
            s, c, v, k = (SET.search(rest), CLR.search(rest),
                          VAL.search(rest), MASK.search(rest))
            if s:
                state[space][addr] = cur | int(s.group(1), 16)
            elif c:
                state[space][addr] = cur & ~int(c.group(1), 16) & 0xffff
            elif v and k:
                mask = int(k.group(1), 16)
                state[space][addr] = (cur & ~mask | int(v.group(1), 16)) & 0xffff

    ndef = 0
    for space in state:
        for addr, v in first_ret[space].items():
            if addr in virgin[space] and addr not in state[space]:
                state[space][addr] = v
                ndef += 1
    return state, ndef


def emit(state, name, source, before, out, cells=None):
    tot = sum(len(v) for v in state.values())
    out.write('/* SPDX-License-Identifier: GPL-2.0\n'
              ' *\n'
              ' * GENERATO da reverse-tools/gen_seed.py: non modificare a mano.\n'
              ' *   sorgente: %s\n'
              ' *   record considerati: #1-%d, cioe\' op_init e rfkill\n'
              ' *   indirizzi seminati: %d\n'
              ' *\n'
              ' * Lo stato che la finestra sotto misura NON puo\' avere perche\' lo\n'
              ' * ha prodotto qualcun altro prima di lei. Si semina solo questo:\n'
              ' * quello che la finestra deve calcolare va calcolato, o la misura\n'
              ' * non misura piu\' niente.\n'
              ' */\n' % (source, before - 1, tot))
    out.write('#ifndef _SEED_%s_H\n#define _SEED_%s_H\n\n'
              % (name.upper(), name.upper()))
    out.write('#include "test_harness.h"\n\n')
    for space in ('phy', 'radio'):
        items = sorted(state[space].items())
        out.write('static const u16 seed_%s_%s[][2] = {\n' % (name, space))
        for i in range(0, len(items), 4):
            row = ''.join('{ 0x%03x, 0x%04x }, ' % (a, v)
                          for a, v in items[i:i + 4])
            out.write('\t%s\n' % row.rstrip())
        out.write('};\n\n')
    items = sorted((cells or {}).items())
    out.write('static const u32 seed_%s_table[][3] = {\n' % name)
    for (tid, off), v in items:
        out.write('\t{ %d, 0x%03x, 0x%08x },\n' % (tid, off, v))
    out.write('};\n\n')
    out.write('static inline void b43_test_seed_%s(void)\n{\n'
              '\tunsigned int i;\n\n'
              '\tfor (i = 0; i < ARRAY_SIZE_TEST(seed_%s_phy); i++)\n'
              '\t\tb43_test_mirror_phy_set(seed_%s_phy[i][0],\n'
              '\t\t\t\t\tseed_%s_phy[i][1]);\n'
              '\tfor (i = 0; i < ARRAY_SIZE_TEST(seed_%s_radio); i++)\n'
              '\t\tb43_test_mirror_radio_set(seed_%s_radio[i][0],\n'
              '\t\t\t\t\t  seed_%s_radio[i][1]);\n'
              '\tfor (i = 0; i < ARRAY_SIZE_TEST(seed_%s_table); i++)\n'
              '\t\tb43_test_mirror_table_set(seed_%s_table[i][0],\n'
              '\t\t\t\t\t  seed_%s_table[i][1],\n'
              '\t\t\t\t\t  seed_%s_table[i][2]);\n'
              '}\n\n' % ((name,) * 11))
    out.write('#endif\n')


def table_cells(capture, before, until):
    """Le celle di tabella che valevano qualcosa all'ingresso della finestra.

    Qui il confine e' PER FORZA diverso da quello dei registri, e vale dirlo. Una
    cella come 15/0x50 non viene scritta da nessuna parte nella cattura: il
    download statico che l'ha riempita e' avvenuto in un boot precedente, e prima
    del record `--before` non c'e' niente da guardare. Il suo stato all'ingresso
    e' osservabile solo dalla PRIMA read che la tocca dentro la finestra.

    La regola resta onesta perche' e' la stessa che il tool applica ai registri
    tramite RETVAL - una read dice lo stato meglio di qualunque inferenza - con
    una condizione in piu': si tiene solo la cella che nessuna write per porta ha
    toccato prima di quella read, e il cui valore non cambia. Se la finestra ci ha
    scritto prima di leggerla, il valore e' cio' che la finestra deve calcolare e
    seminarlo lo farebbe tornare giusto per magia; se cambia fra le read, e'
    l'hardware che ci scrive dentro la finestra ed e' lavoro di un piano per
    cella, non del seme.

    Le due popolazioni le separa trace_tables.hw_written(), che e' anche cio' che
    `trace_tables.py --hw-written` stampa: sulla finestra up-ch1, 44 celle a
    valore fisso qui e 7 a valore variabile nei piani.
    """
    import trace_tables as tt

    records = [r for r in tt.parse(capture) if before <= r['seq'] <= until]
    out = {}
    for (tid, off), c in sorted(tt.hw_written(records).items()):
        vals = set(c['vals'])
        if len(vals) != 1 or not c['mai_scritta']:
            continue
        out[(tid, off)] = c['vals'][0]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('capture')
    ap.add_argument('--before', type=int, required=True,
                    help='il primo record DELLA FINESTRA: si guarda solo prima')
    ap.add_argument('--name', required=True)
    ap.add_argument('--until', type=int, required=True,
                    help='l\'ultimo record della finestra. Serve alle sole celle '
                         'di tabella, il cui stato all\'ingresso e\' osservabile '
                         'solo dalla prima read dentro la finestra: vedi '
                         'table_cells()')
    args = ap.parse_args()

    state, ndef = parse(args.capture, args.before)
    cells = table_cells(args.capture, args.before, args.until)
    emit(state, args.name, args.capture.split('/')[-1], args.before, sys.stdout,
         cells)
    sys.stderr.write('seminati: %d phy, %d radio, di cui %d default del chip, '
                     '%d celle di tabella\n'
                     % (len(state['phy']), len(state['radio']), ndef,
                        len(cells)))


if __name__ == '__main__':
    main()
