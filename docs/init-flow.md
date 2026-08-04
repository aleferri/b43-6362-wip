# Il flusso di init, i due lati affiancati

Serve per rispondere a una domanda che torna sempre: *quando succede cosa, e da
che parte*. Le colonne sono misurate, non ricostruite a memoria:

- **port**: numero di riga nell'output di `./nphy_trace init dsl3580l 1`
  (13223 righe in totale con la serie `0001..0011` applicata);
- **cattura**: numero di record in `opinit-ch1-ch6-bw20.decoded`, primo init;
- **brcmsmac**: la funzione, trovata con `reverse-tools/cfuncs.py`.

## Prima cosa da sapere: dove i due divergono, e dove no

Il README dice che i due ordinano le fasi in modo diverso, "il port comincia
dalle tabelle, il vendore dal radio". È vero solo a metà, e la metà mancante
spiegava da sola il grosso del disallineamento.

**b43 e brcmsmac hanno la stessa distinzione fra init a freddo e init a caldo.**
`dev->phy.do_full_init` in b43 è `pi->phy_init_por` in brcmsmac, stessa
semantica: vero all'attach (`main.c:5462`) e dopo `b43_phy_exit()`, azzerato da
`b43_phy_init()` appena `ops->init()` è andata bene (`phy_common.c:105`). Dietro
quel flag stanno, in b43, il download delle tabelle statiche (quattro siti in
`tables_nphy.c`, con i commenti `/* Static tables */` e `/* Volatile tables */`
già scritti) e `b43_radio_2057_rcal`/`rccal` (`phy_n.c:1053`). In brcmsmac stanno
`wlc_phy_static_table_download_nphy` (`phy_n.c:14206`) e gli stessi rcal.

**La cattura non è un init a freddo.** `PHY.WR addr=0x72 val=0x2800`, l'apertura
della tabella 10 con cui il download statico comincia, non compare in nessuno dei
due init dei 70796 record; le aperture di tabella sono 950 e 1226 contro le ~2400
di un download completo. Quando il tracer è partito, il driver del vendore aveva
già fatto il suo init a freddo.

**L'harness invece lo modellava sempre a freddo**, con `do_full_init = true`
inchiodato in `main.c`. Da qui 8320 op di prefisso che nella cattura non ci sono e
non ci possono essere. Ora il flow `init` fa due init: il primo a freddo e non
tracciato, il secondo col flag azzerato, e il secondo è quello che si confronta.
Il flow `initpor` fa solo quello a freddo, per chi vuole guardarlo.

| | prima | ora |
|---|---|---|
| op del flow `init` | 13223 | **4903** |
| coefficienti RSSI | `0x3f` su tutti e nove | `0x3f` e otto `0x3e`, **come il vendore** |
| finestra `rssi-cal` | 1/16 | **11/16**, e le 3 che restano sono letture della porta dati |

L'ultima riga è il regalo inatteso: la cal RSSI sbagliava di un LSB perché i piani
di lettura venivano consumati anche dalle read che solo l'init a freddo fa
(`rcal`/`rccal`). Modellare il flow giusto ha allineato i piani senza toccarli —
che è quello che `todo-nphy.md` 4ter diceva servisse, e che con `--skip` non era
venuto.

## Cosa resta fra il port e l'allineamento completo

Con il prefisso via, il confronto globale non è più un rimescolamento: le run
lunghe hanno tutte lo **stesso scarto**, cioè sono la stessa sequenza con dei
blocchi inseriti. I blocchi sono tre.

### Il primo blocco non era del core: erano due stub vuoti nostri

Le prime ~84 op del vendore — AFE `0xa6 0x8f 0xa7 0xa5`, init table del radio,
primo cambio canale — le avevo attribuite "al core di b43, che l'harness non
compila". Sbagliato: sono tutte in codice **già compilato**, e l'harness non le
chiamava.

`b43_phy_init()` (`phy_common.c:83`) fa, in quest'ordine:

    ops->switch_analog(dev, true);
    b43_software_rfkill(dev, false);      <- e da qui l'init del radio
    ops->init(dev);
    phy->do_full_init = false;
    b43_switch_channel(dev, phy->channel);

