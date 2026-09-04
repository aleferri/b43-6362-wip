"""Appaiamento ottimo fra due sequenze di op, con la stessa interfaccia di difflib.

`difflib.SequenceMatcher` non cerca la sottosequenza comune piu' lunga: cerca il
blocco contiguo piu' lungo e poi ricorre a destra e a sinistra. Sulle sequenze di
questo repo la differenza non e' accademica. Su `up-ch1`, con la lettura dei due
miscreg lpf in `run_samples`, difflib appaia 19454 op dove l'ottimo ne appaia
21140: lascia **1686** appaiamenti sul tavolo, perche' la cal RX IQ ripete sette
volte una sequenza quasi identica e il blocco piu' lungo che difflib aggancia per
primo puo' essere l'iterazione sbagliata. Da la' in poi un'intera iterazione resta
spaiata su entrambi i lati e il conto dice 69% dove l'ordine e' al 98%.

Il conto per blocchi e' l'unico che misura l'ORDINE, e sull'init di un PHY
l'ordine e' funzionale: le op vanno nella sequenza che l'hardware si aspetta, non
in una qualunque che tocchi le stesse celle. Quindi quel conto deve essere
ottimo, o dice cose false.

Come: LCS bit-parallel (Crochemore, Iliopoulos, Pinzon) per le lunghezze, e
Hirschberg per ricostruire l'allineamento in spazio lineare. Il bitvector che
esce da una passata di LCS codifica le lunghezze su **tutti** i prefissi del
secondo argomento -- uno zero in posizione j vale un incremento -- quindi la riga
che Hirschberg ha bisogno di leggere costa una passata sola.
"""

import collections

Block = collections.namedtuple('Block', 'a b size')


def _row(A, B):
    """Le LCS(A, B[:j]) per ogni j, in una passata."""
    m = len(B)
    if m == 0:
        return [0]
    match = {}
    for j, b in enumerate(B):
        match[b] = match.get(b, 0) | (1 << j)
    V = (1 << m) - 1
    for a in A:
        U = V & match.get(a, 0)
        V = (V + U) | (V - U)
    V &= (1 << m) - 1
    out = [0] * (m + 1)
    c = 0
    for j in range(m):
        if not (V >> j) & 1:
            c += 1
        out[j + 1] = c
    return out


def lcs_length(A, B):
    return _row(A, B)[-1]


def _pairs(A, B, off_a, off_b, out):
    """Le coppie (indice in A, indice in B) di un allineamento ottimo."""
    if not A or not B:
        return
    if len(A) == 1:
        try:
            j = B.index(A[0])
        except ValueError:
            return
        out.append((off_a, off_b + j))
        return
    mid = len(A) // 2
    left = _row(A[:mid], B)
    right = _row(A[mid:][::-1], B[::-1])
    best, split = -1, 0
    for j in range(len(B) + 1):
        s = left[j] + right[len(B) - j]
        if s > best:
            best, split = s, j
    _pairs(A[:mid], B[:split], off_a, off_b, out)
    _pairs(A[mid:], B[split:], off_a + mid, off_b + split, out)


def matching_blocks(A, B):
    """I blocchi contigui appaiati, ordinati, come `get_matching_blocks()`.

    Senza il terminatore vuoto che difflib appende: qui i chiamanti filtrano
    comunque su `size`.
    """
    pairs = []
    _pairs(list(A), list(B), 0, 0, pairs)
    blocks = []
    for a, b in pairs:
        if blocks and blocks[-1][0] + blocks[-1][2] == a \
                and blocks[-1][1] + blocks[-1][2] == b:
            blocks[-1][2] += 1
        else:
            blocks.append([a, b, 1])
    return [Block(*x) for x in blocks]


def _selftest():
    import difflib
    import random

    # 1. lunghezze contro una DP ingenua, su tutti i prefissi
    def dp(A, B):
        prev = [0] * (len(B) + 1)
        for a in A:
            cur = [0] * (len(B) + 1)
            for j, b in enumerate(B):
                cur[j + 1] = prev[j] + 1 if a == b else max(prev[j + 1], cur[j])
            prev = cur
        return prev

    for _ in range(400):
        A = [random.choice('abcd') for _ in range(random.randint(0, 9))]
        B = [random.choice('abcd') for _ in range(random.randint(1, 9))]
        assert _row(A, B) == dp(A, B), (A, B)

    # 2. i blocchi sono un allineamento VALIDO: monotono, e le op combaciano
    #    davvero. Un allineamento lungo ma sbagliato e' peggio di uno corto.
    for _ in range(400):
        A = [random.choice('abcde') for _ in range(random.randint(0, 14))]
        B = [random.choice('abcde') for _ in range(random.randint(0, 14))]
        bl = matching_blocks(A, B)
        tot = pa = pb = 0
        for blk in bl:
            assert blk.a >= pa and blk.b >= pb, (A, B, bl)
            for k in range(blk.size):
                assert A[blk.a + k] == B[blk.b + k], (A, B, bl)
            pa, pb = blk.a + blk.size, blk.b + blk.size
            tot += blk.size
        assert tot == lcs_length(A, B), (A, B, tot, lcs_length(A, B))

    # 3. mai peggio di difflib
    worse = 0
    for _ in range(300):
        A = [random.choice('abc') for _ in range(random.randint(0, 20))]
        B = [random.choice('abc') for _ in range(random.randint(0, 20))]
        d = sum(x.size for x in difflib.SequenceMatcher(
            None, A, B, autojunk=False).get_matching_blocks())
        if lcs_length(A, B) < d:
            worse += 1
    assert worse == 0, worse
    print('lcsmatch: ok (lunghezze, allineamento valido, mai peggio di difflib)')


if __name__ == '__main__':
    _selftest()
