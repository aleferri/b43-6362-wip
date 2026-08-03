# 30 — Sensibilità RX

Board: —      Data: —      Commit tree: —      Patch: —
Strumento e setup (attenuatore, cavo, camera, distanza): —

## PER vs livello di ingresso

| rate | catena | -95 dBm | -90 | -85 | -80 | -70 | -60 |
|---|---|---|---|---|---|---|---|
| 1M CCK | 0 | — | — | — | — | — | — |
| 6M OFDM | 0 | — | — | — | — | — | — |
| 54M OFDM | 0 | — | — | — | — | — | — |

Ripetere per catena 1 e, da M2, per MCS.

## Simmetria fra catene

| segnale noto | RSSI catena 0 | RSSI catena 1 | delta |
|---|---|---|---|
| — | — | — | — |

## Criterio di accettazione

- [ ] delta fra catene entro pochi dB su segnale noto
- [ ] nessuna catena morta
- [ ] misura ripetuta prima e dopo il fix del gain control rev7, con entrambi i
      valori riportati (è il gate di M0/M1)
