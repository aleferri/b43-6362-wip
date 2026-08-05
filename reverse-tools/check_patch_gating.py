#!/usr/bin/env python3
"""Controlla che le righe aggiunte da una patch siano dietro un gate di revisione.

Il motivo e' pratico: nel PHY di b43 quasi tutto e' condiviso fra tutte le N-PHY.
`b43_nphy_op_prepare_structs`, `b43_radio_2057_chantab_upload`,
`b43_nphy_tx_pwr_ctl_init` e i dispatcher dei workaround girano su rev 1 come su
rev 17. Una modifica non iffata cambia il comportamento di hardware che non
abbiamo e non possiamo provare, ed e' un nack immediato a ragione.

Per ogni riga aggiunta lo strumento trova la funzione che la contiene nel file
**dopo** la patch e cerca un gate che la domini:

  - il nome della funzione e' rev-specifico (`..._rev7`, `..._rev19`);
  - piu' su nella funzione c'e' un early return su rev o radio_rev;
  - la riga sta dentro un `if` o un `case` la cui condizione cita rev.

E' un'euristica su brace depth, non un parser C: serve a non spedire una patch
senza esserci passato sopra, non a certificarla. Limite visto in pratica: se
l'hunk cade nelle ultime righe di una funzione, il nome riportato puo' essere
quello della funzione SEGUENTE (il contesto del diff sconfina). E su una serie:
--tree vuole l'albero alla BASE di quella patch, cioe' con le precedenti della
serie applicate, non mainline nudo. Il verdetto sul
gate resta valido, il nome no: se conta, verificarlo con cfuncs.index_functions
sul file dopo la patch. Un "NON GATEATA" va guardato;
puo' essere legittimo (una funzione nuova chiamata solo da un ramo iffato) o
puo' essere il nack.

    ./check_patch_gating.py --tree ~/src/linux ../patches/b43/*.patch
"""

import argparse
import os
import difflib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfuncs  # noqa: E402

RE_FILE = re.compile(r'^\+\+\+ b/(.+)$')
RE_HUNK = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')
RE_REV_NAME = re.compile(r'_rev\d+\w*$')
RE_REV_GUARD = re.compile(r'\b(?:phy->)?(?:radio_)?rev\b')
# Un gate sul TIPO di PHY e' legittimo, ma ha un raggio diverso: tocca tutte le
# revisioni di quel tipo, non solo la nostra. Va riconosciuto e detto.
RE_TYPE_GUARD = re.compile(r'B43_PHYTYPE_\w+')
RE_RETURN = re.compile(r'\breturn\b')
# Assegnazione a una variabile locale: `bool tune_5g = dev->phy.rev == 8 && ...`
# Esclude ==, !=, <=, >= per non prendere i confronti.
RE_ASSIGN = re.compile(r'^\s*(?:\w[\w\s\*]*?\s)?(\w+)\s*=\s*([^=].*)$')


def added_lines(patch_path):
    """[(file, [numeri di riga nel file nuovo])] per ogni file toccato."""
    per_file = {}
    current = None
    new_line = 0
    for raw in open(patch_path, encoding='utf-8', errors='replace'):
        line = raw.rstrip('\n')
        m = RE_FILE.match(line)
        if m:
            current = m.group(1)
            per_file.setdefault(current, [])
            continue
        m = RE_HUNK.match(line)
        if m:
            new_line = int(m.group(1))
            continue
        if current is None:
            continue
        if line.startswith('+') and not line.startswith('+++'):
            per_file[current].append(new_line)
            new_line += 1
        elif line.startswith('-') and not line.startswith('---'):
            pass
        elif line.startswith(' ') or line == '':
            new_line += 1
    return per_file


def added_after_apply(before, after):
    """I numeri di riga del file NUOVO che la patch ha aggiunto.

    Non si possono prendere dagli `@@`: `patch(1)` rilocalizza gli hunk quando
    l'albero non e' esattamente quello su cui la patch e' stata fatta, e da quel
    momento i numeri dell'header sono sbagliati -- in silenzio, perche' lo
    invochiamo con --silent. Su una patch multi-hunk l'errore si accumula e le
    righe finiscono attribuite alla funzione sbagliata, che e' il modo peggiore di
    sbagliare per uno strumento come questo: il nome che stampa esiste.

    Diffare il contenuto prima/dopo da' le posizioni vere qualunque cosa abbia
    fatto patch(1).
    """
    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    nums = []
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ('insert', 'replace'):
            nums.extend(range(j1 + 1, j2 + 1))
    return nums


