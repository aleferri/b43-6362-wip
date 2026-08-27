# test/ — harness di verifica in userspace

Compila i sorgenti N-PHY di b43 **presi da un tree kernel, senza modificarli**,
li fa girare in userspace con uno shim che intercetta ogni accesso all'hardware,
ed emette un trace nel formato di `wl-diag` decodificato. Serve a confrontare
op-per-op quello che il driver fa con quello che il driver proprietario fa nella
cattura sotto `router-data/`.

## Uso

```sh
make KDIR=~/src/linux            # costruisce
./phase_compare.py --vendor ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
./nphy_trace init dsl3580l       # flow di init, trace su stdout
./nphy_trace initpor dsl3580l    # solo l'init a freddo (do_full_init)
./nphy_trace chanset dsl3580l 6  # init poi cambio a canale 6
./nphy_trace rfkill dsl3580l
make compare FLOW=init REF=../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
```

Per provare una patch: si applica **al tree** e si rifà `make`. Le copie in
`build/src/` hanno il sorgente del tree come prerequisito, quindi si aggiornano da
sole e non serve `make clean`. Il prerequisito e' per file di proposito: con uno
stamp unico la copia resta vecchia in silenzio e si misura il codice sbagliato
credendo di misurare la patch.

Il repo non tiene una copia dei sorgenti del driver.

## Come sta insieme

- I `.c` del kernel fanno `#include "b43.h"`, che con le virgolette risolve nella
  loro directory e tirerebbe dentro spinlock, bcma, ssb, ieee80211. Quindi il
  Makefile li **copia** in `build/src/` insieme ai soli header che vogliamo veri
  (`phy_n.h`, `phy_common.h`, `ppr.h`, `tables_nphy.h`, `radio_205{5,6,7}.h`), e
  `b43.h`/`main.h` arrivano da `stubs/`. Copia, mai modifica.
- Compilati: `phy_n.c`, `radio_2057.c`, `tables_nphy.c`, `ppr.c` e
  `lib/math/cordic.c` — quest'ultimo vero, perché i valori del cordic finiscono
  nei registri e uno stub li falserebbe.
- `wrap.c` implementa gli accessor (PHY, radio, MMIO, SHM, MAC) emettendo una
  riga per op, con mirror di memoria per le write. **E un mirror delle tabelle**,
  `tbl_mirror`, keyed su `(id, offset)`: senza, una lettura di tabella passa
  dalla porta dati `0x73` e riprende l'ultima cella scritta da qualunque parte
  invece di quella richiesta.
  Il mirror lo serve `tbl_port_get()` **alla porta dati**, cioe' dentro
  `b43_phy_read` per `0x73` e `0x74`, usando `(id << 10) | off` dall'ultima
  scrittura su `0x72` — non solo al valore di ritorno di `b43_ntab_read`, o il
  driver legge la cella giusta e il trace mostra il mirror del registro. Serve la
  cella **sempre**, anche se nessuno l'ha scritta —
  `tbl_mirror` parte a zero e zero e' la risposta giusta, perche' quelle due
  porte non sono registri e il loro mirror non significa niente — e in lettura
  fa **avanzare l'indirizzo** come l'hardware: la read di `0x73` aggancia la
  cella intera e incrementa, quella di `0x74` rende la word alta agganciata. Le
  due porte si visitano in ordine opposto nei due versi (`0x73` poi `0x74` in
  lettura, `0x74` poi `0x73` in scrittura), e senza l'aggancio l'incremento
  sulla word bassa spingerebbe la lettura della word alta sulla cella dopo.
  Si vede sulla banda del filtro passa-basso che la cal PAPD rilegge da
  `7/0x154`. Le `b43_ntab_*` invece stanno
  in `tables_nphy.c` che compiliamo, quindi si intercettano al linker con
  `--wrap` e poi si chiama la `__real_`: nel trace escono l'etichetta `TBL.WR` e
  le `PHY.WR` su 0x72/0x73/0x74 che ne discendono, come nella cattura.
- `main.c` monta un `struct b43_wldev` finto e chiama una voce di
  `b43_phyops_n`. I valori della board sono decodificati dalla SROM del device.
- `compare.py` normalizza i due lati (via timestamp, numero di record, colonna
  cpu; `PHY.OR`/`PHY.AND` unificate a `PHY.MOD`) e diffa.

## Warning

Due set di flag, perché i due lati hanno responsabilità diverse.

**I nostri file** (`wrap.c`, `main.c`): `-Wall -Wextra -Werror`. L'unica deroga è
`-Wno-unused-parameter`, perché le firme degli accessor le decide il driver.

**I sorgenti del kernel**: warning accesi ma non fatali, perché li compila un
compilatore host con flag diversi da quelli con cui nascono e non possiamo
correggerli (non si modifica il tree). Tre classi restano però **fatali**, perché
non parlano del kernel, parlano dei nostri stub:

    -Werror=implicit-function-declaration
    -Werror=implicit-int
    -Werror=incompatible-pointer-types

