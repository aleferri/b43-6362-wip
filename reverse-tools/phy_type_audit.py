#!/usr/bin/env python3
"""Dove b43 tratta la PHY G e non la N.

Il driver e' nato per le PHY B/G e la N e' arrivata dopo, quindi ci sono punti in
cui un ramo esiste solo per G, o in cui una catena `if/else if` sui tipi di PHY
non ha il caso N. Sul BCM6362 quei punti sono comportamento assente o sbagliato,
e finche' non sono elencati non si sa nemmeno quanti sono.

Lo strumento raggruppa le occorrenze di `B43_PHYTYPE_*` per costrutto: per ogni
`if`/`else if`/`switch` che discrimina sul tipo di PHY raccoglie i tipi citati e
segnala i costrutti dove **G compare e N no**. Salta i file per-PHY
(`phy_g.c`, `phy_n.c`, ...), dove e' ovvio e giusto che si parli di un tipo solo.

E' un'euristica testuale, non un'analisi di flusso: raggruppa per prossimita' di
righe dentro la stessa funzione. Un risultato va letto, non contato.

    ./phy_type_audit.py --tree ~/src/linux
    ./phy_type_audit.py --tree ~/src/linux --all
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfuncs  # noqa: E402

B43 = 'drivers/net/wireless/broadcom/b43'

# I file di una PHY specifica: parlare di un tipo solo la' e' corretto.
PER_PHY = re.compile(r'^(phy_(g|n|a|b|lp|ht|lcn|ac)|radio_2\d{3}|tables_(nphy|lpphy|phy_g|phy_lp))\.[ch]$')

RE_TYPE = re.compile(r'B43_PHYTYPE_(\w+)')
# Un nuovo costrutto comincia qui; le righe successive che citano un tipo di PHY
# senza aprirne uno nuovo appartengono allo stesso.
RE_OPEN = re.compile(r'\b(if|else if|switch|case)\b')

GROUP_GAP = 6      # righe di distanza entro cui si resta nello stesso costrutto


def audit_file(path, name):
    lines, owner = cfuncs.index_functions(path)
    groups = []
    cur = None
    for n, raw in enumerate(lines, 1):
        line = re.sub(r'/\*.*?\*/', ' ', raw)
        types = RE_TYPE.findall(line)
        if not types:
            continue
        fn = owner.get(n) or '(fuori funzione)'
        if (cur and cur['fn'] == fn and n - cur['last'] <= GROUP_GAP):
            cur['types'].update(types)
            cur['last'] = n
            cur['lines'].append((n, raw.strip()))
            continue
        cur = dict(file=name, fn=fn, first=n, last=n, types=set(types),
                   lines=[(n, raw.strip())])
        groups.append(cur)
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tree', required=True)
    ap.add_argument('--all', action='store_true',
                    help='elenca tutti i costrutti, non solo quelli senza N')
    ap.add_argument('--context', action='store_true',
                    help='stampa le righe')
    args = ap.parse_args()

    root = os.path.join(args.tree, B43)
    if not os.path.isdir(root):
        sys.exit('manca %s' % root)

    flagged, total = [], 0
    for name in sorted(os.listdir(root)):
        if not name.endswith(('.c', '.h')) or PER_PHY.match(name):
            continue
        for g in audit_file(os.path.join(root, name), name):
            total += 1
            has_g = 'G' in g['types']
            has_n = 'N' in g['types']
            if args.all or (has_g and not has_n):
                flagged.append(g)

    print('%d costrutti che discriminano sul tipo di PHY, fuori dai file '
          'per-PHY' % total)
    print('%d %s\n' % (len(flagged),
                       'elencati' if args.all else 'citano G e non N'))
    for g in flagged:
        print('%-14s %-34s righe %d-%d   tipi: %s'
              % (g['file'], g['fn'], g['first'], g['last'],
                 ' '.join(sorted(g['types']))))
        if args.context:
            for n, text in g['lines']:
                print('    %5d  %s' % (n, text[:96]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
