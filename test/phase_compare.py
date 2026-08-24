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
import difflib
import importlib.util
import os
import re
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


# Le regioni del primo ciclo della cattura. Servono a dire *dove* il port e il
# vendore divergono su tutta la run, che e' una domanda diversa da quella delle
# finestre: le finestre coprono le fasi che qualcuno ha guardato, le regioni
# coprono tutto, comprese quelle che nessuno ha ancora attribuito.
REGIONS = [
    (132, 10961, 'init vero e proprio'),
    (10962, 14092, 'cal PAPD (a4)'),
    (14093, 15920, 'cal RX IQ, ingresso'),
    (15921, 22246, 'cal RX IQ, sweep di gain'),
    (22247, 23771, 'seconda cal RSSI'),
    (23772, 26100, 'coda'),
]


# La cal PAPD non si misura piu' a finestre per funzione ma come UNA regione
# contigua, e il motivo sono i piani di lettura. I piani sono posizionali:
# servono il valore che l'hardware ha dato solo se il port fa le stesse read
# nello stesso ordine del vendore. Dentro una regione contigua quella condizione
# e' garantita per costruzione, quindi i valori tornano da soli; con una finestra
# per funzione no, e si finisce a inseguire il cursore dei piani invece del
# difetto. Il verdetto qui e' la STRUTTURA dei blocchi contigui, non un
# conteggio: un blocco che si accorcia e' una regressione anche se il totale
# sale.
CONTIG = [
    # UNA finestra, e non a fase: la macro operazione intera.
    #
    # Comincia dove comincia switch_channel - la CHANSPEC di #132, che il tracer
    # emette e il port no - e finisce col MAC abilitato che trasmette, #26100.
    # Sono 22951 op. Tutto cio' che sta prima, #1-131, e' op_init e rfkill: e' lo
    # stato che questo blocco NON PUO' avere e che va seminato, non tracciato.
    #
    # Non si fanno region per fase. Una fase presa da sola dice che la sua
    # sequenza combacia e non dice niente su cio' che le arriva addosso da prima:
    # la finestra chanswitch-ch6 diceva 33/39 "nessuna op mancante" e la fase
    # intera stava al 14%, perche' il 62% era un ciclo di misura che il port non
    # fa affatto. E' implementare bene QUESTA che distingue un radio e un phy che
    # stanno in piedi da uno che traballa.
    #
    # Nessuna ancora: la finestra e' tutta la run, quindi i blocchi si trovano
    # sull'intero output del flow senza agganciarsi a un'op scelta a mano.
    dict(name='up-ch1', rng='132:26100',
         # La cattura non e' una phy_op sola: e' una SEQUENZA di phy_ops, e
         # tracciarne una fingendo il resto e' quello che teneva `recalc-txpower`
         # a 1 op su 716 - la fase c'e' nella cattura (#5726, il secondo
         # pwr_setup, dopo il TPL.RAMW del core a #5672) e nel trace del port non
         # c'era affatto. Il flow `txpower` e' init piu' recalc_txpower, cioe'
         # due voci di phy_ops vere. Le cal restano dove b43 le mette, dentro
         # l'init: quella e' una differenza fra port e vendore, e la tabella
         # delle fasi la mostra invece di nasconderla.
         flow=('txpower', '1'), plan_from=True,
         # Deroga per le sole classi su cui il tracer del vendore **non ha un
         # hook**, e la distinzione conta: "zero occorrenze" da solo non prova
         # niente, perche' puo' voler dire che il tracer non guarda o che wl non
         # lo fa, e le due hanno conseguenze opposte sul port. Due errori in due
         # sessioni, entrambi risolti guardando dove l'accesso passa nel
         # riferimento GPL:
         #
         # - `PMU.` era in deroga per sbaglio: wl-diag aggancia lo spuravoid del
         #   PMU (il decoder lo stampa `PMU.SPUR`), che e' la funzione che mainline
         #   chiama `bcma_pmu_spuravoid_pllupdate`, quindi c'e' ed e' agganciabile:
         #   zero occorrenze vuol dire che **non viene chiamata**, e il PMU.SPUR
         #   del port e' una divergenza vera.
         # - `MMIO.` e' in deroga, ma NON perche' il conteggio sia a zero: il
         #   vendore gli accessi ai registri di core li registra come
         #   `SI.COREREG` (54 nella cattura, `core=0x0`, `off=0x64` e `0x6c`),
         #   quindi cercare "MMIO." non prova niente. La deroga sta in piedi per
         #   il livello: `0x492` e' `psm_phy_hdr_param`, e in brcmsmac ci si
         #   arriva con un `bcma_write16(pi->d11core, D11REGOFFS(...))` **diretto**
         #   dentro `wlc_phy_chanspec_nphy_setup` — nessun accessor da agganciare,
         #   e un tracer di funzioni non lo vede.
         #
         #   Quelle tre op del port sono giuste: il bit 2 e' `MAC_PHY_FORCE_CLK`
         #   (nome di brcmsmac) e forza il clock del PHY per il tempo di scrivere
         #   il `BBCFG` del B-PHY, che con l'N-PHY attivo puo' essere clock-gated.
         #   brcmsmac fa lo stesso in `wlc_phy_chanspec_nphy_setup`, b43 in
         #   `b43_nphy_channel_setup`.
         #
         # `PHY.CLK` e `MAC.FREQ` restano, ed e' una deroga **a termine**: gli
         # hook adesso ci sono (`wlc_bmac_core_phy_clk` e
         # `wlc_bmac_switch_macfreq` in wl-diag), quindi la prima cattura fatta col
         # modulo aggiornato le rende confrontabili. **VA TOLTA quella volta**, e
         # con essa questo commento: tenerla dopo vorrebbe dire nascondere
         # divergenze che il tracer ormai vede.
         #
         # `MMIO.` invece resta: quegli accessi il vendore li fa in parte via
         # `si_corereg` (agganciata, `SI.COREREG` nella cattura) e in parte inline,
         # e l'unico che rompe il blocco e' `0x492`, che e' inline per davvero.
         # Sarebbe piu' onesta ristretta a quell'offset invece che a tutta la
         # classe: da fare quando la deroga a termine sopra sparisce e resta solo
         # questa.
         drop_port=('MMIO.', 'PHY.CLK', 'MAC.FREQ'),
         what='switch_channel fino al MAC abilitato: la macro operazione'),
    # La stessa macro operazione a FREDDO, e sono due finestre non per simmetria:
    # il comportamento cambia col tipo di calibrazione. `wlc_phy_a4(pi, full_cal)`
    # e `wlc_phy_a2_nphy(..., CAL_FULL | CAL_SOFT, ...)` prendono strade diverse, e
    # si vede: nell'intervallo della cal PAPD i buchi di `a3`/`a2` sono 349 e 276
    # op a caldo e **920 e 930** a freddo, perche' la' la ricerca dell'indice di
    # gain e' completa. Verificare una fase di cal contro una cattura sola valida
    # un ramo e non dice niente dell'altro.
    #
    # Il flow e' `initpor`, che e' l'unico che traccia un init a freddo **con** la
    # sequenza di cal: non azzera `perical`, quindi passa dal ramo di `0014`.
    #
    # La fine non e' il MAC abilitato ma il limite di confrontabilita' della
    # cattura: `full-init-*` ha un buco da 65285 record oltre #32769, quindi solo
    # #2-32769 si confronta posizionalmente.
    dict(name='up-ch1-freddo', rng='339:32769',
         capture='full-init-ch1-bw20.decoded',
         flow=('initpor', '1'), plan_from=True,
         drop_port=('MMIO.', 'PHY.CLK', 'MAC.FREQ'),
         what='la macro operazione a freddo: init completo con le cal'),
]