Se una di queste scatta, l'harness sta girando su un modello sbagliato
dell'ambiente e il trace che produce non vale niente. Non è teoria: al primo giro
con i warning spenti erano passate tre funzioni senza prototipo —
`b43_current_band`, `cfg80211_get_chandef_type`,
`b43_wireless_core_phy_pll_reset` — che il chiamante vedeva tornare `int`. La
prima ritorna una enum, e su un'altra ABI quel trace sarebbe stato spazzatura
silenziosa.

`make warncheck` ricompila da zero e confronta l'insieme dei warning dei sorgenti
kernel con `expected-warnings.txt`, normalizzando via i numeri di riga (si
spostano a ogni aggiornamento del tree). Oggi la lista attesa ha una voce:
`-Wswitch` su `B43_BUS_SSB`, perché `CONFIG_B43_SSB` è spento per scelta — quel
core sta su bcma. Se l'insieme cambia, qualcuno ha toccato il tree o gli stub.

`CONFIG_B43_BCMA` invece è **acceso**, e ce l'ha fatto notare `-Wswitch`: senza,
i rami bus-specific sparivano e con loro le op GPIO e ChipCommon, che nella
cattura vendor ci sono. Nel flow `init` di questa board non vengono comunque
raggiunti, ma compilati fuori non avrebbero mai potuto comparire.

## Stub: generati dove si può

- `stubs/sprom.h` — `struct ssb_sprom` **copiata verbatim** dal kernel: i nomi
  dei campi devono combaciare, riscriverli a mano è il modo migliore di
  introdurre una differenza muta.
- `stubs/b43_defs.h` — 488 define e 7 enum estratte da `b43.h`. I commenti sono
  rimossi di proposito: la prima versione li copiava e `B43_BFH_FEM_BT` ha un
  `/*` che continua sulla riga dopo, quindi il commento troncato si mangiava le
  define successive.
- `stubs/bcma_ids.h` — le define bcma/ssb citate dai sorgenti.
- `stubs/b43.h` è scritto a mano ma ridotto ai soli campi usati. La riduzione la
  verifica il compilatore: se il driver ne tocca uno che manca, il build si
  ferma.

## Il seme degli offset di potenza

