#!/usr/bin/env python3
"""Copertura del dispatch per (phy rev, radio rev) nei sorgenti b43.

Scansiona i file b43 indicati, individua le funzioni che discriminano su
`phy->radio_rev` o `phy->rev`, raccoglie i valori citati (case, range,
confronti `==`/`>=`) e segnala quelle che non citano la revisione target.
Segnala anche le funzioni con corpo vuoto (soli commenti), che nel driver
sono gli stub `TODO`.

Il risultato e' un indizio di dove guardare, non una prova: una funzione puo'
legittimamente non citare la revisione perche' il valore ci arriva per
fallthrough o perche' il blocco e' rev-invariante. Va letta a mano.

Uso:
    ./check_gaps.py --tree ~/src/linux --radio-rev 8 --phy-rev 8
    ./check_gaps.py --tree ~/src/linux --format md > /tmp/gap.md
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfuncs  # noqa: E402

B43 = 'drivers/net/wireless/broadcom/b43'
DEFAULT_FILES = ['phy_n.c', 'radio_2057.c', 'tables_nphy.c']

RE_CASE_RANGE = re.compile(r'\bcase\s+(\d+)\s*\.\.\.\s*(\d+)\s*:')
RE_CASE = re.compile(r'\bcase\s+(\d+)\s*:')
RE_CMP = re.compile(r'\b(?:phy->)?(radio_rev|rev)\s*(==|>=|<=|>|<|!=)\s*(\d+)')
RE_SWITCH = re.compile(r'switch\s*\(\s*(?:dev->)?phy(?:->|\.)(radio_rev|rev)\s*\)')
RE_TOUCH = re.compile(r'\bphy(?:->|\.)(radio_rev|rev)\b')


def body(lines, span):
    first, last = span
    return ''.join(lines[first - 1:last])


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    return text


def collect(text, field):
    """Valori citati per `field`, e copertura del target via disuguaglianze.

    Ritorna (valori_esatti, modi, predicati) dove `predicati` sono le
    disuguaglianze trovate, come coppie (operatore, valore).
    """
    values = set()
    modes = set()
    preds = set()

    for chunk in re.finditer(RE_SWITCH, text):
        if chunk.group(1) != field:
            continue
        modes.add('switch')
        tail = text[chunk.end():]
        depth = 0
        end = len(tail)
        for i, ch in enumerate(tail):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        block = tail[:end]
        for lo, hi in RE_CASE_RANGE.findall(block):
            values.update(range(int(lo), int(hi) + 1))
        for val in RE_CASE.findall(block):
            values.add(int(val))

    for name, op, val in RE_CMP.findall(text):
        if name != field:
            continue
        modes.add(op)
        if op == '==':
            values.add(int(val))
        elif op != '!=':
            preds.add((op, int(val)))

    return values, modes, preds


def covered(target, values, preds):
    if target in values:
        return True
    for op, val in preds:
        if op == '>=' and target >= val:
            return True
        if op == '>' and target > val:
            return True
        if op == '<=' and target <= val:
            return True
        if op == '<' and target < val:
            return True
    return False


def is_stub(text):
    inner = text[text.find('{') + 1:text.rfind('}')]
    return strip_comments(inner).strip() == ''


def scan(path, field, target):
    lines, _ = cfuncs.index_functions(path)
    spans = cfuncs.function_ranges(path)
    rows = []
    for fn, span in sorted(spans.items(), key=lambda kv: kv[1][0]):
        raw = body(lines, span)
        text = strip_comments(raw)
        if not RE_TOUCH.search(text):
            if is_stub(raw):
                rows.append((span[0], fn, 'stub', set(), set()))
            continue
        values, modes, preds = collect(text, field)
        if not modes:
            # tocca la revisione ma senza confronti numerici: niente da dire
            continue
        state = 'ok' if covered(target, values, preds) else 'assente'
        if is_stub(raw):
            state = 'stub'
        shown = sorted(values) + ['%s%d' % (op, val) for op, val in sorted(preds)]
        rows.append((span[0], fn, state, shown, sorted(modes)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tree', required=True, help='radice del sorgente kernel')
    ap.add_argument('--radio-rev', type=int, default=8)
    ap.add_argument('--phy-rev', type=int, default=8)
    ap.add_argument('--files', nargs='*', default=DEFAULT_FILES)
    ap.add_argument('--format', choices=['text', 'md'], default='text')
    ap.add_argument('--all', action='store_true',
                    help='mostra anche le funzioni che citano la revisione target')
    args = ap.parse_args()

    out = []
    seen = set()
    for name in args.files:
        path = os.path.join(args.tree, B43, name)
        if not os.path.exists(path):
            sys.exit('manca %s' % path)
        for field, target in (('radio_rev', args.radio_rev), ('rev', args.phy_rev)):
            for line, fn, state, values, modes in scan(path, field, target):
                if state == 'ok' and not args.all:
                    continue
                key = (name, line, fn, state)
                if state == 'stub' and key in seen:
                    continue
                seen.add(key)
                out.append(dict(file=name, line=line, fn=fn, field=field,
                                target=target, state=state,
                                values=values, modes=modes))

    if args.format == 'md':
        print('| file:riga | funzione | campo | rev citate | stato |')
        print('|---|---|---|---|---|')
        for r in out:
            vals = ', '.join(str(v) for v in r['values']) or '—'
            print('| `%s:%d` | `%s` | `%s` | %s | %s |'
                  % (r['file'], r['line'], r['fn'], r['field'], vals, r['state']))
    else:
        for r in out:
            print('%-16s %5d  %-44s %-10s target=%d %-8s citate=[%s]'
                  % (r['file'], r['line'], r['fn'] or '?', r['field'], r['target'],
                     r['state'], ', '.join(str(v) for v in r['values'])))

    stubs = sum(1 for r in out if r['state'] == 'stub')
    print('\n%d voci, di cui %d stub' % (len(out), stubs), file=sys.stderr)


if __name__ == '__main__':
    main()
