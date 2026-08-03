#!/usr/bin/env python3
"""Mappa `chan_info_nphyrev8_2057_rev8` del blob `wl` sulle entry chantab di b43.

Il record vendor e' 44 byte:

    u16 chan          numero di canale
    u16 freq          MHz
    u8  radio[28]     gli stessi campi, nello stesso ordine, di
                      struct b43_nphy_chantabent_rev7 (b43/radio_2057.h)
    u16 phy_regs[6]   struct b43_phy_n_sfo_cfg

Il layout non e' dichiarato da nessuna parte: 44 byte e la posizione di `freq`
vengono dal blob (le frequenze note compaiono a passo 44, offset +2), il resto
e' l'ipotesi che b43 abbia derivato la sua struct da quella del vendor. La
verifica la fa il confronto: se l'ordine fosse sbagliato, i 18 campi 2.4 GHz
non combacerebbero con le 14 entry di b43.

Uso:
    ./chantab_from_blob.py BLOB --tree ~/src/linux --verify
    ./chantab_from_blob.py BLOB --list
    ./chantab_from_blob.py BLOB --tree ~/src/linux --emit-c --band 5g
"""

import argparse
import os
import re
import signal
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blob_tables import Elf32BE  # noqa: E402

SYMBOL = 'chan_info_nphyrev8_2057_rev8'
RECORD = 44
B43_ARRAY = 'b43_nphy_chantab_phy_rev8_radio_rev8'

# Ordine dei 28 u8, da struct b43_nphy_chantabent_rev7.
RADIO_FIELDS = [
    'vcocal_countval0', 'vcocal_countval1', 'rfpll_refmaster_sparextalsize',
    'rfpll_loopfilter_r1', 'rfpll_loopfilter_c2', 'rfpll_loopfilter_c1',
    'cp_kpd_idac', 'rfpll_mmd0', 'rfpll_mmd1', 'vcobuf_tune',
    'logen_mx2g_tune', 'logen_mx5g_tune', 'logen_indbuf2g_tune',
    'logen_indbuf5g_tune',
    'txmix2g_tune_boost_pu_core0', 'pad2g_tune_pus_core0',
    'pga_boost_tune_core0', 'txmix5g_boost_tune_core0',
    'pad5g_tune_misc_pus_core0', 'lna2g_tune_core0', 'lna5g_tune_core0',
    'txmix2g_tune_boost_pu_core1', 'pad2g_tune_pus_core1',
    'pga_boost_tune_core1', 'txmix5g_boost_tune_core1',
    'pad5g_tune_misc_pus_core1', 'lna2g_tune_core1', 'lna5g_tune_core1',
]

# Sottoinsieme e ordine di struct b43_nphy_chantabent_rev7_2g, cioe' gli
# argomenti di RADIOREGS7_2G() nell'array C.
FIELDS_2G = [
    'vcocal_countval0', 'vcocal_countval1', 'rfpll_refmaster_sparextalsize',
    'rfpll_loopfilter_r1', 'rfpll_loopfilter_c2', 'rfpll_loopfilter_c1',
    'cp_kpd_idac', 'rfpll_mmd0', 'rfpll_mmd1', 'vcobuf_tune',
    'logen_mx2g_tune', 'logen_indbuf2g_tune',
    'txmix2g_tune_boost_pu_core0', 'pad2g_tune_pus_core0', 'lna2g_tune_core0',
    'txmix2g_tune_boost_pu_core1', 'pad2g_tune_pus_core1', 'lna2g_tune_core1',
]


def parse_blob(elf):
    data = elf.symbol_bytes(SYMBOL)
    if len(data) % RECORD:
        sys.exit('%s: %d byte non multipli di %d' % (SYMBOL, len(data), RECORD))
    out = []
    for off in range(0, len(data), RECORD):
        rec = data[off:off + RECORD]
        chan, freq = struct.unpack_from('>HH', rec, 0)
        radio = dict(zip(RADIO_FIELDS, rec[4:32]))
        phy = list(struct.unpack_from('>6H', rec, 32))
        out.append(dict(chan=chan, freq=freq, radio=radio, phy=phy))
    return out


