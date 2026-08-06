# CLAUDE.md

Cosa serve sapere prima di toccare qualcosa. Corto di proposito: il dettaglio sta
in `docs/INDEX.md`, qui c'è solo ciò che serve per non ripetere errori già fatti.

## Il progetto

Portare in b43 il supporto **BCM6362 / N-PHY rev 8 / radio 2057 rev 8**, guidati
da una cattura MMIO del driver proprietario `wl 6.30.102.7`. Sette patch già
merged in mainline (`docs/upstream-status.md`), quattordici in `patches/b43/`. **Niente
ha mai girato su hardware**: tutto è verificato riproducendo la cattura in un
harness che compila il vero `phy_n.c`.

## Setup, ogni volta

```sh
sh scripts/fetch-upstream-state.sh ~/src/linux      # sparse, ~60 MB, sha 848acc8ffe1b
cd ~/src/linux
for p in .../patches/mainline/*.patch; do git apply "$p"; done   # tutte e cinque
for p in .../patches/b43/0*.patch; do git apply "$p"; done       # 0010 conflitta, e va bene
cd test && make KDIR=~/src/linux && make KDIR=~/src/linux warncheck
./phase_compare.py --vendor ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
```

**`patches/mainline/` fa parte del baseline, e per un giro questa sezione non lo
diceva.** Con la sola serie `b43/` le due finestre danno **5769** e **8724**, non
5791 e 8746: le 22 op di differenza sono due delle cinque patch mainline, misurate
una per volta — `rf-control-override-value-masks` vale **+14** e
`fifth-tx-power-up-override` **+8**, le altre tre zero. Se il numero non torna,
guardare qui prima di cercare altrove.

L'ordine giusto e' mainline **prima**: cosi' applicano tutte e cinque, e poi
`b43/0010` conflitta perche' `mainline/...sample-table-logic` porta le stesse due
modifiche — e' il conflitto atteso, quello che `patches/mainline/README.md` dice da
sempre. Applicando la serie prima, il conflitto si sposta sulla patch mainline; il
tree che ne esce e' lo stesso e i numeri anche, verificato.

Dentro la serie le patch **vanno applicate in ordine**. La catena di dipendenze,
misurata con `git apply` sull'albero pulito: 0004 dipende da **0002** (contesto in
`tables_nphy.c`), 0009 da 0004, 0012 da **0009**. 0003 non serve a nessuna delle
tre.

## Strumenti

| cosa | dove |
|---|---|
| harness, flow `init initpor initcal full chanset rfkill txpower` | `test/nphy_trace` |
| confronto per fase, 14 finestre | `test/phase_compare.py` |
| confronto globale + per regione | `test/phase_compare.py --global-run DA A --flow F` |
| copertura per insiemi di celle | `test/coverage.py` |
| normalizzazione, `Op` con `.ep` | `test/compare.py` |
| **seed**: lo stato che `op_init` e `rfkill` lasciano | `reverse-tools/gen_seed.py` → `test/seed_up.h` |
| accessi SHM, clock PHY, macfreq, confini MAC (catture nuove) | hook `wlc_bmac_*` in `wl-diag/wl_diag.c` |
| buchi di dispatch, xref brcmsmac, gating delle patch | `reverse-tools/*.py` |

## Stato

`13 finestre: 0 da guardare, 4 divergenze note` piu' **due** finestre vere:
`up-ch1` (**12363 op su 22951, 54%**) e `up-ch1-freddo` (**14353 su 27571, 52%**)

Ci sono arrivate con due patch. `0018` e' la cal RX IQ — il guscio di
`wlc_phy_cal_rxiq_nphy_rev3`, `b43_nphy_txpwr_index()` e **lo sweep di gain** — e
vale **+5761**, da 5791 a 11552. `0019` e' il **gain di pre-calibrazione**, e vale
altri **+811**.

`0019` e' la piu' piccola e la piu' istruttiva: tre righe, e sistemano un **valore
sbagliato** invece di un'op mancante, che e' il motivo per cui nessuno l'aveva
preso. Il port scriveva `0x4027` nelle due celle di gain RFSEQ dove la cattura
scrive `0x4077`, a #8511 e a #14983, e `pad` valeva 4 invece di 14. Non era la
decodifica: `b43_nphy_get_tx_gains()` e `b43_nphy_iq_cal_gain_params()` sono riga
per riga il riferimento, e i due driver leggono lo stesso `0x4027` dalla tabella.
Mancava il passo **in mezzo**: `wlc_phy_precal_txgain_nphy()` programma un indice
di potenza e *poi* si rileggono i gain. La cattura fa vedere le due letture,
`0x4027` a #7038 e `0x4077` a #8080, e mainline lo sapeva — la riga prima della
seconda lettura era `/* TODO N PHY Pre Calibrate TX Gain */`.

