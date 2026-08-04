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
| `0x1d7, 0x1d9, 0x1db, 0x1dd` | #680-683, **subito prima** del blocco di gain control | confinano con quello che `patches/b43/0001` porta: probabilmente la stessa funzione, coda non portata |
| `0x020, 0x021, 0x2a7, 0x2a8, 0x2e6, 0xc33` | #5614-5625 | fase non identificata |
| `0x07b, 0x07e` (12 volte ciascuno) | #11769, #12819 | regione della calibrazione |
| `0x29f, 0x2a0-0x2a4, 0x2be, 0x2e5, 0x348, 0x349, 0x358` | #12194-12324 | regione della calibrazione |
| `0x09a-0x09d` (8 volte) | #15095-15098 | regione della calibrazione |
| `0x129, 0x12a, 0x12b` (8-16 volte) | #15863-15865 | regione della calibrazione |

Le ultime quattro righe, 22 registri su 32, cadono fra #11700 e #15900, che è
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
