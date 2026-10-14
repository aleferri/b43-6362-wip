# The init flow, the two sides side by side

It answers a question that keeps coming back: *when does what happen, and on
which side*. The columns are measured, not reconstructed from memory:

- **port**: line number in the output of `./nphy_trace init dsl3580l 1`. **The
  numbers in this column have to be regenerated**: they come from the
  13223-op trace of the harness that always modelled the cold init (see below),
  not from the current one, which with the series `0001..0013` does 5079 ops;
- **capture**: record number in `opinit-ch1-ch6-bw20.decoded`, first init;
- **brcmsmac**: the function, found with `reverse-tools/cfuncs.py`.

## First thing to know: where the two diverge, and where they do not

The README says the two order the phases differently, "the port starts from the
tables, the vendor from the radio". That is only half true, and the missing
half alone explained most of the misalignment.

**b43 and brcmsmac have the same distinction between cold and hot init.**
b43's `dev->phy.do_full_init` is brcmsmac's `pi->phy_init_por`, same semantics:
true at attach (`main.c:5407`) and after `b43_phy_exit()`, cleared by
`b43_phy_init()` as soon as `ops->init()` has succeeded (`phy_common.c:105`).
Behind that flag sit, in b43, the download of the static tables (four sites in
`tables_nphy.c`, with the `/* Static tables */` and `/* Volatile tables */`
comments already written) and `b43_radio_2057_rcal`/`rccal` (`phy_n.c:1026`). In
brcmsmac there is `wlc_phy_static_table_download_nphy` (`phy_n.c:14178`), called
behind the `phy_init_por` of `wlc_phy_tbl_init_nphy` (`phy_n.c:14206`), and the
same rcals. (Line numbers of the pinned tree.)

**The capture is not a cold init.** `PHY.WR addr=0x72 val=0x2800`, the opening
of table 10 with which the static download starts, appears in neither of the two
inits of the 70796 records — zero occurrences here, two in `full-init-ch1-bw20`.
That marker tells them apart, **not the number of table openings**: they are 950
and 953 in the two hot inits and 935 in the contiguous part of the cold init,
because the static download opens little and writes in bulk. It shows in the
writes, not in the openings: 47566 `PHY.WR` in the cold capture against 38616
here. When the tracer started, the vendor's driver had already done its cold
init.

**The harness on the other hand always modelled it cold**, with
`do_full_init = true` hard-coded in `main.c`. Hence 8320 ops of prefix that are
not in the capture and cannot be. Now the `init` flow does two inits: the first
cold and untraced, the second with the flag cleared, and the second is the one
compared. The `initpor` flow does only the cold one, for whoever wants to look
at it.

| | before | now |
|---|---|---|
| ops of the `init` flow | 13223 | **4903** |
| RSSI coefficients | `0x3f` on all nine | `0x3f` and eight `0x3e`, **like the vendor** |
| `rssi-cal` window | 1/16 | **11/16**, and the 3 left are reads of the data port |

The last row is the unexpected gift: the RSSI cal was one LSB off because the
read plans were also consumed by the reads only the cold init does
(`rcal`/`rccal`). Modelling the right flow aligned the plans without touching
them — which is what `todo-nphy.md` 4ter said was needed, and what `--skip` had
not achieved.

## What remains between the port and full alignment

With the prefix gone, the global comparison is no longer a shuffle: the long
runs all have the **same offset**, i.e. they are the same sequence with some
blocks inserted. The blocks are three.

### The first block was not the core's: it was two empty stubs of ours

The vendor's first ~84 ops — AFE `0xa6 0x8f 0xa7 0xa5`, the radio init table,
the first channel change — are all in code **already built**, and the harness
did not call it.

`b43_phy_init()` (`phy_common.c:83`) does, in this order:

    ops->switch_analog(dev, true);
    b43_software_rfkill(dev, false);      <- and from here the radio init
    ops->init(dev);
    phy->do_full_init = false;
    b43_switch_channel(dev, phy->channel);

