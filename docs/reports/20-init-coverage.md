# 20 — PHY init coverage

Comparison between the raw vendor capture and the port's harness, per sequence.

Board: D-Link DSL-3580L      Flow: two `wl down`/`wl up` + 31 channel changes
Channels: operating 1 and 6, excursions to 5 / 2 / 10, all bw20
Tree commit: 848acc8ffe1b
Vendor capture: `router-data/dsl3580l/` (70796 records, 0 drops, 0 gaps)
Blob: `wl 6.30.102.7.cpe4.12L07.0`

The harness exists (`test/unit/`): it builds the N-PHY sources in userspace and
emits a trace in the same format. The rows with the "port ops" column filled
are real comparisons; the others are still reading the code by hand.

| function | vendor ops | port ops | match | notes |
|---|---|---|---|---|
| `b43_radio_2057_chantab_upload` (2g) | 18 `RAD.WR` per channel change | **18** | **values and order identical** | trace: 31/31 changes on 5 channels; harness: ch6 |
| chantab, 5 GHz fields | 10 `RAD.WR` to 0 | **0** | **missing in the port**, confirmed by the harness | open entry, `docs/trace-init-2g.md` |
| `b43_radio_2057_setup`, loopfilter | no extra write | — | ok | the values come from the chantab |
| `b43_nphy_gain_ctl_workarounds_rev7`, mainline | 21 ops | **0** | empty stub | writes nothing |
| the same, with `patches/b43/MESSAGES.md#0001` | 21 ops | **21** | **positional match, payloads included** | 8 table ops with identical values |
| AFE workaround (tbl 8) | 4 `TBL.WR` | — | to be checked | table 8 = AFECTRL, another workaround |
| `si_pmu_spuravoid` | 0 records | — | — | the vendor does not call it on this SoC |

Whole capture: 70796 ops over 39.8 s, two complete init sequences.

## Positional comparison, per window

`test/unit/phase_compare.py`, which is `b43-ac-wip`'s method: an op-by-op diff
inside an aligned window, on the capture passed through `merge_retvals.py`.

There are 14 windows; here the seven of the init, with the series
`0001..0013` applied. The full list, `static-tables` and the two phases of the
PAPD cal included, is in `test/unit/README.md`.

| window | ops | longest run | result |
|---|---|---|---|
| gain-control | 87 | 87/87 | **ok** |
| papd-comp | 16 | 16/16 | **ok** |
| papd-tables | 774 | 260/774 | 256 missing, 256 extra: same cells and same values, 64 single writes against one bulk |
| ipa-bias | 3 | 3/3 | **ok** |
| chanswitch-ch6 | 39 | 33/39 | **no missing op** since `0011`; the tail is three MMIOs out of step |
| tssi-setup | 19 | 5/19 | 4 missing, 15 extra |
| rssi-cal | 16 | 1/16 | the nine values match after the mainline patch on the RSSI cal; the port writes every coefficient twice and the window is positional (see `test/unit/README.md`) |

Longest global run on the first init, without choosing a phase: **1543
consecutive ops** with the `init` flow, and 4434 ops in common out of 22951 in
466 blocks. With the `full` flow it is 5398 out of 22951 in 677 blocks.

The four patch windows pass op for op, values included. That is the guarantee
set coverage does not give.

## Set coverage

Coverage measured with `test/unit/coverage.py` against the first init
(132-26100). On clean mainline the `full` flow does 175/218 PHY registers and
878/1987 cells.

Cells are counted by expanding the table ops (an op of length N covers N
cells): the percentages differ from the earlier ones because the measurement
changed, not the port.

`full` flow, against the first init:

| | mainline | +`0001`..`0003` | +`0004` | +`0005` | whole series |
|---|---|---|---|---|---|
| PHY registers | 175/218 (80%) | 186/218 (85%) | 186/218 (85%) | 186/218 (85%) | **190/218 (87%)** |
| radio registers | 39/54 (72%) | 39/54 (72%) | 39/54 (72%) | 40/54 (74%) | **50/54 (93%)** |
| table cells | 878/1987 (44%) | 1190/1987 (60%) | **1446/1987 (73%)** | 1446/1987 (73%) | 1446/1987 (73%) |
| ops emitted | 14490 | 15597 | 16117 | 16117 | 16131 |

The ten radio registers of the last column are the 5 GHz fields of `0011`, and
the four PHY ones the CRS thresholds of `0008`. `0010` moves none of these
figures: measured by applying `0001..0009` and then `0010`, the four rows stay
identical — that patch changes what ends up in the cells of table 17, not which
cells are touched.

With the series and the `init` flow, the one that mimics the vendor, **the
port no longer touches anything the vendor does not touch**. In the `full` flow
four IQLOCAL cells remain, which come from the harness's forced calibration and
not from the driver.

The two jumps are `0003` (PAPD compensation, 256 cells) and `0004` (epsilon and
scalar tables, 256 cells), and in both cases every value matches the capture.

The read plans generated from the capture (149 addresses, 2089 paired reads)
change none of these figures: in the `full` flow 70 plans out of 149 are
consumed, but the coverage is identical with and without them. The missing
phases are not missing because of a wrong value read; they are missing because
of early returns and revision gates in the driver.

Of the vendor's 677 SHM offsets the port writes two, and they are not
comparable (different encoding, see `test/unit/README.md`); the other 675 are
written by the b43 core, which the harness does not build. Of the 541 cells
still missing in `full` with the series, 512 are tables 26 and 27 (TX power
control), which the driver **cannot** write as long as
`b43_nphy_tx_pwr_ctl_init()` returns at once for `phy->rev >= 7`; the other 29
are in tables 8, 9, 15 and 7. Tables 31 and 33 are no longer missing: `0004`
initialises them.

## Acceptance criteria

- [x] no `OP_DROP` in the reference capture
- [x] no sequence discontinuity
- [ ] gaps between functions explained one by one (in progress: gain control
      done, AFE and the rest of the init not)
- [x] port harness in place and comparable with `test/unit/compare.py`
- [x] read plans from the capture's `RETVAL`s — done, and measured that they do
      not move the coverage: the residue is structural
- [x] tables 26 and 27: they were the early return of the PAPD path,
      `patches/b43/MESSAGES.md#0003`
- [x] tables 31, 32, 33, 34: PAPD epsilon and scalar, never initialised,
      `patches/b43/MESSAGES.md#0004`
- [x] the three entries the port touches and the vendor does not: one was a bug
      (`patches/b43/MESSAGES.md#0005`), one was not comparable (object memory),
      one was a harness artefact
- [ ] attribute the 28 PHY registers still uncovered (0x9a-0x9d, 0x129-0x12b,
      0x1df, 0x1e1 and others) and the four radio ones, which are the
      `TXRXCOUPLE_2G` of the PAPD cal setup
