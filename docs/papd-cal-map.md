# The PAPD calibration: map of the capture

Mainline b43 does not have this calibration. Before writing it one needs to
know how it is made, and the capture says so. This is the map of the phases,
with the record ranges, what each does and the corresponding brcmsmac function.
What the series has ported since is in "Work order" and the sections after it.

The calibration is **`wlc_phy_a4()`** (`brcm80211/brcmsmac/phy/phy_n.c:25108`),
and it runs **once per init**: the marker of its entry is the write of the
scalar table, and in the 70796-record capture `TBL.WR id=0x20 off=0 len=64`
appears exactly twice, #10966 and #45690, one per init. Inside, for each core,
it calls `wlc_phy_papd_cal_setup_nphy()`, then `wlc_phy_a3_nphy()` — the gain
index search, which is the loop driven by the reads — then
`wlc_phy_papd_cal_cleanup_nphy()`.

Region of the first init: **#10962 - #14092**, ~3100 records.

## The phases

| records | what | where it is in brcmsmac |
|---|---|---|
| #10962-10965 | entry: `0x1e7` and, workaround array, `0x8f`/`0xa5` or | `wlc_phy_a4`, stay-in-carriersearch and txpwrctrl off |
| #10966-11225 | scalar table on 32 and 34, 64 values per core | `wlc_phy_a4`, already ported by `patches/b43/MESSAGES.md#0004` |
| #11226-11228 | RD `0x01`, MOD `0x01` bit 15 | `wlc_phy_a4`, save of the spur |
| #11229-11484 | epsilon core 0 (table 31): **64 single writes** of zero | same, already in `0004` |
| #11485-11740 | epsilon core 1 (table 33), same shape | same, already in `0004` |
| #11741-11755 | `0x186`-`0x194`: the **coefficients of the TX digital filter**, row 3 | `wlc_phy_ipa_restore_tx_digi_filts_nphy` |
| #11756-11837 | RF overrides, save/mod of AFE `0xa6 0x8f 0xa7 0xa5`, the radio's `TXRXCOUPLE_2G` | `wlc_phy_papd_cal_setup_nphy`, core 0 |
| #11838-12159 | `TBL.WR id=0x11` (SAMPLEPLAY), 160 words: the tone, 4000 kHz amplitude 181 | `wlc_phy_tx_tone_nphy` called by `papd_cal_setup` |
| #12160-~12788 | **core 0 loop**: for each gain step, set, play the samples, read back 40+ times, compute, write epsilon | `wlc_phy_a3_nphy` then `wlc_phy_a2_nphy` |
| #12789-12791 | restore of `0x17d`/`0x19d` to `0xaa` | `wlc_phy_papd_cal_cleanup_nphy`, core 0 |
| ~#12800-13273 | core 1 setup: same sequence with the core swapped, tone at #12952 | `wlc_phy_papd_cal_setup_nphy`, core 1 |
| #13274-~13756 | **core 1 loop**, same shape | same |
| #13757-13759 | restore, core 1 | `wlc_phy_papd_cal_cleanup_nphy` |
| #13842-13857 | **epsilon offset**: `0x298`/`0x29c` = `0xf400`, then `0x297`/`0x29b` and `0x2a3`/`0x2a4` | tail of `wlc_phy_a4` |
| #13858 | `0x01` written back with the saved value | same |
| #13859-13918 | TX digital filters put back to the init's | `wlc_phy_ipa_set_tx_digi_filts_nphy` |
| #13921-14092 | tables 26/27 rewritten with updated gain and power | `wlc_phy_txpwr_index_nphy` |

### One setup op not explained

