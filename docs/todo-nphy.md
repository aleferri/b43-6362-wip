# I posti dove b43 non fa quello che il vendore fa

Elenco di lavoro, non di lamentele: ogni voce ha come è stata trovata, cosa
manca, e cosa serve per chiuderla. Le voci già chiuse stanno in
`gap-inventory.md`; qui c'è quello che resta aperto dopo le sei patch.

Misure con `test/coverage.py` contro il primo init della cattura, flow `init` sul
**canale 1**, cioè lo stesso del vendore. Il canale conta: con il port su un
canale diverso nove registri della chantab risultano "diversi" e non lo sono.

## 1. I 32 registri PHY che il vendore scrive e il port no

Raggruppati per il punto della cattura in cui compaiono, che è quello che li
attribuisce.

| registri | dove nella cattura | attribuzione |
|---|---|---|
| `0x1df, 0x1e1` = 0x1591 | #203-204, init radio iniziale | fase prima dell'init PHY, da guardare |
| ~~`0x1d7, 0x1d9, 0x1db, 0x1dd`~~ | #680-683 | **chiusi**: soglie di carrier sense, `patches/b43/0008` |
| `0x020, 0x021, 0x2a7, 0x2a8, 0x2e6, 0xc33` | #5614-5625 | fase non identificata |
| `0x07b, 0x07e` (12 volte ciascuno) | #11769, #12819 | regione della calibrazione |
| `0x29f, 0x2a0-0x2a4, 0x2be, 0x2e5, 0x348, 0x349, 0x358` | #12194-12324 | regione della calibrazione |
| `0x09a-0x09d` (8 volte) | #15095-15098 | regione della calibrazione |
| `0x129, 0x12a, 0x12b` (8-16 volte) | #15863-15865 | regione della calibrazione |

Restano 28 registri su 32, di cui 22 fra #11700 e #15900, che è
dove il vendore fa la calibrazione PAPD e la TX IQ/LO. b43 la PAPD non l'ha
affatto e la IQ/LO all'init la salta (`perical = 2`, "like wl"). Quindi non sono
32 buchi indipendenti: sono due funzioni mancanti e sei registri da attribuire.

## 2. I 14 registri radio

| registri | attribuzione |
|---|---|
| `0x43, 0x4a, 0x70, 0x73, 0x74, 0xa0, 0xf5, 0xf8, 0xf9, 0x125`, tutti a 0 a #145-161 | i campi 5 GHz della entry chantab dual band che il vendore azzera: è la voce 5b di `gap-inventory.md` |
| `0x17d, 0x17e, 0x19d, 0x19e` | il blocco TSSI, ma **solo durante la cal**: read-modify-write a #11828-11837 con valori che cambiano fra le sei occorrenze. Sono della calibrazione, non del setup |

## 3. Registri scritti da entrambi con valore diverso

`coverage.py --values` confronta il primo valore scritto su ogni registro toccato
da entrambi i lati. Serve perché la sola presenza non vede questa classe di
differenza — ed è così che è venuto fuori il TSSI. Sedici voci, in tre gruppi.

### 3a. Coefficienti di moltiplicazione RSSI: `0x1a4-0x1b8` (11 registri)

    vendore  0x1a4 = 0x3e   0x1a6 = 0x02   0x1ac = 0x01   0x1b8 = 0x3f
    port     0x1a4 = 0x3f   0x1a6 = 0x00   0x1ac = 0x3e   0x1b8 = 0x3f

Sono i `B43_NPHY_RSSIMC_*`, cioè la calibrazione RSSI. Entrambi i lati li
scrivono più volte, il vendore in sequenza `0x3e, 0, 0x3e`. I valori del port
divergono su almeno quattro registri.

Va letto insieme alla voce di `docs/phy-g-only.md` su `b43_rssi_postprocess`, che
ha rami per G e LP e non per N: la catena RSSI ha due problemi indipendenti, i
coefficienti programmati e la conversione di quello che si legge. È il numero che
finisce in `ieee80211_rx_status.signal`.

**Aggiornamento dal confronto posizionale** (finestra `rssi-cal`), che dice più
della misura per insiemi e corregge la descrizione qui sopra:

- i registri sono **gli stessi**: il port ne scrive 24 op in tutto il run, il
  vendore 12 nella sua finestra, e l'insieme coincide;
- l'**ordine** no. Il vendore li scrive in un blocco contiguo — `0x1b8`, poi
  `0x1a4, 0x1aa, 0x1b0, 0x1b6` (la X sulle quattro rail), poi `0x1a5, 0x1ab, …`
  (la Y) — mentre il port ne scrive due e poi va a leggere `0xa6, 0xa7, 0xf9`,
  cioè intercala letture e scritture per rail;
