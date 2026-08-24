# CLAUDE.md

Cosa serve sapere prima di toccare qualcosa. Corto di proposito: il dettaglio sta
in `docs/INDEX.md`, qui c'è solo ciò che serve per non ripetere errori già fatti.

## Il progetto

Portare in b43 il supporto **BCM6362 / N-PHY rev 8 / radio 2057 rev 8**, guidati
da una cattura MMIO del driver proprietario `wl 6.30.102.7`. Sette patch già
merged in mainline (`docs/upstream-status.md`), nove candidate in
`patches/mainline/`, ventisei compresse nel rollup di
`patches/b43/`. **Niente
ha mai girato su hardware**: tutto è verificato riproducendo la cattura in un
harness che compila il vero `phy_n.c`.

## Setup, ogni volta

```sh
sh scripts/fetch-upstream-state.sh ~/src/linux      # sparse, ~60 MB, sha 848acc8ffe1b
cd ~/src/linux
for p in .../patches/mainline/*.patch; do git apply "$p"; done   # tutte e nove
git apply .../patches/b43/rollup.diff                            # applica pulito
cd test && make KDIR=~/src/linux && make KDIR=~/src/linux warncheck
./phase_compare.py --vendor ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
```

`patches/b43/` e' **un file solo**, `rollup.diff`, finche' si costruisce: la serie
si ridivide prima di mandare qualunque cosa, e i messaggi delle ventisei patch che
contiene stanno in `patches/b43/MESSAGES.md`. Le citazioni per numero nei documenti
e in `phase_compare.py` risolvono contro quel file.

Il rollup vuole `mainline/` **prima** e non applica da solo, perche' non contiene
`0010` e `0022`: erano duplicati delle due mainline omonime, quindi il conflitto
atteso non c'e' piu'. Il costo e' che `check_patch_gating.py` da' un verdetto
unico per tutto il rollup invece di uno per patch; i tre punti non gateati e le
loro dichiarazioni sono in testa a `rollup.diff`.

**`patches/mainline/` fa parte del baseline, e per un giro questa sezione non lo
diceva.** Con la sola serie `b43/` le due finestre danno **5769** e **8724**, non
5791 e 8746: le 22 op di differenza sono due delle nove patch mainline, misurate
una per volta — `rf-control-override-value-masks` vale **+14** e
`fifth-tx-power-up-override` **+8**, le altre tre zero. Se il numero non torna,
guardare qui prima di cercare altrove. **I due valori assoluti sono di prima di
`0025`/`0026` e oggi non tornano** — la stessa misura da 15158 e 16353; il delta di
22 op non e' stato rifatto, quindi vale come ordine di grandezza e non come misura.

La catena di dipendenze dentro la serie serve alla **ri-divisione**, non al build:
misurata con `git apply` sull'albero pulito, 0004 dipende da **0002** (contesto in
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

`16 finestre: 0 da guardare, 5 divergenze note` piu' **due** finestre vere:
**Il verdetto e' la tabella per fase di `phase_compare.py`: 7205 op su 18808, il
38%.** Non il totale in blocchi contigui, che dice 18462 su 22943 (80%) e che **non
e' una misura**: su `up-ch1` 774 blocchi su 879 stanno sotto le 16 op e valgono
~1900 op del totale. Sommare frammenti da due op e chiamarla copertura e' contare il
sommerso nel PIL.

Un blocco conta se corrisponde a una **fase**: una voce di `phy_ops` dove esiste,
oppure — eccezione dichiarata finche' il port non le espone — una macro operazione
delimitata da un marcatore citato. Il numero per fase e' **uno**, la run contigua
piu' lunga dentro la fase, quindi nessun frammento lo muove.

| fase | op | run | blocchi |
|---|---|---|---|
| `gain-table` | 1540 | **1540 100%** | `1540` |
| `coeff-setup-2` | 1073 | **1066 99%** | `1066` |
| `pwr-setup` | 432 | 266 62% | `266` |
| `idle-tssi` | 660 | 334 51% | `334 123 85 41` |
| `coeff-setup` | 1037 | **1037 100%** | `1037` |
| `coda-idle-tssi` | 1139 | 432 38% | `432 334 41 31` |
| `cal-papd` | 2662 | **850 32%** | `850 2x334 220 178` |
| `cal-tx-iqlo` | 1570 | 443 28% | `443 331 268 80` |
| `cal-rssi-2` | 960 | 98 10% | `98 14x27 21 3x20` |
| `cal-rx-iq` | 5617 | 420 7% | **`6x420 2x360 6x119 12x85`** |
| `perical-ingresso` | 1402 | 119 8% | `2x119 100 90 2x88` |
| `recalc-txpower` (**phy_ops vera**) | 716 | **604 84%** | `604` |

Due fasi tornano per intero, `gain-table` e `coeff-setup`. E la seconda e' la
lezione di questa tabella, perche' per tre sessioni ha detto **zero** e la colpa
era dello strumento: `tbl_port_get()` in `wrap.c` non faceva avanzare l'indirizzo
in lettura, quindi una read in blocco rendeva N volte la stessa cella, e per una
cella che nessuno aveva scritto cadeva sul mirror del **registro** 0x73, cioe'
sull'ultima word versata da qualunque altra tabella. La read che apre la funzione
(`15/0x50 len=7`) prendeva sette volte `0xff86`, la coda di un offset epsilon PAPD,
dove il vendore legge sette zeri, e il port versava `0x000e1b86` in 512 celle. Il
codice del port era giusto e nel posto giusto da sempre.

Da cui la regola, che e' costata tre sessioni: **quando una fase fa zero e le op ci
sono, sospettare il valore prima del punto di chiamata.** I quattro blocchi si
trovavano con un `grep` sull'indirizzo di porta — `0x6940`, `0x6d40`, `0x69c0`,
`0x6dc0` — nello stesso ordine sui due lati; bastava guardarli.

Col mirror che serve le celle e' venuta fuori una cosa dell'**hardware**, non del
port: in 26/27 oltre l'offset 576 la rilettura e' il valore scritto **mascherato a
9 bit**, misurato su cinque celle su cinque (`0x24a`, `0x24c`, `0x25e` sui due
core: scritto `0xffffffe9`, riletto `0x01e9`; scritto `0xffffffbb`, riletto
`0x01bb`). I due lati scrivono lo **stesso** valore, e il mirror tiene i 32 bit
interi. **Non e' stato mascherato di proposito**: cinque celle di una regione in
una cattura non giustificano una larghezza dentro lo strumento, e la divergenza
e' inerte — il solo consumatore e' `b43_nphy_txpwr_index()`, che fa
`(((s16)v) << 4) & 0x1ff0`, e `0xffffffe9` e `0x01e9` danno entrambi `0x1e90`.
Costa due op sulla finestra `txpwr-index` e sta dichiarata la'.

### E buttava via il risultato

In coda alla stessa funzione il motore ha lasciato il risultato in `15/96` e il
driver deve prenderlo da la' e installarlo in `15/80`, dove il resto del driver
cerca i coefficienti. Le due chiamate hanno la **direzione scambiata**:
`write(96)` poi `read(80)`, dove il riferimento fa `read(96)` poi `write(80)`.
Quindi il driver sovrascrive il risultato del motore col buffer vecchio e legge
80 invece di scriverlo. Le tre coppie che seguono nello stesso blocco sono
giuste. La cattura conferma il riferimento: `#10640 TBL.WR id=0x000f off=0x0050
len=4`, primo valore `0x0059`.
`patches/mainline/b43-take-the-n-phy-tx-iq-lo-results-out-instead-of-overwriting-them.patch`.

Chiuderla ha chiuso `coeff-setup-2`, **da 514 a 1066 su 1073**, e la regione
`8505-10733` e' passata da 1195 a **1308 su 1570 (83%) in 50 blocchi**, da 85.

Per un giro ha **rotto `coeff-setup`, da 1037 a 514**, e la colpa era del seme:
la cal ora lascia `0x59` in `15/0x50` come deve, ma l'init non tracciato che
l'harness fa prima di quello tracciato lo lasciava li' anche all'ingresso della
finestra, mentre il vendore a `#3738` legge **zero** e ci arriva solo a `#10640`.
`gen_seed.py` non aveva **nessun supporto per le celle di tabella**. Ora ce l'ha,
e `coeff-setup` e' tornata a 1037 su 1037.

Per le celle il confine del seme e' **per forza** diverso da quello dei registri,
e vale sapere perche'. Per i registri si guarda solo prima della finestra; una
cella come `15/0x50` non e' scritta da nessuna parte nella cattura, perche' il
download statico che l'ha riempita e' di un boot precedente, e prima di `--before`
non c'e' niente da guardare. Il suo stato all'ingresso e' osservabile **solo dalla
prima read dentro la finestra**. Due condizioni tengono onesta la regola: si semina
la cella che nessuna write per porta ha toccato prima di quella read — se la
finestra ci ha scritto, il valore e' cio' che la finestra deve calcolare — e il cui
valore **non cambia** fra le read, perche' se cambia e' l'hardware che ci scrive
dentro la finestra ed e' lavoro di un piano. Sono **39 celle**; le 5 che restano
fuori dalle 44 a valore fisso sono proprio quelle che una write per porta aveva
toccato.

### La cal TX I/Q LO aspettava il contrario