def canon_contig(op):
    """Nessuna riduzione: le read si confrontano col loro valore.

    C'era, e riduceva una read al suo indirizzo perche' l'harness stampava
    val=UNDEFINED mentre la cattura coi RETVAL ripiegati il valore ce l'ha. Ora
    wrap.c stampa il valore che ha servito, quindi la riduzione non serve piu' ed
    e' stata togliere: dentro una regione contigua un blocco dice che il port fa
    le stesse op, nello stesso ordine, **e legge le stesse cose**. Se un giorno
    serve una deroga, va dichiarata per regione come `allow` per le finestre, non
    globale qui."""
    return op


# Le famiglie di op che il port non puo' emettere, e non per un buco del driver:
# l'harness compila il PHY e non il core, quindi MCTRL, gli host flags, la
# template RAM e i GPIO non hanno nessun codice dietro. La object memory ce l'ha
# ma con un encoding che non e' confrontabile — `b43_shm_write16()` prende un
# offset in byte nella regione SHARED, il tracer registra l'argomento di
# `write_objmem16()`, che e' un indirizzo di parola con un altro selettore di
# spazio (vedi CLAUDE.md, `o708`/`o70e`). E' la stessa esclusione che coverage.py
# dichiara, e qui serve a sapere contro cosa si sta misurando: nella regione di
# init sono 1181 op su 9692, cioe' il 12%, e nelle regioni di calibrazione zero.
NOT_COMPARABLE = ('OBJ.WR', 'OBJ.RD', 'MAC.MCTRL', 'MAC.MHF', 'MAC.MHF.RD',
                  'TPL.RAMW', 'GPIO.OUT', 'GPIO.CTL')


def comparable(op):
    """Falso per un'op di una famiglia che il port non ha modo di emettere."""
    return not op.startswith(NOT_COMPARABLE)


def contig_blocks(vops, tops, minsize=16):
    """I blocchi contigui in comune, con il record da cui parte ciascuno.

    difflib da' la struttura giusta: sequenze di op identiche nello stesso
    ordine, che e' esattamente la domanda "fin dove siamo in passo".

    `minsize` decide solo cosa si STAMPA. Il totale si conta su tutti i blocchi:
    filtrare anche il conteggio era un sottoconteggio, e su una finestra da 22951
    op nascondeva ~1500 op vere in run corte. Un buco stampato puo' quindi
    contenere run piu' brevi di minsize, e sulla finestra intera ne contiene:
    dopo le tre MMIO su 0x492 che il tracer vendor non registra il port riprende a
    combaciare per una decina di op alla volta.
    """
    a = [canon_contig(o) for o in vops]
    b = [canon_contig(o) for o in tops]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    blocks = [bl for bl in sm.get_matching_blocks() if bl.size]
    total = sum(bl.size for bl in blocks)
    shown = [(vops[bl.a].ep, bl.a, bl.size) for bl in blocks
             if bl.size >= minsize]
    return shown, total


