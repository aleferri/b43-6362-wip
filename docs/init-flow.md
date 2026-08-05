# Il flusso di init, i due lati affiancati

Serve per rispondere a una domanda che torna sempre: *quando succede cosa, e da
che parte*. Le colonne sono misurate, non ricostruite a memoria:

- **port**: numero di riga nell'output di `./nphy_trace init dsl3580l 1`. **I
  numeri di questa colonna sono da rigenerare**: vengono dal trace da 13223 op
  dell'harness che modellava sempre l'init a freddo (vedi sotto), non da quello di
  adesso, che con la serie `0001..0013` fa 5079 op;
- **cattura**: numero di record in `opinit-ch1-ch6-bw20.decoded`, primo init;
- **brcmsmac**: la funzione, trovata con `reverse-tools/cfuncs.py`.

## Prima cosa da sapere: dove i due divergono, e dove no

Il README dice che i due ordinano le fasi in modo diverso, "il port comincia
dalle tabelle, il vendore dal radio". È vero solo a metà, e la metà mancante
spiegava da sola il grosso del disallineamento.

**b43 e brcmsmac hanno la stessa distinzione fra init a freddo e init a caldo.**
`dev->phy.do_full_init` in b43 è `pi->phy_init_por` in brcmsmac, stessa
semantica: vero all'attach (`main.c:5407`) e dopo `b43_phy_exit()`, azzerato da
`b43_phy_init()` appena `ops->init()` è andata bene (`phy_common.c:105`). Dietro
quel flag stanno, in b43, il download delle tabelle statiche (quattro siti in
`tables_nphy.c`, con i commenti `/* Static tables */` e `/* Volatile tables */`
già scritti) e `b43_radio_2057_rcal`/`rccal` (`phy_n.c:1026`). In brcmsmac sta
`wlc_phy_static_table_download_nphy` (`phy_n.c:14178`), chiamata dietro il
`phy_init_por` di `wlc_phy_tbl_init_nphy` (`phy_n.c:14206`), e gli stessi rcal.

**La cattura non è un init a freddo.** `PHY.WR addr=0x72 val=0x2800`, l'apertura
della tabella 10 con cui il download statico comincia, non compare in nessuno dei
due init dei 70796 record — zero occorrenze qui, due in `full-init-ch1-bw20`. È
quel marcatore a distinguerli, **non il numero di aperture di tabella**: sono 950
e 953 nei due init a caldo e 935 nella parte contigua dell'init a freddo, perché
il download statico apre poco e scrive in bulk. Si vede nelle scritture, non nelle
aperture: 47566 `PHY.WR` nella cattura a freddo contro 38616 qui. Quando il tracer
è partito, il driver del vendore aveva già fatto il suo init a freddo.

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
primo cambio canale — sono tutte in codice **già compilato**, e l'harness non le
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
| init del radio | ~300 | solo port | b43 scrive 488 op su 412 registri radio; il vendore 193 su 90. **Non e' un buco**: le 412 voci sono deliberate e lo stub da 54 impianta il radio, vedi `gap-inventory.md` 4h |
| tabelle PAPD | — | **chiuso da `0012`** | erano 520 op nel posto sbagliato: `0004` le scriveva in `b43_phy_initn`, ora stanno nella cal come nella cattura |
| v@578-751 | 173 | solo vendore | tabella 8, object memory, 45 letture PHY: non attribuito |

Sul primo, il conto va fatto **per fase**: una finestra di record scelta a occhio
come 60-400 mescola l'upload della tabella di init, il `radio_2057_setup` e il primo
cambio canale, e ne esce che 32 registri su 70 hanno un valore diverso da quello
della tabella — la firma di scritture che vengono da un'altra fase.

Il numero che regge è quello su tutto l'init: 193 scritture radio su 90 registri
distinti dal lato vendore, 488 su 412 dal lato port. La conclusione qualitativa
non cambia — b43 scrive molti più registri radio — ma il conto esatto di quali e
in quale fase è da rifare per fase, non su una finestra a occhio.

### L'init del radio, contato per fase

Delimitando la fase come si deve — tutto ciò che sta **prima del primo
`CHANSPEC`**, cioè #132, che è dove `b43_switch_channel()` prende il posto
dell'init del radio — il conto è pulito e dice una cosa sola:

| | valore |
|---|---|
| scritture radio del vendore nella fase | **45** |
| registri distinti | **43** |
| di cui col valore *identico* alla tabella di b43 | **41** |
| col valore diverso | 4 (`0x164`, `0x2e`, `0xce`, `0x11`) |
| registri fuori dalla tabella di b43 | **0** |
| voci che b43 scrive | **412** |

Quindi non è una fase diversa e non sono registri diversi: è **lo stesso
sottoinsieme**, 43 registri su 412, con 41 valori su 45 identici. b43 ne scrive
412. I 4 valori diversi sono la prossima cosa da guardare — `RAD.MOD` esiste nella
cattura, quindi almeno alcuni potrebbero essere read-modify-write resi come WR dal
decoder, e va verificato prima di trarne conclusioni.

