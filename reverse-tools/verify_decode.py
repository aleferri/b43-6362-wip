#!/usr/bin/env python3
"""Verifica che il testo decodificato porti tutto quello che c'era nel binario.

Serve a una cosa sola: poter buttare via il .raw senza perdere informazione. Il
testo e' la forma utile (leggibile, diffabile, grepabile, ed e' quella che
mangiano gli altri strumenti); il binario ha valore solo se il testo perde
qualcosa. Questo script lo misura invece di assumerlo.

Ricostruisce i campi (ts, seq, cpu, op, addr, val, aux) dalle righe decodificate
e li confronta con i record del binario, campo per campo, e riporta le
differenze per op.

    ./verify_decode.py trace.raw flow.decoded
"""

import re
import struct
import sys

REC = struct.Struct(">QIIIIBBH")
SZ = REC.size

OPS = {}  # nome -> codice, ricavato dal decoder per non duplicare la tabella


def load_ops(path='decode-wl-diag.py'):
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, path), encoding='utf-8').read()
    body = src[src.index('OPS = {'):]
    body = body[:body.index('}') + 1]
    for code, name in re.findall(r'(\d+):\s*"([^"]+)"', body):
        OPS[name] = int(code)


RE_LINE = re.compile(r'^\s*([\d.]+)\s+#(\d+)\s+cpu(\d+)\s+(\S+)\s*(.*)$')


def parse_text(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_LINE.match(line.rstrip('\n'))
        if not m:
            continue
        kv = {}
        for k, v in re.findall(r'(\w+)=(\S+)', m.group(5)):
            kv[k] = v.lstrip('#')      # 'for=#123' e' un numero di record
        out.append(dict(ts=m.group(1), seq=int(m.group(2)), cpu=int(m.group(3)),
                        op=m.group(4), kv=kv, raw=m.group(5)))
    return out


def num(kv, *keys):
    for k in keys:
        v = kv.get(k)
        if v is None or v == 'UNDEFINED':
            continue
        try:
            return int(v, 0)
        except ValueError:
            pass
    return None


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    load_ops()
    blob = open(sys.argv[1], 'rb').read()
    text = parse_text(sys.argv[2])

    n = len(blob) // SZ
    if n != len(text):
        print('record binari %d, righe decodificate %d' % (n, len(text)))
    lost = {}
    checked = 0

    for i in range(min(n, len(text))):
        ts, seq, addr, val, aux, op, cpu, pad = REC.unpack(blob[i * SZ:(i + 1) * SZ])
        t = text[i]
        name = t['op']
        problems = []

        if OPS.get(name, -1) != op:
            problems.append('op')
        if t['seq'] != seq:
            problems.append('seq')
        if t['cpu'] != cpu:
            problems.append('cpu')
        if abs(float(t['ts']) - ts / 1e9) > 5e-7:
            problems.append('ts')
        if pad:
            problems.append('pad')

        # addr, val e aux sotto uno qualsiasi dei nomi semantici usati
        seen = set(num(t['kv'], k) for k in t['kv'])
        for field, value in (('addr', addr), ('val', val), ('aux', aux)):
            if value == 0:
                continue                      # zero: niente da perdere
            if value in seen:
                continue
            if field == 'val' and 'UNDEFINED' in t['raw']:
                continue                      # read: il tracer non lo cattura
            if name == 'CHANSPEC' and field == 'addr':
                continue                      # reso espanso, raw= incluso
            problems.append(field)

        checked += 1
        if problems:
            lost.setdefault((name, tuple(sorted(set(problems)))), 0)
            lost[(name, tuple(sorted(set(problems))))] += 1

    print('%d record confrontati' % checked)
    if not lost:
        print('nessuna perdita: il testo copre tutti i campi non nulli')
        return 0
    print('campi non rappresentati nel testo:')
    for (name, fields), count in sorted(lost.items(), key=lambda kv: -kv[1]):
        print('  %-10s %-22s %d record' % (name, ','.join(fields), count))
    return 1


if __name__ == '__main__':
    sys.exit(main())