**L'indice e' 10, e non e' quello che il riferimento sceglierebbe**: brcmsmac tiene
10 per radio 2057 rev 3, 4 e 6 e 0 per tutto il resto, quindi il rev 8 finirebbe su
0. La cattura legge `off=0xca`, cioe' `192 + 10`. Il raggruppamento di brcmsmac e'
piu' vecchio di questo radio, esattamente come quello dell'rccal (voce 5 di
`gap-inventory.md`), e decide la cattura.

E `0019` **ha un costo, misurato**: sulla sola regione della cal PAPD,
#10962-14092, il port passa da 2023 op appaiate su 2662 a **2014**, e da 16 blocchi
contigui a 25; se lo portano #12700-12950 (−6 su 164) e #13700-13870 (−6 su 114).
Nove op contro 811 e' uno scambio da fare, ma **perche' la cal PAPD combaci un po'
peggio quando gira al gain che usa il vendore non e' spiegato**, ed e' la prossima
cosa da guardare.

E il numero non e' il punto: **la forma torna**. La cattura fa tre iterazioni per
core, ognuna un indice di potenza seguito dal suo tono, e il port fa le stesse tre,
ognuna come run di **85, 103, 85 e 420 op** appaiate. I registri PHY coperti passano
da 194 su 218 a **203**.

Un blocco del baseline cambia mano e **non e' una regressione**: le 172 op a #13921,
i due azzeramenti da 84 celle della tabella di controllo potenza, perdono
l'assegnazione a favore di uno dei sei identici che lo sweep ora fa. Misurato su
quella regione da sola il port e' identico prima e dopo — stesse 172 op dalla stessa
posizione, 178 su 183. **Quando un blocco si accorcia si misura la regione da sola
prima di chiamarla regressione**, perche' l'assegnazione e' esclusiva e golosa.

Run intera: flow `full` contro `opinit-ch1-ch6-bw20.decoded` #132-26100, cioe'
il suo primo `up` a canale 1. Per regione, coi numeri di prima dello sweep:

| regione | record | appaiate |
|---|---|---|
| init vero e proprio | #132-10961 | 36% |
| cal PAPD (`a4`) | #10962-14092 | **76%** |
| cal RX IQ, ingresso | #14093-15920 | **0%** |
| cal RX IQ, sweep di gain | #15921-22246 | **9%**, 5812 op, la più grande |
| seconda cal RSSI | #22247-23771 | 0% col flow `full`, 46% col flow `init` |
| coda | #23772-26100 | 29% |

Il totale della global run **non si guarda**: e' oscillato 5953 → 7075 → 5783 su
cambiamenti che hanno solo migliorato la fedelta', perche' l'assegnazione dei
blocchi e' esclusiva e un blocco lungo altrove si porta via le op. Il numero da
guardare e' `up-ch1`. La cal PAPD e' salita da 26% a 68% perche' il suo guscio c'e'
(`patches/b43/0015`): restano fuori `a3`/`a2`, due buchi da 349 e 276 op.

`cal RX IQ, ingresso` e' scesa da 5% a 0%: le 84 op che prima risultavano
appaiate erano coincidenze posizionali, non codice, e lo spostamento del resto le
ha spazzate. **Da guardare**, non da archiviare.

## La struttura della cattura

`wlc_phy_a4` è la cal PAPD e gira **una volta per init**; `a3_nphy` (147 righe)
cerca l'indice di gain e **legge** la tabella epsilon, `a2_nphy` (279) la
**scrive**. Mappa completa in `docs/papd-cal-map.md`, flusso affiancato dei due
driver in `docs/init-flow.md`.

`do_full_init` (b43) == `phy_init_por` (brcmsmac): dietro ci stanno il download
delle tabelle statiche e rcal/rccal.

## Le finestre, che sono due: una per comportamento

`CONTIG` in `phase_compare.py` ha **due** voci, e sono la stessa macro operazione
nei suoi due comportamenti. Non sono due fasi: sono due strade che il codice
prende, e una fase di calibrazione verificata contro una cattura sola valida un
ramo e non dice niente dell'altro.

| finestra | cattura | flow | op | in blocchi |
|---|---|---|---|---|
| `up-ch1` | `opinit-*`, init a caldo | `init` | 22951 | **5791, 25%** |
| `up-ch1-freddo` | `full-init-*`, init completo | `initpor` | 27571 | **8746, 32%** |

`up-ch1` comincia dove comincia `switch_channel` — la `CHANSPEC` di **#132**, che
il tracer emette e il port no — e finisce col **MAC abilitato che trasmette**,
#26100. Nessuna ancora: la finestra e' tutta la run, quindi i blocchi si trovano
sull'intero output del flow senza agganciarsi a un'op scelta a mano.

