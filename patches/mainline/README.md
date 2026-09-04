# patches/mainline

Difetti di mainline indipendenti dal BCM6362 e da questo lavoro. Valgono una
submission a sé, e prima del resto, perché sono corti, non gateati su nessuna
revisione e sbagliati in modo dimostrabile senza avere l'hardware davanti.

**Sono patch separate, non una serie**, e vanno inviate come tanti `[PATCH]` in
altrettanti thread: nessuna ha bisogno di un'altra per essere corretta, e legarle in
una serie significa che una review lunga su una tiene fermo il merge delle altre.
Una sola coppia si tocca, e solo per contesto — `treat-the-n-phy-dac-test` e
`fix-two-defects-in-the-n-phy-sample-table-logic` cambiano righe vicine di
`b43_nphy_gen_load_samples()`, vedi sotto.

| file | cosa | righe |
|---|---|---|
| `b43-fix-two-defects-in-the-n-phy-sample-table-logic` | `<<` lega più forte di `&`, e il passo di fase in una `u16` dopo un `<< 16` di troppo tronca a zero per **tutte** le frequenze che il driver chiede | 6 |
| `b43-test-the-radio-rev-for-the-n-phy-tssia-setup` | `phy->rev != 5` dentro un ramo `phy->rev >= 7`: guard morto, andava sul radio | 12 |
| `b43-fix-the-rounding-of-the-negative-rssi-cal-offsets` | la parentesi di `abs()` nel posto sbagliato: il `+4` finisce dentro il valore negativo invece che sul suo modulo, e ogni offset sotto -4 arrotonda verso lo zero. Lo stesso file la scrive giusta due volte | 2 |
| `b43-fix-two-rf-control-override-value-masks-on-n-phy-rev-7` | due `val_mask` di `tbl_rf_control_override_rev7_over1` non coprono il campo del proprio shift. Col campo `0x0100` il port azzera il bit 8 di `0x340`, che appartiene alla banda del filtro programmata poche op prima | 4 |
| `b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7` | `one_to_many`, caso `TX_PU`: quattro chiamate contro cinque di brcmsmac, manca `(0x1 << 2)` su override 2 | 1 |
| `b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag` | il modo del test DAC e' un `u8` testato `== 1`, b43 lo restringe a `bool` in tre punti: qualunque modo sopra 1 accende la strada sbagliata | 5 |
| `b43-wait-for-the-n-phy-tx-iq-lo-calibration-to-finish` | il polling su `IQLOCAL_CMD` esce quando i bit 15/14 sono **accesi**, cioe' mentre la cal gira, invece di aspettare che si spengano: `SPINWAIT` nel riferimento gira *mentre* l'espressione e' vera. Il driver rilegge i coefficienti ~10 us dopo il comando, dodici volte, e salva cio' che c'era prima | 1 |
| `b43-take-the-n-phy-tx-iq-lo-results-out-instead-of-overwriting-them` | in coda alla cal, `write(96)` e `read(80)` hanno la direzione **scambiata**: il driver sovrascrive il risultato del motore col buffer vecchio e legge 80 invece di scriverlo. Le tre coppie che seguono nello stesso blocco sono giuste, ed e' cio' che lo fa sembrare un refuso | 2 |
| `b43-fill-the-per-rate-transmit-power-offsets-on-n-phy` | `nphy->tx_power_offset[]` non ha **nessuno scrittore**: dichiarata, letta in due posti e riempita da nessuna parte, quindi le 84 celle della tabella di potenza aggiustata escono a zero qualunque cosa dica la SPROM, e ogni rate trasmette alla stessa potenza. **Porta anche uno spostamento di `b43_nphy_tx_pwr_ctrl_coef_setup()` che non c'entra e va scorporato**, vedi sotto | 20 |
| `b43-square-both-terms-of-the-n-phy-rssi-vcm-search` | la ricerca del VCM narrowband minimizza `I² + Q²` e il secondo termine e' scritto `Q * I`: non e' una distanza, ed e' negativo ogni volta che le due rail hanno segno opposto, quindi il minimo cade dove quel prodotto e' piu' negativo. Il VCM scelto e gli offset che ne discendono sono entrambi sbagliati | 2 |
| `b43-program-the-best-n-phy-rssi-vcm-instead-of-the-loop-bound` | il ramo rev 7+ della scelta del VCM migliore programma `vcm`, che all'uscita del ciclo vale 8: il campo e' di tre bit, quindi scrive un bit fuori campo e butta il risultato della ricerca. Il ramo rev 3 sotto e brcmsmac passano entrambi `vcm_final` | 2 |
| `b43-save-the-right-field-of-the-n-phy-tx-power-index` | quando spegne il controllo di potenza acceso, salva l'indice su cui stava ogni catena prendendo i **sette bit bassi** dello stato invece dei bit 8..14, che sono l'indice — lo dice `B43_NPHY_TXPCTL_STAT_BIDX` di questo stesso driver, e venti righe sotto `b43_nphy_get_tx_gains()` lo legge giusto. Il ripristino rimette quel campo sbagliato nell'indice, quindi l'hardware riparte da dove capita | 12 |

Le ultime due si dimostrano **a tre voci**: brcmsmac, la cattura e b43 dicono cose
diverse, e le prime due dicono la stessa. Le righe della cattura stanno nel corpo
delle patch.

`reverse-tools/check_patch_gating.py --tree` su `848acc8ffe1b` segna **sette punti su
cinque** di queste patch, non due. Sei sono corretti e per la stessa ragione — un
refuso di trascrizione o di precedenza C non si mette dietro un gate di revisione,
perché non è una feature di questo hardware, ed è l'eccezione già dichiarata di
`b43/MESSAGES.md#0010`:

