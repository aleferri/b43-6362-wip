# Inventario dei buchi

Generato su `torvalds/linux` @ `848acc8ffe1b` con
`reverse-tools/check_gaps.py --tree ~/src/linux --format md`. La colonna "rev
citate" elenca i valori che la funzione discrimina; `assente` significa che la
revisione target (radio 8 / phy 8) non compare, `stub` che il corpo è vuoto.
Lo strumento dà indizi, non verdetti: sotto ci sono solo le voci che ho poi
letto a mano. Il bilancio, dopo averle lette tutte: di sei voci iniziali **tre
non erano buchi** (`b43_radio_2057_rccal`, `b43_radio_2057_setup`,
`b43_radio_2057_rcal`) e una era accostata alla funzione sbagliata. Il motivo è
sistematico: l'assenza di un `case` in questo driver di solito ricalca il fatto
che il vendore, per quella revisione, non fa niente di speciale. Vale come
avvertenza su come leggere la tabella qui sopra.

| file:riga | funzione | campo | rev citate | stato |
|---|---|---|---|---|
| `phy_n.c:145` | `b43_nphy_rf_ctl_override_rev19` | `radio_rev` | — | stub |
| `phy_n.c:719` | `b43_radio_2057_setup` | `radio_rev` | 0, 1, 2, 3, 4, 6, 9, 14 | assente |
| `phy_n.c:811` | `b43_radio_2057_rcal` | `radio_rev` | 0, 1, 2, 3, 4, 5, 6, 9, 14 | assente |
| `phy_n.c:925` | `b43_radio_2057_rccal` | `radio_rev` | 3, 4, 6 | assente |
| `phy_n.c:1734` | `b43_nphy_rssi_select_rev19` | `radio_rev` | — | stub |
| `phy_n.c:2476` | `b43_nphy_gain_ctl_workarounds_rev19` | `radio_rev` | — | stub |
| `phy_n.c:2481` | `b43_nphy_gain_ctl_workarounds_rev7` | `radio_rev` | — | stub |
| `phy_n.c:4720` | `b43_nphy_tx_cal_radio_setup_rev19` | `radio_rev` | — | stub |
| `phy_n.c:4725` | `b43_nphy_tx_cal_radio_setup_rev7` | `radio_rev` | — | assente |
| `phy_n.c:6333` | `b43_nphy_set_channel` | `radio_rev` | 6, <=4 | assente |
| `phy_n.c:153` | `b43_nphy_rf_ctl_override_rev7` | `rev` | <3, >=19 | assente |
| `phy_n.c:200` | `b43_nphy_rf_ctl_override_one_to_many` | `rev` | <7 | assente |
| `phy_n.c:1301` | `b43_radio_2056_rcal` | `rev` | — | assente |
| `phy_n.c:1740` | `b43_nphy_rev3_rssi_select` | `rev` | <7 | assente |
| `phy_n.c:2571` | `b43_nphy_gain_ctl_workarounds_rev1_2` | `rev` | 2 | assente |
| `phy_n.c:3347` | `b43_nphy_workarounds_rev1_2` | `rev` | 2, <2, <3 | assente |
| `phy_n.c:4588` | `b43_nphy_spur_workaround` | `rev` | <3 | assente |
| `phy_n.c:4919` | `b43_nphy_int_pa_set_tx_dig_filters` | `rev` | 16, 17 | assente |
| `phy_n.c:5592` | `b43_nphy_rev2_cal_rx_iq` | `rev` | <2 | assente |
| `phy_n.c:6538` | `b43_nphy_op_radio_write` | `rev` | <7 | assente |
| `tables_nphy.c:3825` | `b43_nphy_get_gain_ctl_workaround_ent` | `radio_rev` | 11 | assente |
| `tables_nphy.c:3740` | `b43_nphy_get_tx_gain_table` | `rev` | 3, 4, 5, 6, <3 | assente |

## Le voci che contano per il 6362

### 1. `b43_nphy_gain_ctl_workarounds_rev7` — stub vuoto (phy_n.c:2481)

È il buco grosso. Copre il gain control RX di **tutti** i N-PHY rev 7+, quindi
anche il rev 8: soglie di clip, LNA gain, crsmin, RSSI gain. Corpo attuale: un
solo commento `/* TODO */`.