E non è un artefatto del tracer. `PHY.ARRW` è solo un marcatore e le op
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

`b43_phy_initn()` sta in `phy_n.c:5976-6186`, `wlc_phy_init_nphy()` in
`brcmsmac/phy/phy_n.c:19196-19548`. Le due funzioni hanno la **stessa forma**: b43
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
| 17 | coefficienti RSSI | `b43_nphy_scale_offset_rssi` | 11417 | #3723-#3740 | idem | 11/16 |
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

## Quanto siamo lontani dalla run del vendore, per regione

    ./phase_compare.py --vendor router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded \
                       --global-run 132 26100 --flow full --channel 6

| regione | record | op | appaiate | |
|---|---|---|---|---|
| init vero e proprio | #132-10961 | 9692 | 3488 | 36% |
| cal PAPD (`a4`) | #10962-14092 | 2662 | 694 | 26% |
| non attribuita | #14093-15920 | 1698 | 84 | 5% |
| **non attribuita, upload di tabella** | #15921-22246 | 5812 | 514 | **9%** |
| seconda cal RSSI | #22247-23771 | 960 | **0** | **0%** |
| coda | #23772-26100 | 2127 | 618 | 29% |

Totale: 5398 op su 22951, il 24%. Col flow `init` da solo sono 4425, il 19%.

Le percentuali sono **un limite inferiore**: il confronto è posizionale, quindi
un'op presente con lo stesso valore ma in un altro punto conta come non appaiata,
ed è la ragione per cui esistono le finestre con `equiv='multiset'`.

Le finestre verdi e il 36% dell'init non sono in contraddizione: le finestre
coprono fasi precise, e nell'init c'è molto che non sta in nessuna finestra.

La regione da guardare è **#15921-22246**, la più grande e la meno esplorata, più
grande della cal PAPD. È dominata da upload di tabella: 93 `TBL.WR` il cui payload
sono ~5000 op sui registri `0x72`/`0x73`/`0x74`, sulle tabelle 15 (IQLOCAL), 26 e
27 (gain e potenza del tx power control) e 17. Più `0x129` 118 volte. Nessuno l'ha
ancora attribuita.

E la seconda cal RSSI è a **zero**: di quelle 960 op il port non ne azzecca
nessuna, non una parte. È il tipo di numero che dice "questa fase non esiste", non
"questa fase è sfasata".

### Perche' la ripartizione va presa da `--global-run`

`CMP.load_vendor()` scarta le righe di bookkeeping, le ombre delle `SI.COREREG` e le
ombre read-modify-write, quindi **l'indice nella lista di op non e' il numero di
record**. Ricostruire la corrispondenza a mano da' un allineamento che va alla deriva:
fino a 230 op di scarto per regione, con la seconda cal RSSI che risulta al 5% invece
che a zero.

`compare.py` ha `Op`, una sottoclasse di `str` che si porta dietro il numero di record
attraverso tutta la normalizzazione, ed e' `--global-run` a stampare la tabella. Il
totale non dipende da quella corrispondenza, la ripartizione si'.

## L'init a freddo, ora confrontabile

`router-data/dsl-3580l/full-init-ch1-bw20.decoded` e' un init a freddo, quindi il
flow `initpor` dell'harness ha finalmente un riferimento. La parte utilizzabile della
cattura sono i record **#2-#32769**, contigui, prima del buco da overflow.

    cd test && ./nphy_trace initpor dsl3580l 1 > /tmp/por.out
    # confronto con difflib fra /tmp/por.out e i record #2-#32769

| | |
|---|---|
| op del vendore, #2-#32769 | 32056 |
| op del flow `initpor` | 13468 |
| in comune | **7200 (22%)** in 330 blocchi |

E il **download delle tabelle statiche combacia**, che e' la cosa che prima non aveva
alcun riscontro: run di **1424** e **806** op consecutive aperte da
`PHY.WR addr=0x72 val=0x3400` e `val=0x4800`, piu' 258 su `val=0x6840`. Sono le
tabelle N-PHY scritte una dietro l'altra con gli stessi valori nello stesso ordine.

Il 22% complessivo non va letto come "il port sbaglia il 78%": il vendore in un init
a freddo emette 32056 op contro le 13468 del port, e la differenza sono in buona parte
fasi che b43 non ha — la cal PAPD, `rcal`/`rccal`, e la cal RSSI che nel port non gira.
Il confronto per fase resta quello delle finestre di `phase_compare.py`.

Nota per chi rifa' la misura: le finestre di `phase_compare.py` sono ancorate alla
cattura `opinit-*`, che e' a caldo. Per confrontare `initpor` serve passare l'altra
cattura a mano, e una finestra per il download statico non c'e' ancora.
