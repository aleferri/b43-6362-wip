"""Localizzazione delle funzioni C per riga, con euristica a profondita' di graffe.

Non e' un parser C: assume sorgenti in stile kernel (definizione di funzione a
colonna 0, corpo aperto da una graffa a profondita' 0).
"""

import re

_DEF = re.compile(r'^[A-Za-z_][\w\s\*\(\),]*\b(\w+)\s*\(')


def index_functions(path):
    """Ritorna (righe, mappa numero_riga->nome_funzione) 1-based."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()

    owner = {}
    depth = 0
    candidate = None
    current = None
    in_comment = False

    for n, raw in enumerate(lines, 1):
        line = raw
        if in_comment:
            end = line.find('*/')
            if end < 0:
                owner[n] = current
                continue
            line = line[end + 2:]
            in_comment = False
        start = line.find('/*')
        while start >= 0:
            end = line.find('*/', start + 2)
            if end < 0:
                line = line[:start]
                in_comment = True
                break
            line = line[:start] + ' ' + line[end + 2:]
            start = line.find('/*')
        line = re.sub(r'//.*', '', line)
        line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)

        if depth == 0:
            m = _DEF.match(line)
            if m and not line.lstrip().startswith('#'):
                candidate = m.group(1)

        opens = line.count('{')
        closes = line.count('}')
        if depth == 0 and opens:
            current = candidate
        depth += opens - closes
        if depth < 0:
            depth = 0
        owner[n] = current
        if depth == 0 and closes:
            current = None

    return lines, owner


def function_ranges(path):
    """Ritorna {nome: (prima_riga, ultima_riga)} per la prima definizione vista."""
    lines, owner = index_functions(path)
    spans = {}
    for n in range(1, len(lines) + 1):
        fn = owner.get(n)
        if not fn:
            continue
        if fn not in spans:
            spans[fn] = [n, n]
        else:
            spans[fn][1] = n
    return {k: tuple(v) for k, v in spans.items()}
