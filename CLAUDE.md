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
`patches/mainline/`, trentasei compresse nel rollup di `patches/b43/`. **Niente ha
mai girato su hardware**: tutto è verificato riproducendo la cattura in un harness
che compila il vero `phy_n.c`.

## Setup, ogni volta

```sh
sh scripts/fetch-upstream-state.sh ~/src/linux      # sparse, ~60 MB, ATTENZIONE: master
cd ~/src/linux
for p in .../patches/mainline/*.patch; do git apply "$p"; done   # tutte e dodici
git apply .../patches/b43/rollup.diff                            # applica pulito
cd test && make KDIR=~/src/linux && make KDIR=~/src/linux warncheck
./phase_compare.py --vendor ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
```

**Quella prima riga senza secondo argomento prende `master`, non `848acc8ffe1b`**, e
lo script non sa prendere uno sha: `git clone --branch` vuole un nome di ref, e
`git fetch origin 848acc8ffe1b` **fallisce** perche' una want-line vuole 40 caratteri
e non 12 (`couldn't find remote ref`). Per l'albero pinnato la strada che funziona e'
il tarball, che l'abbreviato lo accetta, e la ricetta sta in testa allo script. Se si
misura su `master` i numeri sotto non hanno nessun motivo di tornare, e i riferimenti
`file:riga` sicuramente no.

`patches/mainline/` fa parte del baseline delle misure: senza quelle patch i numeri
sotto non tornano, e prima di cercare una regressione altrove si controlla che ci
siano. Il rollup vuole `mainline/` **prima** e non applica da solo, perche' non
contiene `0010` e `0022`: erano duplicati di due delle mainline. Il costo e' che
`check_patch_gating.py` da' un verdetto unico per tutto il rollup invece di uno per
patch; i tre punti non gateati e le loro dichiarazioni sono in testa a
`rollup.diff`.

`patches/b43/` e' **un file solo** finche' si costruisce: la serie si ridivide prima
di mandare qualunque cosa, e i messaggi delle trentasei patch stanno in
`patches/b43/MESSAGES.md`. Le citazioni per numero nei documenti e in
`phase_compare.py` risolvono contro quel file.

**Come ridividerla sta in `patches/b43/SERIES.md`**: otto serie per competenza, non
un thread da trentasei. L'ordine di `MESSAGES.md` e' quello di scoperta e non serve a
chi le deve rivedere. Li' stanno anche i sei punti dove due serie si contendono la
stessa funzione, misurati, e il peggiore e' `b43_nphy_txpwr_index` con quattro.

**La regola che rende quella divisione possibile e' una sola: un commit per patch, con
la sua voce di `MESSAGES.md` nello stesso commit.** Il confine per patch sta nella
storia, non in una directory di file che si desincronizzano — i ventisei file che
c'erano fino a `394c9e2` sono 718 righe dietro il rollup, ed e' peggio del non
averli. `scripts/patch-from-commit.sh` estrae la patch di un commit quando serve, e
`patches/b43/SPLIT.md` ha i numeri.

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

**Il verdetto e' la tabella per fase di `phase_compare.py`: 8895 op su 18923, il
47%.** Non il totale in blocchi contigui, che dice 21316 su 23060 (92%) e che **non
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
| `coeff-setup-2` | 1074 | **1062 99%** | `1062` |
| `recalc-txpower` (**phy_ops vera**) | 716 | **604 84%** | `604` |
| `pwr-setup` | 432 | **432 100%** | `432` |
| `idle-tssi` | 661 | 432 65% | `432 210` |
| `coda-idle-tssi` | 1140 | 432 38% | `432 334 161 88` |
| `cal-papd` | 2662 | 847 32% | `847 2x361 316 274` |
| `cal-tx-iqlo` | 1570 | 443 28% | `443 349 267 2x110` |
| `cal-rssi-2` | 960 | **960 100%** | `960` |
| `perical-ingresso` | 1403 | 575 41% | `575 409 401` |
| `cal-rx-iq` | 5728 | 531 9% | `531 528 2x527 2x524` |

**La run sbaglia in un verso, e la colonna blocchi c'e' per questo**: prende il
massimo, quindi una fase che ripete N volte la stessa sequenza non puo' superare
~1/N per costruzione, quanto bene la riproduca. E sono tutte le cal. `cal-rx-iq` e'
il caso limite: la run dice **9%** e la forma dice **`2x510 4x507`**, cioe' le sei
iterazioni dello sweep appaiate una per una; misurata da sola con il pavimento dei
piani al suo ingresso (`--global-run 14951 21136`) fa **5595 su 5728, il 98%**, e la
sotto-regione dello sweep (`15921 22246`) **5243 su 5917, l'89%**. Quella fase non e'
un buco.

Attenzione: una regione misurata da sola non e' un'altra vista dello stesso run, e'
un run **diverso** — `--global-run` riposiziona il pavimento dei piani al suo
ingresso. `cal-rx-iq` da sola fa 98% contro il 9% della run; `coeff-setup-2` da sola
fa **331 (31%)** contro 1062 (99%) nel run globale. Nessuno dei due e' sbagliato e
non sono confrontabili.

Il totale della global run **non si guarda**: l'assegnazione dei blocchi e'
esclusiva e golosa, quindi un blocco lungo altrove si porta via le op e il numero
oscilla su cambiamenti che migliorano soltanto. Il numero da guardare e' `up-ch1`.

Per regione, `--global-run 132 26100 --flow txpower --channel 1`. Il flow e' quello
che `up-ch1` dichiara e non `init`: con `init` il port si ferma a 4594 op, la
regione di init fa 4436 e le cinque regioni di calibrazione fanno **zero**, che non
e' una misura di niente (trappola 11).

| regione | record | op | appaiate | non conf. | su conf. | spostate | assenti |
|---|---|---|---|---|---|---|---|
| init vero e proprio | #132-10961 | 9696 | 8217 85% | **1180** | **96%** | 49 | 254 |
| cal PAPD (`a4`) | #10962-14092 | 2662 | **2644 99%** | 0 | 99% | 4 | 14 |
| cal RX IQ, ingresso | #14093-15920 | 1705 | 1696 99% | 3 | **100%** | 2 | 7 |
| cal RX IQ, sweep di gain | #15921-22246 | 5917 | **5888 100%** | 0 | **100%** | 3 | 26 |
| seconda cal RSSI | #22247-23771 | 960 | **960 100%** | 0 | **100%** | 0 | **0** |
| coda | #23772-26100 | 2128 | 1911 90% | **176** | 98% | 10 | 31 |
| **TOTALE** | | | | | | **68** | **332** |

