# CLAUDE.md

What has to be known before touching anything. Short on purpose: the detail is
in `docs/INDEX.md`, here there is only what is needed not to repeat mistakes
already made.

**This file states the state, not how it was reached.** The numbers here are
the ones the tools give today; the intermediate steps are in the commit
messages and in `patches/b43/MESSAGES.md`. If a number here does not add up, the
mistake is here: redo the measurement and fix the line.

## The project

Bring to b43 the support for **BCM6362 / N-PHY rev 8 / radio 2057 rev 8**,
guided by an MMIO capture of the proprietary driver `wl 6.30.102.7`. Seven
patches already merged in mainline (`docs/upstream-status.md`), twelve
candidates in `patches/mainline/`, thirty-six in the series that lives in
`b43/`. **Nothing has ever run on hardware**: everything is verified by
reproducing the capture in a harness that builds the real `phy_n.c`.

## Setup, every time

```sh
sh scripts/fetch-upstream-state.sh ~/src/pin        # pinned tree, from the tarball
cd test/unit && make KDIR=~/src/pin && make KDIR=~/src/pin warncheck
./phase_compare.py --vendor ../../router-data/dsl3580l/opinit-ch1-ch6-bw20.decoded
```

The files the port changes live **whole** in `b43/` (and the bcma ones in
`bcma/`, at their kernel paths), on the tree `848acc8ffe1b` that
`patches/regen-base` declares. The harness takes those from `b43/` and the rest
(untouched headers, `cordic.c`) from `KDIR`, which therefore stays **clean**:
nothing is applied to it. The script without a second argument fetches exactly
that tree; with a ref (`master`) it fetches upstream, and on that the numbers
below have no reason to add up, and the `file:line` references certainly do not.

`b43/` also contains the twelve of `patches/mainline/`: they are part of the
measurement baseline, and without them the numbers below do not add up. For the
same reason `scripts/series-diff.sh ~/src/pin` prints the b43 series as a diff
**from the pinned tree with the mainline patches applied**: it does not contain
`0010` and `0022`, which were duplicates of two of the mainline patches.
`check_patch_gating.py` on that diff gives one verdict for the whole series; the
declarations on the ungated points are in `patches/b43/NOTES.md`.

The series is split again before sending anything, and the messages of the
thirty-six patches are in `patches/b43/MESSAGES.md`. The citations by number in
the documents and in `phase_compare.py` resolve against that file.

**How to split it is in `patches/b43/SERIES.md`**: eight series by area, not one
thread of thirty-six. The order of `MESSAGES.md` is the order of discovery and is
no use to reviewers. The six points where two series contend for the same
function are there too, measured, and the worst is `b43_nphy_txpwr_index` with
four.

**The rule that makes that split possible is one: one commit per patch, with its
`MESSAGES.md` entry in the same commit.** The per-patch boundary lives in the
history, not in a directory of files that drift — the twenty-six files that
existed until `394c9e2` are 718 lines behind the series, which is worse than not
having them. `scripts/patch-from-commit.sh` extracts the patch of a commit when
needed (a commit on `b43/`, or on the old `rollup.diff` for the history before),
and `patches/b43/SPLIT.md` has the numbers — and what the published history
actually holds, which is less than it says: `0027`-`0036` arrive together in
`a608a33`.

The dependency chain inside the series serves the **split**, not the build:
measured with `git apply` on the clean pinned tree, 0004 depends on **0002**
(context in `tables_nphy.c`), 0009 on 0004, 0012 on **0009**. 0003 is needed by
none of the three.

## Tools

| what | where |
|---|---|
| harness, flows `init initpor initcal full chanset rfkill txpower` | `test/unit/nphy_trace` |
| per-phase comparison, 18 windows | `test/unit/phase_compare.py` |
| global + per-region comparison | `test/unit/phase_compare.py --global-run FROM TO --flow F` |
| set coverage of cells | `test/unit/coverage.py` |
| history of a table cell | `reverse-tools/trace_tables.py --cell ID:OFF` |
| segmentation on a marker | `reverse-tools/segment_marker.py` |
| normalisation, `Op` with `.ep` | `test/unit/compare.py` |
| **seed**: the state `op_init` and `rfkill` leave | `reverse-tools/gen_seed.py` → `test/unit/seed_up.h` |
| SHM accesses, PHY clock, macfreq, MAC boundaries (new captures) | `wlc_bmac_*` hooks in `wl-diag/3-4/wl_diag.c` (not in `2-6-30/`) |
| dispatch holes, brcmsmac xref, patch gating | `reverse-tools/*.py` |
| the series as one diff, the bcma patches from `bcma/` | `scripts/series-diff.sh`, `scripts/regen-patches.sh` |

## State

Measured on `b43/` at the reorganisation, `phase_compare.py` with no options and
`--global-run 132 26100 --flow txpower --channel 1`; the harness's traces are
byte for byte those of `054601d`, so these are also the numbers of that commit.

`18 finestre: 0 da guardare, 5 divergenze note, 1 fasi non ancora portate`. No
window is open.

**The verdict is `phase_compare.py`'s per-phase table: 9069 ops of 18923, 48%.**
Not the total in contiguous blocks, which says 21529 of 23060 (93%) and **is not
a measure**: on `up-ch1` most blocks are under 16 ops. Adding up two-op fragments
and calling it coverage is counting the black economy in the GDP.

A block counts if it corresponds to a **phase**: a `phy_ops` entry where one
exists, or — a declared exception as long as the port does not expose them — a
macro operation delimited by a quoted marker. The per-phase number is **one**,
the longest contiguous run inside the phase, so no fragment moves it.

| phase | ops | run | blocks |
|---|---|---|---|
| `idle-tssi` | 661 | **660 100%** | `660` |
| `pwr-setup` | 432 | **432 100%** | `432` |
| `gain-table` | 1540 | **1540 100%** | `1540` |
| `coeff-setup` | 1037 | **1037 100%** | `1037` |
| `recalc-txpower` (**a real phy_ops**) | 716 | **605 84%** | `605` +1 small |
| `perical-ingresso` | 1403 | 575 41% | `575 409 401` +1 small |
| `cal-tx-iqlo` | 1570 | 443 28% | `443 349 267 2x110` +4 small |
| `cal-papd` | 2662 | 792 30% | `792 518 2x381 371` +7 small |
| `cal-rx-iq` | 5728 | 531 9% | `4x531 530 528 434` +4 small |
| `coeff-setup-2` | 1074 | **1062 99%** | `1062` +3 small |
| `cal-rssi-2` | 960 | **960 100%** | `960` |
| `coda-idle-tssi` | 1140 | 432 38% | `432 352 161 88` +1 small |

**The run is wrong in one direction, and that is why the blocks column is
there**: it takes the maximum, so a phase that repeats the same sequence N times
cannot exceed ~1/N by construction, however well it reproduces it. And that is
every cal. `cal-rx-iq` is the limit case: the run says **9%** and the shape says
**`4x531 530 528`**, i.e. the iterations of the sweep paired one by one; measured
on its own with the plans' floor at its entry (`--global-run 14951 21136`) it does
**5702 of 5728, 100%**, and the sweep sub-region (`15921 22246`) **5889 of 5917,
100%**. That phase is not a hole.

Careful: a region measured on its own is not another view of the same run, it is
a **different** run — `--global-run` repositions the plans' floor at its entry.
`cal-rx-iq` alone does 100% against the run's 9%; when this was first written,
`coeff-setup-2` alone did 331 (31%) against 1062 (99%) in the global run. Neither
is wrong and they are not comparable.

The total of the global run **is not looked at**: the assignment of blocks is
exclusive and greedy, so a long block elsewhere takes the ops away and the number
swings on changes that only improve. The number to look at is `up-ch1`.

Per region, `--global-run 132 26100 --flow txpower --channel 1`. The flow is the
one `up-ch1` declares and not `init`: with `init` the port stops at about 4600
ops, the init region does about 4400 and the five calibration regions do
**zero**, which is a measure of nothing (trap 11).

| region | records | ops | paired | not comp. | on comp. | moved | absent |
|---|---|---|---|---|---|---|---|
| init proper | #132-10961 | 9696 | 8420 87% | **1180** | **99%** | 38 | 62 |
| PAPD cal (`a4`) | #10962-14092 | 2662 | **2644 99%** | 0 | 99% | 4 | 14 |
| RX IQ cal, entry | #14093-15920 | 1705 | 1696 99% | 3 | **100%** | 2 | 7 |
| RX IQ cal, gain sweep | #15921-22246 | 5917 | **5888 100%** | 0 | **100%** | 3 | 26 |
| second RSSI cal | #22247-23771 | 960 | **960 100%** | 0 | **100%** | 0 | **0** |
| tail | #23772-26100 | 2128 | 1921 90% | **176** | 98% | 9 | 22 |
| **TOTAL** | | | | | | **56** | **131** |

**The two columns measure two different defects and both are needed.** `paired`
answers "in what order", and on a PHY's init the order is functional: the ops go
in the sequence the hardware expects, not in any one that touches the same cells.
`absent` answers "are they there", i.e. where code is missing. A **moved** op is
not harmless: it is an order defect, and it gets closed like the others.

For `paired` to be worth anything its count has to be **optimal**, and with
difflib it was not: see `lcsmatch.py`. The `absent` count does not crop the port,
which has no record numbers: it looks at the remainder, i.e. the port's ops no
block has paired, counted by string over the whole flow, and consumes them.

`not comp.` are families the port has no way to emit, because the harness builds
the PHY and not the core — `OBJ.*`, `MAC.MCTRL`/`MHF`, `TPL.RAMW`, `GPIO.*` — and
object memory has the non-comparable encoding of `o708`/`o70e` anyway. In the
four calibration regions they are **zero**: all 1356 are in the init and the
tail, where the core works. The total in contiguous blocks does not exclude them,
on purpose.

**The init proper is still the biggest residue, and how big is known now**: of
its unpaired ops, 38 the port does elsewhere and **62 it does not do at all**.
After it come the sweep with 26, the tail with 22 and the PAPD cal with 14; the
second RSSI cal is at **zero**.

The tool now also prints the **biggest unpaired stretches**, with how many of
their ops write: the largest starts at #5004, 20 comparable ops absent out of 577
in the stretch, and all 20 write. Its footer counts 122 absent ops that write and
176 that read over the whole window — 298, against the 131 of the per-region
table; the two counts are not reconciled here. Either way the biggest stretch is
not necessarily the most urgent: the `scrivono` column is the one to order the
work by.

## How the periodic cal holds together

`wlc_phy_cal_perical_nphy_run()` is called once per phase, and each one does the
same bracket: it reads the tx gain from `7/0x110`, saves `nphy_txpwrctrl` and
**turns it off**, runs its phase, and at the end restores — and it is that
restore that writes `adj_pwr_tbl`, 84 cells per chain. Rebuilt in
`b43_nphy_cal_perical_phyinit()`, with these boundaries, all from the capture:

- **the bracket closes once, at the end.** Audit of every boundary between the
  steps, with the test on the payload (84 zeros = disabling, content = enabling):
  between perical and TX I/Q LO no transition, between TX I/Q LO and PAPD a single
  disabling, between PAPD and RX IQ four disablings, between RX IQ and idle TSSI
  none. **There is not a single enabling between the phases**: the control stays
  off for the whole sequence.
- **the six TX phases are ONE step.** The capture emits the twelve commands in a
  row with a single gain read, and the vendor has one bracket for the whole TX
  block, not six.
