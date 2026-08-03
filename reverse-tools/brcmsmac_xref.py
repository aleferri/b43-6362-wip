#!/usr/bin/env python3
"""Xref delle funzioni brcmsmac che discriminano radio rev 8 / N-PHY rev 8.

brcmsmac e' in-tree e GPL: e' il riferimento legittimo per capire cosa il
vendor programma su questa combinazione PHY/radio, e per ogni buco trovato da
`check_gaps.py` serve sapere quale funzione brcmsmac guardare.

Uso:
    ./brcmsmac_xref.py --tree ~/src/linux
    ./brcmsmac_xref.py --tree ~/src/linux --radio-rev 8 --format md
"""

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfuncs  # noqa: E402

PHY_N = 'drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c'


def patterns(radio_rev, phy_rev):
    return [
        ('radiorev', re.compile(r'pubpi\.radiorev\s*==\s*%d\b' % radio_rev)),
        ('radiorev-ge', re.compile(r'pubpi\.radiorev\s*>=\s*%d\b' % radio_rev)),
        ('phyrev', re.compile(r'NREV_IS\(\s*pi->pubpi\.phy_rev\s*,\s*%d\s*\)' % phy_rev)),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tree', required=True)
    ap.add_argument('--radio-rev', type=int, default=8)
    ap.add_argument('--phy-rev', type=int, default=8)
    ap.add_argument('--format', choices=['text', 'md'], default='text')
    args = ap.parse_args()

    path = os.path.join(args.tree, PHY_N)
    if not os.path.exists(path):
        sys.exit('manca %s' % path)

    lines, owner = cfuncs.index_functions(path)
    hits = collections.defaultdict(lambda: collections.Counter())
    first = {}

    for n, line in enumerate(lines, 1):
        for kind, rx in patterns(args.radio_rev, args.phy_rev):
            if rx.search(line):
                fn = owner.get(n) or '(fuori funzione)'
                hits[fn][kind] += 1
                first.setdefault(fn, n)

    rows = sorted(hits.items(), key=lambda kv: first[kv[0]])

    if args.format == 'md':
        print('| funzione brcmsmac | prima riga | radiorev==%d | NREV_IS(rev,%d) |'
              % (args.radio_rev, args.phy_rev))
        print('|---|---|---|---|')
        for fn, c in rows:
            print('| `%s` | %d | %d | %d |'
                  % (fn, first[fn], c['radiorev'] + c['radiorev-ge'], c['phyrev']))
    else:
        for fn, c in rows:
            print('%5d  %-52s radiorev=%d phyrev=%d'
                  % (first[fn], fn, c['radiorev'] + c['radiorev-ge'], c['phyrev']))

    print('\n%d funzioni' % len(rows), file=sys.stderr)


if __name__ == '__main__':
    main()
