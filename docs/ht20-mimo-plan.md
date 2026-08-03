# Piano per HT20 2x2

Obiettivo: il radio integrato del 6362 associa e trasporta traffico a MCS 0-15
in HT20, due stream spaziali, con b43 mainline. HT40 e 5 GHz fuori scope.

## Punto di partenza

b43 non ha nulla di HT: nessuna occorrenza di `ht_cap` o `IEEE80211_HT`,
`b43_band_2GHz` monta solo `b43_g_ratetable`, `b43_generate_tx_phy_ctl1()`
gestisce solo rate legacy con banda fissa a `B43_TXH_PHY1_BW_20`, e in RX
`b43_plcp_get_bitrate_idx_{cck,ofdm}()` non conosce l'HT-SIG.

Quello che c'è già e serve: in `xmit.h` sono definiti i campi MIMO del TX
header (`B43_TXH_PHY1_MODE_{SISO,CDD,STBC,SDM}`, CRATE, MODUL), e il firmware
`ucode22_mimo` è quello che il vendor usa per l'11n su questo core.

## Milestone

### M0 — base legacy sana (prerequisito, nessuna riga di HT)

Chiude i buchi 1-4 di `gap-inventory.md`: gain control rev7, RFPLL loopfilter,
rcal, tx cal radio setup. Criterio di uscita: `reports/30-rx-sensitivity.md` e
`60-regression-legacy.md` compilati, con il legacy 2.4 GHz non peggiore di
prima su tutti i canali e sensibilità RX misurata invece che sperata.

Motivo per cui viene prima: se l'AGC è tarato male, ogni misura MIMO successiva
misura l'AGC, non il MIMO.

### M1 — due catene attive in ricezione

`rxchain = 3` stabile, RSSI per-core plausibile su entrambe le catene, RX
diversity funzionante a rate legacy. Criterio: differenza fra le due catene
entro pochi dB su un segnale noto, e nessuna catena morta.

### M2 — RX HT

Decodifica dell'HT-SIG e riporto a mac80211: `RX_ENC_HT`, indice MCS, flag SGI
e LDPC dove applicabile. Non serve trasmettere HT per validarlo: basta un AP
11n che trasmette e contare i frame decodificati per MCS.

### M3 — TX HT SISO (MCS 0-7)

PLCP MIMO, `phy_ctl1` con MCS/stream/bw, `ht_cap` annunciato con **un solo**
stream (`rx_mask` 0xFF) per separare i problemi di PLCP da quelli di MIMO.
Criterio: iperf stabile a MCS 7, senza retry storm.

### M4 — TX HT 2 stream (MCS 8-15)

Passaggio a SDM, `rx_mask` 0xFF 0xFF, tx power per-core, calibrazione su due
catene. Criterio: `reports/50-throughput-ht20.md` con throughput per MCS e
distribuzione dei retry.

### M5 — pulizia per l'upstream

Serie divisa per argomento, senza `#ifdef` di comodo; aggregazione (AMPDU)
deliberatamente **fuori**, dichiarata come non supportata invece che
mezza-implementata.

## Cose che non ho verificato e che vanno chiarite prima di M3

- se l'`ucode22_mimo` disponibile espone davvero i rate 11n via le stesse
  strutture che b43 usa per il legacy (vedi `firmware-rev22.md`);
- se servono initvals aggiuntivi per la modalità MIMO oltre a
  `n0initvals22`/`n0bsinitvals22`;
- come il vendor sceglie fra CDD, STBC e SDM in funzione del rate e delle
  catene attive. **SALAME**: mi aspetto SDM per gli MCS 8-15 e CDD per gli MCS
  0-7 su due catene, che è quello che fa brcmsmac, ma non l'ho tracciato su
  questo blob.
