# 50 — HT20 2x2 throughput

Board: —      Date: —      Tree commit: —      Patches: —
Peer (AP or STA, chipset, firmware): —
RF setup (distance, attenuation, environment): —

| MCS | streams | UDP throughput | TCP throughput | retry % | notes |
|---|---|---|---|---|---|
| 0 | 1 | — | — | — | — |
| 7 | 1 | — | — | — | — |
| 8 | 2 | — | — | — | — |
| 15 | 2 | — | — | — | — |

## Acceptance criteria

- [ ] MCS 8-15 negotiated and used (not just announced)
- [ ] retries below the declared threshold at the low rates
- [ ] no stuck rate: the ladder goes up and down with the attenuation
- [ ] aggregation declared unsupported, not half active