`up-ch1-freddo` parte dalla `CHANSPEC` di **#339** e finisce a **#32769**, che non
e' il MAC abilitato ma il limite di confrontabilita': quella cattura ha un buco da
65285 record oltre quel punto. Copre **piu'** dell'altra perche' contiene il
download delle tabelle statiche, che a caldo non c'e' — si vedono come blocchi da
**1424** e **806** op, che sono le due vecchie finestre `static-tables`.

**Il parametro giusto adesso c'e': `patches/b43/0017`.**
`b43_nphy_cal_perical_phyinit()` non inchioda piu' `true`: calcola full o parziale
come il riferimento, cioe' `fullcal = (canale != canale dell'ultima cal TX IQ/LO)`,
lo stesso test che `b43_nphy_restore_cal()` fa gia' prima di riusare i
coefficienti. Il tipo della cal RX IQ resta **2** e non e' una dimenticanza:
brcmsmac chiede 2 alla prima cal dopo un'associazione e 0 dopo, b43 non traccia
niente di equivalente, e fra le due costanti 2 e' la conservativa perche' 0 salta
quasi tutto.

Su questa cattura **non sposta op**, e il motivo va detto: entrambe sono di
un'interfaccia che sale su un canale non ancora calibrato, quindi il test viene
`full` in tutte e due. Cambia dalla seconda volta in poi, che nessuna cattura
copre.

Ha fatto uscire un buco dell'harness, e quello si misurava: `main.c` azzerava fra i
due init `rssical_chanspec` e `iqcal_chanspec` «perche' il secondo sia lo stesso
init della cattura» e **non `txiqlocal_chanspec`**. Con `0017` un secondo init che
la trovava valorizzata prendeva la strada parziale: `up-ch1` perdeva **24 op**.
Azzerata anche quella, la finestra torna a 5791 — cioe' le tre parti dello stato di
cal vanno azzerate insieme, non due su tre.

Attenzione a cosa NON e' il discriminante, perche' e' la strada che sembra giusta:
il `full_cal` di `wlc_phy_a4(pi, bool full_cal)` e' **dichiarato e mai usato** nel
corpo, e i tre chiamanti passano tutti `true`; e `pi->nphy_papd_cal_type`, che
sceglie fra `CAL_FULL` e `CAL_SOFT` per l'epsilon, non viene **mai scritto** in
tutto `phy_n.c`, quindi resta 0. Metterli in b43 sarebbe trascrivere peso morto.
Quello che discrimina e' il tipo passato a `cal_rx_iq`, che b43 riceve e poi
**butta** — `b43_nphy_cal_rx_iq` degrada `type` da 2 a 0 su rev >= 7,
`gap-inventory.md` 4a bis.

**Il tipo di calibrazione cambia il comportamento del vendore, e si misura.** `wlc_phy_a4(pi,
full_cal)` e `wlc_phy_a2_nphy(..., CAL_FULL | CAL_SOFT, ...)` prendono strade
diverse: nell'intervallo della cal PAPD i buchi di `a3`/`a2` sono **349 e 276** op
a caldo e **920 e 930** a freddo, perche' la' la ricerca dell'indice di gain e'
completa. `initpor` e' l'unico flow che traccia un init a freddo **con** le cal:
non azzera `perical`, quindi passa dal ramo di `0014`.

Tutto cio' che precede, **#1-131, e' `op_init` e `rfkill`**: e' lo stato che questa
finestra non puo' avere, e si **semina** invece di tracciarlo (sotto).

Le region per fase sono state provate e togliere, quattro in altrettante sessioni,
e non e' un ripensamento estetico: **una fase presa da sola non dice niente su
cio' che le arriva addosso da prima**. La finestra `chanswitch-ch6` diceva 33/39 e
"nessuna op mancante", e la fase intera sta al **14%**, perche' il 62% e' un ciclo
di misura che il port non fa affatto. Il verdetto di `up-ch1` e' la **struttura dei
blocchi**, non una percentuale: un blocco che si accorcia e' una regressione anche
se il totale sale.

Due cose sulla lettura del report, imparate sbagliando:

- **`minsize` filtra la stampa, non il conteggio.** Filtrarlo anche nel totale ha
  dato **5162 invece di 5791** per una sessione: ~630 op vere in run piu' corte di
  16 sparite dal numero. Un buco stampato puo' contenere run brevi.
- **"Zero occorrenze" non prova niente**, e ci sono cascato due volte di fila.
  Puo' voler dire che il tracer non guarda o che `wl` non lo fa, e le due hanno
  conseguenze opposte sul port. Si risolvono guardando **dove l'accesso passa**:
  - `PMU.` era in deroga per sbaglio: `wl-diag` aggancia `si_pmu_spuravoid` (il
    decoder lo stampa `PMU.SPUR`) e la funzione e' quella che mainline chiama
    `bcma_pmu_spuravoid_pllupdate` (`drivers/bcma/driver_chipcommon_pmu.c:493`),
    cioe' esiste ed e' agganciabile: zero occorrenze vuol dire che **wl non la
    chiama**, e il `PMU.SPUR` del port e' una divergenza vera.
  - `MMIO.` e' in deroga, ma la motivazione giusta e' il **livello**, non il
    conteggio: quegli accessi il vendore li registra come **`SI.COREREG`** (54
    nella cattura, `core=0x0`, `off=0x64` e `0x6c`), quindi cercare `MMIO.` non
    prova niente. `0x492` e' `psm_phy_hdr_param`, e in brcmsmac ci si arriva con un
    `bcma_write16(pi->d11core, D11REGOFFS(psm_phy_hdr_param), ...)` **diretto**, non
    con un accessor (`phy/phy_n.c` in `wlc_phy_chanspec_nphy_setup`, e i bit stanno
    in `d11.h:978`): un tracer che aggancia funzioni non lo vede, e infatti nella
    cattura non c'e'.
  - `PHY.CLK` e `MAC.FREQ` restano in deroga **non dimostrata**:
    in brcmsmac sono `brcms_b_core_phy_clk` e `brcms_b_switch_macfreq`
    (`main.c:722` e `main.c:2096`), cioe' accessor veri e agganciabili, e finche'
    non lo sono zero occorrenze non dice niente. Si chiude
    con due hook in `wl-diag` e una cattura nuova.

  Regola: una deroga si dichiara **contro un hook mancante**, mai contro un
  conteggio a zero — e prima di dichiararla si guarda se **l'accessor esiste**.
  La famiglia degli accessor e' grande — in brcmsmac sono **66 `brcms_b_*`**, che
  sono gli stessi rinominati — e `wl-diag` ne agganciava **dieci**: le mancanti
  erano la ragione di tutte e tre le deroghe. Aggiunte `read_shm`,
  `write_shm`, `set_shm` (offset in **byte**, lo stesso livello di
  `b43_shm_*16`: e' cio' che rende confrontabili i **677 offset SHM** che prima
  erano rumore), `core_phy_clk`, `switch_macfreq`, e
  `suspend_mac_and_wait`/`enable_mac`, che danno il confine **MAC abilitato** su
  cui finisce la finestra `up-ch1`.

  Gli accessi che **non** passano da un accessor restano non osservabili, e la
  deroga si dichiara contro quello: `psm_phy_hdr_param` in
  `psm_phy_hdr_param` si scrive diretto, come si vede in brcmsmac. Una
  variante che marcava l'ingresso delle funzioni del PHY e' stata provata e
  **togliere di proposito**: marcare le funzioni interne produce una mappa della
  struttura del driver del vendore, che e' cosa diversa dall'osservare l'hardware
  e molto piu' facile da contestare. Un confine di fase si ricava dalle op degli
  accessor, e `MAC.SUSP`/`MAC.EN` ne danno uno esplicito. Vale per le **catture
  nuove**. Primo blocco `up-ch1`: **33 op**, e le tre op in piu' del port
  restano visibili perche' sono vere.

Dentro `up-ch1` la cal PAPD si legge cosi', ed e' il modo in cui va citata da qui
in avanti: blocchi a #10966 (847 op), #11822 (334), #12784 (145), #12936 (334),
#13752 (90), #13856 (48), #13921 (172).

**Le catture sono due e servono a cose diverse.** `opinit-ch1-ch6-bw20.decoded`
(70796 record) e' il riferimento di tutto quello che sta qui sopra: e' un init **a
caldo** e non contiene il download statico — l'apertura della tabella 10 non
compare in nessuno dei suoi due init — e per questo il flow `init` fa due init e
traccia solo il secondo. `full-init-ch1-bw20.decoded` (81397 record) e' un init **a
freddo**, ed e' la sola che contenga le tabelle di init: contro quella, col flow
`initpor`, il port **le riproduce op per op** — 1424/1424 sulla tabella 13 e
806/806 sulla 18, finestre `static-tables` e `static-tables-2`, le uniche due che
dichiarano `capture=`. Ha un buco da 65285 record oltre #32769, quindi solo
#2-32769 e' confrontabile posizionalmente.

I numeri di record qui e nei documenti sono di `opinit-*` quando non e' detto
altrimenti: gli intervalli esistono in entrambi i file e **non si
autoidentificano**.

In mainline la cal periodica non parte: `perical = 2`, e il ramo che ne consegue in
`b43_phy_initn` è un `;/* TODO */`. `0012` ci mette l'init delle tabelle PAPD e
`0014` la sequenza del vendore — TX IQ/LO, PAPD, RX IQ, coefficienti di potenza,
RSSI — gateata su phy rev 8 e radio rev 8, e dipende da `0012`. Misurato sul flow
`init`: seconda cal RSSI da **0% a 46%**, coda da 8% a 32%, totale da 4434 a 5949
op su 22951. Il flow `full` non si muove, perché mette `perical = 0` e prende
l'altro ramo. Resta fuori il cuore, `a2`/`a3`, e con lui la cal PAPD vera:
`b43_nphy_papd_cal()` è il segnaposto di `0012`.

## I seed, e quanto valgono

`reverse-tools/gen_seed.py --before 132` guarda **solo i record che precedono la
finestra** ed emette `test/seed_up.h`, che `main.c` applica dopo l'init a freddo e
prima di quello tracciato. Due categorie:

1. cio' che `op_init` e `rfkill` hanno programmato;
2. cio' il cui **primo accesso nella cattura e' una read**: nessuno l'ha scritto,
   quindi e' il default del chip. Il criterio non e' "mai scritto" — `0x17d` la cal
   la scrive, ma **dopo** averla letta. Con questo entrano le due `atten` del
   coupler a `0xaa`, che erano l'ultimo buco di valore della cal PAPD.

Totale 68 phy e 70 radio, di cui 91 default. **Misurato: valgono 32 op su 22951.**
Senza seed 5130, coi soli seed di `op_init`+`rfkill` 5130 — zero — e coi default
5162. Quindi il 78% che non combacia **non e' stato mancante, e' codice**, e il
meccanismo resta perche' e' corretto e servira' quando i buchi si chiudono, non
perche' sia la leva. Non farlo sembrare la leva.

## Regole

- **Le misure stanno negli strumenti**, non in script usa-e-getta: vanno rifatte.
- **La doc può essere stale.** Ne ho corretta parecchia; non fidarsi, riverificare.
- I riferimenti `file:riga` vanno controllati sul tree **pristine**, non su quello
  con le patch applicate.
- **Delimitare la fase** prima di contare, con un'op che la chiuda (es. il primo
  `CHANSPEC` per l'init del radio), non a occhio su un intervallo di record.
- **`Op.ep` è l'unico modo** di sapere da che record viene un'op: `load_vendor`
  scarta bookkeeping e ombre, quindi indice ≠ numero di record.
- Ogni patch dietro un gate di revisione, verificato con `check_patch_gating.py`.
  Eccezioni dichiarate, tutte e sole per refusi di trascrizione da brcmsmac in
  codice condiviso: `b43/0010` e la mainline
  `b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7`. Un refuso non e'
  una feature di questo hardware e dietro un gate non ci va.
- Niente commenti "prima era così": quelli vanno nel messaggio di commit.
- **Provenienza in trailer**: `Link:` per ogni URL, uno per riga — e' il nome che
  il kernel conosce, non `Reference:`/`Capture:`/`Tool:`. Il sorgente del kernel si
  cita su **git.kernel.org** pinnato allo sha: `...phy_n.c?id=848acc8ffe1b#n23018`,
  o la riga scivola. La cattura ha un `Link:` al file e, **nel corpo**, l'intervallo
  di record e la prima op con la spaziatura del file, che si ritrova con `grep -F`:
  4,4 MB e 70796 righe, GitHub non la rende e un'ancora di riga non porta da nessuna
  parte. `From:` e `Signed-off-by` vanno **entrambi** su
  `alessio.ferri@mythread.it`, che e' l'indirizzo da cui le patch partono e quello
  dei sette commit gia' merged; il gmail non si usa. Corpo a 75 colonne.