- i **valori non sono confrontabili** nell'harness: vengono da
  `b43_nphy_restore_rssi_cal()`, che rimette la cache prodotta dalla
  calibrazione RSSI, e la cal senza hardware da misurare produce zeri. Lo stesso
  vale per `R2057_NB_MASTER_CORE0/1` (radio `0x0b4`/`0x139`): il port ci scrive
  quello che ha in cache.

Quindi la voce resta aperta ma cambia forma: non "coefficienti sbagliati", ma
ordine diverso e valori non verificabili da qui. Per chiuderla serve o una
cattura con la cal RSSI del vendore isolata, o l'hardware.

### 3b. Potenza target: `0x1ea` = `B43_NPHY_TXPCTL_TPWR`

    vendore  0x3e3e   (62 in Q5.2 = 15.5 dBm)
    port     0x4a4a   (74 in Q5.2 = 18.5 dBm)

Il port programma il `maxpwr_2g` della SROM così com'è; il vendore mette 3 dB in
meno. Tre dB tondi hanno l'aria di un limite — regolatorio per il canale, o il
guadagno d'antenna, o uno degli offset per-rate della SROM — che b43 nel percorso
ppr non sottrae, oppure che l'harness non conosce perché non ho il contesto
regolatorio della board. Da chiudere leggendo quale dei due, non tirando a
indovinare: è potenza in uscita.

Nota di metodo: prima di decodificare `core_pwr_info` dalla SROM il port scriveva
0x0000 qui, e sembrava un buco del driver. Era la mia SPROM incompleta.

### 3c. `0x340, 0x341` = `B43_NPHY_REV7_RF_CTL_MISC_REG3/4`

    vendore  0x400, 0x400, 0x400, 0x0002, 0x4000
    port     0x000, 0x000, 0x000, 0x0000, 0x0004

Sequenze diverse su entrambi. Non attribuito.

### 3d. TSSIG: `0x17b, 0x19b` = `R2057_TX0_TSSIG` / `R2057_TX1_TSSIG`

Questo è il TSSI, ed è la voce più chiara del gruppo.
`b43_nphy_ipa_internal_tssi_setup()` per i rev 7+ fa, per core:

    if (phy->rev != 5) write(r + 0xA, 0);
    if (phy->rev != 7) write(r + 0xB, 1); else write(r + 0xB, 0x31);