Riferimento: `wlc_phy_workarounds_nphy_gainctrl` (brcmsmac `phy_n.c:15593`), che
per radiorev 3 e 8 chiama `wlc_phy_workarounds_nphy_gainctrl_2057_rev6`
(`15224`) e per il solo rev 8 aggiunge `mod_phy_reg(0x283, 0xff, 0x44)` e
`mod_phy_reg(0x280, 0xff, 0x44)`.

Impatto atteso: sensibilità RX e comportamento AGC. **SALAME**: che sia il
primo collo di bottiglia sul 2x2 è la mia ipotesi di lettura, va misurato
(vedi `reports/30-rx-sensitivity.md`) prima di trattarlo come tale.

Patch: `patches/b43/0001`, scritta sui valori della cattura e non su brcmsmac,
perché i due divergono: LNA1 `8, 13, 18, 25` invece di `9, 14, 19, 24`, W1 clip
24 invece di 13, e in 2.4 GHz il device programma anche LNA2, TIA e i gain bits
che il ramo 2 GHz di brcmsmac non tocca. Dettaglio in `docs/trace-init-2g.md`.
Limitata a radio rev 8, 2.4 GHz, 20 MHz. Per le altre revisioni servirebbe una
cattura da quell'hardware; per i 40 MHz serve un device che li accenda, perché il
driver vendor non li usa in 2.4 GHz su questa board (31 chanspec su 31 sono bw20).
Applica pulito su `848acc8ffe1b`, **non compilata e non provata su hardware**.

### 2. `b43_radio_2057_setup` — nessun `case 8`, ma NON è un buco (phy_n.c:719)

Correzione rispetto alla prima stesura di questo documento: il ramo mancante per
radiorev 5/7/8 è un no-op sul 6362 in 2.4 GHz. La catena è questa:

1. `b43_radio_2057_setup()` chiama `b43_radio_2057_chantab_upload()` **prima**
   dello switch su `radio_rev`;
2. l'upload scrive `RFPLL_LOOPFILTER_R1`, `_C2`, `_C1` e `CP_KPD_IDAC` dai campi
   della chantab entry;
3. in `b43_nphy_chantab_phy_rev8_radio_rev8` tutte e 14 le entry portano
   `r1=0x1b, c2=0x0a, c1=0x0a, cp_kpd=0x30`;
4. che sono esattamente i valori che brcmsmac scrive nell'override per radiorev
   5/7/8 in 2.4 GHz (`phy_n.c:20960`);
5. e sono gli stessi che la cattura mostra sul silicio, `025=1b 027=0a 028=0a
   029=30` a ogni cambio canale (`docs/trace-init-2g.md`).

Quindi i registri finiscono giusti per un'altra strada. Vale anche per radio rev
5 (`chantab_phy_rev8_radio_rev5`, stessi quattro valori su tutte le 14 entry).
Il meccanismo dell'override serve altrove: per radio rev 14 la chantab porta
`r1=0x2b, cp_kpd=0x30` e il `case 14` li cambia in `0x1b`/`0x3f`.

Resta invece una differenza reale nella stessa funzione: b43 implementa **solo**
il ramo `b43_nphy_ipa()`, mentre brcmsmac ha anche l'`else` (non-IPA), che per
radiorev != 5 scrive `pad2g_tune_pus = 0x3` e `txmix2g_tune_boost_pu = 0x61`.
Rilevante solo su board con PA esterno: la DSL-3580L non è fra queste, quindi
per questo progetto è una nota, non un lavoro.

### 3. `b43_radio_2057_rcal` — nessun `case 8`, e va bene così (phy_n.c:811)

Seconda correzione: in `wlc_phy_radio205x_rcal` (brcmsmac `phy_n.c:19766`) i
rami radiorev-specifici sono solo tre — radiorev 5 (pre e post, `0x342` e
`IQTEST_SEL_PU`) e radiorev <= 4 o 6 (il trim di tempsense/bandgap alla fine).
Per radiorev 8 il vendore esegue **solo** la sequenza comune di `RCAL_CONFIG`,
che è esattamente ciò che b43 fa cadendo fuori dai suoi `case 5/9/14`.
Verificato riga per riga: niente da aggiungere.

### 4. `b43_nphy_tx_cal_radio_setup_rev7` — non è quello che sembrava (phy_n.c:4725)