- **SALAME** in grassetto sulle ipotesi non verificate sul comportamento del
  codice, **TONNO** sulle risposte infondate.

## Trappole in cui sono già caduto

0. **Usato il blob fuori dal perimetro che `PROVENANCE.md` dichiara.** Quel file
   dice da sempre che del blob servono i **simboli con le size** (per le tabelle) e
   i **prologhi degli accessor** (per sapere se il detour tiene) — perche' il
   prodotto di quell'analisi e' il tracer. Per attribuire il ciclo di misura ho
   disassemblato corpi di funzione ed elencato chiamanti, e le conclusioni sono
   finite qui dentro: giuste, ma dalla fonte sbagliata, e rifatte su `brcmsmac` che
   le aveva tutte. **Le domande sul comportamento vanno a `brcmsmac` prima**, e
   `PROVENANCE.md` si legge prima di aprire il blob, non dopo.

1. **Dichiarata una divergenza del port perche' un'op non era nella cattura.** Le
   tre op su `0x492` in testa a `switch_channel` sembravano un extra di b43, e non
   lo sono: `psm_phy_hdr_param` bit 2 e' `MAC_PHY_FORCE_CLK`, forza il clock del
   PHY per il tempo di scrivere il `BBCFG` del B-PHY che con l'N-PHY attivo puo'
   essere clock-gated, e brcmsmac fa la stessa cosa in
   `wlc_phy_chanspec_nphy_setup`. Non compare nella cattura perche' ci si arriva
   con un `bcma_write16` diretto e il tracer aggancia funzioni. La lezione e' la
   regola sulle deroghe: **prima di dire che il port fa qualcosa in piu', guardare
   se il riferimento GPL lo fa** — e se lo fa, la domanda e' se il tracer possa
   vederlo.