**Le due colonne misurano due difetti diversi e servono entrambe.** `appaiate`
risponde a "in che ordine", e sull'init di un PHY l'ordine e' funzionale: le op vanno
nella sequenza che l'hardware si aspetta, non in una qualunque che tocchi le stesse
celle. `assenti` risponde a "ci sono", cioe' dove manca codice. Un'op **spostata** non
e' innocua: e' un difetto d'ordine, e va chiusa come gli altri.

Perche' `appaiate` valga qualcosa il suo conto deve essere **ottimo**, e con difflib
non lo era: vedi `lcsmatch.py`. Il conto di `assenti` non ritaglia il port, che non ha
numeri di record: guarda l'avanzo, cioe' le op del port che nessun blocco ha appaiato,
contate per stringa su tutto il flow, e le consuma.

`non conf.` sono famiglie che il port non ha modo di emettere, perche' l'harness
compila il PHY e non il core — `OBJ.*` (1286 nella finestra), `MAC.MCTRL`/`MHF`
(40), `TPL.RAMW` (19), `GPIO.OUT` (12) — e la object memory ha comunque
l'encoding non confrontabile di `o708`/`o70e`. Nelle quattro regioni di calibrazione sono **zero**: tutte e 1356
stanno nell'init e nella coda, dove il core lavora. Il totale in blocchi contigui
non le esclude, di proposito.

**L'init vero e proprio resta il residuo piu' grosso, e adesso si sa di quanto**:
delle sue op non appaiate, 64 il port le fa altrove e **254 non le fa affatto**. Sono
quelle 254 il posto dove cercare codice mancante. Il secondo e' lo sweep con 61, poi
la cal PAPD con 29 e la coda con 27; la seconda cal RSSI e' a **zero**. Le spostate
sono 201 in tutto e sono un difetto d'ordine, non un contorno.

Quanto vale il **buco singolo** piu' grande dentro l'init non lo dice nessuno
strumento: `--global-run` stampa le run piu' lunghe, non le distanze fra loro. Serve
per sapere dove stanno quelle 246.

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

Sui confini non resta niente da misurare, e i due numeri che stavano qui erano un
artefatto della regola delle ombre. Contati sui due lati con la regola a coppia: il
marcatore `PHY.WR 0x2c = 0xffff` fa **6 e 6**, e su `0xb0` i due lati sono identici
valore per valore — 16 `MOD 0x7`, 6 `MOD 0x4`, 16 `RD 0xdf7`, 6 `RD 0xdf4`. Non c'e'
nessuna coppia in piu' e nessuna lettura in piu'. Quel che resta su `0xb0` e'
l'**ordine**: in `rxiq-ingresso` il port riceve `0xdf7` dove il vendore ha `0xdf4` e
lo scambio si chiude undici posizioni dopo.

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
blocchi** su `up-ch1` fa 19454 su 23068; **la somma delle run** fa 8896 su 18923.

Il 47% delle run **non puo'** arrivare al 100% per costruzione: la run e' il *massimo*
blocco dentro la fase, quindi una fase che ripete N volte la stessa sequenza si ferma
a ~1/N. `cal-rx-iq` ne e' la dimostrazione: run 532 su 5728 (9%), forma `532 529 528
511`, cioe' tutte e sei le iterazioni appaiate a ~530 ciascuna. Quel numero e' un
rivelatore di regressioni, non un obiettivo.

Il **92% dei blocchi** ha un tetto vero, e si calcola. Le 1752 op non appaiate, per
famiglia:

| famiglia | op | portabile? |
|---|---|---|
| `OBJ.WR` + `OBJ.RD` | 1284 | **no**: 734 indirizzi distinti di object memory, 553 sopra 0x400. E' lo stato di MAC e ucode, e l'harness compila il PHY non il core |
| `PHY.RD`/`WR`/`MOD` | 309 | **si** |
| `TBL.WR`/`RD` | 60 | **si** |
| `RAD.*` | 30 | **si** |
| `TPL.RAMW`, `MAC.MCTRL`, `MAC.MHF`, `GPIO.OUT`, `CHANSPEC` | 69 | **no**, stessa ragione |

Quindi il raggiungibile e' **23068 - 1352 = 21716, il 94,1%**, e siamo a 21316:
restano **400 op portabili**, cioe' siamo al **98,2% del tetto**. Di quelle, **332
sono assenti e 68 spostate**: le prime sono codice che manca, le seconde ordine.
Per regione le assenti sono 254 nell'init, 31 nella coda, 26 nello sweep, 14 nella
cal PAPD, 7 nell'ingresso RX IQ e **0** nella seconda cal RSSI.

Dei **106** tratti non appaiati, `--global-run` stampa i piu' grossi per op
confrontabili, col taglio fra spostate e assenti:

| da record | conf. | spostate | assenti | scrivono | op nel tratto |
|---|---|---|---|---|---|
| #877 | 55 | 4 | 51 | **3** | 61 |
| **#4970** | 44 | 0 | 44 | **27** | 601 |
| **#203** | 27 | 0 | 27 | **10** | 27 |
| #25823 | 19 | 2 | 17 | 2 | 195 |
| **#10761** | 18 | **16** | 2 | 9 | 18 |
| #9727 | 6 | 5 | 1 | 4 | 6 |

La colonna `scrivono` dice quante op del tratto cambiano lo stato del PHY invece di
leggerlo, e serve a **capire** il tratto, non a decidere se portarlo: un blocco di
sole letture va portato comunque, perche' una read di un registro PHY non e' senza
effetti — vedi `#877`, che erano 3 scritture su 51 ed erano tutte da fare. Il tratto
piu' grosso che resta e' **#5004: 20 assenti, tutte e 20 scritture.**

Restano, in ordine di dimensione:

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

**80 op a #796: chiuse.** L'ordine fra aux ADC e sequenze RF era il punto, e la
risposta e' che il device fa la tx2rx due volte, la seconda dopo l'aux ADC. Voce sotto.

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

**Lo spur workaround era uno stub, ed era il primo buco dell'init: portato.**
`b43_nphy_spur_workaround()` apriva e chiudeva la parentesi di carrier search e in
mezzo non faceva niente. Il device li' fa qualcosa, a `#203-#234`, subito dopo la
scrittura di `0x3830` su `NDATAT_DUP40` che e' il sito di chiamata.

Il riferimento su un canale a 20 MHz e radio rev 8 non emette niente, ed e' per questo
che lo stub non si notava: `wlc_phy_adjust_rx_analpfbw_nphy` vale per phy rev < 7,
`adjust_min_noisevar` ha la lista vuota fuori dai canali 3-10 a 40 MHz, e
`adjust_crsminpwr` ripristina solo cio' che un aggiustamento precedente ha salvato.
Quindi la cattura e' l'unica voce, e le due catture concordano.