The harness called only `ops->init()`. And the two `b43_*` in the middle, which
`wrap.c` has to provide because they live in the core, were lying stubs:
`b43_software_rfkill()` was **empty**, and `b43_switch_channel()` printed
`CHANSPEC` and returned 0 without calling the op. The first is the one that
matters: through it go `b43_nphy_op_software_rfkill()` →
`b43_radio_2057_init()` → the radio init table. And `setup()` set
`radio_on = true`, so even calling it the radio would not have been initialised:
on hardware one always gets there with `radio_on` false, because
`b43_phy_exit()` does `software_rfkill(true)`.

Fixed, the trace now opens with the same four AFE writes as the capture (#6-#9)
and contains the radio init table.

### The three blocks that remain

| where | ops | whose | what |
|---|---|---|---|
| radio init | ~300 | port only | b43 writes 488 ops on 412 radio registers; the vendor 193 on 90. **It is not a hole**: the 412 entries are deliberate and the 54-entry stub brings the radio up, see `gap-inventory.md` 4h |
| PAPD tables | — | **closed by `0012`** | they were 520 ops in the wrong place: `0004` wrote them in `b43_phy_initn`, now they sit in the cal as in the capture |
| v@578-751 | 173 | vendor only | table 8, object memory, 45 PHY reads: not attributed |

On the first one, the count has to be made **per phase**: a window of records
picked by eye like 60-400 mixes the upload of the init table, the
`radio_2057_setup` and the first channel change, and what comes out is that 32
registers of 70 have a value different from the table's — the signature of
writes coming from another phase.

The number that holds is the one over the whole init: 193 radio writes on 90
distinct registers on the vendor's side, 488 on 412 on the port's. The
qualitative conclusion does not change — b43 writes many more radio registers —
but the exact count of which and in which phase has to be redone per phase, not
on a window picked by eye.

### The radio init, counted per phase

Delimiting the phase properly — everything **before the first `CHANSPEC`**, i.e.
#132, which is where `b43_switch_channel()` takes over from the radio init — the
count is clean and says only one thing:

| | value |
|---|---|
| vendor radio writes in the phase | **45** |
| distinct registers | **43** |
| of which with a value *identical* to b43's table | **41** |
| with a different value | 4 (`0x164`, `0x2e`, `0xce`, `0x11`) |
| registers outside b43's table | **0** |
| entries b43 writes | **412** |

So it is not a different phase and not different registers: it is **the same
subset**, 43 registers of 412, with 41 values of 45 identical. b43 writes 412.
The 4 different values are the next thing to look at — `RAD.MOD` exists in the
capture, so at least some could be read-modify-writes rendered as WR by the
decoder, and that has to be checked before drawing conclusions.

And it is not a tracer artefact. `PHY.ARRW` is only a marker and the ops that
follow from it are all in the trace (`docs/blob-inventory.md`), and anyway
`phy_reg_write_array` writes **PHY** registers, not radio ones: radio writes go
through `write_radio_reg`, which is hooked. So the vendor really writes 70
registers where b43 writes 412.

brcmsmac does not do it either: `wlc_phy_radio_init_2057` loads the whole table
at every init, and its two `phy_init_por` (`phy_n.c:19968`, `20056`) cover only
rcal/rccal, exactly like b43. It is a difference between `wl 6.30` and the two
GPL drivers, not a transcription error. **SALAME** on what justifies it: that
wl keeps a mirror and rewrites only what changes is a hypothesis, not verified,
and whether the 342 extra writes are harmless is not known.

The 520 block on the other hand is not a hole of the port: it is `0004` in the
wrong place. As long as those writes sit in the init, **the init does not align
by construction**, and that settles empirically the choice of the section
below: option 1 is not enough, option 2 is needed.

| | port | capture |
|---|---|---|
| first ops | volatile table 9 (antswlut) | initvals array and AFE |
| radio init table | absent from the flow | #100-#108 |
| from here on | same order | same order |

## The flow, phase by phase

`b43_phy_initn()` is at `phy_n.c:5976-6186`, `wlc_phy_init_nphy()` at
`brcmsmac/phy/phy_n.c:19196-19548`. The two functions have the **same shape**:
b43 is a port of that one, call by call.

| # | phase | b43 | port | capture | brcmsmac | state |
|---|---|---|---|---|---|---|
| 1 | N-PHY tables | `b43_nphy_tables_init` | 1 | — | `wlc_phy_tbl_init_nphy` | ok |
| 2 | mimo config, txrx chain | `b43_nphy_update_{mimo_config,txrx_chain}` | | | `wlc_phy_{update_mimoconfig,stf_chain_upd}_nphy` | ok |
| 3 | **epsilon offset** + `PAPD_EN0/1` | `b43_nphy_papd_epsilon_offset` | 7329 | #286-#288 | tail of `wlc_phy_a4` (not the init!) | **`0009`** |
| 4 | scalar and epsilon tables | `b43_nphy_papd_tables_init` | 7332 | #10966+ (in the cal) | `wlc_phy_a4` (not the init!) | **`0004`** |
| 5 | TX digital filters | `b43_nphy_int_pa_set_tx_dig_filters` | 7852 | #289-#348 | `wlc_phy_ipa_set_tx_digi_filts_nphy` | 45/60, the rest idempotent |
| 6 | workarounds, phase track | `b43_nphy_workarounds` | 7900 | #349-#362 | `wlc_phy_workarounds_nphy` | ok |
| 7 | 2 GHz IPA bias | inside the rev 7+ workarounds | 8139 | #605-#607 | `wlc_phy_workarounds_nphy_rev7` | **`0005`**, 3/3 |
| 8 | CRS thresholds + RX gain control | inside the workarounds | 8207 | #680-#770 | `wlc_phy_workarounds_nphy_gainctrl` | **`0008`+`0001`**, 87/87 |
| 9 | classifier, clip detection | `b43_nphy_{classifier,read_clip_detection}` | | | `wlc_phy_{classifier,clip_det}_nphy` | ok |
| 10 | tx power control, fixpower | `b43_nphy_tx_power_{ctrl,fix}` | | | `wlc_phy_txpwr{ctrl_enable,_fixpower}_nphy` | different values, `todo-nphy` 3 |
| 11 | internal TSSI setup | `b43_nphy_ipa_internal_tssi_setup` | 8546 | #1251-#1281 | `wlc_phy_ipa_internal_tssi_setup_nphy` | one op too many, `todo-nphy` 3d |
| 12 | **zero-amplitude tone** (idle TSSI) | `b43_nphy_tx_tone(4000, 0)` | 8568 | #1288-#1609 | `wlc_phy_tx_tone_nphy` | **`0010`**, 322/322 |
| 13 | idle TSSI poll | `b43_nphy_poll_rssi` | | #1668-#1678 | `wlc_phy_txpwrctrl_idle_tssi_nphy` | ok |
| 14 | tx power ctl setup | `b43_nphy_tx_power_ctl_setup` | | | `wlc_phy_txpwrctrl_pwr_setup_nphy` | ok |
| 15 | tx gain table + **PAPD compensation** | `b43_nphy_tx_gain_table_upload` | 9938 | #2688-#2703 | `wlc_phy_get_ipa_gaintbl_nphy` | **`0003`**, 16/16 |
| 16 | RSSI cal | `b43_nphy_rssi_cal` | 11069 | up to #3719 | `wlc_phy_rssi_cal_nphy` | polling out of step, 4bis/4ter |
| 17 | RSSI coefficients | `b43_nphy_scale_offset_rssi` | 11417 | #3723-#3740 | same | 11/16 |
| 18 | TX IQ/LO cal | `b43_nphy_cal_tx_iq_lo` | `initcal` only | #8527-#8638 | `wlc_phy_cal_txiqlo_nphy` | **not in the `init` flow** |
| 19 | **PAPD cal** | *does not exist* | — | #10962-#14092 | `wlc_phy_a4` | `papd-cal-map.md` |
| 20 | unattributed region | — | — | #14093-#15920 | ? | not attributed |
| 21 | RSSI cal, second round | — | — | #22247-#23771 | `wlc_phy_rssi_cal_nphy` | outside the port's flow |
| 22 | tx power coef., tx lpf bw, spur | `b43_nphy_tx_pwr_ctrl_coef_setup`, `b43_nphy_tx_lpf_bw` | | | same names | ok |

The empty cells of the **port** column are phases that have no op in the trace
distinctive enough to anchor them without ambiguity: they are there, but they
were not located by hand. Rows 19-21 describe mainline; `rxiq-cal-map.md`,
`papd-cal-map.md` and `CLAUDE.md` say what the series has ported since.

## And now the point: why b43 does not reach the PAPD cal

It is not "b43 does not have `wlc_phy_a4`". It is that **not even brcmsmac
calls `a4` from the init**, and the road that leads there in b43 is an empty
stub.

Looking at the tail of the two functions, the block of calibrations has two
branches:

```
b43:                                    brcmsmac:
if (nphy->perical != 2) {               if (pi->nphy_perical != PHY_PERICAL_MPHASE) {
    b43_nphy_rssi_cal();                    wlc_phy_rssi_cal_nphy();
    b43_nphy_cal_tx_iq_lo();                wlc_phy_cal_txiqlo_nphy();
    b43_nphy_cal_rx_iq();                   wlc_phy_cal_rxiq_nphy();
    b43_nphy_save_cal();                    wlc_phy_savecal_nphy();
} else if (mphase_cal_phase_id == 0) {  } else if (mphase_cal_phase_id == IDLE) {
    ; /* N PHY Periodic Calibration      wlc_phy_cal_perical(pi, PHY_PERICAL_PHYINIT);
         with arg 3 */                  }
}
```

Three things, and the third is the one that matters:

1. **`PHY_PERICAL_MPHASE` is 2** (`brcmsmac/phy/phy_hal.h`), and
   `b43_nphy_op_prepare_structs()` sets `perical = 2`. So b43, by default, takes
   the **second** branch.
2. b43's second branch is a semicolon with a comment. The comment even names the
   right argument: `arg 3` is `PHY_PERICAL_PHYINIT`. It is the only point of the
   init from which the periodic cal is reached, and from there `a4`:
   `wlc_phy_cal_perical` → `wlc_phy_cal_perical_nphy_run` → `cal_txiqlo` →
   **`a4`**.
3. The **first** branch, the one that runs with `perical != 2`, does not call
   `a4` even in brcmsmac.

Hence the counter-intuitive consequence, and the reason it is worth writing
down: the harness's `initcal` flow sets `perical = 0` to "turn the calibrations
on", and so takes the **first** branch — the one that **does not have** the PAPD
cal. Neither of the harness's two flows can show the PAPD cal, and not because
`a4` is missing: what is missing is the dispatcher of the periodic cal, which is
also the place from which the RSSI, TX IQ/LO and RX IQ cals are redone over
time. (That dispatcher is `patches/b43/MESSAGES.md#0014` now.)

The capture confirms it went through there: the order is TX IQ/LO cal
(#8527-#8638) and **right after** the PAPD cal (#10962), which is exactly
`cal_perical_nphy_run` — `cal_txiqlo` then `a4`.

## The problem that follows, to be decided before writing

`0004` and `0009` put into `b43_phy_initn` two things brcmsmac does **inside
`a4`**: the initialisation of the scalar/epsilon tables (row 4 of the table)
and the computation of the epsilon offset (row 3). It was the right choice as
long as the cal is not there: without it, the PAPD engine runs on uninitialised
tables and with an epsilon offset 24 dB off.

When the cal arrives, the three ways out are:

| | what | cost |
|---|---|---|
| 1 | leave them in `initn` and have the cal **redo** them too | the writes are idempotent and the capture does them twice with the same value (epsilon offset at #286 and at #13842), so it works; but the port's init does work the vendor's init does not, and the `papd-tables` and `papd-comp` windows measure the position in the init instead of in the cal |
| 2 | move them into the cal, and call the cal from the init even with `perical = 2` | it is what it takes for the port to resemble the vendor, but it changes the init flow of **every** N-PHY and cannot be gated on the revision without inventing a branch the vendor does not have |
| 3 | move them into the cal and accept that at init they do not run | the most faithful to brcmsmac, the worst in practice: the PAPD engine is back on uninitialised tables every time the cal does not start |

**The measurement decided**: option 1 leaves in `initn` 520 ops the capture
does not have at that point, so with option 1 the init never aligns. Option 2 is
needed — move them into the cal and make the cal reachable from the init — and
that it is also the only road to the PAPD cal is no coincidence: it is the same
`perical` branch.

## How far from the vendor's run, per region

    ./phase_compare.py --vendor ../../router-data/dsl3580l/opinit-ch1-ch6-bw20.decoded \
                       --global-run 132 26100 --flow full --channel 6

| region | records | ops | paired | |
|---|---|---|---|---|
| init proper | #132-10961 | 9692 | 3488 | 36% |
| PAPD cal (`a4`) | #10962-14092 | 2662 | 694 | 26% |
| unattributed | #14093-15920 | 1698 | 84 | 5% |
| **unattributed, table upload** | #15921-22246 | 5812 | 514 | **9%** |
| second RSSI cal | #22247-23771 | 960 | **0** | **0%** |
| tail | #23772-26100 | 2127 | 618 | 29% |

Total: 5398 ops of 22951, 24%. With the `init` flow alone it is 4425, 19%.
These are the figures of when this table was taken; `CLAUDE.md` has the current
ones.

The percentages are **a lower bound**: the comparison is positional, so an op
present with the same value but at another point counts as unpaired, and that
is why the windows with `equiv='multiset'` exist.

The green windows and the 36% of the init do not contradict each other: the
windows cover precise phases, and there is a lot in the init that is in no
window.

The region to look at is **#15921-22246**, the largest and the least explored,
larger than the PAPD cal. It is dominated by table uploads: 93 `TBL.WR` whose
payload is ~5000 ops on registers `0x72`/`0x73`/`0x74`, on tables 15 (IQLOCAL),
26 and 27 (gain and power of the tx power control) and 17. Plus `0x129` 118
times. Nobody has attributed it yet. (`rxiq-cal-map.md` has since: it is the
RX IQ cal.)

And the second RSSI cal is at **zero**: of those 960 ops the port gets none
right, not a part. It is the kind of number that says "this phase does not
exist", not "this phase is out of step".

### Why the breakdown has to be taken from `--global-run`

`CMP.load_vendor()` drops the bookkeeping lines, the shadows of the
`SI.COREREG`s and the read-modify-write shadows, so **the index in the list of
ops is not the record number**. Rebuilding the correspondence by hand gives an
alignment that drifts: up to 230 ops off per region, with the second RSSI cal
coming out at 5% instead of zero.

`compare.py` has `Op`, a subclass of `str` that carries the record number along
through the whole normalisation, and it is `--global-run` that prints the table.
The total does not depend on that correspondence, the breakdown does.

## The cold init, now comparable

`router-data/dsl3580l/full-init-ch1-bw20.decoded` is a cold init, so the
harness's `initpor` flow finally has a reference. The usable part of the capture
is records **#2-#32769**, contiguous, before the overflow hole.

    cd test/unit && ./nphy_trace initpor dsl3580l 1 > /tmp/por.out
    # difflib comparison between /tmp/por.out and records #2-#32769

| | |
|---|---|
| vendor ops, #2-#32769 | 32056 |
| ops of the `initpor` flow | 13468 |
| in common | **7200 (22%)** in 330 blocks |

And the **download of the static tables matches**, which is what had no check
at all before: runs of **1424** and **806** consecutive ops opened by
`PHY.WR addr=0x72 val=0x3400` and `val=0x4800`, plus 258 on `val=0x6840`. They are
the N-PHY tables written one after the other with the same values in the same
order.

The overall 22% is not to be read as "the port is 78% wrong": in a cold init the
vendor emits 32056 ops against the port's 13468, and the difference is largely
phases b43 does not have — the PAPD cal, `rcal`/`rccal`, and the RSSI cal that
does not run in the port. The per-phase comparison stays that of the windows of
`phase_compare.py`.

A note for whoever redoes the measurement: `phase_compare.py`'s windows are
anchored to the `opinit-*` capture, which is hot. To compare `initpor` the other
capture has to be passed by hand, except for the windows that declare their own
(`static-tables` and `static-tables-2` carry `capture='full-init-ch1-bw20.decoded'`,
see `test/unit/README.md`).