# ---------------------------------------------------------------------------
# Op del vendore che il port NON deve emettere, dichiarate una per una.
#
# Le regole sono quelle di cmp_skip.py, e valgono per la stessa ragione: una
# lista di eccezioni e' anche il modo piu' comodo di far tornare un numero.
#
#   1. ogni voce ha un `motivo` scritto e, dove serve, un `dopo` che e' il
#      contesto: la voce si applica solo se l'op vendore precedente combacia;
#   2. quante op sono state saltate si stampa SEMPRE, accanto alla percentuale;
#   3. una voce e' legittima solo se si sa perche' il port non emette quell'op.
#      "Si allinea meglio" non e' un motivo.
#
# Perche' contestuale e non a tappeto: l'etichetta TBL.WR/TBL.RD dove la
# emettono TUTTI E DUE i lati sta facendo lavoro di allineamento, ~950 op che
# combaciano e ancorano i blocchi. Toltala da entrambi i lati in compare.py,
# MISURATO: up-ch1 da 14939 a 4665 e quattro finestre a "da guardare". Quindi si
# salta solo dove il port non la emette, e si dice dove.
SKIPS = (
    dict(pattern=r'^TBL\.(WR|RD) id=0x1[ab] off=0x(140|1c0) len=128$',
         dopo=None, max=8, cascata=False,
         motivo="etichetta del tracer, non un accesso: il payload sulla porta "
                "dati la contiene tutta - 0x72 porta (id << 10) | offset, "
                "0x73/0x74 i valori, e len e' il loro numero. Qui il port non "
                "la emette perche' b43_nphy_tx_pwr_ctrl_coef_setup() scrive a "
                "mano sulla porta invece di passare da b43_ntab_write_bulk, e "
                "l'harness intercetta al linker solo le b43_ntab_*. Dove il "
                "driver passa dall'accessor l'etichetta c'e' su entrambi i lati "
                "e combacia, e allora questa voce non si applica."),
)


def apply_skips(vops):
    """Togli dal flusso vendore le op dichiarate in SKIPS. Ritorna (op, saltate).

    Il conteggio torna al chiamante perche' va stampato: una percentuale su un
    flusso potato e non dichiarato e' esattamente il numero comodo che le regole
    di cmp_skip.py vietano.
    """
    left = [dict(r, rx=re.compile(r['pattern']),
                 dopo_rx=re.compile(r['dopo']) if r['dopo'] else None,
                 hits=0) for r in SKIPS]
    out, skipped = [], 0
    for i, op in enumerate(vops):
        drop = False
        for r in left:
            if r['hits'] >= r['max'] or not r['rx'].match(op):
                continue
            if r['dopo_rx'] and not (i and r['dopo_rx'].match(vops[i - 1])):
                continue
            r['hits'] += 1
            drop = True
            break
        if drop:
            skipped += 1
        else:
            out.append(op)
    return out, skipped

# ---------------------------------------------------------------------------
# Le fasi, che sono l'unita' del verdetto.
#
# Un blocco contiguo conta se corrisponde a una FASE: una voce di phy_ops dove
# esiste, oppure - eccezione dichiarata finche' il port non le espone - una macro
# operazione che sappiamo delimitare con un marcatore. Un frammento da due op non
# e' copertura, e sommarlo al totale era contare il sommerso nel PIL: su up-ch1
# 774 blocchi su 879 stanno sotto le 16 op e valgono ~1900 op del totale.
#
# Percio' il numero per fase e' UNO e non e' una somma: la RUN piu' lunga che
# combacia dentro la fase. Non e' gonfiabile da frammenti per costruzione, ed e'
# la stessa misura che la tabella delle finestre chiama `run` e che il README
# dichiara piu' informativa del conteggio dei mismatch.
#
# `marcatore` e' come la fase e' delimitata: si cita, non si sceglie a occhio.
PHASES = (
    dict(rng=(1034, 1739), name='idle-tssi', op='macro: txpwrctrl_idle_tssi',
         marcatore='tono tbl 17 len 160 a #1288, unico della fase'),
    dict(rng=(1740, 2171), name='pwr-setup', op='macro: txpwrctrl_pwr_setup',
         marcatore='26/27 off 0x0 len 64 a #1740'),
    dict(rng=(2172, 3711), name='gain-table', op='macro: tx_gain_table_upload',
         marcatore='26/27 off 0xc0 len 128 a #2172, unica nella finestra'),
    dict(rng=(3738, 4785), name='coeff-setup', op='macro: txpwrctrl_coeff_setup',
         marcatore='la read di 15/0x50 len=7 che apre la funzione, #3738, poi '
                   '26/27 off 0x140 e 0x1c0 len 128 a #3754 #4013 #4271 #4529'),
    dict(rng=(5726, 6500), name='recalc-txpower', op='phy_ops: recalc_txpower',
         marcatore='secondo 26/27 off 0x0 len 64 a #5726, dopo il TPL.RAMW #5672'),
    dict(rng=(7034, 8504), name='perical-ingresso', op='macro: ingresso della cal',
         marcatore='TPC off #7034, get_tx_gain #7038, precal #7234, hand-back #8086'),
    dict(rng=(8505, 10733), name='cal-tx-iqlo', op='macro: cal_txiqlo',
         marcatore='gain di cal len=2 #8511, ripristino #10733'),
    dict(rng=(10962, 14092), name='cal-papd', op='macro: cal PAPD (a4)',
         marcatore='confini di REGIONS, toni #11838 e #12952'),
    dict(rng=(14951, 21136), name='cal-rx-iq', op='macro: cal_rxiq',
         marcatore='BBCFG #14951, gain di cal #14983, ripristino #21136'),
    dict(rng=(21137, 22246), name='coeff-setup-2', op='macro: txpwrctrl_coeff_setup',
         marcatore='26/27 off 0x140 e 0x1c0 len 128 a #21203'),
    dict(rng=(22247, 23771), name='cal-rssi-2', op='macro: rssi_cal',
         marcatore='confini di REGIONS'),
    dict(rng=(23772, 25000), name='coda-idle-tssi', op='macro: idle_tssi + pwr_setup',
         marcatore='tono #23939, 26/27 off 0x0 len 64 a #24391'),
)


