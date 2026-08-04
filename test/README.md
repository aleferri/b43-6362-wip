# test/ — harness di verifica in userspace

Compila i sorgenti N-PHY di b43 **presi da un tree kernel, senza modificarli**,
li fa girare in userspace con uno shim che intercetta ogni accesso all'hardware,
ed emette un trace nel formato di `wl-diag` decodificato. Serve a confrontare
op-per-op quello che il driver fa con quello che il driver proprietario fa nella
cattura sotto `router-data/`.

## Uso

```sh
make KDIR=~/src/linux            # costruisce
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

Il confronto ha anche trovato un difetto dell'harness, non del driver: `chanset`
chiamava `switch_channel(dev, 6)` senza aggiornare `hw->conf.chandef`, che è
quello che mac80211 fa prima di invocare l'op, e il port programmava la chantab
del canale vecchio. Si vedeva in due registri, 0x16 e 0x2c — vcocal e mmd0, cioè
proprio quelli che dipendono dalla frequenza.

## Quanto lontano arriva

`coverage.py` misura quali registri e quali celle di tabella il vendore scrive e
il port no. Non è un confronto posizionale — quello vuole due sequenze
allineabili, e sull'init non lo sono, perché b43 e il driver proprietario
ordinano le fasi in modo diverso: il port comincia dalle tabelle, il vendore dal
radio.

Contro il primo init della cattura (record 132-26100), **con
`patches/b43/0001` applicata al tree** — senza, il flow `full` scende a 175/218
PHY e 122/533 celle, ed è esattamente la differenza che quella patch fa:

| | flow `init` | flow `full` |
|---|---|---|
| registri PHY | 173/218 (79%) | **186/218 (85%)** |
| registri radio | 19/54 (35%) | **39/54 (72%)** |
| celle di tabella | 86/533 (16%) | **130/533 (24%)** |
| op emesse | 11675 | 14572 |

Il flow `initcal` accende la calibrazione mettendo `nphy->perical = 0` **dal
main dell'harness**, dopo `prepare_structs`. Quel knob deve restare qui:
`b43_nphy_op_prepare_structs()` è comune a ogni N-PHY, e cambiare `perical` lì
cambierebbe l'init di tutti i device che non possiamo provare. Vedi
`docs/upstreaming.md`.

`full` è la corsa più lunga che gli ingressi pubblici permettono: init con la
calibrazione accesa, poi `recalc_txpower`, poi un cambio canale. Non è una
sequenza che sul device capita così: serve a misurare la copertura, non a
riprodurre una run reale.

I registri SHM restano a 0/677 e non è un difetto: le scrive il core di b43, che
non compiliamo — qui c'è solo il PHY.

Cosa resta fuori, e perché:

- **tabelle 26 e 27** (`C0/C1_*_R3`, cioè estimated e adjusted power, gain
  control, I/Q, LO feedthrough, PAPD), 130 celle ciascuna: è il TX power control,
  e `b43_nphy_tx_pwr_ctl_init()` per `phy->rev >= 7` ritorna subito con un
  `/* TODO: Enable this once we have gains configured */`. Il port non può
  scriverle: è il buco del driver, non dell'harness. È anche la ragione per cui
  la tabella RF power offset è codice morto (`docs/rf-pwr-offset-rev8.md`).
- **tabelle 31 e 33**, 64 celle ciascuna, e i registri di gain 0x1d7-0x1e1,
  0x9a-0x9d, 0x129-0x12b: da attribuire, non ancora guardati.
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

Tre cose che il port tocca e il vendore no, da guardare: SHM 0x708 e 0x70e (la
`tx_iq_workaround` di b43 scrive lì, il vendore no o lo fa altrove), il registro
radio 0x5f, e la cella `tbl15+0x60`.
