#!/usr/bin/env python3
"""Autotest di cfuncs.py.

Quattro strumenti di questa cartella attribuiscono righe a funzioni con
`cfuncs.index_functions`, e ci appoggiano conclusioni che finiscono nella doc:
`brcmsmac_xref.py` dice quale funzione brcmsmac guardare per ogni gate,
`check_patch_gating.py` dice se una riga aggiunta da una patch e' dietro un gate.
Se l'attribuzione sbaglia, sbagliano in silenzio: il nome che stampano esiste, e'
solo quello di un'altra funzione.

E' esattamente quello che e' successo con le firme che lo stile kernel manda a
capo, per un intero progetto. Da qui in poi il caso e' coperto.

Uso: ./test_cfuncs.py       exit 1 al primo fallimento
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfuncs  # noqa: E402

# Le due forme che convivono in phy_n.c di brcmsmac, piu' i vicini che un
# tokenizzatore ingenuo confonde con una definizione: il prototipo, la tabella a
# colonna 0, la macro invocata a colonna 0.
SAMPLE = '''\
static u16 one_line(struct x *p)
{
\treturn 0;
}

static void
wrapped(struct x *p,
\tint core)
{
\tint local;

\tlocal = core;
}

static const struct ops table_at_col0 = {
\t.field = wrapped,
};

EXPORT_SYMBOL(one_line);

static int prototype_only(struct x *p, int y);

int
after_the_prototype(void)
{
\treturn 1;
}
'''

# riga (1-based) -> funzione che la contiene, None dove non c'e' funzione
EXPECT = {
    3: 'one_line',
    10: 'wrapped',            # il corpo, dopo una firma su tre righe
    12: 'wrapped',
    16: None,                 # una tabella a colonna 0 non e' dentro wrapped
    19: None,                 # ne' una macro invocata a colonna 0
    21: None,                 # ne' un prototipo
    26: 'after_the_prototype',
}

EXPECT_LEN = {'one_line': 3, 'wrapped': 5, 'after_the_prototype': 3}


def main():
    with tempfile.NamedTemporaryFile('w', suffix='.c', delete=False) as fh:
        fh.write(SAMPLE)
        path = fh.name
    try:
        lines, owner = cfuncs.index_functions(path)
        bad = 0
        for n, want in sorted(EXPECT.items()):
            got = owner.get(n)
            if got != want:
                print('riga %d (%r): atteso %s, ottenuto %s'
                      % (n, lines[n - 1].rstrip(), want, got))
                bad += 1

        spans = cfuncs.function_ranges(path)
        for name, want in sorted(EXPECT_LEN.items()):
            if name not in spans:
                print('%s: nessuno span' % name)
                bad += 1
                continue
            lo, hi = spans[name]
            if hi - lo + 1 != want:
                print('%s: atteso %d righe, ottenute %d (%d-%d)'
                      % (name, want, hi - lo + 1, lo, hi))
                bad += 1
    finally:
        os.unlink(path)

    if bad:
        print('%d controlli falliti' % bad)
        return 1
    print('cfuncs: %d righe e %d span come attesi'
          % (len(EXPECT), len(EXPECT_LEN)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