MIN_BLOCK = 16


def block_shape(sizes):
    """I blocchi da MIN_BLOCK in su, i ripetuti raccolti come NxM.

    Serve perche' la run da sola sbaglia in un verso preciso: prende il MASSIMO,
    quindi una fase che ripete N volte la stessa sequenza non puo' superare ~1/N
    per costruzione, quanto bene la riproduca. Ed e' il caso di tutte le cal.
    cal-rx-iq fa sei blocchi da 410 esatti, cioe' le sei iterazioni dello sweep
    una per una, e la run dice 7%.

    Sei blocchi da 410 non sono una coincidenza, ottantadue da trenta possono
    esserlo: e' questa la differenza che il totale in blocchi non sa fare e che la
    forma fa vedere senza sommare niente.
    """
    from collections import Counter

    if not sizes:
        return ''
    c = Counter(s for s in sizes if s >= MIN_BLOCK)
    if not c:
        return '(nessuno da %d op)' % MIN_BLOCK
    parts = ['%dx%d' % (n, size) if n > 1 else str(size)
             for size, n in sorted(c.items(), reverse=True)]
    resto = sum(1 for s in sizes if s < MIN_BLOCK)
    out = ' '.join(parts[:4])
    if len(parts) > 4:
        out += ' ...'
    if resto:
        out += ' +%d piccoli' % resto
    return out


def phase_report(vops, blocks):
    """Per ogni fase la run piu' lunga che ci cade dentro, e la forma dei blocchi."""
    print('  %-17s %-30s %6s %8s  %s'
          % ('fase', 'cosa e\'', 'op', 'run', 'blocchi'))
    tot_op = tot_run = 0
    for ph in PHASES:
        lo, hi = ph['rng']
        idx = [i for i, o in enumerate(vops) if lo <= o.ep <= hi]
        if not idx:
            continue
        a, b = idx[0], idx[-1]
        best = 0
        sizes = []
        for rec, vi, size in blocks:
            s0, s1 = max(vi, a), min(vi + size - 1, b)
            if s1 >= s0:
                best = max(best, s1 - s0 + 1)
                sizes.append(s1 - s0 + 1)
        tot_op += len(idx)
        tot_run += best
        print('  %-17s %-30s %6d %5d %3.0f%%  %s'
              % (ph['name'], ph['op'], len(idx), best,
                 100.0 * best / len(idx), block_shape(sizes)))
    print('  %-17s %-30s %6d %5d %3.0f%%'
          % ('TOTALE', 'somma delle run, non delle op', tot_op, tot_run,
             100.0 * tot_run / max(1, tot_op)))
    print('\n  La run e\' la sequenza contigua piu\' lunga dentro la fase: un\n'
          '  frammento non la muove. Le op fuori dalle fasi dichiarate non\n'
          '  compaiono, e non e\' una dimenticanza.\n'
          '\n  La colonna blocchi c\'e\' perche\' la run sbaglia in un verso: prende\n'
          '  il massimo, quindi una fase che ripete N volte la stessa sequenza non\n'
          '  puo\' superare ~1/N, quanto bene la riproduca. `6x410` e `82 piccoli`\n'
          '  sono due cose diverse che la run scrive nello stesso modo.')

def run_contig(vendor, reg, out):
    if reg.get('capture'):
        vendor = merged_vendor(os.path.join(HERE, '..', 'router-data',
                                            'dsl-3580l', reg['capture']))
    lo, hi = (int(x) for x in reg['rng'].split(':'))
    vops = CMP.load_vendor(vendor, (lo, hi))
    vops, skipped = apply_skips(vops)
    tall = CMP.load_test(out)
    if reg.get('anchor'):
        off = find_anchor(tall, CMP.normalize_op(reg['anchor']),
                          reg.get('anchor_nth', 0))
        if off < 0:
            return None, 'ancora non trovata: %s' % reg['anchor']
    else:
        off = 0
    tops = tall[off:]
    drop = reg.get('drop_port', ())
    if drop:
        tops = [o for o in tops if not any(o.startswith(d) for d in drop)]
    blocks, total = contig_blocks(vops, tops, minsize=1)
    return dict(nops=len(vops), blocks=blocks, matched=total,
                skipped=skipped, vops=vops), None