Il `phy->radio_rev != 5` in questa funzione riguarda l'esistenza del registro
`TSSIA`, non un ramo mancante per il rev 8. I tre siti radiorev 8 di
`wlc_phy_a4` che lo strumento aveva accostato a questa funzione stanno altrove:
sono la scelta della tabella PAPD pad-gain, cioè la questione di
`rf-pwr-offset-rev8.md`. Voce chiusa, e sostituita da quella.

### 4b. La tabella RF power offset del rev 8 usa i valori del rev 5 — CHIUSA

Il vendore per radiorev 7 e 8 usa `nphy_papd_padgain_dlt_2g_2057rev7`, la
tabella merged usa i valori del rev 5. **Deciso dalla cattura**: ricalcolando le
128 celle PAPD che quella tabella alimenta, i valori rev 7 le predicono tutte, i
valori in tree ne predicono 5. Correzione in `patches/b43/0002`, dettaglio in
`docs/rf-pwr-offset-rev8.md`.

### 4c. Il percorso PAPD non viene mai eseguito sui rev 7+

`b43_nphy_tx_gain_table_upload()` recupera la tabella degli offset e poi ritorna
per `phy->rev >= 7` con un `/* TODO: Enable this once we have gains configured */`,
quindi le tabelle 26 e 27 a offset 576 (128 celle per core, la compensazione
PAPD) restano non programmate. Il loop che le calcola è già lì e nell'harness
produce esattamente le 256 celle della cattura. `patches/b43/0003` lo abilita per
radio 2057 rev 8 e lascia gli altri rev 7+ come sono. Da mandare dopo `0002`:
con i valori sbagliati scrive 246 celle su 256 diverse dal vendore.

### 5. `b43_radio_2057_rccal` — non è un buco

Lo strumento lo segnala perché il ramo "special" cita solo 3/4/6, ma per il rev
8 la strada giusta è proprio l'altra: in brcmsmac `wlc_phy_radio2057_rccal`
(`19874`) il gruppo `chip43226_6362A0` è radiorev 3/4/6, e il rev 8 va sul ramo
v7 con `MASTER 0x61/0x69/0x73`, `TRC0 0xe9/0xd5/0x99`, `X1 0x6e`. Le costanti
combaciano con quelle in b43: **verificato, niente da fare**.

### 5b. La chantab non scriveva i campi 5 GHz che il vendore azzera — CHIUSA

b43 ha due forme di tabella di canale rev 7+: quella intera e una **solo 2 GHz**
che lascia fuori dieci campi per risparmiare spazio. Lasciando fuori i campi ha
lasciato fuori anche le loro scritture, quindi un cambio canale su una board che
usa la tabella 2 GHz lascia `LOGEN_MX5G_TUNE`, `LOGEN_INDBUF5G_TUNE`,
`PGA_BOOST_TUNE` e i `TXMIX5G`/`PAD5G`/`LNA5G` dei due core col valore del canale
precedente.

Tre fonti indipendenti dicono che vanno scritti, e a zero:

- la **cattura**: ognuno dei dieci viene scritto con valore 0, a **tutti e 31** i
  cambi canale, su cinque canali e due cicli di interfaccia;
- **brcmsmac**, che tiene una tabella sola per le due bande: in
  `chan_info_nphyrev8_2057_rev8` ogni riga a 2.4 GHz ha zero in quelle dieci
  colonne, quindi scrive dieci zeri a ogni cambio;
- **b43 stessa**, nel ramo della tabella intera, li scrive in posizione.

E la posizione non è quella ovvia: i dieci sono **intercalati** con quelli a 2
GHz, non in coda — `0x43` subito dopo `0x41`, `0x4a` dopo `0x47`, i tre del core 0
fra `PAD2G` e `LNA2G`. È lo stesso ordine del ramo intero di b43.

`patches/b43/0011` li scrive, gateata su radio 2057 rev 8, la sola combinazione
che la cattura copre. Le altre due board che passano per la tabella 2 GHz (phy
rev 8 con radio rev 5, phy rev 17 con radio rev 14) restano come sono: brcmsmac
non ha righe a 2.4 GHz per quei radio, quindi non c'è niente contro cui
confrontarle.

Dopo la patch la finestra `chanswitch-ch6` non ha **nessuna op mancante**: le
prime 33 su 39 combaciano posizionalmente, e il resto sono le stesse op con gli
stessi valori sfasate di tre, perché l'harness registra tre accessi MMIO che il
tracer vendor non registra. Prima combaciavano 11 su 39 e mancavano dieci op.

### 4d. Il motore PAPD gira su tabelle non inizializzate — CHIUSA

