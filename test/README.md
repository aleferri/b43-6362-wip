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
./nphy_trace chanset dsl3580l 6  # init poi cambio a canale 6
./nphy_trace rfkill dsl3580l
make compare FLOW=init REF=../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
```

Per provare una patch: si applica **al tree** e si rifà `make`. Le copie in
`build/src/` hanno il sorgente del tree come prerequisito, quindi si aggiornano da
sole — non serve `make clean`, e prima serviva: con uno stamp unico la copia
restava vecchia in silenzio e si misurava il codice sbagliato credendo di misurare
la patch. Ci sono cascato, e le prime cifre di copertura erano quelle sbagliate.

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
  riga per op, con mirror di memoria per le write. Le `b43_ntab_*` invece stanno
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
- `stubs/b43_defs.h` — 487 define e 7 enum estratte da `b43.h`. I commenti sono
  rimossi di proposito: la prima versione li copiava e `B43_BFH_FEM_BT` ha un
  `/*` che continua sulla riga dopo, quindi il commento troncato si mangiava le
  define successive.
- `stubs/bcma_ids.h` — le define bcma/ssb citate dai sorgenti.
- `stubs/b43.h` è scritto a mano ma ridotto ai soli campi usati. La riduzione la
  verifica il compilatore: se il driver ne tocca uno che manca, il build si
  ferma.

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

Con `patches/b43/0001` applicata al tree, il flow `init` riproduce il blocco di
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
in fase. `patches/b43/0010` chiude i due, e le 160 word diventano identiche alla
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
| papd-tables (`0004`) | 5 | **5/5** | **ok** |
| ipa-bias (`0005`) | 3 | **3/3** | **ok** |
| sampleplay-tssi | 322 | **322/322** | **ok** |
| sampleplay-iqlo (`0010`) | 322 | **322/322** | **ok** |
| txdigi-filts | 60 | 45/60 | mancano 15, e sono **idempotenti**: il vendore riscrive `0x195`-`0x1a3` con gli stessi valori |
| chanswitch-ch6 | 39 | 11/39 | mancano **esattamente 10**: i campi 5 GHz della voce 5b |
| tssi-setup | 19 | 5/19 | mancano 4, in più 15: il `0x17b` di troppo e lo sfasamento |
| rssi-cal | 16 | 1/16 | mancano 15: i valori vengono dalla cal, che l'harness non fa |
| papd-digifilt, papd-calsetup | - | - | fasi della cal PAPD non portate: l'ancora non c'è, ed è lo stato atteso |

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
che nessuno faceva (`patches/b43/0008`), e una `PHY.RD` di troppo nella guardia
di `0001`, che leggeva `BANDCTL` dall'hardware dove b43 usa lo stato software. E le due divergenze note sono localizzate,
non solo contate — la cattura dice che i dieci campi 5 GHz della voce 5b vanno
scritti **in mezzo** alla sequenza (0x43 dopo 0x41, 0x4a dopo 0x47), non in coda.

C'è anche `--global-run DA A`, che non scegli una fase a mano: prende tutta la
finestra del vendore e tutto l'output del flow, e riporta le run più lunghe. Sul
primo init: **1540 op consecutive** (dal caricamento della TX gain table in poi),
poi 323, 266, 172, e in totale 3342 op in comune su 23126 in 332 blocchi. È la
misura più onesta di dove sta il port: copre pezzi, e i pezzi sono contigui.

Il passo che avevo saltato: `merge_retvals.py` sulla cattura prima di
confrontare. Senza, le 11049 righe `RETVAL` entrano nel diff come op a sé e
sfasano tutto. `phase_compare.py` lo fa da solo.

### coverage.py — copertura per insiemi

Misura quali registri e quali celle di tabella il vendore scrive e il port no.
Non è posizionale: serve a dire *quanto* manca e a trovare le voci al contrario,
non a dire se l'ordine è giusto. Utile per orientarsi, debole come garanzia.

Le celle si contano **espandendo le table-op**: un'op di lunghezza N copre N
celle. Contarla come una sola sottostimava il port, che scrive in bulk dove il
vendore scrive cella per cella — le percentuali di questa tabella sono quindi
diverse da quelle che avevo scritto prima del fix, ed è cambiata la misura, non
il port.

Contro il primo init della cattura (record 132-26100), flow `full`:

| | mainline | +`0001`..`0003` | +`0004` | +`0005` | serie intera |
|---|---|---|---|---|---|
| registri PHY | 175/218 (80%) | 186/218 (85%) | 186/218 (85%) | 186/218 (85%) | **190/218 (87%)** |
| registri radio | 39/54 (72%) | 39/54 (72%) | 39/54 (72%) | **40/54 (74%)** | 40/54 (74%) |
| celle di tabella | 878/1987 (44%) | 1190/1987 (60%) | 1446/1987 (73%) | 1446/1987 (73%) | 1446/1987 (73%) |
| op emesse | 14488 | 15598 | 16118 | 16118 | 16121 |

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

I registri SHM restano a 0/677 e non è un difetto: le scrive il core di b43, che
non compiliamo — qui c'è solo il PHY.

Cosa resta fuori, e perché:

- **tabelle 26 e 27** a offset 576, la compensazione PAPD: era l'early return di
  `b43_nphy_tx_gain_table_upload()`, chiuso da `patches/b43/0003`.
- **tabelle 31, 32, 33, 34**, cioè epsilon e scalare del PAPD: b43 accendeva il
  motore PAPD senza inizializzare le tabelle che legge. Chiuso da
  `patches/b43/0004`.
- **i registri di gain 0x1d7-0x1e1, 0x9a-0x9d, 0x129-0x12b** e gli altri 32
  ancora scoperti: da attribuire, non ancora guardati.
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

**E adesso il punto onesto: i piani non spostano la copertura.** Con e senza, il
flow `full` emette 14490 e 14488 op, e registri e celle coperte sono identici. 72
indirizzi su 149 consumano il loro piano, quindi vengono usati; semplicemente le
fasi che mancano non mancano per colpa di un valore letto sbagliato. È una mia
ipotesi che cade: l'avevo scritta due volte come "il prossimo lavoro ovvio".

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
core con valori diversi dove il vendore usa lo stesso. `patches/b43/0005` lo
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
