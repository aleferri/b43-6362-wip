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
| la stessa, con `patches/b43/MESSAGES.md#0001` | 21 op | **21** | **match posizionale, payload inclusi** | 8 table-op con valori identici |
| workaround AFE (tbl 8) | 4 `TBL.WR` | — | da verificare | tabella 8 = AFECTRL, altro workaround |
| `si_pmu_spuravoid` | 0 record | — | — | il vendore non lo chiama su questo SoC |

Totale cattura: 70796 op su 39.8 s, due sequenze di init complete.

## Confronto posizionale, per finestra

`test/phase_compare.py`, che è il metodo di `b43-ac-wip`: diff op-per-op dentro
una finestra allineata, sulla cattura passata per `merge_retvals.py`.

Sono 14 finestre; qui le sette dell'init, con la serie `0001..0013` applicata.
L'elenco completo, `static-tables` e le due fasi della cal PAPD comprese, sta in
`test/README.md`.

| finestra | op | run più lunga | esito |
|---|---|---|---|
| gain-control | 87 | 87/87 | **ok** |
| papd-comp | 16 | 16/16 | **ok** |
| papd-tables | 774 | 260/774 | mancano 256, in più 256: stesse celle e stessi valori, 64 scritture singole contro un bulk |
| ipa-bias | 3 | 3/3 | **ok** |
| chanswitch-ch6 | 39 | 33/39 | **nessuna op mancante** da `0011`; la coda è sfasata di tre MMIO |
| tssi-setup | 19 | 5/19 | mancano 4, in più 15 |
| rssi-cal | 16 | 1/16 | i nove valori combaciano dopo la patch mainline sulla cal RSSI; il port scrive ogni coefficiente due volte e la finestra è posizionale (vedi `test/README.md`) |

Run più lunga globale sul primo init, senza scegliere una fase: **1543 op
consecutive** col flow `init`, e 4434 op in comune su 22951 in 466 blocchi. Col
flow `full` sono 5398 su 22951 in 677 blocchi.

Le quattro finestre delle patch passano op per op, valori inclusi. È la garanzia
che la copertura per insiemi non dà.

## Copertura per insiemi

Copertura misurata con `test/coverage.py` contro il primo init (132-26100). Su
mainline pulito il flow `full` fa 175/218 registri PHY e 878/1987 celle.

Le celle sono contate espandendo le table-op (un'op di lunghezza N copre N
celle): le percentuali sono diverse da quelle di prima perché è cambiata la
misura, non il port.

Flow `full`, contro il primo init:

| | mainline | +`0001`..`0003` | +`0004` | +`0005` | serie intera |
|---|---|---|---|---|---|
| registri PHY | 175/218 (80%) | 186/218 (85%) | 186/218 (85%) | 186/218 (85%) | **190/218 (87%)** |
| registri radio | 39/54 (72%) | 39/54 (72%) | 39/54 (72%) | 40/54 (74%) | **50/54 (93%)** |
| celle di tabella | 878/1987 (44%) | 1190/1987 (60%) | **1446/1987 (73%)** | 1446/1987 (73%) | 1446/1987 (73%) |
| op emesse | 14490 | 15597 | 16117 | 16117 | 16131 |

I dieci registri radio dell'ultima colonna sono i campi 5 GHz di `0011`, e i
quattro PHY le soglie CRS di `0008`. `0010` non muove nessuna di queste cifre:
misurato applicando `0001..0009` e poi `0010`, le quattro righe restano identiche
— quella patch cambia cosa finisce nelle celle della tabella 17, non quali celle
vengono toccate.

Con la serie e il flow `init`, quello che imita il vendore, **il port non tocca
più niente che il vendore non tocchi**. Nel flow `full` restano quattro celle
IQLOCAL, che vengono dalla calibrazione forzata dell'harness e non dal driver.

I due salti sono `0003` (compensazione PAPD, 256 celle) e `0004` (tabelle
epsilon e scalare, 256 celle), e in entrambi i casi ogni valore coincide con la
cattura.

I piani di lettura generati dalla cattura (149 indirizzi, 2089 read appaiate) non
cambiano nessuna di queste cifre: nel flow `full` 70 piani su 149 vengono
consumati, ma la copertura è identica con e senza. Le fasi che mancano non mancano
per un valore letto sbagliato, mancano per early return e gate di revisione nel
driver.

Dei 677 offset SHM del vendore il port ne scrive due, e non sono confrontabili
(encoding diverso, vedi `test/README.md`); gli altri 675 li scrive il core di b43,
che l'harness non compila. Delle 541 celle ancora mancanti in `full` con la serie,
512 sono le tabelle 26 e 27 (TX power control) che il driver **non può** scrivere
finché `b43_nphy_tx_pwr_ctl_init()` ritorna subito per `phy->rev >= 7`; le altre
29 stanno nelle tabelle 8, 9, 15 e 7. Le tabelle 31 e 33 non mancano più: le
inizializza `0004`.

## Criterio di accettazione

- [x] nessun `OP_DROP` nella cattura di riferimento
- [x] nessuna discontinuità di sequenza
- [ ] gap fra funzioni spiegati uno per uno (in corso: gain control fatto,
      AFE e il resto dell'init no)
- [x] harness del port esistente e confrontabile con `test/compare.py`
- [x] piani di lettura dai `RETVAL` della cattura — fatti, e misurato che non
      spostano la copertura: il residuo è strutturale
- [x] tabelle 26 e 27: erano l'early return del percorso PAPD, `patches/b43/MESSAGES.md#0003`
- [x] tabelle 31, 32, 33, 34: epsilon e scalare del PAPD, mai inizializzate,
      `patches/b43/MESSAGES.md#0004`
- [x] le tre voci che il port tocca e il vendore no: una era un bug
      (`patches/b43/MESSAGES.md#0005`), una non era confrontabile (object memory), una era
      un artefatto dell'harness
- [ ] attribuire i 28 registri PHY ancora scoperti (0x9a-0x9d, 0x129-0x12b,
      0x1df, 0x1e1 e altri) e i quattro radio, che sono i `TXRXCOUPLE_2G` del
      setup della cal PAPD
