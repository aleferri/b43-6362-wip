# The places where b43 does not do what the vendor does

A working list, not a list of complaints: every entry has how it was found,
what is missing, and what it takes to close it. The entries already closed are
in `gap-inventory.md`; here is what remains open after the first six patches.

Measurements with `test/unit/coverage.py` against the capture's first init,
`init` flow on **channel 1**, i.e. the vendor's. The channel matters: with the
port on a different channel nine chantab registers come out "different" and
they are not.

## 1. The 32 PHY registers the vendor writes and the port does not

Grouped by the point of the capture where they appear, which is what
attributes them.

| registers | where in the capture | attribution |
|---|---|---|
| `0x1df, 0x1e1` = 0x1591 | #203-204, initial radio init | phase before the PHY init, to be looked at |
| ~~`0x1d7, 0x1d9, 0x1db, 0x1dd`~~ | #680-683 | **closed**: carrier sense thresholds, `patches/b43/MESSAGES.md#0008` |
| `0x020, 0x021, 0x2a7, 0x2a8, 0x2e6, 0xc33` | #5614-5625 | phase not identified |
| `0x07b, 0x07e` (12 times each) | #11769, #12819 | calibration region |
| `0x29f, 0x2a0-0x2a4, 0x2be, 0x2e5, 0x348, 0x349, 0x358` | #12194-12324 | calibration region |
| `0x09a-0x09d` (8 times) | #15095-15098 | calibration region |
| `0x129, 0x12a, 0x12b` (8-16 times) | #15863-15865 | calibration region |

28 registers of 32 remain, 22 of them between #11700 and #15900, which is where
the vendor does the PAPD and the TX IQ/LO calibrations. b43 does not have PAPD
at all and skips IQ/LO at init (`perical = 2`, "like wl"). So they are not 32
independent holes: they are two missing functions and six registers to
attribute.

## 2. The 14 radio registers

| registers | attribution |
|---|---|
| `0x43, 0x4a, 0x70, 0x73, 0x74, 0xa0, 0xf5, 0xf8, 0xf9, 0x125`, all to 0 at #145-161 | the 5 GHz fields of the dual-band chantab entry the vendor clears: it is entry 5b of `gap-inventory.md` |
| `0x17d, 0x17e, 0x19d, 0x19e` | the TSSI block, but **only during the cal**: read-modify-write at #11828-11837 with values that change across the six occurrences. They belong to the calibration, not to the setup |

## 3. Registers written by both with a different value

`coverage.py --values` compares the first value written to every register both
sides touch. It is needed because presence alone does not see this class of
difference — and that is how the TSSI came out. Sixteen entries, in three
groups.

### 3a. RSSI multiplication coefficients: `0x1a4-0x1b8` (11 registers)

    vendor   0x1a4 = 0x3e   0x1a6 = 0x02   0x1ac = 0x01   0x1b8 = 0x3f
    port     0x1a4 = 0x3f   0x1a6 = 0x00   0x1ac = 0x3e   0x1b8 = 0x3f

They are the `B43_NPHY_RSSIMC_*`, i.e. the RSSI calibration. Both sides write
them several times, the vendor in the sequence `0x3e, 0, 0x3e`. The port's
values diverge on at least four registers.

To be read together with the entry of `docs/phy-g-only.md` on
`b43_rssi_postprocess`, which has branches for G and LP and not for N: the RSSI
chain has two independent problems, the coefficients programmed and the
conversion of what is read. It is the number that ends up in
`ieee80211_rx_status.signal`.

**Update from the positional comparison** (`rssi-cal` window), which says more
than the set measurement and corrects the description above:

- the registers are **the same**: the port writes 24 ops of them in the whole
  run, the vendor 12 in its window, and the set coincides;
- the **order** is not. The vendor writes them in a contiguous block — `0x1b8`,
  then `0x1a4, 0x1aa, 0x1b0, 0x1b6` (the X on the four rails), then
  `0x1a5, 0x1ab, …` (the Y) — while the port writes two and then goes to read
  `0xa6, 0xa7, 0xf9`, i.e. interleaves reads and writes per rail;