def find_anchor(tops, anchor, nth):
    """L'indice dell'occorrenza `nth` dell'ancora, o -1.

    L'ancora non e' sempre unica dentro un flow: la tabella dei campioni viene
    ricaricata a ogni tono, quindi la sua TBL.WR compare piu' volte e la
    finestra deve poter dire quale delle due la interessa.
    """
    seen = 0
    for i, op in enumerate(tops):
        if CMP.ops_equal(anchor, op):
            if seen == nth:
                return i
            seen += 1
    return -1


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
         what='compensazione PAPD, patches/b43/MESSAGES.md#0003'),
    dict(name='papd-tables', rng='10966:11740',
         anchor='TBL.WR id=0x20 off=0x0 len=64',
         # La cal ora parte da recalc_txpower, che il flow init non
         # chiama: questa finestra ne ha bisogno e usa il flow che la esegue.
         flow=('txpower', '1'),
         what='tabelle scalare ed epsilon della cal, patches/b43/MESSAGES.md#0004 e 0012',
         known='resta una sola op, e non e\' una sequenza: il valore che la '
               'PHY.RD di 0x01 restituisce. Le due tabelle scalare, il '
               'salvataggio del reset RX e le due tabelle epsilon scritte cella '
               'per cella combaciano. Questa finestra e\' ormai un '
               'sottoinsieme della regione papd-cal, che e\' la misura da '
               'guardare.'),
    dict(name='ipa-bias', rng='605:607',
         anchor='PHY.WR addr=0x32f val=0x3',
         flow=('init', '1'),
         what='bias IPA 2 GHz, patches/b43/MESSAGES.md#0005'),
    # Filtri digitali TX dell'init: tre gruppi di 15 coefficienti su 0x186,
    # 0x195 e 0x2c5, le prime tre righe di tbl_tx_filter_coef_rev4.
    # L'unica finestra su una cattura diversa: il download delle tabelle statiche
    # esiste solo in un init a freddo, che la opinit-* non e'.
    dict(name='static-tables', rng='535:1958',
         capture='full-init-ch1-bw20.decoded',
         anchor='PHY.WR addr=0x72 val=0x3400',
         flow=('initpor', '1'),
         what='tabella statica 13 dell\'init a freddo, 1424 op'),
    dict(name='static-tables-2', rng='1959:2764',
         capture='full-init-ch1-bw20.decoded',
         anchor='PHY.WR addr=0x72 val=0x4800',
         flow=('initpor', '1'),
         what='tabella statica 18, 806 op'),
    dict(name='txdigi-filts', rng='289:348', test_len=45,
         anchor='PHY.WR addr=0x186 val=0xfe87',
         flow=('init', '1'),
         what='b43_nphy_int_pa_set_tx_dig_filters',
         known='mancano 15: il vendore riscrive 0x195-0x1a3 con la riga 1 una '
               'seconda volta, con valori IDENTICI alla prima, quindi lo stato '
               'della tabella e\' lo stesso e la differenza e\' solo nel '
               'conteggio delle op. Lo fa in due punti indipendenti della '
               'cattura (#334-348 all\'init, #13904-13918 in coda alla cal). In '
               'b43 quella riscrittura c\'e\' solo nel ramo phy rev 17, dove e\' '
               'altrettanto idempotente.'),
    # La tabella dei campioni, id 17: il tono che ogni cal che suona campioni
    # usa come stimolo. Due finestre perche' le due chiamate hanno ampiezze
    # diverse, e l'ampiezza e' cio' che rende visibile il difetto di 0010.
    dict(name='sampleplay-tssi', rng='1288:1609',
         anchor='TBL.WR id=0x11 off=0x0 len=160',
         flow=('init', '1'),
         what='tono a ampiezza 0 dell\'idle TSSI, 160 word'),
    dict(name='sampleplay-iqlo', rng='8638:8959',
         anchor='TBL.WR id=0x11 off=0x0 len=160', anchor_nth=1,
         flow=('initcal', '1'),
         what='tono 2500 kHz ampiezza 250 della cal TX IQ/LO, patches/b43/MESSAGES.md#0010'),
    dict(name='rssi-cal', rng='3723:3740',
         # I nove registri dei coefficienti: 0x1b8 e gli otto RSSIMC. Qui il
         # confronto che conta e' sullo STATO, non sulla sequenza.
         finali=(0x1b8, 0x1a4, 0x1a5, 0x1a6, 0x1a7,
                 0x1aa, 0x1ab, 0x1ac, 0x1ad),
         finali_len=200,
         anchor='PHY.WR addr=0x1b8 val=0x3f',
         flow=('init', '1'),
         what='coefficienti di moltiplicazione RSSI',
         allow=('PHY.RD', 'RAD.RD', 'RAD.MOD', 'PHY.WR addr=0x1d',
                'PHY.WR addr=0x1c', 'PHY.MOD'),
         known='i nove valori combaciano col vendore da quando la parentesi di '
               'abs() e\' al suo posto (patches/mainline, cal RSSI): 0x1b8 = 0x3f '
               'e otto 0x3e. Quello che resta non e\' un valore: il vendore scrive '
               'gli otto di fila in 16 op, il port ne mette ~140 perche\' scrive '
               'ogni coefficiente due volte, zero e poi il valore, e intercala le '
               'read e gli override RF. Allargando test_len a 200 gli otto 0x3e si '
               'appaiano per multiinsieme, ma entrano 37 op del port che il '
               'vendore in questa finestra non ha: le due finestre non sono '
               'commensurabili. Questa fase vuole un confronto sul VALORE FINALE '
               'dei nove registri, che e\' un\'asserzione che questo strumento non '
               'fa. Restano fuori anche due table-read del vendore, TBL.RD id=0x7 '
               'off=0x110 (il salvataggio del tx gain originale, che 0014 non '
               'porta) e TBL.RD id=0xf off=0x50.'),
    # Fasi della calibrazione PAPD, dalla mappa in docs/papd-cal-map.md. Non
    # passano e non devono: b43 la cal PAPD non ce l'ha. Sono qui pronte per
    # quando la si porta, cosi' si verifica una fase per volta.
    dict(name='txpwr-index', rng='15285:15340',
         # Una chiamata sola di txpwr_index dentro lo sweep, per giudicare la
         # posizione invece di riallineare a mano - cosa che mi e' andata storta
         # tre volte. L'ancora e' la read del gain all'indice 10 sul core 0.
         anchor='TBL.RD id=0x1a off=0xca len=1', anchor_nth=0,
         # La cal ora parte da recalc_txpower, che il flow init non
         # chiama: questa finestra ne ha bisogno e usa il flow che la esegue.
         flow=('txpower', '1'),
         what='txpwr_index: gain, dac, radio gain, il moltiplicatore in due celle',
         known='le celle per indice della tabella di potenza (26/0x14a, 0x1ca, '
               '0x24a) le serve il mirror della TABELLA e non piu\' quello del '
               'registro, e dentro questa finestra 26/0x14a torna 0x0000 su '
               'entrambi i lati (trace_tables.py --cell 0x1a:0x14a). Restano '
               'sei op, e sono tre cose. Due sono la RILETTURA di 26/0x24a, '
               'e non e\' una divergenza del port: i due lati SCRIVONO lo '
               'stesso 0xffffffe9 (#2319 il port, #2768 il vendore), e '
               'l\'hardware lo rilegge troncato a 9 bit, 0x01e9. Misurato su '
               'cinque celle su cinque in 26/27 oltre l\'offset 576 '
               '(0x24a 0x24c 0x25e), riletto == scritto & 0x1ff, e il mirror '
               'della tabella tiene i 32 bit interi. E\' inerte: il solo '
               'consumatore e\' b43_nphy_txpwr_index(), che fa '
               '(((s16)v) << 4) & 0x1ff0, e i due valori danno lo stesso '
               '0x1e90 sul maskset di PAPD_EN. Delle altre due, il bbmult: il '
               'vendore legge 0x2c2c e scrive 0x2e2c, il port fa 0x2e2e in '
               'entrambe, cioe\' sta su un indice diverso; e 0x1e7, 0xa contro '
               '0x19. La sesta e\' di forma: il vendore fa TBL.WR 26 off 0x40 '
               'len 84 dove il port apre la porta dati a mano.'),
         # Il punto di chiamata di coef_setup non e' fra le cose che restano da
         # trovare: b43 la chiama due volte come il vendore, e nei due punti
         # giusti - una in coda all'init prima delle cal, una dentro la cal
         # periodica dopo la RX IQ. La fase coeff-setup lo misura, 1037 op su
         # 1037 fra la read che la apre e i quattro blocchi che la chiudono.
         # Quello che diverge nella SECONDA e' il contenuto del buffer che la
         # alimenta: 15/0x50-0x53 sono i coefficienti che la cal TX IQ/LO
         # produce, il vendore ci ha 0x59/0x013 e il port zeri, perche' in
         # userspace quella cal non misura niente (test/README.md, il cursore
         # dei piani). Percio' la seconda coeff-setup si chiude quando si
         # chiude la cal TX IQ/LO, non prima, e non con un'altra chiamata.
    dict(name='adj-pwr-tbl', rng='5986:6070',
         # Le 84 celle della tabella di potenza aggiustata, la sola fase in cui
         # due board si controllano a vicenda: la 3580L ha le nibble SROM tutte
         # uguali e non discrimina niente, la vd630 le ha da 2 a 8. Con i due
         # tetti per gruppo di 0025: 84 su 84 qui, 82 su 84 sulla vd630, e le
         # due che restano sono uno sfasamento di un gruppo nella colonna a una
         # catena, non un valore sbagliato.
         anchor='TBL.WR id=0x1a off=0x40 len=84', anchor_nth=4,
         flow=('txpower', '1'),
         what='adj_pwr_tbl: 84 celle, quattro colonne per numero di catene'),
    dict(name='recalc-txpower', rng='5726:6244',
         # La fase che nella tabella per fase fa 1 op su 716, e non perche' il
         # port non la sappia fare: la fa, ma in fondo alla traccia invece che in
         # mezzo all'init, dove la mette il vendore. Questa finestra la confronta
         # SENZA la posizione, agganciandosi alla terza apertura di 26/0x0 - le
         # prime due sono l'init - cosi' si vede se le op sono le stesse.
         #
         # Il cortocircuito di b43_nphy_op_recalc_txpower resta: se le tabelle le
         # ha gia' scritte l'init, uscire subito salta lavoro ridondante. Il flow
         # invalida la cache per rendere la fase osservabile, non per correggerla.
         anchor='TBL.WR id=0x1a off=0x0 len=64', anchor_nth=2,
         flow=('txpower', '1'),
         what='recalc_txpower: pwr_setup piu\' txpwrctrl_enable, sei table-op'),
    dict(name='papd-digifilt', rng='11741:11755',
         anchor='PHY.WR addr=0x186 val=0xfed9',
         flow=('init', '1'),
         what='filtri digitali TX della cal, riga 3 su 0x186-0x194',
         pending='cal PAPD non portata: b43 ha la riga 3 di '
                 'tbl_tx_filter_coef_rev4 ma nessun equivalente di '
                 'wlc_phy_ipa_restore_tx_digi_filts_nphy, che la scrive solo '
                 'per la durata della cal.'),
    dict(name='chanswitch-ch6', rng='34940:34990', test_len=42,
         anchor='RAD.WR addr=0x16 val=0x58',
         flow=('chanset', '6'),
         what='upload della chantab al cambio canale',
         allow=('MMIO.', 'PHY.WR addr=0x1d3'),
         known='nessuna op mancante da quando 0011 scrive i dieci campi 5 GHz '
               'intercalati. Le prime 33 combaciano; dalla 34 il port infila tre '
               'MMIO su 0x492 (deroga dichiarata: il tracer vendor non le '
               'registra li\') e da li\' in poi le due sequenze sono sfasate di '
               'tre, con le stesse op e gli stessi valori.'),
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