Cosa fa: lo stesso valore `0x1591` nei due registri `STRA_2U`/`STRA_2L`, poi una
rilettura — una coppia di celle della tabella 7 a `0x106`, e poi **due volte** tre
celle della tabella 0 a `0x0b`, `0x13`, `0x23` e il registro `TRLOSS` (`0x169`). I
valori si buttano, e non e' una ragione per togliere le letture.

Vale **54 op**: le 27 del suo tratto e 27 piu' avanti che erano spaiate solo perche'
l'allineamento aveva slittato. L'init da 8297 a **8351** appaiate e le sue assenti da
183 a **129**, il totale delle assenti da 261 a **207**, i blocchi da 21396 a
**21450** e a freddo da 21257 a **21299**. `MESSAGES.md#0031`. Nota: `docs/gap-inventory.md`
resta com'e', perche' quella tabella e' misurata sul tree **pristine** e lo stub la'
c'e' ancora — e' il rollup che lo riempie.

**Il tratto a #10714: b43 lascia acceso l'override lpf, una volta per init.** Non sono
quattro op di trace, e' uno stato che resta nell'hardware. Contati sui due lati:

| | vendore | port |
|---|---|---|
| accende il bit di override (`0x342`, `0x80`) | 9 | 9 |
| spegne il campo di banda (`0x340`, `0x700`) | **9** | **8** |
| spegne il bit di override (`0x342`, `0x80`) | 5 | 4 |

Nel vendore accensioni e spegnimenti del campo si appaiano uno a uno:

    on  1641  8629 11764 12878 15056 15060 18136 18140 24292
    off 1714 10715 12871 13839 15057 15061 18137 18141 24365

La coppia lunga e' `8629 -> 10715`: l'override acceso da un sample play resta su per
tutta la cal TX I/Q LO e viene spento solo al confine della cal PAPD. Il port ne perde
esattamente uno, quindi **un'accensione senza spegnimento**.

La causa e' la contabilita': `lpf_bw_overrode_for_sample_play` e' un **bool**, e
`b43_nphy_run_samples()` lo mette a vero solo `if (!(lpf_bw3 | lpf_bw4))`, cioe' solo
se l'override non era gia' acceso. Il primo `b43_nphy_stop_playback()` che passa lo
consuma e lo azzera, e l'accensione di un play successivo resta senza proprietario.
Il device invece spegne una volta per accensione, nove e nove.

**Chiuso, e il contatore non era la strada.** Guardando i record fra `8629` e `10715`:
c'e' **un solo** `stop_playback`, a `#10693`, e l'override gli sopravvive — viene spento
21 record dopo, in coda al resto del cleanup. Quindi quell'override non e' del sample
play: e' della **cal TX I/Q LO**, acceso da `b43_nphy_tx_cal_phy_setup()`, e nessuno lo
spegneva. Il bool di `stop_playback` va bene per l'override che quella funzione possiede
davvero; questo dura piu' di diversi play.

Spento alla fine di `b43_nphy_tx_cal_phy_cleanup()`, dove finisce il suo proprietario.
Ora sono **nove e nove** su entrambi i lati, l'init passa da 8416 a **8420** appaiate e
le sue assenti da 66 a **62**, i blocchi da 21525 a **21529**. `MESSAGES.md#0036`.

E la sequenza del port lo diceva, contata sulle op normalizzate: `ON@6925` con
`stop@8409` e nessun `off`, mentre le altre otto coppie si chiudevano tutte.

**Il tratto a #5004: e' l'ACI scan, e sta sopra il PHY.** Le sue 20 op confrontabili
stanno a `#5614-#5633` e sono un **applica-e-ripristina** dei gain e delle soglie CRS:
`0x20`/`0x2a7` a `0x7e`, `0x21`/`0x2a8` a `0x624`, `7/0x106` a `0x623f`, `0x280`/`0x283`
mascherati a `0x44`, `0x2e6` a `0x4477`, `0xc33` a `0x10`, e poi di nuovo `0x283`,
`0x280`, `7/0x106` e `0x21`/`0x2a8`.

**Diciotto su venti sono idempotenti**: quei valori sono esattamente quelli che i
registri hanno gia', letti a `#884-#896` — `0x7e`, `0x624`, `0x3644` la cui parte bassa
e' `0x44`, `0x623f` — e riletti identici a `#26077-#26087`. Le due che non si possono
verificare sono `0x2e6` e `0xc33`, senza nome ne' qui ne' nel riferimento e mai lette
nella cattura.

**Non e' portabile dentro `phy_n.c`**, e non e' una scusa: quel blocco sta fra op che il
port non emette affatto — la pulizia della SHM a `#5600-#5612` e una `MAC.MHF` — e
prima del setup del chanspec. Cioe' viene da **sopra il PHY**, come l'ACI scan, ed e'
la sua prima comparsa dentro l'init. L'harness compila il PHY e non il MAC, quindi da
qui non si puo' nemmeno misurare. Stessa voce dell'ACI scan.

**I tratti a #4958 e #6330: mezzi chiusi.** Sono lo stesso blocco di quattro op due
volte, ed e' `b43_nphy_tx_power_ctrl()` sul ramo che **accende**: il device azzera i due
bit di abilitazione (`0xc000` = `HWPCTLEN|PCTLEN`, lasciando `COEFF`), rimette i due
indici, e **poi** accende tutti e tre (`0xe000`). b43 accendeva prima e rimetteva gli
indici dopo, quindi il controllo girava con gli indici vecchi per due scritture.

Riordinato: le due op sui bit ora combaciano. Le due scritture degli indici no, e per
due ragioni insieme — sono gateate su `tx_pwr_idx != 128`, e i valori che b43 ha la'
sono `0x19` dove il device scrive `0xa` e `0xc`. **Quella e' una domanda su cosa
conserva il salvataggio dell'indice**, non su dove sta l'op. Vale assenti da 138 a
**135** e blocchi da 21522 a **21525**. `MESSAGES.md#0035`.

**Il tratto a #3732: localizzato, non chiuso.** E' **una** lettura del gain corrente
(`TBL.RD 7/0x110 len=2`) che il vendore fa fra `restore_rssi_cal` e
`tx_pwr_ctrl_coef_setup` — la lettura della tabella 15/80 di `#3738` e' la prima op di
`coef_setup` — e che b43 fa **prima**. I conteggi combaciano, **nove e nove**, quindi
e' ordine e non codice mancante: otto delle nove si appaiano al record esatto, e solo
la prima e' in ritardo di ~1000 record.

