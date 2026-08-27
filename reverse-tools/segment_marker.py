#!/usr/bin/env python3
"""Segmenta due trace su un marcatore e confronta i segmenti.

Serve quando la STRUTTURA di una macro operazione e' quella giusta e si vuole
sapere quale pezzo manca, invece di guardare un totale. Il marcatore e' un'op che
il codice emette una volta per giro di quella struttura, e i segmenti che ne
escono si contano e si confrontano uno a uno.

Il marcatore puo' essere una SEQUENZA, e non e' un vezzo: una singola op quasi mai
identifica una struttura. Il caso per cui e' nato lo mostra. La cal periodica del
riferimento apre ogni fase leggendo il tx gain da 7/0x110 e subito dopo spegne il
controllo di potenza; ma quella stessa cella la legge anche get_tx_gain(), con la
condizione OPPOSTA su txpwrctrl. Contare la sola lettura somma due cose diverse e
il numero non vuol dire niente.

La coppia invece distingue: la lettura seguita, entro poche op, dalla scrittura che
apre lo svuotamento della tabella di potenza.

    segment_marker.py \\
        --marker 'TBL\\.RD\\s+id=0x0007 off=0x0110 len=2' \\
        --marker 'PHY\\.WR\\s+addr=0x0072 val=0x6840' \\
        --within 12 --range 132 26100 \\
        router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded /tmp/port.out

Non appaia le op e non calcola percentuali: quello lo fa phase_compare.py. Qui si
guarda solo quanti segmenti ci sono, quanto sono lunghi e di che op sono fatti,
che e' cio' che serve per decidere dove la struttura non combacia.
"""

import argparse
import re
import sys

FAMILY = re.compile(r'(PHY|RAD|MMIO|TBL)\.(RD|WR|MOD|AND|OR)')
SEQ = re.compile(r'#(\d+)')


def match_at(lines, i, marks, within):
    """Vero se la sequenza di marcatori parte alla riga i.

    Il primo deve stare esattamente li'; gli altri in ordine entro `within` righe
    dal precedente, non necessariamente adiacenti - fra un'op e la successiva il
    codice ne emette altre e la sequenza non e' contigua.
    """
    if not marks[0].search(lines[i]):
        return False
    pos = i
    for mk in marks[1:]:
        found = None
        for j in range(pos + 1, min(pos + 1 + within, len(lines))):
            if mk.search(lines[j]):
                found = j
                break
        if found is None:
            return False
        pos = found
    return True


def segments(path, marks, within, lo, hi):
    """I segmenti, ognuno dal marcatore incluso fino al successivo escluso.

    Cio' che precede il primo marcatore non e' un segmento e viene scartato: non
    appartiene a nessun giro della struttura.
    """
    lines, seqs_all = [], []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = SEQ.search(line)
        n = int(m.group(1)) if m else None
        if lo is not None and (n is None or not (lo <= n <= hi)):
            continue
        lines.append(line)
        seqs_all.append(n)

    cuts, seqs = [], []
    for i in range(len(lines)):
        if match_at(lines, i, marks, within):
            cuts.append(i)
            seqs.append(seqs_all[i])
    out = []
    for i, c in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else len(lines)
        out.append((seqs[i], lines[c:end]))
    return out


def profile(seg):
    counts = {}
    for line in seg:
        m = FAMILY.search(line)
        if m:
            counts[m.group(0)] = counts.get(m.group(0), 0) + 1
    return counts


def top(counts, n=3):
    return ' '.join('%s:%d' % (k.replace('PHY.', ''), v)
                    for k, v in sorted(counts.items(), key=lambda x: -x[1])[:n])


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('trace', nargs=2, help='il trace di riferimento e quello da confrontare')
    ap.add_argument('--marker', required=True, action='append',
                    help='regex dell\'op che apre un giro della struttura. '
                         'Ripetibile: i marcatori devono comparire in ordine '
                         'entro --within righe l\'uno dall\'altro, e il giro si '
                         'apre dove comincia il primo')
    ap.add_argument('--within', type=int, default=12,
                    help='quante righe al massimo fra un marcatore e il '
                         'successivo (default 12)')
    ap.add_argument('--range', nargs=2, type=int, metavar=('DA', 'A'),
                    help='limita ai record in questo intervallo di seq, e vale '
                         'per il primo trace: il secondo di solito non ha una '
                         'numerazione confrontabile')
    args = ap.parse_args()

    marks = [re.compile(m) for m in args.marker]
    lo, hi = args.range if args.range else (None, None)
    a = segments(args.trace[0], marks, args.within, lo, hi)
    b = segments(args.trace[1], marks, args.within, None, None)

    print('%s: %d segmenti' % (args.trace[0].split('/')[-1], len(a)))
    print('%s: %d segmenti' % (args.trace[1].split('/')[-1], len(b)))
    if len(a) != len(b):
        print('\nI segmenti sono %d contro %d: la struttura non combacia, e la '
              'differenza\ne\' quella da guardare prima di qualunque numero sulle '
              'op.' % (len(a), len(b)))
    print()
    print('%-4s %8s %-28s %8s %-28s' % ('#', 'op', 'primo trace', 'op', 'secondo'))
    for i in range(max(len(a), len(b))):
        sa = a[i] if i < len(a) else (None, [])
        sb = b[i] if i < len(b) else (None, [])
        marca = ('#%d' % sa[0]) if sa[0] is not None else '-'
        print('%-4s %8d %-28s %8d %-28s'
              % (marca, len(sa[1]), top(profile(sa[1])),
                 len(sb[1]), top(profile(sb[1]))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