`b43_nphy_cal_tx_iq_lo()` scrive un comando su `IQLOCAL_CMD` e poi fa polling
sullo stesso registro per aspettare che il motore finisca, prima di rileggere i
coefficienti. Il test era **invertito**: `if (tmp & 0xC000) break;` esce quando i
due bit sono **accesi**, cioe' *mentre* la cal gira. Il riferimento gira al
contrario, `SPINWAIT(((read_phy_reg(pi, 0xc0) & 0xc000) != 0), 20000)`, e
`SPINWAIT` cicla **mentre** l'espressione e' vera. Quindi b43 usciva alla prima
read, ~10 us dopo il comando, e salvava come coefficienti migliori cio' che la
tabella conteneva prima che il motore ci scrivesse — dodici volte, una per
comando.

Le due liste di comandi erano identiche da sempre, dodici valori nello stesso
ordine, e questo e' cio' che ha portato al difetto: le **write** combaciavano
(699 contro 698 nel corpo della cal), le tabelle combaciavano (94/95 e 20/20), e
mancavano **445 read**. Tutte su un indirizzo: `0xc0`, 455 volte nel vendore e 12
nel port. Il piano di lettura c'era ed era completo, 455 entry: non era capienza.

Corretta la condizione, il port fa **455 read su 455**, esatte, e la regione
`8505-10733` passa da **741 su 1570 in 97 blocchi a 1195 in 85**.
`patches/mainline/b43-wait-for-the-n-phy-tx-iq-lo-calibration-to-finish.patch`,
non gateata perche' il ciclo e' di ogni N-PHY.

**E la tabella per fase non si e' mossa di un'op.** `cal-tx-iqlo` resta 331 su
1570, il totale resta 5924. Le 454 op guadagnate stanno in una dozzina di blocchi
da ~65, uno per comando, e la run piu' lunga dentro la fase e' ancora lo stesso
blocco da 323 di prima. La metrica per fase e' fatta di proposito per ignorare i
frammenti, e qui il prezzo di quella scelta si vede: **sotto-riporta un fix
giusto**. Il verdetto in questo caso e' la struttura dei blocchi, che e' migliorata
in entrambi i versi — piu' op appaiate e blocchi piu' lunghi — e i blocchi contigui
su `up-ch1` da 16392 a 16846. Prima di dire che un cambiamento non serve perche' la
fase non si muove, guardare i blocchi.

`recalc_txpower`, che e' una `phy_ops` **vera** e non una macro, fa **0 su 716**, e
la regione da sola dice 295 su 716 in 10 blocchi con una run da 266: e'
l'assegnazione esclusiva, misurata identica prima e dopo il fix. La colonna blocchi
per quella fase e' **vuota**, e questo conferma che lo zero e' reale nel run
globale: la' dentro non c'e' nessun blocco da 16 op in su.

### adj_pwr_tbl: 36 contro 3, ed e' la parentesi per fase di mphase

`b43_nphy_tx_power_ctrl()` scrive la tabella di potenza aggiustata — 26/0x40 e
27/0x40, 84 celle, 85 op per scrittura — **solo nel ramo di abilitazione**. Sulla
finestra `up-ch1` il vendore la programma **36 volte** per tabella, il port **3**.
Sono ~5600 op del vendore, il 27% della finestra, che il port non emette affatto,
ed e' l'asimmetria piu' grossa che resta.

Il meccanismo e' chiaro e non e' in discussione. `b43_nphy_txpwr_index()` fa
`tx_pwr_ctrl_state = nphy->txpwrctrl`, disabilita, lavora, e ripristina: se al
momento della chiamata il controllo era **spento**, il ripristino rispegne e la
tabella non si scrive. `b43_phy_initn()` spegne a monte del blocco di cal e
riaccende in coda, e la cal gira **in mezzo**, quindi tutti quei ripristini non
fanno niente. Il port tocca `0x1e7` 52 volte contro le 12 del vendore, e con
`PHY.AND 0x1fff`/`0x7fff`, cioe' il ramo di spegnimento.

**Provato a differire il blocco gateato dopo `b43_nphy_tx_power_ctrl(dev,
tx_pwr_state)`, in fondo a `initn`, dove il riferimento lo ha di fatto — la' e'
solo schedulato e gira dalla macchina mphase, a controllo gia' ripristinato. Il
risultato e' NEGATIVO e la modifica NON e' in albero:**

| | prima | differita |
|---|---|---|
| `adj_pwr_tbl` 26/0x40 | 3 | 13 |
| `perical-ingresso` | 119, `2x119 100 90 2x88` | 172, **`5x172`** |
| `cal-rx-iq` | 420, **`6x420`** | 360, **`6x332`** |
| totale per fase | 6602 | 6592 |
| **blocchi contigui** | **17532 (76%)** | **15148 (66%)** |

Le 88 op che ogni iterazione dello sweep perde sono **una scrittura di
`adj_pwr_tbl`** che il port infila dentro l'iterazione e il vendore non ha: il
vendore la scrive all'**ingresso** di `cal_rx_iq` (#15109, #15332, #15920) ma non
dentro ogni iterazione.

**Cercarla dentro `cal_rx_iq` e' escluso, e con una prova secca**:
`b43_nphy_rev3_cal_rx_iq()` (72 righe) e l'implementazione vera del riferimento,
`wlc_phy_cal_rxiq_nphy_rev3()` (159 righe), hanno **zero** chiamate a
`tx_power_ctrl`/`txpwrctrl_enable` e a `txpwr_index`. Nessuno dei due tocca il
controllo di potenza la' dentro, quindi quelle scritture vengono dal **chiamante**.

E dove cadono lo dice il conteggio, che e' il punto da cui ripartire. Delle 36:

| dove | quante |
|---|---|
| `cal-rx-iq` | 12 |
| `perical-ingresso` | 7 |
| `coda-idle-tssi` | 6 |
| `cal-papd` | 5 |
| `recalc-txpower` | 2 |
| init, prima delle fasi | 2 |
| `coeff-setup`, `cal-tx-iqlo` | 1 ciascuna |

Sono **sparse su tutte le fasi**, non concentrate in un punto: e' la macchina a stati
mphase che fra una fase e l'altra passa dal ripristino del controllo di potenza, e
l'espansione inline di b43 le fa di fila senza quella parentesi per fase. Quindi non
e' una chiamata mancante da aggiungere: e' la differenza fra una macchina a stati e
un blocco sequenziale, e chiuderla vuole riprodurre la parentesi per fase — un
lavoro di struttura, non una patch. **Due ipotesi facili sono state escluse con dei
numeri: spostare tutto in fondo a `initn`, e cercare dentro `cal_rx_iq`.**

### La macchina a stati mphase, ricostruita e IN ALBERO

`wlc_phy_cal_perical_nphy_run()` e' chiamata una volta per fase, e ognuna fa la
stessa parentesi: legge il tx gain da `7/0x110`, salva `nphy_txpwrctrl` e lo
**spegne**, esegue la sua fase, e in coda `txpwrctrl_enable(tx_pwr_ctrl_state)`.
E' quel ripristino a scrivere `adj_pwr_tbl`. Ricostruita in
`b43_nphy_cal_perical_phyinit()`, piu' il blocco differito in coda a `initn`
perche' le due meta' sono **accoppiate** — la parentesi ripristina cio' che trova,
e la' il controllo e' spento.

Serviva anche `mphase_txcal_numcmds`, che non era impostata da nessuna parte: con
`mphase=true` il ciclo dei comandi girava a vuoto.

| | base | **in albero** | vendore |
|---|---|---|---|
| `adj_pwr_tbl` 26/0x40 | 3 | **18** | 36 |
| `perical-ingresso` | `2x119 100 90 2x88` | **`6x172`** | |
| `cal-rx-iq` | `6x420` | `6x420` | |
| `cal-tx-iqlo` | 443, 8 piccoli | **428, 11 piccoli** | |
| totale per fase | **6602** | **6558** | |
| blocchi contigui | 17532 | **18462** | |

**E' piu' bassa di prima, e sta in albero comunque.** Il numero da battere resta
6602.

### La misura del tono della cal PAPD, portata

`wlc_phy_a1/a2/a3_nphy` e `wlc_phy_papd_decode_epsilon` non c'erano: il motore
girava sulle tabelle azzerate e `b43_nphy_papd_cal()` lo dichiarava nel proprio
commento. Portate come `b43_nphy_papd_run_one()` (un passo del motore su un core),
`b43_nphy_papd_gain_search()` (il codice di pad gain che smette di clippare, un
passo per volta fino a venti) e `b43_nphy_papd_smooth_epsilon()` (la media a
finestra scorrevole sulla tabella epsilon), piu' il decoder dei due campi da 13 bit.

Solo il ramo rev 7 e oltre e solo la meta' 2 GHz, perche' il chiamante prova phy
rev 8, radio rev 8 e la banda: gli altri rami sarebbero peso morto. Gli helper
c'erano gia' tutti — `ipa_set_bbmult`, `rf_ctl_override_one_to_many`,
`rf_ctl_override_rev7`, `get_tx_gains`.

**Blocchi contigui da 17532 a 17838 (76% -> 78%): il primo numero di questa serie
sopra il valore di base.** Il motore ora sweepa davvero, 405 scritture su `0x2be`.
Il totale per fase resta 6558 contro 6602 — la run piu' lunga di `cal-papd` non si
muove — ma la forma passa da `794 2x334 172 2x78 +14` a `794 2x334 220 178 +32`.
`adj_pwr_tbl` resta 13 su 36, quindi la parentesi di quelle due sotto-calibrazioni
non e' ancora quella del vendore: i segmenti sono 14 contro 9.