Chi la fa, con `B43_TEST_TBLDBG=7:110`: sette dalle chiamate a
`b43_nphy_int_pa_set_tx_dig_filters()` (`phy_n.c:5549`), una da
`run_pending_perical()` (`7777`), una da `5958` e una da `6708`. Quella in ritardo e'
la prima delle sette, e in `b43_phy_initn` l'ordine e'
`int_pa_set_tx_dig_filters` (che legge) → `restore_rssi_cal` → `coef_setup`, dove il
vendore ha `restore_rssi_cal` → legge → `coef_setup`.

**Non l'ho spostata**, e la ragione e' che dentro `int_pa_set_tx_dig_filters` quel
valore **si usa**: `curr_gain` diventa `target` per le tre righe di filtri. Spostare la
lettura vuol dire cambiare quale gain quella funzione vede, e non ho una fonte che dica
che il vendore la legge due volte o che la usa altrove. Quattro op, e per muoverle
serve capire chi consuma il valore nel vendore.

**`tssi-setup` chiusa, 19 su 19, e dentro c'era un valore sbagliato.** Due cose, a
`#1251-#1281`.

La prima: `b43_nphy_ipa_internal_tssi_setup()` scrive sette registri radio per core, e
il device **ne rilegge quattro prima** — `r+8`, `r+9`, `r+0xB`, `r+0xA` in quest'ordine,
una volta per core, a `#1251-#1257` e `#1266-#1272`. Aggiunte.

La seconda e' piu' di un'op fuori posto. Sul percorso 2 GHz b43 scrive **1** nel
registro TSSI di banda G di ogni core per ogni phy rev diversa da 7, e `0x31` per la 7.
E' trascritto giusto dal riferimento (`phy_n.c:17075-17080`). **Il device non fa
nessuna delle due**: legge quel registro, trova `2`, e lo lascia — in `#1259-#1281` non
c'e' nessuna `RAD.WR 0x17b` ne' `0x19b`, e il `2` e' ancora la' quando la cal TX I/Q LO
mette `0x31` a `#8537` e rimette `2` a `#10743`. Quindi non e' ordine: e' un **valore
sbagliato lasciato nella radio per tutto l'init**, e la cattura e' l'unica voce contro
il riferimento. Scrittura gateata via sul radio rev 8.

Vale l'init da 8406 a **8414** appaiate e le sue assenti da 76 a **68**, il totale delle
assenti da 154 a **138**, i blocchi da 21505 a **21521**. E le finestre con divergenze
dichiarate scendono da **sei a cinque**. `MESSAGES.md#0033` e `#0034`.

**Il tratto a #877: portato.** Sono 61 op, `#877-#987`, in coda ai workaround fra la
seconda passata della tx2rx e l'impulso `BBCFG RESETCCA` di `#988`, e il port non
emetteva **niente** li': andava da `#876` a `#988` di fila.

Ogni registro letto e' uno che `gain_ctl_workarounds()` e le tabelle di gain hanno
appena **scritto**: i quattro gain iniziali e le soglie di clip per core, le soglie
narrowband, i due `CRSMINPOWER`, le dodici soglie `ED_CRS` (`0x224`-`0x22f`), due
blocchi della tabella 4 e i registri master e RSSI IDAC su entrambi i core radio.
Rileggere quello che si e' appena programmato e' cio' che fa un driver prima che
qualcosa possa cambiarlo, e quel qualcosa qui e' l'**ACI scan**, che la cattura fa
dopo e che questo driver non ha.

I valori si buttano, e non e' una ragione per saltare le letture. **Fuori dalla patch
di proposito**: la lista in SHM a `0x1570`-`0x1576` che dichiara `0x8f`, `0xa6`,
`0xa5`, `0xa7` all'ucode, e un bit nella parola 4 degli hostflag. Quel bit non ha nome
ne' in b43 ne' nel riferimento, e accendere un flag dell'ucode senza nome sulla sola
fede di una cattura sarebbe una congettura sul firmware.

Vale l'init da 8351 a **8406** appaiate, cioe' il **99%** delle confrontabili, e le
sue assenti da 129 a **76**; il totale delle assenti da 207 a **154**, i blocchi da
21450 a **21505** e a freddo da 21299 a **21350**. `MESSAGES.md#0032`.

**Il tratto a #796: chiuso, ed erano 80 op su 122.** Non erano le otto maskset a
mancare — quelle c'erano gia', **nella passata sbagliata**. Il device programma la
sequenza RF **tx2rx due volte**, con gli stessi sette eventi e gli stessi ritardi:
la prima a #390-#420 e la seconda a #796-#874, questa preceduta dalle otto maskset su
`AFECTL_C1`/`C2` e dalle tabelle dell'ADC ausiliario a #771-#789. Contate su tutta la
finestra: il device scrive `7/0x10`, `7/0x90` e le nove celle di padding **due volte**,
b43 una. I valori sono identici fra le due passate e fra i due lati, ed e' per questo
che uscivano come op **mancanti** e non come valori sbagliati.

Ne' b43 ne' il riferimento avevano la seconda passata. Aggiunta in coda a
`b43_nphy_workarounds_rev7plus()`, dopo le tabelle dell'ADC, con le maskset spostate
la' dalla prima passata dove non ci vanno. Vale l'init da 8217 op appaiate a **8297**
e le sue assenti da 254 a **183**, il totale delle assenti da 332 a **261**, i blocchi
da 21316 a **21396** e a freddo da 21177 a **21257**. `MESSAGES.md#0030`.

Quel che resta di quel tratto e' un'altra cosa e comincia a **#877**: 51 op assenti,
le letture appaiate di `0x20`/`0x2a7`, `0x21`/`0x2a8`, `0x22`/`0x2a9` e le quattro
`OBJ.WR` a `0x1570`-`0x1576` che dichiarano all'ucode i registri `0x8f`, `0xa6`,
`0xa5`, `0xa7` — cioe' la lista della tempsense. E' il buco piu' grosso che resta.

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

- **`rxiq-ingresso`, 510 su 1510 con 57 divergenze, e sono tre gruppi tutti
  attribuiti.** Sei sono la rilettura a 9 bit delle tabelle 26/27 oltre l'offset 576,
  a `@31`, `@434` e `@947` con la word alta accanto. Due sono su `0xb0`, dove i
  conteggi combaciano e cambia solo l'ordine. Le altre **49 sono un solo sfasamento
  di due**: a `@1459` il vendore legge `0x340` e `0x341` e il port li' non li legge;
  da `@1461` le due sequenze sono le stesse, spostate di due. Quelle due op sono
  identificate e **chiuse**, voce sotto.