def final_values(ops, regs):
    """L'ultimo valore scritto su ciascun registro, nell'ordine in cui capita.

    Serve alle finestre dove il confronto posizionale non puo' dire niente di
    utile: quando i due lati arrivano allo stesso stato per strade diverse - il
    vendore scrivendo ogni registro una volta, il port scrivendone alcuni due
    volte, zero e poi il valore - contare le op misura la strada e non lo stato.
    Il criterio che conta la' e' se i registri finiscono con lo stesso contenuto,
    e questa e' l'unica cosa che lo dice.

    Non sostituisce la run: una finestra puo' avere lo stato giusto e la sequenza
    sbagliata, e sono due difetti diversi che vanno visti tutti e due.
    """
    out = {}
    for op in ops:
        m = re.match(r'(PHY|RAD|MMIO)\.WR addr=(0x[0-9a-f]+) val=(0x[0-9a-f]+)', op)
        if not m:
            continue
        addr = int(m.group(2), 16)
        if addr in regs:
            out[addr] = int(m.group(3), 16)
    return out


def run(vendor, win, verbose):
    # Una finestra puo' dichiarare la propria cattura con `capture`: le finestre
    # nate contro l'init a caldo (opinit-*) non si possono ancorare a fasi che
    # solo un init a freddo contiene, come il download delle tabelle statiche.
    if win.get('capture'):
        vendor = os.path.join(HERE, '..', 'router-data', 'dsl-3580l',
                              win['capture'])
    out = os.path.join('/tmp', 'phase_%s.out' % win['name'])
    flow, chan = win['flow']
    with open(out, 'w') as fh:
        r = subprocess.run([os.path.join(HERE, 'nphy_trace'), flow, 'dsl3580l', chan],
                           stdout=fh, stderr=subprocess.DEVNULL)
    if r.returncode:
        return None, 'harness uscito con %d' % r.returncode

    lo, hi = (int(x) for x in win['rng'].split(':'))
    vops = CMP.load_vendor(vendor, (lo, hi))
    vops, skipped = apply_skips(vops)
    tall = CMP.load_test(out)
    if not vops:
        return None, 'finestra vendore vuota'

    nth = win.get('anchor_nth', 0)
    off = find_anchor(tall, CMP.normalize_op(win['anchor']), nth)
    if off < 0:
        return None, 'ancora non trovata%s: %s' % (
            '' if not nth else ' (occorrenza %d)' % nth, win['anchor'])

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

    # L'asserzione sullo stato, per le finestre che la dichiarano con `finali`.
    regs = win.get('finali')
    if regs:
        # Lo span del port e' il suo, dichiarato: il confronto posizionale usa
        # tante op quante ne ha il vendore, e su quelle il port ha appena
        # scritto gli zeri e non ancora i valori. Troncare li' misurerebbe uno
        # stato intermedio e direbbe che non combacia niente.
        fspan = win.get('finali_len', span)
        fv = final_values(vops, set(regs))
        ft = final_values(tall[off:off + fspan], set(regs))
        diff = {r: (fv.get(r), ft.get(r)) for r in regs
                if fv.get(r) != ft.get(r)}
        res['finali'] = (len(regs) - len(diff), len(regs), diff)

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
        if res.get('finali') and res['finali'][2]:
            print('  registri che NON finiscono sullo stesso valore:')
            for r, (a, b) in sorted(res['finali'][2].items()):
                fmt = lambda x: 'mai scritto' if x is None else '0x%04x' % x
                print('    0x%03x  vendore %s   port %s' % (r, fmt(a), fmt(b)))
    return res, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--vendor', required=True)
    ap.add_argument('--only', help='una sola finestra, per nome')
    ap.add_argument('-v', '--verbose', action='store_true',
                    help='stampa le differenze, e la diagnosi per multiinsieme')
    ap.add_argument('--flow', default='init',
                    help='il flow da far girare (init, initcal, full, ...)')
    ap.add_argument('--channel', default='1')
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
            subprocess.run([os.path.join(HERE, 'nphy_trace'), args.flow,
                            'dsl3580l', args.channel], stdout=fh,
                           stderr=subprocess.DEVNULL)
        tops = CMP.load_test(out)
        import difflib
        sm = difflib.SequenceMatcher(None, vops, tops, autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        matched = set()
        for b in blocks:
            matched.update(range(b.a, b.a + b.size))
        blocks.sort(key=lambda b: -b.size)
        print('flow %s, vendore %d op, port %d op' % (args.flow, len(vops),
                                                     len(tops)))
        print('run piu\' lunghe (op consecutive che combaciano):')
        for b in blocks[:8]:
            print('  %4d op   vendore @%-6d port @%-6d   prima: %s'
                  % (b.size, b.a, b.b, vops[b.a][:58]))
        tot = len(matched)
        print('\ntotale op in comune: %d su %d del vendore (%.0f%%), in %d blocchi'
              % (tot, len(vops), 100.0 * tot / max(1, len(vops)), len(blocks)))
        print('\nper regione (il numero di record se lo porta dietro l\'op, '
              'vedi CMP.Op):')
        print('  %-34s %-16s %6s %9s %7s %9s'
              % ('regione', 'record', 'op', 'appaiate', 'n.conf', 'su conf.'))
        tot_nc = 0
        for rlo, rhi, name in REGIONS:
            idx = [i for i, o in enumerate(vops) if rlo <= o.ep <= rhi]
            if not idx:
                continue
            m = sum(1 for i in idx if i in matched)
            nc = sum(1 for i in idx if not comparable(vops[i]))
            tot_nc += nc
            conf = len(idx) - nc
            print('  %-34s %-16s %6d %5d %3.0f%% %7d %8.0f%%'
                  % (name, '#%d-%d' % (rlo, rhi), len(idx), m,
                     100.0 * m / len(idx), nc,
                     100.0 * m / conf if conf else 0.0))
        if tot_nc:
            print('\n  n.conf: op di famiglie che il port non puo\' emettere, '
                  'perche\' l\'harness compila')
            print('  il PHY e non il core, e perche\' la object memory ha un '
                  'encoding diverso. Sono')
            print('  ' + ' '.join(sorted(NOT_COMPARABLE)) + '.')
            print('  Stessa esclusione che coverage.py dichiara per la SHM. Il '
                  'totale in blocchi')
            print('  contigui sopra NON le esclude: questa colonna dice contro '
                  'cosa si misura.')
        return 0

    for reg in CONTIG:
        if args.only and reg['name'] != args.only:
            continue
        rout = '/tmp/phase_%s.out' % reg['name']
        flow, chan = reg['flow']
        env = dict(os.environ)
        if reg.get('plan_from'):
            env['B43_TEST_PLAN_FROM'] = reg['rng'].split(':')[0]
        # Fuori dalle regioni che lo chiedono NON si passa, e non e' una
        # dimenticanza. Posizionare
        # il cursore all'ingresso della regione sembra la cosa giusta e
        # MISURATO PEGGIORA: papd-cal scende da 1830 a 1816 op in blocchi e il
        # primo blocco da 847 a 843, perche' dentro la regione i piani servono
        # valori dove il mirror era giusto - le quattro read AFE. Il knob c'e' in
        # wrap.c per indagarlo; finche' non si sa quale read sfasa, il mirror e'
        # meno bugiardo. Vedi CLAUDE.md, Prossimo passo.
        with open(rout, 'w') as fh:
            subprocess.run([os.path.join(HERE, 'nphy_trace'), flow,
                            'dsl3580l', chan], stdout=fh,
                           stderr=subprocess.DEVNULL, env=env)
        res, err = run_contig(vendor, reg, rout)
        print('regione %s (%s): %s' % (reg['name'], reg['rng'], reg['what']))
        if err:
            print('  %s\n' % err)
        else:
            print('  %d op del vendore, %d in blocchi contigui (%.0f%%);'
                  ' la forma per fase e\' nella colonna blocchi'
                  % (res['nops'], res['matched'],
                     100.0 * res['matched'] / res['nops']))
            if res['skipped']:
                print('  %d op saltate per skip dichiarati (SKIPS in questo'
                      ' file), non contate nel denominatore' % res['skipped'])
            if reg['name'] == 'up-ch1':
                phase_report(res['vops'], res['blocks'])
            print()

    if args.only and any(r['name'] == args.only for r in CONTIG):
        return 0

    bad = known = pending = 0
    print('%-16s %-5s %-8s %-9s %s'
          % ('finestra', 'op', 'run', 'esito', 'cosa copre'))
    for win in WINDOWS:
        if args.only and win['name'] != args.only:
            continue
        res, err = run(vendor, win, args.verbose)
        if err and win.get('pending'):
            # Fase non ancora portata: non trovare l'ancora e' lo stato atteso.
            print('%-16s %-5s %-8s %-9s %s'
                  % (win['name'], '-', '-', 'assente', win['what']))
            print('%-30s %s' % ('', win['pending']))
            pending += 1
            continue
        if err:
            print('%-16s %-5s %-8s %-9s %s'
                  % (win['name'], '-', '-', 'ERR', err))
            bad += 1
            continue

        run_s = '%d/%d' % (res['run'], res['nops'])
        diag = ''
        # Lo stato finale, dove dichiarato, va nella riga di riepilogo: e' il
        # verdetto che conta per le finestre in cui i due lati raggiungono lo
        # stesso stato per strade diverse, e nasconderlo dietro -v lo rende
        # inutile.
        if res.get('finali'):
            ok, tot, _ = res['finali']
            diag = 'stato finale %d/%d registri' % (ok, tot)
        if res['mismatch']:
            diag = ((diag + '; ') if diag else '') + \
                'mancano %d, in piu\' %d' % (sum(res['missing'].values()),
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

        print('%-16s %-5d %-8s %-9s %s'
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
