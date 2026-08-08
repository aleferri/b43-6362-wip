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

# Il numero di record c'e' nel trace vendor e non nell'output dell'harness,
# che deve restare mangiabile da compare.py: qui e' opzionale.
RE_LINE = re.compile(r'^\s*(?:[\d.]+\s+)?(?:#(\d+)\s+)?cpu\d+\s+(\S+)\s*(.*)$')
ADDR_REG, DATA_LO, DATA_HI = 0x72, 0x73, 0x74


def parse(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_LINE.match(line.rstrip('\n'))
        if not m:
            continue
        kv = dict(re.findall(r'(\w+)=(\S+)', m.group(3)))
        out.append(dict(seq=int(m.group(1)) if m.group(1) else len(out) + 1,
                        op=m.group(2), kv=kv))
    return out


def as_int(kv, key):
    v = kv.get(key)
    if v is None or v == 'UNDEFINED':
        return None
    try:
        return int(v, 0)
    except ValueError:
        return None


def retvals(records):
    """RETVAL indicizzati per il record cui si riferiscono.

    Nel trace vendor una read porta `val=UNDEFINED` e il valore arriva in un
    record RETVAL a parte; nell'output dell'harness il valore e' sulla read
    stessa. Le due forme si trattano insieme.
    """
    out = {}
    for r in records:
        if r['op'] == 'RETVAL':
            ref = r['kv'].get('for', '')
            if ref.startswith('#'):
                out[int(ref[1:])] = as_int(r['kv'], 'val')
    return out


def collect_reads(records):
    """Ogni TBL.RD con i valori serviti, ricostruiti dalle PHY.RD successive.

    Sulle read la porta dati bassa viene prima di quella alta, al contrario
    delle write: qui l'ordine si segue invece di assumerlo.
    """
    rv = retvals(records)
    tables = []
    i = 0
    while i < len(records):
        r = records[i]
        if r['op'] != 'TBL.RD':
            i += 1
            continue
        tbl = dict(seq=r['seq'], kind='RD', id=as_int(r['kv'], 'id'),
                   off=as_int(r['kv'], 'off'), len=as_int(r['kv'], 'len'),
                   values=[], width=16, addr_seen=None)
        pending_lo = None
        j = i + 1
        while j < len(records):
            n = records[j]
            if n['op'] == 'RETVAL':
                j += 1
                continue
            if n['op'] == 'PHY.WR' and as_int(n['kv'], 'addr') == ADDR_REG:
                if tbl['addr_seen'] is not None:
                    break
                tbl['addr_seen'] = as_int(n['kv'], 'val')
                j += 1
                continue
            if n['op'] != 'PHY.RD':
                break
            addr = as_int(n['kv'], 'addr')
            val = as_int(n['kv'], 'val')
            if val is None:
                val = rv.get(n['seq'])
            if addr == DATA_LO:
                if pending_lo is not None:
                    tbl['values'].append(pending_lo)
                pending_lo = val
            elif addr == DATA_HI:
                tbl['width'] = 32
                tbl['values'].append(((val or 0) << 16) | (pending_lo or 0))
                pending_lo = None
            else:
                break
            j += 1
        if pending_lo is not None:
            tbl['values'].append(pending_lo)
        tables.append(tbl)
        i = j
    return tables


def collect(records):
    """Ogni TBL.WR con i valori ricostruiti dalle PHY.WR successive."""
    tables = []
    i = 0
    while i < len(records):
        r = records[i]
        if r['op'] != 'TBL.WR':
            i += 1
            continue
        tbl = dict(seq=r['seq'], kind='WR', id=as_int(r['kv'], 'id'),
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


def hw_written(records):
    """Celle la cui rilettura il mirror per porta non puo' riprodurre.

    Si percorrono write e read in ordine di record tenendo lo stato per cella,
    esattamente come fa il mirror dell'harness. Una read che rende un valore
    diverso da quello che l'ultima write per porta ci ha messo -- o che rende un
    valore su una cella che nessuna write per porta ha mai toccato -- e' una cella
    il cui contenuto arriva da qualcos'altro: il motore di calibrazione, o il
    download statico fuori dalla finestra. Per quelle un piano e' l'unica fonte
    onesta, perche' il mirror non ha modo di saperle.

    Le altre non le vuole nessuno: se la write per porta c'e', il valore giusto e'
    quello che la tabella contiene, ed e' quello che il mirror rende.
    """
    events = []
    for t in collect(records):
        events.append((t['seq'], 'WR', t))
    for t in collect_reads(records):
        events.append((t['seq'], 'RD', t))
    events.sort(key=lambda e: (e[0], e[1]))

    state = {}
    cells = {}
    for seq, kind, t in events:
        if t['id'] is None or t['off'] is None:
            continue
        for k, val in enumerate(t['values']):
            key = (t['id'], t['off'] + k)
            if kind == 'WR':
                state[key] = val
                continue
            if val is None:
                continue
            if state.get(key) != val:
                c = cells.setdefault(key, dict(n=0, first=seq, vals=[],
                                               mai_scritta=key not in state))
                c['n'] += 1
                c['vals'].append(val)
            state[key] = val
    return cells


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
    ap.add_argument('--cell', metavar='ID:OFF',
                    help='storia di una sola cella: ogni accesso, read e write,'
                         ' in ordine di record, col valore che quella cella'
                         ' aveva o prendeva')
    ap.add_argument('--hw-written', action='store_true',
                    help='celle la cui rilettura il mirror per porta non puo'
                         ' riprodurre, cioe\' quelle che scrive qualcos\'altro:'
                         ' sono le sole per cui un piano per cella e\' una fonte'
                         ' e non un suggerimento')
    args = ap.parse_args()

    records = parse(args.trace)
    if args.range:
        lo, hi = args.range
        records = [r for r in records if lo <= r['seq'] <= hi]

    if args.cell:
        want_id, want_off = (int(x, 0) for x in args.cell.split(':'))
        hist = []
        for t in collect(records) + collect_reads(records):
            if t['id'] != want_id or t['off'] is None:
                continue
            k = want_off - t['off']
            if k < 0 or k >= max(len(t['values']), t['len'] or 0):
                continue
            val = t['values'][k] if k < len(t['values']) else None
            hist.append((t['seq'], t['kind'], t['len'] or 0, val))
        hist.sort()
        prev = None
        for seq, kind, ln, val in hist:
            shown = '?' if val is None else '0x%04x' % val
            # Una write che non cambia il valore non e' un cambio di stato, e
            # distinguerle e' il punto di guardare una cella sola.
            mark = ''
            if kind == 'WR':
                mark = '  <-- cambia' if val != prev else '  (idem)'
                if val is not None:
                    prev = val
            elif prev is None and val is not None:
                prev = val
            print('#%-6d %s  len %-3d %s%s' % (seq, kind, ln, shown, mark))
        print('\n%d accessi alla cella tbl %d off 0x%x' % (len(hist), want_id,
                                                           want_off))
        return

    if args.hw_written:
        cells = hw_written(records)
        if args.id is not None:
            cells = {k: v for k, v in cells.items() if k[0] in args.id}
        per_tbl = {}
        for (tid, off), c in sorted(cells.items()):
            per_tbl.setdefault(tid, []).append((off, c))
        tot = 0
        for tid in sorted(per_tbl):
            offs = per_tbl[tid]
            tot += sum(c['n'] for _, c in offs)
            print('tbl %2d: %d celle, %d riletture non riproducibili'
                  % (tid, len(offs), sum(c['n'] for _, c in offs)))
            for off, c in offs:
                vals = ' '.join('0x%04x' % v for v in c['vals'][:8])
                if len(c['vals']) > 8:
                    vals += ' ...'
                print('    off 0x%03x  x%-3d  #%-6d %s%s'
                      % (off, c['n'], c['first'], vals,
                         '  (mai scritta per porta)' if c['mai_scritta'] else ''))
        print('\n%d celle, %d riletture' % (len(cells), tot))
        return

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
