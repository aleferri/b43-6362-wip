# 50 — Throughput HT20 2x2

Board: —      Data: —      Commit tree: —      Patch: —
Controparte (AP o STA, chipset, firmware): —
Setup RF (distanza, attenuazione, ambiente): —

| MCS | stream | throughput UDP | throughput TCP | retry % | note |
|---|---|---|---|---|---|
| 0 | 1 | — | — | — | — |
| 7 | 1 | — | — | — | — |
| 8 | 2 | — | — | — | — |
| 15 | 2 | — | — | — | — |

## Criterio di accettazione

- [ ] MCS 8-15 negoziati e usati (non solo annunciati)
- [ ] retry sotto la soglia dichiarata ai rate bassi
- [ ] nessun rate stuck: la scala sale e scende con l'attenuazione
- [ ] aggregazione dichiarata non supportata, non mezza-attiva
