#!/usr/bin/env python3
"""Estrazione e verifica delle tabelle N-PHY / radio 2057 dal blob `wl`.

Il blob e' un ELF32 MIPS big-endian *relocatable* non strippato: le tabelle
statiche stanno in .data/.rodata con simboli e size, quindi si leggono senza
disassemblare. Nessuna dipendenza esterna: il lettore ELF sta qui sotto.

Tre modi:

  --list [regex]        elenca i simboli dati con size (default: nphy|2057)
  --dump SYM            hexdump del simbolo
  --verify SYM --against FILE:ARRAY
                        confronta il contenuto del simbolo con un array C del
                        tree kernel, deducendo lo stride del record vendor dal
                        matching della colonna indirizzi

Il modo --verify e' il motivo per cui questo file esiste: le tabelle merged
upstream sono state ricavate da dump MMIO, e questo controlla che coincidano
con la tabella statica dentro il driver proprietario che le ha prodotte.

Esempi:
    ./blob_tables.py --list 2057rev8 -- wlDSL-3580_EU.o_save
    ./blob_tables.py --verify regs_2057_rev8 \\
        --against ~/src/linux/drivers/net/wireless/broadcom/b43/radio_2057.c:r2057_rev8_init \\
        -- wlDSL-3580_EU.o_save
"""

import argparse
import re
import struct
import sys

SHT_SYMTAB = 2


class Elf32BE:
    """Lettore minimale: sezioni, symtab, contenuto di un simbolo."""

    def __init__(self, path):
        with open(path, 'rb') as fh:
            self.buf = fh.read()
        if self.buf[:4] != b'\x7fELF':
            raise ValueError('non e\' un ELF')
        if self.buf[4] != 1 or self.buf[5] != 2:
            raise ValueError('atteso ELF32 big-endian')
        (self.e_shoff, ) = struct.unpack_from('>I', self.buf, 0x20)
        self.e_shentsize, self.e_shnum, self.e_shstrndx = struct.unpack_from(
            '>HHH', self.buf, 0x2E)
        self.sections = []
        for i in range(self.e_shnum):
            off = self.e_shoff + i * self.e_shentsize
            name, stype, flags, addr, offset, size, link, info, align, entsize = \
                struct.unpack_from('>IIIIIIIIII', self.buf, off)
            self.sections.append(dict(name_off=name, type=stype, offset=offset,
                                      size=size, link=link, entsize=entsize))
        shstr = self.sections[self.e_shstrndx]
        for sec in self.sections:
            sec['name'] = self._cstr(shstr['offset'] + sec['name_off'])
        self.symbols = {}
        for sec in self.sections:
            if sec['type'] != SHT_SYMTAB:
                continue
            strtab = self.sections[sec['link']]
            count = sec['size'] // sec['entsize']
            for i in range(count):
                off = sec['offset'] + i * sec['entsize']
                st_name, st_value, st_size, st_info, st_other, st_shndx = \
                    struct.unpack_from('>IIIBBH', self.buf, off)
                if not st_name or not st_size:
                    continue
                name = self._cstr(strtab['offset'] + st_name)
                self.symbols[name] = dict(value=st_value, size=st_size,
                                          shndx=st_shndx)

    def _cstr(self, off):
        end = self.buf.index(b'\x00', off)
        return self.buf[off:end].decode('ascii', 'replace')

    def symbol_bytes(self, name):
        sym = self.symbols.get(name)
        if not sym:
            raise KeyError(name)
        sec = self.sections[sym['shndx']]
        start = sec['offset'] + sym['value']
        return self.buf[start:start + sym['size']]


