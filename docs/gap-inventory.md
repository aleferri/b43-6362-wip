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
Limitata a radio rev 8, 2.4 GHz, 20 MHz: per le altre revisioni non ho catture.
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

### 5b. La chantab non scrive i campi 5 GHz che il vendore azzera

Sul cambio canale il vendore scrive dieci registri in più, tutti a zero: i campi
5 GHz e PGA della entry dual band (`LOGEN_MX5G_TUNE`, `LOGEN_INDBUF5G_TUNE`,
`PGA_BOOST_TUNE_CORE0/1`, `TXMIX5G_BOOST_TUNE_CORE0/1`,
`PAD5G_TUNE_MISC_PUS_CORE0/1`, `LNA5G_TUNE_CORE0/1`). b43 usa la variante
`chantabent_rev7_2g` e non li tocca. Impatto ignoto, e il percorso è condiviso
con altri device: voce aperta, non patch. Vedi `docs/trace-init-2g.md`.

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