- the **values are not comparable** in the harness: they come from
  `b43_nphy_restore_rssi_cal()`, which puts back the cache produced by the RSSI
  calibration, and the cal with no hardware to measure produces zeros. The same
  holds for `R2057_NB_MASTER_CORE0/1` (radio `0x0b4`/`0x139`): the port writes
  there what it has in cache.

So the entry stays open but changes shape: not "wrong coefficients", but a
different order and values not verifiable from here. Closing it needs either a
capture with the vendor's RSSI cal isolated, or the hardware. (`4bis` and
`test/unit/README.md` say how far the read plans got since.)

### 3b. Target power: `0x1ea` = `B43_NPHY_TXPCTL_TPWR`

    vendor   0x3e3e   (62 in Q5.2 = 15.5 dBm)
    port     0x4a4a   (74 in Q5.2 = 18.5 dBm)

The port programs the SROM's `maxpwr_2g` as it is; the vendor puts 3 dB less.
A round three dB looks like a limit — regulatory for the channel, or the
antenna gain, or one of the SROM's per-rate offsets — that b43 does not
subtract in the ppr path, or that the harness does not know because it lacks
the board's regulatory context. To be closed by reading which of the two, not
by guessing: it is output power.

A note on method: before `core_pwr_info` was decoded from the SROM the port
wrote 0x0000 here, and it looked like a driver hole. It was the harness's
incomplete SPROM.

### 3c. `0x340, 0x341` = `B43_NPHY_REV7_RF_CTL_MISC_REG3/4`

    vendor   0x400, 0x400, 0x400, 0x0002, 0x4000
    port     0x000, 0x000, 0x000, 0x0000, 0x0004

Different sequences on both. Not attributed.

### 3d. TSSIG: `0x17b, 0x19b` = `R2057_TX0_TSSIG` / `R2057_TX1_TSSIG`

This is the TSSI, and it is the clearest entry of the group.
`b43_nphy_ipa_internal_tssi_setup()` for revs 7+ does, per core:

    if (phy->rev != 5) write(r + 0xA, 0);
    if (phy->rev != 7) write(r + 0xB, 1); else write(r + 0xB, 0x31);