### Le sei fasi TX sono UN passo, e come si e' scoperto

Divise in sei con `mphase=true`, `cal-tx-iqlo` cade da 428 a **331 in 28
frammenti**. La prima spiegazione — le parentesi di troppo — era **sbagliata**:
togliendo cinque parentesi e lasciando la divisione, il numero resta 331. E' la
**divisione** dei dodici comandi in sei pezzi da due, che fa emettere alla cal il
lavoro per pezzo fra l'uno e l'altro. La cattura li ha contigui, con una sola
lettura del gain a #8505 invece di una per fase.

Due misure per separare due cause che sembravano una: senza quella seconda misura
avrei attribuito 97 op alla cosa sbagliata.

### Il "doppio" dei coefficienti RSSI non e' del port: lo fa anche il vendore

La finestra `rssi-cal` diceva che il port scrive ogni coefficiente **due volte**, zero e
poi il valore, come se fosse una sua stranezza. **Falso, e mi ha sviato**: nella fase
`cal-rssi-2` il vendore fa esattamente la stessa cosa — `0x1a4` a `0x0000` e poi a
`0x003e`, `0x1aa` idem, e cosi' per tutti. Quella parte e' **fedele**.

L'asimmetria vera e' un conteggio: **21** scritture sui nove registri nella finestra
`up-ch1` del vendore contro **28** del port, quindi sette in piu'. E la regione da sola
si appaia in blocchi da 98, 46, 46 e 43 op, che non e' il quadro di una fase sbagliata.

Corretto il testo della finestra. Era una diagnosi scritta bene e sbagliata, e per
giorni ha indirizzato verso un difetto del port che non c'e' — compreso il sospetto su
`offset[2 * core]`, che con lo stato finale a 9/9 e il doppio dichiarato fedele non ha
piu' niente che lo sostenga.

### Il "doppio" dei coefficienti RSSI non e' del port: lo fa anche il vendore

La finestra `rssi-cal` diceva che il port scrive ogni coefficiente **due volte**, zero e
poi il valore, come se fosse una sua stranezza. **Falso, e mi ha sviato**: nella fase
`cal-rssi-2` il vendore fa la stessa cosa — `0x1a4` a `0x0000` e poi a `0x003e`, `0x1aa`
idem. Quella parte e' **fedele**.

L'asimmetria vera e' un conteggio: **21** scritture sui nove registri nella finestra
`up-ch1` del vendore contro **28** del port, sette in piu'. E la regione da sola si
appaia in blocchi da 98, 46, 46 e 43 op, che non e' il quadro di una fase sbagliata.

**Il testo dentro `phase_compare.py` NON e' ancora corretto**, e questo va saputo: la
stringa `known` di `rssi-cal` continua a dire che il doppio e' del port e che
l'asserzione sullo stato finale non esiste. Due tentativi di sostituzione sono falliti
in silenzio per l'escaping, il terzo ha rotto la sintassi del file e l'ho ripristinato
dal commit. Chi passa da qui la sistemi a mano: sono due frasi in quella stringa, e la
verita' e' questa voce.

Era una diagnosi scritta bene e sbagliata, e per giorni
ha indirizzato verso un difetto del port che non c'e' - compreso il sospetto su
`offset[2 * core]`, che con lo stato finale a 9/9 e il doppio dichiarato fedele non ha
piu' niente che lo sostenga.

### L'asserzione sullo stato finale, e cosa dice subito

`phase_compare.py` ha ora `finali` e `finali_len`: per i registri che una finestra
dichiara, confronta **l'ultimo valore scritto** sui due lati invece della sequenza di
op. Lo span del port e' il suo, dichiarato, e non quello del vendore — sulle sole 16 op
della finestra il port ha appena scritto gli zeri e non ancora i valori, e troncare li'
misurerebbe uno stato intermedio. Ci sono cascato al primo tentativo: diceva 4 registri
su 9 diversi, ed era il troncamento.

Su `rssi-cal`: **stato finale 9/9 registri**. Quindi lo stato e' quello del vendore e
cio' che diverge e' la strada, e la run che fa 1 su 16 va letta cosi': **stato giusto,
sequenza no**. Sono due difetti diversi e ora si vedono tutti e due, nella stessa riga
di riepilogo invece che dietro `-v`.

Questo chiude la voce che la finestra portava aperta da giorni, e conferma che il
sospetto su `offset[2 * core]` **non e' un difetto di valore**: i nove registri
arrivano dove devono.

### Il fix di recalc aveva rotto due finestre, e non me ne ero accorto

Spostando la cal su `recalc_txpower`, il flow `init` — che recalc non lo chiama — ha
smesso di eseguirla del tutto. Due finestre che la ancoravano, `papd-tables` e
`txpwr-index`, sono passate a `ERR: ancora non trovata`, e il riepilogo da «0 da
guardare» a «2». **Non l'avevo visto perche' avevo guardato solo blocchi e TOTALE.**
Portate le due sul flow `txpower`, che la esegue: si torna a 0 da guardare.

La riga `N finestre: X da guardare` va letta a ogni giro, non solo il totale: e' l'unica
cosa che dice se un cambiamento ha rotto un'ancora, e le due misure grandi non se ne
accorgono.

### cal-rssi-2: un sospetto NON verificato, e perche' non l'ho toccato

`cal-rssi-2` fa 98 su 960 in `98 14x27 21 3x20`, ed e' l'unica fase rimasta con
frammentazione vera invece di ripetizione strutturale. La diagnosi della finestra
`rssi-cal` regge: il vendore scrive gli otto coefficienti di fila in 16 op, il port ne
mette ~140 perche' scrive ogni coefficiente **due volte**, zero e poi il valore, e
intercala read e override RF.

`b43_nphy_scale_offset_rssi()` scrive una volta per chiamata, quindi il doppio e' nel
chiamante. La' c'e' una cosa che salta all'occhio: il ciclo calcola `offset[j]` e poi
passa **`offset[2 * core]`**.

**Non e' verificato e non l'ho toccato.** Quella struttura di ciclo in brcmsmac non
esiste nella stessa forma — nel riferimento non c'e' ne' `offset[j]` ne'
`offset[2 * core]` — quindi la trascrizione non si puo' confrontare riga per riga come
per gli altri difetti trovati. E c'e' una controprova: la finestra dichiara che **i
nove valori combaciano gia'**, `0x1b8 = 0x3f` e otto `0x3e`; se l'indice fosse sbagliato
i valori non tornerebbero.

Il vero ostacolo lo dice la finestra stessa, e non e' il driver: «questa fase vuole un
confronto sul VALORE FINALE dei nove registri, che e' un'asserzione che questo strumento
non fa». Finche' quell'asserzione non c'e', qualunque modifica qui si giudica su una
misura che non sa distinguere «scritto due volte» da «scritto male». **E' lavoro di
strumento prima che di driver**, ed e' il motivo per cui questa fase e' rimasta indietro
mentre le altre si chiudevano.

### Spostata: recalc-txpower da 0 a 604, e il totale a 7205

La sequenza differita non gira piu' in coda a `b43_phy_initn()` ma dalla coda di
`b43_nphy_op_recalc_txpower()`, dietro `nphy->perical_pending`. E' il solo punto fra i
due in cui l'harness passa; nel riferimento la fa partire il watchdog, che qui non c'e'.

| | prima | dopo |
|---|---|---|
| `recalc-txpower` | 0 su 716, nessun blocco | **604 su 716 (84%), un blocco solo** |
| totale per fase | 6658 | **7205 (38%)** |
| blocchi contigui `up-ch1` | 18309 | **18462 (80%)** |
| `up-ch1-freddo` | 18022 | **18163 (66%)** |

**+603 op sul verdetto in un colpo**, la fase piu' grande a zero chiusa all'84%.

Il freddo per un giro e' crollato a **7212 (26%)**, e la ragione insegna qualcosa sul
banco: `flow_initpor` non chiamava `recalc_txpower`, quindi con la cal appesa a quella
il flow a freddo non la faceva girare **affatto** — undicimila op perse. mac80211
chiama `recalc_txpower` dopo l'init **sempre**, quindi il flow a freddo che non lo
faceva era il banco a essere infedele, non il driver: aggiunta la chiamata in
`test/main.c`, e il freddo e' tornato **sopra** il valore di partenza.

### recalc-txpower fa zero perche' gira nel posto sbagliato

La fase e' 600 `PHY.WR`, 6 `PHY.MOD` e **sei** `TBL.WR`: `26/0x0` e `27/0x0` da 64
celle a #5726 e #5856, poi due coppie di `26/0x40` e `27/0x40` da 84 a #5986, #6072,
#6158, #6244. Il port fa **tre** scritture da 64 celle come il vendore, quindi non
manca niente: sono nel posto sbagliato.

| | posizioni delle `26/0x0 len=64` |
|---|---|
| vendore | #1740 (init), **#5726** (la fase), #24391 (coda-idle-tssi) |
| port | #1291 (init), **#22723**, #23406 |

Il vendore la fa a **#5726, fra l'init e le cal**; il port a **#22723**, cioe' dopo
tutto l'init, cal comprese. `recalc_txpower` e' una `phy_ops` che l'harness chiama
quando `b43_phy_initn()` e' tornata, e la sequenza differita che ho costruito sta in
coda a `initn`: quindi le cal finiscono **prima** che recalc parta, mentre il vendore
fa init, recalc, poi le cal.

