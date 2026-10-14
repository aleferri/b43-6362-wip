# test/unit/ — userspace verification harness

Builds b43's N-PHY sources **without modifying them** — the files of `../../b43/`
where the port changes them, the pinned tree's for the rest — runs them in
userspace with a shim that intercepts every hardware access, and emits a trace
in the decoded `wl-diag` format. It compares op by op what the driver does with
what the proprietary driver does in the capture under `router-data/`.

## Use

```sh
make KDIR=~/src/pin              # builds; KDIR is the clean pinned tree
./phase_compare.py --vendor ../../router-data/dsl3580l/opinit-ch1-ch6-bw20.decoded
./nphy_trace init dsl3580l       # init flow, trace on stdout
./nphy_trace initpor dsl3580l    # the cold init only (do_full_init)
./nphy_trace chanset dsl3580l 6  # init, then a change to channel 6
./nphy_trace rfkill dsl3580l
make compare FLOW=init REF=../../router-data/dsl3580l/opinit-ch1-ch6-bw20.decoded
```

To try a change: edit the file in `../../b43/` and run `make` again. The copies
in `build/src/` have their source as a prerequisite, so they update themselves
and no `make clean` is needed. The prerequisite is per file on purpose: with a
single stamp the copy silently stays old, and one measures the wrong code
believing one measures the change. A file present in `../../b43/` wins over the
tree's.

## How it holds together

- The kernel `.c` files do `#include "b43.h"`, which with the quotes resolves
  in their directory and would pull in spinlocks, bcma, ssb, ieee80211. So the
  Makefile **copies** them into `build/src/` together with only the headers we
  want real (`phy_n.h`, `phy_common.h`, `ppr.h`, `tables_nphy.h`,
  `radio_205{5,6,7}.h`), and `b43.h`/`main.h` come from `stubs/`. Copy, never
  modify.
- Built: `phy_n.c`, `radio_2057.c`, `tables_nphy.c`, `ppr.c` and
  `lib/math/cordic.c` — the latter real, because the cordic values end up in
  the registers and a stub would falsify them.
- `wrap.c` implements the accessors (PHY, radio, MMIO, SHM, MAC) emitting one
  line per op, with a memory mirror for the writes. **And a mirror of the
  tables**, `tbl_mirror`, keyed on `(id, offset)`: without it, a table read goes
  through data port `0x73` and gets the last cell written anywhere instead of
  the one requested.
  `tbl_port_get()` serves the mirror **at the data port**, i.e. inside
  `b43_phy_read` for `0x73` and `0x74`, using `(id << 10) | off` from the last
  write to `0x72` — not only as the return value of `b43_ntab_read`, or the
  driver reads the right cell and the trace shows the register's mirror. It
  serves the cell **always**, even if nobody wrote it — `tbl_mirror` starts at
  zero and zero is the right answer, because those two ports are not registers
  and their mirror means nothing — and on reads it **advances the address**
  like the hardware: the read of `0x73` latches the whole cell and increments,
  the read of `0x74` returns the latched high word. The two ports are visited
  in opposite order in the two directions (`0x73` then `0x74` reading, `0x74`
  then `0x73` writing), and without the latch the increment on the low word
  would push the read of the high word onto the next cell. It shows on the
  low-pass filter band the PAPD cal reads back from `7/0x154`. The `b43_ntab_*`
  on the other hand are in `tables_nphy.c`, which we build, so they are
  intercepted at the linker with `--wrap` and then the `__real_` is called: the
  trace gets the `TBL.WR` label and the `PHY.WR`s on 0x72/0x73/0x74 that follow
  from it, as in the capture.
- `main.c` sets up a fake `struct b43_wldev` and calls an entry of
  `b43_phyops_n`. The board values are decoded from the device's SROM.
- `compare.py` normalises the two sides (no timestamp, record number, cpu
  column; `PHY.OR`/`PHY.AND` unified into `PHY.MOD`) and diffs.
- `lcsmatch.py` pairs the two sequences **optimally**, and it is not an
  ornament: `difflib` looks for the longest contiguous block, not the longest
  common subsequence, and on `up-ch1` it leaves 1686 pairings on the table
  because on the RX IQ cal, which repeats almost the same sequence seven times,
  it latches onto the wrong iteration. `python3 lcsmatch.py` runs its tests.

