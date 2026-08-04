# 20 — Copertura dell'init PHY

Confronto fra la cattura vendor grezza e l'harness del port, per sequenza.

Board: D-Link DSL-3580L      Flow: due `wl down`/`wl up` + 31 cambi canale
Canali: operativi 1 e 6, escursioni a 5 / 2 / 10, tutti bw20
Commit tree: 848acc8ffe1b
Cattura vendor: `router-data/dsl-3580l/` (70796 record, 0 drop, 0 gap)
Blob: `wl 6.30.102.7.cpe4.12L07.0`

Nota: l'harness del port non esiste ancora (vedi `test/README.md`), quindi la
colonna "op port" non è compilabile. Le righe qui sotto sono il confronto fra la
cattura e il **codice** b43, fatto a mano: serve come base per l'harness, non lo
sostituisce.

| funzione | op vendor | op port | match | note |
|---|---|---|---|---|
| `b43_radio_2057_chantab_upload` (2g) | 18 `RAD.WR` per cambio canale | — | **valori e ordine identici** | 31/31 cambi, canali 1, 2, 5, 6, 10 |
| chantab, campi 5 GHz | 10 `RAD.WR` a 0 | — | **assenti nel port** | voce aperta, `docs/trace-init-2g.md` |
| `b43_radio_2057_setup`, loopfilter | nessuna scrittura extra | — | ok | i valori arrivano dalla chantab |
| `b43_nphy_gain_ctl_workarounds_rev7` | 3 `PHY.MOD` + 8 `TBL.WR` + 4 `PHY.WR` + 2 `PHY.MOD` | — | **stub in mainline** | `patches/b43/0001` scritta su questi numeri, identici nei due init |
| workaround AFE (tbl 8) | 4 `TBL.WR` | — | da verificare | tabella 8 = AFECTRL, altro workaround |
| `si_pmu_spuravoid` | 0 record | — | — | il vendore non lo chiama su questo SoC |

Totale cattura: 70796 op su 39.8 s, due sequenze di init complete.

## Criterio di accettazione

- [x] nessun `OP_DROP` nella cattura di riferimento
- [x] nessuna discontinuità di sequenza
- [ ] gap fra funzioni spiegati uno per uno (in corso: gain control fatto,
      AFE e il resto dell'init no)
- [ ] harness del port esistente e confrontabile con `test/compare.py`