Da cui lo zero e la colonna blocchi vuota: le op ci sono tutte e cadono 17000 record
piu' avanti della finestra della fase.

**Il fix e' strutturale e non locale**: la sequenza differita non puo' stare in coda a
`initn` se recalc deve girare prima. Va spostata dove l'harness la possa invocare fra
le due — cioe' il flow deve diventare init, recalc, cal — e questo tocca `test/main.c`
e il punto di chiamata nel driver insieme. Vale 716 op, la fase piu' grande a zero.

### La seconda forzatura dell'indice: SOPRA il baseline

Allineate le due sequenze di write con i numeri di record, la coppia in eccesso e' a
**#7091 e #7490** (`2e2c 2e2e`): una **seconda forzatura**, dove il vendore ne ha una
sola. E `precal_txgain` era chiamato due volte, nel blocco differito e al passo INIT.

Tolto quello del passo INIT — il blocco differito lo fa prima di entrare:

| | prima | dopo |
|---|---|---|
| write di `15/0x57` che combaciano | 7 | **12, esatte** |
| `cal-papd` | 794 | **850** (baseline 847) |
| `cal-tx-iqlo` | 428 | **443** (baseline 443) |
| totale per fase | 6587 | **6658** |
| blocchi contigui | 18254 | **18309** |

**6658 contro 6602: il deficit della ricostruzione e' chiuso, e siamo 56 op sopra il
baseline.** `cal-papd` e `cal-tx-iqlo`, le due fasi che erano sotto, sono tornate
entrambe sopra.

Nota su un errore evitato per un soffio: giri prima avevo provato a togliere
`precal_txgain` dal **blocco differito**, e costava 730 op — da cui la conclusione «il
doppione serve», messa a verbale. Era vera per **quello** dei due, non per l'altro. Il
conteggio «due chiamate dove il vendore ne ha una» non diceva quale togliere, e la
risposta e' venuta dall'allineare le write **coi numeri di record** e vedere dove
nasce la divergenza.

### Le due coppie stanno entrambe PRIMA delle cal, e la coda non restituisce

Mappate le write di `15/0x57` del vendore sulle fasi, invece di provare permutazioni:

    #1219 #1239 #1710      init
    #7445 2e2c             perical-ingresso   <- forza
    #7868 2e2e             perical-ingresso
    #8096 2c2e             perical-ingresso   <- restituisce
    #8294 2c2c             perical-ingresso
    #10694                 cal-tx-iqlo

**Entrambe le coppie sono dentro `perical-ingresso`, prima che le cal comincino** — ed
e' esattamente cio' che il marcatore della fase dichiarava da sempre: «get_tx_gain
#7038, precal #7234, hand-back #8086». Il blocco differito le fa gia' tutte due:
`precal_txgain` forza, la coppia con indice `-1` restituisce.

Quindi la restituzione in coda alla macchina a stati era una **terza** coppia, dopo le
cal, che il vendore non ha. Togliendola: le write che combaciano passano da **5 a 7**,
il conteggio va a **35 come il vendore**, run **invariate a 6587**, blocchi 18254 (-4).

Con lei sono usciti `restore_tx_gain`, che non ha piu' lettori, e l'assegnazione di
`cal_orig_pwr_idx` al passo INIT, che diventava scritta e mai letta — il peso morto che
avevo introdotto due commit prima inseguendo l'ipotesi sbagliata.

Resta la write 8: il port fa `2e2c 2e2e` dove il vendore fa `2c2c 4000 4000`, quindi c'e'
ancora una coppia in eccesso piu' avanti. Ma il metodo ora e' provato due volte:
mappare le write sulle fasi e guardare **dove** cadono, non quante sono.

### Le due insieme sono rifiutate: la coppia differita FORZA l'indice che serve

Provate insieme, ed e' la quinta ipotesi chiusa su questo residuo. Conteggio a 35 come
il vendore, e **sequenza peggiore di prima**:

    vendore  2c44 2c2c 2c2c 2e2c 2e2e 2c2e 2c2c 2c2c 4000 4000
    port     2c44 2c2c 2c2c 2e2c 2e2e 2e2e 2e2e 2e2e 4000 4000

Il ripristino non avviene **del tutto**, e il motivo e' meccanico: il ramo con indice
`-1` in `b43_nphy_txpwr_index()` rimette `saved->bbmult` solo se un indice era stato
forzato prima, cioe' se `saved->index >= 0`. Togliendo la coppia dal blocco differito
nessuno forza piu' niente, quindi la restituzione della coda diventa un **no-op**.
Blocchi 18102, run 6584: peggio di entrambe le versioni singole.

Quindi quella coppia non e' di troppo: **e' lei a forzare l'indice** che la coda poi
restituisce, ed e' la ragione per cui rimuoverla da sola costava 151 op. Il residuo di
15 op non e' in nessuna delle cinque cose provate:

| ipotesi | esito |
|---|---|
| indice iniziale sbagliato (`txpi`) | no, e' 30 e combacia |
| valore iniziale del bbmult | no, `0x2c44` su entrambi |
| calcolo del bbmult | no, la scala e' identica |
| coppia differita di troppo | no, -151, e serve a forzare |
| `-1` nella coda, da sola o accoppiata | -3 e -156 |

Cio' che resta da guardare e' l'**ordine** fra le due: nel vendore la coppia che forza
e quella che restituisce stanno in due punti precisi che non ho ancora localizzato
nella cattura. Il modo e' quello che ha funzionato per il controllo di potenza -
trovare i record delle due coppie e vedere quali fasi le separano - non provare
un'altra permutazione a naso.

### La restituzione va con -1, non con l'indice: 7 write su 7, e la coppia che resta

Il salvataggio in `b43_nphy_txpwr_index()` e' protetto da `if (saved->index < 0)`,
quindi salva una volta sola: quello e' corretto. Il difetto era **quale chiamata**. Il
vendore alle write 6-8 fa `2c2e 2c2c 2c2c`, tre write che rimettono `saved->bbmult` su
entrambi i byte: e' il ramo con indice **-1**. La coda della macchina a stati invece
forzava `cal_orig_pwr_idx`, che scrive il bbmult della riga di gain di quell'indice —
`0x312e` e `0x3131` — e da li' trascinava `0x2e`.

Messo `-1`: le write che combaciano passano da **5 a 7**.

    vendore  2c44 2c2c 2c2c 2e2c 2e2e 2c2e 2c2c  2c2c 4000 4000
    port     2c44 2c2c 2c2c 2e2c 2e2e 2c2e 2c2c  2e2c 2e2e 2e2e

**Ma da sola costa**: blocchi 18258 -> 18253, run 6587 -> 6584. Non e' in albero. Il
motivo si vede nella riga: all'ottava il port riparte con `2e2c 2e2e`, cioe' **un'altra
coppia** — i due `txpwr_index(-1, true)` del blocco differito, che sparano dopo.

Quindi le due modifiche sono **accoppiate**, come lo erano la parentesi e il
differimento: `-1` nella coda **piu'** la rimozione della coppia nel blocco differito.
Provate una per volta danno -3 e -151; insieme non sono state provate, ed e' **una
misura sola**. E' il punto da cui ripartire, e la verifica e' che le write diventino
35 con le prime otto uguali.

### Le due write in piu' non erano di troppo: e' il SALVATAGGIO a essere tardi

Elencate tutte le write di `15/0x57` sui due lati, 35 contro 37:

    vendore  2c44 2c2c 2c2c 2e2c 2e2e **2c2e 2c2c 2c2c** 4000 4000 2c2c ...
    port     2c44 2c2c 2c2c 2e2c 2e2e **312e 3131 2e31 2e2e 2e2e** 4000 4000 ...

Le prime cinque combaciano. Poi il vendore **ripristina** l'originale `0x2c`, e il
port sale a `0x31` e ridiscende a `0x2e`, che si trascina per tutto il resto.

Provato a togliere la coppia di `txpwr_index(-1, true)` dal blocco differito, che
sembrava la chiamata in piu'. **Il conteggio va a 35 = 35, e non risolve niente:** il
port fa `2e2e 2e2e 2e2e` dove il vendore fa `2c2e 2c2c 2c2c`, quindi il ripristino
continua a non avvenire, e i blocchi contigui scendono di **151** (18258 -> 18107) a
run invariate. Non e' in albero.

Quindi non era una chiamata di troppo, ed e' la quarta ipotesi chiusa su questo
residuo. Il difetto e' che `saved->bbmult` contiene **gia'** `0x2e` quando il
ripristino lo rimette: il *salvataggio* avviene dopo che l'indice si e' mosso. Il
posto e' `b43_nphy_txpwr_index()` al ramo che fa
`saved->bbmult = (tmp >> (core ? 0 : 8)) & 0xFF`, e la domanda e' a quale chiamata
quel salvataggio veda gia' il valore nuovo.

E la lezione, la stessa di tutta questa serie: **un conteggio che torna non prova che
il comportamento sia giusto.** 35 uguale a 35 con la sequenza ancora sbagliata, e 151
op contigue perse per averlo inseguito.

### Il bbmult non ha un difetto di valore: ha un difetto di FASE

Eseguito il confronto delle due storie di `15/0x57` con `trace_tables.py --cell`, e la
sequenza dei valori e' **la stessa su entrambi i lati**, passo per passo:

    0x4444 -> 0x2c44 -> 0x2c2c -> 0x2c2c -> 0x2e2c -> 0x2e2e -> ...