- **RX IQ and RSSI are a single step.** Between the reread of the `save_cal`
  coefficients (#21169, `15/0x50 len 8`) and the one that opens `coef_setup`
  (#21187, len 7) there are eighteen ops and nothing else: in two steps, two
  84-cell reprogrammings would pass between them.
- **handing the index back sits between PAPD and RX IQ**, and is done with index
  `-1`: the capture has two calls to `txpwr_index` there, one per core, each with
  its save and reapply (#14101/#14305 core 0, #14524/#14728 core 1).
- **the deferred hand-back does not restore the compensations** (`restore_cals`
  false): in the capture there are no writes to `15/0x50`, `15/0x55` and
  `15/0x5d` between the write of the bbmult and the reprogramming of the power
  table, and the four brcmsmac sites that call with the saved index all pass
  `false`.
- **the bbmult goes back into TWO cells**, 87 and 95: the capture does the
  read-modify-write on `15/0x57` (#8096) and then the same on `15/0x5f` (#8103),
  as the branch that forces the index does. The reference touches only 87.
- **the per-chain index is read from the hardware at the entry**, from bits
  8..14 of `C1_TXPCTL_STAT` and `C2_TXPCTL_STAT`, not from `index_internal`, and
  **it is not one**: what the tail forces again is 10 on core 0 and 12 on core 1.
  Which of the five pairs of reads produces it, and why it is not the pair the
  reference uses, is in the dedicated section below.
- **the tail of the sequence forces those two indices again**, one call per core,
  before the single closing: the capture reads `26/0xca` at #25017 and `27/0xcc`
  at #25418, and between the two calls the power control stays off — the four
  payloads of 84 zeros at #24841, #25064, #25242, #25465 — with the only enabling
  after them, at #25641, which is the closing. It is worth **+762 contiguous
  ops**, the biggest gain of the series, with runs unchanged.
- **the hand-back test is on the state at the entry of the sequence**, not of the
  step: with the single closing at the end, the per-step state is false after the
  first opening.
- **`precal_txgain` twice is not a duplicate**: the capture has two, one in the
  deferred block and one at the INIT step.
- **the sequence runs after `recalc_txpower`**, not at the end of
  `b43_phy_initn()`: the vendor does init, recalc (#5726-6500), then the cal
  (#7034 on). The call point is the end of `b43_nphy_op_recalc_txpower()`, behind
  `nphy->perical_pending`, which is the only place between the two the harness
  goes through; in the reference the watchdog starts it, and there is none here.
  mac80211 calls `recalc_txpower` after the init **always**, so a flow that does
  not do it is the bench being unfaithful.

`nphy->cal_orig_pwr_idx[]` is set in **one place only**, inside
`if (nphy->perical != 2)`. This hardware has `perical == 2` — which is the reason
the state machine exists — so it does not go through there and that array stays
at zero: it has to be taken at the INIT step.

**The meaning of the precal is different from how it sounds**: the forced index
serves only to *read* some gains, not to stay programmed. The vendor forces it,
reads, and at once gives back radio gain, dac gain, bbmult and the
compensations; the cals run on the hardware as it was, with the gains read at
the forced index. **The index is 10, and it is not the one the reference would
choose**: brcmsmac keeps 10 for radio 2057 rev 3, 4 and 6 and 0 for everything
else, so rev 8 would end up on 0, but the capture reads `off=0xca`, i.e.
`192 + 10`. brcmsmac's grouping is older than this radio, exactly like the
rccal's (`gap-inventory.md` entry 5), and the capture decides.

The full/partial parameter is not a constant: `fullcal = (channel != channel of
the last TX IQ/LO cal)`, the same test `b43_nphy_restore_cal()` already does
before reusing the coefficients. On this capture it **moves no op**, because both
inits are of an interface coming up on an uncalibrated channel: it changes from
the second time on, which no capture covers. The type of the RX IQ cal stays
**2** and it is not an oversight: brcmsmac asks for 2 at the first cal after an
association and 0 afterwards, b43 tracks nothing equivalent, and between the two
constants 2 is the conservative one because 0 skips almost everything.

Careful with what is **not** the discriminant, because it is the road that looks
right: the `full_cal` of `wlc_phy_a4(pi, bool full_cal)` is declared and never
used in the body, and the three callers all pass `true`; and
`pi->nphy_papd_cal_type`, which chooses between `CAL_FULL` and `CAL_SOFT` for the
epsilon, is never written anywhere in `phy_n.c`. Putting them in b43 would be
transcribing dead weight.

The three parts of the cal state — `rssical_chanspec`, `iqcal_chanspec`,
`txiqlocal_chanspec` — have to be cleared **together** between the harness's two
inits, not two out of three, or the second init takes the partial road.

## The narrowband RSSI cal

The VCM search is pure arithmetic, and mainline gets two pieces of it wrong. The
distance to minimise is `I² + Q²` and the second term was `Q * I`, which is not a
distance and is negative whenever the rails have opposite signs. And the rev 7+
branch that programs the winner passed `vcm`, which at the loop exit is 8 on a
three-bit field: it wrote a bit out of the field and threw the search away. The
two are in `patches/mainline/`, can be proved against brcmsmac without hardware
and hold for rev 3 too.

With the two, the second RSSI cal measured on its own does **956 of 960, 100%**,
in 3 blocks, with a single run of 940. It was 623 in 22 blocks. In the per-phase
table, `cal-rssi-2` is at **960 of 960**.

The same region found the defect in the index field: the capture reads
`0x1ed`/`0x1ee` at #7034 and #7036 and gets `0x1900`, so the index is 25 and the
seven low bits are zero. The port wrote 0 there where the vendor writes 25.

The read of `GPIO_SEL` outside the write's gate is needed too (see
`patches/b43/NOTES.md`): without it, the region breaks into 22 blocks instead of
3. It is inert on hardware and not a mainline candidate.

## The five TXPCTL_STAT pairs at the entry, attributed

`wlc_phy_cal_perical_nphy_run` at its head does, in this order:

    if (phase_id == IDLE || phase_id == INIT) {
            nphy_cal_orig_pwr_idx[0..1] = (read_phy_reg(0x1ed/0x1ee) >> 8) & 0x7f;
            if (nphy_txpwrctrl != PHY_TPC_HW_OFF)
                    table_read(RFSEQ, 2, 0x110, ..., nphy_cal_orig_tx_gain);
    }
    target_gain = wlc_phy_get_tx_gain_nphy(pi);
    tx_pwr_ctrl_state = pi->nphy_txpwrctrl;
    wlc_phy_txpwrctrl_enable_nphy(pi, PHY_TPC_HW_OFF);

In the capture there are **ten reads** of `0x1ed`/`0x1ee` in the whole of
`up-ch1`, five pairs, and they map one by one:

| record | values | who does it |
|---|---|---|
| #7034/#7036 | **25, 25** | `nphy_cal_orig_pwr_idx`, IDLE/INIT branch, before the gain |
| #7038 | — | `nphy_cal_orig_tx_gain`, gated on the control being on |
| #7044/#7046 | **10, 12** | `wlc_phy_get_tx_gain_nphy()`, branch with the control on |
| #7050/#7052 | 10, 12 | inside `txpwrctrl_enable(OFF)`: it is `nphy_txpwr_idx` |
| #10784/#10786 | 10, 12 | same, in the PAPD region |
| #26073/#26075 | 10, 12 | same, at the end |

**The reference does not describe what the capture does at the tail.** The
`restore_tx_gain` branch, which the state machine turns on in the RSSICAL phase,
forces `nphy_cal_orig_pwr_idx` again, i.e. **25 and 25**, which with
`192 + index` would mean reading `26/0xd9`. The capture reads `26/0xca` and
`27/0xcc`, i.e. **10 and 12**: the indices the two chains had *after* the gain
read, not before. It is the same pattern as the precal index and the rccal's
grouping — brcmsmac is older than this radio — and the capture decides.

**Fixed, in two moves.** First the order: `target` is taken **before** the
precal, like the reference, not after. Then the variable: the index the tail
forces again is recorded by `b43_nphy_get_tx_gains()`, in its branch with the
control on, which is the read at #7044/#7046 — i.e. the tail puts back 10 and 12
by construction and not by an accident of the read plan.

The two wrong roads, tried and measured, because both look like the right one:

- using `tx_pwr_idx[]`, which on paper is the pair worth 10 and 12: the tail goes
  to `26/0xd9` and does not match. In the port that field ends at 25/25, the
  opposite of the vendor, because the three `tx_power_ctrl(false)` of the
  deferred block consumed the plan's entries before the sequence.
- reading the pair at the head of the sequence as the reference does: it gives
  25 and 25, which is the right value for `nphy_cal_orig_pwr_idx` and the wrong
  one for the tail.

The two ops of #7034/#7036 were then ported too, with the reference's names and
nobody reading them: see the next section, which says why an op whose value
nobody needs is still an op to port.

Measured: contiguous blocks 19247 -> **19254**, cold 18167 -> **18169**,
`perical-ingresso` divergences 905 -> **885**. Then came the two below.

## Things worth as much as a defect, which are not one

The corrections that moved the numbers most add no code: they put in order what
was there.

**The deferred block has to run inside the bracket.** The reference turns the
power control off at the head of the run, before anything forces an index. The
port turned it off only on entering the first step, so the precal and the two
hand-backs returned the control **on** and each one reprogrammed the 84 cells.
Hence six or seven blocks of 80-110 ops in which the vendor writes zeros and the
port writes content. The sequence now gets the entry state as an argument
instead of reading it again after the deferred block has turned it.
`perical-ingresso` divergences **885 -> 323**, missing ops **675 -> 42**.

**The disabling branch opened the data port by hand.**
`b43_nphy_tx_power_ctrl()` wrote 84 cells in a loop on `B43_NPHY_TABLE_DATALO`
where the enabling branch, ten lines below, uses `b43_ntab_write_bulk()` on the
same two tables at the same offset. Same cells, different road — but the
vendor's tracer hooks the table function, so its op is there and the port's is
not, and **that single missing op put everything that followed one out of
step**. It showed in the segment map: the equal blocks got one shorter at every
84-cell write — 77, 76, 75, 74, 73, 72... Per-phase total **7206 -> 7578**,
`cal-rx-iq` from 420 to 510, `rxiq-ingresso` from 306 to 401, `txpwr-index` from
6 known divergences to 4.

Cold loses 39 ops (18750 -> 18711) and no window broke: the assignment of blocks
is exclusive and greedy.

**The reference's two entry reads were exactly the six ops that were missing.**
`nphy_cal_orig_pwr_idx` (the pair, 2 ops) and `nphy_cal_orig_tx_gain` (the table
read on `7/0x110`, 4 ops) are done by the reference at the head of the run and
then not read again — the tail puts back the index taken *with* the gains, not
this one. So they looked like two dead ops not to port, and they were not:
without them the whole rest of the phase was six ops early, and it was those six
that triggered the families above at every 84-cell write. Ported, with the
reference's names and the same nothing reading them; the index the tail uses is
in `pwr_idx_at_gain[]`, written by `b43_nphy_get_tx_gains()`.
`perical-ingresso` divergences **286 -> 95**.

The rule that comes from it: **a vendor op whose value nobody needs is not, for
that reason, an op not to port.** If the hardware sees it, the sequence contains
it, and everything that follows is measured from it.

**The two ops that close `perical-ingresso` were a mainline defect and an
order.** In mainline `nphy->txcal_bbmult` is **read and never written**:
`b43_nphy_update_tx_cal_ladder()` reads it, and scales with it the 36 rungs of
the ladder the TX I/Q LO cal uses, and with no writer it is zero — every rung
comes out at zero amplitude, on every N-PHY rev 3 and up. The reference fills it
at the end of `wlc_phy_precal_txgain_nphy()` when `save_bbmult`, which on rev 7
and up is always, and again at the end of `wlc_phy_cal_txgainctrl_nphy()`. In
the capture it is the `TBL.RD 15/0x57` at #8076, right after the forcing.
**Mainline candidate**, as soon as what it changes on the cal has been measured.

And the gains at the forcing are taken between the forcing and the hand-back
(#8080), not inside the INIT step of the state machine: the reference does
`cal_target_gain = get_tx_gain()` right after `precal_txgain()`, in the same
step. Divergences **95 -> 19**, run **409 -> 573**, per-phase total
**7586 -> 7750**.

**And the per-step bracket does not go on every step.** With the power control
already off since before the deferred block, `b43_nphy_pwr_ctl_open()` inside the
loop turns nothing off and skips the gain read: 172 ops per step remain that the
hardware does not see. The port emitted **48** 84-cell writes against the
vendor's **36**, and the twelve extra were these.

Which one to keep is said by **the boundary audit**, not by intuition: between
perical and TX I/Q LO no transition, between TX I/Q LO and PAPD **one**, between
PAPD and RX IQ four — which are the two per core the PAPD cal opens itself —
between RX IQ and idle TSSI none. So only the opening at the head of the PAPDCAL
step stays. Removing all six gained on the RX IQ entry and lost **172 contiguous
ops** elsewhere: measured, not deduced, and it is why the answer was neither
"always" nor "never". `rxiq-ingresso` run **401 -> 500**, divergences
**722 -> 542**, missing ops **184 -> 19**.

**And the RX IQ calibration gain was wrong for two overlapping reasons.** The
capture writes `0x4077` on both chains, which is the `cal_gain` of entry 10 of
`b43_ntab_tx_gain_ipa_2057_rev8_2g` (`0x4077002e`: ipa 7, pad 14, pga 0, txgm 4) —
the index the precal forces on both. The port wrote `0x4027`, i.e. pad 4, which
is what comes out of interpreting the current content of `7/0x110`.

The formula of `b43_nphy_iq_cal_gain_params()` is identical to the reference,
so the defect was in the gains it receives, and they are two:

1. **`b43_nphy_cal_perical_phyinit()` overwrote the parameter** it had just
   received: it read the gains again at the head of its own function, with the
   power control already off, so `b43_nphy_get_tx_gains()` took the branch that
   reads `7/0x110` instead of the one that indexes the table. The caller passed
   pad 14,12 and the function used pad 4,4. Found with a temporary print after
   three readings of the code had not seen it: **when two plausible values
   contend for a result, print.**
2. **the RX IQ cal wants the gains at the forced index**, not the entry ones.
   With the entry gains, which have per-chain indices 10 and 12, `0x4077` and
   `0x4067` come out; with the ones at the forcing, 10 on both, `0x4077` and
   `0x4077`.

**The carrier search is counted, and the outer hold was missing.**
`wlc_phy_a4()` keeps it open from line 25133 to 25380, i.e. for the whole PAPD
cal; `b43_nphy_papd_cal()` did not. The hold is refcounted on `deaf_count`, so
without the outer one the brackets of the inner steps come out as entry-exit
pairs of their own: the port emitted **8** pairs against the vendor's **6**, and
the two extra were short, 27 and 34 ops, i.e. exactly inner ones the vendor gets
for free. The way to see it is to count the positions of `PHY.WR 0x2c = 0xffff`
(entry) and `= 0x404e` (exit) on both sides and look at the length of the pairs,
not only at how many there are.

**And the capture confirms it, which is the only check that counts here.** The
vendor's six pairs, by record, are:

| entry | exit | ops | what it covers |
|---|---|---|---|
| #1620 | #1666 | 34 | init |
| #8492 | #10756 | 1601 | TX I/Q LO cal |
| **#10771** | **#14946** | **3658** | **PAPD cal**, #10962-14092 |
| #14964 | #21143 | 5615 | RX IQ entry and sweep |
| #22245 | #23900 | 1052 | coeff setup and RSSI cal |
| #24271 | #24317 | 34 | idle TSSI |

The third covers the whole PAPD cal and exits at #14946, which is exactly the
exit seen in the 25-op group. And the shape of the port's pairs gets closer:

    vendor           34 1601 3658      5615 1052 34
    port, with hold  34 1052 1617 5112 5702 1052 34
    port, without    34 1052 1617 27 34 5702 1052 34

From eight pairs to seven, and the two short ones (27 and 34) disappear into the
long one.

Careful with how that 5112 against 3658 is read: **it is not a misplaced hold.**
Look at the two ends and they match op for op — at the exit, on both sides,
`PHY.WR 0x73=0x0`, `MOD 0x1e7 mask=0xe000`, `MOD 0x8f`, `MOD 0xa5`, `RD 0xb0`,
`MOD 0xb0=0x7`, `WR 0x2c=0x404e`, `WR 0x42=0x404e`. The length differs because
the port emits 1454 ops **inside** the PAPD cal that the vendor does not, which
was already known (`cal-papd` did 847 of 2662 and `a3`/`a2` were not there).
Counting the length of a hold does not measure the hold, it measures what is
inside it.

At the boundaries there is nothing left to measure, and the two numbers that
were here were an artefact of the shadows rule. Counted on both sides with the
pair rule: the marker `PHY.WR 0x2c = 0xffff` does **6 and 6**, and on `0xb0` the
two sides are identical value by value — 16 `MOD 0x7`, 6 `MOD 0x4`, 16 `RD 0xdf7`,
6 `RD 0xdf4`. There is no extra pair and no extra read. What remains on `0xb0` is
the **order**: in `rxiq-ingresso` the port receives `0xdf7` where the vendor has
`0xdf4`, and the swap closes eleven positions later.

A note on method, which was first got wrong: the first version of this entry
said "the run is a proxy, the GPL source is not". **No.** brcmsmac is much older
than the driver the capture comes from, and in this work it has shown it three
times (the precal index, the rccal's grouping, the index the tail forces again).
The capture decides, always. Here the capture and brcmsmac agree, but the check
was available and should have been done first — not afterwards, and not because
someone pointed it out.

**And one op was worth four hundred and sixty-six divergences.** The save block
of the RX IQ cal saves one register more than the port: `0x2ff`, read at `#15015`
right after the four rev 7 override registers and before `0x297` and `0x29b`.
brcmsmac **never** reads it — it touches only bits 0, 13, 14 and 15 of that
address in the rev 7 override path — so here the capture decides, as for the
precal index and the rccal's grouping. Saved and not restored, which is what the
capture does: the read is there, a write in this phase is not.

Why it is worth 466 divergences is the lesson: the missing read put everything
that followed **one** out of step, and afterwards it never realigned, because
from there on there are long runs of identical zeros and of identical sample
table content. The groups of 357, 46, 21, 16, 5 and the four pairs of 2 were all
that. `rxiq-ingresso` from **530 to 64** divergences.

The way to find it, which is the part to reuse: when the divergence groups are
many and the equal runs between them all have the same length, **they are not
many defects, it is an offset**. It is located by looking for the point from
which `port[i+1] == vendor[i]` holds for a dozen ops, and then by taking the
**multiset difference** on the span around it: what remains on one side only,
excluding the families with an exception, is the missing op. Here it was one
line.

**And the PAPD cal cleanup goes inside the second bracket, before it closes.**
The port did `run_one`, `pwr_ctl_close`, `cleanup`; the capture stops the tone,
puts back the multiplier and the coupler, walks the list of overrides at
#13749-#13918, and **only after** reprograms the adjusted power table.

Found with the positional comparison: aligning after the tail of step 2, the
vendor does `PHY.RD 0xc7` — `stop_playback` — where the port did `PHY.RD 0x1e7`
and the 84 cells.

**Two lines swapped**: contiguous blocks 20982 -> **21074 (92%)**, cold 18983 ->
**19333 (70%)**, portable hole 616 -> **524**. It is the best ratio of lines
touched to ops recovered in the whole series, better than the two runs of the TX
I/Q LO ladder — and the 163-op hole chased for three rounds was not a content
hole, it was this.

Method, which is the reusable part: the positional **segment map** of an
anchored window — how long the equal run, how long the different one, and the
first op of each — reduces 885 divergences to three families in one screen.
Counting the divergences says nothing; looking at how they are distributed says
everything.

## The ceiling is not 100%, it is 94%

The two metrics measure different things, and it is worth saying with numbers.
**The sum of the blocks** on `up-ch1` is 21529 of 23068; **the sum of the runs**
is 9069 of 18923.

The 48% of the runs **cannot** reach 100% by construction: the run is the
*largest* block inside the phase, so a phase that repeats the same sequence N
times stops at ~1/N. `cal-rx-iq` is the proof: run 531 of 5728 (9%), shape
`4x531 530 528 434`, i.e. the sweep's iterations paired at ~530 each. That number
is a regression detector, not a goal.

The **93% of the blocks** has a real ceiling, and it can be computed. The ops no
port can emit, by family:

| family | ops | portable? |
|---|---|---|
| `OBJ.WR` + `OBJ.RD` | 1284 | **no**: 734 distinct object memory addresses, 553 above 0x400. It is MAC and ucode state, and the harness builds the PHY, not the core |
| `TPL.RAMW`, `MAC.MCTRL`, `MAC.MHF`, `GPIO.OUT`, `CHANSPEC` | 69 | **no**, same reason |

So what is reachable is **23068 - 1352 = 21716, 94.1%**, and the port is at
21529: **187 portable ops** are left, i.e. **99.1% of the ceiling**. Of those,
**131 are absent and 56 moved** (the per-region table in "State"): the first are
missing code, the second order. By region the absent ones are 62 in the init,
22 in the tail, 26 in the sweep, 14 in the PAPD cal, 7 in the RX IQ entry and
**0** in the second RSSI cal.

Of the **99** unpaired stretches, `--global-run` prints the largest by comparable
ops, with the split between moved and absent:

| from record | comp. | moved | absent | write | ops in the stretch |
|---|---|---|---|---|---|
| **#5004** | 20 | 0 | 20 | **20** | 577 |
| #25823 | 19 | 2 | 17 | 2 | 195 |
| **#10761** | 18 | **16** | 2 | 9 | 18 |
| #9727 | 6 | 6 | 0 | 4 | 6 |
| #9008 | 5 | 5 | 0 | 3 | 5 |
| #24823 | 4 | 4 | 0 | 4 | 4 |
| #3732 | 4 | 4 | 0 | 1 | 4 |

The `write` column says how many ops of the stretch change the PHY's state
instead of reading it, and it serves to **understand** the stretch, not to decide
whether to port it: a block of reads only is ported anyway, because a read of a
PHY register is not without effects — see `#877` below, which was 3 writes out
of 51 and all of them had to be done. The largest stretch left is **#5004: 20
absent, all 20 writes**, and it is the ACI scan, which is not portable inside
`phy_n.c` (below).

What follows is how the stretches that were above these were closed, in order of
size; the numbers in each paragraph are those of that step.

**The PAPD cal pulses the reset of the clear channel assessment.** Right after
the carrier search hold and well before the tables, the capture at
#10773-#10776 reads BBCFG, writes it back with the `RSTCCA` bit set and then with
`RSTCCA` and `RSTRX` clear. The port had only the write that saves and clears the
RX reset — which the capture has too, but **inside** the `papd-tables` window, as
`PHY.MOD mask=0x8000`. They are two distinct writes at two distinct points and
the port had one: a single write of the cleared value leaves the same value
behind and **never resets the assessment**.

The spot matters and it was got wrong twice: in place of the existing write, or
before the scalar tables, the per-phase run loses **262 ops** and `papd-tables`
goes from `ok` to `noto`, because the comparison there is positional. After the
hold and before the tables everything is full again.

**The TX I/Q LO cal puts back the radio registers it takes.**
`b43_nphy_tx_cal_radio_setup_rev7()` saves nine cells per core —
`TX_SSI_MASTER`, `IQCAL_VCM_HG`, `IQCAL_IDAC`, `TSSI_VCM`, `TX_SSI_MUX`, `TSSIA`,
`TSSIG`, `TSSI_MISC1` — rewrites them with the calibration's values, and
**nothing put them back**: they stayed dirty for as long as the interface was
up. Sixteen radio registers. The capture restores them in address order at
#10737-#10752, right after the gains go back in place. **+16** and **+16**,
exactly the number of writes.

14 of the sixteen remain with different counts (vendor 9-14 against port 5-10):
those differences are elsewhere, not in the restore.

**80 ops at #796: closed.** The order between aux ADC and RF sequences was the
point, and the answer is that the device does the tx2rx twice, the second after
the aux ADC. Entry below.

**The PAPD enabling tail is ported.** At #13842-#13854 the vendor puts back the
epsilon offsets and turns the engine on, with the status rereads in between:
adjust core 0, reads of `0x2bf` and `0x2c0`, adjust core 1, reads of `0x2b1` and
`0x2b2`, then bit 0 of `PAPD_EN0` and `PAPD_EN1`. It needs four new names in
`phy_n.h` for the status cells, which b43 did not have. Counting register by
register, now **all ten** of the engine's match: `0x297`, `0x298`, `0x29b`,
`0x29c`, `0x2a3`, `0x2a4`, `0x2b1`, `0x2b2`, `0x2bf`, `0x2c0`. Numbers unchanged,
and it is in because that bit **turns the engine on**: a PAPD cal that does not
turn it on is useless.

**55 ops at #884 and 20 at #5614** — they are a pair: the vendor **reads back**
the group `gain_ctl_workarounds` writes (`0x20`, `0x2a7`, `0x21`, `0x2a8`,
`7/0x106`, `0x280`, `0x283`) and later **rewrites** it with the same values.
brcmsmac has no save/restore of that group. No risk to the state: the restore
rewrites what is already there.

**32 ops at #203** — the `0x1df`/`0x1e1`, i.e. `STRA_2U`/`STRA_2L`, once declared
not portable: b43 has them only as defines and brcmsmac never writes them. Closed
by the spur workaround, below.

**174 ops in 81 fragments under 10 ops** — these do not close by hand: 2-9 op
fragments are where the vendor's tracer has its observability holes
(`phyclk_fgc`, `switch_macfreq`) and where a missing op cannot be told from an
unrecorded one. They need the new capture and the two hooks.

**The spur workaround was a stub, and it was the first hole of the init:
ported.** `b43_nphy_spur_workaround()` opened and closed the carrier search
bracket and did nothing in between. The device does something there, at
`#203-#234`, right after the write of `0x3830` to `NDATAT_DUP40`, which is the
call site.

The reference on a 20 MHz channel and radio rev 8 emits nothing, and that is why
the stub went unnoticed: `wlc_phy_adjust_rx_analpfbw_nphy` holds for phy rev < 7,
`adjust_min_noisevar` has the list empty outside channels 3-10 at 40 MHz, and
`adjust_crsminpwr` restores only what a previous adjustment saved. So the
capture is the only voice, and the two captures agree.

What it does: the same value `0x1591` into the two registers
`STRA_2U`/`STRA_2L`, then a reread — a pair of table 7 cells at `0x106`, and then
**twice** three table 0 cells at `0x0b`, `0x13`, `0x23` and the `TRLOSS` register
(`0x169`). The values are thrown away, and that is no reason to remove the reads.

It is worth **54 ops**: the 27 of its stretch and 27 further on that were
unpaired only because the alignment had slipped. The init from 8297 to **8351**
paired and its absent from 183 to **129**, the total absent from 261 to **207**,
the blocks from 21396 to **21450** and cold from 21257 to **21299**.
`MESSAGES.md#0031`. Note: `docs/gap-inventory.md` stays as it is, because that
table is measured on the **pristine** tree and the stub is still there — it is
`b43/` that fills it.

**The stretch at #10714: b43 leaves the lpf override on, once per init.** It is
not four trace ops, it is state that stays in the hardware. Counted on both
sides:

| | vendor | port |
|---|---|---|
| turns the override bit on (`0x342`, `0x80`) | 9 | 9 |
| turns the band field off (`0x340`, `0x700`) | **9** | **8** |
| turns the override bit off (`0x342`, `0x80`) | 5 | 4 |

In the vendor the field's turn-ons and turn-offs pair one to one:

    on  1641  8629 11764 12878 15056 15060 18136 18140 24292
    off 1714 10715 12871 13839 15057 15061 18137 18141 24365

The long pair is `8629 -> 10715`: the override turned on by a sample play stays
up for the whole TX I/Q LO cal and is turned off only at the boundary of the
PAPD cal. The port loses exactly one, so **a turn-on without a turn-off**.

The cause looked like bookkeeping: `lpf_bw_overrode_for_sample_play` is a
**bool**, and `b43_nphy_run_samples()` sets it true only
`if (!(lpf_bw3 | lpf_bw4))`, i.e. only if the override was not already on. The
first `b43_nphy_stop_playback()` that goes by consumes it and clears it, and the
turn-on of a later play is left without an owner. The device instead turns off
once per turn-on, nine and nine.

**Closed, and the counter was not the road.** Looking at the records between
`8629` and `10715`: there is **a single** `stop_playback`, at `#10693`, and the
override survives it — it is turned off 21 records later, at the end of the rest
of the cleanup. So that override does not belong to the sample play: it belongs
to the **TX I/Q LO cal**, turned on by `b43_nphy_tx_cal_phy_setup()`, and nobody
turned it off. The `stop_playback` bool is fine for the override that function
really owns; this one outlives several plays.

Turned off at the end of `b43_nphy_tx_cal_phy_cleanup()`, where its owner ends.
Now it is **nine and nine** on both sides, the init goes from 8416 to **8420**
paired and its absent from 66 to **62**, the blocks from 21525 to **21529**.
`MESSAGES.md#0036`.

And the port's sequence said so, counted on the normalised ops: `ON@6925` with
`stop@8409` and no `off`, while the other eight pairs all closed.

**The stretch at #5004: it is the ACI scan, and it sits above the PHY.** Its 20
comparable ops are at `#5614-#5633` and are an **apply-and-restore** of the gains
and of the CRS thresholds: `0x20`/`0x2a7` to `0x7e`, `0x21`/`0x2a8` to `0x624`,
`7/0x106` to `0x623f`, `0x280`/`0x283` masked to `0x44`, `0x2e6` to `0x4477`,
`0xc33` to `0x10`, and then again `0x283`, `0x280`, `7/0x106` and
`0x21`/`0x2a8`.

**Eighteen of twenty are idempotent**: those values are exactly the ones the
registers already have, read at `#884-#896` — `0x7e`, `0x624`, `0x3644` whose low
part is `0x44`, `0x623f` — and read back identical at `#26077-#26087`. The two that
cannot be checked are `0x2e6` and `0xc33`, with no name here or in the reference
and never read in the capture.

**It is not portable inside `phy_n.c`**, and it is not an excuse: that block sits
among ops the port does not emit at all — the SHM cleanup at `#5600-#5612` and a
`MAC.MHF` — and before the chanspec setup. That is, it comes from **above the
PHY**, like the ACI scan, and it is its first appearance inside the init. The
harness builds the PHY and not the MAC, so from here it cannot even be measured.
Same entry as the ACI scan.

**The stretches at #4958 and #6330: half closed.** They are the same four-op
block twice, and it is `b43_nphy_tx_power_ctrl()` on the branch that **turns
on**: the device clears the two enable bits (`0xc000` = `HWPCTLEN|PCTLEN`,
leaving `COEFF`), puts the two indices back, and **then** turns all three on
(`0xe000`). b43 turned on first and put the indices back afterwards, so the
control ran with the old indices for two writes.

Reordered: the two ops on the bits now match. The two writes of the indices do
not, for two reasons together — they are gated on `tx_pwr_idx != 128`, and the
values b43 has there are `0x19` where the device writes `0xa` and `0xc`. **That is
a question about what the save of the index keeps**, not about where the op sits.
Worth absent from 138 to **135** and blocks from 21522 to **21525**.
`MESSAGES.md#0035`.

**The stretch at #3732: located, not closed.** It is **one** read of the current
gain (`TBL.RD 7/0x110 len=2`) the vendor does between `restore_rssi_cal` and
`tx_pwr_ctrl_coef_setup` — the read of table 15/80 at `#3738` is the first op of
`coef_setup` — and that b43 does **before**. The counts match, **nine and
nine**, so it is order and not missing code: eight of the nine pair at the exact
record, and only the first is ~1000 records late.

Who does it, with `B43_TEST_TBLDBG=7:110`: seven from the calls to
`b43_nphy_int_pa_set_tx_dig_filters()` (`phy_n.c:5549`), one from
`run_pending_perical()` (`7777`), one from `5958` and one from `6708` (lines of
`phy_n.c` at the time of the measurement: they have moved since, and `b43/` no
longer has those calls at those lines). The late one is the first of the seven, and in `b43_phy_initn`
the order is `int_pa_set_tx_dig_filters` (which reads) → `restore_rssi_cal` →
`coef_setup`, where the vendor has `restore_rssi_cal` → read → `coef_setup`.

**It was not moved**, and the reason is that inside `int_pa_set_tx_dig_filters`
that value **is used**: `curr_gain` becomes `target` for the three rows of
filters. Moving the read means changing which gain that function sees, and there
is no source saying the vendor reads it twice or uses it elsewhere. Four ops, and
moving them needs understanding who consumes the value in the vendor.

**`tssi-setup` closed, 19 of 19, and there was a wrong value inside.** Two
things, at `#1251-#1281`.

The first: `b43_nphy_ipa_internal_tssi_setup()` writes seven radio registers per
core, and the device **reads four of them back first** — `r+8`, `r+9`, `r+0xB`,
`r+0xA` in this order, once per core, at `#1251-#1257` and `#1266-#1272`. Added.

The second is more than an op out of place. On the 2 GHz path b43 writes **1**
into each core's G-band TSSI register for every phy rev other than 7, and `0x31`
for 7. It is transcribed right from the reference (`phy_n.c:17075-17080`). **The
device does neither**: it reads that register, finds `2`, and leaves it — in
`#1259-#1281` there is no `RAD.WR 0x17b` nor `0x19b`, and the `2` is still there
when the TX I/Q LO cal puts `0x31` at `#8537` and puts `2` back at `#10743`. So it
is not order: it is a **wrong value left in the radio for the whole init**, and
the capture is the only voice against the reference. The write is gated off on
radio rev 8.

Worth the init from 8406 to **8414** paired and its absent from 76 to **68**, the
total absent from 154 to **138**, the blocks from 21505 to **21521**. And the
windows with declared divergences go down from **six to five**.
`MESSAGES.md#0033` and `#0034`.

**The stretch at #877: ported.** It is 61 ops, `#877-#987`, at the end of the
workarounds between the second tx2rx pass and the `BBCFG RESETCCA` pulse at
`#988`, and the port emitted **nothing** there: it went from `#876` to `#988`
straight.

Every register read is one that `gain_ctl_workarounds()` and the gain tables
have just **written**: the four initial gains and the clip thresholds per core,
the narrowband thresholds, the two `CRSMINPOWER`, the twelve `ED_CRS` thresholds
(`0x224`-`0x22f`), two blocks of table 4 and the master and RSSI IDAC registers
on both radio cores. Reading back what was just programmed is what a driver does
before something can change it, and that something here is the **ACI scan**,
which the capture does afterwards and this driver does not have.

The values are thrown away, and that is no reason to skip the reads. **Left out
of the patch on purpose**: the list in SHM at `0x1570`-`0x1576` that declares
`0x8f`, `0xa6`, `0xa5`, `0xa7` to the ucode, and a bit in word 4 of the
hostflags. That bit has no name either in b43 or in the reference, and turning
on an unnamed ucode flag on the sole faith of a capture would be a conjecture
about the firmware.

Worth the init from 8351 to **8406** paired, i.e. **99%** of the comparable
ones, and its absent from 129 to **76**; the total absent from 207 to **154**,
the blocks from 21450 to **21505** and cold from 21299 to **21350**.
`MESSAGES.md#0032`.

**The stretch at #796: closed, and it was 80 ops of 122.** It was not the eight
masksets that were missing — those were already there, **in the wrong pass**.
The device programs the RF **tx2rx** sequence **twice**, with the same seven
events and the same delays: the first at #390-#420 and the second at
#796-#874, the latter preceded by the eight masksets on `AFECTL_C1`/`C2` and by
the auxiliary ADC tables at #771-#789. Counted over the whole window: the device
writes `7/0x10`, `7/0x90` and the nine padding cells **twice**, b43 once. The
values are identical between the two passes and between the two sides, and that
is why they came out as **missing** ops and not as wrong values.

Neither b43 nor the reference had the second pass. Added at the end of
`b43_nphy_workarounds_rev7plus()`, after the ADC tables, with the masksets moved
there from the first pass where they do not belong. Worth the init from 8217
paired ops to **8297** and its absent from 254 to **183**, the total absent from
332 to **261**, the blocks from 21316 to **21396** and cold from 21177 to
**21257**. `MESSAGES.md#0030`.

What remained of that stretch was another thing and starts at **#877**: the 51
absent ops ported by `0032`, above, and the four `OBJ.WR` at `0x1570`-`0x1576`
that declare to the ucode the registers `0x8f`, `0xa6`, `0xa5`, `0xa7` — i.e. the
tempsense list — which stay out.

## What remains open

Most of the entries below are closed, and they stay as the record of how: each
says what it changed, with the numbers of its step. What is open is said as
such.

- **`M_CTS_DURATION`: in.** The RXCAL phase now writes it with the MAC on, like
  the reference. It needed a new define, `B43_SHM_SH_CTSDUR = 0x00B8`, and the
  same one in `test/unit/stubs/b43_defs.h`, which the README declares generated
  from the tree's `b43.h` but for which there is no script: added by hand, count
  from 487 to 488.

  And it brought out two things about the comparison. **The port does emit**
  `MAC.EN`/`MAC.SUSP` — `wrap.c` lines 689 and 694 — and it is not true that the
  harness stubs them silently: the vendor's decoder calls them
  `MAC.MCTRL val=0x1/0x0 mask=0x1`, i.e. with the MACCTL bit they change, and it
  is a naming problem like `GPIO.OUTEN` → `GPIO.OE`. Normalised in `compare.py`.
  And the object memory space: b43 passes `B43_SHM_SHARED`, which in its enum is
  1, where the vendor's decoder prints `0x10000` — in these two captures
  `0x10000` is the **only** value that appears, 3565 and 3295 times, so the
  translation is unambiguous for the data we have. Translated in `compare.py`,
  with the note that if a capture with a second space shows up that function has
  to be redone with a map.

  Before getting there a **skip** on the two `MAC.MCTRL` was tried, and it was
  the wrong mechanism: a skip says "this op cannot be emitted", and these can.
  Removed.

- **The extra pair was not a pair, and it was the seed.** The seventh marker
  `PHY.WR 0x2c = 0xffff` is not an entry into carrier search: it is the clip
  detection that `b43_nphy_rev3_rssi_cal()` turns off by itself. The real pairs
  are six, resolved one by one: `run_samples` (three times), `cal_tx_iq_lo`,
  `papd_cal`, `rev3_cal_rx_iq`.

  And the vendor, in its first RSSI step, **does not calibrate: it restores**.
  Between #132 and #8000 it reads `0x219` **only once** — zero polls — and at
  #3712-#3731 it writes the two radio registers and the twelve PHY ones in a row,
  which is exactly the body of `b43_nphy_restore_rssi_cal()`. The capture is a
  **hot** init: the vendor's driver already has `rssical_chanspec` set from a
  previous boot and takes the restore road. The bench cleared that chanspec
  together with the others, so the port did a full calibration: **1052 ops the
  vendor does not have**.

  Fixed in the **bench**, not in the driver: `rssical_chanspec_2G` stays set.
  The other three are cleared as before, because the capture really contains the
  TX I/Q LO and RX I/Q cals (the brackets at #8492 and #14964 say so).

  **The values are not seeded: the first init, which does the calibration, puts
  them there.** The two radio registers and **eleven of the twelve** PHY ones come
  out identical to the capture. Copying them from the capture instead of letting
  them be computed is worth **one op** on `up-ch1` (20403 against 20402), and
  fourteen constants copied into the bench are not worth an op.

  The only one that differs is `0x1ac`, the fine narrowband offset of **core 0 on
  the Q rail**: the bench computes 0, the capture has 1. And the loop that writes
  it already uses `offset[i]` and not `offset[2 * core]`, so it is not the shape of
  the code — it is the polled values that differ by one step. Open, and small.

  **Cold, how they are computed is unknown, and it is not an omission: there is
  no capture.** `full-init-ch1-bw20` **starts** the RSSI cal and is cut off: the
  first two groups of polls are at #32637 and #32709, and at #32769 the
  65285-record hole begins. So of the cold algorithm we have the code — the VCM
  sweep, which in this work was corrected twice — and no trace to check it
  against. Having one needs a new capture that covers past #32769.

  | | before | after |
  |---|---|---|
  | **per-phase total** | 7749 (41%) | **8590 (46%)** |
  | `up-ch1` contiguous blocks | 20035 (87%) | **20403 (89%)** |
  | `cal-rssi-2` | run 99, 10% | **run 940, 98%**, shape `940 18` |
  | `rssi-cal` window | 1/16, 15 missing | **9/16, 4 missing** |
  | carrier search pairs | 7 | **6**, like the vendor |
  | reads of `0xb0` | 25 | 22 (vendor 16) |

  It is the biggest gain of the whole work, and it is not a line of driver: it is
  a line of seed. **When a phase does an order of magnitude less than the rest,
  look at whether the bench is forcing it down a branch the capture does not
  take.**


- **The one-to-many override of the TX gain used the wrong field.** The
  `TX_GAIN` case of `b43_nphy_rf_ctl_override_one_to_many()` passed `0x4000`; the
  reference does `(0x1 << 12)` for the gain and **`(0x1 << 13)`** for the lpf gain,
  i.e. `0x1000` and `0x2000`. And the count of the turn-offs on `0xe7`/`0xec`
  confirms it on its own: the vendor turns `0x4000` off **zero** times and `0x2000`
  eight, the port turned `0x4000` off four times and `0x2000` two. Also corrected
  the cut of the second argument, `(value & 0x8000) >> 14` instead of
  `value >> 14`, which carried bit 14 along — the same one the first call takes
  inside the gain.

  Contiguous blocks 20951 -> **20971**, cold 18964 -> **18972**, and the small
  fragments of `cal-papd` from 19 to **9**. After the fix the per-field counts all
  matched except `0x8` (6 against 4) and `0x2000` (8 against 12).

  **Read again in full, field by field, and the rest is fine.** `RXRF_PU` does
  `(1<<5)`, `(1<<4)`, `(1<<3)` on ID1; `RX_PU` the five on ID1/ID1/ID1/ID2/ID1 with
  `0x800` at zero; `TX_PU` the five on ID0/ID1/ID2/ID2/ID1 with `0x800` at one — and
  that fifth is there because a mainline patch puts it; `RX_GAIN` uses
  `(0x1 << 11)` and `(0x3 << 13)`, i.e. `0x800` and `0x6000`, and the cut
  `value >> 8` on a `u16` is equivalent to the reference's `(value & 0xff00) >> 8`.
  Only `TX_GAIN` was broken.

  The two per-field counts that did not match were chased **for the state, not
  for the score**: if the vendor turns an override off and we do not, it stays on.

  **`0x8`, two in the port against three: it was an override left on.** The TX
  I/Q LO cal inside the setup does `rf_ctl_override_rev7(0x8, 0, 0x3, false, 0)` —
  it turns on field 0x8 on table 0 — and nothing turned it off again. It stayed on
  on both cores after the calibration. The capture turns it off at #10729 and
  #10731, right before the gains go back in place, **and the spot matters**: put
  after `stop_playback` it costs 13 ops on the `cal-tx-iqlo` run, put right next to
  `ntab_write_bulk(7, 0x110, save)` it is worth four. Contiguous blocks 20971 ->
  **20975**, cold 18972 -> **18976**.

  **`0x2000`, six in the port against four: closed, and the classification was
  wrong.** The turn-ons matched, two and two; it was the turn-offs that were six
  against four. The **positional** comparison of sixteen ops, aligning the tail of
  core 1's step 2, settles it: without the `0x1000`/`0x2000` pair that had been put
  at the head of `b43_nphy_papd_cal_cleanup()` it does **16 of 16**, and inside
  those sixteen there is the `0x1000`/`0x2000` of #13741-#13748 that had been
  attributed to the cleanup. It does not belong to the cleanup: it is the **tail of
  `papd_run_one()`**, which already emits it.

  So the vendor's four turn-offs of `0x2000` are **two per core in the steps**, and
  the cleanup does none. With the pair removed, the counts all match — `0x2000`
  four and four, `0x1000` eight and eight — and the classification by presence of
  a `0x2000` next to it is identical op for op:
  `alone, P, P, alone, P, P, alone, alone`.

  The **second** turn-off of `0x1000` alone in the cleanup's list of fields
  (#12820, #13788, after `0x800`/table 0) remains: that one is real and stays in.

  And the idea of gating the tail of `run_one` on `gain_ctrl` falls: the vendor
  does it in **both** steps.

  **A note on the arbiter.** That gate had been measured three times and each time
  it lost 258 ops, and from that it had been concluded that the vendor did it in
  one step only. The 258 were an artefact of `difflib`, which **is not
  monotonic**: removing ops from the port's side can lose pairings. For a question
  on eight ops the arbiter is the positional comparison on a nearby anchor, not the
  matcher — and the three measurements written on this page were all useless.

  Also burnt: **moving the auxiliary ADC tables before the RF sequences**, which is
  the capture's order: it costs 24 ops. (The question was then answered by the
  second tx2rx pass, "#796" in "The ceiling".)

- **Eight masksets on `AFECTL_C1`/`C2`, gated on radio rev 8.** The capture has
  them at #796-#803: bits 2, 3 and 6 to one and bit 7 to zero, core 0 then core 1
  each time, and without touching the override pair next to them. The reference
  touches those bits only in the tempsense path, and there always together with
  `0x8f` and `0xa5`. They now sit in the second tx2rx pass, where the capture has
  them (`MESSAGES.md#0030`).

- **The first delay of the TX2RX sequence is `0x46`, not 8.** The capture writes
  it at #806, in the seven-cell bulk on table 7 offset `0x90`. For rev 7 and up the
  reference does not help: `wlc_phy_workarounds_nphy_rev7()` **does not program**
  the TX2RX sequence at all, so the 8 that was in
  `b43_nphy_workarounds_rev7plus()` had nothing behind it. The six delays that
  follow and all seven events already matched. It costs **one** op, because that
  cell sat inside a hole that started earlier: it is in because the value has a
  source and the previous one did not.

- **`tx_power_offset[]` has to be filled before the traced init, and it is the
  seed again.** At #2000 and #2086 the vendor writes the 84 cells of the adjusted
  power table **with content** — `0 0 0 0` and then `2 c c c` repeated — where the
  port wrote eighty-four zeros. The reason: only `recalc_txpower` fills
  `nphy->tx_power_offset[]`, and in the harness it ran **after** the traced init;
  the vendor's driver has those offsets because the capture is a hot init and its
  previous boot computed them. Added an untraced `recalc_txpower` right after the
  cold init, inside the region that writes to `/dev/null`.

  **Mind the pending flag**: without turning `perical_pending` off first, that
  recalc drags along the deferred sequence, which redoes the RSSI cal and rewrites
  the cache — and the second init would restore that one instead of the first
  one's. Tried: `up-ch1` lost 479 ops and the `rssi-cal` window no longer found its
  anchor (`PHY.WR 0x1b8 val=0x3f` disappears). With `perical_pending = false`
  first, only the computation of the offsets remains.

  Contiguous blocks 20632 -> **20952 (91%)**, per phase 8590 -> **8756 (47%)**,
  portable hole 963 -> **643**, and the `pwr-setup` window goes from 266/432 to
  **432/432**.

  Third time the bottleneck was the seed and not the driver, after the RSSI cal
  and the entry gains. **The rule holds: before looking for missing code, look at
  whether the bench starts from a state the capture does not have.**

- **The ladder of the TX I/Q LO cal is written in two runs, not interleaved.**
  `b43_nphy_update_tx_cal_ladder()` wrote 0, 32, 1, 33, 2, 34...; the capture
  writes `0x00`-`0x11` and then `0x20`-`0x31`, two consecutive blocks, and shows it
  **twice** (#9015-#9123 and #9735-#9843). The same thirty-six cells of table 15
  and the same values: only the grouping changes. brcmsmac interleaves too —
  **fifth time**.

  Contiguous blocks 20426 -> **20632 (90%)**, cold 18758 -> **18965 (69%)**,
  portable hole 1169 -> **963**. Two lines of loop for 206 ops.

- **The auxiliary ADC tables are no longer a `/* TODO */`.** In
  `b43_nphy_workarounds_rev7plus()` the four bulk writes on table 8, offsets
  `0x08`, `0x18`, `0x0c` and `0x1c`, were commented out because the arrays were
  not there. The capture has them at #771-#794: `0x8e 0x96 0x96 0x8b` for core 0,
  `0x8f 0x9f 0x9f 0x96` for core 1, `0x02 0x02 0x02 0x00` for the two gain ones.

  The reference picks the last element from the power detector range and from the
  band. Only this board's combination is in the port — range 2, radio 2057 rev 8,
  2 GHz — because the others have no capture behind them. And there brcmsmac
  writes `0x8c` on **both** cores where the capture writes `0x8b` on core 0 and
  leaves core 1 at `0x96`, which is the array's default; the gain element agrees
  at 0. **Fourth time** brcmsmac is older than the driver of the captures.

  Contiguous blocks 20402 -> **20426**, cold 18734 -> **18758**, portable hole
  1193 -> **1169**.

- **The PAPD cal cleanup also turns off field `0x2000`, and the first two go
  before stopping the tone.** The capture, at #13741-#13748: `e7`+`0x7c` and
  `ec`+`0x7f` (field `0x1000`), then `e7`+`0x348` and `ec`+`0x349` (field `0x2000`,
  whose value sits in the four low bits of those two registers and not in a whole
  register). Those eight ops turned out to be the tail of `papd_run_one()`, not of
  the cleanup (entry on `0x2000` above), and that is where they are now.

- **Old: the gate in `b43_nphy_run_samples()` is NOT to be added.** The reference
  gates there on `phyhang_avoid` (`phy_n.c:23087`) and b43 calls unconditionally;
  and `hang_avoid` in b43 is `(rev == 3 || rev == 4)`, false on rev 8. It looks
  like a typo, and it is not: inside the **vendor**'s first 34-op pair
  (#1620-#1666) there are `0xa1`, `0xa3`, `0xa4`, `0xc3`, `0xc4`, `0xc5`, `0xc6`, the
  lpf override on `0x340`-`0x343` and the read of `15/0x57` — i.e. `run_samples`,
  with the bracket, on a rev 8. The vendor does it, and b43's ungated call is
  right **for this hardware**. brcmsmac is older, again.

  The gate was tried and measured: the port goes from **7 pairs to 5** where the
  vendor has 6, i.e. it moves away; cold however it gains **+1137** (18734 ->
  19871, 68% -> 72%) and hot it loses 126, with the per-phase run from 7749 to
  7737. Withdrawn for the pair count and for the run, but **that +1137 cold is not
  explained**, and it was the biggest thing not understood at the time.

  The site of the extra pair was then the one of 1052 ops that opens at `@3271`,
  right after the last op of `b43_nphy_tx_power_ctl_setup()`, and it is **not**
  `tx_power_ctl_setup` — that one is gated on `hang_avoid` in both drivers,
  checked. The method that works: `fprintf` with `__builtin_return_address(0)`
  inside `b43_nphy_stay_in_carrier_search()` and resolution with `nm -n`, keeping
  in mind that the PIE offset has to be computed and that a wrong estimate shifts
  the symbol by one. (It turned out to be the RSSI cal's clip detection, entry
  above.)

- **A mainline defect found on the way, which does not concern this hardware.**
  `hang_avoid` in b43 is `(phy->rev == 3 || phy->rev == 4)`; in brcmsmac
  `NREV_GE(rev, 3) && NREV_LT(rev, 6)`, i.e. 3, 4 **and 5**. On rev 5 b43 skips all
  the anti-hang brackets the reference puts in. Mainline candidate, provable
  against brcmsmac without hardware, not measurable here.

- **The count of the `rxiq-ingresso` window goes from 64 to 555, and it is not a
  regression.** With the three ops in their place the parity of the alignment
  changes and a shift that was masked comes back up: the read plan of `0xb0`. The
  ops stay the same — 18 missing and 18 extra out of 1503 — and the two big
  measures go up by 4 each. It closes by removing the extra carrier search pair,
  not by working in that window.

- **Old entry, for the record: `M_CTS_DURATION` was not an exception.** In the
  15-op group of `rxiq-ingresso` the vendor does, between the two `MAC.MCTRL`, an
  `OBJ.WR addr=0xb8 val=0x2710`: it is `write_shm(M_CTS_DURATION, 10000)`, because
  `M_CTS_DURATION = M_PSM_SOFT_REGS + 0x5c * 2 = 0xb8`. The reference does it
  **twice**, in both branches that lead to the RX IQ cal (`phy_n.c:25413` for the
  state machine and `25460` for the other), and in b43 it was **nowhere**:
  `grep CTS_DURATION` over the whole driver found nothing.

  It had been filed under the `OBJ.WR` exception, and the exception says
  something else: that the harness cannot **emit** object memory ops in a
  comparable way — not that the driver may skip **doing** the write. And indeed
  `wrap.c` has `b43_shm_write16()` and prints it as `OBJ.WR`, so the write would
  even be visible in the trace. The two `MAC.MCTRL` around it are
  `b43_mac_enable()` and `b43_mac_suspend()`.

- **`rxiq-ingresso`, 510 of 1510 with 57 divergences, and they are three groups,
  all attributed.** Six are the 9-bit reread of tables 26/27 beyond offset 576, at
  `@31`, `@434` and `@947` with the high word next to it. Two are on `0xb0`, where
  the counts match and only the order changes. The other **49 are a single shift
  of two**: at `@1459` the vendor reads `0x340` and `0x341` and the port does not
  read them there; from `@1461` the two sequences are the same, shifted by two.
  Those two ops are identified and **closed**, entry below.

- **The two reads of `0x340`/`0x341` in `run_samples`: closed.**
  `b43_nphy_run_samples()` on the `rev >= 7` branch read `0x342` and `0x343` for
  the lpf override bits and stopped there. The reference reads two more and
  throws both values away — `read_phy_reg(pi, 0x340)` and `(pi, 0x341)`,
  `phy_n.c:23109` and `23110`, with the comment `lpf_bw_ctl_miscreg3/4` — and the
  capture does the same: of the 28 reads of `0x340`, **22 are preceded exactly by
  `RD 0x342`, `RD 0x343`**, i.e. every sample play. The other six are two other
  sites b43 already has. The value thrown away does not authorise removing the
  read: a read of a PHY register is not without effects.

  Added (`MESSAGES.md#0027`): `rxiq-ingresso` from 57 divergences to **37** and run
  from 510 to 532, `cal-rssi-2` to **960 of 960**, `idle-tssi` from 357 to 432,
  per-phase run from 8779 to **8896**.

  The collapse of the blocks this change seemed to cause — 21110 to 19454, the
  sweep from 5784 paired to 4112 — was **difflib**, not the order: see
  `lcsmatch.py`. With the optimal pairing the sweep is at **5798** and `up-ch1` at
  **21140**, i.e. 30 ops better than before the change. The diff of the port's two
  traces already said so: 51 lines, 26 ops added and **four** lines of different
  behaviour.

- **difflib did not look for the longest common subsequence, and for a year the
  block count gave false numbers: closed.** `SequenceMatcher` looks for the
  longest contiguous block and then recurses right and left. On the RX IQ cal,
  which repeats an almost identical sequence seven times, the first block it
  latches onto can be the wrong iteration, and from there a whole iteration stays
  unpaired on both sides. Measured: on `up-ch1` difflib pairs **19454** ops where
  the optimum pairs **21140**, i.e. it leaves **1686** on the table.

  `lcsmatch.py` does the optimal pairing: bit-parallel LCS for the lengths and
  Hirschberg for the alignment, 0.4 s on `up-ch1`. The bitvector that comes out of
  one LCS pass encodes the lengths on all prefixes of the second argument, so the
  row Hirschberg reads costs a single pass. Its tests check three things: the
  lengths against a naive DP on all prefixes, that the blocks are a **valid**
  alignment — monotonic, and with ops that really match, because a long wrong
  alignment is worse than a short one — and that it is never worse than difflib.

  What changes, with the same driver and the same capture:

  | | difflib | optimal |
  |---|---|---|
  | `up-ch1`, blocks | 19454 (84%) | **21140 (92%)** |
  | `up-ch1-freddo` | 19867 (72%) | **21011 (76%)** |
  | RX IQ cal sweep | 4112 (69%) | **5798 (98%)** |
  | `cal-rx-iq`, shape | `532 529 528 511` | `531 528 2x527 2x524` |
  | contiguous holes | 120 | 114 |
  | portable ops unpaired | 2262 | **576** |

  The shape of `cal-rx-iq` is the signature: six iterations paired at ~527 each,
  which is what a phase repeating six times has to give. With difflib they were
  four numbers above 500 and two iterations gone.

- **The `PHY.CLK` exception is now applied, not just declared.** The reasoning
  that justifies it is in the list of exceptions further down:
  `b43_phy_force_clock()` is `phyclk_fgc`, the tracer hooks `core_phy_clk`, so those
  ops are not observable and in the two DSL-3580L captures they are **zero**. It
  still stayed in the port's flow though, and there it did harm: the per-window
  comparison is positional, so a single op one side cannot have shifts everything
  that follows by one. Removing it from the port's side — `PORT_UNSHOWABLE` in
  `compare.py`, the mirror of `NOT_COMPARABLE` — takes `perical-ingresso` from 13
  divergences to **5** and `rxiq-ingresso` from 492 to **57**. The denominator is
  not touched: the harm was not there.

  If one day the measurement is made against `router-data/vd630/fullinit.txt`,
  careful: there two `PHY.CLK` are present, both `val=0x1`, and they come from the
  other function. The same name covers two things and they have to be separated
  first.

- **The shadow of a `MOD` is a pair, and has to be recognised as a pair:
  closed.** `drop_rmw_shadows()` recognised the shadow by prefix alone and ate a
  whole **run** of `RD`s on the same address, so it deleted all 110 reads of the
  poll of `0x129` (`IQEST_CMD`), which sit downstream of the `MOD` that starts the
  command, and the six `RD 0xb0` that are the read of the **second** call to
  `b43_nphy_classifier()` inside `stay_in_carrier_search()`. The port does those
  reads, and they were left without a counterpart.

  The inner read of a read-modify-write never comes alone: if the tracer records
  the read it records the write too. So an `RD` that follows a `MOD` without a `WR`
  behind it is a real op. On `up-ch1` the old rule dropped 175 ops in runs of
  length `1x6 2x28 3x1 5x1 6x5 27x1 48x1`: the runs of 1 and 2 were real shadows,
  the other 113 were not.

  What changed: `up-ch1` from 22951 to **23068** vendor ops, and the visible reads
  of `0xb0` from 16 to **22**, which is the real number in the capture.
  `perical-ingresso` from 17 divergences to **13**, `rxiq-ingresso` from 555 to
  **492**, the `idle-tssi` run from 334 to **357**. No window opened.

- **The read plan of `0x129` was out of phase, and the shadows rule hid it.** The
  vendor closes every poll by reading the value with START off **twice** — 8
  estimates out of 8: four `1 1 1 1 0 0`, one `1 1 1 16 16`, one `1 1 1 1 32 32`,
  one of 48 and one of 27. The reference does **three** reads at the end:
  `SPINWAIT` (`phy_n.c:26050`), the `WARN` (`26052`) and the `if` that opens the
  read of the accumulators (`26056`); the capture has two, so wl 6.30 does not
  have the `WARN`. b43 does **one**, which serves both as exit test and as guard.

  The plan is a queue per address, so the extra entry was consumed by nobody and
  taken by the next call, which exited at the first round:
  `B43_TEST_PLANDBG=1` gave 65 reads in 8 calls, shapes `5 1 5 1 4 1 47 1`, with
  the entries all consumed inside the vendor's **first four** estimates. The even
  calls waited for nothing.

  It was not the bench's invariant giving way: `wrap.c` declares it per address,
  and says that if the port skips a read the values of that address shift by
  one. Here the port skipped nothing: it is the vendor doing one more **by the
  shape of its source**, and b43 has no way to consume it. The shift was
  therefore structural and grew by one per estimate.

  **Closed in `gen_readplans.py`, with a declared list**: `POLL_DOUBLE_TAIL` holds
  the command registers whose end the vendor's source reads twice, and today it
  has a single line, `PHY 0x129`. A general rule cannot be deduced from the
  capture, and it was tried: "drop the duplicated tail of every poll" also touches
  `0x21a` and `0x219`, which in the second RSSI cal are **eight equal samplings in
  a row** and not a poll, and would starve their plan of 416 entries.
  `PHY 0x0c0` (`IQLOCAL_CMD`) on the other hand does not belong there and the
  reason is measured: its 24 groups end with the value changing only once
  (`0x8434 0x8434 0x8434 0x434`), so b43 and the vendor do the same number.

  The plan loses 8 entries of 110 and the poll is back in phase: 102 reads in 8
  calls, shapes `5 5 4 47 5 5 5 26`, i.e. one per estimate and each one read fewer
  than the vendor, which is exactly right. Worth the sweep from 5798 paired to
  **5882**, its **moved from 58 to 11** and **absent from 61 to 24**, the total moved
  from 201 to **153** and absent from 375 to **339**, `up-ch1` from 21140 to
  **21224** and cold from 21011 to **21093**. The 47-portable-op hole at #17913 is
  gone.

  The twelve accumulators (`0x12c`-`0x131`, `0x134`-`0x139`) were **8 and 8 on all
  twelve** before too, so the values of the estimate were the capture's: it was
  the waiting that was wrong, not the estimate.
- **`perical-ingresso` is closed**: 575 of 1402 with 17 declared divergences.
- **A small entry remains**: the two `PHY.MOD 0x349 val=0x0 mask=0xf` at #13320 and
  #13392 the port never emits — the 4-bit mask is field `0x2000` alone, the
  `(0x1 << 13)` entry of the rev 7 override table.
- **Half of the capture was compared with nothing, and now what it contains is
  known.** The capture goes up to **#70796** and `up-ch1` measures `#132-26100`.
  The structure, counted on the `CHANSPEC` markers:

  | | records | what |
  |---|---|---|
  | `#132` ch=1 | 25969 | the init, i.e. `up-ch1` |
  | `#26101`-`#34937` | 8837 | 14 hops of the ACI scan, ch1↔ch5 every 2 s |
  | `#34938` ch=6 | **27034** | the channel change and what follows |
  | `#61972`-`#70796` | 8825 | 15 hops of the ACI scan, ch6↔ch2↔ch10 |

  It is not "ch1 then ch6": it is init, scan, change, scan. Of the 27034-record
  block we compared **42 ops**, those of `chanswitch-ch6`. And that block is not
  a channel change: within **1.45 s** of the change the vendor redoes the
  calibration from scratch — `IQLOCAL_CMD` at #43852, the sample plays at #43366,
  the I/Q estimates at #51744 — a block as big as the init.

  **And that block is an init all over again.** The longest common subsequence
  between `#132-26100` and `#34938-61971` is **22308 ops of 23649, 94%**: on the
  channel change the device redoes the same sequence as the init, on the new
  channel.

  **Whoever calls it in b43 does not exist, and it is not a typo.** The `do_cal` /
  `deferred_cal` block is in **`b43_phy_initn()`**, not in the channel change
  path: `b43_nphy_set_channel()` goes through `b43_nphy_channel_setup()`, which
  has nothing of calibration. So `op_switch_channel` emits **60 ops** and cannot
  emit more. And the condition `do_cal = !nphy->iqcal_chanspec_2G.center_freq` is
  **identical** to the reference (`wlc_phy_init_nphy`, `phy_n.c:19483`), so there
  is nothing to fix there: in the reference the recalibration comes from the
  **watchdog**, `wlc_phy_cal_perical(PHY_PERICAL_WATCHDOG)` under `glacial_timer`
  (`phy_cmn.c:2278`), and b43 has no equivalent.

  Consequence on hardware, not on the bench: **b43 puts back on ch6 the TX I/Q LO
  and RX I/Q calibration made on ch1**, where the device recalibrates from
  scratch.

  **Tried separately, the calibration code knows how to do the new channel.**
  `flow_chancal` does the hot init, changes channel and does the init again: it is
  a manoeuvre of the bench — the cal chanspecs cleared as `flow_init` does before
  the traced init — and it serves to separate "the code knows" from "someone
  calls it". Measured:

      ./phase_compare.py --vendor .../opinit-ch1-ch6-bw20.decoded \
          --global-run 34938 61971 --flow chancal --channel 6
      -> 21593 of 23649, 91%

  i.e. as much as `up-ch1`. The measured surface of the repository doubles.

  Two things were needed to get there, and both were traps of the bench. **The
  read plans ended with `up-ch1`**: without those of the new range every wait
  falls on the mirror and spins up to its limit — measured, 181338 reads of
  `0x2be` in a single poll of the PAPD cal and four million ops in all. Now
  `gen_readplans.py` can make sets with different names
  (`--name ch6` -> `b43_test_load_readplans_ch6()`) and there is
  `readplans_ch6.h`. And **`--max-len` truncates**: with 512, `0x2be` lost 466 of
  978 and the poll spun anyway. `up-ch1`'s plans were not truncated, that range
  stays under 512.

  The two blocks **are not windows**, and not by oversight: 23649 and 29979 ops
  against the port's 46307 and 55304 cost `lcsmatch` minutes, being
  O(n*m/64) per Hirschberg level. They are measured with the global run, and the
  two commands are in the comment at the point of the table where the windows
  would have gone.

  And `flow_full` was built on `initcal` instead of on the hot init, so it did not
  compare with this capture, and no window used it. Now it is `flow_txpower` plus
  the channel change, i.e. `op_init` up to the end of `op_switch_channel`, and it
  stays at 60 ops because that is how much b43 really does.

  **The cold capture has the same block too, and now it is measured.**
  `full-init-*` has `#339` ch=1, then `#98383` ch=**11** for **34738 records**, then
  the ACI hops ch7↔ch11. The 65286-record hole between `#32769` and `#98055` is
  the tracer's buffer wrapping around, so the ch11 block is good data. And it is
  an init too: LCS with the truncated cold init **26521 of 29979, 88%** (with the
  hot one on ch1, 75%, which says that cold resembles cold more).
  `flow_chancalpor`, based on `flow_initpor`, plans `readplans_ch11.h`:

      --global-run 98383 133120 --flow chancalpor --channel 11
      -> 25526 of 29979, 85%

  More than the 76% of the cold init, which contains the power-on things the
  bench does not do.

  **The two bases were already there and they are the ones the windows use**:
  `flow_txpower` for the hot capture, `flow_initpor` for the cold one. What was
  missing was a set of read plans per range, one per capture, and
  `flow_chancal_from()`, which takes base and plans as parameters. The two flows
  are three lines each.

  **How much of each capture is inside a compared range, counting the records that
  exist:**

  | capture | records present | before | now |
  |---|---|---|---|
  | `opinit-*` (hot) | 59693 | 23211, 39% | **47003, 79%** |
  | `full-init-*` (cold) | 69557 | 28401, 41% | **59127, 85%** |

  The rest are the hops of the ACI scan, which is a policy above the PHY.

- **The 75 moved ops of the PAPD cal are ONE switching too many of the power
  control.** They are not scattered: four are isolated
  `PHY.MOD 0x2a3`/`0x2a4 val=0x3 mask=0x7` (#12220, #12354, #13334, #13406), the
  other **71 are a contiguous block**, `#13842-#13918`, which the port emits all
  together and in the right order — the `PAPD_STAT` reads, the `PAPD_EN`, the masks
  on the `CAL_SHIFTS`, the `BBCFG` and the three rows of filters, i.e. the tail of
  `b43_nphy_papd_cal()`.

  How far out of place: the pairing before that block has offset **-23**, after it
  **-94**, and the port emits it at `@12267` where the previous offset would put it
  at `@12091`. **176 ops late**, and in between the port slips in 176 that start
  with `PHY.RD 0x1e7` and `TBL.WR id=0x1a off=0x40 len=84`.

  The count adds up exactly. A `TBL.WR` of 84 cells unrolls on the table port into
  **86 ops** (`0x72` with the address, then 84 `0x73`, plus the `TBL.WR` itself), and
  the power control writes them **in pairs**, table 26 and table 27:
  `86 + 86 + 4 = 176`. It is not a block of work: it is **a single** extra switch
  of the power control.

  Who writes them is `b43_nphy_tx_power_ctrl()`: zeros when it turns off,
  `adj_pwr_tbl` when it turns on, on both tables. It has nine callers, and inside
  the calibration every phase turns off and on again. Counted the writes of
  `26/0x40` over `#132-26100`: the port does **43**, the vendor **36**, and all seven
  extra fall in the cal region.

- **The seven extra reprogrammings of the power table: closed.** Found with
  `B43_TEST_PWRCTLDBG=1`, which in the wrap of `b43_ntab_write_bulk()` prints the
  `backtrace()` of every 84-cell write of `26/0x40`. The offsets resolve with
  `addr2line -f -e nphy_trace`. Of the 43 of the traced round:

  | writes | site that switches the control |
  |---|---|
  | **24** | `b43_nphy_txpwr_index()`, its internal turn off/on |
  | 10 | `b43_nphy_pwr_ctl_open`/`close()` inside `b43_nphy_papd_cal()` |
  | 3 | `b43_phy_initn()` |
  | 2 | `b43_nphy_op_recalc_txpower()` |
  | 2 | `run_pending_perical()` and `cal_perical_phyinit()` |
  | 2 | `b43_nphy_txpwr_index()`, another site |

  Every site is in a perfect bracket, off and on: `gainctrl` opens **six**, not
  twelve. The twelve are the *writes*, two per bracket, and telling the two apart
  is what it takes not to get the conclusion wrong.

  It is not that b43 writes where the device does not: **the reference too writes
  the 84 zeros when it turns off** (`wlc_phy_txpwrctrl_enable_nphy`,
  `PHY_TPC_HW_OFF` branch). The difference is **how many times** it switches, and
  now where is known, because the port's writes are attributed to the regions
  through the pairing: those inside a paired block have the vendor's exact record,
  not an estimated one.

  | region | vendor | port |
  |---|---|---|
  | init | 13 | 13 |
  | **PAPD cal** | **1** | **8** |
  | RX IQ entry | 7 | 7 |
  | RX IQ sweep | 9 | 9 |
  | second RSSI cal | 0 | 0 |
  | tail | 6 | 6 |

  **All seven extra writes were in the PAPD cal, and no other region had one too
  many.** The device does that calibration reprogramming the adjusted power table
  **once**, at the end; b43 reprogrammed it eight times, with the four brackets of
  `pwr_ctl_open`/`close` — one per pass, two per chain — and the inner ones of
  `txpwr_index`.

  **Closed**: a single bracket around the whole calibration, opened before the
  per-chain loop and closed after the rows of filters, which is where the device
  writes the table (#13921, right after the rows end at #13918). The passes still
  have the control off, and the inner brackets become harmless by themselves: the
  turning-off branch touches the table **only if the control is really on** in the
  hardware, so they find the bits already off and emit nothing.

  Worth: the PAPD cal from 2573 paired ops to **2644 of 2662**, its **moved from 75
  to 4**, the sweep at **100%**, total moved from 153 to **76**, contiguous blocks
  from 21239 to **21316**, holes from 112 to **105**. `MESSAGES.md#0029`. The absent
  do not move, and that is the point: it changes **when** the driver does a thing,
  not whether it does it.

  And the comment that said that in the capture every opened bracket is what lets
  the closing reprogram the table, quoting four openings at #12197, #12331, #13311,
  #13383, goes: the openings are there, but they reprogram nothing. **One** extra
  write remains in the PAPD cal, 2 against 1.

- **The rewrite of row 1 of the TX filters: closed for rev 8.**
  `b43_nphy_int_pa_set_tx_dig_filters()` writes the first three rows of
  `tbl_tx_filter_coef_rev4` on `0x186`, `0x195` and `0x2c5`, fifteen registers per
  row, and then rewrites row 1 on `0x195` a second time **only** if
  `phy.rev == 17`. This device is rev 8 and does it: in the capture the groups on
  `0x195` are **four** against three of `0x186` and two of `0x2c5` — `#304` and
  `#334` at init, `#13874` and `#13904` at the end of the cal — and the fifteen
  values are **identical** in all four. Counted on both sides: `0x186` 45 and 45,
  `0x2c5` 30 and 30, `0x195` 60 and 30.

  It is idempotent, so the state of the registers does not change; the defect is
  the **shape**. The three rows are a single block of forty-five writes, and
  fifteen missing in the middle put everything that follows out of place. With the
  rewrite the `txdigi-filts` window goes from "15 missing" to **60 of 60**, the
  windows with declared divergences go down from 7 to **6**, the init gains 15
  paired ops and the total absent go down from 339 to **324**.

  The gate is the revision it is measured on. brcmsmac on the 20 MHz path does not
  write `0x195` twice — `wlc_phy_ipa_set_tx_digi_filts_nphy` writes the three rows
  and that is it — so the capture is the only voice, and it is no voice on any
  other revision.

  **What remains** is that in the PAPD cal the fifteen ops are now **moved** and
  not paired: the second occurrence, at `#13904`, is latched onto the other one.
  The region's moved go from 60 to 75 and its absent from 29 to 14, i.e. the total
  count improves but the cal's tail has an order of its own, still to look at.

- **`cal-papd`: `a3`/`a2` stay out**, two holes of 349 and 276 ops hot and 920 and
  930 cold, because cold the gain index search is complete.
- The **#190-254** hole of `switch_channel` is not portable, and it is not the
  spurwar: in brcmsmac both flags that turn that body on,
  `nphy_gband_spurwar_en` and `nphy_gband_spurwar2_en`, are gated `phy_rev < 7` in
  `wlc_phy_attach_nphy`, so on rev 8 the function does nothing — exactly like b43's
  stub. The ops left out are `PHY.WR 0x1df = 0x1591`, `0x1e1 = 0x1591` and a
  `TBL.RD id=0x7 off=0x106 len=2`; those two addresses (`STRA_2U`/`STRA_2L`) exist in
  b43 only as defines and **brcmsmac never writes them**. Same category as
  `RAD.RD 0x81`: vendor ops with no GPL reference, not ported. (The spur workaround
  entry in "The ceiling" has since ported them on the capture alone, `0031`.)
- **The measurement loop is the ACI scan.** The name is in brcmsmac, which keeps
  its **prototype and not its body**: `int wlc_phy_aci_scan_nphy(struct brcms_phy *pi);`
  in `phy/phy_int.h:1097`. ACI is *adjacent channel interference*, and it explains
  the shape the capture shows: the off-channel hop every ~2 seconds, 100 samples per
  core on `0x1c9`/`0x1ca`, and its absence from the first up. **It is not
  `poll_rssi`**: that one alternates the two registers and on rev 8 reads
  `0x219`/`0x21a`, while here they are 100 consecutive on one register and 100 on
  the other. And on rev 8 the two addresses are not the GPIO latches the names in
  `phy_n.h` say: in the capture **3400 reads and zero writes**. The orphan
  prototype is the point: it is a **policy** that sits above the PHY, and the
  corresponding place in b43 is the interference mitigation
  (`B43_INTERFMODE_*`), which exists only for the G-PHY.
  `b43_nphy_rev8_chan_meas()` in `0015` is its measurement primitive and stays
  without a caller until the policy exists.

## One thing of the hardware, not of the port

In 26/27 beyond offset 576 the readback is the written value **masked to 9
bits**, measured on five cells out of five (`0x24a`, `0x24c`, `0x25e` on both
cores: written `0xffffffe9`, read back `0x01e9`; written `0xffffffbb`, read back
`0x01bb`). The two sides write the **same** value and the harness's table mirror
keeps all 32 bits: **it was not masked on purpose**, because five cells of one
region in one capture do not justify a width inside the tool, and the divergence
is inert — the only consumer is `b43_nphy_txpwr_index()`, which does
`(((s16)v) << 4) & 0x1ff0`, and `0xffffffe9` and `0x01e9` both give `0x1e90`. It
costs two ops on the `txpwr-index` window and is declared there.

## The structure of the capture

`wlc_phy_a4` is the PAPD cal and runs **once per init**; `a3_nphy` (147 lines)
looks for the gain index and **reads** the epsilon table, `a2_nphy` (279)
**writes** it. Full map in `docs/papd-cal-map.md`, the two drivers' flows side by
side in `docs/init-flow.md`.

`do_full_init` (b43) == `phy_init_por` (brcmsmac): behind it are the download of
the static tables and rcal/rccal.

Inside `up-ch1` the PAPD cal reads like this, and it is how it is to be quoted:
blocks at #10966 (847 ops), #11822 (334), #12784 (145), #12936 (334), #13752 (90),
#13856 (48), #13921 (172). (Block positions of an earlier pairing; the current
shape of the phase is `792 518 2x381 371`, see "State".)

**There are two captures and they serve different purposes.**
`opinit-ch1-ch6-bw20.decoded` (70796 records) is the reference of everything
above: it is a **hot** init and does not contain the static download — the
opening of table 10 appears in neither of its two inits — and that is why the
`init` flow does two inits and traces only the second. `full-init-ch1-bw20.decoded`
(81397 records) is a **cold** init, and the only one that contains the init
tables: against it, with the `initpor` flow, the port **reproduces them op for
op** — 1424/1424 on table 13 and 806/806 on table 18, windows `static-tables` and
`static-tables-2`, the only two that declare `capture=`. It has a 65285-record
hole beyond #32769, so only #2-32769 can be compared positionally.

The record numbers here and in the documents are `opinit-*`'s unless said
otherwise: the ranges exist in both files and **do not identify themselves**.

In mainline the periodic cal does not start: `perical = 2`, and the branch that
follows in `b43_phy_initn` is a `;/* TODO */`. `0012` puts the init of the PAPD
tables there and `0014` the vendor's sequence, gated on phy rev 8 and radio rev
8. The `full` flow does not move, because it sets `perical = 0` and takes the
other branch. `initpor` is the only flow that traces a cold init **with** the
cals: it does not clear `perical`, so it goes through `0014`'s branch.

## The regions, which are two: one per behaviour

`CONTIG` in `phase_compare.py` has **two** entries, and they are the same macro
operation in its two behaviours. They are not two phases: they are two roads the
code takes, and a calibration phase checked against a single capture validates
one branch and says nothing about the other.

| region | capture | flow | ops | in blocks |
|---|---|---|---|---|
| `up-ch1` | `opinit-*`, hot init | `txpower` | 23060 | **21529, 93%** |
| `up-ch1-freddo` | `full-init-*`, full init | `initpor` | 27704 | **21364, 77%** |

`up-ch1` starts where `switch_channel` starts — the `CHANSPEC` at **#132**, which
the tracer emits and the port does not — and ends with the **MAC enabled and
transmitting**, #26100. No anchor: the region is the whole run, so the blocks are
found over the whole output of the flow without latching onto an op picked by
hand.

`up-ch1-freddo` starts from the `CHANSPEC` at **#339** and ends at **#32769**,
which is not the MAC enabled but the limit of comparability. It covers **more**
than the other because it contains the download of the static tables, which is
not there hot — they show as blocks of **1424** and **806** ops.

Everything before, **#1-131, is `op_init` and `rfkill`**: it is the state this
region cannot have, and it is **seeded** instead of traced (below).

Per-phase regions were tried and removed, and it is not an aesthetic second
thought: **a phase taken alone says nothing about what lands on it from
before**. The `chanswitch-ch6` window says 33/39 and "no missing op", and the
whole phase is at **14%**, because 62% of it is a measurement loop the port does
not do at all. The verdict of `up-ch1` is the **structure of the blocks**, not a
percentage: a block that gets shorter is a regression even if the total goes up.

Two things on reading the report:

- **`minsize` filters the printing, not the count.** Filtering it in the total
  too removes ~630 real ops in runs shorter than 16. A printed hole can contain
  short runs.
- **"Zero occurrences" proves nothing.** It can mean the tracer does not look or
  that `wl` does not do it, and the two have opposite consequences for the port.
  It is settled by looking at **where the access goes through**:
  - `PMU.`: `wl-diag` hooks `si_pmu_spuravoid` (the decoder prints it `PMU.SPUR`)
    and the function is the one mainline calls `bcma_pmu_spuravoid_pllupdate`
    (`drivers/bcma/driver_chipcommon_pmu.c:493`), i.e. it exists and can be hooked:
    zero occurrences means **wl does not call it**, and the port's `PMU.SPUR` is a
    real divergence.
  - `MMIO.` has an exception, but the right motivation is the **level**, not the
    count: the vendor records those accesses as **`SI.COREREG`** (54 in the
    capture, `core=0x0`, `off=0x64` and `0x6c`), so looking for `MMIO.` proves
    nothing. `0x492` is `psm_phy_hdr_param`, and in brcmsmac it is reached with a
    **direct** `bcma_write16`, not with an accessor (in
    `wlc_phy_chanspec_nphy_setup`, bit in `d11.h:978`): a tracer that hooks
    functions does not see it.
  - `PHY.CLK`: the exception holds, but **it was evaluated against the wrong
    accessor**. `b43_phy_force_clock()` corresponds to `wlapi_bmac_phyclk_fgc` →
    `brcms_b_phyclk_fgc` (`main.c:1716`), not to `brcms_b_core_phy_clk`.
    `wl-diag` hooks `wlc_bmac_core_phy_clk`, which is another function: so
    `phyclk_fgc` **is not hooked** and its ops are not observable in these
    captures. And the port does the right thing — `b43_nphy_reset_cca()` and
    `wlc_phy_resetcca_nphy()` are identical, `fgc(ON)`, BBCFG, `fgc(OFF)`,
    `RESET2RX` — so the `PHY.CLK`s the vendor does not have are a hole of the
    tracer, not of the port, and `PORT_UNSHOWABLE` removes them from the port's
    flow because an unobservable op shifts the positional comparison. To close it
    fully: a hook on `phyclk_fgc` and a new capture. `MAC.FREQ` stays an
    undemonstrated exception as before (`brcms_b_switch_macfreq`, hooked in
    `wl-diag/3-4/`, so zero occurrences would mean wl does not call it: to be
    checked again on a new capture).

  Rule: an exception is declared **against a missing hook**, never against a zero
  count, and **never on a whole family when inside it there is an op the driver
  should do**: the `OBJ.WR` exception says the harness cannot emit object memory
  in a comparable way, not that b43 may skip writing the SHM. That was fallen into
  with `M_CTS_DURATION` — and before declaring it one looks at whether **the
  accessor exists**. And it is not enough that *an* accessor of the family is
  hooked: **one looks at which accessor that access goes through.** Object memory
  teaches it: `write_objmem16` was hooked, but a region read 192 times and never
  written is written by `copyto_objmem`, which internally calls `write_objmem` and
  not the `*16` variant, which was not hooked (`gap-inventory.md` 4i). The family
  is large — in brcmsmac there are **66 `brcms_b_*`** — and `wl-diag` hooked **ten**:
  the missing ones were the reason for all three exceptions. Added (in `3-4/`
  only) `read_shm`, `write_shm`, `set_shm` (offset in **bytes**, the same level as
  `b43_shm_*16`: that is what makes the **677 SHM offsets** comparable, which
  before were noise), `core_phy_clk`, `switch_macfreq`, and
  `suspend_mac_and_wait`/`enable_mac`, which give the **MAC enabled** boundary
  `up-ch1` ends on.

  Accesses that do **not** go through an accessor stay unobservable, and the
  exception is declared against that. A variant that marked the entry of the
  PHY's functions was tried and **removed on purpose**: marking internal functions
  produces a map of the structure of the vendor's driver, which is something other
  than observing the hardware and much easier to contest. A phase boundary is
  derived from the accessors' ops, and `MAC.SUSP`/`MAC.EN` give an explicit one.
  It holds for **new captures**.

The `!do_full_init` gate on the tail of the periodic cal **is not to be added**,
and the reason is instructive: the cold region contains the **first nine ops** of
that phase and then ends, because at #32769 the 65285-record hole begins. The last
records of the cold capture, #32753-32769, are the same ops in the same order as
#23761-23777 in the hot capture: the vendor starts the phase cold too, and the
hole cuts it. **Gating there would be gating against a hole**, which is the same
mistake as gating against a zero count.

## The seeds, and what they are worth

`reverse-tools/gen_seed.py --before 132` looks **only at the records that precede
the region** and emits `test/unit/seed_up.h`, which `main.c` applies after the
cold init and before the traced one. Two categories:

1. what `op_init` and `rfkill` programmed;
2. what is **first accessed in the capture by a read**: nobody wrote it, so it is
   the chip's default. The criterion is not "never written" — the cal writes
   `0x17d`, but **after** reading it. This brings in the coupler's two `atten` at
   `0xaa`, which were the last value hole of the PAPD cal.

68 phy and 70 radio in all, of which 91 defaults. **Measured: they are worth 32
ops out of 23068**, so what does not match **is not missing state, it is code**.
The mechanism stays because it is correct and will be needed when the holes
close, not because it is the lever. Do not make it look like the lever.

For **table cells** the boundary of the seed is necessarily different from the
registers'. For registers one looks only before the region; a cell like
`15/0x50` is written nowhere in the capture, because the static download that
filled it belongs to a previous boot. Its state at the entry is observable **only
from the first read inside the region**, and two conditions keep the rule honest:
the cell is seeded only if no port write touched it before that read — if the
region wrote it, the value is what the region has to compute — and only if its
value **does not change** between the reads, because if it changes it is the
hardware writing into it inside the region, and that is a plan's job. They are
**39 cells**; the 5 left out of the 44 with a fixed value are those a port write
had touched.

## Rules

- **Measurements live in the tools**, not in throwaway scripts: they have to be
  redone.
- **The documentation can be stale.** A lot of it has been corrected; do not
  trust it, check again.
- `file:line` references to mainline are checked on the **pinned** tree, not on
  `b43/`; references to `b43/` say so.
- **Delimit the phase** before counting, with an op that closes it (e.g. the
  first `CHANSPEC` for the radio init), not by eye on a range of records.
- **`Op.ep` is the only way** to know which record an op comes from:
  `load_vendor` drops bookkeeping and shadows, so index ≠ record number.
- **When a phase scores zero and the ops are there, suspect the value before the
  call site.** `coeff-setup` said zero for three sessions and the fault was in
  `tbl_port_get()` in `wrap.c`, which did not advance the address on reads.
- **When a table cell diverges, look at its history before the reference's
  flow**: `trace_tables.py --cell ID:OFF` prints it, reads included, and tells the
  writes that change the value from the idempotent ones.
- **A count that adds up does not prove the behaviour is right.** 35 writes equal
  to 35 with the sequence still wrong has happened, and it cost 151 contiguous
  ops.
- **Counting occurrences of an op without checking what that op means** is the
  source of all three retractions in this file: the two directions of
  `b43_nphy_tx_power_ctrl()` are told apart only by the **payload** (84 zeros =
  turning off), and in b43 they even had different op shapes. The vendor's tracer
  hooks the table function and sees both directions the same way, so its counts
  **are not comparable** with ours op by op unless the shapes match.
- **A marker has to be checked to mark one thing only.** `TBL.RD 7/0x110 len=2`
  does not belong to the bracket: `b43_nphy_get_tx_gains()` reads it too, with the
  **opposite** condition.
- **When a number goes down, measure the region alone before calling it a
  regression**: the assignment of blocks is exclusive and greedy, and a block can
  change hands without anything getting worse.
- **Before saying a change is not needed because the phase does not move, look at
  the blocks**: the per-phase metric ignores fragments on purpose, and
  under-reports a right fix.
- **Before saying the port does something extra, look at whether the GPL
  reference does it** — and if it does, the question is whether the tracer can see
  it.
- **The precedence is: the capture, then brcmsmac.** brcmsmac serves to
  understand the shape and to give the names, and for that it is irreplaceable;
  but it is much older than the driver that produced these captures, and every
  time the two disagreed it was wrong (precal index, rccal grouping, index forced
  again at the tail). A change is **not** justified by brcmsmac against a
  measurement: one goes looking in the capture for the direct proof, which is
  usually there.
- **A defect that looks like one has to be measured before believing it.** The
  `type = 2 -> 0` downgrade in `b43_nphy_cal_rx_iq()` had always been taken for a
  defect; removing it the port got worse by 476 ops, because the real defect was
  upstream (`bool` instead of the DAC test mode).
- **The check of a build is the exit status, not a grep.** The compile line
  contains `-Werror`, so `grep error` always matches:
  `if make KDIR=... >/tmp/b.log 2>&1; then echo OK; else grep -E 'error:' /tmp/b.log; fi`
- **The `N finestre: X da guardare` line has to be read at every round**, not only
  the total: it is the only thing that says whether a change broke an anchor, and
  the two big measures do not notice.
- Every patch behind a revision gate, checked with `check_patch_gating.py`.
  Declared exceptions, all and only for transcription typos from brcmsmac in
  shared code: `b43/MESSAGES.md#0010` and the mainline
  `b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7`. A typo is not a
  feature of this hardware and does not go behind a gate. The list of the six
  points the tool flags is in `patches/b43/NOTES.md`.
- No "it used to be like this" comments: those go in the commit message. It also
  holds for measurement deltas — `from X to Y` in a comment is history.
- **Provenance in trailers**: `Link:` for every URL, one per line — it is the name
  the kernel knows, not `Reference:`/`Capture:`/`Tool:`. Kernel sources are cited
  on **git.kernel.org** pinned to the sha: `...phy_n.c?id=848acc8ffe1b#n23018`, or
  the line slips. A link into this repository is pinned to a sha too, because
  paths here move. The capture has a `Link:` to the file and, **in the body**, the
  record range and the first op with the file's spacing, which `grep -F` finds:
  4.4 MB and 70796 lines, GitHub does not render it and a line anchor leads
  nowhere. `From:` and `Signed-off-by` both go on `alessio.ferri@mythread.it`,
  which is the address the patches leave from and the one of the seven commits
  already merged; the gmail one is not used. Body at 75 columns.
- **SALAME** in bold on unverified hypotheses about the behaviour of the code,
  **TONNO** on unfounded answers.

## Traps already fallen into

1. **Used the blob outside the perimeter `PROVENANCE.md` declares.** That file has
   always said that what is needed from the blob is the **symbols with their
   sizes** (for the tables) and the **prologues of the accessors** (to know whether
   the detour holds), because the product of that analysis is the tracer. To
   attribute the measurement loop, function bodies were disassembled and callers
   listed: right conclusions, wrong source, redone on `brcmsmac`, which had them
   all. **Questions about behaviour go to `brcmsmac` first**, and `PROVENANCE.md` is
   read before opening the blob, not after.
2. Built the harness against a tree other than the one believed, and read the
   results as regressions. The port's files now always come from `b43/`, and
   `KDIR` matters only for what the port does not touch: it has to be the pinned
   tree, and `git -C ~/src/pin status` has to be empty before believing a number.
3. Quoted line numbers of `b43/` as if they were the pinned tree's:
   `phy_n.c:4021` instead of `3950`.
4. Counted a phase on a window by eye that mixed three, and concluded something
   false ("70 registers, a subset of the 412" — 32 of 70 had a different value).
5. Rebuilt the op→record correspondence by hand: it drifts by up to 230 ops.
6. Attributed to the "core not built" ops that were in code built and not called
   (`b43_software_rfkill` was an empty stub in `wrap.c`).
7. Believed an anchor of `phase_compare.py` never found (`0x186 val=0x100`, which
   does not exist in the capture): a `pending` window with an impossible anchor
   never fails and never says anything.
8. Wrote "a read on hardware is needed" when the value was in the capture.
9. **Believed a window that broke, instead of looking at what it was latched
   onto.** `recalc-txpower` went from 519/519 to 432/519 when the tail of the
   periodic cal was added, and it looked like a driver regression. It was the
   anchor: the window took the **third** opening of `26/0x0`, which was the port's
   recalc as long as the sequence ran elsewhere, and which with the sequence at the
   end of recalc became the power setup of the cal's tail. It compared the
   vendor's recalc with the port's tail. With the anchor corrected to the second,
   the window is back to 519/519 **with** the change in. An ordinal anchor moves
   when the code moves: when a window breaks, first look at where it landed.
10. **Believed an unanchored per-region measure.** A slice of 1402 vendor ops
    compared against the port's 24000 gave 92% in 31 blocks, and from those 31
    blocks a fragmentation inside `b43_nphy_txpwr_index()` was deduced. It was not
    there: the blocks were spread over 14065 ops of trace, i.e. they were the ten
    identical writes of 84 zeros, each taken from a different point. The total of
    the whole window does not have this problem, because the slice is the whole
    run. Rule: **before reading a per-region number, look at where the blocks
    land.** `phase_compare.py --global-run` now prints it by itself.
11. Measured on a flow other than the one the region declares: `up-ch1` declares
    `flow=('txpower', '1')`, which is init **plus** `recalc_txpower`. The comment
    next to the region explains it.
12. **Exec bits** get lost at every merge done by applying a diff (`git apply`
    without `--index` does not put them in the index). Seven times so far:
    `sh scripts/check-exec-bits.sh`. (`scripts/patch-from-commit.sh` was the
    eighth.)
13. **Cut a text mixing notes and diff by line count**, and before that on the
    first `---`: but the notes use `---` between one increment and the next too,
    and 73 lines of increments disappeared, twice (the head of the old rollup,
    today `patches/b43/NOTES.md`). Cut on the first `diff --git`, and check that
    the surviving piece matches the source before stitching back.

## Defects found in mainline, to remember what to look for

`patches/mainline/` holds the **twelve** independent of this hardware, to be sent
first and as **twelve separate `[PATCH]`es in as many threads**, not as a series:
they do not depend on each other, and tying them means a long review on one
blocks the merge of the others. The list with one line each is in
`patches/mainline/README.md`, which is the source. With `sample-table-logic`
alone, `sampleplay-tssi` and `sampleplay-iqlo` do 322/322.

Two things are not ready to ship, and they are in that README:
`treat-the-n-phy-dac-test` does not apply on the clean tree without
`sample-table-logic` before it (a context dependency, not a logical one), and
`fill-the-per-rate` carries a move of `b43_nphy_tx_pwr_ctrl_coef_setup()` that has
to be split off, because its reason is the capture and not a mainline defect.

The biggest is the **field** of the power index: turning off the power control
when it is on, b43 saves the seven low bits of the per-chain status instead of
bits 8..14, and the restore puts that field back into the index. It runs on every
N-PHY rev 3 and up, on every path that brackets work with the control off — the
calibrations and the channel change. On this capture the index is 25 and the
seven low bits are zero, i.e. the bottom of the table. The define of this same
driver, `B43_NPHY_TXPCTL_STAT_BIDX`, says so, and twenty lines below
`b43_nphy_get_tx_gains()` reads the same field right.

Transcription typos from brcmsmac and C precedence, not feature holes: the two
of the PAPD cal are `tbl_rf_control_override_rev7_over1` with two `val_mask`s that
do not cover their own shift's field, and `one_to_many` `TX_PU` with four calls out
of five (proved three ways: brcmsmac and the capture agree against b43). Then, in
order: `0005` wrong register, `0010` `<<` binding tighter than `&` plus a phase step
truncated in a `u16`, `0011` ten fields lost with the "2 GHz only" table, `0012`
tables initialised in the wrong place. It is always worth comparing the **gate**
besides the body: b43 had `phy->rev != 5` where brcmsmac has `radiorev != 5`
(`docs/todo-nphy.md` 3d bis).

Two more candidates are not in `patches/mainline/` yet: `nphy->txcal_bbmult`, read
and never written ("Things worth as much as a defect"), and `hang_avoid` covering
revs 3-4 where brcmsmac covers 3-5 ("What remains open").

## The radio init, closed

The blob's record is `{u16 address; u16 init; u8 do_init; u8 pad}`, six bytes, and
**39 entries of 412 have the flag**. b43 had inherited address and value (412 of
412 identical) and lost the column. The capture matches the flag exactly: 39 of
39, and the 4 extra registers come from other code. The 54-entry stub that hangs
the radio is **brcmsmac**'s `do_init` set, which is older.
`patches/b43/MESSAGES.md#0013`, not tried on hardware. See
`docs/gap-inventory.md` 4h.

## Two blobs, and which to use

`wlDSL-3580_EU.o_save` is wl 6.30.102.7 (DSL-3580L, where the capture comes
from), `wlD6220.o_save` is wl 7.14.89.14. All 33 **data** symbols of 2057 rev5-8
have identical sizes in the two, `regs_2057_rev8` is identical byte for byte.
Three functions differ, `wlc_phy_workarounds_nphy_gainctrl_2057_rev5/6/7`, and
`rev6` is the body the b43 stub lacks: for that one **6.30 is read**, which is the
capture's blob. The blob gives brcmsmac's real names: `a3` =
`wlc_phy_papd_cal_gctrl_nphy` (2444 bytes, 147 lines, the ratio adds up).
`wlc_phy_papd_cal_nphy` (6088) is `a2` **or** `a4`: they have 279 and 276 lines,
the size does not tell them apart, and `a2` cannot be found by size. See
`docs/blob-inventory.md`.

The same `wl 7.14.89.14` drives a second instance of this core on the TG789vac
v2, and the D6220's `wl0` attach under it is in `router-data/d6220/`
(`docs/ac-wip-xref.md`).

## Next step

1. **The values of the power indices**: b43 has `0x19` where the device writes
   `0xa` and `0xc`, and they are the two ops left in the stretches at #4958 and
   #6330. A question about what the save of the index keeps.
2. **The stretch at #10761**, 16 moved ops of 18, which is the biggest single site
   among the 56 moved that remain — the carrier search bracket, `0x2c`/`0x42`, the
   baseband reset and the two reads of the index. Then #9727 (6), #9008 (5),
   #3732 (4), #24823 (4): they are in a few sites, not spread out.
3. **The stretch at #25823**, 17 absent, which is the same snapshot as #877 plus
   the power indices, read at the end of `up-ch1` before the first hop of the ACI
   scan: it belongs to the ACI scan like #5004.
4. The PAPD cal still has **one** extra write of the power table, 2 against 1:
   the single bracket opens one where the device opens none, i.e. the opening
   falls inside the region instead of before it.
5. **Who calls the recalibration on channel change.** That the code can do it is
   measured on both captures, 91% on ch6 hot and 85% on ch11 cold; what is missing
   is the reference's watchdog, and without it on hardware b43 uses on the new
   channel the calibration of the old one.
6. The ACI scan, which is a policy above the PHY and not a function to hook.
7. **Bring the per-patch history into the published repository**, if it exists
   in a local clone (`patches/b43/SPLIT.md`): without it, splitting `0027`-`0036`
   is not a command.