`b43_phy_initn()` accende PAPD su ogni device con PA interno (`PAPD_EN0` e
`PAPD_EN1`), ma non tocca le tabelle che quel motore legge: la scalare (32 e 34)
e le epsilon (31 e 33). Restano con quello che c'era.

La cattura mostra il vendore scrivere la scalare con 64 valori per core — gli
stessi che brcmsmac ha in `nphy_papd_scaltbl`, verificati identici — e azzerare le
64 epsilon per core. `patches/b43/0004` fa lo stesso per radio 2057 rev 8: nell'
harness le 256 celle coincidono con la cattura, zero divergenti.

Non aggiunge la calibrazione PAPD, che è quella che riempirebbe le epsilon con
valori veri: dà al motore uno stato definito invece di quello che capita.

### 4e. I registri di bias IPA 2 GHz sono sbagliati sul rev 8 — CHIUSA

Trovata dalla lista **al contrario** di `test/coverage.py`, cioè i registri che il
port scrive e il vendore no. Era una riga sola, `r05f`.

Il ramo rev 7/8 dei workaround IPA scrive `0x5F` e `0xE8`, che sono
`IPA2G_GAIN_CORE0` e `IPA2G_IMAIN_CORE1`: un registro di ciascuna coppia, su core
diversi. Lo scostamento fra i due core di questo radio è 0x85, quindi il gemello
di `IPA2G_IMAIN_CORE1` è `IPA2G_IMAIN_CORE0` a `0x63`, non `0x5F`.

La cattura, nello stesso punto e in entrambi gli init, scrive `0x63 = 0x14` e
`0xE8 = 0x14` — IMAIN su entrambi i core, stesso valore — e `0x5F` non lo tocca
mai. b43 invece lascia IMAIN_CORE0 al suo valore, scrive il registro di gain del
core 0 con un valore destinato al bias, e programma i due core in modo diverso.

`patches/b43/0005` dà al rev 8 un `case` suo e programma IMAIN su entrambi i core.
Il rev 7 tiene il suo `case` e il suo comportamento: ha probabilmente lo stesso
problema, ma non c'è una cattura da hardware con quel radio, e il ramo 40 MHz
nemmeno. I due `case` sono separati di proposito, con 20 e 40 MHz divisi dentro
ciascuno: chi arriva con una cattura da un 2057 rev 7 tocca il suo ramo e non deve
farsi carico del nostro. Il prezzo è la duplicazione delle due righe del 40 MHz, e
si paga volentieri.

### 4f. Nessuna misura del rumore di fondo su N-PHY — CHIUSA

`b43_calculate_link_quality()` e `handle_irq_noise()` ritornano subito se la PHY
non è una G, quindi su N-PHY `dev->stats.link_noise` resta al valore iniziale e
mac80211 riceve una costante come rumore di fondo.

Il meccanismo per N c'è in brcmsmac: la ucode lascia una potenza complessa per
core nel blocco di power indication in SHM (`M_PWRIND_BLKS = 0x308`), il driver
azzera le quattro parole, alza `MCMD_BG_NOISE`, e alla risposta compone
`(hi << 16) | lo` per core, divide per 512, converte in dB e somma −103. Il rumore
riportato è il massimo fra i core.

La cattura legge esattamente quelle quattro parole, 96 volte, e passando i suoi
valori per la conversione escono **−82, −86, −88 dBm** per core: plausibili e
coerenti fra i due core. `patches/b43/0006` la cabla.

Attenzione al recinto: non è gateata sulla revisione ma sul **tipo** di PHY,
quindi tocca tutte le N-PHY. L'argomento per accettarla è che oggi quelle
riportano un numero che non è mai stato misurato. L'altra patch che esce dal
recinto è `0010`, vedi 4g.

Il resto dei punti dove b43 tratta la G e non la N sta in `docs/phy-g-only.md`:
venti costrutti, di cui i due del rumore e quattro in `xmit.c` sul RSSI e sulla
decodifica RX sono buchi veri, gli altri legittimi.

### 4g. La tabella dei campioni non contiene un tono — CHIUSA

Trovata dalle finestre `sampleplay-*` di `test/phase_compare.py`, confrontando le
160 word della tabella 17 op per op con la cattura.