Vendore ai record #1215 #1219 #1239 #1710 #7445 #7868; port a #817 #820 #837 #1262
#5715 #6103. **Nessun difetto di calcolo**: ogni valore che il port scrive, il vendore
lo scrive, nello stesso ordine.

Ma il port ci arriva **prima** e va **oltre**: dopo `0x2e2e` continua a `0x312e` e
`0x3131`, e le transizioni totali sono **37 contro 35**. Da cui la divergenza a
#11756: il vendore la' e' ancora su `0x2c2c` e il port e' gia' a `0x2e2e`, perche' ha
percorso piu' avanti la stessa scala.

Quindi non e' un valore da correggere, e nemmeno l'indice di partenza: e' **quante
volte** il port cambia indice, e quando. Due transizioni in piu' su 35, e in anticipo.
Il posto da guardare e' chi chiama `txpwr_index()` e quante volte — che e' la stessa
domanda che l'audit dei confini ha risolto per il controllo di potenza, con lo stesso
metodo: contare le transizioni per confine sui due lati invece di guardare i valori.

Le tre ipotesi su questo residuo sono ora tutte chiuse: non e' l'indice iniziale
(`txpi = 30`, combacia), non e' il valore iniziale del bbmult (`0x2c44`, combacia),
non e' il calcolo (la scala e' identica). E' il conteggio.

### index_internal e' giusto: l'origine e' una delle 36 scritture del bbmult

Ipotesi «l'indice di partenza e' sbagliato»: **rifiutata**. Per `phy->rev >= 7`,
`txpi[0] = txpi[1] = 30`, e 30 e' esattamente l'indice che il bbmult `0x2c` del
vendore implica. `index_internal` combacia.