- **Le due letture di `0x340`/`0x341` in `run_samples`: chiuse.**
  `b43_nphy_run_samples()` sul ramo `rev >= 7` leggeva `0x342` e `0x343` per i bit di
  override lpf e si fermava li'. Il riferimento ne legge altre due e butta via entrambi
  i valori — `read_phy_reg(pi, 0x340)` e `(pi, 0x341)`, `phy_n.c:23109` e `23110`, col
  commento `lpf_bw_ctl_miscreg3/4` — e la cattura fa lo stesso: delle 28 letture di
  `0x340`, **22 sono precedute esattamente da `RD 0x342`, `RD 0x343`**, cioe' ogni
  sample play. Le altre sei sono altri due siti che b43 ha gia'. Il valore buttato non
  autorizza a togliere la lettura: una read di un registro PHY non e' senza effetti.

  Aggiunte (rollup, `MESSAGES.md#0027`): `rxiq-ingresso` da 57 divergenze a **37** e
  run da 510 a 532, `cal-rssi-2` a **960 su 960**, `idle-tssi` da 357 a 432, run per
  fase da 8779 a **8896**.

  Il crollo dei blocchi che questa modifica sembrava causare — 21110 a 19454, lo sweep
  da 5784 appaiate a 4112 — era **difflib**, non l'ordine: vedi `lcsmatch.py`. Con
  l'appaiamento ottimo lo sweep sta a **5798** e `up-ch1` a **21140**, cioe' 30 op
  meglio di prima della modifica. Il diff dei due trace del port lo diceva gia': 51
  righe, 26 op aggiunte e **quattro** righe di comportamento diverso.

- **difflib non cercava la sottosequenza comune piu' lunga, e per un anno il conto
  per blocchi ha detto numeri falsi: chiuso.** `SequenceMatcher` cerca il blocco
  contiguo piu' lungo e poi ricorre a destra e a sinistra. Sulla cal RX IQ, che ripete
  sette volte una sequenza quasi identica, il primo blocco che aggancia puo' essere
  l'iterazione sbagliata, e da li' un'iterazione intera resta spaiata su entrambi i
  lati. Misurato: su `up-ch1` difflib appaia **19454** op dove l'ottimo ne appaia
  **21140**, cioe' ne lascia **1686** sul tavolo.

  `lcsmatch.py` fa l'appaiamento ottimo: LCS bit-parallel per le lunghezze e
  Hirschberg per l'allineamento, 0,4 s su `up-ch1`. Il bitvector che esce da una
  passata di LCS codifica le lunghezze su tutti i prefissi del secondo argomento,
  quindi la riga che Hirschberg legge costa una passata sola. I suoi test verificano
  tre cose: le lunghezze contro una DP ingenua su tutti i prefissi, che i blocchi
  siano un allineamento **valido** — monotono, e con le op che combaciano davvero,
  perche' un allineamento lungo e sbagliato e' peggio di uno corto — e che non sia mai
  peggio di difflib.

  Cosa cambia, con lo stesso driver e la stessa cattura:

  | | difflib | ottimo |
  |---|---|---|
  | `up-ch1`, blocchi | 19454 (84%) | **21140 (92%)** |
  | `up-ch1-freddo` | 19867 (72%) | **21011 (76%)** |
  | sweep della cal RX IQ | 4112 (69%) | **5798 (98%)** |
  | `cal-rx-iq`, forma | `532 529 528 511` | `531 528 2x527 2x524` |
  | buchi contigui | 120 | 114 |
  | op portabili non appaiate | 2262 | **576** |

  La forma di `cal-rx-iq` e' la firma: sei iterazioni appaiate a ~527 ciascuna, che e'
  quello che una fase che ripete sei volte deve dare. Con difflib erano quattro
  numeri sopra 500 e due iterazioni sparite.

- **La deroga su `PHY.CLK` adesso e' applicata, non solo dichiarata.** Il ragionamento
  che la giustifica sta nella lista delle deroghe piu' sotto: `b43_phy_force_clock()`
  e' `phyclk_fgc`, il tracer aggancia `core_phy_clk`, quindi quelle op non sono
  osservabili e nelle due catture della DSL-3580L sono **zero**. Restava pero' dentro
  il flusso del port, e li' faceva danno: il confronto per finestra e' posizionale,
  quindi una sola op che un lato non puo' avere sfasa di uno tutto quello che segue.
  Toglierla dal lato port — `PORT_UNSHOWABLE` in `compare.py`, il simmetrico di
  `NOT_COMPARABLE` — vale `perical-ingresso` da 13 divergenze a **5** e
  `rxiq-ingresso` da 492 a **57**. Il denominatore non si tocca: il danno non era la'.

  Se un giorno si misura contro `router-data/vd630/fullinit.txt`, attenzione: la' due
  `PHY.CLK` ci sono, entrambe `val=0x1`, e vengono dall'altra funzione. Lo stesso nome
  copre due cose e vanno separate prima.

- **L'ombra di una `MOD` e' una coppia, e va riconosciuta come coppia: chiuso.**
  `drop_rmw_shadows()` riconosceva l'ombra dal solo prefisso e si mangiava una **run**
  intera di `RD` sullo stesso indirizzo, quindi cancellava tutte e 110 le letture del
  poll di `0x129` (`IQEST_CMD`), che stanno a valle della `MOD` che accende il
  comando, e le sei `RD 0xb0` che sono il read della **seconda** chiamata a
  `b43_nphy_classifier()` dentro `stay_in_carrier_search()`. Il port quelle letture le
  fa, e restavano senza controparte.

  La lettura interna di una read-modify-write non arriva mai da sola: se il tracer
  registra la read registra anche la write. Quindi una `RD` che segue una `MOD` senza
  una `WR` dietro e' un'op vera. Su `up-ch1` la vecchia regola scartava 175 op in run
  di lunghezza `1x6 2x28 3x1 5x1 6x5 27x1 48x1`: le run da 1 e da 2 erano ombre vere,
  le altre 113 no.

  Cosa e' cambiato: `up-ch1` da 22951 a **23068** op del vendore, e le letture visibili
  di `0xb0` da 16 a **22**, che e' il numero vero della cattura. `perical-ingresso` da
  17 divergenze a **13**, `rxiq-ingresso` da 555 a **492**, la run di `idle-tssi` da
  334 a **357**. Nessuna finestra si e' aperta.

