# 60 — Legacy 2.4 GHz regression

To be filled in **before every upstream submission**, with and without the
series applied.

Board: —      Date: —      Tree commit: —      Series: —

| channel | assoc | TCP throughput before | after | PER before | after |
|---|---|---|---|---|---|
| 1 | — | — | — | — | — |
| 6 | — | — | — | — | — |
| 11 | — | — | — | — | — |
| 13 | — | — | — | — | — |

## Other devices touched by the series

The patches on `b43_radio_2057_setup` and on the rev7 gain control also touch
radio revs 5 and 7 (43217/43227) and every N-PHY rev 7+. Without that
hardware, write here explicitly that it was not tested: reviewers need to know.

| device | tested | result |
|---|---|---|
| integrated BCM6362 | — | — |
| other N-PHY rev 7+ | no | — |
