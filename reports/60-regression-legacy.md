# 60 — Regressione legacy 2.4 GHz

Da compilare **prima di ogni invio upstream**, con e senza la serie applicata.

Board: —      Data: —      Commit tree: —      Serie: —

| canale | assoc | throughput TCP prima | dopo | PER prima | dopo |
|---|---|---|---|---|---|
| 1 | — | — | — | — | — |
| 6 | — | — | — | — | — |
| 11 | — | — | — | — | — |
| 13 | — | — | — | — | — |

## Altri device toccati dalla serie

Le patch su `b43_radio_2057_setup` e sul gain control rev7 toccano anche radio
rev 5 e 7 (43217/43227) e tutti i N-PHY rev 7+. Se non hai quell'hardware, va
scritto qui esplicitamente che non è stato testato: è un'informazione che serve
a chi rivede.

| device | testato | esito |
|---|---|---|
| BCM6362 integrato | — | — |
| altri N-PHY rev 7+ | no | — |