- **Il piano di lettura di `0x129` e' fuori fase, e la regola delle ombre lo nascondeva.**
  Il vendore chiude ogni poll leggendo **due volte** il valore con START spento — 8
  stime su 8: quattro `1 1 1 1 0 0`, una `1 1 1 16 16`, una `1 1 1 1 32 32`, una da 48
  e una da 27. Il riferimento ne fa **tre**, di letture in coda: `SPINWAIT`
  (`phy_n.c:26050`), la `WARN` (`26052`) e l'`if` che apre la lettura degli
  accumulatori (`26056`); la cattura ne ha due, quindi il wl 6.30 non ha la `WARN`.
  b43 ne fa **una**, che gli serve sia da test d'uscita sia da guardia.

  Il piano e' una coda per indirizzo, quindi la voce di troppo non la consumava
  nessuno e se la prendeva la chiamata dopo, che uscisse al primo giro:
  `B43_TEST_PLANDBG=1` dava 65 letture in 8 chiamate, forme `5 1 5 1 4 1 47 1`, con le
  entry consumate tutte dentro le **prime quattro** stime del vendore. Le chiamate
  pari non aspettavano niente.

  Non era l'invariante del banco a cedere: `wrap.c` la dichiara per indirizzo, e dice
  che se il port salta una lettura i valori di quell'indirizzo si sfasano di uno. Qui
  il port non saltava niente: e' il vendore che ne fa una in piu' **per forma del
  sorgente**, e b43 non ha modo di consumarla. Lo sfasamento era quindi strutturale e
  cresceva di uno per stima.

  **Chiuso in `gen_readplans.py`, con una lista dichiarata**: `POLL_DOUBLE_TAIL` tiene
  i registri di comando la cui fine il sorgente del vendore legge due volte, e oggi ha
  una riga sola, `PHY 0x129`. Una regola generale non si puo' dedurre dalla cattura, e
  ci ho provato: "togli la coda duplicata di ogni poll" tocca anche `0x21a` e `0x219`,
  che nella seconda cal RSSI sono **otto campionamenti uguali di fila** e non un poll,
  e affamerebbe il loro piano di 416 voci. `PHY 0x0c0` (`IQLOCAL_CMD`) invece non ci
  va e la ragione e' misurata: i suoi 24 gruppi finiscono col valore che cambia una
  volta sola (`0x8434 0x8434 0x8434 0x434`), quindi b43 e il vendore ne fanno lo
  stesso numero.

  Il piano perde 8 voci su 110 e il poll torna in fase: 102 letture in 8 chiamate,
  forme `5 5 4 47 5 5 5 26`, cioe' una per stima e ciascuna una lettura meno del
  vendore, che e' esattamente giusto. Vale lo sweep da 5798 appaiate a **5882**, le
  sue **spostate da 58 a 11** e le **assenti da 61 a 24**, il totale delle spostate da
  201 a **153** e delle assenti da 375 a **339**, `up-ch1` da 21140 a **21224** e a
  freddo da 21011 a **21093**. Il buco da 47 op portabili a #17913 non c'e' piu'.

  I dodici accumulatori (`0x12c`-`0x131`, `0x134`-`0x139`) erano **8 e 8 su tutti e
  dodici** anche prima, quindi i valori della stima erano quelli della cattura: era
  falsa l'attesa, non la stima.
- **`perical-ingresso` e' chiusa**: 575 su 1402 con 17 divergenze dichiarate.
- **Resta una voce piccola**: le due `PHY.MOD 0x349 val=0x0 mask=0xf` a #13320 e
  #13392 che il port non emette mai — la maschera a 4 bit e' il campo `0x2000` da
  solo, la voce `(0x1 << 13)` della tabella di override rev 7.