E il bbmult **parte identico**: la prima scrittura di `15/0x57` e' `0x2c44` su
entrambi i lati (#820 nel port, #1219 nel vendore). Le scritture totali sono 37
contro 35. Quindi la divergenza verso `0x2e2e` la introduce **una** di quelle ~36, e
non lo stato iniziale.

Il passo successivo e' un comando: `trace_tables.py --cell 0xf:0x57` sui due trace, e
confrontare le due storie per trovare la prima scrittura che diverge. E' la stessa
tecnica che ha chiuso `coeff-setup` — la' era `--cell 0xf:0x50` — quindi lo strumento
c'e' gia' e la domanda e' chiusa, non aperta.

### Il deficit di cal-papd e il bbmult di txpwr-index sono lo stesso difetto

Localizzata la rottura. Il blocco di `cal-papd` parte a vendor @0 (#10962) e si ferma
a **@794, cioe' #11756**, dove il base arrivava a @846. Riprende a @851, quindi il
buco e' di 57 op.

A #11756 il vendore legge `15/0x57`, il bbmult, e prende **`0x2c2c`**. Il port legge
`0x2e2e`. E' la **stessa** divergenza che la finestra `txpwr-index` porta dichiarata
da giorni: «il vendore legge 0x2c2c e scrive 0x2e2c, il port fa 0x2e2e in entrambe,
cioe' sta su un indice diverso». La run si rompe su un valore, come sempre.

Quindi le 15 op che restano sotto il baseline e le sei divergenze di `txpwr-index`
non sono due voci: sono **una**, ed e' l'indice di potenza su cui il port si trova.
Il primo posto da guardare e' `txpwrindex[].index_internal`, che e' anche cio' che il
passo INIT ora salva in `cal_orig_pwr_idx`: se l'indice di partenza e' sbagliato, la
restituzione rimette fedelmente un valore sbagliato, e la catena e' coerente in tutti
i punti tranne l'origine.

### L'indice da restituire era zero, e i sotto-blocchi lo dicevano

`nphy->cal_orig_pwr_idx[]` e' impostata in **un posto solo**, dentro
`if (nphy->perical != 2)`. Questo hardware ha `perical == 2` — che e' la ragione per
cui esiste la macchina a stati — quindi la' non passa e quell'array **resta a zero**:
la restituzione forzava l'indice 0 invece di rimettere quello di partenza. Preso al
passo INIT, dov'e' nell'altro ramo, subito prima di `precal_txgain`.

| | prima | dopo |
|---|---|---|
| blocchi contigui | 18229 (79%) | **18258 (80%)** |
| totale per fase | 6584 | **6587** |
| forma di `cal-rx-iq` | `6x420 360 342 2x119 +42` | **`6x420 2x360 6x119 12x85 +21`** |

I gruppi `6x119` e `11x85` sono tornati, e i frammenti sono 21 contro i 22 di prima
del guard: il costo di 3 op del commit precedente e' rientrato e c'e' un guadagno
sopra.

**Ed e' la previsione dalla forma che ha funzionato.** Il guard corretto costava 3 op
e frammentava `cal-rx-iq` da 22 a 42 pezzi; guardando **quali** gruppi si rompevano —
i `6x119` e gli `11x85`, non i `6x420` — la diagnosi era che le due chiamate
partivano ma con il valore sbagliato, non nel posto sbagliato. Un totale non
distingue le due cose, la colonna dei blocchi si'.

### Il buco prima della RX IQ e' vuoto: candidato chiuso

Le 98 op fra #14854 e l'inizio di `cal-rx-iq` a #14951 non contengono nessuna
struttura: una scrittura su `0x72` e **84 su `0x73`**, cioe' la coda dello
spegnimento che parte a #14853 — il confine che avevo scelto tagliava una transizione
a meta' — piu' sei registri sparsi (`0xb0` due volte, `0x1e7`, `0xb8`, `0xa5`,
`0x8f`, `0x42`). Zero table-op, zero op radio.

Quindi la frammentazione di `cal-rx-iq` da 22 a 42 pezzi **non viene da qualcosa che
manca la'**, e quel candidato e' chiuso. Va cercata dentro la fase, confrontando la
forma prima e dopo il guard: `6x420 2x360 6x119 12x85 +22` contro
`6x420 360 342 2x119 +42`. I gruppi che si sono rotti sono i `6x119` e gli `11x85`,
non i `6x420`, quindi sono le iterazioni interne dello sweep e non il suo scheletro.

### Il guard era sbagliato: sullo stato d'ingresso, non del passo

Il test era `restore_tx_gain && tx_pwr_ctrl_state`, dove il secondo e' lo stato
salvato **dal passo**. Con la chiusura unica alla fine quel valore e' falso dopo la
prima apertura, quindi la restituzione non partiva del tutto: il port emetteva **una**
`TBL.RD 7/0x110 len=1` dove il vendore ne ha **due**. Corretto a
`entry_pwr_ctrl_state`, quello dell'ingresso della sequenza — che nella macchina a
stati e' l'unico che vale.

Verifica prevista e passata: **da 1 a 2, come il vendore**. E costa:

| | prima | dopo |
|---|---|---|
| blocchi contigui | 18254 (80%) | 18229 (79%) |
| totale per fase | 6587 | **6584** |
| frammenti di `cal-rx-iq` | 22 | **42** |

**Sta in albero comunque**, e non per ottimismo: il guard di prima era provabilmente
sbagliato, e lasciarlo per difendere 3 op sarebbe tenere un difetto noto in cambio di
un numero. Il prezzo dice una cosa precisa: ora il **meccanismo** e' giusto — due
chiamate, come il vendore — ma il **punto** in cui cadono non lo e' ancora, e la
frammentazione di `cal-rx-iq` da 22 a 42 e' dove guardare.

### La restituzione dell'indice sta fra la PAPD e la RX IQ

Dentro il buco `#14093-14950`, oltre ai quattro spegnimenti, ci sono **due chiamate
a `txpwr_index`, una per core**, ognuna col suo salva e riapplica, riconoscibili
dalle table-op: #14101 legge `7/0x110`, `15/0x57`, `15/0x50 len 2`, `15/0x55` (salva,
core 0), #14305 riscrive `7/0x110` e `15/0x57` (riapplica), e #14524/#14728 fanno lo
stesso su `7/0x111` per il core 1.

Nel port `restore_tx_gain` era sul passo RX IQ, quindi la restituzione girava **dopo**
la cal RX IQ invece che prima. Spostata su PAPD.

**Numeri neutri**: 18254 e 6587 identici, con i frammenti di `cal-papd` da 34 a 31.
Sta dentro per l'evidenza della cattura, non per il numero, e questo va detto invece
di vendere il -3 sui frammenti come un guadagno.

Il conto non e' chiuso: il port emette **una** `TBL.RD 7/0x110 len=1` dove il vendore
ne ha **due**, quindi una delle due chiamate per il core 0 manca ancora. Il guard e'
`restore_tx_gain && tx_pwr_ctrl_state`, e con la chiusura unica alla fine quello stato
per passo e' falso dopo la prima apertura: e' il prossimo posto da guardare.

### La parentesi si chiude UNA volta, alla fine

Audit di ogni confine fra i passi, contro la cattura, col test sul payload:

| confine | transizioni |
|---|---|
| perical -> TX I/Q LO | nessuna |
| TX I/Q LO -> PAPD | 1 spegnimento (#10790, #10876) |
| PAPD -> RX IQ | **4 spegnimenti** (#14121 #14207, #14344 #14430, #14544 #14630, #14767 #14853) |
| RX IQ -> idle TSSI | nessuna |

**Non c'e' una sola accensione fra le fasi.** Sono tutti spegnimenti, e gli
spegnimenti sono le *aperture*: il controllo di potenza resta spento per tutta la
sequenza e si ripristina una volta, alla fine. Le chiusure per passo che avevo messo
non esistono nel vendore.

| | prima | dopo |
|---|---|---|
| blocchi contigui | 17830 (78%) | **18254 (80%)** |
| totale per fase | 6587 | **6587** |

**+424 op contigue e nessuna perdita sulle run.** Ed e' il primo cambiamento di
questa serie che migliora senza costare niente, perche' e' il primo dedotto da un
audit sistematico dei confini invece che da un'ipotesi su un confine per volta: il
tentativo precedente — togliere la sola chiusura fra TX I/Q LO e PAPD — dava +473
blocchi ma **-53** sulle run, perche' lasciava in piedi le altre tre chiusure che il
vendore non ha.

### Fra la cal TX I/Q LO e la PAPD: una transizione, non due

Indagato `cal-papd`. Fra le due fasi la cattura ha **228 op**, e dentro **una sola**
transizione del controllo di potenza: `26/0x40` a #10790 e `27/0x40` a #10876, con
payload di **84 zeri**, quindi uno **spegnimento** — cioe' l'apertura della parentesi
di PAPD, non la chiusura di quella della TX I/Q LO.

La macchina a stati ne fa **due**: la chiusura di TXPHASE0, con contenuto, piu'
l'apertura di PAPDCAL. Il vendore tiene il controllo **spento** fra le due fasi.

Provato a togliere la chiusura su TXPHASE0. **Risultato contrastante, e non e' in
albero:**

| | in albero | senza la chiusura |
|---|---|---|
| blocchi contigui | 17830 (78%) | **18303 (80%)** |
| totale per fase | **6587** | 6534 |

I blocchi guadagnano **473 op**, il piu' alto misurato in tutta la serie, e le run
perdono 53. La prova dalla cattura e' solida — una transizione, ed e' uno
spegnimento — quindi la modifica va nella direzione giusta e paga dove conta la
contiguita'. Ma il verdetto dichiarato e' la run, e la run scende: non e' entrata.

**La domanda aperta, precisa:** quale fase perde le 53 op. Non `cal-papd` (resta
794), non `coeff-setup-2` (1066), non `cal-tx-iqlo` (428). Va letta la tabella
completa a confronto, e se la fase che perde e' una dove la cattura mostra la
chiusura, allora la chiusura va tolta solo fra TXPHASE0 e PAPDCAL e non in generale
— che e' esattamente il tipo di distinzione che ha chiuso `coeff-setup-2`.

### La run misura op SEQUENZIALI, e i frammenti sono il difetto

Tentazione da cui guardarsi, e in cui stavo scivolando: `cal-papd` -53 e
`coeff-setup-2` -29 convivevano con i blocchi contigui in crescita, e la conclusione
comoda era «le op ci sono, sono solo in pezzi piu' corti, e' un artefatto della
metrica». **No.** La run misura op sequenziali perche' l'obiettivo e' riprodurre la
sequenza del vendore, non totalizzare op appaiate: se stanno in pezzi piu' corti,
stiamo facendo le cose giuste **nell'ordine sbagliato**, e quello e' il difetto.

Applicato a `coeff-setup-2`, ha dato la risposta in una misura. 1037 e' esattamente
il conto della funzione, e il base faceva 1066 = 1037 piu' **29 op contigue davanti**:
nel base `save_cal` e `coef_setup` erano adiacenti. La cattura conferma che devono
esserlo — `TBL.RD 15/0x50 len=8` a #21169 e `len=7` a #21187, diciotto op di distanza
e nient'altro in mezzo. Nella macchina a stati fra i due passava la chiusura e la
riapertura della parentesi, cioe' **due riprogrammazioni da 84 celle**.

Uniti `RXCAL` e `RSSICAL` in un passo: `coeff-setup-2` torna a **1066 su 1073 in UN
blocco**, `1066 +2 piccoli` contro `1037 29 +2` di prima, e il totale per fase va a
**6587**. Le 29 op erano esattamente quelle, e la forma lo dimostra meglio del numero.

Resta **cal-papd -53** e 15 op sotto il base. Non e' la parentesi, misurato; non e'
`get_tx_gains`, misurato; non e' `precal_txgain`. Il metodo che ha funzionato qui si
applica identico: la fase fa 794 in `794 2x334 220 178 +34 piccoli`, quindi trovare
quale sequenza il base teneva unita e la macchina a stati spezza, e guardare la
cattura per sapere se ha ragione il base.

### Le due op del deficit che si sono trovate, e la terza che non c'era

Tre ipotesi sul deficit di 47 op, tutte valutate con la tabella per fase, due
rifiutate e una accolta:

| ipotesi | esito |
|---|---|
| parentesi solo dove paga (non su PAPD e RSSI) | **rifiutata**: fasi ferme, blocchi 17831 -> 17673 |
| `get_tx_gains()` una volta invece di una per passo | **accolta**: `cal-papd` +3, totale 6555 -> 6558 |
| `precal_txgain` doppio, uno da togliere | **rifiutata, e il doppio serve**: `perical-ingresso` da `6x172` a `2x172`, blocchi 17830 -> 17100 |

La terza e' quella che insegna qualcosa. Sembrava un doppione introdotto da me — il
blocco differito in `initn` chiama `precal_txgain` e il passo INIT lo richiama — e
invece la **cattura ne ha due**: togliendone uno si perdono 730 op di blocchi
contigui e quattro dei sei blocchi da 172. Quello che sembra ridondante nel codice
non e' ridondante nella sequenza.

Il deficit resta **44 op** su 6602, e non e' ne' nella parentesi ne' nelle letture
di gain ne' in una duplicazione. Le tre ipotesi facili sono esaurite; la prossima
misura utile e' il delta per fase fra l'albero attuale e `aad63a3` letto sui
**blocchi** invece che sulle run, perche' `cal-papd` -53 e `coeff-setup-2` -29
convivono con blocchi contigui in crescita, e quelle due cose insieme dicono che le
op ci sono e stanno in pezzi piu' corti.

### Il deficit di 47 op non e' della parentesi, e come si controlla il build

Il debito della macchina mphase, scomposto per fase contro `aad63a3`: `cal-papd`
**-53**, `coeff-setup-2` **-29**, `cal-tx-iqlo` -15, `perical-ingresso` **+53**.
Netto -44, piu' -3 del porting PAPD.

Ipotesi: la parentesi paga su `perical-ingresso` e costa su `cal-papd` e
`coeff-setup-2`, quindi va tenuta solo dove paga. **Rifiutata dalla misura**:
togliendola su `PAPDCAL` e `RSSICAL`, `cal-papd` resta 791, `coeff-setup-2` resta
1037, il totale resta 6555 e i blocchi contigui **scendono** da 17831 a 17673. Non
e' in albero.

Quindi quelle -82 op vengono da qualcos'altro nella ristrutturazione, e i candidati
sono le op che i passi emettono **fuori** dalla parentesi: `get_tx_gains()` chiamata
una volta per passo, e il `precal_txgain` del passo INIT.

**E una nota su come si controlla un build, che e' la causa meccanica di un giro
buttato.** `make ... 2>&1 | grep error` non funziona qui: la riga di compilazione
contiene `-Werror`, quindi il grep matcha **sempre** e non distingue un build
riuscito da uno fallito. Con quel controllo un edit applicato a metà — una
sostituzione su tre andata a vuoto, con una variabile non dichiarata — e' passato per
buono, e la misura che ne e' uscita diceva 2419 op e 3498 blocchi. Il controllo
giusto e' lo **stato di uscita**:

    if make KDIR=... >/tmp/b.log 2>&1; then echo OK; else grep -E 'error:' /tmp/b.log; fi

### Contati i due versi, e la terza ritrattazione

I due versi di `b43_nphy_tx_power_ctrl()` si distinguono dal **payload**: lo
spegnimento versa 84 zeri, l'accensione il contenuto di `nphy->adj_pwr_tbl`.
Ricostruito con `trace_tables.collect()`, che rende i valori:

| | accensioni (payload con contenuto) | spegnimenti |
|---|---|---|
| vendore | 12 | 60 |
| port, flow `txpower` | **4** | 26 |

**La prima volta l'ho contato sul flow sbagliato** — `init` invece di `txpower` — e
ne e' uscito zero accensioni, da cui la conclusione che `adj_pwr_tbl` fosse sempre
vuota e che il buco fosse `recalc_txpower` che non gira. Falso su tutta la linea: la
regione `up-ch1` dichiara `flow=('txpower', '1')`, che e' init **piu'**
`recalc_txpower`, e quel flow esiste da prima proprio per questo — il commento
accanto alla regione lo spiega, e non l'ho letto prima di misurare.

Il conto vero e' **4 contro 12**: il port riempie la tabella, ma la programma con
contenuto un terzo delle volte. E questo si somma con quanto sopra invece di
sostituirlo — `recalc_txpower` gira, e la fase `recalc-txpower` fa comunque 0 su 716
con la colonna blocchi vuota, quindi il suo buco e' un'altra cosa e resta aperto.

Tre ritrattazioni su questo filo, tutte dallo stesso errore in tre forme: contare
occorrenze di un'op senza verificare cosa quell'op significhi — sui due lati del
confronto la prima volta, fra i due versi della stessa funzione la seconda, fra due
flow diversi la terza. Cio' che ha tenuto in ogni giro sono state le misure sui
blocchi e sulle fasi, che girano sul flow dichiarato dalla regione e non su quello
che passo a mano.

### RITRATTAZIONE 2: il 13 contro 36 non era un confronto

Esteso `segment_marker.py` a una **sequenza** di marcatori, per distinguere la
parentesi (lettura di `7/0x110` seguita dallo spegnimento) dalla sola lettura. E la
sequenza sul vendore da' **zero** segmenti, che e' l'informazione.

Il motivo: in b43 i due versi di `b43_nphy_tx_power_ctrl()` hanno **forme d'op
diverse**. L'accensione usa `b43_ntab_write_bulk()`, che l'harness traccia come
`TBL.WR id=26 off=0x40 len=84`; lo spegnimento scrive a mano
`b43_phy_write(TABLE_ADDR, 0x6840)` piu' 84 `DATALO`, e di `TBL.WR` non ne emette.
Il tracer del vendore invece aggancia la funzione di tabella, quindi vede **tutti e
due i versi allo stesso modo**.

I conteggi, sulla finestra `up-ch1`:

| | `TBL.WR 26/0x40 len=84` | `0x72 = 0x6840` grezzo |
|---|---|---|
| vendore | 36 | **36** |
| port | 13 | **54** |

Le 36 del vendore sono **accensioni piu' spegnimenti**, non accensioni. E il port
ne fa 13 + 54 = **67**, cioe' piu' del vendore, non meno. **Il «13 contro 36» non
era un confronto fra le stesse due cose**, e tutto quello che ci ho appeso sopra —
che mancassero 23 riprogrammazioni della tabella, che la parentesi di mphase fosse
la causa, i due tentativi di ricostruirla — poggiava su quel numero.

Cosa resta valido: la macchina a stati mphase e il porting della cal PAPD, perche'
sono misurati sui blocchi contigui e sulle fasi, non su quel conteggio. Cosa cade:
l'obiettivo «portare `adj_pwr_tbl` da 18 a 36». Non c'e' niente da portare a 36.

Per rifare il confronto per davvero serve contare i due versi separatamente **su
entrambi i lati**, e sul vendore i due versi si distinguono solo dal contesto,
perche' l'op e' identica. Il candidato e' la coppia «`TBL.WR 26/0x40 len=84` seguita
da `TBL.WR 27/0x40 len=84`»: l'accensione le fa consecutive, lo spegnimento le
separa con altre op. Da verificare, non verificato.

### RITRATTAZIONE: quel marcatore non e' della parentesi

Il ramo di abilitazione di `b43_nphy_tx_power_ctrl()` scrive `adj_pwr_tbl`
**senza nessuna condizione**: le due `b43_ntab_write_bulk(26/64)` e `(27/64)` sono
la prima cosa dell'`else`. Quindi non c'e' nessun test nascosto da trovare, e il
13 e' esattamente il numero di volte che il controllo viene **acceso**. Quello non
era mai in dubbio.

Il difetto sta nel marcatore. `TBL.RD 7/0x110 len=2` **non e' della parentesi**:
lo legge anche `b43_nphy_get_tx_gains()`, e con la condizione **opposta** —
la parentesi legge se `nphy->txpwrctrl` e' **vero**, `get_tx_gains()` legge se e'
**falso**. E la parentesi chiama `get_tx_gains()` subito dopo aver spento, quindi
una parentesi con il controllo acceso produce **due** letture e una con il
controllo spento **una**.

Percio' i «9 contro 20» di `segment_marker.py` non contano parentesi: contano una
somma di due cose con condizioni opposte, e **la conclusione che il vendore ha nove
parentesi non e' sostenuta da quella misura**. Le quattro parentesi PAPD del
commit precedente sono state messe su quella base, ed e' per questo che non hanno
mosso `adj_pwr_tbl`: la base era sbagliata, non l'esecuzione.

Cosa serve per rifarla: un marcatore che distingua i due lettori. La parentesi si
riconosce dalla lettura di `7/0x110` **seguita** dallo spegnimento del controllo,
cioe' dalla coppia, non dalla singola op. `segment_marker.py` accetta una regex su
una riga sola, quindi va esteso a una sequenza — ed e' un lavoro sullo strumento
prima che sul driver.

### Con le fasi allineate, la parentesi diventa un marcatore

La lettura del tx gain che apre ogni invocazione sta dentro un
`if (txpwrctrl != OFF)`, quindi `TBL.RD 7/0x110 len=2` marca **le parentesi in cui
il controllo di potenza era acceso**. Segmentando i due trace su quella —
`reverse-tools/segment_marker.py`, nuovo — il vendore ne ha **9** e il port **20**.

Le nove del vendore, e dove cadono:

| record | fase | quante |
|---|---|---|
| #3732 | init | 1 |
| #7038, #8080 | `perical-ingresso` | 2 |
| #8505 | `cal-tx-iqlo` | **1, non sei** |
| #12197, #12331, #13311, #13383 | `cal-papd` | **4** |
| #14977 | `cal-rx-iq` | 1 |

**Quindi la granularita' non e' una-per-fase-mphase, e la mia e' sbagliata in due
versi opposti.** Le sei parentesi sulle fasi TX sono di troppo: il vendore ne ha
**una** per tutto il blocco TX I/Q LO, ed e' per questo che `cal-tx-iqlo` fa 331
con undici passi e 428 con sei — dividerla spezza una sequenza che nella cattura e'
contigua. E ne **mancano quattro dentro `cal-papd`**, che sta a 847 su 2662.

Il conto quadra con il controllo di potenza spento durante le fasi TX: il marcatore
non c'e' perche' la lettura non avviene, non perche' la fase non giri. Il port
invece ha il controllo acceso la' dentro, e i sette segmenti da 198 op che
`segment_marker.py` mostra alternati alle sei fasi sono la parentesi che gira a
vuoto.

Cosa manca, quindi, in ordine di grandezza e non piu' a naso: **una** parentesi sul
blocco TX invece di sei, e **quattro** dentro `b43_nphy_papd_cal()` dove oggi non ce
n'e' nessuna.

### La run sbaglia in un verso, e ci sono cascato io

La colonna **blocchi** c'e' perche' la run prende il **massimo**, quindi una fase
che ripete N volte la stessa sequenza non puo' superare ~1/N per costruzione,
quanto bene la riproduca. E sono tutte le cal.

`cal-rx-iq` e' il caso limite: la run dice **7%** e la forma dice **`6x420`**, cioe'
le sei iterazioni dello sweep appaiate una per una, esatte. Misurata da sola con il
pavimento dei piani al suo ingresso, la regione fa **5418 su 5617, il 96%**, e la
sotto-regione dello sweep **4676 su 4735, il 99%**. Quella fase non e' un buco: e'
riprodotta, e cio' che resta sono ~140 op nell'**ingresso**, non nello sweep.

Questa pagina lo diceva gia' — «le sei iterazioni dello sweep sono vere e hanno la
forma giusta, ma la run piu' lunga e' **una** iterazione» — e la tabella lo
nascondeva, perche' mostrava solo `7%`. Ci sono cascato leggendo la tabella e ho
chiamato `cal-rx-iq` il buco piu' grosso rimasto: non lo era. Da cui la colonna.

Due avvertenze sul misurare una regione **da sola**, che non e' un'altra vista
dello stesso run ma un run **diverso**: `--global-run` riposiziona il pavimento dei
piani all'ingresso di quella regione, e si vede nei due versi. `cal-rx-iq` da sola
fa 96% contro il 7% della run; `coeff-setup-2` da sola fa **330 (30%)** contro
1066 (99%) nel run globale. Non sono confrontabili, e nessuno dei due numeri e'
sbagliato.

Il totale vecchio resta stampato sopra la tabella, e serve a vedere quanto sommerso
c'e': 17532 contro 6602.

`up-ch1-freddo` **e' scesa di 75 con `0024`**, ed e' l'assegnazione che
redistribuisce: della fase che `0024` aggiunge, la finestra fredda contiene le
**prime nove op**. Finisce a #32769, dove comincia il buco da 65285 record, e la
scrittura tardiva della tabella di potenza sta a **#106217**, dall'altra parte.

Quelle nove op vanno dette, perche' sono la ragione per cui la fase **non va gateata
su `!do_full_init`**: gli ultimi record della cattura fredda, #32753-32769, sono le
otto read che aprono la misura dell'idle TSSI piu' il primo override, e sono le
stesse op nello stesso ordine di #23761-23777 nella cattura calda. Quindi il vendore
la fase la comincia anche a freddo; il buco la taglia dopo nove record, e non e' la
cattura che ne mostra l'assenza. **Gatare qui vorrebbe dire gatare contro un buco**,
che e' lo stesso errore di gatare contro un conteggio a zero — la regola sulle
deroghe vale nei due sensi, e per un giro questa voce l'ha detto al rovescio.

Verificato invece che dedotto: i tre blocchi che smettono di comparire sono tutti in
fondo alla finestra (#32507, #32613, #32685) e su quella regione da sola il port e'
identico prima e dopo, 183 su 217 in 29 blocchi; e le nove fanno 9 su 14 in due
blocchi in entrambi i casi, perche' il port le emette gia' dall'idle TSSI che fa
salendo.

Ci sono arrivate con due patch. `0018` e' la cal RX IQ — il guscio di
`wlc_phy_cal_rxiq_nphy_rev3`, `b43_nphy_txpwr_index()` e **lo sweep di gain** — e
vale **+5761**, da 5791 a 11552. `0019` e' il **gain di pre-calibrazione**, e vale
altri **+811**. `0020` rimette l'indice di potenza a posto in coda alla cal PAPD,
e ne vale **+771**; `0021` lo **restituisce** subito dopo la lettura dei gain, e
vale **+491**. `0022`+`0023` chiudono la cal RX IQ con la **misura** — tono,
coefficienti, `save_cal` — e valgono **+726**; `0024` aggiunge la **coda** della cal
periodica (idle TSSI, power setup, vcocal) e vale **+456**.

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
`0020` non le recupera, e non doveva: sono localizzate e identificate.

**Le nove op sono due `TBL.WR id=0xf off=0x57` e `off=0x5f` col valore `0x2c2c`**, a
#12785 e #12867, ognuna preceduta da `PHY.MOD 0xc3 mask=0x4` — cioe' due
`stopplayback` che rimettono il **bbmult salvato**. Il vendore rimette `0x2c`, il
port `0x2e`. E la tabella di gain del port e' giusta: la cattura la scrive lei
stessa a #2194, `0x4077_002e` all'indice 10, bbmult `0x2e`. Quindi in quel punto il
vendore **non e' all'indice 10**: e' gia' tornato al 30, il cui bbmult e' `0x2c`.

**Chiuse da `0021`, e la risposta non era nel riferimento.** Chi riporta l'indice
cosi' presto non e' nessuno dei quattro punti di brcmsmac: due stanno in
`precal_txgain` sui rami phy rev < 7, uno in `wlc_phy_cal_txgainctrl_nphy`
(chiamata solo da quei rami), il quarto e' la coda di `wlc_phy_a4` che `0020` porta
e che gira **dopo** #12867. L'ha trovata `trace_tables.py --cell 0xf:0x57`, aggiunto
per questo: il bbmult fa `0x2c2c` → `0x2e2c` → `0x2e2e` mentre l'indice viene
forzato core per core, e poi torna a `0x2c2e` e `0x2c2c` a **#8096** e **#8294**,
dove il vendore esegue il ramo a **indice negativo** di `txpwr_index` — quello che
`0019` aveva lasciato fuori dicendo che non aveva chiamanti.

**Il senso del precal e' un'altra cosa da come suona:** l'indice forzato serve solo
a *leggere* dei gain, non a restare programmato. Il vendore lo forza, legge, e
restituisce subito radio gain, dac gain, bbmult e le compensazioni; le cal girano
sull'hardware di prima, coi gain letti all'indice forzato.

**Regola che ne esce: quando una cella di tabella diverge, guardare la sua storia
prima del flusso del riferimento.** `trace_tables.py --cell ID:OFF` la stampa,
letture comprese, e distingue le write che cambiano il valore da quelle idempotenti.

**E la regola gemella, che e' costata un'ora: un difetto che sembra tale va misurato
prima di crederci.** `gap-inventory.md` 4a bis diceva da sempre che il degrado
`type = 2 -> 0` in `b43_nphy_cal_rx_iq()` era un difetto. Togliendolo il port e'
peggiorato di **476 op**. Il difetto vero era un altro e a monte: b43 restringeva a
`bool` il **modo** del test DAC, che il riferimento testa `== 1`, quindi un tipo 2
costruiva il tono sulla banda sbagliata. Con quello sistemato (`0022` e la sesta
mainline) il tipo 2 e il tipo 0 danno le stesse op, come nel riferimento, e il port
porta il tipo vero senza pagarlo. Il degrado **era** un difetto, ma non quello che
si vedeva, e la misura ha indicato la direzione giusta solo dopo aver guardato
`if (dac_test_mode == 1)` nel riferimento.

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

Per regione, flow `init`, `--global-run 132 26100`, **rimisurato**:

| regione | record | op | appaiate | non conf. | su confrontabili | prima dello sweep |
|---|---|---|---|---|---|---|
| init vero e proprio | #132-10961 | 9692 | 4868 50% | **1180** | **57%** | 36% |
| cal PAPD (`a4`) | #10962-14092 | 2662 | 1933 73% | 0 | 73% | 76% |
| cal RX IQ, ingresso | #14093-15920 | 1698 | 1513 89% | 3 | 89% | 0% |
| cal RX IQ, sweep di gain | #15921-22246 | 5812 | 4921 85% | 0 | 85% | 9% |
| seconda cal RSSI | #22247-23771 | 960 | 623 65% | 0 | 65% | 0% |
| coda | #23772-26100 | 2127 | 949 45% | **176** | **49%** | 29% |

**La colonna `non conf.` e' nuova, e prima quelle op stavano nel denominatore**:
sono famiglie che il port non ha modo di emettere, perche' l'harness compila il PHY
e non il core — `OBJ.*` (1286 nella finestra), `MAC.MCTRL`/`MHF` (40), `TPL.RAMW`
(19), `GPIO.OUT` (12) — e la object memory ha comunque l'encoding non confrontabile
di `o708`/`o70e`. **`coverage.py` le escludeva e lo dichiarava, `phase_compare.py`
no**: era un'incoerenza fra i due strumenti, chiusa. Il totale in blocchi contigui
**non** le esclude, di proposito: la colonna dice contro cosa si misura, non gonfia
il verdetto.

Dove cadono e' la parte interessante: **nelle quattro regioni di calibrazione sono
zero**, quindi quelle percentuali erano gia' oneste; tutte e 1356 stanno nell'init e
nella coda, che sono le due regioni dove il core lavora.

La cal PAPD scende di tre punti e **non e' una regressione**: misurata da sola la
regione fa 2023 su 2662 (76%), e la differenza e' l'assegnazione esclusiva, che con
piu' blocchi in gara redistribuisce. Vale la regola di sopra: quando un numero
scende, misurare la regione da sola prima di crederci.

**L'init vero e proprio resta il buco piu' grosso**, anche col denominatore giusto:
3643 op confrontabili non appaiate su 8511. Il buco singolo piu' grande della
finestra sta li', **3099 op dopo #2172**, e un terzo di quello e' object memory: le
op confrontabili sono ~2155, quasi tutte scritture delle tabelle 26/27 (128, 84 e 64
celle) che il port fa, ma in un punto diverso della sequenza. Prima di cercare codice
mancante li', conviene guardare l'**ordine**.

Il totale della global run **non si guarda**: e' oscillato 5953 → 7075 → 5783 su
cambiamenti che hanno solo migliorato la fedelta', perche' l'assegnazione dei
blocchi e' esclusiva e un blocco lungo altrove si porta via le op. Il numero da
guardare e' `up-ch1`. La cal PAPD e' salita da 26% a 68% perche' il suo guscio c'e'
(`patches/b43/MESSAGES.md#0015`): restano fuori `a3`/`a2`, due buchi da 349 e 276 op.

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
| `up-ch1` | `opinit-*`, init a caldo | `txpower` | 22943 | **18462, 80%** |
| `up-ch1-freddo` | `full-init-*`, init completo | `initpor` | 27563 | **18163, 66%** |

`up-ch1` comincia dove comincia `switch_channel` — la `CHANSPEC` di **#132**, che
il tracer emette e il port no — e finisce col **MAC abilitato che trasmette**,
#26100. Nessuna ancora: la finestra e' tutta la run, quindi i blocchi si trovano
sull'intero output del flow senza agganciarsi a un'op scelta a mano.

`up-ch1-freddo` parte dalla `CHANSPEC` di **#339** e finisce a **#32769**, che non
e' il MAC abilitato ma il limite di confrontabilita': quella cattura ha un buco da
65285 record oltre quel punto. Copre **piu'** dell'altra perche' contiene il
download delle tabelle statiche, che a caldo non c'e' — si vedono come blocchi da
**1424** e **806** op, che sono le due vecchie finestre `static-tables`.

**Il parametro giusto adesso c'e': `patches/b43/MESSAGES.md#0017`.**
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
  E non basta che *un* accessor della famiglia sia agganciato: **si guarda da che
  accessor passa quell'accesso.** Ci sono ricaduto sulla object memory —
  `write_objmem16` era agganciata, quindi ho concluso che una regione letta 192
  volte e mai scritta la scrivesse l'ucode. La scrive `copyto_objmem`, che dentro
  chiama `write_objmem` e non la variante `*16`, e non era agganciata. Quattro hook
  aggiunti, vedi `gap-inventory.md` 4i.
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
  codice condiviso: `b43/MESSAGES.md#0010` e la mainline
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

`patches/mainline/` sono i **sei** indipendenti da questo hardware, da mandare per
primi e come **sei `[PATCH]` separate in altrettanti thread**, non come serie: non
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
set `do_init` di **brcmsmac**, che e' piu' vecchio. `patches/b43/MESSAGES.md#0013`, non provata su
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
   con segno, uno rumore attorno a zero. `patches/b43/MESSAGES.md#0015` aggiunge i nomi
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
2. **Il cursore dei piani era avvelenato al primo hit, ed e' chiuso: ora e' per
   indirizzo.** Era uno, globale e monotono, e il primo `planhit` di tutta la run
   era `PHY 0x7a` servito dal record **14999** — il vendore quel registro lo legge
   solo dentro la cal RX IQ, il port all'init — da cui tutto sotto il 15000
   irraggiungibile. Chiuso: `saltate` da 923 a **0**, `fuori posizione` da 8823 a
   **524**. **Ma il verdetto per fase si e' mosso di 13 op**, da 5911 a 5924: servire
   al port tre volte e mezzo i valori della cattura non compra niente, quindi cio'
   che resta aperto non e' l'harness che non risponde. Resta buona la prima delle due
   strade: **regioni contigue**, dove l'ordine delle read e' lo stesso per
   costruzione (fatto per la cal PAPD, `CONTIG` in
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
