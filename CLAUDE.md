# CLAUDE.md

Cosa serve sapere prima di toccare qualcosa. Corto di proposito: il dettaglio sta
in `docs/INDEX.md`, qui c'è solo ciò che serve per non ripetere errori già fatti.

**Questo file dice lo stato, non come ci si è arrivati.** I numeri qui sono quelli
che gli strumenti danno oggi; le tappe intermedie stanno nei messaggi di commit e
in `patches/b43/MESSAGES.md`. Se un numero qui non torna, l'errore è qui: rifare la
misura e correggere la riga.

## Il progetto

Portare in b43 il supporto **BCM6362 / N-PHY rev 8 / radio 2057 rev 8**, guidati
da una cattura MMIO del driver proprietario `wl 6.30.102.7`. Sette patch già
merged in mainline (`docs/upstream-status.md`), dodici candidate in
`patches/mainline/`, ventisei compresse nel rollup di `patches/b43/`. **Niente ha
mai girato su hardware**: tutto è verificato riproducendo la cattura in un harness
che compila il vero `phy_n.c`.

## Setup, ogni volta

```sh
sh scripts/fetch-upstream-state.sh ~/src/linux      # sparse, ~60 MB, sha 848acc8ffe1b
cd ~/src/linux
for p in .../patches/mainline/*.patch; do git apply "$p"; done   # tutte e dodici
git apply .../patches/b43/rollup.diff                            # applica pulito
cd test && make KDIR=~/src/linux && make KDIR=~/src/linux warncheck
./phase_compare.py --vendor ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
```

`patches/mainline/` fa parte del baseline delle misure: senza quelle patch i numeri
sotto non tornano, e prima di cercare una regressione altrove si controlla che ci
siano. Il rollup vuole `mainline/` **prima** e non applica da solo, perche' non
contiene `0010` e `0022`: erano duplicati di due delle mainline. Il costo e' che
`check_patch_gating.py` da' un verdetto unico per tutto il rollup invece di uno per
patch; i tre punti non gateati e le loro dichiarazioni sono in testa a
`rollup.diff`.

`patches/b43/` e' **un file solo** finche' si costruisce: la serie si ridivide prima
di mandare qualunque cosa, e i messaggi delle ventisei patch stanno in
`patches/b43/MESSAGES.md`. Le citazioni per numero nei documenti e in
`phase_compare.py` risolvono contro quel file.

La catena di dipendenze dentro la serie serve alla **ri-divisione**, non al build:
misurata con `git apply` sull'albero pulito, 0004 dipende da **0002** (contesto in
`tables_nphy.c`), 0009 da 0004, 0012 da **0009**. 0003 non serve a nessuna delle
tre.

## Strumenti

| cosa | dove |
|---|---|
| harness, flow `init initpor initcal full chanset rfkill txpower` | `test/nphy_trace` |
| confronto per fase, 18 finestre | `test/phase_compare.py` |
| confronto globale + per regione | `test/phase_compare.py --global-run DA A --flow F` |
| copertura per insiemi di celle | `test/coverage.py` |
| storia di una cella di tabella | `reverse-tools/trace_tables.py --cell ID:OFF` |
| segmentazione su un marcatore | `reverse-tools/segment_marker.py` |
| normalizzazione, `Op` con `.ep` | `test/compare.py` |
| **seed**: lo stato che `op_init` e `rfkill` lasciano | `reverse-tools/gen_seed.py` → `test/seed_up.h` |
| accessi SHM, clock PHY, macfreq, confini MAC (catture nuove) | hook `wlc_bmac_*` in `wl-diag/wl_diag.c` |
| buchi di dispatch, xref brcmsmac, gating delle patch | `reverse-tools/*.py` |

## Stato

`18 finestre: 0 da guardare, 7 divergenze note`. Nessuna finestra e' aperta.

**Il verdetto e' la tabella per fase di `phase_compare.py`: 8756 op su 18808, il
47%.** Non il totale in blocchi contigui, che dice 21090 su 22943 (92%) e che **non
e' una misura**: su `up-ch1` la gran parte dei blocchi sta sotto le 16 op. Sommare
frammenti da due op e chiamarla copertura e' contare il sommerso nel PIL.

Un blocco conta se corrisponde a una **fase**: una voce di `phy_ops` dove esiste,
oppure — eccezione dichiarata finche' il port non le espone — una macro operazione
delimitata da un marcatore citato. Il numero per fase e' **uno**, la run contigua
piu' lunga dentro la fase, quindi nessun frammento lo muove.

| fase | op | run | blocchi |
|---|---|---|---|
| `gain-table` | 1540 | **1540 100%** | `1540` |
| `coeff-setup` | 1037 | **1037 100%** | `1037` |
| `coeff-setup-2` | 1073 | **1062 99%** | `1062` |
| `recalc-txpower` (**phy_ops vera**) | 716 | **604 84%** | `604` |
| `pwr-setup` | 432 | **432 100%** | `432` |
| `idle-tssi` | 660 | 334 51% | `334 210 73 22` |
| `coda-idle-tssi` | 1139 | 432 38% | `432 334 161 73` |
| `cal-papd` | 2662 | 847 32% | `847 2x344 316 274` |
| `cal-tx-iqlo` | 1570 | 443 28% | `443 333 268 110` |
| `cal-rssi-2` | 960 | **940 98%** | `940 18` |
| `perical-ingresso` | 1402 | 575 41% | `575 409 401` |
| `cal-rx-iq` | 5617 | 510 9% | `2x510 4x507 2x362 321` |

**La run sbaglia in un verso, e la colonna blocchi c'e' per questo**: prende il
massimo, quindi una fase che ripete N volte la stessa sequenza non puo' superare
~1/N per costruzione, quanto bene la riproduca. E sono tutte le cal. `cal-rx-iq` e'
il caso limite: la run dice **7%** e la forma dice **`6x420`**, cioe' le sei
iterazioni dello sweep appaiate una per una; misurata da sola con il pavimento dei
piani al suo ingresso fa **5418 su 5617, il 96%**, e la sotto-regione dello sweep
**4676 su 4735, il 99%**. Quella fase non e' un buco. Cio' che le resta fuori sono
~140 op nell'**ingresso**.

Attenzione: una regione misurata da sola non e' un'altra vista dello stesso run, e'
un run **diverso** — `--global-run` riposiziona il pavimento dei piani al suo
ingresso. `cal-rx-iq` da sola fa 96% contro il 7% della run; `coeff-setup-2` da sola
fa **330 (30%)** contro 1062 (99%) nel run globale. Nessuno dei due e' sbagliato e
non sono confrontabili.

Il totale della global run **non si guarda**: l'assegnazione dei blocchi e'
esclusiva e golosa, quindi un blocco lungo altrove si porta via le op e il numero
oscilla su cambiamenti che migliorano soltanto. Il numero da guardare e' `up-ch1`.

Per regione, flow `init`, `--global-run 132 26100`:

| regione | record | op | appaiate | non conf. | su confrontabili |
|---|---|---|---|---|---|
| init vero e proprio | #132-10961 | 9692 | 4868 50% | **1180** | **57%** |
| cal PAPD (`a4`) | #10962-14092 | 2662 | 1933 73% | 0 | 73% |
| cal RX IQ, ingresso | #14093-15920 | 1698 | 1513 89% | 3 | 89% |
| cal RX IQ, sweep di gain | #15921-22246 | 5812 | 4921 85% | 0 | 85% |
| seconda cal RSSI | #22247-23771 | 960 | **958 100%** | 0 | **100%** |
| coda | #23772-26100 | 2127 | 949 45% | **176** | **49%** |

`non conf.` sono famiglie che il port non ha modo di emettere, perche' l'harness
compila il PHY e non il core — `OBJ.*` (1286 nella finestra), `MAC.MCTRL`/`MHF`
(40), `TPL.RAMW` (19), `GPIO.OUT` (12) — e la object memory ha comunque
l'encoding non confrontabile di `o708`/`o70e`. Nelle quattro regioni di calibrazione sono **zero**: tutte e 1356
stanno nell'init e nella coda, dove il core lavora. Il totale in blocchi contigui
non le esclude, di proposito.

**L'init vero e proprio resta il buco piu' grosso**: 3643 op confrontabili non
appaiate su 8511. Il buco singolo piu' grande della finestra sta li', **3099 op dopo
#2172**, e un terzo e' object memory; le confrontabili sono ~2155, quasi tutte
scritture delle tabelle 26/27 (128, 84 e 64 celle) che il port **fa**, in un punto
diverso della sequenza. Prima di cercare codice mancante li', guardare l'**ordine**.

## Come sta insieme la cal periodica

`wlc_phy_cal_perical_nphy_run()` e' chiamata una volta per fase, e ognuna fa la
stessa parentesi: legge il tx gain da `7/0x110`, salva `nphy_txpwrctrl` e lo
**spegne**, esegue la sua fase, e in coda ripristina — ed e' quel ripristino a
scrivere `adj_pwr_tbl`, 84 celle per catena. Ricostruita in
`b43_nphy_cal_perical_phyinit()`, con questi confini, tutti dalla cattura:

- **la parentesi si chiude una volta, alla fine.** Audit di ogni confine fra i
  passi, col test sul payload (84 zeri = spegnimento, contenuto = accensione): fra
  perical e TX I/Q LO nessuna transizione, fra TX I/Q LO e PAPD un solo
  spegnimento, fra PAPD e RX IQ quattro spegnimenti, fra RX IQ e idle TSSI nessuna.
  **Non c'e' una sola accensione fra le fasi**: il controllo resta spento per tutta
  la sequenza.
- **le sei fasi TX sono UN passo.** La cattura emette i dodici comandi di fila con
  una sola lettura del gain, e il vendore ha una parentesi per tutto il blocco TX,
  non sei.
- **RX IQ e RSSI sono un passo solo.** Fra la rilettura dei coefficienti di
  `save_cal` (#21169, `15/0x50 len 8`) e quella che apre `coef_setup` (#21187, len
  7) ci sono diciotto op e nient'altro: in due passi fra i due passerebbero due
  riprogrammazioni da 84 celle.