## Warnings

Two sets of flags, because the two sides have different responsibilities.

**Our files** (`wrap.c`, `main.c`): `-Wall -Wextra -Werror`. The only exception
is `-Wno-unused-parameter`, because the driver decides the accessors'
signatures.

**The kernel sources**: warnings on but not fatal, because a host compiler
builds them with flags other than the ones they were written for, and fixing
them is not this harness's job. Three classes stay **fatal** though, because
they do not speak about the kernel, they speak about our stubs:

    -Werror=implicit-function-declaration
    -Werror=implicit-int
    -Werror=incompatible-pointer-types

If one of these fires, the harness is running on a wrong model of the
environment and the trace it produces is worth nothing. It is not theory: on
the first round, with warnings off, three functions without a prototype had
gone through — `b43_current_band`, `cfg80211_get_chandef_type`,
`b43_wireless_core_phy_pll_reset` — which the caller saw returning `int`. The
first one returns an enum, and on another ABI that trace would have been silent
garbage.

`make warncheck` rebuilds from scratch and compares the set of warnings of the
kernel sources with `expected-warnings.txt`, normalising the line numbers away
(they move at every tree update). Today the expected list has one entry:
`-Wswitch` on `B43_BUS_SSB`, because `CONFIG_B43_SSB` is off by choice — that
core is on bcma. If the set changes, someone touched the sources or the stubs.

`CONFIG_B43_BCMA` on the other hand is **on**, and `-Wswitch` pointed it out:
without it, the bus-specific branches disappeared and with them the GPIO and
ChipCommon ops, which are in the vendor capture. In this board's `init` flow
they are not reached anyway, but compiled out they could never have shown up.

## Stubs: generated where possible

- `stubs/sprom.h` — `struct ssb_sprom` **copied verbatim** from the kernel: the
  field names have to match, and rewriting them by hand is the best way to
  introduce a silent difference.
- `stubs/b43_defs.h` — 488 defines and 7 enums extracted from `b43.h`. The
  comments are removed on purpose: the first version copied them, and
  `B43_BFH_FEM_BT` has a `/*` that continues on the next line, so the truncated
  comment ate the defines that followed.
- `stubs/bcma_ids.h` — the bcma/ssb defines the sources quote.
- `stubs/b43.h` is written by hand but reduced to the fields in use. The
  compiler checks the reduction: if the driver touches a missing one, the build
  stops.

## The power offset seed