L'harness chiamava solo `ops->init()`. E i due `b43_*` di mezzo, che `wrap.c`
deve fornire perché stanno nel core, erano stub bugiardi: `b43_software_rfkill()`
era **vuoto**, e `b43_switch_channel()` stampava `CHANSPEC` e ritornava 0 senza
chiamare l'op. Il primo è quello che conta: dentro passa
`b43_nphy_op_software_rfkill()` → `b43_radio_2057_init()` → tabella di init del
radio. E `setup()` metteva `radio_on = true`, quindi anche chiamandolo il radio
non si sarebbe inizializzato: sull'hardware ci si arriva sempre con `radio_on`
falso, perché `b43_phy_exit()` fa `software_rfkill(true)`.

Sistemati, il trace ora apre con le stesse quattro scritture AFE della cattura
(#6-#9) e contiene la tabella di init del radio.

### I tre blocchi che restano

| dove | op | di chi | cosa |
|---|---|---|---|
| init del radio | **342** | solo port | b43 carica tutte le 412 voci di `r2057_rev8_init`; il vendore, a caldo, scrive **70 registri distinti** (77 scritture), e tutti e 70 sono un sottoinsieme dei 412 |
| p@37-557 | **520** | solo port | `TBL.WR id=0x20 0x22 0x1f 0x21`, le tabelle scalare ed epsilon del PAPD: `patches/b43/0004` le scrive in `b43_phy_initn`, il vendore dentro `wlc_phy_a4` (#10966-#11740) |
| v@578-751 | 173 | solo vendore | tabella 8, object memory, 45 letture PHY: non attribuito |

Sul primo: non è un artefatto del tracer. `PHY.ARRW` è solo un marcatore e le op
che ne discendono sono tutte nel trace (`docs/blob-inventory.md`), e comunque
`phy_reg_write_array` scrive registri **PHY**, non radio: le scritture radio
passano da `write_radio_reg`, che è agganciato. Quindi il vendore scrive davvero
70 registri dove b43 ne scrive 412.

Nemmeno brcmsmac lo fa: `wlc_phy_radio_init_2057` carica la tabella intera a ogni
init, e i suoi due `phy_init_por` (`phy_n.c:19968`, `20056`) coprono solo
rcal/rccal, esattamente come b43. È una differenza fra `wl 6.30` e i due driver
GPL, non un errore di trascrizione. **SALAME** su cosa la giustifichi: che wl
tenga uno specchio e riscriva solo ciò che cambia è un'ipotesi, non l'ho
verificata, e non so se le 342 scritture in più siano innocue o no.

Il blocco da 520 invece non è un buco del port: è `0004` che sta nel posto
sbagliato. Finché quelle scritture stanno nell'init, **l'init non si allinea per
costruzione**, e questo risolve empiricamente la scelta della sezione qui sotto:
la 1 non basta, serve la 2.

| | port | cattura |
|---|---|---|
| prime op | tabella 9 volatile (antswlut) | array di initvals e AFE |
| init table del radio | assente dal flow | #100-#108 |
| da qui in poi | stesso ordine | stesso ordine |

## Il flusso, fase per fase

`b43_phy_initn()` sta in `phy_n.c:6130-6345`, `wlc_phy_init_nphy()` in
`brcmsmac/phy/phy_n.c:19197-19548`. Le due funzioni hanno la **stessa forma**: b43
è un port di quella, chiamata per chiamata.

| # | fase | b43 | port | cattura | brcmsmac | stato |
|---|---|---|---|---|---|---|
| 1 | tabelle N-PHY | `b43_nphy_tables_init` | 1 | — | `wlc_phy_tbl_init_nphy` | ok |
| 2 | mimo config, txrx chain | `b43_nphy_update_{mimo_config,txrx_chain}` | | | `wlc_phy_{update_mimoconfig,stf_chain_upd}_nphy` | ok |
| 3 | **offset epsilon** + `PAPD_EN0/1` | `b43_nphy_papd_epsilon_offset` | 7329 | #286-#288 | coda di `wlc_phy_a4` (non l'init!) | **`0009`** |
| 4 | tabelle scalare ed epsilon | `b43_nphy_papd_tables_init` | 7332 | #10966+ (nella cal) | `wlc_phy_a4` (non l'init!) | **`0004`** |
| 5 | filtri digitali TX | `b43_nphy_int_pa_set_tx_dig_filters` | 7852 | #289-#348 | `wlc_phy_ipa_set_tx_digi_filts_nphy` | 45/60, resto idempotente |
| 6 | workaround, phase track | `b43_nphy_workarounds` | 7900 | #349-#362 | `wlc_phy_workarounds_nphy` | ok |
| 7 | bias IPA 2 GHz | dentro i workaround rev 7+ | 8139 | #605-#607 | `wlc_phy_workarounds_nphy_rev7` | **`0005`**, 3/3 |
| 8 | soglie CRS + gain control RX | dentro i workaround | 8207 | #680-#770 | `wlc_phy_workarounds_nphy_gainctrl` | **`0008`+`0001`**, 87/87 |
| 9 | classifier, clip detection | `b43_nphy_{classifier,read_clip_detection}` | | | `wlc_phy_{classifier,clip_det}_nphy` | ok |
| 10 | tx power control, fixpower | `b43_nphy_tx_power_{ctrl,fix}` | | | `wlc_phy_txpwr{ctrl_enable,_fixpower}_nphy` | valori diversi, `todo-nphy` 3 |
| 11 | setup TSSI interno | `b43_nphy_ipa_internal_tssi_setup` | 8546 | #1251-#1281 | `wlc_phy_ipa_internal_tssi_setup_nphy` | un'op in più, `todo-nphy` 3d |
| 12 | **tono a ampiezza 0** (idle TSSI) | `b43_nphy_tx_tone(4000, 0)` | 8568 | #1288-#1609 | `wlc_phy_tx_tone_nphy` | **`0010`**, 322/322 |
| 13 | poll dell'idle TSSI | `b43_nphy_poll_rssi` | | #1668-#1678 | `wlc_phy_txpwrctrl_idle_tssi_nphy` | ok |
| 14 | tx power ctl setup | `b43_nphy_tx_power_ctl_setup` | | | `wlc_phy_txpwrctrl_pwr_setup_nphy` | ok |
| 15 | tx gain table + **compensazione PAPD** | `b43_nphy_tx_gain_table_upload` | 9938 | #2688-#2703 | `wlc_phy_get_ipa_gaintbl_nphy` | **`0003`**, 16/16 |
| 16 | cal RSSI | `b43_nphy_rssi_cal` | 11069 | fino a #3719 | `wlc_phy_rssi_cal_nphy` | polling sfasato, 4bis/4ter |
| 17 | coefficienti RSSI | `b43_nphy_scale_offset_rssi` | 11417 | #3723-#3740 | idem | 1/16 |
| 18 | cal TX IQ/LO | `b43_nphy_cal_tx_iq_lo` | solo `initcal` | #8527-#8638 | `wlc_phy_cal_txiqlo_nphy` | **non nel flow `init`** |
| 19 | **cal PAPD** | *non esiste* | — | #10962-#14092 | `wlc_phy_a4` | `papd-cal-map.md` |
| 20 | regione non attribuita | — | — | #14093-#15920 | ? | non attribuita |
| 21 | cal RSSI, secondo giro | — | — | #22247-#23771 | `wlc_phy_rssi_cal_nphy` | fuori dal flow del port |
| 22 | coef. tx power, tx lpf bw, spur | `b43_nphy_tx_pwr_ctrl_coef_setup`, `b43_nphy_tx_lpf_bw` | | | omonime | ok |

Le celle vuote nella colonna **port** sono fasi che nel trace non hanno un'op
abbastanza distintiva da ancorarle senza ambiguità: ci sono, ma non le ho
localizzate a mano.

## E adesso il punto: perché b43 non arriva alla cal PAPD

Non è "b43 non ha `wlc_phy_a4`". È che **nemmeno brcmsmac chiama `a4`
dall'init**, e la strada che ci arriva in b43 è uno stub vuoto.

Guardando la coda delle due funzioni, il blocco delle calibrazioni ha due rami:

```
b43:                                    brcmsmac:
if (nphy->perical != 2) {               if (pi->nphy_perical != PHY_PERICAL_MPHASE) {
    b43_nphy_rssi_cal();                    wlc_phy_rssi_cal_nphy();
    b43_nphy_cal_tx_iq_lo();                wlc_phy_cal_txiqlo_nphy();
    b43_nphy_cal_rx_iq();                   wlc_phy_cal_rxiq_nphy();
    b43_nphy_save_cal();                    wlc_phy_savecal_nphy();
} else if (mphase_cal_phase_id == 0) {  } else if (mphase_cal_phase_id == IDLE) {
    ; /* N PHY Periodic Calibration      wlc_phy_cal_perical(pi, PHY_PERICAL_PHYINIT);
         with arg 3 */                  }
}
```

Tre cose, e la terza è quella che conta:

1. **`PHY_PERICAL_MPHASE` vale 2** (`brcmsmac/phy/phy_hal.h`), e
   `b43_nphy_op_prepare_structs()` mette `perical = 2`. Quindi b43, di default,
   prende il **secondo** ramo.
2. Il secondo ramo di b43 è un punto e virgola con un commento. Il commento
   nomina anche l'argomento giusto: `arg 3` è `PHY_PERICAL_PHYINIT`. È l'unico
   punto dell'init da cui si arriva alla cal periodica, e da lì a `a4`:
   `wlc_phy_cal_perical` → `wlc_phy_cal_perical_nphy_run` → `cal_txiqlo` → **`a4`**.
3. Il **primo** ramo, quello che gira con `perical != 2`, non chiama `a4`
   nemmeno in brcmsmac.

Da cui la conseguenza contro-intuitiva, e la ragione per cui vale la pena
scriverla: il flow `initcal` dell'harness mette `perical = 0` per "accendere le
calibrazioni", e così prende il **primo** ramo — quello che la cal PAPD **non ce
l'ha**. Nessuno dei due flow dell'harness può mostrare la cal PAPD, e non perché
manchi `a4`: manca il dispatcher della cal periodica, che è anche il posto da cui
la cal RSSI, la TX IQ/LO e la RX IQ vengono rifatte nel tempo.

La cattura conferma di essere passata da lì: l'ordine è cal TX IQ/LO (#8527-#8638)
e **subito dopo** la cal PAPD (#10962), che è esattamente
`cal_perical_nphy_run` — `cal_txiqlo` poi `a4`.

## Il problema che ne segue, e che va deciso prima di scrivere

`0004` e `0009` mettono in `b43_phy_initn` due cose che brcmsmac fa **dentro
`a4`**: l'inizializzazione delle tabelle scalare/epsilon (riga 4 della tabella) e
il calcolo dell'offset epsilon (riga 3). Era la scelta giusta finché la cal non
c'è: senza, il motore PAPD gira su tabelle non inizializzate e con 24 dB di offset
sbagliato.

Quando la cal arriva, le tre uscite sono:

| | cosa | costo |
|---|---|---|
| 1 | lasciarle in `initn` e farle **rifare** anche dalla cal | le scritture sono idempotenti e la cattura le fa due volte con lo stesso valore (offset epsilon a #286 e a #13842), quindi funziona; ma l'init del port fa lavoro che l'init del vendore non fa, e le finestre `papd-tables` e `papd-comp` misurano la posizione dell'init invece di quella della cal |
| 2 | spostarle nella cal, e chiamare la cal dall'init anche con `perical = 2` | è ciò che serve perché il port assomigli al vendore, ma cambia il flusso di init di **tutte** le N-PHY e non è gateabile sulla revisione senza inventare un ramo che il vendore non ha |
| 3 | spostarle nella cal e accettare che all'init non girino | il più fedele a brcmsmac, il peggiore in pratica: torna il motore PAPD su tabelle non inizializzate ogni volta che la cal non parte |

**La misura ha deciso**: la 1 lascia in `initn` 520 op che la cattura non ha in
quel punto, quindi con la 1 l'init non si allinea mai. Serve la 2 — spostarle
nella cal e rendere la cal raggiungibile dall'init — e il fatto che sia anche
l'unica strada verso la cal PAPD non è una coincidenza: è lo stesso ramo
`perical`.
