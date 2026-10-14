# 30 — RX sensitivity

Board: —      Date: —      Tree commit: —      Patches: —
Instrument and setup (attenuator, cable, chamber, distance): —

## PER vs input level

| rate | chain | -95 dBm | -90 | -85 | -80 | -70 | -60 |
|---|---|---|---|---|---|---|---|
| 1M CCK | 0 | — | — | — | — | — | — |
| 6M OFDM | 0 | — | — | — | — | — | — |
| 54M OFDM | 0 | — | — | — | — | — | — |

Repeat for chain 1 and, from M2, per MCS.

## Symmetry between chains

| known signal | RSSI chain 0 | RSSI chain 1 | delta |
|---|---|---|---|
| — | — | — | — |

## Acceptance criteria

- [ ] delta between chains within a few dB on a known signal
- [ ] no dead chain
- [ ] measurement repeated before and after the rev7 gain control fix, with
      both values reported (it is the M0/M1 gate)