- **la restituzione dell'indice sta fra la PAPD e la RX IQ**, e va fatta con
  indice `-1`: la cattura ha la' due chiamate a `txpwr_index`, una per core, ognuna
  col suo salva e riapplica (#14101/#14305 core 0, #14524/#14728 core 1).
- **la restituzione differita non ripristina le compensazioni** (`restore_cals`
  falso): nella cattura fra la write del bbmult e la riprogrammazione della tabella
  di potenza non ci sono write a `15/0x50`, `15/0x55` e `15/0x5d`, e i quattro siti
  di brcmsmac che chiamano con l'indice salvato passano tutti `false`.
- **il bbmult si rimette in DUE celle**, 87 e 95: la cattura fa la read-modify-write
  su `15/0x57` (#8096) e poi la stessa su `15/0x5f` (#8103), come fa il ramo che
  forza l'indice. Il riferimento tocca solo la 87.
- **l'indice per catena si legge dall'hardware all'ingresso**, dai bit 8..14 di
  `C1_TXPCTL_STAT` e `C2_TXPCTL_STAT`, non da `index_internal`, e **non e' uno**:
  quello che la coda riforza e' 10 sul core 0 e 12 sul core 1. Quale delle cinque
  coppie di letture lo produca, e perche' non e' la coppia che il riferimento usa,
  sta nella sezione dedicata piu' sotto.
- **la coda della sequenza riforza quei due indici**, una chiamata per core, prima
  della chiusura unica: la cattura legge `26/0xca` a #25017 e `27/0xcc` a #25418, e
  fra le due chiamate il controllo di potenza resta spento — i quattro payload da 84
  zeri di #24841, #25064, #25242, #25465 — con l'unica accensione dopo, a #25641, che
  e' la chiusura. Vale **+762 op contigue**, il guadagno piu' grosso della serie, a
  run invariate. Il port ci arriva coi numeri giusti ma per la ragione sbagliata:
  vedi la sezione sulle cinque coppie.
- **il test della restituzione e' sullo stato d'ingresso della sequenza**, non del
  passo: con la chiusura unica alla fine lo stato per passo e' falso dopo la prima
  apertura.
- **`precal_txgain` due volte non e' un doppione**: la cattura ne ha due, una nel
  blocco differito e una al passo INIT.
- **la sequenza gira dopo `recalc_txpower`**, non in coda a `b43_phy_initn()`: il
  vendore fa init, recalc (#5726-6500), poi la cal (#7034 in avanti). Il punto di
  chiamata e' la coda di `b43_nphy_op_recalc_txpower()`, dietro
  `nphy->perical_pending`, che e' il solo posto fra i due in cui l'harness passa;
  nel riferimento la fa partire il watchdog, che qui non c'e'. mac80211 chiama
  `recalc_txpower` dopo l'init **sempre**, quindi un flow che non lo faccia e' il
  banco a essere infedele.

`nphy->cal_orig_pwr_idx[]` e' impostata in **un posto solo**, dentro
`if (nphy->perical != 2)`. Questo hardware ha `perical == 2` — che e' la ragione per
cui esiste la macchina a stati — quindi la' non passa e quell'array resta a zero: va
preso al passo INIT.

**Il senso del precal e' diverso da come suona**: l'indice forzato serve solo a
*leggere* dei gain, non a restare programmato. Il vendore lo forza, legge, e
restituisce subito radio gain, dac gain, bbmult e le compensazioni; le cal girano
sull'hardware di prima, coi gain letti all'indice forzato. **L'indice e' 10, e non
e' quello che il riferimento sceglierebbe**: brcmsmac tiene 10 per radio 2057 rev 3,
4 e 6 e 0 per tutto il resto, quindi il rev 8 finirebbe su 0, ma la cattura legge
`off=0xca`, cioe' `192 + 10`. Il raggruppamento di brcmsmac e' piu' vecchio di questo
radio, esattamente come quello dell'rccal (`gap-inventory.md` voce 5), e decide la
cattura.

Il parametro full/parziale non e' una costante: `fullcal = (canale != canale
dell'ultima cal TX IQ/LO)`, lo stesso test che `b43_nphy_restore_cal()` fa gia'
prima di riusare i coefficienti. Su questa cattura **non sposta op**, perche'
entrambi gli init sono di un'interfaccia che sale su un canale non calibrato: cambia
dalla seconda volta in poi, che nessuna cattura copre. Il tipo della cal RX IQ resta
**2** e non e' una dimenticanza: brcmsmac chiede 2 alla prima cal dopo
un'associazione e 0 dopo, b43 non traccia niente di equivalente, e fra le due
costanti 2 e' la conservativa perche' 0 salta quasi tutto.

Attenzione a cosa **non** e' il discriminante, perche' e' la strada che sembra
giusta: il `full_cal` di `wlc_phy_a4(pi, bool full_cal)` e' dichiarato e mai usato
nel corpo, e i tre chiamanti passano tutti `true`; e `pi->nphy_papd_cal_type`, che
sceglie fra `CAL_FULL` e `CAL_SOFT` per l'epsilon, non viene mai scritto in tutto
`phy_n.c`. Metterli in b43 sarebbe trascrivere peso morto.

Le tre parti dello stato di cal — `rssical_chanspec`, `iqcal_chanspec`,
`txiqlocal_chanspec` — vanno azzerate **insieme** fra i due init dell'harness, non
due su tre, o il secondo init prende la strada parziale.

## La cal RSSI narrowband

La ricerca del VCM e' aritmetica pura, e mainline ne sbaglia due pezzi. La distanza
da minimizzare e' `I² + Q²` e il secondo termine era `Q * I`, che non e' una distanza
ed e' negativo ogni volta che le rail hanno segno opposto. E il ramo rev 7+ che
programma il vincitore passava `vcm`, che all'uscita del ciclo vale 8 su un campo di
tre bit: scriveva un bit fuori campo e buttava la ricerca. Le due stanno in
`patches/mainline/`, sono provabili contro brcmsmac senza hardware e valgono anche
per il rev 3.

Con le due, la seconda cal RSSI misurata da sola fa **956 su 960, il 100%**, in 3
blocchi, con una run singola da 940. Era 623 in 22 blocchi.

La fase nella tabella per fase resta a 99 su 960, e **non e' una contraddizione**: i
blocchi di poll di questa fase sono identici a quelli dello sweep della cal RX IQ, e
l'assegnazione golosa li assegna a quella. E' il caso da citare quando un numero per fase
non si muove dopo un fix giusto.

La stessa regione ha fatto trovare il difetto del campo dell'indice: la cattura
legge `0x1ed`/`0x1ee` a #7034 e #7036 e rende `0x1900`, quindi l'indice e' 25 e i
sette bit bassi sono zero. Il port ne scriveva 0 dove il vendore scrive 25.

Serve anche la lettura di `GPIO_SEL` fuori dal gate della scrittura (vedi la testa di
`rollup.diff`): senza, la regione si spezza in 22 blocchi invece di 3. E' inerte
sull'hardware e non e' un candidato mainline.

## Le cinque coppie di TXPCTL_STAT all'ingresso, attribuite

`wlc_phy_cal_perical_nphy_run` in testa fa, in quest'ordine:

    if (phase_id == IDLE || phase_id == INIT) {
            nphy_cal_orig_pwr_idx[0..1] = (read_phy_reg(0x1ed/0x1ee) >> 8) & 0x7f;
            if (nphy_txpwrctrl != PHY_TPC_HW_OFF)
                    table_read(RFSEQ, 2, 0x110, ..., nphy_cal_orig_tx_gain);
    }
    target_gain = wlc_phy_get_tx_gain_nphy(pi);
    tx_pwr_ctrl_state = pi->nphy_txpwrctrl;
    wlc_phy_txpwrctrl_enable_nphy(pi, PHY_TPC_HW_OFF);

Nella cattura ci sono **dieci letture** di `0x1ed`/`0x1ee` in tutta `up-ch1`, cinque
coppie, e si mappano una per una:

| record | valori | chi la fa |
|---|---|---|
| #7034/#7036 | **25, 25** | `nphy_cal_orig_pwr_idx`, ramo IDLE/INIT, prima del gain |
| #7038 | — | `nphy_cal_orig_tx_gain`, gateato su controllo acceso |
| #7044/#7046 | **10, 12** | `wlc_phy_get_tx_gain_nphy()`, ramo a controllo acceso |
| #7050/#7052 | 10, 12 | dentro `txpwrctrl_enable(OFF)`: e' `nphy_txpwr_idx` |
| #10784/#10786 | 10, 12 | idem, nella regione PAPD |
| #26073/#26075 | 10, 12 | idem, in coda |

**Il riferimento non descrive quello che la cattura fa in coda.** Il ramo
`restore_tx_gain`, che la macchina a stati accende nella fase RSSICAL, riforza
`nphy_cal_orig_pwr_idx`, cioe' **25 e 25**, che con `192 + indice` vorrebbe dire
leggere `26/0xd9`. La cattura legge `26/0xca` e `27/0xcc`, cioe' **10 e 12**: gli
indici che le due catene avevano *dopo* la lettura del gain, non prima. E' lo stesso
schema dell'indice di precal e del raggruppamento dell'rccal — brcmsmac e' piu'
vecchio di questo radio — e decide la cattura.

**Sistemato, e in due mosse.** Prima l'ordine: `target` si prende **prima** del
precal, come il riferimento, non dopo. Poi la variabile: l'indice che la coda
riforza lo registra `b43_nphy_get_tx_gains()`, nel suo ramo a controllo acceso, che
e' la lettura di #7044/#7046 — cioe' la coda rimette 10 e 12, per costruzione e non
per un accidente del piano di lettura.

Le due strade sbagliate, provate e misurate, perche' sembrano entrambe quella
giusta:

- usare `tx_pwr_idx[]`, che sulla carta e' la coppia che vale 10 e 12: la coda passa
  a `26/0xd9` e non combacia. Nel port quel campo finisce a 25/25, al contrario del
  vendore, perche' le tre `tx_power_ctrl(false)` del blocco differito consumavano le
  voci del piano prima della sequenza.
- leggere la coppia in testa alla sequenza come fa il riferimento: da' 25 e 25, che
  e' il valore giusto per `nphy_cal_orig_pwr_idx` e quello sbagliato per la coda.

Restano fuori le due op di #7034/#7036: nel riferimento riempiono
`nphy_cal_orig_pwr_idx`, che qui la coda non usa, quindi portarle vorrebbe dire
aggiungere un campo che nessuno legge. Costano due op e stanno dichiarate qui.

Misurato: blocchi contigui 19247 -> **19254**, a freddo 18167 -> **18169**,
divergenze di `perical-ingresso` 905 -> **885**. Poi sono arrivate le due sotto.

## Due cose che valgono quanto un difetto, e non lo sono

Le due correzioni che hanno mosso di piu' i numeri non aggiungono codice: mettono in
ordine quello che c'era.

**Il blocco differito deve girare dentro la parentesi.** Il riferimento spegne il
controllo di potenza in testa alla run, prima che qualcosa forzi un indice. Il port
lo spegneva solo entrando nel primo passo, quindi il precal e i due hand-back
restituivano il controllo **acceso** e ognuno riprogrammava le 84 celle. Da qui, sei
o sette blocchi da 80-110 op in cui il vendore scrive zeri e il port scrive
contenuto. La sequenza ora riceve lo stato d'ingresso come argomento invece di
rileggerlo dopo che il blocco differito lo ha girato. Divergenze di
`perical-ingresso` **885 -> 323**, op mancanti **675 -> 42**.

**Il ramo di spegnimento apriva la porta dati a mano.** `b43_nphy_tx_power_ctrl()`
scriveva 84 celle in un ciclo su `B43_NPHY_TABLE_DATALO` dove il ramo di accensione,
dieci righe sotto, usa `b43_ntab_write_bulk()` sulle stesse due tabelle allo stesso
offset. Stesse celle, strada diversa — ma il tracer del vendore aggancia la funzione
di tabella, quindi la sua op c'e' e quella del port no, e **quell'unica op mancante
sfasava di uno tutto cio' che seguiva**. Si vedeva nella mappa dei segmenti: i
blocchi uguali si accorciavano di uno a ogni scrittura da 84 celle — 77, 76, 75, 74,
73, 72... Totale per fase **7206 -> 7578**, `cal-rx-iq` da 420 a 510,
`rxiq-ingresso` da 306 a 401, `txpwr-index` da 6 divergenze note a 4.

Il freddo perde 39 op (18750 -> 18711) e nessuna finestra si e' rotta:
l'assegnazione dei blocchi e' esclusiva e golosa.

**Le due letture d'ingresso del riferimento erano proprio le sei op che mancavano.**
`nphy_cal_orig_pwr_idx` (la coppia, 2 op) e `nphy_cal_orig_tx_gain` (la table-read su
`7/0x110`, 4 op) le fa il riferimento in testa alla run e poi non le rilegge — la
coda rimette l'indice preso *con* i gain, non questo. Sembravano quindi due op morte
da non portare, e non lo erano: senza di loro tutto il resto della fase stava sei op
in anticipo, ed erano quei sei che facevano scattare le famiglie di sopra a ogni
scrittura da 84 celle. Portate, coi nomi del riferimento e con lo stesso nulla che le
legge; l'indice che la coda usa sta in `pwr_idx_at_gain[]`, scritto da
`b43_nphy_get_tx_gains()`. Divergenze di `perical-ingresso` **286 -> 95**.

Regola che ne viene: **un'op del vendore il cui valore non serve a nessuno non e' per
questo un'op da non portare.** Se l'hardware la vede, la sequenza la contiene, e
tutto quello che segue si misura da lei.

**Le due op che chiudono `perical-ingresso` erano un difetto di mainline e un
ordine.** `nphy->txcal_bbmult` in mainline e' **letto e mai scritto**: lo legge
`b43_nphy_update_tx_cal_ladder()`, che ci scala i 36 gradini della scala che la cal
TX I/Q LO usa, e senza scrittore vale zero — ogni gradino esce ad ampiezza zero, su
ogni N-PHY rev 3 e su. Il riferimento lo riempie in coda a
`wlc_phy_precal_txgain_nphy()` quando `save_bbmult`, che sul rev 7 e su e' sempre, e
di nuovo in coda a `wlc_phy_cal_txgainctrl_nphy()`. Nella cattura e' la `TBL.RD
15/0x57` a #8076, subito dopo il forzamento. **Candidato mainline**, appena si e'
misurato cosa cambia sulla cal.

E i gain al forzamento si prendono fra il forzamento e la restituzione (#8080), non
dentro il passo INIT della macchina a stati: il riferimento fa
`cal_target_gain = get_tx_gain()` subito dopo `precal_txgain()`, nello stesso passo.
Divergenze **95 -> 19**, run **409 -> 573**, totale per fase **7586 -> 7750**.

**E la parentesi per passo non va su tutti i passi.** Con il controllo di potenza
gia' spento da prima del blocco differito, `b43_nphy_pwr_ctl_open()` dentro il ciclo
non spegne niente e la lettura del gain la salta: restano 172 op per passo che
l'hardware non vede. Il port ne emetteva **48** di scritture da 84 celle contro le
**36** del vendore, e le dodici in piu' erano queste.

Quale tenere lo dice **l'audit dei confini**, non un'intuizione: fra perical e TX I/Q
LO nessuna transizione, fra TX I/Q LO e PAPD **una**, fra PAPD e RX IQ quattro — che
sono le due per core che la cal PAPD apre da se' — fra RX IQ e idle TSSI nessuna.
Quindi resta la sola apertura in testa al passo PAPDCAL. Togliendole tutte e sei si
guadagnava sull'ingresso della RX IQ e si perdevano **172 op contigue** altrove:
misurato, non dedotto, ed e' il motivo per cui la risposta non era ne' "sempre" ne'
"mai". `rxiq-ingresso` run **401 -> 500**, divergenze **722 -> 542**, op mancanti
**184 -> 19**.

**E il gain di calibrazione della RX IQ era sbagliato per due ragioni sovrapposte.**
La cattura scrive `0x4077` su entrambe le catene, che e' il `cal_gain` della voce 10
di `b43_ntab_tx_gain_ipa_2057_rev8_2g` (`0x4077002e`: ipa 7, pad 14, pga 0, txgm 4) —
l'indice che il precal forza su entrambe. Il port scriveva `0x4027`, cioe' pad 4, che
e' quello che si ottiene interpretando il contenuto corrente di `7/0x110`.

La formula di `b43_nphy_iq_cal_gain_params()` e' identica al riferimento, quindi il
difetto era nei gain che le arrivano, e sono due:

1. **`b43_nphy_cal_perical_phyinit()` sovrascriveva il parametro** che aveva appena
   ricevuto: rileggeva i gain in testa alla propria funzione, col controllo di potenza
   gia' spento, quindi `b43_nphy_get_tx_gains()` prendeva il ramo che legge `7/0x110`
   invece di quello che indicizza la tabella. Il chiamante passava pad 14,12 e la
   funzione usava pad 4,4. Trovato con una stampa temporanea dopo che tre letture del
   codice non l'avevano visto: **quando due valori plausibili si contendono un
   risultato, si stampa.**
2. **la cal RX IQ vuole i gain all'indice forzato**, non quelli d'ingresso. Coi gain
   d'ingresso, che hanno gli indici per catena 10 e 12, escono `0x4077` e `0x4067`;
   con quelli al forzamento, 10 su entrambe, escono `0x4077` e `0x4077`.

**La carrier search e' a contatore, e il hold esterno mancava.** `wlc_phy_a4()` la
tiene aperta dalla riga 25133 alla 25380, cioe' per tutta la cal PAPD;
`b43_nphy_papd_cal()` no. Il hold e' refcountato su `deaf_count`, quindi senza quello
esterno le parentesi dei passi interni escono come coppie ingresso-uscita per conto
loro: il port emetteva **8** coppie contro le **6** del vendore, e le due in piu'
erano corte, 27 e 34 op, cioe' proprio inner che il vendore ha gratis. Il modo di
vederlo e' contare le posizioni di `PHY.WR 0x2c = 0xffff` (ingresso) e `= 0x404e`
(uscita) sui due lati e guardare la lunghezza delle coppie, non solo quante sono.

**E la cattura lo conferma, che e' la sola verifica che conta qui.** Le sei coppie
del vendore, per record, sono:

| ingresso | uscita | op | cosa copre |
|---|---|---|---|
| #1620 | #1666 | 34 | init |
| #8492 | #10756 | 1601 | cal TX I/Q LO |
| **#10771** | **#14946** | **3658** | **cal PAPD**, #10962-14092 |
| #14964 | #21143 | 5615 | ingresso e sweep della RX IQ |
| #22245 | #23900 | 1052 | coeff setup e cal RSSI |
| #24271 | #24317 | 34 | idle TSSI |

La terza copre la cal PAPD per intero ed esce a #14946, che e' esattamente l'uscita
che avevo visto nel gruppo da 25 op. E la forma delle coppie del port si avvicina:

    vendore          34 1601 3658      5615 1052 34
    port, con hold   34 1052 1617 5112 5702 1052 34
    port, senza      34 1052 1617 27 34 5702 1052 34

Da otto coppie a sette, e le due corte (27 e 34) spariscono nella lunga.

Attenzione a come si legge quel 5112 contro 3658: **non e' un hold fuori posto.**
Guardate le due estremita' e combaciano op per op — all'uscita, sui due lati, `PHY.WR
0x73=0x0`, `MOD 0x1e7 mask=0xe000`, `MOD 0x8f`, `MOD 0xa5`, `RD 0xb0`, `MOD 0xb0=0x7`,
`WR 0x2c=0x404e`, `WR 0x42=0x404e`. La lunghezza differisce perche' il port emette
1454 op **dentro** la cal PAPD che il vendore non emette, cosa che si sapeva gia'
(`cal-papd` fa 847 su 2662 e `a3`/`a2` non ci sono). Contare la lunghezza di un hold
non misura il hold, misura cio' che ci sta dentro.

Quel che resta di misurabile sui confini sono due numeri: il port ha **una coppia in
piu'**, 7 contro 6, e **9 letture di `0xb0` in piu'**, 25 contro 16. I valori scritti
combaciano — 18 volte `0x7` e 7 volte `0x4` contro 16 e 6 — quindi e' un conteggio di
chiamate a `b43_nphy_classifier()`, non un valore sbagliato. Sono ~20 op ed e' la voce
piu' piccola aperta.

Nota metodologica, e la avevo sbagliata: la prima versione di questa voce diceva
"la run e' un proxy, il sorgente GPL non lo e'". **No.** brcmsmac e' molto piu' vecchio
del driver da cui viene la cattura, e in questo lavoro lo ha dimostrato tre volte
(l'indice di precal, il raggruppamento dell'rccal, l'indice che la coda riforza). La
cattura decide, sempre. Qui la cattura e brcmsmac concordano, ma la verifica era
disponibile e andava fatta prima — non dopo, e non perche' qualcuno l'ha fatto
notare.

**E un'op sola valeva quattrocentosessantasei divergenze.** Il blocco di salvataggio
della cal RX IQ salva un registro in piu' del port: `0x2ff`, letto a `#15015` subito
dopo i quattro registri di override rev 7 e prima di `0x297` e `0x29b`. brcmsmac non
lo legge **mai** — tocca solo i bit 0, 13, 14 e 15 di quell'indirizzo nel percorso di
override rev 7 — quindi qui decide la cattura, come per l'indice di precal e il
raggruppamento dell'rccal. Salvato e non ripristinato, che e' quello che la cattura
fa: la lettura c'e', una write in questa fase no.

Il perche' vale 466 divergenze e' la lezione: la lettura mancante sfasava di **uno**
tutto quello che seguiva, e dopo non si riallineava mai, perche' da li' in poi sono
corse lunghe di zeri identici e di contenuto identico della tabella dei campioni. I
gruppi da 357, 46, 21, 16, 5 e le quattro coppie da 2 erano tutti quello. `rxiq-
ingresso` da **530 a 64** divergenze.

Il modo di trovarla, che e' la parte da riusare: quando i gruppi di divergenza sono
molti e le corse uguali fra loro sono tutte della stessa lunghezza, **non sono molti
difetti, e' un offset**. Si localizza cercando il punto da cui `port[i+1] ==
vendor[i]` regge per una decina di op, e poi si fa la **differenza per multiinsieme**
sulla span attorno: quello che resta da un lato solo, escluse le famiglie in deroga,
e' l'op che manca. Qui era una riga.

**E la pulizia della cal PAPD va dentro la seconda parentesi, prima che si chiuda.**
Il port faceva `run_one`, `pwr_ctl_close`, `cleanup`; la cattura ferma il tono,
rimette il moltiplicatore e il coupler, cammina la lista degli override a
#13749-#13918, e **solo dopo** riprogramma la tabella di potenza aggiustata.

Trovato col confronto posizionale: allineando dopo la coda del passo 2, il vendore fa
`PHY.RD 0xc7` — `stop_playback` — dove il port faceva `PHY.RD 0x1e7` e le 84 celle.

**Due righe scambiate**: blocchi contigui 20982 -> **21074 (92%)**, a freddo 18983 ->
**19333 (70%)**, buco portabile 616 -> **524**. E' il rapporto migliore fra righe
toccate e op recuperate di tutta la serie, meglio delle due corse della scala TX I/Q
LO — e il buco da 163 op che inseguivo da tre giri non era un buco di contenuto, era
questo.

Metodo, che e' la parte riusabile: la **mappa dei segmenti** posizionali di una
finestra ancorata — quanto lunga la corsa uguale, quanto lunga la diversa, e la prima
op di ciascuna — riduce 885 divergenze a tre famiglie in una schermata. Contare le
divergenze non dice niente; guardare come si distribuiscono dice tutto.

## Il tetto non e' il 100%, ed e' il 94%

Le due metriche misurano cose diverse e conviene dirlo con i numeri. **La somma dei
blocchi** su `up-ch1` fa 21090 su 22951; **la somma delle run** fa 8756 su 18808.

Il 46% delle run **non puo'** arrivare al 100% per costruzione: la run e' il *massimo*
blocco dentro la fase, quindi una fase che ripete N volte la stessa sequenza si ferma
a ~1/N. `cal-rx-iq` ne e' la dimostrazione: run 510 su 5617 (9%), forma `2x510
4x507`, cioe' tutte e sei le iterazioni appaiate a ~510 ciascuna, e misurata da sola
fa il 96%. Quel numero e' un rivelatore di regressioni, non un obiettivo.

Il **89% dei blocchi** ha un tetto vero, e si calcola. Le 2549 op non appaiate, per
famiglia:

| famiglia | op | portabile? |
|---|---|---|
| `OBJ.WR` + `OBJ.RD` | 1285 | **no**: 734 indirizzi distinti di object memory, 553 sopra 0x400. E' lo stato di MAC e ucode, e l'harness compila il PHY non il core |
| `PHY.WR`/`RD`/`MOD` | 1008 | **si** |
| `TBL.WR`/`RD` | 135 | **si** |
| `RAD.*` | 50 | **si** |
| `TPL.RAMW`, `MAC.MHF`, `MAC.MCTRL`, `GPIO.OUT`, `CHANSPEC` | 71 | **no**, stessa ragione |

Quindi il raggiungibile e' **22951 - 1356 = 21595, il 94%**, e siamo a 21090: restano
**508 op portabili**, e il tetto misurato e' 21598, il 94,1%: siamo al **97,6% del
tetto**. E stanno quasi tutte in un posto: **888 nell'init** (#132-10961),
209 nella cal PAPD, 44 nella coda, 41 nello sweep RX IQ, 9 nell'ingresso RX IQ, 2
nella seconda cal RSSI.

Dei buchi contigui, i due piu' grandi (601 op a #4970 e 497 a #6442) sono quasi tutti
object memory: 44 e 0 op portabili. Restano, in ordine di dimensione:

**La cal PAPD pulsa il reset della valutazione di canale libero.** Subito dopo il hold
della carrier search e molto prima delle tabelle, la cattura a #10773-#10776 legge
BBCFG, lo riscrive col bit `RSTCCA` a uno e poi con `RSTCCA` e `RSTRX` a zero. Il port
aveva solo la write che salva e azzera il reset RX — che la cattura ha anch'essa, ma
**dentro** la finestra `papd-tables`, come `PHY.MOD mask=0x8000`. Sono due scritture
distinte in due punti distinti e il port ne aveva una: una singola write del valore
azzerato lascia lo stesso valore dietro e **non resetta mai la valutazione**.

Il posto conta e l'ho sbagliato due volte: al posto della write esistente, o prima
delle tabelle scalari, la run per fase perde **262 op** e `papd-tables` passa da `ok`
a `noto`, perche' il confronto la' e' posizionale. Dopo il hold e prima delle tabelle
torna tutto pieno.

**La cal TX I/Q LO rimette i registri radio che si prende.**
`b43_nphy_tx_cal_radio_setup_rev7()` salva nove celle per core — `TX_SSI_MASTER`,
`IQCAL_VCM_HG`, `IQCAL_IDAC`, `TSSI_VCM`, `TX_SSI_MUX`, `TSSIA`, `TSSIG`,
`TSSI_MISC1` — le riscrive coi valori della calibrazione, e **niente le rimetteva**:
restavano sporche per tutto il tempo che l'interfaccia stava su. Sedici registri del
radio. La cattura le ripristina in ordine di indirizzo a #10737-#10752, subito dopo
che i gain tornano al loro posto. **+16** e **+16**, esattamente il numero delle
write.

Restano 14 dei sedici con conteggi diversi (vendore 9-14 contro port 5-10): quelle
differenze sono altrove, non nel ripristino.

**80 op a #796** — le otto maskset su `AFECTL_C1/C2` piu' quel che segue, e la
posizione dipende dall'ordine fra aux ADC e sequenze RF che non e' capito.

**La coda di abilitazione della PAPD e' portata.** A #13842-#13854 il vendore rimette
gli offset epsilon e accende il motore, con le riletture di stato in mezzo: adjust
core 0, letture di `0x2bf` e `0x2c0`, adjust core 1, letture di `0x2b1` e `0x2b2`,
poi il bit 0 di `PAPD_EN0` e `PAPD_EN1`. Servono quattro nomi nuovi in `phy_n.h` per
le celle di stato, che b43 non aveva. Contando registro per registro, ora **tutti e
dieci** quelli del motore combaciano: `0x297`, `0x298`, `0x29b`, `0x29c`, `0x2a3`,
`0x2a4`, `0x2b1`, `0x2b2`, `0x2bf`, `0x2c0`. Numeri fermi, e sta dentro perche' quel
bit **accende il motore**: una cal PAPD che non lo accende non serve a niente.

**55 op a #884 e 20 a #5614** — sono una coppia: il vendore **rilegge** il gruppo che
`gain_ctl_workarounds` scrive (`0x20`, `0x2a7`, `0x21`, `0x2a8`, `7/0x106`, `0x280`,
`0x283`) e piu' tardi lo **riscrive** con gli stessi valori. brcmsmac non ha nessun
salva/ripristina di quel gruppo. Nessun rischio di stato: il ripristino riscrive
quello che c'e' gia'.

**32 op a #203** — le `0x1df`/`0x1e1`, cioe' `STRA_2U`/`STRA_2L`, gia' dichiarate non
portabili: b43 le ha solo come define e brcmsmac non le scrive mai. Vanno sottratte
dal tetto.

**174 op in 81 frammenti sotto le 10 op** — questi non si chiudono a mano: frammenti
da 2-9 op sono dove il tracer del vendore ha i suoi buchi di osservabilita'
(`phyclk_fgc`, `switch_macfreq`) e dove non si distingue un'op mancante da un'op non
registrata. Servono la cattura nuova e i due hook.

**135 op a #796** — e qui il disallineamento comincia su **quattro maskset per core**
su `AFECTL_C1`/`AFECTL_C2` (`0xa6`/`0xa7`) che il port non emette affatto: bit 2, 3 e 6
messi a uno e bit 7 azzerato, subito dopo la `PHY.ARRW` di #795. In
`wlc_phy_workarounds_nphy_rev7()` non ci sono: quel blocco tocca `0xa6`/`0xa7` solo sul
bit 2 e sul bit 0, e quelli il port li fa e combaciano. Sesta volta che il riferimento
non copre quello che la cattura fa, ed e' la prima cosa da guardare al prossimo giro:
sono otto op che ne sbloccano 135. Sono scritture di
tabella nell'ordine sbagliato, che e' quello che questa pagina dice da giorni.

## Cosa resta aperto

- **`M_CTS_DURATION`: messo.** La fase RXCAL ora lo scrive col MAC acceso, come il
  riferimento. Serviva una define nuova, `B43_SHM_SH_CTSDUR = 0x00B8`, e la stessa in
  `test/stubs/b43_defs.h`, che il README dichiara generato dal `b43.h` del tree ma per
  cui non c'e' uno script: aggiunta a mano, conteggio da 487 a 488.

  E ha fatto emergere due cose sul confronto. `MAC.EN`/`MAC.SUSP` **il port li
  emette** — `wrap.c` righe 689 e 694 — e non e' vero che l'harness li stubba muti: il
  decoder del vendore li chiama `MAC.MCTRL val=0x1/0x0 mask=0x1`, cioe' col bit di
  MACCTL che cambiano, ed e' un problema di nomi come `GPIO.OUTEN` → `GPIO.OE`.
  Normalizzati in `compare.py`. E lo spazio della object memory: b43 passa
  `B43_SHM_SHARED`, che nella sua enum vale 1, dove il decoder del vendore stampa
  `0x10000` — in queste due catture `0x10000` e' l'**unico** valore che compare, 3565
  e 3295 volte, quindi la traduzione e' univoca per i dati che abbiamo. Tradotta in
  `compare.py`, con la nota che se salta fuori una cattura con un secondo spazio
  quella funzione va rifatta con una mappa.

  Prima di arrivarci ho provato uno **skip** sulle due `MAC.MCTRL`, ed era il
  meccanismo sbagliato: uno skip dice "questa op non e' emettibile", e quelle lo sono.
  Rimosso.

- **La coppia di troppo non era una coppia, ed era il seme.** Il settimo marcatore
  `PHY.WR 0x2c = 0xffff` non e' un ingresso in carrier search: e' la clip detection
  che `b43_nphy_rev3_rssi_cal()` spegne da se'. Le coppie vere sono sei, risolte una
  per una: `run_samples` (tre volte), `cal_tx_iq_lo`, `papd_cal`, `rev3_cal_rx_iq`.

  E il vendore, nel suo primo passo RSSI, **non calibra: restaura**. Fra #132 e #8000
  legge `0x219` **una volta sola** — zero poll — e a #3712-#3731 scrive di fila i due
  registri radio e i dodici PHY, che e' esattamente il corpo di
  `b43_nphy_restore_rssi_cal()`. La cattura e' un init **a caldo**: il driver del
  vendore ha gia' `rssical_chanspec` valorizzata da un boot precedente e prende la
  strada del restore. Il banco azzerava quella chanspec insieme alle altre, quindi il
  port faceva una calibrazione completa: **1052 op che il vendore non ha**.

- **L'override uno-a-molti del TX gain usa il campo sbagliato.** Il caso `TX_GAIN`
  di `b43_nphy_rf_ctl_override_one_to_many()` passava `0x4000`; il riferimento fa
  `(0x1 << 12)` per il gain e **`(0x1 << 13)`** per il lpf gain, cioe' `0x1000` e
  `0x2000`. E il conteggio degli spegnimenti su `0xe7`/`0xec` lo conferma da solo: il
  vendore spegne `0x4000` **zero** volte e `0x2000` otto, il port spegneva `0x4000`
  quattro volte e `0x2000` due. Corretto anche il taglio del secondo argomento,
  `(value & 0x8000) >> 14` invece di `value >> 14`, che si portava dietro il bit 14 —
  lo stesso che la prima chiamata prende dentro il gain.

  Blocchi contigui 20951 -> **20971**, a freddo 18964 -> **18972**, e i frammenti
  piccoli di `cal-papd` da 19 a **9**. Dopo la correzione i conteggi per campo
  combaciano tutti tranne `0x8` (6 contro 4) e `0x2000` (8 contro 12).

  **Riletta tutta, campo per campo, e il resto e' a posto.** `RXRF_PU` fa
  `(1<<5)`, `(1<<4)`, `(1<<3)` su ID1; `RX_PU` le cinque su ID1/ID1/ID1/ID2/ID1 con
  `0x800` a zero; `TX_PU` le cinque su ID0/ID1/ID2/ID2/ID1 con `0x800` a uno — e
  quella quinta c'e' perche' la mette una mainline; `RX_GAIN` usa `(0x1 << 11)` e
  `(0x3 << 13)`, cioe' `0x800` e `0x6000`, e il taglio `value >> 8` su una `u16` e'
  equivalente al `(value & 0xff00) >> 8` del riferimento. Solo `TX_GAIN` era rotta.

  Dopo la correzione i conteggi per campo degli spegnimenti su `0xe7`/`0xec`
  combaciavano tutti tranne due, e vanno inseguiti **per lo stato, non per il
  punteggio**: se il vendore spegne un override e noi no, quello resta acceso.

  **`0x8`, due nel port contro tre: era un override lasciato acceso.** La cal TX I/Q
  LO interna al setup fa `rf_ctl_override_rev7(0x8, 0, 0x3, false, 0)` — accende il
  campo 0x8 su tabella 0 — e niente lo rispegneva. Restava acceso su entrambi i core
  dopo la calibrazione. La cattura lo spegne a #10729 e #10731, subito prima che i
  gain tornino al loro posto, **e il punto conta**: messo dopo `stop_playback` costa
  13 op sulla run di `cal-tx-iqlo`, messo attaccato al `ntab_write_bulk(7, 0x110,
  save)` ne vale quattro. Blocchi contigui 20971 -> **20975**, a freddo 18972 ->
  **18976**.

  **`0x2000`, sei nel port contro quattro: aperto, e con due ipotesi gia' bruciate.**
  Gli **accensioni** combaciano, due e due; sono gli spegnimenti a essere sei contro
  quattro. I sei del port stanno due per passo con due passi per core piu' due
  pulizie; i quattro del vendore (#12321, #12777, #13373, #13745) uno per core piu'
  due. Il verso e' quello innocuo — op in piu', non in meno, quindi nessun override
  resta acceso.

  **Chiuso, e la mia classificazione era sbagliata.** Il confronto **posizionale** di
  sedici op, allineando la coda del passo 2 del core 1, lo dice senza appello: senza
  la coppia `0x1000`/`0x2000` che avevo messo in testa a `b43_nphy_papd_cal_cleanup()`
  fa **16 su 16**, e dentro quelle sedici c'e' il `0x1000`/`0x2000` di #13741-#13748
  che avevo attribuito alla pulizia. Non e' della pulizia: e' la **coda di
  `papd_run_one()`**, che le emette gia'.

  Quindi i quattro spegnimenti di `0x2000` del vendore sono **due per core nei
  passi**, e la pulizia non ne fa nessuno. Togliata la coppia, i conteggi combaciano
  tutti — `0x2000` quattro e quattro, `0x1000` otto e otto — e la classificazione per
  presenza di un `0x2000` accanto e' identica op per op: `solo, E, E, solo, E, E,
  solo, solo`.

  Resta il **secondo** spegnimento di `0x1000` da solo nella lista dei campi della
  pulizia (#12820, #13788, dopo `0x800`/tabella 0): quello e' reale e sta dentro.

  E cade l'idea di gatare la coda di `run_one` su `gain_ctrl`: il vendore la fa in
  **entrambi** i passi.

  **Nota sull'arbitro.** Quel gate l'avevo misurato tre volte e ogni volta perdeva 258
  op, e io ne avevo concluso che il vendore lo facesse in un passo solo. Le 258 erano
  un artefatto di `difflib`, che **non e' monotono**: togliendo op dal lato port puo'
  perdere appaiamenti. Per una domanda su otto op l'arbitro e' il confronto
  posizionale su un'ancora vicina, non il matcher — e le tre misure che avevo scritto
  in questa pagina erano tutte inutili.

  Bruciata anche **spostare le tabelle dell'ADC ausiliario prima delle sequenze RF**,
  che e' l'ordine della cattura: costa 24 op. La posizione delle otto maskset su
  `AFECTL_C1/C2` resta legata a quella.

- **Otto maskset su `AFECTL_C1`/`C2`, gateate su radio rev 8.** La cattura le ha a
  #796-#803: bit 2, 3 e 6 a uno e bit 7 a zero, core 0 poi core 1 ogni volta, e senza
  toccare la coppia di override accanto. Il riferimento quei bit li tocca solo nel
  percorso della tempsense, e la' sempre insieme a `0x8f` e `0xa5`.

  Numeri fermi, e la posizione **non** e' ancora quella del vendore: lui le mette fra
  le tabelle dell'ADC ausiliario e le sequenze RF, il port le mette prima di entrambe.
  Spostare le tabelle dell'aux ADC prima delle sequenze, che e' l'ordine della cattura,
  costa **24 op**: qualcosa in mezzo dipende dall'ordine e non e' capito. Le otto op
  stanno dentro perche' la cattura le ha.

- **Il primo ritardo della sequenza TX2RX e' `0x46`, non 8.** La cattura lo scrive a
  #806, nel bulk da sette celle su tabella 7 offset `0x90`. Per rev 7 e su il
  riferimento non aiuta: `wlc_phy_workarounds_nphy_rev7()` **non programma affatto** la
  sequenza TX2RX, quindi l'8 che stava in `b43_nphy_workarounds_rev7plus()` non aveva
  niente dietro. I sei ritardi che seguono e tutti e sette gli eventi combaciavano
  gia'. Costa **una** op, perche' quella cella sta dentro il buco da 135 che comincia
  prima: sta dentro perche' il valore ha una fonte e il precedente no.

- **`tx_power_offset[]` va riempita prima dell'init tracciato, ed e' ancora il seme.**
  A #2000 e #2086 il vendore scrive le 84 celle della tabella di potenza aggiustata
  **col contenuto** — `0 0 0 0` e poi `2 c c c` ripetuto — dove il port scriveva
  ottantaquattro zeri. Il motivo: `nphy->tx_power_offset[]` la riempie solo
  `recalc_txpower`, che nell'harness girava **dopo** l'init tracciato; il driver del
  vendore quegli offset ce li ha perche' la cattura e' un init a caldo e il suo boot
  precedente li ha calcolati. Aggiunto un `recalc_txpower` non tracciato subito dopo
  l'init a freddo, dentro la regione che scrive su `/dev/null`.

  **Attenzione al pending**: senza spegnere `perical_pending` prima, quel recalc si
  tira dietro la sequenza differita, che rifa' la cal RSSI e riscrive la cache — e il
  secondo init restaurerebbe quella invece di quella del primo. Provato: `up-ch1`
  perdeva 479 op e la finestra `rssi-cal` non trovava piu' la sua ancora (`PHY.WR
  0x1b8 val=0x3f` sparisce). Con `perical_pending = false` prima, resta solo il calcolo
  degli offset.

  Blocchi contigui 20632 -> **20952 (91%)**, per fase 8590 -> **8756 (47%)**, buco
  portabile 963 -> **643**, e la finestra `pwr-setup` passa da 266/432 a **432/432**.

  Terza volta che il collo di bottiglia e' il seme e non il driver, dopo la cal RSSI e
  i gain d'ingresso. **La regola vale: prima di cercare codice mancante, guardare se il
  banco parte da uno stato che la cattura non ha.**

- **La scala della cal TX I/Q LO si scrive in due corse, non interleavata.**
  `b43_nphy_update_tx_cal_ladder()` scriveva 0, 32, 1, 33, 2, 34...; la cattura scrive
  `0x00`-`0x11` e poi `0x20`-`0x31`, due blocchi consecutivi, e lo mostra **due volte**
  (#9015-#9123 e #9735-#9843). Stesse trentasei celle della tabella 15 e stessi valori:
  cambia solo il raggruppamento. brcmsmac interleava anche lui — **quinta volta**.

  Blocchi contigui 20426 -> **20632 (90%)**, a freddo 18758 -> **18965 (69%)**, buco
  portabile 1169 -> **963**. Due righe di ciclo per 206 op: il rapporto migliore fra
  righe toccate e op recuperate di tutta la serie.

- **Le tabelle dell'ADC ausiliario non sono piu' un `/* TODO */`.** In
  `b43_nphy_workarounds_rev7plus()` le quattro write bulk su tabella 8, offset `0x08`,
  `0x18`, `0x0c` e `0x1c`, erano commentate via perche' gli array non c'erano. La
  cattura le ha a #771-#794: `0x8e 0x96 0x96 0x8b` per il core 0, `0x8f 0x9f 0x9f
  0x96` per il core 1, `0x02 0x02 0x02 0x00` per i due di gain.

  Il riferimento sceglie l'ultimo elemento dal power detector range e dalla banda.
  Solo la combinazione di questa board sta nel port — range 2, radio 2057 rev 8, 2 GHz
  — perche' le altre non hanno cattura dietro. E la' brcmsmac scrive `0x8c` su
  **entrambi** i core dove la cattura scrive `0x8b` sul core 0 e lascia il core 1 a
  `0x96`, che e' il default dell'array; l'elemento di gain concorda a 0. **Quarta
  volta** che brcmsmac e' piu' vecchio del driver delle catture.

  Blocchi contigui 20402 -> **20426**, a freddo 18734 -> **18758**, buco portabile
  1193 -> **1169**.

- **La pulizia della cal PAPD spegne anche il campo `0x2000`, e le due prime vanno
  prima di fermare il tono.** La cattura, a #13741-#13748: `e7`+`0x7c` e `ec`+`0x7f`
  (campo `0x1000`), poi `e7`+`0x348` e `ec`+`0x349` (campo `0x2000`, il cui valore sta
  nei quattro bit bassi di quei due registri e non in un registro intero). Il port il
  `0x2000` non lo spegneva affatto e il `0x1000` lo spegneva dopo. Ora le otto op sono
  op per op quelle della cattura, e i numeri **non si muovono**: quel vicinato resta
  dentro il buco da 167 op, che va capito per intero. Sta dentro perche' e' giusto, non
  perche' paga.

  Corretto nel **banco**, non nel driver: `rssical_chanspec_2G` resta valorizzata. Le
  altre tre si azzerano come prima, perche' la cattura la cal TX I/Q LO e la RX I/Q le
  contiene davvero (le parentesi a #8492 e #14964 lo dicono).

  **I valori non si seminano: ce li mette il primo init**, che la calibrazione la fa.
  Ne escono i due registri radio e **undici dei dodici** PHY identici alla cattura.
  Copiarli dalla cattura invece di lasciarli calcolare vale **una op** su `up-ch1`
  (20403 contro 20402), e quattordici costanti copiate dentro il banco non valgono
  un'op.

  L'unico che differisce e' `0x1ac`, l'offset fine narrowband del **core 0 sulla rail
  Q**: il banco calcola 0, la cattura ha 1. E il ciclo che lo scrive usa gia'
  `offset[i]` e non `offset[2 * core]`, quindi non e' la forma del codice — sono i
  valori polled a differire di un passo. Voce aperta, e piccola.

  **A freddo non sappiamo come vengono calcolati, e non e' un'omissione: non c'e'
  cattura.** `full-init-ch1-bw20` la cal RSSI la **comincia** e viene troncata: i
  primi due gruppi di poll stanno a #32637 e #32709, e a #32769 parte il buco da 65285
  record. Quindi dell'algoritmo a freddo abbiamo il codice — lo sweep dei VCM, che in
  questo lavoro e' stato corretto due volte — e nessuna traccia contro cui verificarlo.
  Per averla serve una cattura nuova che copra oltre #32769.

  | | prima | dopo |
  |---|---|---|
  | **totale per fase** | 7749 (41%) | **8590 (46%)** |
  | `up-ch1` blocchi contigui | 20035 (87%) | **20403 (89%)** |
  | `cal-rssi-2` | run 99, 10% | **run 940, 98%**, forma `940 18` |
  | finestra `rssi-cal` | 1/16, mancano 15 | **9/16, mancano 4** |
  | coppie carrier search | 7 | **6**, come il vendore |
  | letture di `0xb0` | 25 | 22 (vendore 16) |

  E' il guadagno piu' grande di tutto il lavoro, e non e' una riga di driver: e' una
  riga di seme. **Quando una fase fa un ordine di grandezza in meno del resto,
  guardare se il banco la sta forzando su un ramo che la cattura non prende.**

- **Vecchio: il gate in `b43_nphy_run_samples()` NON va messo.** Il riferimento la' gatea su `phyhang_avoid`
  (`phy_n.c:23087`) e b43 chiama senza condizione; e `hang_avoid` in b43 e'
  `(rev == 3 || rev == 4)`, falso su rev 8. Sembra un refuso, e non lo e': dentro la
  prima coppia da 34 op del **vendore** (#1620-#1666) ci sono `0xa1`, `0xa3`, `0xa4`,
  `0xc3`, `0xc4`, `0xc5`, `0xc6`, l'override lpf su `0x340`-`0x343` e la lettura di
  `15/0x57` — cioe' `run_samples`, con la parentesi, su un rev 8. Il vendore la fa, e
  la chiamata senza gate di b43 e' giusta **per questo hardware**. brcmsmac e' piu'
  vecchio, di nuovo.

  Provato a mettere il gate e misurato: il port passa da **7 coppie a 5** dove il
  vendore ne ha 6, cioe' si allontana; a freddo pero' guadagna **+1137** (18734 ->
  19871, 68% -> 72%) e a caldo perde 126, con la run per fase da 7749 a 7737.
  Ritratto per il conteggio delle coppie e per la run, ma **quel +1137 a freddo non e'
  spiegato**, ed e' la cosa piu' grossa non capita adesso.

  Il sito della coppia in piu' resta da trovare: e' quella da 1052 op che apre a
  `@3271`, subito dopo l'ultima op di `b43_nphy_tx_power_ctl_setup()`, e **non** e'
  `tx_power_ctl_setup` — quella e' gateata su `hang_avoid` in entrambi i driver,
  verificato. Il metodo che funziona: `fprintf` con `__builtin_return_address(0)`
  dentro `b43_nphy_stay_in_carrier_search()` e risoluzione con `nm -n`, tenendo
  presente che l'offset PIE va calcolato e che una stima sbagliata sposta il simbolo
  di uno.

- **Difetto di mainline trovato per strada, che non riguarda questo hardware.**
  `hang_avoid` in b43 e' `(phy->rev == 3 || phy->rev == 4)`; in brcmsmac
  `NREV_GE(rev, 3) && NREV_LT(rev, 6)`, cioe' 3, 4 **e 5**. Su rev 5 b43 salta tutte
  le parentesi anti-hang che il riferimento mette. Candidato mainline, dimostrabile
  contro brcmsmac senza hardware, non misurabile qui.

- **Il conto della finestra `rxiq-ingresso` passa da 64 a 555, e non e' una
  regressione.** Con le tre op al loro posto la parita' dell'allineamento cambia e
  riemerge uno sfasamento che era mascherato: il piano di lettura di `0xb0`. Le op
  restano le stesse — mancano 18 e ce ne sono 18 in piu' su 1503 — e le due misure
  grandi salgono di 4 ciascuna. Si chiude togliendo la coppia di carrier search di
  troppo, non lavorando in quella finestra.

- **Vecchia voce, per memoria: `M_CTS_DURATION` non era una deroga.** Nel gruppo da 15
  op di `rxiq-ingresso` il vendore fa, in mezzo alle due `MAC.MCTRL`, una `OBJ.WR
  addr=0xb8 val=0x2710`: e' `write_shm(M_CTS_DURATION, 10000)`, perche'
  `M_CTS_DURATION = M_PSM_SOFT_REGS + 0x5c * 2 = 0xb8`. Il riferimento la fa **due
  volte**, in entrambi i rami che portano alla cal RX IQ (`phy_n.c:25413` per la
  macchina a stati e `25460` per l'altro), e in b43 **non c'e' da nessuna parte**:
  `grep CTS_DURATION` su tutto il driver non trova niente.

  L'avevo archiviata dentro la deroga `OBJ.WR`, e la deroga dice un'altra cosa: che
  l'harness non puo' **emettere** op di object memory in modo confrontabile — non che
  il driver non debba **fare** la scrittura. E infatti `wrap.c` ha `b43_shm_write16()`
  e la stampa come `OBJ.WR`, quindi la scrittura sarebbe perfino visibile nel trace.
  Le due `MAC.MCTRL` attorno sono `b43_mac_enable()` e `b43_mac_suspend()`: quelle si
  la' l'harness le stubba, e la deroga su di loro regge.

- **`rxiq-ingresso`, 500 su 1503 con 64 divergenze**, di cui una **non** dichiarabile:
  la `OBJ.WR` di sopra. Le altre sono sei di rilettura a 9 bit, le due `MAC.MCTRL` col
  rimescolamento che ne segue, le due `PHY.CLK` (buco del tracer, vedi sopra), tre di
  allineamento dei piani a valle della coppia di carrier search in piu', ventotto di
  confine con la fase dopo. I blocchi sono 500, 401, 288, 178.
- **`perical-ingresso` e' chiusa**: 575 su 1402 con 17 divergenze dichiarate.
- **Restano due voci, entrambe piccole.** La coppia di carrier search in piu' (7
  contro 6, con 9 letture di `0xb0` in piu' e i valori scritti che combaciano), e le
  due `PHY.MOD 0x349 val=0x0 mask=0xf` a #13320 e #13392 che il port non emette mai —
  la maschera a 4 bit e' il campo `0x2000` da solo, la voce `(0x1 << 13)` della
  tabella di override rev 7.
- **`cal-papd`: restano fuori `a3`/`a2`**, due buchi da 349 e 276 op a caldo e 920 e
  930 a freddo, perche' a freddo la ricerca dell'indice di gain e' completa.
- Il buco **#190-254** di `switch_channel` non e' portabile, e non e' lo spurwar: in
  brcmsmac entrambi i flag che accendono quel corpo, `nphy_gband_spurwar_en` e
  `nphy_gband_spurwar2_en`, sono gateati `phy_rev < 7` in `wlc_phy_attach_nphy`,
  quindi su rev 8 la funzione non fa niente — esattamente come lo stub di b43. Le op
  che restano fuori sono `PHY.WR 0x1df = 0x1591`, `0x1e1 = 0x1591` e una `TBL.RD
  id=0x7 off=0x106 len=2`; quei due indirizzi (`STRA_2U`/`STRA_2L`) in b43 esistono
  solo come define e **brcmsmac non li scrive mai**. Stessa categoria di `RAD.RD
  0x81`: op del vendore senza riferimento GPL, non si porta.
- **Il ciclo di misura e' l'ACI scan.** Il nome sta in brcmsmac, che ne tiene il
  **prototipo e non il corpo**: `int wlc_phy_aci_scan_nphy(struct brcms_phy *pi);`
  in `phy/phy_int.h:1097`. ACI e' *adjacent channel interference*, e spiega la forma
  che la cattura mostra: l'hop fuori canale ogni ~2 secondi, 100 campioni per core
  su `0x1c9`/`0x1ca`, e l'assenza dal primo up. **Non e' `poll_rssi`**: quella
  alterna i due registri e su rev 8 legge `0x219`/`0x21a`, mentre qui sono 100
  consecutive su un registro e 100 sull'altro. E i due indirizzi su rev 8 non sono i
  latch GPIO che dicono i nomi in `phy_n.h`: nella cattura **3400 letture e zero
  scritture**. Il prototipo orfano e' il punto: e' una **politica** che sta sopra il
  PHY, e il posto corrispondente in b43 e' la mitigazione dell'interferenza
  (`B43_INTERFMODE_*`), che esiste solo per il G-PHY. `b43_nphy_rev8_chan_meas()` in
  `0015` e' la sua primitiva di misura e resta senza chiamante finche' la politica
  non c'e'.

## Una cosa dell'hardware, non del port

In 26/27 oltre l'offset 576 la rilettura e' il valore scritto **mascherato a 9
bit**, misurato su cinque celle su cinque (`0x24a`, `0x24c`, `0x25e` sui due core:
scritto `0xffffffe9`, riletto `0x01e9`; scritto `0xffffffbb`, riletto `0x01bb`). I
due lati scrivono lo **stesso** valore e il mirror delle tabelle nell'harness tiene i
32 bit interi: **non e' stato mascherato di proposito**, perche' cinque celle di una
regione in una cattura non giustificano una larghezza dentro lo strumento, e la
divergenza e' inerte — il solo consumatore e' `b43_nphy_txpwr_index()`, che fa
`(((s16)v) << 4) & 0x1ff0`, e `0xffffffe9` e `0x01e9` danno entrambi `0x1e90`. Costa
due op sulla finestra `txpwr-index` e sta dichiarata la'.

## La struttura della cattura

`wlc_phy_a4` è la cal PAPD e gira **una volta per init**; `a3_nphy` (147 righe)
cerca l'indice di gain e **legge** la tabella epsilon, `a2_nphy` (279) la
**scrive**. Mappa completa in `docs/papd-cal-map.md`, flusso affiancato dei due
driver in `docs/init-flow.md`.

`do_full_init` (b43) == `phy_init_por` (brcmsmac): dietro ci stanno il download
delle tabelle statiche e rcal/rccal.

Dentro `up-ch1` la cal PAPD si legge cosi', ed e' il modo in cui va citata: blocchi
a #10966 (847 op), #11822 (334), #12784 (145), #12936 (334), #13752 (90), #13856
(48), #13921 (172).

**Le catture sono due e servono a cose diverse.** `opinit-ch1-ch6-bw20.decoded`
(70796 record) e' il riferimento di tutto quello che sta qui sopra: e' un init **a
caldo** e non contiene il download statico — l'apertura della tabella 10 non compare
in nessuno dei suoi due init — e per questo il flow `init` fa due init e traccia
solo il secondo. `full-init-ch1-bw20.decoded` (81397 record) e' un init **a
freddo**, ed e' la sola che contenga le tabelle di init: contro quella, col flow
`initpor`, il port **le riproduce op per op** — 1424/1424 sulla tabella 13 e 806/806
sulla 18, finestre `static-tables` e `static-tables-2`, le uniche due che dichiarano
`capture=`. Ha un buco da 65285 record oltre #32769, quindi solo #2-32769 e'
confrontabile posizionalmente.

I numeri di record qui e nei documenti sono di `opinit-*` quando non e' detto
altrimenti: gli intervalli esistono in entrambi i file e **non si
autoidentificano**.

In mainline la cal periodica non parte: `perical = 2`, e il ramo che ne consegue in
`b43_phy_initn` è un `;/* TODO */`. `0012` ci mette l'init delle tabelle PAPD e
`0014` la sequenza del vendore, gateata su phy rev 8 e radio rev 8. Il flow `full`
non si muove, perché mette `perical = 0` e prende l'altro ramo. `initpor` e' l'unico
flow che traccia un init a freddo **con** le cal: non azzera `perical`, quindi passa
dal ramo di `0014`.

## Le finestre, che sono due: una per comportamento

`CONTIG` in `phase_compare.py` ha **due** voci, e sono la stessa macro operazione
nei suoi due comportamenti. Non sono due fasi: sono due strade che il codice
prende, e una fase di calibrazione verificata contro una cattura sola valida un
ramo e non dice niente dell'altro.

| finestra | cattura | flow | op | in blocchi |
|---|---|---|---|---|
| `up-ch1` | `opinit-*`, init a caldo | `txpower` | 22943 | **21090, 92%** |
| `up-ch1-freddo` | `full-init-*`, init completo | `initpor` | 27563 | **19349, 70%** |

`up-ch1` comincia dove comincia `switch_channel` — la `CHANSPEC` di **#132**, che
il tracer emette e il port no — e finisce col **MAC abilitato che trasmette**,
#26100. Nessuna ancora: la finestra e' tutta la run, quindi i blocchi si trovano
sull'intero output del flow senza agganciarsi a un'op scelta a mano.

`up-ch1-freddo` parte dalla `CHANSPEC` di **#339** e finisce a **#32769**, che non
e' il MAC abilitato ma il limite di confrontabilita'. Copre **piu'** dell'altra
perche' contiene il download delle tabelle statiche, che a caldo non c'e' — si
vedono come blocchi da **1424** e **806** op.

Tutto cio' che precede, **#1-131, e' `op_init` e `rfkill`**: e' lo stato che questa
finestra non puo' avere, e si **semina** invece di tracciarlo (sotto).

Le region per fase sono state provate e togliere, e non e' un ripensamento estetico:
**una fase presa da sola non dice niente su cio' che le arriva addosso da prima**.
La finestra `chanswitch-ch6` dice 33/39 e "nessuna op mancante", e la fase intera
sta al **14%**, perche' il 62% e' un ciclo di misura che il port non fa affatto. Il
verdetto di `up-ch1` e' la **struttura dei blocchi**, non una percentuale: un blocco
che si accorcia e' una regressione anche se il totale sale.

Due cose sulla lettura del report:

- **`minsize` filtra la stampa, non il conteggio.** Filtrarlo anche nel totale
  toglie ~630 op vere in run piu' corte di 16. Un buco stampato puo' contenere run
  brevi.
- **"Zero occorrenze" non prova niente.** Puo' voler dire che il tracer non guarda o
  che `wl` non lo fa, e le due hanno conseguenze opposte sul port. Si risolve
  guardando **dove l'accesso passa**:
  - `PMU.`: `wl-diag` aggancia `si_pmu_spuravoid` (il decoder lo stampa `PMU.SPUR`)
    e la funzione e' quella che mainline chiama `bcma_pmu_spuravoid_pllupdate`
    (`drivers/bcma/driver_chipcommon_pmu.c:493`), cioe' esiste ed e' agganciabile:
    zero occorrenze vuol dire che **wl non la chiama**, e il `PMU.SPUR` del port e'
    una divergenza vera.
  - `MMIO.` e' in deroga, ma la motivazione giusta e' il **livello**, non il
    conteggio: quegli accessi il vendore li registra come **`SI.COREREG`** (54 nella
    cattura, `core=0x0`, `off=0x64` e `0x6c`), quindi cercare `MMIO.` non prova
    niente. `0x492` e' `psm_phy_hdr_param`, e in brcmsmac ci si arriva con un
    `bcma_write16` **diretto**, non con un accessor (in
    `wlc_phy_chanspec_nphy_setup`, bit in `d11.h:978`): un tracer che aggancia
    funzioni non lo vede.
  - `PHY.CLK`: la deroga regge, ma **era valutata contro l'accessor sbagliato**.
    `b43_phy_force_clock()` corrisponde a `wlapi_bmac_phyclk_fgc` →
    `brcms_b_phyclk_fgc` (`main.c:1716`), non a `brcms_b_core_phy_clk`. `wl-diag`
    aggancia `wlc_bmac_core_phy_clk`, che e' un'altra funzione: quindi
    `phyclk_fgc` **non e' agganciato** e le sue op non sono osservabili in queste
    catture. E il port fa la cosa giusta — `b43_nphy_reset_cca()` e
    `wlc_phy_resetcca_nphy()` sono identiche, `fgc(ON)`, BBCFG, `fgc(OFF)`,
    `RESET2RX` — quindi le due `PHY.CLK` che il vendore non ha sono un buco del
    tracer, non del port. Per chiuderla del tutto: un hook su `phyclk_fgc` e una
    cattura nuova. `MAC.FREQ` resta in deroga non dimostrata come prima
    (`brcms_b_switch_macfreq`, agganciato in `wl-diag`, quindi zero occorrenze
    vorrebbe dire che wl non lo chiama: da riverificare su una cattura nuova).

  Regola: una deroga si dichiara **contro un hook mancante**, mai contro un
  conteggio a zero, e **mai su una famiglia intera quando dentro c'e' un'op che il
  driver dovrebbe fare**: la deroga `OBJ.WR` dice che l'harness non puo' emettere
  object memory in modo confrontabile, non che b43 possa non scrivere la SHM. Ci sono
  cascato su `M_CTS_DURATION` — e prima di dichiararla si guarda se **l'accessor esiste**. E
  non basta che *un* accessor della famiglia sia agganciato: **si guarda da che
  accessor passa quell'accesso.** La object memory lo insegna: `write_objmem16` era
  agganciata, ma una regione letta 192 volte e mai scritta la scrive
  `copyto_objmem`, che dentro chiama `write_objmem` e non la variante `*16`, che non
  era agganciata (`gap-inventory.md` 4i). La famiglia e' grande — in brcmsmac sono
  **66 `brcms_b_*`** — e `wl-diag` ne agganciava **dieci**: le mancanti erano la
  ragione di tutte e tre le deroghe. Aggiunte `read_shm`, `write_shm`, `set_shm`
  (offset in **byte**, lo stesso livello di `b43_shm_*16`: e' cio' che rende
  confrontabili i **677 offset SHM** che prima erano rumore), `core_phy_clk`,
  `switch_macfreq`, e `suspend_mac_and_wait`/`enable_mac`, che danno il confine **MAC
  abilitato** su cui finisce `up-ch1`.

  Gli accessi che **non** passano da un accessor restano non osservabili, e la deroga
  si dichiara contro quello. Una variante che marcava l'ingresso delle funzioni del
  PHY e' stata provata e **togliere di proposito**: marcare le funzioni interne
  produce una mappa della struttura del driver del vendore, che e' cosa diversa
  dall'osservare l'hardware e molto piu' facile da contestare. Un confine di fase si
  ricava dalle op degli accessor, e `MAC.SUSP`/`MAC.EN` ne danno uno esplicito. Vale
  per le **catture nuove**.

Il gate `!do_full_init` sulla coda della cal periodica **non va messo**, e il motivo
e' istruttivo: la finestra fredda contiene le **prime nove op** di quella fase e poi
finisce, perche' a #32769 comincia il buco da 65285 record. Gli ultimi record della
cattura fredda, #32753-32769, sono le stesse op nello stesso ordine di #23761-23777
nella cattura calda: il vendore la fase la comincia anche a freddo, e il buco la
taglia. **Gatare la' vorrebbe dire gatare contro un buco**, che e' lo stesso errore
di gatare contro un conteggio a zero.

## I seed, e quanto valgono

`reverse-tools/gen_seed.py --before 132` guarda **solo i record che precedono la
finestra** ed emette `test/seed_up.h`, che `main.c` applica dopo l'init a freddo e
prima di quello tracciato. Due categorie:

1. cio' che `op_init` e `rfkill` hanno programmato;
2. cio' il cui **primo accesso nella cattura e' una read**: nessuno l'ha scritto,
   quindi e' il default del chip. Il criterio non e' "mai scritto" — `0x17d` la cal
   la scrive, ma **dopo** averla letta. Con questo entrano le due `atten` del
   coupler a `0xaa`, che erano l'ultimo buco di valore della cal PAPD.

Totale 68 phy e 70 radio, di cui 91 default. **Misurato: valgono 32 op su 22951**,
quindi cio' che non combacia **non e' stato mancante, e' codice**. Il meccanismo
resta perche' e' corretto e servira' quando i buchi si chiudono, non perche' sia la
leva. Non farlo sembrare la leva.

Per le **celle di tabella** il confine del seme e' per forza diverso da quello dei
registri. Per i registri si guarda solo prima della finestra; una cella come
`15/0x50` non e' scritta da nessuna parte nella cattura, perche' il download statico
che l'ha riempita e' di un boot precedente. Il suo stato all'ingresso e' osservabile
**solo dalla prima read dentro la finestra**, e due condizioni tengono onesta la
regola: si semina la cella che nessuna write per porta ha toccato prima di quella
read — se la finestra ci ha scritto, il valore e' cio' che la finestra deve
calcolare — e il cui valore **non cambia** fra le read, perche' se cambia e'
l'hardware che ci scrive dentro la finestra ed e' lavoro di un piano. Sono **39
celle**; le 5 che restano fuori dalle 44 a valore fisso sono quelle che una write per
porta aveva toccato.

## Regole

- **Le misure stanno negli strumenti**, non in script usa-e-getta: vanno rifatte.
- **La doc può essere stale.** Ne ho corretta parecchia; non fidarsi, riverificare.
- I riferimenti `file:riga` vanno controllati sul tree **pristine**, non su quello
  con le patch applicate.
- **Delimitare la fase** prima di contare, con un'op che la chiuda (es. il primo
  `CHANSPEC` per l'init del radio), non a occhio su un intervallo di record.
- **`Op.ep` è l'unico modo** di sapere da che record viene un'op: `load_vendor`
  scarta bookkeeping e ombre, quindi indice ≠ numero di record.
- **Quando una fase fa zero e le op ci sono, sospettare il valore prima del punto di
  chiamata.** `coeff-setup` ha detto zero per tre sessioni e la colpa era di
  `tbl_port_get()` in `wrap.c`, che non faceva avanzare l'indirizzo in lettura.
- **Quando una cella di tabella diverge, guardare la sua storia prima del flusso del
  riferimento**: `trace_tables.py --cell ID:OFF` la stampa, letture comprese, e
  distingue le write che cambiano il valore da quelle idempotenti.
- **Un conteggio che torna non prova che il comportamento sia giusto.** 35 write
  uguali a 35 con la sequenza ancora sbagliata e' successo, e ha costato 151 op
  contigue.
- **Contare occorrenze di un'op senza verificare cosa quell'op significhi** e' la
  fonte di tutte e tre le ritrattazioni di questo file: i due versi di
  `b43_nphy_tx_power_ctrl()` si distinguono solo dal **payload** (84 zeri =
  spegnimento), e in b43 hanno perfino forme d'op diverse — l'accensione emette
  `TBL.WR`, lo spegnimento scrive a mano la porta e non ne emette. Il tracer del
  vendore aggancia la funzione di tabella e vede i due versi allo stesso modo,
  quindi i suoi conteggi **non sono confrontabili** con i nostri per op.
- **Un marcatore va verificato che marchi una cosa sola.** `TBL.RD 7/0x110 len=2`
  non e' della parentesi: lo legge anche `b43_nphy_get_tx_gains()`, con la condizione
  **opposta**.
- **Quando un numero scende, misurare la regione da sola prima di chiamarla
  regressione**: l'assegnazione dei blocchi e' esclusiva e golosa, e un blocco puo'
  cambiare mano senza che niente sia peggiorato.
- **Prima di dire che un cambiamento non serve perche' la fase non si muove,
  guardare i blocchi**: la metrica per fase ignora i frammenti di proposito, e
  sotto-riporta un fix giusto.
- **Prima di dire che il port fa qualcosa in piu', guardare se il riferimento GPL lo
  fa** — e se lo fa, la domanda e' se il tracer possa vederlo.
- **La precedenza e': la cattura, poi brcmsmac.** brcmsmac serve a capire la forma e a
  dare i nomi, e per quello e' insostituibile; ma e' molto piu' vecchio del driver che
  ha prodotto queste catture, e ogni volta che i due hanno litigato aveva torto lui
  (indice di precal, raggruppamento dell'rccal, indice riforzato in coda). Un
  cambiamento **non** si giustifica con brcmsmac contro una misura: si va a cercare
  nella cattura la prova diretta, che di solito c'e'.
- **Un difetto che sembra tale va misurato prima di crederci.** Il degrado
  `type = 2 -> 0` in `b43_nphy_cal_rx_iq()` era dato per difetto da sempre;
  togliendolo il port peggiorava di 476 op, perche' il difetto vero era a monte
  (`bool` invece del modo del test DAC).
- **Il controllo di un build e' lo stato di uscita, non un grep.** La riga di
  compilazione contiene `-Werror`, quindi `grep error` matcha sempre:
  `if make KDIR=... >/tmp/b.log 2>&1; then echo OK; else grep -E 'error:' /tmp/b.log; fi`
- **La riga `N finestre: X da guardare` va letta a ogni giro**, non solo il totale:
  e' l'unica cosa che dice se un cambiamento ha rotto un'ancora, e le due misure
  grandi non se ne accorgono.
- Ogni patch dietro un gate di revisione, verificato con `check_patch_gating.py`.
  Eccezioni dichiarate, tutte e sole per refusi di trascrizione da brcmsmac in
  codice condiviso: `b43/MESSAGES.md#0010` e la mainline
  `b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7`. Un refuso non e'
  una feature di questo hardware e dietro un gate non ci va.
- Niente commenti "prima era così": quelli vanno nel messaggio di commit. Vale anche
  per i delta di misura — `da X a Y` in un commento e' storia.
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

1. **Usato il blob fuori dal perimetro che `PROVENANCE.md` dichiara.** Quel file
   dice da sempre che del blob servono i **simboli con le size** (per le tabelle) e
   i **prologhi degli accessor** (per sapere se il detour tiene), perche' il
   prodotto di quell'analisi e' il tracer. Per attribuire il ciclo di misura ho
   disassemblato corpi di funzione ed elencato chiamanti: conclusioni giuste, fonte
   sbagliata, rifatte su `brcmsmac` che le aveva tutte. **Le domande sul
   comportamento vanno a `brcmsmac` prima**, e `PROVENANCE.md` si legge prima di
   aprire il blob, non dopo.
2. Costruito l'harness contro un tree **senza le patch** e letto i risultati come
   regressioni. Controllare `git -C ~/src/linux diff --stat` prima di credere a un
   numero. (Idea aperta: farlo fallire in `make`.)
3. Citato numeri di riga presi dal tree patchato: `phy_n.c:4021` invece di `3950`.
4. Contata una fase su una finestra a occhio che ne mescolava tre, e concluso il
   falso ("70 registri sottoinsieme dei 412" — 32 su 70 avevano valore diverso).
5. Ricostruito a mano la corrispondenza op→record: deriva fino a 230 op.
6. Attribuito al "core non compilato" op che erano in codice compilato e non
   chiamato (`b43_software_rfkill` era uno stub vuoto in `wrap.c`).
7. Creduto a un'ancora di `phase_compare.py` mai trovata (`0x186 val=0x100`, che
   nella cattura non esiste): una finestra `pending` con ancora impossibile non
   fallisce mai e non dice niente.
8. Scritto "serve una lettura su hardware" quando il valore era nella cattura.
9. **Creduto a una finestra che si e' rotta, invece di guardare su cosa era
   agganciata.** `recalc-txpower` e' passata da 519/519 a 432/519 aggiungendo la coda
   della cal periodica, e sembrava una regressione del driver. Era l'ancora: la
   finestra prendeva la **terza** apertura di `26/0x0`, che era la recalc del port
   finche' la sequenza girava altrove, e che con la sequenza in coda a recalc e'
   diventata il power setup della coda della cal. Confrontava la recalc del vendore
   con la coda del port. Corretta l'ancora alla seconda, la finestra torna 519/519
   **con** la modifica dentro. Un'ancora ordinale si sposta quando il codice si
   sposta: quando una finestra si rompe, prima si guarda dove e' atterrata.
10. **Creduto a una misura per regione non ancorata.** Una fetta di 1402 op del
    vendore confrontata contro le 24000 del port dava 92% in 31 blocchi, e da quei
    31 blocchi ho dedotto una frammentazione dentro `b43_nphy_txpwr_index()`. Non
    c'era: i blocchi si spargevano su 14065 op di traccia, cioe' erano le dieci
    scritture da 84 zeri identiche fra loro, prese ognuna da un punto diverso. Il
    totale della finestra intera non ha questo problema, perche' la fetta e'
    l'intera run. Regola: **prima di leggere un numero per regione, guardare dove
    atterrano i blocchi.** `phase_compare.py --global-run` ora lo stampa da solo.
11. Misurato su un flow diverso da quello che la regione dichiara: `up-ch1` dichiara
   `flow=('txpower', '1')`, che e' init **piu'** `recalc_txpower`. Il commento
   accanto alla regione lo spiega.
12. I **bit di esecuzione** si perdono a ogni merge fatto applicando il diff
    (`git apply` senza `--index` non li mette nell'indice). Sette volte finora:
    `sh scripts/check-exec-bits.sh`.
13. **Tagliata la testa di `rollup.diff` per numero di righe**, e prima ancora sul
    primo `---`: ma la nota di copertura usa `---` anche fra un incremento e
    l'altro, quindi sono spariti 73 righe di incrementi, due volte. Si taglia sul
    primo `diff --git`, e si controlla che il pezzo sopravvissuto combaci con
    `git show HEAD` prima di ricucire.

## Difetti trovati in mainline, per ricordare cosa cercare

`patches/mainline/` sono i **dodici** indipendenti da questo hardware, da mandare
per primi e come **dodici `[PATCH]` separate in altrettanti thread**, non come serie: non
dipendono l'una dall'altra, e legarle vuol dire che una review lunga su una blocca il
merge delle altre. L'elenco con una riga a testa sta in `patches/mainline/README.md`,
che e' la fonte. Con la sola `sample-table-logic`, `sampleplay-tssi` e
`sampleplay-iqlo` fanno 322/322.

Il piu' grosso e' il **campo** dell'indice di potenza: spegnendo il controllo
acceso, b43 salva i sette bit bassi dello stato per catena invece dei bit 8..14, e
il ripristino rimette quel campo nell'indice. Gira su ogni N-PHY rev 3 e su, su
ogni percorso che parentesizza del lavoro col controllo spento — le calibrazioni e
il cambio canale. Su questa cattura l'indice e' 25 e i sette bit bassi sono zero,
cioe' il fondo della tabella. Lo dice il define di questo stesso driver,
`B43_NPHY_TXPCTL_STAT_BIDX`, e venti righe sotto `b43_nphy_get_tx_gains()` legge lo
stesso campo giusto.

Refusi di trascrizione da brcmsmac e di precedenza C, non buchi di feature: i due
della cal PAPD sono `tbl_rf_control_override_rev7_over1` con due `val_mask` che non
coprono il campo del proprio shift, e `one_to_many` `TX_PU` con quattro chiamate su
cinque (dimostrati a tre voci: brcmsmac e la cattura concordano contro b43). Poi, in
ordine: `0005` registro sbagliato, `0010` `<<` che lega più forte di `&` più un passo
di fase troncato in una `u16`, `0011` dieci campi persi con la tabella "solo 2 GHz",
`0012` tabelle inizializzate nel posto sbagliato. Vale sempre la pena confrontare il
**gate** oltre al corpo: b43 ha `phy->rev != 5` dove brcmsmac ha `radiorev != 5`
(`docs/todo-nphy.md` 3d bis).

## L'init del radio, chiuso

Il record del blob e' `{u16 address; u16 init; u8 do_init; u8 pad}`, sei byte, e **39
voci su 412 hanno il flag**. b43 aveva ereditato indirizzo e valore (412 su 412
identici) e perso la colonna. La cattura combacia col flag esattamente: 39 su 39, e i
4 registri in piu' vengono da altro codice. Lo stub da 54 che impianta il radio e' il
set `do_init` di **brcmsmac**, che e' piu' vecchio. `patches/b43/MESSAGES.md#0013`,
non provata su hardware. Vedi `docs/gap-inventory.md` 4h.

## Due blob, e quale usare

`wlDSL-3580_EU.o_save` e' wl 6.30.102.7 (DSL-3580L, da cui viene la cattura),
`wlD6220.o_save` e' wl 7.14.89.14. Tutti e 33 i simboli **dati** del 2057 rev5-8 hanno
size identica fra i due, `regs_2057_rev8` e' identica byte per byte. Differiscono tre
funzioni `wlc_phy_workarounds_nphy_gainctrl_2057_rev5/6/7`, e la `rev6` e' il corpo che
manca allo stub di b43: per quella **si legge il 6.30**, che e' il blob della cattura.
Il blob da' i nomi veri di brcmsmac: `a3` = `wlc_phy_papd_cal_gctrl_nphy` (2444 byte,
147 righe, il rapporto torna). `wlc_phy_papd_cal_nphy` (6088) e' `a2` **o** `a4`: hanno
279 e 276 righe, la size non le distingue, e `a2` per size non si trova. Vedi
`docs/blob-inventory.md`.

## Prossimo passo

1. `perical-ingresso` resta a 119 su 1402 con 885 divergenze: l'ordine d'ingresso e'
   a posto, quel che resta e' dentro la fase.
2. L'ordine dentro `rxiq-ingresso`: 306 su 1503, ma solo 182 op mancanti, quindi il
   contenuto c'e' e il problema e' dove sta.
3. L'init vero e proprio, il buco piu' grosso: 3099 op dopo #2172, e un terzo e'
   object memory. Guardare l'ordine prima di cercare codice mancante.
4. L'ACI scan, che e' una politica sopra il PHY e non una funzione da agganciare.