def parse_c_pairs(path, array):
    """Estrae le coppie {addr, val} da un array C del kernel."""
    text = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'\b%s\s*\[\s*\]\s*\[\s*2\s*\]\s*=\s*\{' % re.escape(array), text)
    if not m:
        m = re.search(r'\b%s\s*\[\s*\]\s*=\s*\{' % re.escape(array), text)
    if not m:
        raise SystemExit('array %s non trovato in %s' % (array, path))
    depth = 0
    for i in range(m.end() - 1, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                body = text[m.end():i]
                break
    else:
        raise SystemExit('array %s non chiuso' % array)
    body = re.sub(r'/\*.*?\*/', ' ', body, flags=re.S)
    num = r'-?(?:0x[0-9a-fA-F]+|\d+)'
    pairs = re.findall(r'\{\s*(%s)\s*,\s*(%s)\s*\}' % (num, num), body)
    if pairs:
        return [(int(a, 0), int(b, 0)) for a, b in pairs]
    flat = re.findall(num, body)
    return [(None, int(v, 0)) for v in flat]


def candidate_layouts(blob, addrs):
    """Deduce (stride, off_addr, off_val, width_val) dal matching indirizzi.

    Le tabelle vendor sono array di struct con un campo indirizzo u16; stride e
    offset non sono noti a priori (dipendono da come il compilatore ha allineato
    la struct in quella build), quindi si cercano provando le combinazioni e
    tenendo quelle in cui la colonna indirizzi riproduce quella del kernel.
    """
    found = []
    for stride in (4, 6, 8):
        if len(blob) < stride * len(addrs):
            continue
        for off_a in range(0, stride - 1, 2):
            got = [struct.unpack_from('>H', blob, i * stride + off_a)[0]
                   for i in range(len(addrs))]
            if got != addrs:
                continue
            for off_v in range(0, stride - 1):
                for width in (1, 2):
                    if off_v + width > stride or off_v == off_a:
                        continue
                    found.append((stride, off_a, off_v, width))
    return found


def read_values(blob, n, stride, off_v, width):
    out = []
    for i in range(n):
        if width == 1:
            out.append(blob[i * stride + off_v])
        else:
            out.append(struct.unpack_from('>H', blob, i * stride + off_v)[0])
    return out


def cmd_list(elf, pattern):
    rx = re.compile(pattern, re.I)
    rows = [(n, s['size']) for n, s in elf.symbols.items() if rx.search(n)]
    for name, size in sorted(rows, key=lambda r: r[0]):
        print('%-52s %6d  0x%x' % (name, size, size))
    print('\n%d simboli' % len(rows), file=sys.stderr)


def cmd_dump(elf, name, stride):
    data = elf.symbol_bytes(name)
    print('# %s: %d byte' % (name, len(data)))
    for off in range(0, len(data), stride):
        chunk = data[off:off + stride]
        print('%04x  %s' % (off, ' '.join('%02x' % b for b in chunk)))


def cmd_verify(elf, name, against, elem):
    path, _, array = against.rpartition(':')
    if not path:
        raise SystemExit('--against vuole FILE:ARRAY')
    pairs = parse_c_pairs(path, array)
    blob = elf.symbol_bytes(name)
    print('kernel  %s:%s -> %d entry' % (path.split('/')[-1], array, len(pairs)))
    print('blob    %s -> %d byte' % (name, len(blob)))

    if pairs[0][0] is None:
        # array piatto (solo valori): confronto diretto nel formato elemento
        want = [v for _, v in pairs]
        code = {'u32': '>%dI', 's32': '>%di', 'u16': '>%dH',
                's16': '>%dh', 'u8': '>%dB', 's8': '>%db'}[elem]
        got = list(struct.unpack_from(code % len(want), blob, 0))
        bad = [(i, w, g) for i, (w, g) in enumerate(zip(want, got)) if w != g]
        report(want, bad, '%s flat' % elem)
        return

    addrs = [a for a, _ in pairs]
    layouts = candidate_layouts(blob, addrs)
    if not layouts:
        print('\nnessun layout riproduce la colonna indirizzi del kernel:')
        print('  primi indirizzi kernel: %s' % ' '.join('%03x' % a for a in addrs[:8]))
        print('  primi u16 del blob:     %s'
              % ' '.join('%04x' % struct.unpack_from('>H', blob, i * 2)[0]
                         for i in range(8)))
        raise SystemExit(2)

    best = None
    for stride, off_a, off_v, width in layouts:
        got = read_values(blob, len(pairs), stride, off_v, width)
        bad = [(i, w, g) for i, ((_, w), g) in enumerate(zip(pairs, got)) if w != g]
        if best is None or len(bad) < len(best[1]):
            best = ((stride, off_a, off_v, width), bad)

    (stride, off_a, off_v, width), bad = best
    print('layout dedotto: stride=%d addr@%d val@%d (u%d), '
          'record nel blob=%d' % (stride, off_a, off_v, width * 8, len(blob) // stride))
    report([v for _, v in pairs], bad, 'valori')


def report(want, bad, what):
    if not bad:
        print('\nOK: %d/%d %s identici' % (len(want), len(want), what))
        return
    print('\nDIFF: %d/%d %s divergono' % (len(bad), len(want), what))
    for i, w, g in bad[:20]:
        print('  [%3d] kernel=0x%04x blob=0x%04x' % (i, w, g))
    if len(bad) > 20:
        print('  ... altri %d' % (len(bad) - 20))
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('blob', help='il file wl*.o del firmware OEM')
    ap.add_argument('--list', nargs='?', const=r'nphy|2057', metavar='REGEX')
    ap.add_argument('--dump', metavar='SYM')
    ap.add_argument('--stride', type=int, default=16, help='byte per riga di --dump')
    ap.add_argument('--verify', metavar='SYM')
    ap.add_argument('--against', metavar='FILE:ARRAY')
    ap.add_argument('--elem', default='u32',
                    choices=['u32', 's32', 'u16', 's16', 'u8', 's8'],
                    help='formato elemento per gli array piatti')
    args = ap.parse_args()

    elf = Elf32BE(args.blob)

    if args.list:
        cmd_list(elf, args.list)
    elif args.dump:
        cmd_dump(elf, args.dump, args.stride)
    elif args.verify:
        if not args.against:
            raise SystemExit('--verify richiede --against FILE:ARRAY')
        cmd_verify(elf, args.verify, args.against, args.elem)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
