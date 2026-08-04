#!/usr/bin/env python3
"""Confronto POSIZIONALE per finestre, come si fa in b43-ac-wip.

Il confronto op-per-op sull'init intero non ha senso e non e' un limite del
metodo: b43 e il driver proprietario ordinano le fasi in modo diverso — il port
comincia dalle tabelle, il vendore dal radio — quindi le due sequenze non sono
allineabili nel loro insieme. Sono allineabili **dentro una fase**, ed e' lo
stesso motivo per cui compare.py ha `--range` e `--align-on`.

Qui c'e' la tabella delle finestre riconosciute nella cattura, ciascuna con
l'ancora su cui allineare l'output dell'harness. Per ognuna si chiama compare.py
e si riporta quante op del vendore combaciano posizionalmente.

Una finestra che passa dice una cosa forte: in quella fase il port fa le stesse
op, con gli stessi valori, nello stesso ordine. Una che non passa dice dove
guardare, e la prima riga di differenza e' il punto.

    ./phase_compare.py --vendor ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
    ./phase_compare.py --vendor ... --only gain-control -v
"""

import argparse
import collections
import importlib.util
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_compare():
    """compare.py come modulo: la normalizzazione delle op deve essere la
    stessa, e serve accedere alle due liste per misurare piu' di un numero."""
    spec = importlib.util.spec_from_file_location(
        'b43_compare', os.path.join(HERE, 'compare.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CMP = _load_compare()


def longest_run(vops, tops):
    """La run piu' lunga di op consecutive che combaciano, e dove comincia.

    Serve sempre, anche quando la finestra passa: dice fin dove le due sequenze
    stanno insieme, che e' un numero piu' informativo del conteggio dei
    mismatch. Su finestre di questa taglia il quadratico va benissimo.
    """
    best = (0, 0, 0)
    for i in range(len(vops)):
        for j in range(len(tops)):
            n = 0
            while (i + n < len(vops) and j + n < len(tops)
                   and CMP.ops_equal(vops[i + n], tops[j + n])):
                n += 1
            if n > best[0]:
                best = (n, i, j)
    return best


def multiset_verdict(vops, tops, allow):
    """Confronto per multiinsieme dentro la finestra.

    Vale quando nella finestra le op sono indipendenti fra loro, cioe' quando
    (write read)xN e writexN readxN portano allo stesso stato: l'ordine non e'
    informazione e imporlo produce un falso allarme. La deroga e' dichiarata per
    finestra, non globale, e le op in piu' sul lato port sono ammesse solo se
    la loro classe e' in `allow`.
    """
    want = collections.Counter(vops)
    got = collections.Counter(tops)
    missing = want - got
    extra = got - want
    unexpected = collections.Counter()
    for op, n in extra.items():
        if not any(op.startswith(a) for a in allow):
            unexpected[op] += n
    return missing, unexpected

# Finestre nella cattura opinit-ch1-ch6-bw20.decoded, primo init a canale 1.
# flow/args: come lanciare l'harness perche' quella fase ci sia dentro.
WINDOWS = [
    dict(name='gain-control', rng='680:770',
         anchor='PHY.MOD addr=0x1d9 val=0x0 mask=0x20',
         flow=('init', '1'),
         what='soglie CRS (0008) e gain control RX (0001)'),
    dict(name='tssi-setup', rng='1259:1281', test_len=30,
         anchor='RAD.WR addr=0x175 val=0x5',
         flow=('init', '1'),
         what='b43_nphy_ipa_internal_tssi_setup',
         known='op in piu\': il port scrive 0x17b, il vendore in questa fase no '
               '(docs/todo-nphy.md 3d). Da @3 in poi e\' lo sfasamento.'),
    dict(name='papd-comp', rng='2688:2703',
         anchor='TBL.WR id=0x1a off=0x240 len=1',
         flow=('init', '1'),
         what='compensazione PAPD, patches/b43/0003'),
    dict(name='papd-tables', rng='10966:10970',
         anchor='TBL.WR id=0x20 off=0x0 len=64',
         flow=('init', '1'),
         what='tabelle scalare ed epsilon, patches/b43/0004'),
    dict(name='ipa-bias', rng='605:607',
         anchor='PHY.WR addr=0x32f val=0x3',
         flow=('init', '1'),
         what='bias IPA 2 GHz, patches/b43/0005'),
    dict(name='rssi-cal', rng='3723:3740',
         anchor='PHY.WR addr=0x1b8 val=0x3f',
         flow=('init', '1'),
         what='coefficienti di moltiplicazione RSSI',
         test_len=44,
         equiv='multiset',
         allow=('PHY.RD', 'RAD.RD', 'RAD.MOD', 'PHY.WR addr=0x1d',
                'PHY.WR addr=0x1c', 'PHY.MOD'),
         equiv_why='le scritture dei coefficienti sono indipendenti fra loro: '
                   'il vendore le raggruppa, il port le intercala alle '
                   'letture, e (write read)xN equivale a writexN readxN.'),
    # Fasi della calibrazione PAPD, dalla mappa in docs/papd-cal-map.md. Non
    # passano e non devono: b43 la cal PAPD non ce l'ha. Sono qui pronte per
    # quando la si porta, cosi' si verifica una fase per volta.
    dict(name='papd-tone', rng='11741:11755',
         anchor='PHY.WR addr=0x186 val=0x100',
         flow=('init', '1'),
         what='tono di test, 0x186-0x194',
         pending='cal PAPD non portata: b43 ha b43_nphy_tx_tone() ma nessuno la '
                 'chiama nell\'init. Vedi docs/papd-cal-map.md punto 1.'),
    dict(name='chanswitch-ch6', rng='34940:34990', test_len=220,
         anchor='RAD.WR addr=0x16 val=0x58',
         flow=('chanset', '6'),
         what='upload della chantab al cambio canale',
         allow=('MMIO.', 'PHY.WR addr=0x1d3'),
         known='mancano i 10 campi 5 GHz (voce 5b), INTERCALATI: 0x43 dopo 0x41, '
               '0x4a dopo 0x47. Gli 8 su 0x2b/0x2e non mancano: sono il vcocal, '
               'che il vendore fa come RD+WR e b43 come mask/set - stessa cosa, '
               'resa diversa (docs/todo-nphy.md 3g).'),
]


def merged_vendor(vendor):
    """Ripiega i RETVAL nelle read, come fa la pipeline di ac.

    Senza questo passo le righe RETVAL entrano nel confronto come op a se' e
    sfasano tutto: il vendore ne ha 11049. E' il passo che avevo saltato.
    """
    out = vendor + '.rv'
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(vendor):
        tool = os.path.join(HERE, '..', 'reverse-tools', 'merge_retvals.py')
        subprocess.run([sys.executable, tool, vendor, out], check=True,
                       stdout=subprocess.DEVNULL)
    return out


def run(vendor, win, verbose):
    out = os.path.join('/tmp', 'phase_%s.out' % win['name'])
    flow, chan = win['flow']
    with open(out, 'w') as fh:
        r = subprocess.run([os.path.join(HERE, 'nphy_trace'), flow, 'dsl3580l', chan],
                           stdout=fh, stderr=subprocess.DEVNULL)
    if r.returncode:
        return None, 'harness uscito con %d' % r.returncode

    lo, hi = (int(x) for x in win['rng'].split(':'))
    vops = CMP.load_vendor(vendor, (lo, hi))
    tall = CMP.load_test(out)
    if not vops:
        return None, 'finestra vendore vuota'

    off = CMP.find_offset(tall, CMP.normalize_op(win['anchor']))
    if off < 0:
        return None, 'ancora non trovata: %s' % win['anchor']

    # Il confronto posizionale usa tante op quante ne ha il vendore; la finestra
    # piu' larga (test_len) serve solo alla diagnosi per multiinsieme, dove
    # troncare inventa mancanti e in piu'.
    span = win.get('test_len', len(vops))
    tops = tall[off:off + span]
    tpos = tall[off:off + len(vops)]

    mism = sum(1 for v, t in zip(vops, tpos) if not CMP.ops_equal(v, t))
    mism += abs(len(vops) - len(tpos))
    run_len, vi, ti = longest_run(vops, tpos)

    # La diagnosi per multiinsieme si calcola sempre: dire "36 differenze
    # posizionali" non fa capire niente, dire "10 op mancanti e 0 in piu'" si'.
    missing, unexpected = multiset_verdict(vops, tops, win.get('allow', ()))
    res = dict(nops=len(vops), mismatch=mism, run=run_len, run_at=(vi, ti),
               missing=missing, unexpected=unexpected)

    if verbose:
        for i, (v, t) in enumerate(zip(vops, tops)):
            if not CMP.ops_equal(v, t):
                print('  @%d:\n    vendor: %s\n    test:   %s' % (i, v, t))
        if res['missing']:
            print('  op del vendore che il port non fa:')
            for op, n in res['missing'].items():
                print('    x%-3d %s' % (n, op))
        if res['unexpected']:
            print('  op in piu\' del port, fuori dalla deroga:')
            for op, n in res['unexpected'].items():
                print('    x%-3d %s' % (n, op))
    return res, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--vendor', required=True)
    ap.add_argument('--only', help='una sola finestra, per nome')
    ap.add_argument('-v', '--verbose', action='store_true',
                    help='stampa le differenze, e la diagnosi per multiinsieme')
    ap.add_argument('--global-run', nargs=2, metavar=('DA', 'A'),
                    help='la run piu\' lunga fra TUTTA la finestra vendore '
                         'indicata e tutto l\'output del flow init: dice fin '
                         'dove le due sequenze stanno insieme senza scegliere '
                         'una fase a mano')
    args = ap.parse_args()

    if not os.path.exists(os.path.join(HERE, 'nphy_trace')):
        sys.exit("manca ./nphy_trace: prima `make KDIR=...`")
    vendor = merged_vendor(args.vendor)
    print('vendore: %s\n' % os.path.basename(vendor))

    if args.global_run:
        lo, hi = (int(x) for x in args.global_run)
        vops = CMP.load_vendor(vendor, (lo, hi))
        out = '/tmp/phase_globalrun.out'
        with open(out, 'w') as fh:
            subprocess.run([os.path.join(HERE, 'nphy_trace'), 'init',
                            'dsl3580l', '1'], stdout=fh,
                           stderr=subprocess.DEVNULL)
        tops = CMP.load_test(out)
        import difflib
        sm = difflib.SequenceMatcher(None, vops, tops, autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        blocks.sort(key=lambda b: -b.size)
        print('vendore %d op, port %d op' % (len(vops), len(tops)))
        print('run piu\' lunghe (op consecutive che combaciano):')
        for b in blocks[:8]:
            print('  %4d op   vendore @%-6d port @%-6d   prima: %s'
                  % (b.size, b.a, b.b, vops[b.a][:58]))
        tot = sum(b.size for b in blocks)
        print('\ntotale op in comune: %d su %d del vendore (%.0f%%), in %d blocchi'
              % (tot, len(vops), 100.0 * tot / max(1, len(vops)), len(blocks)))
        return 0

    bad = known = pending = 0
    print('%-16s %-5s %-6s %-9s %s'
          % ('finestra', 'op', 'run', 'esito', 'cosa copre'))
    for win in WINDOWS:
        if args.only and win['name'] != args.only:
            continue
        res, err = run(vendor, win, args.verbose)
        if err and win.get('pending'):
            # Fase non ancora portata: non trovare l'ancora e' lo stato atteso.
            print('%-16s %-5s %-6s %-9s %s'
                  % (win['name'], '-', '-', 'assente', win['what']))
            print('%-30s %s' % ('', win['pending']))
            pending += 1
            continue
        if err:
            print('%-16s %-5s %-6s %-9s %s'
                  % (win['name'], '-', '-', 'ERR', err))
            bad += 1
            continue

        run_s = '%d/%d' % (res['run'], res['nops'])
        diag = ''
        if res['mismatch']:
            diag = 'mancano %d, in piu\' %d' % (sum(res['missing'].values()),
                                                sum(res['unexpected'].values()))
        if res['mismatch'] == 0:
            verdict = 'ok'
        elif win.get('equiv') == 'multiset':
            if not res['missing'] and not res['unexpected']:
                verdict = 'ok*'          # stesse op, ordine diverso: dichiarato
            else:
                verdict = '%d+%d DIFF' % (sum(res['missing'].values()),
                                          sum(res['unexpected'].values()))
                bad += 1
        elif win.get('known'):
            verdict = '%d noto' % res['mismatch']
            known += 1
        else:
            verdict = '%d DIFF' % res['mismatch']
            bad += 1

        print('%-16s %-5d %-6s %-9s %s'
              % (win['name'], res['nops'], run_s, verdict, win['what']))
        if diag:
            print('%-30s %s' % ('', diag))
        if verdict == 'ok*':
            print('%-30s %s' % ('', win.get('equiv_why', 'ordine irrilevante '
                                            'nella finestra, dichiarato')))
        elif res['mismatch'] and win.get('known'):
            print('%-30s %s' % ('', win['known']))

    print('\nrun = la sequenza consecutiva piu\' lunga che combacia, su quante '
          'op ha la finestra')
    print("ok* = stesse op con gli stessi valori, ordine diverso, equivalenza "
          "dichiarata per quella finestra")
    print('\n%d finestre: %d da guardare, %d divergenze note, %d fasi non '
          'ancora portate'
          % (len(WINDOWS) if not args.only else 1, bad, known, pending))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