La tabella SAMPLEPLAY è lo stimolo di ogni calibrazione che suona campioni: cal
TX IQ/LO, misura dell'idle TSSI, cal RX IQ del rev 2, e la cal PAPD quando ci
sarà. Due refusi in mainline la rendono inutilizzabile, e vanno insieme perché
nessuno dei due si vede senza l'altro corretto.

**Il passo di fase.** `b43_nphy_gen_load_samples()` (phy_n.c:1530) tiene `rot` e
`angle` in `u16` e calcola `rot = (((freq * 36) / bw) << 16) / 100`, poi passa
`CORDIC_FIXED(angle)`. Il riferimento è `wlc_phy_gen_load_samples_nphy`
(`brcmsmac/phy/phy_n.c:23030`), dove `rot` e `theta` sono `s32` e
`rot = ((f_kHz * 36) / phy_bw) / 100`, cioè gradi interi, perché
`cordic_calc_iq()` scala il suo argomento da sé. Il `<< 16` di b43 è quindi di
troppo, e in più rende il risultato un multiplo esatto di 65536 ogni volta che
`(freq * 36) / bw` è multiplo di 100 — che vale per **tutte** le frequenze che il
driver chiede: 2500 e 5000 dalla cal TX IQ/LO (phy_n.c:5389), 4000 dall'idle TSSI
(phy_n.c:3950) e dalla cal RX IQ rev 2 (phy_n.c:5718). Nella `u16` il passo
diventa 0: l'angolo non avanza e i campioni sono tutti uguali. Al posto del tono
c'è un livello continuo.

**L'impacchettamento.** `b43_nphy_load_samples()` (phy_n.c:1518) scrive
`data[i] = (samples[i].i & 0x3FF << 10)`, e `<<` lega più forte di `&`: maschera
con `0x3FF << 10` invece di spostare il valore mascherato. Per le ampiezze in uso
la componente in fase sta nei dieci bit bassi e viene azzerata; sui valori
negativi resta l'estensione del segno.

La cattura dà il formato senza ambiguità — `((i & 0x3ff) << 10) | (q & 0x3ff)`,
come in `wlc_phy_loadsampletable_nphy` — e tre toni da confrontare: ampiezza 0 a
#1288 (idle TSSI), ampiezza 250 a 2500 kHz a #8638 (cal TX IQ/LO, periodo 8
campioni), ampiezza 181 a 4000 kHz a #11838 (cal PAPD, periodo 5).

`patches/b43/0010` sistema entrambi. Sul tono di #8638, parole sbagliate su 160:
160 in mainline (tutte zero), 140 con la sola maschera corretta, 120 col solo
passo corretto, **0** con la patch.

Anche questa esce dal recinto del nostro radio: non è gateata su niente, tocca
ogni N-PHY. L'argomento per accettarla è che oggi quelle calibrazioni girano su
uno stimolo che non è il segnale che credono di suonare.

### 6. `dev_id 0x435f` e la banda 5 GHz

Non è un buco di dispatch ma un problema di rivendicazione. In
`b43_wireless_core_attach()` (main.c:5410) le bande vengono prima indovinate da
`BCMA_IOST` — e il nostro host driver sintetizza `2G_PHY=1, 5G_PHY=0` — ma
subito dopo `b43_supported_bands()` (main.c:5313) le **sovrascrive** partendo dal
`dev_id`, e `0x435f` sta nella lista dual band. Il fixup SPROM della DSL-3580L
imposta proprio `0x435f` (serve a b43 per riconoscere il chip), quindi b43
registra anche una banda 5 GHz.

Il silicio non c'entra: nel blob esistono `nphy_tpc_5GHz_txgain_epa_2057rev8`,
`nphy_tpc_txgain_ipa_5g_2057rev8` e la `chan_info_nphyrev8_2057_rev8` contiene
**109 canali 5 GHz** (4920..5900 MHz) oltre ai 14 di 2.4 GHz — verificato con
`reverse-tools/chantab_from_blob.py --list`. La combinazione PHY rev 8 / radio
2057 rev 8 è dual band per il vendor.

Il punto è che **b43 non ha** quelle tabelle: `r2057_get_chantabent_rev7()` per
`case 8` ritorna solo le 14 entry 2.4 GHz (delle 123 del vendor), quindi un
canale 5 GHz finisce in errore. Da decidere, e da misurare prima: se un `iw list` mostra la banda 5 GHz
e uno scan lì dentro produce errori, la patch upstream è far dipendere la banda
dall'IOST (o da un caso dedicato) invece che dal solo `dev_id`.
