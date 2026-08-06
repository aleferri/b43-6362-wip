# Provenienza dei dati

## Blob OEM

`wl 6.30.102.7.cpe4.12L07.0`, estratto dal firmware stock della D-Link
DSL-3580L (`wlDSL-3580_EU.o`), ELF32 MIPS big-endian relocatable non strippato.
Il blob **non sta in questo repo**: è materiale proprietario D-Link/Broadcom.
Gli strumenti lo prendono come argomento su una copia locale.

Da esso vengono, e sono verificabili con `reverse-tools/blob_tables.py`:

| tabella b43 | simbolo nel blob | esito |
|---|---|---|
| `r2057_rev8_init` (412 entry) | `regs_2057_rev8` (413 record, stride 6) | 412/412 identici |
| `b43_ntab_tx_gain_ipa_2057_rev8_2g` (128 u32) | `nphy_tpc_txgain_ipa_2g_2057rev8` | 128/128 identici |
| `b43_ntab_rf_pwr_offset_2057_rev8_2g` (32 s16) | `nphy_papd_padgain_dlt_2g_2057rev5` | 32/32 identici |
| `b43_nphy_chantab_phy_rev8_radio_rev8` (14 entry) | `chan_info_nphyrev8_2057_rev8` (123 record, stride 44) | 336/336 campi identici (`chantab_from_blob.py`) |

## Codice di riferimento GPL

`brcmsmac` in-tree (`drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c`)
è il riferimento legittimo per capire cosa il vendor programma su N-PHY rev 8 /
radio 2057 rev 8. `reverse-tools/brcmsmac_xref.py` produce l'elenco delle
funzioni interessate.

## Cosa si guarda del blob

Del blob servono due cose, e sono limitate: i simboli con le loro size (per
estrarre le tabelle statiche, che è quello che fa `blob_tables.py`) e i prologhi
e le uscite degli accessor da agganciare, quanto basta a sapere se il detour del
tracer regge su quella funzione — se c'è un branch nelle prime quattro parole,
il modulo la corrompe.

Il criterio che tiene insieme le due voci e' **dove va il prodotto**. Localizzare
i simboli e i siti di chiamata serve a costruire lo strumento di misura: il
risultato e' `wl-diag`, che osserva l'hardware, e senza quei siti gli hook non si
possono installare. Leggere il corpo di una funzione per sapere *cosa fa il
driver* produce invece un'affermazione sul comportamento, e quella affermazione
finirebbe nel port: quella strada non si prende, e per le stesse domande si guarda
`brcmsmac`, che e' GPL e pubblicato dallo stesso vendore.

Questo perimetro e' stato **superato una volta**, e conviene dire come: per
attribuire un ciclo di misura visto in una cattura sono stati disassemblati corpi
di funzione, elencati i chiamanti e cercata una costante su tutto `.text`. Le
conclusioni erano giuste ma la fonte no, e sono state rifatte su `brcmsmac` — dove
c'erano tutte, una perfino migliore: `wlc_phy_aci_scan_nphy` sta in
`phy/phy_int.h:1097` come **prototipo senza corpo**, che dice piu' di qualunque
disassemblato sul fatto che quella e' una politica sopra il PHY. La lezione: le
domande sul comportamento si portano a `brcmsmac` **prima**, non dopo.
