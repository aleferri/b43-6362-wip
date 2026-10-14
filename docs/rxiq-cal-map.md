# The RX IQ calibration: map of the capture

Mainline b43 does not have this calibration: `b43_nphy_rev3_cal_rx_iq()` is
**`return -1;`** for every N-PHY rev 3+, and `b43_nphy_cal_rx_iq()` downgrades
`type` from 2 to 0 when `phy->rev >= 7` (see `gap-inventory.md` 4a bis). Behind
that stub there are **7510 ops** of the capture, a third of the init window: it
is the biggest unported piece of the driver. This is the map, made like the one
of the PAPD cal and for the same reason: before writing the code one needs to
know what shape it has. What has been ported since is in "What is ported" below.

Reference capture: `opinit-ch1-ch6-bw20.decoded`, first `up` on channel 1.

## The boundaries

The region sits between the end of `wlc_phy_a4` (#14092) and the start of the
second RSSI cal (#22247). It is not delimited by eye: the ops that close it are
those of **length 2 on table 7 at `off=0x110`**, i.e. the two tx gain entries of
the two cores together, at **#14977**, **#14983** and **#21136**. Every other
write to that table in the region is `len=1`, one core at a time.

They were three and not two, and they are not save and restore: the right
reading comes from `wlc_phy_cal_rxiq_nphy_rev3` (`phy_n.c:27304`) and the
capture confirms it op for op.

| record | op | what it is |
|---|---|---|
| #14977 | `TBL.RD len=2` | `gain_save`, the tx gain of both cores before touching anything |
| #14983 | `TBL.WR len=2`, `0x4077` on both | `cal_gain`, i.e. the output of `wlc_phy_iqcal_gainparams_nphy` for the two cores |
| #21136 | `TBL.WR len=2` | the restore of `gain_save`, at the end of the function |

So **#14983 is not a save**: it is the write of the calibration gain, and the
save is the read at #14977 — which b43 can do, because
`b43_nphy_iq_cal_gain_params()` is already there.

The preamble adds up too, and it serves to place the shell: **#14966-14969** on
`0x01` is `BBConfig` read and written back with bit 15 cleared, **#14970-14976**
is `wlc_phy_stay_in_carriersearch_nphy(pi, true)`. So the phase does not start at
#14093 as the boundary in `REGIONS` says: it starts at **#14966**, and what lies
in between is the tail of the PAPD cal's `wlc_phy_txpwr_index_nphy` (`CLAUDE.md`,
"Come sta insieme la cal periodica").

## The brcmsmac functions

`wlc_phy_cal_rxiq_nphy()` dispatches to `wlc_phy_cal_rxiq_nphy_rev3()`
(`brcmsmac/phy/phy_n.c:27304`), which for each core calls, in order:

| function | line | what it does |
|---|---|---|
| `wlc_phy_rxcal_physetup_nphy` | 26701 | PHY setup for the core being calibrated |
| `wlc_phy_rxcal_radio_setup_nphy` | 26197 | radio setup, per core |
| `wlc_phy_rxcal_gainctrl_nphy` | 27058 | the gain sweep, which forwards to `_rev5` |
| `wlc_phy_rxcal_gainctrl_nphy_rev5` | 26855 | the body of the sweep |
| `wlc_phy_rxcal_radio_cleanup_nphy` | 26519 | radio restore |
| `wlc_phy_rxcal_phycleanup_nphy` | 26828 | PHY restore |

## The unit that repeats

The sweep is made of iterations of this shape, readable in full in the capture
because they are all table ops:

    TBL.RD  id=0x07 off=0x110|0x111 len=1   the core's current tx gain
    TBL.RD  id=0x0f off=0x57 / 0x50 / 0x55  IQLOCAL coefficients
    TBL.WR  id=0x1a off=0x40 len=84         84 zeros, core 0
    TBL.WR  id=0x1b off=0x40 len=84         84 zeros, core 1
    TBL.RD  id=0x1a|0x1b off=0x??ca len=1   the tx gain at the chosen index
    TBL.WR  id=0x07 off=0x110|0x111 len=1   the chosen tx gain
    TBL.RD  + TBL.WR id=0x0f off=0x57       read-modify-write of the coefficients
    TBL.RD  + TBL.WR id=0x0f off=0x5f
    TBL.RD  id=0x1a off=0x14a, 0x1ca, 0x24a three cells at a stride of 0x80
    TBL.WR  id=0x1a off=0x40 len=84         84 zeros again
    TBL.WR  id=0x1b off=0x40 len=84

**The unit is a function, and it has a name**: `wlc_phy_txpwr_index_nphy`
(`phy_n.c:28295`) with **index 10**. The four reads are the four tables the
index selects, 128 cells apart from each other: the gain at `192+10 = 0xca`, the
IQ compensation at `320+10 = 0x14a`, the local oscillator one at
`448+10 = 0x1ca`, the RF power offset at `576+10 = 0x24a`. The same function with
**index 30** is the tail of the PAPD cal, and gives `0xde`/`0x15e`/`0x1de`/`0x25e`.

And the `len=84` **are not a gain upload**, as this section used to say: they are
`wlc_phy_txpwrctrl_enable_nphy` turning the power control off by clearing 84
cells per core, twice per call — 84 `PHY.WR 0x73 val=0x0000` in a row, checked
at #15240-15280, followed by `AND 0x1e7 clr 0xe000` (`TXPCTL_CMD`) and by the two
`OR 0x100` on `0x8f`/`0xa5`. **b43 already has that code**, in
`b43_nphy_tx_power_ctrl()`, and it is why the 172-op block at #13921 paired even
before the RX IQ cal existed.

The two cores are told apart by the offset on table 7: **`0x110` is core 0,
`0x111` core 1**, and the capture alternates.

## The iterations, with the records

Ten writes of the tx gain and eight tones of 160 words:

| tx gain | core | tone that follows |
|---|---|---|
| #14305 | 0 | — |
| #14728 | 1 | — |
| #14983 | **both** (`len=2`) | — |
| #15293 | 0 | #15508 |
| #16104 | 0 | #16319 |
| #16915 | 0 | #17130, #17542 |
| #18373 | 1 | #18588 |
| #19184 | 1 | #19399 |
| #19995 | 1 | #20210, #20624 |
| #21136 | **both** (`len=2`) | — |

The first three iterations play no tone and sit in the region `phase_compare.py`
calls `cal RX IQ, ingresso` (#14093-15920); from the fourth on every iteration
has its tone, and it is the `cal RX IQ, sweep di gain` (#15921-22246). The tone
is the same stimulus as the PAPD cal: table 17, 160 words.

## What is ported, and what is not

`patches/b43/MESSAGES.md#0018`: the shell of `wlc_phy_cal_rxiq_nphy_rev3`,
`b43_nphy_txpwr_index()` and the sweep. `up-ch1` from 5791 to **11552 ops of
22951**, three iterations per core like the capture, each as a run of 85, 103,
85 and 420 paired ops; `0019` (pre-calibration gain), `0020` (power index put
back after the PAPD cal) and `0021` (index handed back after reading the gains)
take it to **13625**. `0022`+`0023` close with the **measurement** — tone at the
requested cal type and `b43_nphy_calc_rx_iq_comp()` — and reach **14351, 63%**:
the capture's two measuring tones, #17542 and #20624, come out as contiguous runs
of **336 and 334 ops**. The function returns 0 and `b43_nphy_save_cal()` runs for
the first time.

Two things the port does not do, declared:

- the 5 GHz branch of the sweep, because four of its six steps ask for a fixed tx
  gain built with a value b43 does not keep (the line that would save it is
  inside an `#if 0`). The caller is restricted to 2 GHz for this reason.
- the negative-index branch of `txpwr_index`, which replays state nobody reads
  in b43.

## What it means for the port

It is not ported piecemeal, for the same reason as `a2`/`a3`: **the decisions
depend on what it measures**. The ops are almost all writes, but which values
are written into table 26/27 and into the IQLOCAL coefficients is decided by the
gain the sweep finds, which in turn depends on the reads. A port that writes
the sequence without the computation produces the right ops with the wrong
values, which is the worst way of looking right.

What this map makes possible is the order of work: per-core `physetup` and
`radio_setup` are pure writes and verifiable in full — the same category as
point 1 of `papd-cal-map.md` — while the sweep wants the read plans in order,
and the plans now have the position (`test/unit/README.md`, positional plans).

## This one too is in the cold capture, and contiguous

Checked: in the contiguous part of `full-init-ch1-bw20.decoded` the whole phase
is there, with the same delimiter found on `opinit-*` — the two `len=2` writes on
table 7 with the tx gain entries of both cores, at **#25161** and **#31364** — and
in between **eight tones** (#25686, #26497, #27308, #27722, #28774, #29579,
#30390, #30804) and 34 gain uploads on 26/27 at `off=0x40 len=84`. Same shape and
same tone count as the region in `opinit-*`.

So **both cals are written and checked offline**: the reads with their values
are there, the part is contiguous so the positional comparison is legitimate,
and no new capture is needed. For the plans and the tolerance see the
corresponding section of `papd-cal-map.md`.

## Why a `pending` window cannot be used

Tried, and it does not work: the unported phases of the PAPD cal have a
`pending` window in `phase_compare.py` because their anchor is an op the port
**does not emit at all**, and not finding it is the expected state. For the RX
IQ cal there is no such op among the structural ones:

| candidate anchor | why it does not work |
|---|---|
| `TBL.WR id=0x7 off=0x110` (tx gain) | the port does 74 of them on table 7, `len=1` and `len=2` included: they come from the TX IQ/LO cal and from the power index |
| ops on IQLOCAL (`id=0xf`) | 124 port ops, from the TX IQ/LO cal |
| the three cells at stride 0x80 on 26 (`off=0x15e`, `0x1de`, `0x25e`) | `0x25e` shows up at #1222 too, outside the phase, and the port emits one; the triple `0x14a`/`0x1ca`/`0x24a` is also at #7455-7467, in the TX IQ/LO cal |

Every class of op this phase uses is also used by a phase the port implements.
With such an anchor the window does not say `assente`: it latches onto the wrong
place and reports an invented divergence — measured, 5/215 and 172/5596, two
false "to look at". It is trap 6 the other way round, and the limit is the
tool's: the anchor is **one** op, and this phase would need a sequence. Do not
try again without changing that first.

Consequence beyond the ops: the stub returns **-1**, and in `b43_phy_initn` the
`save_cal` sits behind `if (b43_nphy_cal_rx_iq(...) == 0)`, so as long as the stub
is there **no calibration is ever saved**, neither from the `perical != 2` branch
nor from the sequence of `0014`.