| patch | funzione | perché il non-gate va bene |
|---|---|---|
| `program-the-fifth-tx-power-up-override` | `b43_nphy_rf_ctl_override_one_to_many()` | quinta chiamata mancante, gira su ogni rev 7 e su |
| `treat-the-n-phy-dac-test-as-a-mode-not-a-flag` | `b43_nphy_gen_load_samples()`, `b43_nphy_run_samples()` | restringimento `u8` → `bool`, sbagliato su ogni rev |
| `fix-two-defects-in-the-n-phy-sample-table-logic` | `b43_nphy_load_samples()`, `b43_nphy_gen_load_samples()` | `<<` che lega più di `&` e un passo di fase troncato: tronca per ogni rev |
| `wait-for-the-n-phy-tx-iq-lo-calibration-to-finish` | `b43_nphy_cal_tx_iq_lo()` | polarità del `SPINWAIT`; il ciclo non sta sotto nessun gate, e il difetto non è per rev |

Il settimo **non** è coperto da quell'eccezione, e va guardato prima di spedire:
`b43-fill-the-per-rate-transmit-power-offsets-on-n-phy` in
`b43_nphy_op_recalc_txpower()`. Riempire un array che nessuno scrive cambia cosa
programmano tutte le N-PHY rev 3 e su, e non è un refuso: è comportamento nuovo su
hardware che non abbiamo. Il verdetto dello strumento sull'**altro** hunk della stessa
patch, `b43_phy_initn` "dentro if (rev >= 3 &&", è un falso positivo del suo
euristico — la riga aggiunta ha **un tab** di rientro, quindi sta al livello della
funzione, dopo che il blocco `if (phy->rev >= 3) ... else ...` si è chiuso.

E quell'hunk è un problema a sé, che non ha niente a che vedere col resto della
patch: sposta `b43_nphy_tx_pwr_ctrl_coef_setup()` **prima** delle calibrazioni.
Il commento lo giustifica dicendo che nel riferimento quella chiamata è l'ultima cosa
dell'init e che ciò che la precede si limita a schedulare una calibrazione. **Non è
così**: in `wlc_phy_init_nphy` il ramo non-mphase chiama `wlc_phy_cal_txiqlo_nphy` e
`wlc_phy_cal_rxiq_nphy` **inline** (`phy_n.c:19516` e `19519`) e `wlc_phy_txpwrctrl_
coeff_setup_nphy` viene **dopo** (`19534`), cioè esattamente dove b43 la ha adesso.
Solo il ramo mphase schedula. Quindi la giustificazione scritta contraddice il
riferimento che cita; la ragione vera è la cattura, e una ragione che è la cattura non
sta in `patches/mainline/`, che per definizione raccoglie difetti indipendenti da
questo hardware. Va scorporato nel rollup, o gateato, prima di spedire il resto.

Si dimostrano senza hardware: per precedenza C e aritmetica, perché un guard non può
essere falso, o perché brcmsmac e la cattura concordano contro b43.

Undici applicano **da sole** su mainline pulito. La dodicesima e'
`b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag`, e non e' un difetto della patch
ma una dipendenza di contesto: il suo primo hunk ha `u16 bw, len;` fra le righe di
contesto, e sul pulito quella riga e' `u16 bw, len, rot, angle;`. E' la
`sample-table-logic` a spezzarla in due (`u16 bw, len;` piu' `s32 rot, angle;`).
Applicata quella prima, la dac-test entra con offset -43 e -113. **Chi la prende da
sola dal thread non la applica**, e va detto nel corpo della patch.

Il difetto non si vede seguendo la riga di `CLAUDE.md`, che le applica con un `for`
in ordine alfabetico: `fix-two-defects-in-the-n-phy-sample-table-logic` viene prima
di `treat-`.

`b43-fill-the-per-rate-transmit-power-offsets-on-n-phy` **applica** su
`848acc8ffe1b`, e senza fuzz — `git apply` non ne concede — ma con offset **-643,
-643, -1027 e -1054**: e' stata generata sopra il rollup, che allunga `phy_n.c` di
~1000 righe. Va comunque rigenerata sul baseline pulito prima di spedirla, perche'
quattro offset da mille righe su un albero che si muove sono una patch che scade da
sola, non perche' oggi non entri.

  for p in patches/mainline/*.patch; do git apply --check "$p"; done

La prima porta due difetti insieme, e non per pigrizia: nessuna delle due metà, da
sola, produce una tabella dei campioni giusta — 140 parole sbagliate su 160 con la
sola maschera corretta, 120 col solo passo di fase. Sono due righe di una stessa
logica rotta, e separarle darebbe due patch che nessuno può verificare.

Con la prima applicata, le finestre `sampleplay-tssi` e `sampleplay-iqlo` di
`test/phase_compare.py` fanno **322/322** entrambe: le due tabelle dei campioni
diventano identiche alla cattura, parola per parola, senza niente della serie in
`patches/b43/`. Il rollup di `patches/b43/` non porta piu' quelle
due modifiche: si applica sopra queste, che le hanno gia'.

La seconda non è in `patches/b43/`: cambia cosa programmano un radio 2057 rev 5 e
un phy rev 7 in 5 GHz, e non abbiamo né l'uno né l'altro. Il razionale sta in
`docs/todo-nphy.md` 3d bis.

`b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag` e' latente: nessun chiamante in
tree passa un modo diverso da 0 o 1, quindi da sola non cambia niente. Morde il
primo chiamante con un modo vero, che e' la cal RX IQ — e la misura c'e': col
`bool`, un tipo 2 costruisce le 160 word del tono su una banda di 80 o 82 invece di
20, e il port perde **476 op** su `up-ch1`. Il rollup di `patches/b43/` si applica sopra
questa e non la duplica.

Nessuna ha girato su hardware.
