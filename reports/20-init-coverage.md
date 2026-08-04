# 20 — Copertura dell'init PHY

Confronto fra la cattura vendor grezza e l'harness del port, per sequenza.

Board: D-Link DSL-3580L      Flow: due `wl down`/`wl up` + 31 cambi canale
Canali: operativi 1 e 6, escursioni a 5 / 2 / 10, tutti bw20
Commit tree: 848acc8ffe1b
Cattura vendor: `router-data/dsl-3580l/` (70796 record, 0 drop, 0 gap)
Blob: `wl 6.30.102.7.cpe4.12L07.0`

L'harness esiste (`test/`): compila i sorgenti N-PHY del tree in userspace e
emette un trace nello stesso formato. Le righe con la colonna "op port" piena
sono confronti veri; le altre sono ancora lettura a mano del codice.

| funzione | op vendor | op port | match | note |
|---|---|---|---|---|
| `b43_radio_2057_chantab_upload` (2g) | 18 `RAD.WR` per cambio canale | **18** | **valori e ordine identici** | trace: 31/31 cambi su 5 canali; harness: ch6 |
| chantab, campi 5 GHz | 10 `RAD.WR` a 0 | **0** | **assenti nel port**, confermato dall'harness | voce aperta, `docs/trace-init-2g.md` |
| `b43_radio_2057_setup`, loopfilter | nessuna scrittura extra | — | ok | i valori arrivano dalla chantab |
| `b43_nphy_gain_ctl_workarounds_rev7`, mainline | 21 op | **0** | stub vuoto | non scrive niente |
| la stessa, con `patches/b43/0001` | 21 op | **21** | **match posizionale, payload inclusi** | 8 table-op con valori identici |
| workaround AFE (tbl 8) | 4 `TBL.WR` | — | da verificare | tabella 8 = AFECTRL, altro workaround |
| `si_pmu_spuravoid` | 0 record | — | — | il vendore non lo chiama su questo SoC |

Totale cattura: 70796 op su 39.8 s, due sequenze di init complete.

Copertura misurata con `test/coverage.py` contro il primo init (132-26100), con
`patches/b43/0001` applicata al tree. Su mainline pulito il flow `full` fa
175/218 registri PHY e 122/533 celle: la differenza è quella patch.

| | flow `init` | flow `full` | `full` con 0001+0002+0003 |
|---|---|---|---|
| registri PHY | 173/218 (79%) | 186/218 (85%) | 186/218 (85%) |
| registri radio | 19/54 (35%) | 39/54 (72%) | 39/54 (72%) |
| celle di tabella | 86/533 (16%) | 130/533 (24%) | **386/533 (72%)** |
| op emesse | 11675 | 14572 | 15598 |

Le prime due colonne di `full` sono con la sola `0001`; su mainline pulito fa
175/218 PHY e 122/533 celle. Il salto delle celle viene da `0003`, che abilita la
compensazione PAPD: 256 celle in più, e tutte identiche alla cattura.

I piani di lettura generati dalla cattura (149 indirizzi, 2089 read appaiate) non
cambiano nessuna di queste cifre: 72 piani su 149 vengono consumati, ma la
copertura è identica con e senza. Le fasi che mancano non mancano per un valore
letto sbagliato, mancano per early return e gate di revisione nel driver.

I 677 offset SHM del vendore restano a zero: li scrive il core di b43, che
l'harness non compila. Delle 403 celle ancora mancanti in `full`, 260 sono le
tabelle 26 e 27 (TX power control) che il driver **non può** scrivere finché
`b43_nphy_tx_pwr_ctl_init()` ritorna subito per `phy->rev >= 7`, e 128 sono le
tabelle 31 e 33, da attribuire.

## Criterio di accettazione

- [x] nessun `OP_DROP` nella cattura di riferimento
- [x] nessuna discontinuità di sequenza
- [ ] gap fra funzioni spiegati uno per uno (in corso: gain control fatto,
      AFE e il resto dell'init no)
- [x] harness del port esistente e confrontabile con `test/compare.py`
- [x] piani di lettura dai `RETVAL` della cattura — fatti, e misurato che non
      spostano la copertura: il residuo è strutturale
- [x] tabelle 26 e 27: erano l'early return del percorso PAPD, `patches/b43/0003`
- [ ] attribuire le tabelle 31 e 33 (64 celle ciascuna) e i 32 registri PHY
      ancora scoperti