`RAD.RD 0x81` at **#11820** and **#12934** in the first init, #46544 and #48182
in the second: four reads in 70796 records, all inside `papd_cal_setup`, one per
core, always **between the four AFE reads and the four mods on the same four**.
The register is `TR2G_CONFIG1_CORE0_NU`, the same address for both cores,
written **once per init** (#83, `val=0x1`) in the radio init block and never
again; the reads return `0x1`. brcmsmac does not touch it, and in both drivers
it exists only as a define.

A generic flush is **ruled out**: a barrier would show everywhere, not four
times. What remains is a flag the init plants in a free register and reads
back, or a barrier right at that point — the last read before the first writes
to the same four registers. **SALAME** on both: the capture does not tell them
apart. The blob would, by looking at whether the return ends up in a store or in
a branch. It is not in the driver: a read whose value we do not know to be
needed does not go into mainline.

Core 0 and core 1 are told apart without ambiguity: `papd_cal_setup` writes
`TXRXCOUPLE_2G_PWRUP`/`ATTEN` as `0xc`/`0xf0` on the core under calibration and
as `0x0`/`0xff` on the other, so #11834-11837 (`0x17e`/`0x17d` on) is core 0 and
#12948-12951 (`0x19e`/`0x19d` on) is core 1.

The boundaries with a tilde are those between the end of `a3_nphy` and the
start of the cleanup: the two have no op that separates them uniquely, and
finding one was not needed.

## What is NOT the cal

**#14093-15920 is not a second round of `wlc_phy_a4`.** It starts again with the
same prologue (`0x1e7`, array, `0x8f`/`0xa5`), but the scalar table is not there,
and `a4` always writes it. That region reads table 15 (IQLOCAL) 13 times and
writes it 7, touches 26 and 27, and plays a tone at **2000 kHz amplitude 181**
(#15508, a period of 10 samples). This file used to call it unattributed:
`rxiq-cal-map.md` has since placed it, the tail of the PAPD cal's
`wlc_phy_txpwr_index_nphy` up to #14965 and the entry of the RX IQ cal from
#14966.

## An extra write that changes nothing

The blob writes `0x195`-`0x1a3` with row 1 **twice**: the first in the round
over the three types, the second right after `0x2c5`-`0x2d3`. The 15 values of
the second are **identical** to the first, so the state of the table is the same
and the difference with the port is only in the number of ops. It does so at two
independent points of the capture, #334-348 at init and #13904-13918 at the end
of the cal, so it is not a capture artefact.

b43 has the same rewrite, gated on phy rev 17 (`phy_n.c:4938`, with the comment
"Verified with BCM43131 and BCM43217"), where it is just as idempotent. On rev 8
it is not needed and is not to be added: the `txdigi-filts` window reports it as
a known divergence, not as a hole.

## What this map says

**The first three phases are already done.** Scalar and epsilon are
`patches/b43/MESSAGES.md#0004`. It is no coincidence: they were the part without
mathematics, i.e. the only one that could be ported by looking at the values
alone.

**The heart is `a3_nphy` and `a2_nphy`, and they are two different things.**
Between #12160 and #13756, per core, the driver alternates "set the gain, play
the samples, read back 40 times, compute, write the epsilon". The work is split:
`wlc_phy_a3_nphy` (147 lines) is the gain index search and **reads** the epsilon
table in a 20-step loop; `wlc_phy_a2_nphy` (279 lines), called right after for
the same core, **writes** the epsilon table through `set_bbmult`. `a2` was not
even named here, and not out of distraction: `cfuncs.py` did not see it, so it
appeared neither in the xref nor in the counts (see `docs/todo-nphy.md`
point 5).

The decisions depend on what it measures, so the code is not verified by
comparing writes: it is verified only if the reads reach it right. The capture's
read plans serve exactly that, and it is why they exist.

**`0x186`-`0x194` is not the tone.** They are `B43_NPHY_TXF_20CO_S*`, the
coefficients of the 20 MHz TX digital filter, and the 15 values captured are
row 3 of `tbl_tx_filter_coef_rev4` (`tables_nphy.c:3126`), the same as
`NPHY_IPA_REV4_txdigi_filtcoeffs[3]` in brcmsmac. The cal sets them for its own
duration (`restore_tx_digi_filts`, #11741) and puts them back as at init when it
ends (`set_tx_digi_filts`, #13859). For one session they were taken for the tone
and the first point of the work order rested on that; the wrong anchor in
`phase_compare.py` (`val=0x100`, which does not exist in the capture) was the
consequence.

**The real tone is table 17**, and b43 already has `b43_nphy_tx_tone()` and
`b43_nphy_run_samples()`. That piece however was broken: see below.

## Work order

Points 1 and 2 are **done**, `patches/b43/MESSAGES.md#0015`, and they came out
together because neither stands on its own: a setup without a cleanup leaves the
RF overrides, the AFE ones and the coupler on, and the cal's filter outside the
cal is worse than not touching it.

1. ~~the setup of `papd_cal_setup`~~ — plus the **cleanup**, which the plan did
   not name, plus the pieces of `wlc_phy_a4` around them: the RX reset saved and
   cleared between the scalar and the epsilon tables and rewritten at the end,
   the bbmult saved before the loop, bit 13 of `PAPD_CAL_SHIFTS0/1` turned off
   again afterwards.
2. ~~`restore`/`set` of the digital filters~~ — `papd-digifilt` window **15/15**.
3. **a single step of the core 0 loop**. The read plans no longer need to be
   "on" but **in order**: see below.
4. **the mathematics of `a3_nphy` and `a2_nphy`**, and it is last because it is
   the only part that cannot be verified in pieces.

(`patches/b43/NOTES.md` has what came after this list: the measurement of the
tone and the gain search, the epsilon smoothing added and then removed for
having no source, and the engine turned on at the end of the cal.)

### The epsilon tables are written cell by cell

It is not a fidelity quirk: `0015` changed the 64-cell bulk into two loops of 64
single writes, like brcmsmac and like the vendor. It costs 64 table address
setups instead of one, and in exchange the bulk relied on the auto-increment of
the address, which nobody has tested here. The `papd-tables` window went from
**260/774 to 513/774**, and what remains is a single op: the value the `PHY.RD`
of `0x01` returns.

## What is already ported, after reading the map

### The epsilon offset

Reading the tail of `wlc_phy_a4` a **complete and verifiable** piece came out
that does not need the calibration.

b43 writes `nphy->papd_epsilon_offset[]` into the EPS table adjust registers
(`0x298`/`0x29c`) inside the IPA branch of `b43_phy_initn`, but never computes
it: it writes zero. brcmsmac computes it at the end of the cal:

    offset = -60 + 27 + eps_offset - (padgain_delta[pad_gain] + 1) / 2

with `eps_offset = -1` on this radio at 2.4 GHz. The value captured is `0xf400`
with mask `0xff80` (#13842 and #13847 at the end of the cal, and the same value
at init in #286 and #288), i.e. **-24** in the signed 9-bit field, from which
`delta[i] = -21`, which in the table of rev7 values is **index 15**.

`patches/b43/MESSAGES.md#0009` evaluates the formula — `0002` already has the
table — with the index as a constant taken from the capture. The port now
writes `0xf400`, identical to the vendor, where before it wrote `0`: 24 dB of
difference on the predistortion. When the gain search arrives (point 3 above),
the index comes from it and the constant goes.

### The sample table

The tone is the stimulus of every cal that plays samples, and in b43 it was not
a tone. `b43_nphy_gen_load_samples()` computed the phase step as
`(((freq * 36) / bw) << 16) / 100` inside a `u16`, while `cordic_calc_iq()` wants
integer degrees and scales by itself: the `<< 16` is one too many and makes the
result a multiple of 65536 for **every** frequency the driver asks for (2500 and
5000 from the TX IQ/LO cal, 4000 from the idle TSSI and from the rev 2 RX IQ
cal), so the step truncated to zero and the 160 samples came out all equal. On
top of that `b43_nphy_load_samples()` wrote `samples[i].i & 0x3FF << 10`, where
`<<` binds tighter than `&`, throwing away the in-phase component.

`patches/b43/MESSAGES.md#0010` closes both. Against the capture, on the TX
IQ/LO cal's tone at 2500 kHz amplitude 250 (#8638):

| | wrong words of 160 |
|---|---|
| mainline | 160, all zero |
| only the mask fixed | 140, constant `0x3e800` |
| only the phase step fixed | 120, in-phase component lost |
| `0010` | **0** |

Neither half alone gets closer, and that is why it is one patch and not two.
The `sampleplay-tssi` and `sampleplay-iqlo` windows of `phase_compare.py` hold
the result: 322/322 both with the patch, 2/322 the second without.

## Against which capture it is verified, and with what tolerance

The cal is **not verified on `opinit-*`**: that one is a hot init, and only the
**cold capture**, `full-init-ch1-bw20.decoded`, contains the cal in full, in its
contiguous part `#2-32769`. Measured: 3499 reads paired out of 3499, and the
plans are generated with

```sh
./reverse-tools/gen_readplans.py router-data/dsl3580l/full-init-ch1-bw20.decoded \
    --range 2 32769 --name full --max-len 512 > test/unit/readplans_full.h
```

which gives **148 plans**. `--max-len 512` is not optional: with the default of
64 the plans of the addresses a cal reads back dozens of times get truncated and
the cal averages the mirror (see `test/unit/README.md`).

**Tolerance on the values that depend on rccal.** Between a full and a partial
init the rccal values change by a few units, and it has been seen on other
devices too: it is not a defect of the port or of the capture. So for the
quantities that follow from it the criterion is not bit-for-bit equality but
**magnitude**: a formula that produces the expected value **within +-2** is
probably the right formula, and is to be treated as such instead of being
chased. Exact equality stays the criterion for everything else — tables,
registers programmed from constants, coefficients that do not go through rccal.

In the cold capture the PAPD cal starts at **#18662** (the scalar table) and
its tones are at #19534 and #21806.

## The plan for `a2` and `a3`, with the names and the measured size

### The names

| brcmsmac | b43 | where the name comes from |
|---|---|---|
| `wlc_phy_a3_nphy` | `b43_nphy_papd_cal_gain_ctrl()` | from the blob: `wlc_phy_papd_cal_gctrl_nphy`. It is the gain index search, it **reads** the epsilon table in a 20-step loop |
| `wlc_phy_a2_nphy` | `b43_nphy_papd_cal_epsilon()` | **our name, not the vendor's**: the blob does not identify it (`blob-inventory.md`). It computes the epsilon and **writes** it through `set_bbmult`. The comment above the function has to say so, or in six months someone looks for it in brcmsmac and does not find it |
| `wlc_phy_a4` | `b43_nphy_papd_cal()` | the name `0012` already introduced: it stays the top level, the two above sit under it |

### How big, measured and not estimated

The two functions are 279 + 147 lines, and their dependency closure is
**fourteen distinct calls**:

| call | how many | b43 equivalent |
|---|---|---|
| `mod_phy_reg`, `write_phy_reg`, `read_phy_reg` | 38 | `b43_phy_maskset` / `b43_phy_write` / `b43_phy_read` |
| `wlc_phy_table_read_nphy`, `_write_nphy` | 4 | `b43_ntab_read_bulk`, `b43_ntab_write_bulk` |
| `wlc_phy_rfctrl_override_nphy`, `_rev7`, `_1tomany` | 9 | `b43_nphy_rf_ctl_override`, `_rev7`, `_one_to_many` — all three are there |
| `wlc_phy_get_tx_gain_nphy` | 1 | `b43_nphy_get_tx_gains` |
| `wlc_phy_ipa_set_bbmult_nphy` | 2 | **to be checked** |
| `wlc_phy_papd_decode_epsilon` | 2 | **to be checked** |
| `wlc_phy_a1_nphy` | 2 | **another obfuscated name, to be identified** |

So it is not an isolated block: it rests almost entirely on things b43 has. The
unknowns are **three functions**. An afternoon of work, and whoever picks it up
does not have to redo this count.

### The order, and why it is this one

The prerequisite has changed: it is not "separating the plans by capture", it
is **having the contiguous phase**. The plans are positional, so they serve the
value the hardware gave only if the port does the same reads in the same order
as the vendor; inside a contiguous region that condition is true by
construction, and then the values come back by themselves without positioning
anything per call.

Measured inside the only window, `up-ch1` (#132-26100): in the interval of the
cal the contiguous blocks are at **#10966 (847 ops)**, #11822 (334), #12784
(145), #12936 (334), #13752 (90), #13856 (48), #13921 (172). There are no
per-phase regions, and not by oversight: a phase taken alone says nothing about
what lands on it from before. The structure:

| from | contiguous ops | what |
|---|---|---|
| #10966 | 847 | scalar tables, RX reset, epsilon cell by cell, filters, bbmult, filter band, RF overrides |
| — | hole of 1 | `RAD.RD 0x81`, not explained |
| #11822 | 5 | AFE mods |
| — | hole of 3 | the **coupler attens**: see below |
| #11822 | 334 | AFE mods, coupler, the 160-word tone |
| — | **hole of 349** | `a3`/`a2`, core 0 |
| #12792 | 74 | the 17 overrides turned off by the cleanup |
| #12882 | 48 | tail of the cleanup, AFE and bbmult |
| #12936 | 334 | core 1, same shape |
| — | **hole of 276** | `a3`/`a2`, core 1 |
| #13760 | 74 | cleanup core 1 |
| #13856 | 48 | tail of `a4` |

So:

1. **The two big holes are `a3`/`a2`** and they are the real work. Everything
   else is contiguous, and inside that contiguous part the plans are in order.
2. ~~The 3 ops of the filter band~~ — **closed, and it was neither the capture
   nor the plans.** The harness mirrored only PHY, radio, MMIO and SHM: a table
   read goes through data port `0x73`, so the port got back the last cell
   written anywhere — the epsilons just cleared, i.e. 0 — instead of `7/0x154`.
   Both write that cell, and with the same value (`0x2c64`, #6996 in the cold
   capture). With `tbl_mirror` added to `wrap.c`, the first block went from
   **796 to 847 ops** and the total from 1812 to 1836. Before looking there it
   was blamed on the plans and then on the hot capture: **TONNO** both times.
3. **Then the code**, one cal step at a time, with the +-2 criterion on the
   values that go through rccal (section above), **against the
   `papd-cal-freddo` region**.

### The bbmult: it was a defect of the harness, not of the port

For one session this entry said that b43 never writes cell 87 of table 15 and
that the cleanup therefore restores a zero. **TONNO**: the port writes `0x2c2c`
there, the same value as the vendor, four times before the cal.

The hole was in the table mirror, added wrong: it served the cell to the return
value of `b43_ntab_read` but **not at the data port**, and in the trace the line
compared is the `PHY.RD` of `0x73`, which kept giving the register's mirror. So
the driver read the right thing and the measurement said no. Fixed with
`tbl_port_get()` in `wrap.c`: `0x73` and `0x74` serve the cell addressed by the
last write to `0x72`, which carries `(id << 10) | off` for every width.

The lesson, and it is the second time in this phase: **when a read does not add
up, look at the harness before the driver**. The two times before, the read
plans and the wrong capture were blamed.

### The coupler attens: only the capture knows them

Two value holes remain, `RAD.RD 0x17d` and `0x19d`: the vendor reads `0xaa`, the
port `0`. Those two registers **are not in `r2057_rev8_init`** and neither driver
writes them: `0xaa` is the chip's default, and the only place it exists is the
capture. The plan has it, `{0xaa, 0xaa, 0xaa}` at records 11828, 12946, 15083.

**Closed by the seeds, not by the plans.** `reverse-tools/gen_seed.py` seeds the
addresses whose first access in the capture is a read, i.e. the chip's
defaults, and `0x17d`/`0x19d` at `0xaa` are exactly that. The criterion is not
"never written": the cal writes them, but after reading them.

The `B43_TEST_PLAN_FROM` knob stays, off: positioning the cursor at the entry of
a region **measured worse** (1830 → 1816, first block 847 → 843), because the
plans served values where the mirror was right. The open question is which read
shifts the plan, not whether to position the cursor.

### The same phase in two independent captures

`papd-cal-freddo` (#18662-24096 of `full-init-ch1-bw20.decoded`) gives **3727
vendor ops and the same 1830 in blocks, 49%**, with the same first block of 847.
The denominator is bigger because that one is a full cal: the two holes of
`a3`/`a2` are **920 and 930** ops instead of 349 and 276.

Two reasons why that is the capture to verify `a2`/`a3` on:

- **the tail of the cleanup matches for longer**, 82 ops against 48, because the
  values it restores are those a full init leaves behind;
- the structure of the blocks is **the same** in two captures that have nothing
  in common but the driver: it is the strongest confirmation that the shell is
  right, stronger than any percentage on a single capture.

### The check rule

Before believing any number of this phase, the tree measured has to be the one
believed. Today that means `KDIR` is the clean pinned tree
(`git -C ~/src/pin status` empty) and the harness builds from `b43/`.

When the series was applied to the tree, the check was
`git -C ~/src/linux diff --numstat`: with `0001..0014` and the mainline patch on
the RSSI cal it had to say **213 insertions and 13 deletions** on `phy_n.c`, and
`--global-run 132 26100` on the `init` flow **5953 ops of 22951, 26%, 721
blocks**; with `0015` and the two mainline patches on the RF overrides as well,
**249+/7-** on `phy_n.c`, **2+/2-** on `tables_nphy.c`, and `--global-run` at
**7075 of 22951, 31%**. Those are the numbers of that state, not of today's
`b43/`.

If it does not add up, the tree is bare and every measurement of the cal is
noise: it is trap 1, and one falls into it again.

## Why the rest is not ported in pieces

The heart is `a3_nphy` plus `a2_nphy` for two cores, and it does not break into
parts that can be verified individually: either there is the complete cal step
or nothing is verified. And `papd_cal_setup`, which is point 1 of the list
because it is all writes, is 250 lines — verifiable does not mean small, and as
long as the gain search is not there it has no caller, so as a patch of its own
it would be dead code.

The epsilon offset and the sample table on the other hand were isolated
computations with captured values to compare against, and that is why they
closed.
