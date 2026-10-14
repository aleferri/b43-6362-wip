# patches/b43 — how to split the thirty-six

This is a **plan for when it ships**, not something to do now: the series stays
unsplit in `b43/` until the SPROM has a road upstream, and why is in `SPLIT.md`.

Thirty-six patches in one thread do not get read. `MESSAGES.md` keeps them in
order of discovery, which is the order they were found in and not the order
that makes sense to whoever reviews them. This is the split by area: **eight
series**, each about one thing, each sendable on its own.

The criterion is who has to review it. A series of tables only is checked
against the blob and the SPROM; a calibration one wants someone who knows what
that calibration does. Mixing them makes the same person do both.

## A — radio 2057 rev 8 data (5)

`0013` `0002` `0005` `0011` `0003`

Tables and register values, no algorithm. Reviewed against the OEM blob and the
SPROM, with `reverse-tools/blob_tables.py`, and needs no knowledge of the
calibrations. It is the series to send first: everything else depends on it for
data and nothing depends on it for code.

## B — init workarounds and RX thresholds (6)

`0001` `0008` `0030` `0031` `0032` `0007`

What the init programs once and never touches again: RX gain control, carrier
sense thresholds, the RF sequence, the spur workaround that was a stub. All
inside `b43_nphy_workarounds_rev7plus()` and neighbours.

## C — sample play and transmit filters (6)

`0010` `0022` `0027` `0028` `0036` `0026`

The tone every calibration uses as its stimulus: generation of the sample
table, the DAC test mode, the filter band overrides and the rows of the digital
filters. `0010` is also one of the twelve in `patches/mainline/`, and here is
the part that depends on this hardware.

## D — TX power control and TSSI (5)

`0033` `0034` `0035` `0021` `0025`

The TSSI setup, the order between enabling and indices, the return of the power
index. `0034` is the only one of the series that goes against the reference: the
capture is the only voice for it.

## E — PAPD calibration (6)

`0004` `0009` `0012` `0015` `0020` `0029`

The power detector: tables, epsilon offset, the engine's round, the power
control bracket.

## F — RX I/Q calibration (3)

`0016` `0018` `0023`

Switching the PHY to the calibration, the gain sweep, measuring the tone and
computing the coefficients.

## G — the periodic calibration machine (4)

`0014` `0017` `0019` `0024`

The orchestration: who starts the calibration, full or partial, the input gain,
the tail. It calibrates nothing itself, it decides who calibrates.

## H — noise floor (1)

`0006`

On its own because it depends on nothing and nothing depends on it.

## The order, and why it is not arbitrary

    A  →  B  →  C  →  D  →  G  →  E  →  F        H whenever

A first because the tables serve everyone. C and D before the calibrations
because the tone and the power control are what the calibrations use. G before
E and F because it is what calls them.

## The points of conflict, measured

Six functions are touched by more than one series. They are not logical
dependencies — every patch stands on its own — but they are the places where
two series contend for the same context lines, so they have to be applied in
the order above or regenerated:

| function | series |
|---|---|
| `b43_nphy_txpwr_index` | C D E F |
| `b43_nphy_tx_power_fix` | C E F |
| `b43_phy_initn` | E F G |
| `b43_nphy_op_prepare_structs` | D E |
| `b43_nphy_iq_cal_gain_params` | F G |
| `b43_nphy_restore_cal` | F G |

`b43_nphy_txpwr_index` is the worst point, four series on one function. If one of
the four goes into a long review, the other three no longer apply without
regenerating. It is worth considering sending `0021` alone before everything
else, so the conflict is resolved once.

## What is not verified, and why

That the eight series apply one after the other as eight separate files. This
split is on **subjects**, not on cut hunks, and trying to cut it does not hold:
of the 40 hunks of `phy_n.c` in the series only **9** can be attributed to a
single series, 24 are in functions no message names and 7 in contended
functions. And there is a hole in the split itself — the series has hunks in the
TX I/Q LO calibration (`tx_cal_radio_setup_rev7`, `update_tx_cal_ladder`,
`cal_tx_iq_lo`, `tx_cal_phy_cleanup`) and none of the eight series claims it.

The numbers and the way forward are in `SPLIT.md`. In short: where the
per-patch commit exists the split is a command; for the others there are 37
judgements no automatic check can validate, and sending them as a single series
split by area is a legitimate alternative.