2. Costruito l'harness contro un tree **senza le patch** e letto i risultati come
   regressioni. Controllare `git -C ~/src/linux diff --stat` prima di credere a un
   numero. (Idea aperta: farlo fallire in `make`.)
2. Citato numeri di riga presi dal tree patchato: `phy_n.c:4021` invece di `3950`.
3. Contata una fase su una finestra a occhio che ne mescolava tre, e concluso il
   falso ("70 registri sottoinsieme dei 412" — 32 su 70 avevano valore diverso).
4. Ricostruito a mano la corrispondenza op→record: deriva fino a 230 op, e la
   seconda cal RSSI risultava al 5% invece di 0%.
5. Attribuito al "core non compilato" op che erano in codice compilato e non
   chiamato (`b43_software_rfkill` era uno stub vuoto in `wrap.c`).
6. Creduto a un'ancora di `phase_compare.py` mai trovata (`0x186 val=0x100`, che
   nella cattura non esiste): una finestra `pending` con ancora impossibile non
   falisce mai e non dice niente.
7. Scritto "serve una lettura su hardware" quando il valore era nella cattura.
8. I **bit di esecuzione** si perdono a ogni merge fatto applicando il diff
   (`git apply` senza `--index` non li mette nell'indice). Sette volte finora:
   `sh scripts/check-exec-bits.sh`.

## Difetti trovati in mainline, per ricordare cosa cercare

`patches/mainline/` sono i **cinque** indipendenti da questo hardware, da mandare per
primi e come **cinque `[PATCH]` separate in altrettanti thread**, non come serie: non
dipendono l'una dall'altra, e legarle vuol dire che una review lunga su una blocca il
merge delle altre. L'elenco con una riga a testa sta in `patches/mainline/README.md`,
che e' la fonte. Con la sola `sample-table-logic`, `sampleplay-tssi` e
`sampleplay-iqlo` fanno 322/322.


Refusi di trascrizione da brcmsmac e di precedenza C, non buchi di feature:
i due della cal PAPD sono `tbl_rf_control_override_rev7_over1` con due `val_mask`
che non coprono il campo del proprio shift, e `one_to_many` `TX_PU` con quattro
chiamate su cinque (`patches/mainline/`, dimostrati a tre voci: brcmsmac e la
cattura concordano contro b43). Poi, in ordine:
`0005` registro sbagliato, `0010` `<<` che lega più forte di `&` più un passo di
fase troncato in una `u16`, `0011` dieci campi persi con la tabella "solo 2 GHz",
`0012` tabelle inizializzate nel posto sbagliato. Vale sempre la pena confrontare
il **gate** oltre al corpo: b43 ha `phy->rev != 5` dove brcmsmac ha
`radiorev != 5` (`docs/todo-nphy.md` 3d bis).

## L'init del radio, chiuso

Il record del blob e' `{u16 address; u16 init; u8 do_init; u8 pad}`, sei byte, e **39
voci su 412 hanno il flag**. b43 aveva ereditato indirizzo e valore (412 su 412
identici) e perso la colonna. La cattura combacia col flag esattamente: 39 su 39, e i
4 registri in piu' vengono da altro codice. Lo stub da 54 che impianta il radio e' il
set `do_init` di **brcmsmac**, che e' piu' vecchio. `patches/b43/0013`, non provata su
hardware. Vedi `docs/gap-inventory.md` 4h.

## Due blob, e quale usare

`wlDSL-3580_EU.o_save` e' wl 6.30.102.7 (DSL-3580L, da cui viene la cattura),
`wlD6220.o_save` e' wl 7.14.89.14. Tutti e 33 i simboli **dati** del 2057 rev5-8 hanno
size identica fra i due, `regs_2057_rev8` e' identica byte per byte. Differiscono tre
funzioni `wlc_phy_workarounds_nphy_gainctrl_2057_rev5/6/7`, e la `rev6` e' il corpo che
manca allo stub di b43: per quella **si legge il 6.30**, che e' il blob della cattura.
Il blob da' i nomi veri di brcmsmac: `a3` = `wlc_phy_papd_cal_gctrl_nphy` (2444 byte,
147 righe, il rapporto torna). `wlc_phy_papd_cal_nphy` (6088) e' `a2` **o** `a4`: hanno
279 e 276 righe, la size non le distingue, e `a2` per size non si trova. Vedi `docs/blob-inventory.md`.