After the cold init, and always untraced, a `recalc_txpower` runs: it is what
fills `nphy->tx_power_offset[]`, and without it the adjusted power table comes
out as zeros for the whole traced init, where the vendor writes it with content
(#2000 and #2086). The capture is a hot init, and the vendor's driver has those
offsets from the boot before.

Before calling it `perical_pending` is turned off, or the recalc drags along
the deferred sequence of the periodic cal, which redoes the RSSI cal and
rewrites the cache: the second init would restore that one instead of the first
init's. It costs 479 ops on `up-ch1` and makes the `rssi-cal` window lose its
anchor.

## The RSSI cal seed

Of the four calibration chanspecs, `rssical_chanspec_2G` is **not** cleared
between the two inits. The reason is in the capture: it is a hot init, and the
vendor at the first RSSI step **restores** instead of calibrating — between #132
and #8000 it reads `0x219` only once, zero polls, and at #3712-#3731 it writes
the two radio registers and the twelve PHY ones in a row. Clearing the chanspec,
the port took the calibration road, 1052 ops the vendor does not have, which
were worth 841 ops on the sum of the runs.

The other three are cleared, because the capture contains the TX I/Q LO and RX
I/Q cals.

The cache values **are not seeded**: the first init, which does the
calibration, puts them there, and the two radio registers and eleven of the
twelve PHY ones come out identical to the capture. Copying them by hand from
the capture is worth one op on `up-ch1`, which does not pay for fourteen
constants in the bench. The only one that differs is `0x1ac`, the fine
narrowband offset of core 0 on the Q rail: 0 against 1.

And cold there is nothing to check against: `full-init-ch1-bw20` starts the
RSSI cal at #32637, and at #32769 the 65285-record hole begins.

## The cold init and the hot one

The `init` flow does **two** inits: the first with `do_full_init` true and **not
traced**, the second with the flag cleared, and the second is the one compared.
The read plans are reloaded between the two, because they represent the second
one's reads and the first, which really runs, consumes them too.

The reason is in `docs/init-flow.md`: b43's `do_full_init` is brcmsmac's
`phy_init_por`, and the capture is not a cold init — the opening of table 10,
with which the static download starts, appears in neither of its two inits.
Always modelling the cold init put a prefix of 8320 ops that the reference does
not have: the flow went from 13223 to 4903 ops, and the RSSI cal coefficients
stopped being off by one LSB because the plans are no longer consumed by reads
only the cold init does.

`initpor` does only the cold init, to look at what it writes: it is not
compared with this capture, because there is no capture starting from power-on
reset.

## What it does NOT simulate

- Waits (`udelay`, `msleep`) are silent: there is not a single `DELAY` record in
  the vendor capture, so emitting them here would put every comparison out of
  step.
- `b43_radio_wait_value` declares the first read successful. Without a plan the
  mirror would never converge; in the trace it stays visible as a single
  `RAD.RD` instead of N.
- The radio 2055 and 2056 paths (N-PHY rev 1-6) **abort**: on rev 8 they are
  never called, and if the flow ends up there the device is set up wrong.
  Better to stop than to return zero silently.
- Reads without a plan return the mirror. Reproducing the branches that depend
  on the hardware state needs the read plans, built from the capture's
  `RETVAL`s (`b43_test_plan_{phy,radio,mmio}_reads`).

## What it has already found

With `b43/`, the change `patches/b43/MESSAGES.md#0001` makes the `init` flow
reproduce the capture's gain control block **op for op**: 0x1c and 0x32 with
bit 13, 0x289=0x46, 0x283=0x44, 0x280=0x44, the eight table ops (LNA1, LNA2, TIA
gain, gain bits per core) with identical payloads, the clip1 low gain codes
0x37/0x2ad=0x74 and 0x38/0x2ae=0x18, and 0x300/0x301=0x18. Without it those
registers are not written at all, which is the behaviour of the mainline stub.

The `chanset` flow reproduces the channel change: all 18 registers of the
2.4 GHz chantab with the same values and in the same order as the vendor,
tried on channel 6. And it makes the known hole visible: the ten 5 GHz
registers the vendor clears on every channel change (`LOGEN_MX5G_TUNE`,
`PGA_BOOST_TUNE_CORE0/1`, `TXMIX5G_*`, `PAD5G_*`, `LNA5G_*`) are not there on the
port's side, because b43 uses the `chantabent_rev7_2g` variant.

The two **sample table** windows found the biggest defect so far, and in
mainline, not in the port. Table 17 is the tone every calibration that plays
samples uses as its stimulus, and b43 did not produce one:
`b43_nphy_gen_load_samples()` kept the phase step in a `u16` after multiplying
it by 2^16, and for every frequency the driver asks for that product is an exact
multiple of 65536, so the step truncated to **zero** and the 160 samples came
out all equal; and `b43_nphy_load_samples()` masked with `0x3FF << 10` instead of
shifting the masked value, throwing away the in-phase component.
`patches/b43/MESSAGES.md#0010` closes both, and the 160 words become identical
to the capture. Without it `sampleplay-iqlo` does 2/322, with it 322/322: that is
the measure of what having the window is worth.

It also corrected the map of the cal: `papd-tone` looked for `0x186` with
`val=0x100`, a value that does not exist in the capture, because `0x186`-`0x194`
is not the tone but the coefficients of the TX digital filter (see
`docs/papd-cal-map.md`). A `pending` window with an impossible anchor never fails
and never says anything: it is the quietest way of being wrong.

The comparison also found a defect of the harness, not of the driver: `chanset`
called `switch_channel(dev, 6)` without updating `hw->conf.chandef`, which is
what mac80211 does before invoking the op, and the port programmed the old
channel's chantab. It showed in two registers, 0x16 and 0x2c — vcocal and mmd0,
exactly the ones that depend on the frequency.

## How far it gets

Two measures, and they serve different purposes. **The strong one is the
positional one**, and for too long only the other was used.

### phase_compare.py — positional comparison by window

It is `b43-ac-wip`'s method: `compare.py` normalises the two sides and diffs op
by op, with `--range` to limit the capture to a window and `--align-on` to latch
the harness output onto the first op of that window.

On the **whole** init it does not align, and that is not a limit of the method:
b43 and the proprietary driver order the phases differently, the port starts
from the tables and the vendor from the radio. Inside a phase it aligns very
well. `phase_compare.py` keeps the table of the recognised windows and compares
them all:

| window | ops | run | result |
|---|---|---|---|
| gain-control (`0008`+`0001`) | 87 | **87/87** | **ok** |
| papd-comp (`0003`) | 16 | **16/16** | **ok** |
| papd-tables (`0004`+`0012`+`0015`) | 774 | **774/774** | **ok** |
| ipa-bias (`0005`) | 3 | **3/3** | **ok** |
| static-tables (`initpor`) | 1424 | **1424/1424** | **ok** |
| static-tables-2 (`initpor`) | 806 | **806/806** | **ok** |
| sampleplay-tssi | 322 | **322/322** | **ok** |
| sampleplay-iqlo (`0010`) | 322 | **322/322** | **ok** |
| txdigi-filts | 60 | 45/60 | 15 missing, and they are **idempotent**: the vendor rewrites `0x195`-`0x1a3` with the same values |
| chanswitch-ch6 (`0011`) | 39 | 33/39 | **no missing op**; the tail is three out of step because of the MMIOs the vendor does not record |
| tssi-setup | 19 | 5/19 | 4 missing, 15 extra: the extra `0x17b` and the shift |
| rssi-cal | 16 | 11/16 | 5 missing, 3 extra: the nine coefficients match, the missing ones are `PHY.RD` on `0x73`, which the plans exclude on purpose |
| papd-digifilt (`0015`) | 15 | **15/15** | **ok** |

### The regions, which are two: `CONTIG`

`CONTIG` has **two** entries, the same macro operation in its two behaviours:
`up-ch1` (hot init, `opinit-*`, `init` flow) of **22943 ops, 16242 in contiguous
blocks, 71%**, and `up-ch1-freddo` (full init, `full-init-*`, `initpor` flow) of
**27563 ops, 17615, 64%**. Two and not one because the calibration type changes
the behaviour — `full_cal` against `soft`, and the holes of `a3`/`a2` go from 349
and 276 ops to 920 and 930 — so a cal phase checked against a single capture
validates one branch and says nothing about the other. The second covers more
than the first because it contains the download of the static tables.

With `patches/b43/MESSAGES.md#0017` the port chooses full or partial like the
reference instead of pinning `true`. On these two captures nothing changes —
both are of an interface coming up on an uncalibrated channel, so the test
comes out `full` in both — but it brought out a hole here: `main.c` cleared
`rssical_chanspec` and `iqcal_chanspec` between the two inits and not
`txiqlocal_chanspec`, and a second init that found it set took the partial
road, **−24 ops** on `up-ch1`. The three parts of the cal state are cleared
together. The blocks are searched over the whole output of the flow, and the
verdict is the structure of the blocks, not the percentage: a block that gets
shorter is a regression even if the total goes up.

Per-phase regions were tried and removed, four in as many sessions. The reason
is not aesthetic: **a phase taken alone says nothing about what lands on it
from before**. `chanswitch-ch6` said 33/39 and "no missing op"; the whole phase
is at 14%, because 200 ops out of 321 are a loop of 100+100 consecutive reads on
`0x1c9`/`0x1ca` the port does not do at all, and which nobody has attributed
yet (`CLAUDE.md`, "Cosa resta aperto", ACI scan). A window that passes while the
phase is at 14% is worse than no window.

The per-phase comparisons stay in the **windows** above, which are the detail;
`up-ch1` is the measure.

### The seeds

The state the window cannot have is seeded by
`reverse-tools/gen_seed.py --before 132` into `test/unit/seed_up.h`, applied by
`main.c` after the cold init and before the traced one. **Only what precedes the
window** is seeded: seeding the state produced inside it would make a register
the port programs wrong come back right by magic.

Two categories: what `op_init` and `rfkill` programmed, and what is **first
accessed by a read**, i.e. the chip's default — a criterion that is not "never
written", because the cal writes `0x17d` after reading it. The coupler's two
`atten` at `0xaa` come in this way.

**They are worth 32 ops out of 22951**: 5130 without, 5130 with only the
`op_init`+`rfkill` seeds, 5162 with the defaults. The rest of the gap is code
that is missing, not state. `B43_TEST_NOSEED=1` turns them off.

The **run** column is the longest consecutive sequence that matches, out of the
window's ops: it says how far the two sequences stay together, which tells more
than the count of mismatches. And next to every window that diverges there is
the diagnosis by **multiset** — how many vendor ops are missing and how many the
port does in excess, values included — because "36 positional differences"
explains nothing and "10 missing" does.

### The equivalences, computed and not declared

Two different renderings of the same thing are reduced, and the reduction is
derived from the data instead of being assumed:

- **`PHY.OR`/`PHY.AND` against `PHY.MOD`**: b43 uses `b43_phy_set`/`b43_phy_mask`,
  the vendor `phy_reg_mod`. They are all brought to the form of the mod, where
  `val` is the value of the field and `mask` the field modified.
- **the shadows of a read-modify-write**: the tracer hooks both `mod_radio_reg`
  and the `read_radio_reg`/`write_radio_reg` it calls, and the same RMW ends up
  in the trace as **three** ops. b43 records one. The two shadows are dropped,
  but only if they immediately follow a `MOD` on the same address — an isolated
  `RD` or `WR` is the real op and stays.

The second paid off at once: the channel change vcocal seemed to be missing (8
ops) and it was not, and the "missing" of that window went down to 10, which are
exactly the 5 GHz fields of entry 5b.

An "ok" here says something strong: in that phase the port does the same ops,
with the same values, in the same order. And it pays: widening the
`gain-control` window from #685 to #680 brought out four CRS threshold writes
nobody did (`patches/b43/MESSAGES.md#0008`), and one `PHY.RD` too many in the
guard of `0001`, which read `BANDCTL` from the hardware where b43 uses the
software state. And the two known divergences are located, not just counted —
the capture says the ten 5 GHz fields of entry 5b have to be written **in the
middle** of the sequence (0x43 after 0x41, 0x4a after 0x47), not at the end.

There is also `--global-run FROM TO`, which does not pick a phase by hand: it
takes the whole vendor window and the whole output of the flow, and reports the
longest runs. On the first init (`--global-run 132 26100`, `init` flow): **1543
consecutive ops** (from the loading of the TX gain table on), then 323, 266, 260,
and in total 4434 ops in common out of 22951 in 466 blocks. With the `full` flow
it is 5398 out of 22951, in 677 blocks. It is the most honest measure of where
the port stands: it covers pieces, and the pieces are contiguous.

`merge_retvals.py` is needed on the capture before comparing: without it, the
11049 `RETVAL` lines enter the diff as ops of their own and shift everything.
`phase_compare.py` does it by itself.

### coverage.py — set coverage

Measures which registers and which table cells the vendor writes and the port
does not. It is not positional: it serves to say *how much* is missing and to
find the reverse entries, not to say whether the order is right. Useful to get
one's bearings, weak as a guarantee.

Cells are counted **by expanding the table ops**: an op of length N covers N
cells. Counting it as one underestimates the port, which writes in bulk where
the vendor writes cell by cell.

Against the capture's first init (records 132-26100), `full` flow:

| | mainline | +`0001`..`0003` | +`0004` | +`0005` | whole series |
|---|---|---|---|---|---|
| PHY registers | 175/218 (80%) | 186/218 (85%) | 186/218 (85%) | 186/218 (85%) | **190/218 (87%)** |
| radio registers | 39/54 (72%) | 39/54 (72%) | 39/54 (72%) | 40/54 (74%) | **50/54 (93%)** |
| table cells | 878/1987 (44%) | 1190/1987 (60%) | 1446/1987 (73%) | 1446/1987 (73%) | 1446/1987 (73%) |
| ops emitted | 14490 | 15597 | 16117 | 16117 | 16131 |

The four extra PHY registers of the last column are the CRS thresholds of
`0008`. **`0010` moves nothing in this table**, and it is not a defect of the
patch: b43 already wrote the cells of table 17, only with the wrong content,
and this measure looks at which cells are touched and not at what ends up in
them. It is the clearest demonstration of the limit of set coverage: the
sample table defect could not come out of here, the positional comparison
found it.

The `initcal` flow turns the calibration on by setting `nphy->perical = 0`
**from the harness's main**, after `prepare_structs`. That knob has to stay
here: `b43_nphy_op_prepare_structs()` is common to every N-PHY, and changing
`perical` there would change the init of every device we cannot test. See
`docs/upstreaming.md`.

`full` is the longest run the public entry points allow: init with the
calibration on, then `recalc_txpower`, then a channel change. It is not a
sequence that happens like that on the device: it serves to measure coverage,
not to reproduce a real run.

The comparison is **on the cells and registers touched, not positional**: where
the vendor writes 64 cells one by one and the port does one bulk, the state of
the table is the same and the sequence of ops is not.

`phase_compare.py` makes the same exclusion since the per-region table got the
`non conf.` column: before, those ops were in the regions' denominator and
diluted them — 1180 out of 9692 in the init, 176 out of 2127 in the tail,
**zero** in all four calibration regions. The total in contiguous blocks does not
exclude them, on purpose.

Of the 677 SHM offsets the vendor touches the port writes two, and
`coverage.py` does not compare them: they are `o708`/`o70e`, with the different
encoding explained below. The other 675 are written by the b43 core, which we do
not build — only the PHY is here.

What is left out, and why:

- **tables 26 and 27** at offset 576, the PAPD compensation: it was the early
  return of `b43_nphy_tx_gain_table_upload()`, closed by
  `patches/b43/MESSAGES.md#0003`.
- **tables 31, 32, 33, 34**, i.e. PAPD epsilon and scalar: b43 turned the PAPD
  engine on without initialising the tables it reads. Closed by
  `patches/b43/MESSAGES.md#0004`.
- **the gain registers 0x9a-0x9d, 0x129-0x12b, 0x1df, 0x1e1** and the other 28
  still uncovered (`--details` lists them): to be attributed, not looked at yet.
  The four radio ones left are `0x17d`/`0x17e`/`0x19d`/`0x19e`, the
  `TXRXCOUPLE_2G` of the PAPD cal setup, which is not ported.

## Read plans, and what they do NOT explain

`readplans_init.h` is generated by `reverse-tools/gen_readplans.py`: it pairs
every read of the capture with its `RETVAL` and emits, per address, the sequence
of values the hardware returned. 149 plans, 2089 reads paired out of 2089. The
port's reads that have a plan get those values instead of the mirror;
`B43_TEST_NOPLANS=1` turns them off.

0x72, 0x73 and 0x74 stay out of the plans: they are the table access port, and
replaying the capture's values on them reproduces nothing — in the port those
reads serve to read a table, and the right value is what the table contains.
With them in, the plan of 0x73 was consumed 185 times and falsified every
`b43_ntab_read`.

**The plans are a queue per address, and do not know from which point of the
capture the values come.** The port consumes an address's plan in the order it
reads it, so it is enough for it to do one read fewer than the vendor before a
phase for all the values of that phase to arrive one out of step. It is not a
capacity problem: measured, **zero plans in overrun** both with `0014` and
without, all 149 have entries to spare. The consumption count changes (0x8f goes
from 1/28 to 23/28 with `0014`), the position does not.

That is where the RSSI cal comes from: the vendor computes `0x1b8 = 0x3f` and
eight `0x3e`, the port nine `0x3f`. The `rssi-cal` window gave 11/16 for a reason
other than the one written here: the second init took the **restore** road and
rewrote the cache computed by the first init, which had got the right values.
With `0014` the first init recomputes that cache and the window falls to 1/16 —
but even before it was not measuring a cal, it was measuring a copy. Now the
flow clears the cal chanspecs between the two inits, so the second redoes the
cals like the capture, and the window tells the truth: 1/16, one LSB apart.

## Positional plans: the mechanism is there, the win is not

The plan entries now carry the **record number** of the capture they come from
(`gen_readplans.py` emits it in a second array), and `plan_get()` serves the
first entry from the cursor on instead of the next one in the queue. When an
address has no entry from the cursor forward, the read falls on the mirror and
the counter says so: before, a zero came out in its place, which is the quietest
possible lie.

With `B43_TEST_TBLDBG=id:off` (hexadecimal, without `0x`) every read of that
cell comes out with the `backtrace()` of whoever asked for it. It serves when the
same read comes from several sites and one needs to know which is out of place:
the nine reads of the current gain (`7:110`) come from four different points,
and the position in the trace does not say which.

With `B43_TEST_PWRCTLDBG=1` every write of the adjusted power table (`26/0x40`,
84 cells) comes out with the `backtrace()` of whoever asked for it, offsets in
the binary included, which resolve with `addr2line -f -e nphy_trace`. It serves
because switching the power control always emits the same 176 ops (86 + 86 + 4)
from whichever of its nine callers it comes, so the position in the trace does
not say where it comes from. That is how the 75 displaced ops of the PAPD cal
became four brackets too many in the gain search of the RX IQ cal.

With `B43_TEST_PLANDBG=1` every hit and every miss comes out with the record
served and the cursor. It is what found the real defect, which was not the
position: **`gen_readplans.py` truncated every plan to 64 values** (`--max-len`,
default 64). The port reads `0x219` and `0x21a` 161 times each in the RSSI cal,
the vendor 152 times in the region of the second cal alone and 324 in the whole
capture: with 64 entries the plan ended at once and the other 97 reads per
address — **the 194 "out of position"**, all on these two registers — read the
mirror. The cal averaged half capture and half mirror.

Regenerated with `--max-len 512`, the two plans have 162 entries, the port
consumes 161, and the counters go to **zero out of position and zero skipped**.
Now the values the RSSI cal averages really come from the capture.

### But the cursor is one, and it is poisoned at the first hit

That "zero out of position" holds for `0x219` and `0x21a`, not for the run. The
cursor is **global and monotonic**, and the first `planhit` of the whole run is
this one:

    planhit PHY 0x007a rec 14999 cursore 0

The plan of `PHY 0x7a` has three entries, at records `{14999, 18079, 22291}`: the
vendor reads that register **only inside the RX IQ cal**, the port reads it in
the init. One read out of order, and from there on the cursor sits at 15000:
everything the vendor read before record 15000 becomes unreachable for the rest
of the run. It shows clearly on an address with a single entry at the start of
the init:

    planmiss RAD 0x016b cursore 26067 ultima 553

### The cursor is per address

The second of the two roads is done, and the first — **contiguous regions**,
`CONTIG` above — stays and pays as before. Every plan has its own cursor, and
`plan_pos` is only the common floor they start from, the entry of the region
under measurement.

The invariant that holds is **per address**: the reads the port does of an
address are a subsequence of those the vendor does of the same address. The
global one, on the interleaving between different addresses, does not hold, and
`PHY 0x7a` proves it. The price is the other way round: if the port skips a read
of an address, the following values **of that address** shift by one. It shifts
one at a time instead of all, and a shifted value breaks the run as a missing op
does, so the per-phase measure sees it.

Measured, `init` flow against `opinit-ch1-ch6-bw20`, report columns summed:

| | consumed | skipped | out of position |
|---|---|---|---|
| global cursor | 1496 | 923 | 8823 |
| per address | 1035 | **0** | **524** |

Counted instead as `planhit`/`planmiss` lines with `B43_TEST_PLANDBG=1`: from
**585 served and 18221 missed** to **2074 and 1058**.

**And the per-phase verdict moved by 13 ops**, from 5911 to 5924, with the
contiguous blocks from 16242 to 16392. This is the result, not the counters:
serving the port three and a half times the capture's values bought almost
nothing, so what remains open **is not the harness failing to answer reads**. It
is the port's sequence of ops really diverging.

And it was true at once: looking at the sequence instead of the values, the TX
I/Q LO cal yielded a mainline defect — the writes matched and 445 **reads** were
missing, all on `0xc0`, because the polling waited for the opposite of what it
should. See `CLAUDE.md`. But the per-address cursor is what makes that fix
measurable: without the values of `0xc0`'s plan served in order, the corrected
loop would have no way of running 455 times.

One phase lost: `cal-tx-iqlo` from 333 to 331, and it is not the exclusive
assignment — the region alone gives **746 of 1570 in 99 blocks** with the global
cursor and **741 in 97** per address. A real loss of 5 ops. The mechanism has not
been attributed: a value that used to fall on the mirror and matched by chance
now comes from the plan and does not match is the obvious hypothesis, but **it
is not verified**.

And with the values read right, the LSB that remained turned out to be **a
mainline defect**, not a limit of the harness: in `b43_nphy_rev3_rssi_cal()` the
negative branch of the rounding writes `-(abs(offset[j] + 4) / 8)`, with the
parenthesis of `abs()` in the wrong place, so the 4 ends up inside the negative
value instead of on its magnitude and every offset below -4 rounds towards zero.
brcmsmac takes the magnitude, adds `NPHY_RSSICAL_NPOLL / 2`, divides and negates
at the end, and the same file gets it right twice: in the coarse phase of this
function and in `b43_nphy_rev2_rssi_cal()`. With the parenthesis fixed, the nine
coefficients become `0x1b8 = 0x3f` plus eight `0x3e`, **identical to the
capture**: `patches/mainline/b43-fix-the-rounding-of-the-negative-rssi-cal-offsets.patch`.

The `rssi-cal` window stays at **1/16** anyway, and the multiset road was tried
and does not work: the vendor does 16 ops, the port ~140 (it writes every
coefficient twice, zero and then the value, and interleaves reads and RF
overrides). Widening `test_len` to 200 the eight `0x3e` pair up — **and that is
the proof the values are right** — but 37 port ops come in that the vendor does
not have in that window, and the verdict gets worse instead of telling the
truth: the two windows are not commensurable.

So this phase does not close with this tool. It wants a comparison on the
**final value** of the registers — after the phase, `0x1a4` holds what it holds in
the capture — which is a different assertion from comparing sequences of ops,
and does not exist today. Two vendor table reads the port does not do also stay
out, `TBL.RD id=0x7 off=0x110` (the save of the original tx gain, which `0014`
does not carry) and `TBL.RD id=0xf off=0x50`.

**And now the honest point: the plans do not move the coverage.** With and
without them, the `full` flow emits 14490 and 14488 ops, and the registers and
cells covered are identical. 72 addresses out of 149 consume their plan, so they
are used; simply, the missing phases are not missing because of a value read
wrong: read plans are not the explanation, although they look like it.

What is left out is **structural**: early returns and revision gates inside the
driver, not hardware state. The plans stay because they cost nothing, make the
reads faithful and will serve when the calibration loops really run, but they
are not the lever.

## The reverse entries, looked at

The port touching something the vendor does not touch is the strongest signal
the harness produces, because there is no way to explain it with "b43 does
less". There were three, and they ended in three different ways.

**`r05f` was a real bug**, in mainline: the rev 7/8 branch of the IPA
workarounds writes `IPA2G_GAIN_CORE0` where the vendor writes
`IPA2G_IMAIN_CORE0`, and programs the two cores with different values where the
vendor uses the same. `patches/b43/MESSAGES.md#0005` fixes it for rev 8, details
in `docs/gap-inventory.md`.

**`o708` and `o70e` were not comparable.** They are
`B43_SHM_SH_NPHY_TXPWR_INDX0/1`, and the problem is the unit:
`b43_shm_write16()` takes an offset in **bytes** into the SHARED region and
divides it by 4 internally, while the vendor's tracer records the argument of
`write_objmem16()`, which is a word address with a different space selector
(`0x10000` against `B43_SHM_SHARED` = 1). The harness intercepts at the API
level and the tracer at another: comparing those addresses only produces noise.
Now `coverage.py` counts object memory and does not compare it, and says so.

**`tbl15+0x60..0x63` is an artefact of mine.** It shows up only in the `full`
flow, which turns the calibration on with `perical = 0`: it is the IQLOCAL
table written by the cal, which the vendor does not do at init. In the `init`
flow, the one that mimics the vendor, the reverse list is **empty**.

### Windows on a different capture

A window can declare `capture='<file>'` and is compared against that instead of
the `--vendor` given on the command line. It serves for the phases one capture
does not contain: `static-tables` and `static-tables-2` exist only in a **cold**
init, and `opinit-*` is hot.