def strip(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', text)


def gate_for(lines, span, target):
    """Cerca un gate che domini la riga target, dentro la funzione span."""
    first, last = span
    depth = 0
    open_conditions = []          # (depth, testo della condizione)
    # Nomi locali che valgono quanto un confronto su rev, perche' vengono da
    # uno. Ripetere `dev->phy.rev == 8 && dev->phy.radio_rev == 8` dieci volte
    # e' peggio del calcolarlo una volta, e uno strumento che non riconosce il
    # flag spinge a scrivere il codice peggiore.
    rev_flags = set()
    for n in range(first, min(target, last) + 1):
        code = strip(lines[n - 1])
        if depth and RE_REV_GUARD.search(code) and RE_RETURN.search(code):
            return 'early return su rev alla riga %d' % n
        m = RE_ASSIGN.match(code)
        if m:
            if RE_REV_GUARD.search(m.group(2)):
                rev_flags.add(m.group(1))
            else:
                rev_flags.discard(m.group(1))   # riassegnato da altro
        for ch in code:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                open_conditions = [c for c in open_conditions if c[0] <= depth]
        m = re.search(r'\b(if|case|switch)\b(.*)$', code)
        if m:
            cond = m.group(2)
            flag = next((f for f in rev_flags
                         if re.search(r'\b%s\b' % re.escape(f), cond)), None)
            if RE_REV_GUARD.search(cond):
                open_conditions.append((depth, code.strip()[:60]))
            elif flag:
                open_conditions.append(
                    (depth, '%s   [%s viene da rev]' % (code.strip()[:44], flag)))
    for _, cond in open_conditions:
        return 'dentro %s' % cond
    return None


def check(tree, patch_path):
    per_file = added_lines(patch_path)
    verdicts = []
    before = {}
    with tempfile.TemporaryDirectory() as tmp:
        for rel in per_file:
            src = os.path.join(tree, rel)
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            else:
                open(dst, 'w').close()
            with open(dst, encoding='utf-8', errors='replace') as fh:
                before[rel] = fh.readlines()
        # patch(1) e non git apply: la directory temporanea non e' un repo, e
        # git apply fuori da un work tree rifiuta i path.
        res = subprocess.run(['patch', '-p1', '--forward', '--silent', '-i',
                              os.path.abspath(patch_path)],
                             cwd=tmp, capture_output=True, text=True)
        if res.returncode or 'previously applied' in res.stdout:
            hint = ('la patch sembra GIA\' applicata sull\'albero: --tree vuole '
                    'un albero pulito' if 'previously applied' in res.stdout
                    else (res.stderr.strip() or res.stdout.strip())[:90])
            return [('(patch non applicabile)', None, hint)]

        for rel in per_file:
            path = os.path.join(tmp, rel)
            lines, owner = cfuncs.index_functions(path)
            nums = added_after_apply(before[rel], lines)
            spans = cfuncs.function_ranges(path)
            seen = set()
            for n in nums:
                fn = owner.get(n)
                if fn is None:
                    key = (rel, '(fuori funzione)')
                    if key not in seen:
                        seen.add(key)
                        verdicts.append((rel, '(dato o dichiarazione)', 'ok'))
                    continue
                if fn in seen:
                    continue
                seen.add(fn)
                if RE_REV_NAME.search(fn):
                    verdicts.append((rel, fn, 'nome rev-specifico'))
                    continue
                # Funzione aggiunta per intero dalla patch: il gate, se c'e',
                # sta nel chiamante. Non e' un allarme.
                #
                # Il confronto guarda solo le righe con del contenuto: righe
                # vuote e righe di sola graffa sono identiche a decine di altre
                # nel file, quindi il diff le appaia altrove e non finiscono fra
                # le aggiunte. Pretendere il sottoinsieme completo dello span
                # farebbe passare per "non gateata" ogni funzione nuova.
                span_lines = set(range(spans[fn][0], spans[fn][1] + 1))
                span_lines = {n for n in span_lines
                              if lines[n - 1].strip() not in ('', '{', '}')}
                if span_lines and span_lines <= set(nums):
                    verdicts.append((rel, fn,
                                     'funzione nuova, il gate sta nel chiamante'))
                    continue
                # Se il gate lo introduce la patch stessa, e' quello da dire.
                own = None
                for k in sorted(x for x in nums if spans[fn][0] <= x <= spans[fn][1]):
                    code = strip(lines[k - 1])
                    if RE_REV_GUARD.search(code) and RE_RETURN.search(code):
                        own = 'gate aggiunto dalla patch alla riga %d' % k
                        break
                    if RE_REV_GUARD.search(code) and re.search(r'\bif\b', code):
                        own = 'gate aggiunto dalla patch alla riga %d' % k
                        break
                    if RE_TYPE_GUARD.search(code) and re.search(r'\b(if|return)\b', code):
                        own = ('gate sul TIPO di PHY alla riga %d: tocca tutte '
                               'le rev di quel tipo' % k)
                        break
                    ma = RE_ASSIGN.match(code)
                    if ma and RE_REV_GUARD.search(ma.group(2)):
                        own = ('gate aggiunto dalla patch alla riga %d: %s '
                               'viene da rev' % (k, ma.group(1)))
                        break
                gate = own or gate_for(lines, spans[fn], n)
                if not gate:
                    body = ''.join(lines[spans[fn][0] - 1:spans[fn][1]])
                    if RE_TYPE_GUARD.search(strip(body)):
                        gate = 'gate sul TIPO di PHY: tocca tutte le rev di quel tipo'
                verdicts.append((rel, fn, gate or 'NON GATEATA'))
    return verdicts


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tree', required=True)
    ap.add_argument('patches', nargs='+')
    args = ap.parse_args()

    bad = 0
    for patch in args.patches:
        print('== %s' % os.path.basename(patch))
        for rel, fn, verdict in check(args.tree, patch):
            flag = '  !!' if verdict == 'NON GATEATA' else '    '
            print('%s %-28s %-46s %s' % (flag, rel.split('/')[-1], fn, verdict))
            if verdict == 'NON GATEATA':
                bad += 1
    print('\n%d punti da guardare' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