Dopo l'init a freddo, e sempre non tracciato, gira un `recalc_txpower`: e' quello che
riempie `nphy->tx_power_offset[]`, e senza di lui la tabella di potenza aggiustata
esce a zeri per tutto l'init tracciato, dove il vendore la scrive col contenuto
(#2000 e #2086). La cattura e' un init a caldo e il driver del vendore quegli offset
li ha dal boot prima.

Prima di chiamarlo si spegne `perical_pending`, o il recalc si tira dietro la sequenza
differita della cal periodica, che rifa' la cal RSSI e riscrive la cache: il secondo
init restaurerebbe quella invece di quella del primo init. Costa 479 op su `up-ch1` e
fa perdere l'ancora alla finestra `rssi-cal`.

## Il seme della cal RSSI

Delle quattro chanspec di calibrazione, `rssical_chanspec_2G` **non** si azzera fra i
due init. La ragione sta nella
cattura: e' un init a caldo, e il vendore al primo passo RSSI **restaura** invece di
calibrare — fra #132 e #8000 legge `0x219` una volta sola, zero poll, e a #3712-#3731
scrive i due registri radio e i dodici PHY di fila. Azzerando la chanspec il port
prendeva la strada della calibrazione, 1052 op che il vendore non ha e che valevano
841 op sulla somma delle run.

Le altre tre si azzerano, perche' la cattura la cal TX I/Q LO e la RX I/Q le contiene.

I valori della cache **non si seminano**: ce li mette il primo init, che la
calibrazione la fa, e ne escono i due registri radio e undici dei dodici PHY identici
alla cattura. Copiarli a mano dalla cattura vale una op su `up-ch1`, che non paga
quattordici costanti dentro il banco. L'unico che differisce e' `0x1ac`, l'offset fine
narrowband del core 0 sulla rail Q: 0 contro 1.

E a freddo non c'e' niente contro cui verificare: `full-init-ch1-bw20` la cal RSSI la
comincia a #32637 e a #32769 parte il buco da 65285 record.

## L'init a freddo e quello a caldo

Il flow `init` fa **due** init: il primo con `do_full_init` vero e **non
tracciato**, il secondo col flag azzerato, e il secondo e' quello che si
confronta. I piani di lettura si ricaricano fra i due, perche' rappresentano le
read del secondo e le consuma anche il primo, che gira per davvero.

Il motivo sta in `docs/init-flow.md`: `do_full_init` in b43 e' `phy_init_por` in
brcmsmac, e la cattura non e' un init a freddo — l'apertura della tabella 10 con
cui comincia il download statico non compare in nessuno dei suoi due init.
Modellare sempre l'init a freddo metteva 8320 op di prefisso che nel riferimento
non ci sono: il flow e' passato da 13223 a 4903 op, e i coefficienti della cal
RSSI hanno smesso di sbagliare di un LSB perche' i piani non vengono piu'
consumati dalle read che solo l'init a freddo fa.

`initpor` fa solo l'init a freddo, per guardare cosa scrive: non si confronta con
questa cattura, perche' una cattura che parta dal power-on reset non c'e'.

## Cosa NON simula

- Le attese (`udelay`, `msleep`) sono silenziose: nella cattura vendor non c'è
  un solo record `DELAY`, quindi emetterli qui sfaserebbe ogni confronto.
- `b43_radio_wait_value` dichiara riuscita la prima lettura. Senza un piano il
  mirror non convergerebbe mai; nel trace la cosa resta visibile come una sola
  `RAD.RD` invece di N.
- I percorsi radio 2055 e 2056 (N-PHY rev 1-6) **abortiscono**: sul rev 8 non
  vengono mai chiamati, e se il flow ci finisce il device è montato male. Meglio
  fermarsi che restituire zero in silenzio.
- Le read senza piano ritornano il mirror. Per riprodurre i rami che dipendono
  dallo stato dell'hardware servono i piani di lettura, da costruire dai
  `RETVAL` della cattura (`b43_test_plan_{phy,radio,mmio}_reads`).

## Cosa ha già trovato

Col rollup applicato al tree, la modifica `patches/b43/MESSAGES.md#0001` fa
riprodurre al flow `init` il blocco di
gain control della cattura **op per op**: 0x1c e 0x32 con il bit 13, 0x289=0x46,
0x283=0x44, 0x280=0x44, le otto table-op (LNA1, LNA2, TIA gain, gain bits per
core) con i payload identici, i clip1 low gain code 0x37/0x2ad=0x74 e
0x38/0x2ae=0x18, e 0x300/0x301=0x18. Senza la patch quei registri non vengono
scritti affatto, che è il comportamento dello stub in mainline.

Il flow `chanset` riproduce il cambio canale: tutti e 18 i registri della
chantab 2.4 GHz con gli stessi valori e nello stesso ordine del vendore, provato
su canale 6. E rende visibile il buco noto: i dieci registri 5 GHz che il vendore
azzera a ogni cambio canale (`LOGEN_MX5G_TUNE`, `PGA_BOOST_TUNE_CORE0/1`,
`TXMIX5G_*`, `PAD5G_*`, `LNA5G_*`) dal lato port non ci sono, perché b43 usa la
variante `chantabent_rev7_2g`.

Le due finestre della **tabella dei campioni** hanno trovato il difetto più
grosso finora, e in mainline, non nel port. La tabella 17 è il tono che ogni
calibrazione che suona campioni usa come stimolo, e b43 non ne produceva uno:
`b43_nphy_gen_load_samples()` teneva il passo di fase in una `u16` dopo averlo
moltiplicato per 2^16, e per tutte le frequenze che il driver chiede quel
prodotto è un multiplo esatto di 65536, quindi il passo troncava a **zero** e i
160 campioni uscivano tutti uguali; e `b43_nphy_load_samples()` mascherava con
`0x3FF << 10` invece di spostare il valore mascherato, buttando via la componente
in fase. `patches/b43/MESSAGES.md#0010` chiude i due, e le 160 word diventano identiche alla
cattura. Senza la patch `sampleplay-iqlo` fa 2/322, con la patch 322/322: è la
misura di quanto valga avere la finestra.

Ha anche corretto la mappa della cal: `papd-tone` cercava `0x186` con `val=0x100`,
un valore che nella cattura non esiste, perché `0x186`-`0x194` non è il tono ma
sono i coefficienti del filtro digitale TX (vedi `docs/papd-cal-map.md`). Una
finestra `pending` con un'ancora impossibile non fallisce mai e non dice mai
niente: è il modo più silenzioso di sbagliarsi.

Il confronto ha anche trovato un difetto dell'harness, non del driver: `chanset`
chiamava `switch_channel(dev, 6)` senza aggiornare `hw->conf.chandef`, che è
quello che mac80211 fa prima di invocare l'op, e il port programmava la chantab
del canale vecchio. Si vedeva in due registri, 0x16 e 0x2c — vcocal e mmd0, cioè
proprio quelli che dipendono dalla frequenza.

## Quanto lontano arriva

Due misure, e servono a cose diverse. **La forte è quella posizionale**, e per
troppo tempo ho usato solo l'altra.

### phase_compare.py — confronto posizionale per finestre

È il metodo di `b43-ac-wip`: `compare.py` normalizza i due lati e diffa op per
op, con `--range` per limitare la cattura a una finestra e `--align-on` per
agganciare l'output dell'harness al primo op di quella finestra.

Sull'init **intero** non si allinea, e non è un limite del metodo: b43 e il
driver proprietario ordinano le fasi in modo diverso, il port comincia dalle
tabelle e il vendore dal radio. Dentro una fase si allinea benissimo.
`phase_compare.py` tiene la tabella delle finestre riconosciute e le confronta
tutte:

| finestra | op | run | esito |
|---|---|---|---|
| gain-control (`0008`+`0001`) | 87 | **87/87** | **ok** |
| papd-comp (`0003`) | 16 | **16/16** | **ok** |
| papd-tables (`0004`+`0012`+`0015`) | 774 | **774/774** | **ok** |
| ipa-bias (`0005`) | 3 | **3/3** | **ok** |
| static-tables (`initpor`) | 1424 | **1424/1424** | **ok** |
| static-tables-2 (`initpor`) | 806 | **806/806** | **ok** |
| sampleplay-tssi | 322 | **322/322** | **ok** |
| sampleplay-iqlo (`0010`) | 322 | **322/322** | **ok** |
| txdigi-filts | 60 | 45/60 | mancano 15, e sono **idempotenti**: il vendore riscrive `0x195`-`0x1a3` con gli stessi valori |
| chanswitch-ch6 (`0011`) | 39 | 33/39 | **nessuna op mancante**; la coda è sfasata di tre per gli MMIO che il vendore non registra |
| tssi-setup | 19 | 5/19 | mancano 4, in più 15: il `0x17b` di troppo e lo sfasamento |
| rssi-cal | 16 | 11/16 | mancano 5, in più 3: i nove coefficienti combaciano, le mancanti sono `PHY.RD` su `0x73`, che i piani escludono di proposito |
| papd-digifilt (`0015`) | 15 | **15/15** | **ok** |

### Le finestre, che sono due: `CONTIG`

`CONTIG` ha **due** voci, la stessa macro operazione nei suoi due comportamenti:
`up-ch1` (init a caldo, `opinit-*`, flow `init`) da **22943 op, 16242 in blocchi
contigui, 71%**, e `up-ch1-freddo` (init completo, `full-init-*`, flow `initpor`)
da **27563 op, 17615, 64%**. Due e non una perche' il tipo di calibrazione cambia
il comportamento — `full_cal` contro `soft`, e i buchi di `a3`/`a2` passano da 349
e 276 op a 920 e 930 — quindi una fase di cal verificata contro una cattura sola
valida un ramo e tace sull'altro. La seconda copre piu' della prima perche'
contiene il download delle tabelle statiche.

Con `patches/b43/MESSAGES.md#0017` il port sceglie full o parziale come il riferimento invece
di inchiodare `true`. Su queste due catture non cambia niente — sono entrambe di
un'interfaccia che sale su un canale non calibrato, quindi il test viene `full` in
tutte e due — ma ha fatto uscire un buco qui: `main.c` azzerava fra i due init
`rssical_chanspec` e `iqcal_chanspec` e non `txiqlocal_chanspec`, e un secondo init
che la trovava valorizzata prendeva la strada parziale, **−24 op** su `up-ch1`. Le
tre parti dello stato di cal si azzerano insieme. Non ha ancora — i blocchi si cercano su tutto l'output del flow —
e il verdetto e' la struttura dei blocchi, non la percentuale: un blocco che si
accorcia e' una regressione anche se il totale sale.

Le region per fase sono state provate e togliere, quattro in altrettante sessioni.
Il motivo non e' estetico: **una fase presa da sola non dice niente su cio' che le
arriva addosso da prima**. `chanswitch-ch6` diceva 33/39 e "nessuna op mancante";
la fase intera sta al 14%, perche' 200 op su 321 sono un ciclo di 100+100 read
consecutive su `0x1c9`/`0x1ca` che il port non fa affatto, e che nessuno ha ancora
attribuito (`CLAUDE.md`, "Cosa resta aperto", ACI scan). Una finestra che passa mentre la fase
e' al 14% e' peggio di nessuna finestra.

I confronti per fase restano nelle **finestre** qui sopra, che sono il dettaglio;
`up-ch1` e' la misura.

### I seed

Lo stato che la finestra non puo' avere lo semina
`reverse-tools/gen_seed.py --before 132` in `test/seed_up.h`, applicato da `main.c`
dopo l'init a freddo e prima di quello tracciato. Si semina **solo cio' che
precede la finestra**: seminare lo stato prodotto dentro farebbe tornare giusto per
magia un registro che il port programma male.

Due categorie: quello che `op_init` e `rfkill` hanno programmato, e quello il cui
**primo accesso e' una read**, cioe' il default del chip — criterio che non e' "mai
scritto", perche' `0x17d` la cal la scrive dopo averla letta. Le due `atten` del
coupler a `0xaa` entrano per questa via.

**Valgono 32 op su 22951**: 5130 senza, 5130 coi soli seed di `op_init`+`rfkill`,
5162 coi default. Il resto del divario e' codice che manca, non stato.
`B43_TEST_NOSEED=1` li disattiva.

La colonna **run** è la sequenza consecutiva più lunga che combacia, su quante op
ha la finestra: dice fin dove le due sequenze stanno insieme, che è più
informativo del conteggio dei mismatch. E accanto a ogni finestra che diverge
c'è la diagnosi per **multiinsieme** — quante op del vendore mancano e quante ne
fa il port in più, valori compresi — perché "36 differenze posizionali" non fa
capire niente e "mancano 10" sì.

### Le equivalenze, calcolate e non dichiarate

Due rese diverse della stessa cosa si riducono, e la riduzione si ricava dai
dati invece di essere assunta:

- **`PHY.OR`/`PHY.AND` contro `PHY.MOD`**: b43 usa `b43_phy_set`/`b43_phy_mask`,
  il vendore `phy_reg_mod`. Si portano tutte alla forma della mod, dove `val` è
  il valore del campo e `mask` il campo modificato.
- **le ombre di una read-modify-write**: il tracer aggancia sia
  `mod_radio_reg` sia la `read_radio_reg`/`write_radio_reg` che quella chiama, e
  la stessa RMW finisce nel trace come **tre** op. b43 ne registra una. Le due
  ombre si scartano, ma solo se seguono immediatamente una `MOD` sullo stesso
  indirizzo — una `RD` o `WR` isolata è l'op vera e resta.

La seconda ha ripagato subito: il vcocal del cambio canale sembrava mancare (8
op) e non mancava, e i "mancanti" di quella finestra sono scesi a 10, che sono
esattamente i campi 5 GHz della voce 5b.

Un "ok" qui dice una cosa forte: in quella fase il port fa le stesse op, con gli
stessi valori, nello stesso ordine. E paga: allargando la finestra
`gain-control` da #685 a #680 sono venute fuori quattro scritture di soglie CRS
che nessuno faceva (`patches/b43/MESSAGES.md#0008`), e una `PHY.RD` di troppo nella guardia
di `0001`, che leggeva `BANDCTL` dall'hardware dove b43 usa lo stato software. E le due divergenze note sono localizzate,
non solo contate — la cattura dice che i dieci campi 5 GHz della voce 5b vanno
scritti **in mezzo** alla sequenza (0x43 dopo 0x41, 0x4a dopo 0x47), non in coda.

C'è anche `--global-run DA A`, che non scegli una fase a mano: prende tutta la
finestra del vendore e tutto l'output del flow, e riporta le run più lunghe. Sul
primo init (`--global-run 132 26100`, flow `init`): **1543 op consecutive** (dal
caricamento della TX gain table in poi), poi 323, 266, 260, e in totale 4434 op
in comune su 22951 in 466 blocchi. Col flow `full` sono 5398 su 22951, in 677
blocchi. È la misura più onesta di dove sta il port: copre pezzi, e i pezzi sono
contigui.

Serve `merge_retvals.py` sulla cattura prima di confrontare: senza, le 11049 righe
`RETVAL` entrano nel diff come op a sé e sfasano tutto. `phase_compare.py` lo fa da
solo.

### coverage.py — copertura per insiemi

Misura quali registri e quali celle di tabella il vendore scrive e il port no.
Non è posizionale: serve a dire *quanto* manca e a trovare le voci al contrario,
non a dire se l'ordine è giusto. Utile per orientarsi, debole come garanzia.

Le celle si contano **espandendo le table-op**: un'op di lunghezza N copre N
celle. Contarla come una sola sottostima il port, che scrive in bulk dove il vendore
scrive cella per cella.

Contro il primo init della cattura (record 132-26100), flow `full`:

| | mainline | +`0001`..`0003` | +`0004` | +`0005` | serie intera |
|---|---|---|---|---|---|
| registri PHY | 175/218 (80%) | 186/218 (85%) | 186/218 (85%) | 186/218 (85%) | **190/218 (87%)** |
| registri radio | 39/54 (72%) | 39/54 (72%) | 39/54 (72%) | 40/54 (74%) | **50/54 (93%)** |
| celle di tabella | 878/1987 (44%) | 1190/1987 (60%) | 1446/1987 (73%) | 1446/1987 (73%) | 1446/1987 (73%) |
| op emesse | 14490 | 15597 | 16117 | 16117 | 16131 |

I quattro registri PHY in più dell'ultima colonna sono le soglie CRS di `0008`.
**`0010` non muove nulla in questa tabella**, e non è un difetto della patch: le
celle della tabella 17 b43 le scriveva già, solo col contenuto sbagliato, e questa
misura guarda quali celle vengono toccate e non cosa ci finisce dentro. È la
dimostrazione più netta del limite della copertura per insiemi: il difetto della
tabella dei campioni non poteva uscire da qui, l'ha trovato il confronto
posizionale.

Il flow `initcal` accende la calibrazione mettendo `nphy->perical = 0` **dal
main dell'harness**, dopo `prepare_structs`. Quel knob deve restare qui:
`b43_nphy_op_prepare_structs()` è comune a ogni N-PHY, e cambiare `perical` lì
cambierebbe l'init di tutti i device che non possiamo provare. Vedi
`docs/upstreaming.md`.

`full` è la corsa più lunga che gli ingressi pubblici permettono: init con la
calibrazione accesa, poi `recalc_txpower`, poi un cambio canale. Non è una
sequenza che sul device capita così: serve a misurare la copertura, non a
riprodurre una run reale.

Il confronto è **sulle celle e sui registri toccati, non posizionale**: dove il
vendore scrive 64 celle una per una e il port ne fa una bulk, lo stato della
tabella è lo stesso e la sequenza di op no.

`phase_compare.py` fa la stessa esclusione da quando la tabella per regione ha la
colonna `non conf.`: prima quelle op stavano nel denominatore delle regioni e le
diluivano — 1180 su 9692 nell'init, 176 su 2127 nella coda, **zero** in tutte e
quattro le regioni di calibrazione. Il totale in blocchi contigui non le esclude di
proposito.

Dei 677 offset SHM che il vendore tocca il port ne scrive due, e `coverage.py`
non li confronta: sono `o708`/`o70e`, con l'encoding diverso spiegato sotto. Gli
altri 675 li scrive il core di b43, che non compiliamo — qui c'è solo il PHY.

Cosa resta fuori, e perché:

- **tabelle 26 e 27** a offset 576, la compensazione PAPD: era l'early return di
  `b43_nphy_tx_gain_table_upload()`, chiuso da `patches/b43/MESSAGES.md#0003`.
- **tabelle 31, 32, 33, 34**, cioè epsilon e scalare del PAPD: b43 accendeva il
  motore PAPD senza inizializzare le tabelle che legge. Chiuso da
  `patches/b43/MESSAGES.md#0004`.
- **i registri di gain 0x9a-0x9d, 0x129-0x12b, 0x1df, 0x1e1** e gli altri 28
  ancora scoperti (`--details` li elenca): da attribuire, non ancora guardati.
  I quattro radio che restano sono `0x17d`/`0x17e`/`0x19d`/`0x19e`, i
  `TXRXCOUPLE_2G` del setup della cal PAPD, che non è portato.
## Piani di lettura, e cosa NON spiegano

`readplans_init.h` è generato da `reverse-tools/gen_readplans.py`: appaia ogni
read della cattura col suo `RETVAL` ed emette, per indirizzo, la sequenza di
valori che l'hardware ha restituito. 149 piani, 2089 read appaiate su 2089. Le
read del port che hanno un piano ottengono quei valori invece del mirror;
`B43_TEST_NOPLANS=1` li disattiva.

Fuori dai piani stanno 0x72, 0x73 e 0x74: sono la porta di accesso alle tabelle, e
rigiocarci i valori della cattura non riproduce niente — nel port quelle read
servono a leggere una tabella, e il valore giusto è quello che la tabella
contiene. Con dentro anche loro, il piano di 0x73 veniva consumato 185 volte e
falsava tutti i `b43_ntab_read`.

**I piani sono una coda per indirizzo, e non sanno da che punto della cattura
vengono i valori.** Il port consuma il piano di un indirizzo nell'ordine in cui
lo legge, quindi basta che faccia una read in meno del vendore prima di una fase
perche' tutti i valori di quella fase arrivino sfasati di uno. Non e' un problema
di capienza: misurato, **zero piani in overrun** sia con `0014` sia senza, tutti
i 149 hanno entry di scorta. Il conto dei consumi cambia (0x8f passa da 1/28 a
23/28 con `0014`), la posizione no.

Da qui viene la cal RSSI: il vendore calcola `0x1b8 = 0x3f` e otto `0x3e`, il
port nove `0x3f`. La finestra `rssi-cal` dava 11/16 per un motivo che non era
quello scritto qui: il secondo init prendeva la strada del **restore** e
riscriveva la cache calcolata dal primo init, che i valori giusti li aveva
azzeccati. Con `0014` il primo init ricalcola quella cache e la finestra crolla a
1/16 — ma anche prima non stava misurando una cal, stava misurando una copia. Ora
il flow azzera le chanspec di cal fra i due init, cosi' il secondo rifa' le cal
come la cattura, e la finestra dice il vero: 1/16, un LSB di differenza.

## Piani posizionali: il meccanismo c'e', la vittoria no

Le entry dei piani ora si portano dietro il **numero di record** della cattura da
cui vengono (`gen_readplans.py` lo emette in un secondo array), e `plan_get()`
serve la prima entry che viene dal cursore in poi invece della prossima in coda.
Quando per un indirizzo non c'e' nessuna entry dal cursore in avanti, la read
cade sul mirror e il contatore lo dice: prima al suo posto usciva uno zero, che e'
la bugia piu' silenziosa possibile.

Con `B43_TEST_PLANDBG=1` ogni hit e ogni miss escono con il record servito e il
cursore. E' quello che ha trovato il difetto vero, che non era la posizione:
**`gen_readplans.py` troncava ogni piano a 64 valori** (`--max-len`, default 64).
Il port legge `0x219` e `0x21a` 161 volte a testa nella cal RSSI, il vendore 152
volte nella sola regione della seconda cal e 324 in tutta la cattura: con 64 entry
il piano finiva subito e le altre 97 read per indirizzo — **le 194 "fuori
posizione"**, tutte su questi due registri — leggevano il mirror. La cal mediava
mezza cattura e mezzo specchio.

Rigenerato con `--max-len 512`, i due piani hanno 162 entry, il port ne consuma
161, e i contatori vanno a **zero fuori posizione e zero saltate**. Ora i valori
che la cal RSSI media vengono davvero dalla cattura.

### Ma il cursore e' uno, ed e' avvelenato al primo hit

Quel "zero fuori posizione" vale per `0x219` e `0x21a`, non per la run. Il cursore
e' **globale e monotono**, e il primo `planhit` di tutta la run e' questo:

    planhit PHY 0x007a rec 14999 cursore 0

Il piano di `PHY 0x7a` ha tre entry, ai record `{14999, 18079, 22291}`: il vendore
quel registro lo legge **solo dentro la cal RX IQ**, il port lo legge nell'init.
Una read fuori ordine, e da li' in poi il cursore sta a 15000: tutto quello che il
vendore ha letto prima del record 15000 diventa irraggiungibile per il resto della
run. Si vede in chiaro su un indirizzo con una sola entry a inizio init:

    planmiss RAD 0x016b cursore 26067 ultima 553

### Il cursore e' per indirizzo

La seconda delle due strade e' fatta, e la prima — **regioni contigue**, `CONTIG`
sopra — resta e paga come prima. Ogni piano ha il suo cursore, e `plan_pos` e' solo
il pavimento comune da cui partono, l'ingresso della regione sotto misura.

L'invariante che regge e' **per indirizzo**: le read che il port fa di un indirizzo
sono una sottosequenza di quelle che il vendore fa dello stesso indirizzo. Quella
globale, sull'interleaving fra indirizzi diversi, non regge, e `PHY 0x7a` lo
dimostra. Il prezzo e' l'altro verso: se il port salta una read di un indirizzo, i
valori successivi **di quell'indirizzo** si sfasano di uno. Sfasa uno per volta
invece di tutti, e un valore sfasato rompe la run come la rompe un'op mancante,
quindi la misura per fase lo vede.

Misurato, flow `init` contro `opinit-ch1-ch6-bw20`, colonne del report sommate:

| | consumati | saltate | fuori posizione |
|---|---|---|---|
| cursore globale | 1496 | 923 | 8823 |
| per indirizzo | 1035 | **0** | **524** |

Contate invece come righe `planhit`/`planmiss` con `B43_TEST_PLANDBG=1`: da
**585 servite e 18221 mancate** a **2074 e 1058**.

**E il verdetto per fase si e' mosso di 13 op**, da 5911 a 5924, con i blocchi
contigui da 16242 a 16392. Questo e' il risultato, non i contatori: servire al port
tre volte e mezzo i valori della cattura non ha comprato quasi niente, quindi cio'
che resta aperto **non e' l'harness che non risponde alle read**. E' la sequenza di
op del port che diverge davvero.

Ed e' stato subito vero: guardando la sequenza invece dei valori, la cal TX I/Q LO
ha reso un difetto di mainline — le write combaciavano e mancavano 445 **read**,
tutte su `0xc0`, perche' il polling aspettava il contrario di quello che doveva.
Vedi `CLAUDE.md`. Ma il cursore per indirizzo e' cio' che rende quel fix
misurabile: senza i valori del piano di `0xc0` serviti in ordine, il ciclo corretto
non avrebbe modo di girare 455 volte.

Una fase ha perso: `cal-tx-iqlo` da 333 a 331, e non e' l'assegnazione esclusiva —
la regione da sola da' **746 su 1570 in 99 blocchi** col cursore globale e **741 in
97** per indirizzo. Perdita vera di 5 op. Il meccanismo non e' stato attribuito: un
valore che prima cadeva sul mirror e per caso combaciava, ora arriva dal piano e non
combacia, e' l'ipotesi ovvia ma **non e' verificata**.

E con i valori letti giusti l'LSB che restava si e' rivelato **un difetto di
mainline**, non un limite dell'harness: in `b43_nphy_rev3_rssi_cal()` il ramo
negativo dell'arrotondamento scrive `-(abs(offset[j] + 4) / 8)`, con la parentesi
di `abs()` nel posto sbagliato, quindi il 4 finisce dentro il valore negativo
invece che sul suo modulo e ogni offset sotto -4 arrotonda verso lo zero. brcmsmac
prende il modulo, aggiunge `NPHY_RSSICAL_NPOLL / 2`, divide e nega alla fine, e lo
stesso file la scrive giusta due volte: nella fase coarse di questa funzione e in
`b43_nphy_rev2_rssi_cal()`. Corretta la parentesi, i nove coefficienti diventano
`0x1b8 = 0x3f` piu' otto `0x3e`, **identici alla cattura**:
`patches/mainline/b43-fix-the-rounding-of-the-negative-rssi-cal-offsets.patch`.

La finestra `rssi-cal` resta comunque **1/16**, e la strada del multiinsieme e'
stata provata e non funziona: il vendore fa 16 op, il port ~140 (scrive ogni
coefficiente due volte, zero e poi il valore, e intercala read e override RF).
Allargando `test_len` a 200 gli otto `0x3e` si appaiano — **ed e' la prova che i
valori sono giusti** — ma entrano 37 op del port che il vendore in quella finestra
non ha, e il verdetto peggiora invece di dire il vero: le due finestre non sono
commensurabili.

Quindi questa fase non si chiude con questo strumento. Vuole un confronto sul
**valore finale** dei registri — dopo la fase, `0x1a4` vale quello che vale nella
cattura — che e' un'asserzione diversa dal confronto di sequenze di op, e oggi non
c'e'. Restano fuori anche due table-read del vendore che il port non fa,
`TBL.RD id=0x7 off=0x110` (il salvataggio del tx gain originale, che `0014` non
porta) e `TBL.RD id=0xf off=0x50`.

**E adesso il punto onesto: i piani non spostano la copertura.** Con e senza, il
flow `full` emette 14490 e 14488 op, e registri e celle coperte sono identici. 72
indirizzi su 149 consumano il loro piano, quindi vengono usati; semplicemente le
fasi che mancano non mancano per colpa di un valore letto sbagliato: i piani di
lettura non sono la spiegazione, benché lo sembrino.

Quello che resta fuori è **strutturale**: early return e gate di revisione dentro
il driver, non stato dell'hardware. I piani restano perché costano nulla, rendono
fedeli le read e serviranno quando i loop di calibrazione gireranno davvero, ma
non sono la leva.

## Le voci al contrario, guardate

Il port che tocca qualcosa che il vendore non tocca è il segnale più forte che
l'harness produce, perché non c'è modo di spiegarlo con "b43 fa meno". Erano tre,
e sono finite in tre modi diversi.

**`r05f` era un bug vero**, in mainline: il ramo rev 7/8 dei workaround IPA scrive
`IPA2G_GAIN_CORE0` dove il vendore scrive `IPA2G_IMAIN_CORE0`, e programma i due
core con valori diversi dove il vendore usa lo stesso. `patches/b43/MESSAGES.md#0005` lo
sistema per il rev 8, dettaglio in `docs/gap-inventory.md`.

**`o708` e `o70e` non erano confrontabili.** Sono `B43_SHM_SH_NPHY_TXPWR_INDX0/1`,
e il problema è l'unità di misura: `b43_shm_write16()` prende un offset in **byte**
nella regione SHARED e lo divide per 4 al suo interno, mentre il tracer del vendore
registra l'argomento di `write_objmem16()`, che è un indirizzo di parola con un
selettore di spazio diverso (`0x10000` contro `B43_SHM_SHARED` = 1). L'harness
intercetta al livello dell'API e il tracer a un altro: confrontare quegli indirizzi
produce solo rumore. Ora `coverage.py` la object memory la conta e non la confronta,
e lo dice.

**`tbl15+0x60..0x63` è un artefatto mio.** Compare solo nel flow `full`, che accende
la calibrazione con `perical = 0`: è la tabella IQLOCAL scritta dalla cal, che il
vendore all'init non fa. Nel flow `init`, quello che imita il vendore, la lista al
contrario è **vuota**.

### Finestre su una cattura diversa

Una finestra puo' dichiarare `capture='<file>'` e viene confrontata contro quella
invece che contro il `--vendor` passato in riga di comando. Serve per le fasi che una
cattura non contiene: `static-tables` e `static-tables-2` stanno solo in un init **a
freddo**, e la `opinit-*` e' a caldo.