In the capture, in the corresponding phase (#1259-1265) the vendor writes
`0x175, 0x176, 0x177, 0x178, 0x179, 0x17a, 0x17c` with the same values as the
port, and **does not touch `0x17b` at all**. It writes it later, at #8537, with
`0x31`, in a different phase: preceded by reads of the same registers and with
other values (`0x175 = 0x06`, `0x176 = 0x43`, `0x177 = 0x55`), i.e. the
save-reconfigure typical of the TX calibration.

So the `phy->rev != 7 ? 1 : 0x31` branch seems to mix the two phases: it puts
the cal's value into the setup for rev 7, and for the other revs it writes 1
where the vendor leaves things alone.

**The value is known without hardware.** The capture contains the write of the
radio init table, `#104: 0x17b = 0x02` and `#105: 0x19b = 0x02`, one core per
line; and the four reads of `0x17b` in the two inits (#1256, #8528, #23907,
#35958) all return **`0x02`**. So the value the vendor has on that register
during the setup is `0x02`, it gets there from the init table, and does not
depend on the chip's reset value. `0x31` is the TX cal's value: written at
#8537, put back to `0x02` at #10743.

And b43's `r2057_rev8_init` already has `0x17b = 0x02` and `0x19b = 0x02`,
identical. So the TSSI setup **overwrites** with 1 a value b43 itself had just
programmed right.

The vendor's two drivers disagree with each other: `0x02` in the captured
6.30.102.7 blob, `0x01` in brcmsmac at `brcmsmac/phy/phy_n.c:17077`, which
writes `TSSIG = 0x1` for every phy rev other than 7 and so for ours too.
**Between the two the blob wins**: `wl 6.30` is far ahead of brcmsmac, which is
stuck at 5.100.x, and for this radio it is the driver that runs on the hardware
the capture comes from. The right value is `0x02`, i.e. what the init table
already sets: the defect is writing `1` in the setup, which has to go for rev 8.

It is not a patch yet because the power measurement goes through that register,
and the patch has to come with the corresponding measurement
(`docs/reports/40-tx-power.md`), like `0001` and `0002`. But the value is no
longer in question.

### 3d bis. And a transcription typo, on the next line

Looking at that branch something else came out. brcmsmac gates the two
registers on different things:

    if (pi->pubpi.radiorev != 5)      -> TSSIA
    if (!NREV_IS(pi->pubpi.phy_rev,7)) -> TSSIG

b43 transcribed **both** as `phy->rev`:

    if (phy->rev != 5)  b43_radio_write(dev, r + 0xA, 0);   /* radiorev in brcmsmac */
    if (phy->rev != 7)  b43_radio_write(dev, r + 0xB, 1);   /* this one matches */

Radio 2057 exists from phy rev 7 up, so `phy->rev != 5` is **always true** in
that branch and b43 always writes TSSIA, where brcmsmac skips it on radio rev 5
— and a channel table for radio rev 5 does exist in this tree
(`b43_nphy_chantab_phy_rev8_radio_rev5`). On our rev 8 the two forms of the gate
give the same result, so it explains no divergence of the capture and cannot be
patched with what we have here. It stays written here because it is a real
defect and whoever comes with a 2057 rev 5 starts from here. It is now the
mainline patch `b43-test-the-radio-rev-for-the-n-phy-tssia-setup`.

**It does not come from the merged series**, checked and not hoped: none of the
seven patches of `docs/upstream-status.md` touches `phy_n.c` — the files are
`main.c`, `radio_2057.c` and `tables_nphy.c`. The typo is older, from the rev 7+
code written for the 43217/43227/43228.

## 3f. `0x7b` and `0x7e`: just marked

`B43_NPHY_RFCTL_RXG1` and `RXG2`. The rev7 RF override table already has the
entry for the `0x0800` field that drives them, but no driver path passes that
field; the vendor writes them 12 times each during the calibration. There is
nothing to add without knowing in which phase and with which values, so
`patches/b43/MESSAGES.md#0007` puts a TODO line next to the dead entry and moves
on.

## 3g. The vcocal was not missing

In the channel change window the positional comparison reported eight missing
ops on `0x2b` and `0x2e`, i.e. `RFPLL_MISC_EN` and `RFPLL_MISC_CAL_RESETN`: the
VCO calibration at the end of `b43_radio_2057_setup()`. b43 does it, and does it
the same way.

The difference was in the rendering: the vendor's tracer hooks both
`mod_radio_reg` and the read and the write it calls, so a single RMW shows up as
three ops, while b43 with `b43_radio_mask`/`b43_radio_set` produces one. Dropping
the two shadows — only when they immediately follow a `MOD` on the same address
— the four vcocal ops match and the missing ones of that window go down to
**exactly 10**, the 5 GHz fields of entry 5b.

It is worth noting what would have happened without: eight ops attributed to a
nonexistent hole, and entry 5b inflated from 10 to 18.

## 3e. A note on method: the positional comparison comes first

Entries 3a-3d came out of `coverage.py --values`, which compares sets and first
values. It is the weak measure. The strong one is `test/unit/phase_compare.py`,
which diffs op by op inside an aligned window.

Applied to the TSSI it says something precise: it is not "a different value on
`0x17b`", it is **one op too many**. The port writes `0x17b = 1` between `0x17a`
and `0x176`, where the vendor in that phase goes straight to `0x176`, and from
there on the two sequences are one out of step. In the same way the channel
change matches for 11 ops and then the vendor writes the 5 GHz fields
**interleaved**, not at the end: if entry 5b is closed, they go in those
positions. That is what `0011` does.

## 5. The formulas: what is really missing for rev 8

Mainline's `phy_n.c` has 48 `/* TODO` at `848acc8ffe1b` (this file used to say
25; recounted with `grep -c '/\* TODO'`), but that count misleads: most of them
are in `phy->rev >= 19` branches, i.e. PHYs that do not concern us. **SALAME**:
the "most" is the old count's reading, not redone on the 48. For
rev 8 this is the situation.

**Present and working**: the RSSI calibration (`b43_nphy_rev3_rssi_cal`, which
rev 8 uses because the dispatch is `rev >= 3`), TX IQ/LO
(`b43_nphy_cal_tx_iq_lo` with the rev 7 branch and the `R2057_TX*_LOFT_*`
registers), the save/restore of the calibrations. They are not stubs: they run.

**Missing entirely in mainline**: the **PAPD calibration**. Mainline b43 has no
function that does it — it turns the engine on (`PAPD_EN0`/`EN1`); the series
initialises its tables (`patches/b43/MESSAGES.md#0004`) and computes the
epsilon offset (`0009`), but never computes the epsilons. In brcmsmac the block
is:

| function | lines | what it does |
|---|---|---|
| `wlc_phy_a2_nphy` | 279 | computes and **writes** the epsilon table, per gain step |
| `wlc_phy_a4` | 276 | the top level: setup, a3 and a2 per core, restore |
| `wlc_phy_papd_cal_setup_nphy` | 250 | RF overrides, AFE, TXRXCOUPLE, tone |
| `wlc_phy_a3_nphy` | 147 | the gain index search: **reads** the epsilon table |
| `wlc_phy_papd_cal_cleanup_nphy` | 124 | the restore of that setup |
| `wlc_phy_ipa_restore_tx_digi_filts_nphy` | 41 | the cal's digital filter |
| `wlc_phy_txpwr_papd_cal_nphy` | 13 | the "gain has drifted by 4" gate |
| `wlc_phy_ipa_set_bbmult_nphy` | 6 | writes the bbmult |

About **1150 lines**. Careful with `wlc_phy_ipa_set_bbmult_nphy`: it has six,
not 722 — that number came from `cfuncs.py` before it recognised the signatures
kernel style wraps, and the same holds for any count made with that version.

It is also the explanation of the 22 unattributed PHY registers between #11700
and #15900: they are not 22 independent holes, they are that missing block.
`papd-cal-map.md` says how much of it the series has ported since.

## 4bis. The RSSI cal: the plans work, the sampling does not

Update on 3a, measured and no longer hypothesised.

The read plans **are consumed**: 22 values of 27 for each of `0xa6`, `0xa7`,
`0xf9`, `0xfb`, which are the registers `b43_nphy_poll_rssi()` reads. (The
earlier round where they "moved nothing" was a stale binary: a lesson of its
own, `make` before measuring.)

With the plans on, the coefficients the port writes are `0x3f` where the vendor
puts `0x3e`: **one LSB**. So the formula is right; what differs is the sampling.
The exact count: the port does **22** reads per register where the vendor does
**27** per init. The plan is a FIFO per address, so with 5 polls fewer the port
consumes the values of the wrong rounds and the average comes out one off.

What is NOT the cause: the number of VCM levels. b43 loops `vcm < 8` and
brcmsmac has `vcm_level_max = 8`, identical.

### 4ter. Where the five extra reads are, and why knowing it is not enough

Counted. In the first init the vendor reads `0xa6` **27 times**, and they are not
27 polls: 21 inside the RSSI cal plus six scattered ones, each from a different
phase.

| record | phase |
|---|---|
| #1668 | the idle TSSI poll (`poll_rssi` with one sample) |
| #8563 | the TX IQ/LO cal |
| #11812 | `papd_cal_setup` core 0, the save of the AFE |
| #12930 | `papd_cal_setup` core 1 |
| #14991 | the unattributed region #14093-15920 |
| #22255 | the save of the ~20 registers at the head of the RSSI cal (#22247-22289) |
| #22381-#23761 | the 20 polls of the vcm loop, one every 72 records |
| #24319 | one after the cal |

The read plan is a **FIFO per address over the whole capture**. The port does 22
reads of `0xa6`, so it consumes the first 22 entries — and among those are
`#11812`, `#12930` and `#14991`, i.e. three phases the port **does not run**.
Three of its polls read values that belong to the PAPD cal and to the
unattributed region.

It looked like the cause. It is not, or not all of it: a `--skip` was added to
`gen_readplans.py` to exclude from the plan the intervals of the phases the port
does not do, and tried twice — excluding #10962-15920, then the TX IQ/LO cal at
#8500-8600 too, to make the count of reads before the cal match. In both cases
the coefficient **gets worse**: from `0x3f` to `0x0000`, where the vendor writes
`0x3f` on `0x1b8` and `0x3e` on the other eight. Aligning the FIFO is not enough.

Why it is not enough is visible in the port's trace: inside a poll the port
reads `0xa6 0xa7 0xf9 0xfb 0x8f 0xa5 0xe5 0xe6`, the vendor at the head of the
cal reads `0x91 0x92 0x8f 0xa5 0xa6 0xa7 0xe7 ...`. It is not only the **how
many** that differs, it is the **which and in what order**: a FIFO per address
does not align by moving the ends of an interval, and closing this entry needs
pairing the polls, not the reads.

`--skip` stays in the tool because it is correct and useful anyway (the plan has
to match the flow: `init` does not do the TX IQ/LO cal, `initcal` does), but
`readplans_init.h` was not regenerated: with the skip the `init` flow is worse,
and a plan that worsens the result is not committed just because it is more
"right" in theory.

(Since then the plans carry their record and the cursor is per address, and
the last LSB turned out to be a mainline rounding defect:
`test/unit/README.md`, "Positional plans".)

## 4. How to redo the measurements

```sh
cd test/unit
./nphy_trace init dsl3580l 1 > /tmp/port.out          # channel 1, like the vendor
./coverage.py ../../router-data/dsl3580l/opinit-ch1-ch6-bw20.decoded \
    /tmp/port.out --range 132 26100 --values
```

Two traps fallen into, so as not to fall into them again:

- **a different channel** between port and capture: nine chantab registers come
  out as differences and are not;
- **incomplete SPROM** in the harness: the fields not decoded become zeros, and
  the zeros look like driver holes. If a difference concerns power, look at
  `main.c` before the driver.

## 6. The first 84 ops: no spur avoidance, and no measurements

`PMU.SPUR` appears **zero** times in both captures, the hot one and the cold
one. Spur avoidance is not here and not elsewhere in what we have:
`si_pmu_spuravoid` is among the hooked symbols, so if the vendor called it we
would see it. The absence is data.

And they are not measurements, although there are reads. Two patterns, neither
of which queries the hardware:

**The `SI.COREREG`s are the read half of a read-modify-write.** The value they
return is the one just written — `#10` reads `0x64` and returns `0x400`, which is
what `#9` wrote with `GPIO.OUT`; `#14` reads `0x68` and returns `0x407`, written
by `#13` with `GPIO.OE`. `si_gpioout` and `si_gpioouten` are mask/set helpers,
and the tracer sees the read because it hooks the accessor.

**The `OBJ`s are a write-then-verify of the SHM.** `#46-#49` write four words
(`0x98`, `0x9a`, `0x9c`, `0x9e`), `#50-#57` read the same four back and get
identical values. Consistent with the ratio of 17 writes to 5 reads: if they
were measurements it would be the other way round.

The real measurements in the capture all come later, and they are recognised
because the value read **is not predictable** from the one written: the idle
TSSI poll, the 20 polls of the RSSI cal's vcm loop, the 40 rereads per gain step
of the PAPD cal, `rcal`/`rccal`. It is the same distinction the harness rests
on — where the value is predictable the mirror is enough, where it is not the
read plans are needed.

### To be checked: the AFE sequence is doubled

`PHY.ARRW` plus the four AFE writes (`0xa6 0x8f 0xa7 0xa5`) appear twice, at
**#20-#24** and at **#27-#31**, with the same values. In between there are only
`MAC.MHF 0x0000` and `MAC.MCTRL`.

b43 calls `switch_analog(true)` once from `b43_phy_init()`, and the harness emits
one. If the vendor does it twice there is a step we do not have — the suspicion
is a `radio_on` that goes and comes back, or a second round of the rfkill path —
but it is not verified. They are not measurements in any case: they are the
same four writes, so the question is what happens **between** the two, not what
they read.

The D6220's `wl0` attach under 7.14 has the same pattern: two blocks of AFE
overrides on `0x0a6`/`0x08f`/`0x0a7`/`0x0a5`, each after clearing bit 10 of
`0x078`, with host flags in between (`router-data/d6220/README.md`). There the
two blocks write different values (`0x000d`/`0x0000`, then `0x00fd`/`0x07ff`).
