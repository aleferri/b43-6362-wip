#!/usr/bin/env python3
"""Ricostruisce le scritture di tabella N-PHY da un trace wl-diag decodificato.

Nel port N-PHY una table-op e' una sequenza di register-write: l'indirizzo va su
0x72 come `(id << 10) | offset`, i dati su 0x73 (16 bit bassi) e, per le tabelle
a 32 bit, su 0x74 (16 bit alti) prima di ogni 0x73. Il record `TBL.WR` del
tracer e' solo l'intestazione: il contenuto sta nelle `PHY.WR` che seguono.

Questo strumento le riassocia e stampa i valori, che e' cio' che serve per
scrivere una patch b43 con i numeri veri invece di quelli dedotti da brcmsmac.

Uso:
    ./trace_tables.py flow.decoded
    ./trace_tables.py flow.decoded --range 600 900 --id 0 --id 1
    ./trace_tables.py flow.decoded --id 0 --c-array lna1_gain
"""

import argparse
import re

RE_LINE = re.compile(r'^\s*(?:[\d.]+\s+)?#(\d+)\s+cpu\d+\s+(\S+)\s*(.*)$')
ADDR_REG, DATA_LO, DATA_HI = 0x72, 0x73, 0x74


def parse(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_LINE.match(line.rstrip('\n'))
        if not m:
            continue
        kv = dict(re.findall(r'(\w+)=(\S+)', m.group(3)))
        out.append(dict(seq=int(m.group(1)), op=m.group(2), kv=kv))
    return out


def as_int(kv, key):
    v = kv.get(key)
    if v is None or v == 'UNDEFINED':
        return None
    try:
        return int(v, 0)
    except ValueError:
        return None


def collect(records):
    """Ogni TBL.WR con i valori ricostruiti dalle PHY.WR successive."""
    tables = []
    i = 0
    while i < len(records):
        r = records[i]
        if r['op'] != 'TBL.WR':
            i += 1
            continue
        tbl = dict(seq=r['seq'], id=as_int(r['kv'], 'id'),
                   off=as_int(r['kv'], 'off'), len=as_int(r['kv'], 'len'),
                   values=[], width=None, addr_seen=None)
        pending_hi = None
        j = i + 1
        while j < len(records):
            n = records[j]
            if n['op'] in ('RETVAL', 'PHY.RD'):
                j += 1
                continue
            if n['op'] != 'PHY.WR':
                break
            addr = as_int(n['kv'], 'addr')
            val = as_int(n['kv'], 'val')
            if addr == ADDR_REG:
                if tbl['addr_seen'] is not None:
                    break
                tbl['addr_seen'] = val
            elif addr == DATA_HI:
                pending_hi = val
                tbl['width'] = 32
            elif addr == DATA_LO:
                if pending_hi is not None:
                    tbl['values'].append((pending_hi << 16) | val)
                    pending_hi = None
                else:
                    tbl['values'].append(val)
            else:
                break
            j += 1
        if tbl['width'] is None:
            tbl['width'] = 16
        tables.append(tbl)
        i = j
    return tables


def check(tbl):
    """Coerenza fra intestazione e dati ricostruiti."""
    problems = []
    if tbl['addr_seen'] is None:
        problems.append('nessuna scrittura di indirizzo')
    else:
        want = ((tbl['id'] or 0) << 10) | (tbl['off'] or 0)
        if tbl['addr_seen'] != want:
            problems.append('indirizzo 0x%04x != (id<<10)|off = 0x%04x'
                            % (tbl['addr_seen'], want))
    if tbl['len'] is not None and len(tbl['values']) != tbl['len']:
        problems.append('%d valori per len=%d' % (len(tbl['values']), tbl['len']))
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('trace')
    ap.add_argument('--range', nargs=2, type=int, metavar=('DA', 'A'),
                    help='limita ai record in questo intervallo di seq')
    ap.add_argument('--id', type=lambda s: int(s, 0), action='append',
                    help='mostra solo queste tabelle (ripetibile)')
    ap.add_argument('--c-array', metavar='NOME',
                    help='emette i valori come array C con questo nome')
    args = ap.parse_args()

    records = parse(args.trace)
    if args.range:
        lo, hi = args.range
        records = [r for r in records if lo <= r['seq'] <= hi]

    tables = collect(records)
    if args.id is not None:
        tables = [t for t in tables if t['id'] in args.id]

    if args.c_array:
        for n, t in enumerate(tables):
            fmt = '0x%02x' if t['width'] == 16 and max(t['values'] or [0]) < 0x100 \
                else ('0x%04x' if t['width'] == 16 else '0x%08x')
            print('/* tbl %d off 0x%x, seq #%d */' % (t['id'], t['off'], t['seq']))
            print('static const u%d %s_%d[] = {' % (t['width'], args.c_array, n))
            for i in range(0, len(t['values']), 8):
                chunk = t['values'][i:i + 8]
                print('\t' + ' '.join((fmt + ',') % v for v in chunk))
            print('};')
        return

    for t in tables:
        vals = ' '.join('0x%02x' % v if v < 0x100 else '0x%x' % v
                        for v in t['values'])
        note = check(t)
        print('#%-6d tbl %2d off 0x%03x len %2d u%-2d  %s%s'
              % (t['seq'], t['id'], t['off'], t['len'] or 0, t['width'], vals,
                 '   [!] ' + '; '.join(note) if note else ''))

    bad = sum(1 for t in tables if check(t))
    print('\n%d table-op, %d con incoerenze' % (len(tables), bad))


if __name__ == '__main__':
    main()
