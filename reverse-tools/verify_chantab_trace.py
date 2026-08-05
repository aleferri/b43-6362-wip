#!/usr/bin/env python3
"""Confronta la chantab di b43 con le scritture radio di un trace catturato.

A ogni cambio canale il driver OEM riversa nel radio i campi della sua channel
info table. Se b43 ha la tabella giusta, quelle scritture sono le stesse, con gli
stessi valori e nello stesso ordine in cui
`b43_radio_2057_chantab_upload()` le farebbe. Questo strumento lo verifica per
ogni `CHANSPEC` presente nel trace, cioe' su tutti i canali che la cattura
tocca, invece che su uno scelto a mano.

Confronta solo i 18 campi della variante 2.4 GHz; i registri 5 GHz che il
vendore azzera (e che b43 non tocca) vengono elencati a parte, non contati come
errore.

    ./verify_chantab_trace.py flow.decoded --tree ~/src/linux
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chantab_from_blob import parse_b43, FIELDS_2G  # noqa: E402

B43 = 'drivers/net/wireless/broadcom/b43'

# I registri, nell'ordine in cui b43_radio_2057_chantab_upload() li scrive.
UPLOAD_ORDER = [
    'VCOCAL_COUNTVAL0', 'VCOCAL_COUNTVAL1', 'RFPLL_REFMASTER_SPAREXTALSIZE',
    'RFPLL_LOOPFILTER_R1', 'RFPLL_LOOPFILTER_C2', 'RFPLL_LOOPFILTER_C1',
    'CP_KPD_IDAC', 'RFPLL_MMD0', 'RFPLL_MMD1', 'VCOBUF_TUNE',
    'LOGEN_MX2G_TUNE', 'LOGEN_INDBUF2G_TUNE',
    'TXMIX2G_TUNE_BOOST_PU_CORE0', 'PAD2G_TUNE_PUS_CORE0', 'LNA2G_TUNE_CORE0',
    'TXMIX2G_TUNE_BOOST_PU_CORE1', 'PAD2G_TUNE_PUS_CORE1', 'LNA2G_TUNE_CORE1',
]

# Campi 5 GHz e PGA della entry dual band: il vendore li azzera in 2.4 GHz.
FIVE_GHZ_REGS = [
    'LOGEN_MX5G_TUNE', 'LOGEN_INDBUF5G_TUNE',
    'PGA_BOOST_TUNE_CORE0', 'TXMIX5G_BOOST_TUNE_CORE0',
    'PAD5G_TUNE_MISC_PUS_CORE0', 'LNA5G_TUNE_CORE0',
    'PGA_BOOST_TUNE_CORE1', 'TXMIX5G_BOOST_TUNE_CORE1',
    'PAD5G_TUNE_MISC_PUS_CORE1', 'LNA5G_TUNE_CORE1',
]

RE_LINE = re.compile(r'^\s*[\d.]+\s+#(\d+)\s+cpu\d+\s+(\S+)\s*(.*)$')


def radio_regs(tree):
    hdr = open(os.path.join(tree, B43, 'radio_2057.h'),
               encoding='utf-8', errors='replace').read()
    out = {}
    for name in UPLOAD_ORDER + FIVE_GHZ_REGS:
        m = re.search(r'#define\s+R2057_%s\s+(0x[0-9a-fA-F]+)' % name, hdr)
        if not m:
            sys.exit('R2057_%s non trovato in radio_2057.h' % name)
        out[name] = int(m.group(1), 0)
    return out


def freq_of(chan):
    if chan == 14:
        return 2484
    return 2412 + (chan - 1) * 5


def parse_trace(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_LINE.match(line.rstrip('\n'))
        if not m:
            continue
        kv = dict(re.findall(r'(\w+)=(\S+)', m.group(3)))
        out.append((int(m.group(1)), m.group(2), kv))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('trace')
    ap.add_argument('--tree', required=True)
    ap.add_argument('--window', type=int, default=400,
                    help='record da esaminare dopo ogni CHANSPEC')
    args = ap.parse_args()

    regs = radio_regs(args.tree)
    by_addr = {v: k for k, v in regs.items()}
    entries = {e['freq']: e for e in
               parse_b43(os.path.join(args.tree, B43, 'radio_2057.c'))}
    recs = parse_trace(args.trace)
    index = {seq: i for i, (seq, _, _) in enumerate(recs)}

    switches = [(seq, int(kv['ch'])) for seq, op, kv in recs
                if op == 'CHANSPEC' and 'ch' in kv]
    print('%d cambi canale nel trace\n' % len(switches))

    total_bad = 0
    for seq, chan in switches:
        freq = freq_of(chan)
        entry = entries.get(freq)
        start = index[seq]
        writes = []
        for i in range(start + 1, min(start + 1 + args.window, len(recs))):
            s, op, kv = recs[i]
            if op == 'CHANSPEC':
                break
            if op != 'RAD.WR':
                continue
            addr = int(kv.get('addr', '0'), 0)
            if addr in by_addr:
                writes.append((by_addr[addr], int(kv.get('val', '0'), 0)))

        got = [(n, v) for n, v in writes if n in UPLOAD_ORDER]
        extra = [(n, v) for n, v in writes if n in FIVE_GHZ_REGS]

        if entry is None:
            print('ch%-3d %4d MHz  nessuna entry in b43' % (chan, freq))
            total_bad += 1
            continue

        want = [(n, entry['radio'][f]) for n, f in zip(UPLOAD_ORDER, FIELDS_2G)]
        if got == want:
            zeros = all(v == 0 for _, v in extra)
            print('ch%-3d %4d MHz  18/18 identici e in ordine'
                  '   (+%d registri 5 GHz%s)'
                  % (chan, freq, len(extra), ', tutti a 0' if zeros else ''))
            continue

        total_bad += 1
        print('ch%-3d %4d MHz  DIFF' % (chan, freq))
        if [n for n, _ in got] != [n for n, _ in want]:
            print('   ordine/insieme diverso')
            print('   trace : %s' % ' '.join(n for n, _ in got))
            print('   kernel: %s' % ' '.join(n for n, _ in want))
        for (gn, gv), (wn, wv) in zip(got, want):
            if gn == wn and gv != wv:
                print('   %-32s kernel=0x%02x trace=0x%02x' % (gn, wv, gv))

    print('\n%d cambi canale, %d con differenze' % (len(switches), total_bad))
    return 1 if total_bad else 0


if __name__ == '__main__':
    sys.exit(main())