## Prossimo passo

0. **Il buco #190-254 di `switch_channel` non e' portabile, e non e' lo spurwar.**
   Per un giro questa voce diceva che era `wlc_phy_spurwar_nphy` e che b43 ne aveva
   uno stub vuoto. Sbagliato: in brcmsmac **entrambi** i flag che accendono quel
   corpo, `nphy_gband_spurwar_en` e `nphy_gband_spurwar2_en`, sono gateati
   `phy_rev < 7` (`wlc_phy_attach_nphy`), quindi su rev 8 quella funzione non fa
   niente — **esattamente come lo stub di b43**, che quindi e' corretto.

   Le op che restano fuori sono `PHY.WR 0x1df = 0x1591`, `0x1e1 = 0x1591` e una
   `TBL.RD id=0x7 off=0x106 len=2`. Quei due indirizzi (`STRA_2U`/`STRA_2L`) in b43
   esistono solo come define e **brcmsmac non li scrive mai**: e' la stessa
   categoria di `RAD.RD 0x81`, un'op del vendore senza riferimento GPL. Non si
   porta.

1. **Il ciclo di misura e' l'ACI scan.** Il nome sta in brcmsmac, che ne tiene il
   **prototipo e non il corpo**: `int wlc_phy_aci_scan_nphy(struct brcms_phy *pi);`
   in `phy/phy_int.h:1097`, dichiarata e mai definita. ACI e' *adjacent channel
   interference*, e spiega la forma che la cattura mostra: l'hop fuori canale ogni
   ~2 secondi, 100 campioni per core su `0x1c9`/`0x1ca`, e l'assenza dal primo up.

   **Non e' `poll_rssi`**: quella alterna i due registri e su rev 8 legge
   `0x219`/`0x21a` (`NREV_LT(phy_rev, 2)` sceglie l'altra coppia), mentre qui sono
   100 consecutive su un registro e 100 sull'altro. E i due indirizzi su rev 8 non
   sono i latch GPIO che dicono i nomi in `phy_n.h`: nella cattura **3400 letture e
   zero scritture**.

   Il prototipo orfano in brcmsmac e' il punto: e' una **politica** che sta sopra il
   PHY, e il posto corrispondente in b43 e' la mitigazione dell'interferenza
   (`B43_INTERFMODE_*`), che esiste **solo per il G-PHY**. Portarla vuol dire
   aggiungere l'ACI scan all'N-PHY: una feature con una politica, non una funzione
   da agganciare. `b43_nphy_rev8_chan_meas()` in `0015` e' la sua primitiva di
   misura e resta senza chiamante finche' la politica non c'e'.

2. **Il vecchio punto sul ciclo di misura.** Il vendore fa
   **100 read consecutive su `0x1c9` e 100 su `0x1ca`**, dentro lo stesso
   save/restore di otto registri (`0x8f 0xa5 0xa6 0xa7 0xe5 0xe6 0xf9 0xfb`) che
   inquadra `wlc_phy_poll_rssi_nphy`. I due indirizzi in `phy_n.h` sono
   `GPIO_LOOUT`/`HIOUT`, ma su rev 8 non sono latch di uscita: **3400 letture e
   zero scritture** in 70796 record, e il valore e' una coppia di campi da 6 bit
   con segno, uno rumore attorno a zero. `patches/b43/0015` aggiunge i nomi
   `B43_NPHY_REV8_MEAS_C1/C2` accanto ai vecchi e la funzione
   `b43_nphy_rev8_chan_meas()`.

   **Il chiamante non c'e', e le esclusioni sono misurate**, non ragionate:

   | dove | letture di `0x1c9`/`0x1ca` |
   |---|---|
   | `op_init` e `rfkill`, #1-131 | **0** |
   | il primo up intero, #132-26100 | **0** |
   | un dwell di scansione, #26103-26655 | **200** |

   Messo a fine `switch_channel` costa **74 op** nella finestra `up-ch1`, perche'
   li' il vendore non lo fa. E in brcmsmac **non esiste affatto**: ogni chiamante
   di `poll_rssi` usa `nsamps` 1 o 8, mai 100, e il suo noise sample passa dal
   power indication block in SHM, che e' la strada che `0006` ha gia' portato e
   verificato (-82..-88 dBm).

   Quindi non e' una funzione da agganciare: e' una **politica** che il driver del
   vendore ha sopra il PHY — salta fuori canale ogni ~2 secondi, misura, torna — e
   che b43 non ha, perche' la sua politica equivalente e' il link quality ogni 30
   secondi con un altro meccanismo. Agganciarla a `recalc_txpower` o inventarsi
   una phy op per un valore di cui non si sa il consumatore sarebbe peggio del
   buco. Serve la cattura di **un hop periodico con lo stato del MAC intorno**,
   fino a la' la funzione resta senza chiamante e `0015` lo dice
   nel messaggio.

1. **`b43_nphy_rev3_cal_rx_iq()`**, che e' `return -1;` per ogni N-PHY rev 3+.
   Dietro ci stanno le due regioni prima non attribuite, **7510 op** fra
   #14093 e #22246, un terzo della finestra: sono la cal RX IQ, e si riconosce
   dai sette toni da 160 word (#16319, #17130, #17542, #18588, #19399, #20210,
   #20624), dagli upload di gain su 26/27 a `off=0x40 len=84` fra un tono e
   l'altro, e dalle coppie read/write su IQLOCAL cella per cella. In piu'
   `b43_nphy_cal_rx_iq()` degrada `type` da 2 a 0 su rev >= 7, e siccome lo stub
   torna -1 non parte nemmeno `b43_nphy_save_cal()`, che nella sequenza di `0014`
   sta dietro quel controllo. **Non** sono "scritture pure verificabili per
   intero" come diceva questa voce: gli upload li decide la cal.
2. **Il cursore dei piani di lettura e' avvelenato al primo hit**, e non e' la cal
   RSSI chiamata due volte come diceva questa voce. Il cursore e' uno, globale e
   monotono: il primo `planhit` di tutta la run e' `PHY 0x7a` servito dal record
   **14999** — il vendore quel registro lo legge solo dentro la cal RX IQ, il port
   all'init — e da li' in poi tutto cio' che il vendore ha letto prima del 15000 e'
   irraggiungibile. Sulla run: **593 planhit contro 1815 planmiss**, e per esempio
   `RAD 0x16b`, che ha una sola entry al record 553, la manca. Due strade, e la
   prima e' quella che paga: **regioni contigue**, dove l'ordine delle read e' lo
   stesso per costruzione (fatto per la cal PAPD, `CONTIG` in
   `phase_compare.py`); oppure un cursore per indirizzo invece che globale. Vedi
   `test/README.md`.
3. **Quale read sfasa i piani dentro una regione.** Il cursore si puo' posizionare
   all'ingresso della regione (`B43_TEST_PLAN_FROM`), sembra la cosa giusta e
   **misurato peggiora**: `papd-cal` da 1830 a 1816 op in blocchi, primo blocco da
   847 a 843, perche' i piani servono valori dove il mirror era giusto — le quattro
   read AFE. Il knob c'e' e non e' attivo. Dietro ci sono le due `atten` del
   coupler (`0x17d`/`0x19d`, `0xaa`), che non stanno in nessuna tabella e le sa
   solo la cattura: sono l'ultimo buco di valore della cal PAPD.
4. **Il confine fra `cal PAPD` e `cal RX IQ, ingresso` in `REGIONS` e' sbagliato.**
   Sta a #14092/#14093 e taglia in mezzo la coda di `wlc_phy_txpwr_index_nphy`: le
   prime 172 op della seconda regione sono l'upload dei gain e il port le fa
   identiche. Lo 0% di quella riga e' l'assegnazione esclusiva dei blocchi della
   global run, non la verita'. La cattura coi
   RETVAL ripiegati il valore ce l'ha, quindi ogni read conta come divergenza e
   `canon_contig()` in `phase_compare.py` la riduce all'indirizzo. E' una
   riduzione che nasconde informazione vera: appena il trace porta il valore
   servito, va togliere, e i valori letti diventano verificabili dentro una
   regione.
5. **`RAD.RD 0x81` in `papd_cal_setup`, senza spiegazione.** Quattro read in 70796
   record, tutte dentro il setup, una per core per init, sempre fra le quattro
   read AFE e le quattro mod sulle stesse. Il registro (`TR2G_CONFIG1_CORE0_NU`) e'
   scritto una volta per init a #83 con `1` e mai piu', e le read tornano `1`;
   brcmsmac non lo tocca. Nel driver **non c'e'**: un read di cui non sappiamo se
   il valore serve non va in mainline. Serve una cattura che mostri se qualcosa a
   valle dipende da quella lettura.
6. Init del radio: 412 voci contro 43 del vendore, dentro il 36% dell'init.