- **Metà della cattura non è confrontata con niente, e ora si sa cosa contiene.**
  La cattura arriva a **#70796** e `up-ch1` misura `#132-26100`. La struttura, contata
  sui marcatori `CHANSPEC`:

  | | record | cosa |
  |---|---|---|
  | `#132` ch=1 | 25969 | l'init, cioe' `up-ch1` |
  | `#26101`-`#34937` | 8837 | 14 salti dell'ACI scan, ch1↔ch5 ogni 2 s |
  | `#34938` ch=6 | **27034** | il cambio canale e cio' che segue |
  | `#61972`-`#70796` | 8825 | 15 salti dell'ACI scan, ch6↔ch2↔ch10 |

  Non e' "ch1 poi ch6": e' init, scan, cambio, scan. Del blocco da 27034 record ne
  confrontavamo **42 op**, quelle di `chanswitch-ch6`. E quel blocco non e' un cambio
  canale: entro **1,45 s** dal cambio il vendore rifa' la calibrazione da zero —
  `IQLOCAL_CMD` a #43852, i sample play a #43366, le stime I/Q a #51744 — un blocco
  grande come l'init.

  **E quel blocco e' un init da capo.** La sottosequenza comune piu' lunga fra
  `#132-26100` e `#34938-61971` e' **22308 op su 23649, il 94%**: al cambio canale il
  device rifa' la stessa sequenza dell'init, sul canale nuovo.

  **Chi la chiama in b43 non c'e', e non e' un refuso.** Il blocco `do_cal` /
  `deferred_cal` sta in **`b43_phy_initn()`**, non nel percorso del cambio canale:
  `b43_nphy_set_channel()` passa da `b43_nphy_channel_setup()`, che di calibrazione
  non ha niente. Quindi `op_switch_channel` emette **60 op** e non puo' emetterne
  altre. E la condizione `do_cal = !nphy->iqcal_chanspec_2G.center_freq` e' **identica**
  al riferimento (`wlc_phy_init_nphy`, `phy_n.c:19483`), quindi non c'e' niente da
  correggere li': nel riferimento la ricalibrazione arriva dal **watchdog**,
  `wlc_phy_cal_perical(PHY_PERICAL_WATCHDOG)` sotto `glacial_timer`
  (`phy_cmn.c:2278`), e b43 non ha l'equivalente.

  Conseguenza sull'hardware, non sul banco: **b43 rimette su ch6 la calibrazione TX
  I/Q LO e RX I/Q fatta su ch1**, dove il device ricalibra da zero.

  **Provato separatamente, il codice della calibrazione il canale nuovo lo sa fare.**
  `flow_chancal` fa l'init a caldo, cambia canale e rifa' l'init: e' una manovra del
  banco — le chanspec di cal azzerate come fa `flow_init` prima dell'init tracciato —
  e serve a separare "il codice sa" da "qualcuno lo chiama". Misurato:

      ./phase_compare.py --vendor .../opinit-ch1-ch6-bw20.decoded \
          --global-run 34938 61971 --flow chancal --channel 6
      -> 21593 su 23649, il 91%

  cioe' quanto `up-ch1`. La superficie misurata del repo raddoppia.

  Due cose sono servite per arrivarci, ed erano entrambe trappole del banco. **I piani
  di lettura finivano con `up-ch1`**: senza quelli del range nuovo ogni attesa cade sul
  mirror e gira fino al suo limite — misurato, 181338 letture di `0x2be` in un solo
  poll della cal PAPD e quattro milioni di op in tutto. Ora `gen_readplans.py` sa fare
  set con nomi diversi (`--name ch6` -> `b43_test_load_readplans_ch6()`) e c'e'
  `readplans_ch6.h`. E **`--max-len` tronca**: con 512, `0x2be` ne perdeva 466 su 978 e
  il poll girava a vuoto comunque. I piani di `up-ch1` non erano troncati, quel range
  sta sotto 512.

  I due blocchi **non sono finestre**, e non per dimenticanza: 23649 e 29979 op contro
  46307 e 55304 del port costano minuti a `lcsmatch`, che e' O(n*m/64) per livello di
  Hirschberg. Si misurano con la global run, e i due comandi stanno nel commento nel
  punto della tabella dove le finestre sarebbero andate.

  E `flow_full` era costruito su `initcal` invece che sull'init a caldo, quindi non si
  confrontava con questa cattura, e nessuna finestra lo usava. Ora e' `flow_txpower`
  piu' il cambio canale, cioe' `op_init` fino alla fine di `op_switch_channel`, e resta
  a 60 op perche' quello e' quanto b43 fa davvero.

  **Anche la cattura a freddo ha lo stesso blocco, e adesso e' misurato.**
  `full-init-*` ha `#339` ch=1, poi `#98383` ch=**11** per **34738 record**, poi i
  salti ACI ch7↔ch11. Il buco da 65286 record fra `#32769` e `#98055` e' il giro del
  buffer del tracer, quindi il blocco ch11 e' dati buoni. Ed e' init anche lui: LCS con
  l'init a freddo troncato **26521 su 29979, l'88%** (col caldo su ch1 il 75%, che dice
  che il freddo assomiglia piu' al freddo). `flow_chancalpor`, base `flow_initpor`,
  piani `readplans_ch11.h`:

      --global-run 98383 133120 --flow chancalpor --channel 11
      -> 25526 su 29979, l'85%

  Piu' del 76% dell'init a freddo, che ha dentro la roba del power-on che il banco non
  fa.

  **Le due basi c'erano gia' e sono quelle che le finestre usano**: `flow_txpower` per
  la cattura a caldo, `flow_initpor` per quella a freddo. Cio' che mancava era un set
  di piani di lettura per range, uno per cattura, e `flow_chancal_from()` che prende
  base e piani come parametri. I due flow sono tre righe a testa.

  **Quanta cattura e' dentro un range confrontato, contando i record che esistono:**

  | cattura | record presenti | prima | ora |
  |---|---|---|---|
  | `opinit-*` (caldo) | 59693 | 23211, 39% | **47003, 79%** |
  | `full-init-*` (freddo) | 69557 | 28401, 41% | **59127, 85%** |

  Il resto sono i salti dell'ACI scan, che e' una politica sopra il PHY.

- **Le 75 op spostate della cal PAPD sono UNA commutazione di troppo del controllo
  di potenza.** Non sono sparse: quattro sono `PHY.MOD 0x2a3`/`0x2a4 val=0x3 mask=0x7`
  isolate (#12220, #12354, #13334, #13406), le altre **71 sono un blocco contiguo**,
  `#13842-#13918`, che il port emette tutto insieme e nell'ordine giusto — le letture
  `PAPD_STAT`, i `PAPD_EN`, le maschere sui `CAL_SHIFTS`, la `BBCFG` e le tre righe dei
  filtri, cioe' la coda di `b43_nphy_papd_cal()` (`phy_n.c:7340-7353`).

  Di quanto e' fuori posto: l'appaiamento prima di quel blocco ha scostamento **-23**,
  dopo **-94**, e il port lo emette a `@12267` dove lo scostamento precedente lo
  metterebbe a `@12091`. **176 op tardi**, e in mezzo il port ne infila 176 che
  cominciano con `PHY.RD 0x1e7` e `TBL.WR id=0x1a off=0x40 len=84`.

  Il conto torna esatto. Una `TBL.WR` da 84 celle si srotola sulla porta delle tabelle
  in **86 op** (`0x72` con l'indirizzo, poi 84 `0x73`, piu' la `TBL.WR` stessa), e il
  controllo di potenza le scrive **a coppie**, tabella 26 e tabella 27:
  `86 + 86 + 4 = 176`. Non e' un blocco di lavoro: e' **una sola** commutazione del
  controllo di potenza in piu'.

  Chi le scrive e' `b43_nphy_tx_power_ctrl()` (`phy_n.c:3766`): zeri quando spegne
  (`3802`), `adj_pwr_tbl` quando accende (`3827`), su entrambe le tabelle. Ha nove
  chiamanti, e dentro la calibrazione ogni fase spegne e riaccende. Contate le
  scritture di `26/0x40` su `#132-26100`: il port ne fa **43**, il vendore **36**, e
  tutte e sette le in piu' cadono nella regione di cal.

  Quindi "75 op spostate nella cal PAPD" si riduce a **sette commutazioni di troppo del
  controllo di potenza durante la cal**, una delle quali si mette fra il blocco
  precedente e la coda della `papd_cal`. Trovare quale dei nove chiamanti le fa vuole
  un contatore per sito, che non c'e'.

- **Le sette riprogrammazioni di troppo della tabella di potenza: chiuse.**
  Trovate con `B43_TEST_PWRCTLDBG=1`, che nel wrap di `b43_ntab_write_bulk()` stampa il
  `backtrace()` di ogni scrittura di `26/0x40` da 84 celle. Gli offset si risolvono con
  `addr2line -f -e nphy_trace`. Delle 43 del giro tracciato:

  | scritture | sito che commuta il controllo |
  |---|---|
  | **24** | `b43_nphy_txpwr_index()`, il suo spegni/riaccendi interno (`4038` e `4107`) |
  | 10 | `b43_nphy_pwr_ctl_open`/`close()` dentro `b43_nphy_papd_cal()` |
  | 3 | `b43_phy_initn()` |
  | 2 | `b43_nphy_op_recalc_txpower()` |
  | 2 | `run_pending_perical()` e `cal_perical_phyinit()` |
  | 2 | `b43_nphy_txpwr_index()` a `4005` |

  Ogni sito e' in parentesi perfetta, spegni e riaccendi: `gainctrl` ne apre **sei**,
  non dodici. Le dodici sono le *scritture*, due per parentesi, e distinguere le due
  cose e' cio' che serve per non sbagliare la conclusione.

  Non e' che b43 scriva dove il device non scrive: **anche il riferimento scrive gli 84
  zeri quando spegne** (`wlc_phy_txpwrctrl_enable_nphy`, ramo `PHY_TPC_HW_OFF`), e il
  commento a `phy_n.c:3796` lo dice gia'. La differenza e' **quante volte** si commuta,
  e adesso si sa dove, perche' le scritture del port si attribuiscono alle regioni
  passando dall'appaiamento: quelle dentro un blocco appaiato hanno il record del
  vendore esatto, non stimato.

  | regione | vendore | port |
  |---|---|---|
  | init | 13 | 13 |
  | **cal PAPD** | **1** | **8** |
  | ingresso RX IQ | 7 | 7 |
  | sweep RX IQ | 9 | 9 |
  | seconda cal RSSI | 0 | 0 |
  | coda | 6 | 6 |

  **Tutte e sette le scritture di troppo stavano nella cal PAPD, e nessun'altra regione
  ne aveva una di scarto.** Il device fa quella calibrazione riprogrammando la tabella
  di potenza aggiustata **una volta sola**, alla fine; b43 la riprogrammava otto, con
  le quattro parentesi di `pwr_ctl_open`/`close` — una per passata, due per catena — e
  quelle interne di `txpwr_index`.

  **Chiuso**: una parentesi sola attorno a tutta la calibrazione, aperta prima del
  ciclo per catena e chiusa dopo le righe dei filtri, che e' dove il device scrive la
  tabella (#13921, subito dopo che le righe finiscono a #13918). Le passate il
  controllo spento lo hanno ancora, e le parentesi interne diventano innocue da sole:
  il ramo che spegne tocca la tabella **solo se il controllo e' davvero acceso**
  nell'hardware, quindi trovano i bit gia' spenti e non emettono niente.

  Vale: la cal PAPD da 2573 op appaiate a **2644 su 2662**, le sue **spostate da 75 a
  4**, lo sweep al **100%**, il totale delle spostate da 153 a **76**, i blocchi
  contigui da 21239 a **21316**, i buchi da 112 a **105**. `MESSAGES.md#0029`. Le
  assenti non si muovono, ed e' il punto: cambia **quando** il driver fa una cosa, non
  se la fa.

  E cade il commento a `phy_n.c:7303`, che diceva che nella cattura ogni parentesi
  aperta e' cio' che permette alla chiusura di riprogrammare la tabella, citando
  quattro aperture a #12197, #12331, #13311, #13383: le aperture ci sono, ma non
  riprogrammano niente. Resta **una** scrittura di scarto nella cal PAPD, 2 contro 1.

- **La riscrittura della riga 1 dei filtri TX: chiusa per il rev 8.**
  `b43_nphy_int_pa_set_tx_dig_filters()` scrive le prime tre righe di
  `tbl_tx_filter_coef_rev4` su `0x186`, `0x195` e `0x2c5`, quindici registri per
  riga, e poi riscrive la riga 1 su `0x195` una seconda volta **solo** se
  `phy.rev == 17`. Questo device e' rev 8 e lo fa: nella cattura i gruppi su `0x195`
  sono **quattro** contro tre di `0x186` e due di `0x2c5` — `#304` e `#334` all'init,
  `#13874` e `#13904` in coda alla cal — e i quindici valori sono **identici** nei
  quattro. Contati sui due lati: `0x186` 45 e 45, `0x2c5` 30 e 30, `0x195` 60 e 30.

  E' idempotente, quindi lo stato dei registri non cambia; il difetto e' la
  **forma**. Le tre righe sono un blocco unico di quarantacinque scritture, e
  quindici mancanti nel mezzo fanno cadere fuori posto tutto quello che segue. Con la
  riscrittura la finestra `txdigi-filts` passa da "mancano 15" a **60 su 60**, le
  finestre con divergenze dichiarate scendono da 7 a **6**, l'init guadagna 15 op
  appaiate e le assenti totali scendono da 339 a **324**.

  Il gate e' la revisione su cui e' misurato. brcmsmac nel percorso a 20 MHz non
  scrive `0x195` due volte — `wlc_phy_ipa_set_tx_digi_filts_nphy` scrive le tre righe
  e basta — quindi la cattura e' l'unica voce, e non e' una voce su nessun'altra
  revisione.

  **Quello che resta** e' che nella cal PAPD le quindici op sono ora **spostate** e non
  appaiate: la seconda occorrenza, a `#13904`, e' agganciata all'altra. Le spostate
  della regione salgono da 60 a 75 e le assenti scendono da 29 a 14, cioe' il conto
  totale migliora ma la coda della cal ha un ordine suo, ancora da guardare.

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
| `up-ch1` | `opinit-*`, init a caldo | `txpower` | 23060 | **21316, 92%** |
| `up-ch1-freddo` | `full-init-*`, init completo | `initpor` | 27704 | **21364, 77%** |

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
    `RESET2RX` — quindi le `PHY.CLK` che il vendore non ha sono un buco del
    tracer, non del port, e `PORT_UNSHOWABLE` le toglie dal flusso del port perche'
    un'op non osservabile sfasa il confronto posizionale. Per chiuderla del tutto:
    un hook su `phyclk_fgc` e una cattura nuova. `MAC.FREQ` resta in deroga non dimostrata come prima
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

Totale 68 phy e 70 radio, di cui 91 default. **Misurato: valgono 32 op su 23068**,
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

Due cose non sono pronte per la spedizione, e stanno in quel README: `treat-the-n-phy-
dac-test` non applica sul pulito senza `sample-table-logic` davanti (dipendenza di
contesto, non logica), e `fill-the-per-rate` porta dentro uno spostamento di
`b43_nphy_tx_pwr_ctrl_coef_setup()` che va scorporato, perche' la sua ragione e' la
cattura e non un difetto di mainline.

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

1. **I valori degli indici di potenza**: b43 ha `0x19` dove il device scrive `0xa` e
   `0xc`, e sono le due op che restano nei tratti a #4958 e #6330. Domanda su cosa
   conserva il salvataggio dell'indice.
2. **Il tratto a #10761**, 16 op spostate su 18, che e' il sito singolo piu' grosso
   fra le 56 spostate che restano — la parentesi di carrier search, `0x2c`/`0x42`, il
   reset del baseband e le due letture dell'indice. Poi #9727 (6), #9008 (5), #3732
   (4), #24823 (4): stanno in sei siti, non spalmate.
3. **Il tratto a #25823**, 17 assenti, che e' la stessa istantanea di #877 piu' gli
   indici di potenza, letta alla fine di `up-ch1` prima del primo salto dell'ACI
   scan: appartiene all'ACI scan come #5004.
4. La cal PAPD ha ancora **una** scrittura di scarto della tabella di potenza,
   2 contro 1: la parentesi unica ne apre una dove il device ne apre zero, cioe'
   l'apertura cade dentro la regione invece che prima.
5. **Chi chiama la ricalibrazione al cambio canale.** Che il codice sappia farlo e'
   misurato su entrambe le catture, 91% su ch6 a caldo e 85% su ch11 a freddo; quello
   che manca e' il watchdog del riferimento, e senza di lui sull'hardware b43 usa sul
   canale nuovo la calibrazione del canale vecchio.
6. L'ACI scan, che e' una politica sopra il PHY e non una funzione da agganciare.