def parse_b43(path):
    """Le entry di b43: freq + 18 argomenti di RADIOREGS7_2G + 6 di PHYREGS."""
    text = open(path, encoding='utf-8', errors='replace').read()
    start = text.index('%s[] = {' % B43_ARRAY)
    body = text[start:text.index('\n};', start)]
    out = []
    pattern = (r'\.freq\s*=\s*(\d+),\s*RADIOREGS7_2G\(([^)]*)\)\s*,'
               r'\s*PHYREGS\(([^)]*)\)')
    for m in re.finditer(pattern, body, re.S):
        radio = [int(v, 0) for v in m.group(2).split(',')]
        phy = [int(v, 0) for v in m.group(3).split(',')]
        if len(radio) != 18 or len(phy) != 6:
            sys.exit('entry %s: %d radio / %d phy, attesi 18 / 6'
                     % (m.group(1), len(radio), len(phy)))
        out.append(dict(freq=int(m.group(1)),
                        radio=dict(zip(FIELDS_2G, radio)), phy=phy))
    return out


def cmd_list(records):
    bands = {}
    for r in records:
        bands.setdefault('2g' if r['freq'] < 3000 else '5g', []).append(r)
    for band in sorted(bands):
        rs = bands[band]
        print('%s: %d record, %d..%d MHz'
              % (band, len(rs), rs[0]['freq'], rs[-1]['freq']))
    print('\ntotale %d record da %d byte' % (len(records), RECORD))


def cmd_verify(records, entries):
    by_freq = {r['freq']: r for r in records}
    print('blob    %s -> %d record' % (SYMBOL, len(records)))
    print('kernel  %s -> %d entry' % (B43_ARRAY, len(entries)))

    missing = [e['freq'] for e in entries if e['freq'] not in by_freq]
    if missing:
        print('\nfrequenze del kernel assenti nel blob: %s' % missing)
        return 1

    bad = []
    for e in entries:
        r = by_freq[e['freq']]
        for name in FIELDS_2G:
            want, got = e['radio'][name], r['radio'][name]
            if want != got:
                bad.append((e['freq'], name, want, got))
        for i, (want, got) in enumerate(zip(e['phy'], r['phy'])):
            if want != got:
                bad.append((e['freq'], 'phy_regs[%d]' % i, want, got))

    checked = len(entries) * (len(FIELDS_2G) + 6)
    if not bad:
        print('\nOK: %d campi su %d canali identici' % (checked, len(entries)))
        return 0

    print('\nDIFF: %d campi su %d divergono' % (len(bad), checked))
    for freq, name, want, got in bad[:40]:
        print('  %d %-32s kernel=0x%04x blob=0x%04x' % (freq, name, want, got))
    if len(bad) > 40:
        print('  ... altri %d' % (len(bad) - 40))
    return 1


def cmd_emit_c(records, band):
    """Emette le entry come array C nel formato di b43 (rev7 dual band)."""
    sel = [r for r in records
           if (r['freq'] < 3000) == (band == '2g')]
    print('/* generato da chantab_from_blob.py, sorgente: %s */' % SYMBOL)
    print('static const struct b43_nphy_chantabent_rev7 GENERATED[] = {')
    for r in sel:
        print('\t{')
        print('\t\t.freq\t\t\t= %d,' % r['freq'])
        vals = ['0x%02x' % r['radio'][f] for f in RADIO_FIELDS]
        print('\t\tRADIOREGS7(%s,' % ', '.join(vals[:8]))
        for i in range(8, 24, 8):
            print('\t\t\t   %s,' % ', '.join(vals[i:i + 8]))
        print('\t\t\t   %s),' % ', '.join(vals[24:]))
        print('\t\tPHYREGS(%s),' % ', '.join('0x%04x' % v for v in r['phy']))
        print('\t},')
    print('};')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('blob')
    ap.add_argument('--tree', help='radice del sorgente kernel')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--emit-c', action='store_true')
    ap.add_argument('--band', choices=['2g', '5g'], default='2g')
    args = ap.parse_args()

    records = parse_blob(Elf32BE(args.blob))

    if args.list:
        cmd_list(records)
        return

    if args.emit_c:
        cmd_emit_c(records, args.band)
        return

    if args.verify:
        if not args.tree:
            raise SystemExit('--verify richiede --tree')
        path = os.path.join(args.tree, 'drivers/net/wireless/broadcom/b43',
                            'radio_2057.c')
        sys.exit(cmd_verify(records, parse_b43(path)))

    ap.print_help()


if __name__ == '__main__':
    # l'output di --emit-c finisce spesso in `head`: SIGPIPE di default invece
    # del traceback di Python.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