Nella cattura, nella fase corrispondente (#1259-1265) il vendore scrive
`0x175, 0x176, 0x177, 0x178, 0x179, 0x17a, 0x17c` con gli stessi valori del port,
e **`0x17b` non lo tocca affatto**. Lo scrive più tardi, a #8537, con `0x31`, in
una fase diversa: preceduto dalle letture degli stessi registri e con altri
valori (`0x175 = 0x06`, `0x176 = 0x43`, `0x177 = 0x55`), cioè un
salva-riconfigura tipico della calibrazione TX.

Quindi il ramo `phy->rev != 7 ? 1 : 0x31` sembra mescolare le due fasi: mette il
valore della cal nel setup per il rev 7, e per gli altri rev scrive 1 dove il
vendore lascia il valore di reset.

Non l'ho patchato: "il vendore non scrive" non dice quale sia il valore di reset,
e su questo registro passa la misura di potenza. Per chiudere serve leggere
`0x17b` prima e dopo il setup su hardware, o una cattura che includa il reset del
core.

## 3f. `0x7b` e `0x7e`: marcati e basta

`B43_NPHY_RFCTL_RXG1` e `RXG2`. La tabella degli override RF rev7 ha già la voce
per il campo `0x0800` che li pilota, ma nessun percorso del driver passa quel
campo; il vendore li scrive 12 volte ciascuno durante la calibrazione. Non c'è
niente da aggiungere senza sapere in che fase e con che valori, quindi
`patches/b43/0007` mette una riga di TODO accanto alla voce morta e si va avanti.

## 3g. Il vcocal non mancava

Nella finestra del cambio canale il confronto posizionale segnalava otto op
mancanti su `0x2b` e `0x2e`, cioè `RFPLL_MISC_EN` e `RFPLL_MISC_CAL_RESETN`: la
VCO calibration alla fine di `b43_radio_2057_setup()`. b43 la fa, e la fa uguale.

La differenza era nella resa: il tracer del vendore aggancia sia `mod_radio_reg`
sia la read e la write che quella chiama, quindi una sola RMW compare come tre
op, mentre b43 con `b43_radio_mask`/`b43_radio_set` ne produce una. Scartate le
due ombre — solo quando seguono immediatamente una `MOD` sullo stesso indirizzo
— le quattro op del vcocal combaciano e i mancanti di quella finestra scendono a
**esattamente 10**, i campi 5 GHz della voce 5b.

Vale la pena notare cosa sarebbe successo senza: otto op attribuite a un buco
inesistente, e la voce 5b gonfiata da 10 a 18.

## 3e. Nota di metodo: il confronto posizionale viene prima

Le voci 3a-3d sono uscite da `coverage.py --values`, che confronta insiemi e
primi valori. È la misura debole. Quella forte è `test/phase_compare.py`, che
diffa op per op dentro una finestra allineata, ed è il metodo di `b43-ac-wip`
che avevo importato nel primo giro senza mai eseguirlo.

Applicata al TSSI, dice più di quanto avessi capito: non è "un valore diverso su
`0x17b`", è **un'op in più**. Il port scrive `0x17b = 1` fra `0x17a` e `0x176`,
dove il vendore in quella fase passa direttamente a `0x176`, e da lì in poi le
due sequenze sono sfasate di uno. Allo stesso modo il cambio canale combacia per
11 op e poi il vendore scrive i campi 5 GHz **intercalati**, non in coda: se si
chiude la voce 5b, vanno messi in quelle posizioni.

## 5. Le formule: cosa manca davvero per il rev 8

Ho contato i `TODO` in `phy_n.c` e sono 25, ma è un conteggio che inganna: la
grande maggioranza sono rami `phy->rev >= 19`, cioè PHY che non ci riguardano.
Per il rev 8 la situazione è questa.

**Presenti e funzionanti**: la calibrazione RSSI (`b43_nphy_rev3_rssi_cal`, che
il rev 8 usa perché il dispatch è `rev >= 3`), la TX IQ/LO
(`b43_nphy_cal_tx_iq_lo` con il ramo rev 7 e i registri `R2057_TX*_LOFT_*`), il
save/restore delle calibrazioni. Non sono stub: girano.

**Mancante per intero**: la **calibrazione PAPD**. b43 non ha nessuna funzione
che la faccia — accende il motore (`PAPD_EN0`/`EN1`), ora gli inizializza le
tabelle (`patches/b43/0004`), ma non calcola mai gli epsilon. In brcmsmac sono
`wlc_phy_a3_nphy` (146 righe), `wlc_phy_a4` (275), `wlc_phy_ipa_set_bbmult_nphy`
(722) e `wlc_phy_txpwr_papd_cal_nphy` (12): **~1150 righe**.

È anche la spiegazione dei 22 registri PHY non attribuiti fra #11700 e #15900:
non sono 22 buchi indipendenti, sono quella funzione che non esiste. Portarla è
il pezzo grosso che resta, e non è roba da mezz'ora.

## 4bis. La cal RSSI: i piani funzionano, il campionamento no

Aggiornamento su 3a, misurato e non più ipotizzato.

I piani di lettura **vengono consumati**: 22 valori su 27 per ciascuno di
`0xa6`, `0xa7`, `0xf9`, `0xfb`, che sono i registri che `b43_nphy_poll_rssi()`
legge. (Il giro precedente in cui "non spostavano niente" era un binario stale:
lezione a parte, `make` prima di misurare.)

Con i piani attivi i coefficienti che il port scrive sono `0x3f` dove il vendore
mette `0x3e`: **un LSB**. La formula quindi è giusta; quello che differisce è il
campionamento. Il conto preciso: il port fa **22** letture per registro dove il
vendore ne fa **27** per init. Il piano è una FIFO per indirizzo, quindi con 5
poll in meno il port consuma i valori dei round sbagliati e la media esce di uno.

Cosa NON è la causa: il numero di livelli VCM. b43 cicla `vcm < 8` e brcmsmac ha
`vcm_level_max = 8`, identici. Le 5 letture in più del vendore vengono da
qualcos'altro, e non l'ho ancora trovato.

## 4. Come rifare le misure

```sh
cd test
./nphy_trace init dsl3580l 1 > /tmp/port.out          # canale 1, come il vendore
./coverage.py ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded \
    /tmp/port.out --range 132 26100 --values
```

Due trappole in cui sono cascato, per non ricascarci:

- **canale diverso** fra port e cattura: nove registri della chantab escono come
  differenze e non lo sono;
- **SPROM incompleta** nell'harness: i campi che non decodifico diventano zeri, e
  gli zeri sembrano buchi del driver. Se una differenza riguarda la potenza,
  guardare prima `main.c` che il driver.
