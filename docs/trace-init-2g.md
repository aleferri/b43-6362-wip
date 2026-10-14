# The DSL-3580L 2.4 GHz init trace

Captured with `wl-diag/2-6-30` on the stock firmware, blob `wl 6.30.102.7`,
integrated radio of the BCM6362 (N-PHY rev 8, radio 2057 rev 8), 2.4 GHz bw20.

The flow is **two `wl down` / `wl up` cycles**, not an attach: the first with
operating channel 1, the second with operating channel 6. Between the two, 15 s
of radio down. In both cycles the driver leaves the operating channel every 2 s
— to ch5 in the first, to ch2 and ch10 in the second — and comes straight back.

The data is in `router-data/dsl3580l/opinit-ch1-ch6-bw20.decoded`, decoded; the
binary is not in the repository (see the record next to it for the sha256 and
the no-loss check).

## Quality of the capture

70796 records, 39.8 s, **zero `OP_DROP` and zero sequence discontinuities**: no
loss, so the positional comparison with the port is legitimate.

| records | contents |
|---|---|
| 1 - 131 | initial radio init (45 `RAD.WR`) |
| 132 - 26100 | first `up`, channel 1: complete PHY init (16834 `PHY.WR`, 771 `TBL.WR`) |
| 26101 - 34156 | 7 excursions to ch5 and back |
| 34157 - 34937 | `down` and 15 s of waiting: 781 records, `GPIO.CTL`/`GPIO.OUT`, 15 `MAC.MCTRL` |
| 34938 - 61971 | second `up`, channel 6: complete PHY init (16855 `PHY.WR`, 775 `TBL.WR`) |
| 61972 - 70796 | 5 cycles ch2 / ch10 / ch6 |

**Two init sequences, not one.** Having two on different operating channels is
the most useful thing about the capture: it tells what depends on the channel
from what is fixed.

Histogram: 38616 `PHY.WR`, 11049 `RETVAL`, 9410 `PHY.RD`, 2314 `OBJ.WR`, 1901
`PHY.MOD`, 1606 `TBL.WR`, 1314 `RAD.WR`, 1251 `OBJ.RD`, 856 `PHY.OR`, 781
`PHY.AND`, 570 `TBL.RD`, 332 `RAD.RD`, 223 `PHY.ARRW`, 184 `RAD.MOD`, plus the
markers.

## What it settled about the tracer

Three uncertainties that were noted as such in the tracer's code:

- **`phy_reg_write_array`**: the second argument is the number of **words**, not
  of records. `#5 PHY.ARRW val=0x000c` followed by 4 `PHY.WR` → 12 words,
  3-word records. And the choice of hooking it as a marker only is confirmed
  right: every op that follows from it is in the trace through the accessors.
- **`len`/`off` order in `wlc_phy_table_write_nphy`**: settled. The offsets
  observed (0x00, 0x04, 0x08, 0x20, 0x10, 0x1c) and the lengths (1, 2, 4, 10)
  make sense only in the decoder's current assignment; swapped, they would give
  `len=0`.
- **`si_pmu_spuravoid`, `and_radio_reg`, `or_radio_reg`**: **zero** records in
  the whole capture, and zero PMU records of any kind. On this SoC the clocking
  does not go through the bcma PMU, so it is consistent; the hooks stay because
  they cost nothing, but no records are to be expected from there.

## What it confirmed about the kernel

**The merged chantab is the right one, on every channel the capture touches.**
`reverse-tools/verify_chantab_trace.py` compares the 18 fields of the 2.4 GHz
variant for every `CHANSPEC`: **31 channel changes out of 31, zero
differences**, on the five channels present (1, 2, 5, 6, 10), with the same
values and in the same order in which `b43_radio_2057_chantab_upload()` writes
them. For example on the change to ch5:

    016=55 017=16 022=30 025=1b 027=0a 028=0a 029=30 02c=80 02d=09
    037=0f 041=09 047=06 05c=61 05e=73 09a=f0 0e1=61 0e3=73 11f=f0

That includes `R1=0x1b`, `C1=C2=0x0a`, `CP_KPD_IDAC=0x30`, i.e. the confirmation
on silicon that the missing `case 8` in `b43_radio_2057_setup()` is a no-op (see
`gap-inventory.md`, entry 2), and the confirmation holds on five different
channels, not on one.

## What it corrected

**The gain control values are not brcmsmac's.** The first draft of the patch
came from `wlc_phy_workarounds_nphy_gainctrl_2057_rev6`; the device does
otherwise:

| what | brcmsmac | device |
|---|---|---|
| LNA1 gain | 9, 14, 19, 24 | **8, 13, 18, 25** |
| W1 clip (0x300/0x301) | 13 | **24** |
| 0x283 | 0x40, then 0x44 from the dispatcher | **0x44 only** |
| LNA2, TIA gain, TIA gain bits at 2.4 GHz | not written | **written** |

brcmsmac's 2 GHz branch is poorer than what the 6.30 blob runs: LNA2
(`fc 06 0a 0f`), TIA gain (`ff 00 03 06...`) and the gain bits (`00 01 02 03...`)
are programmed, and there are also the clip1 low gain codes
(0x37/0x2ad = 0x74, 0x38/0x2ae = 0x18). `patches/b43/MESSAGES.md#0001` was
rewritten on these numbers.

The two inits give the same identical block — same registers, same values, same
order, at #685-#770 with operating channel 1 and at #35491-#35576 with operating
channel 6. So these values **do not depend on the channel**, and it is legitimate
to hard-code them in C as the patch does.

## What it found that was new

On the channel change the vendor writes **ten more registers**, all to zero:

    0x043 LOGEN_MX5G_TUNE          0x04a LOGEN_INDBUF5G_TUNE
    0x070 PGA_BOOST_TUNE_CORE0     0x0f5 PGA_BOOST_TUNE_CORE1
    0x073 TXMIX5G_BOOST_TUNE_CORE0 0x0f8 TXMIX5G_BOOST_TUNE_CORE1
    0x074 PAD5G_TUNE_MISC_PUS_CORE0 0x0f9 PAD5G_TUNE_MISC_PUS_CORE1
    0x0a0 LNA5G_TUNE_CORE0         0x125 LNA5G_TUNE_CORE1

They are the 5 GHz and PGA fields of the **dual-band** entry: the vendor uses the
44-byte record at 2.4 GHz too and clears the 5 GHz part, while b43 uses the
`chantabent_rev7_2g` variant and does not touch those registers at all.

**SALAME**: that leaving them at their previous value has a measurable effect
(current, leakage from the 5 GHz branch) is a hypothesis, not data. Before
touching the shared path of `chantab_upload`, which concerns other devices too,
a measurement is needed. Open entry, not a patch.

## Still to capture

A note on 40 MHz, which is not in the list for a reason: on this board the
vendor driver does not use 40 MHz at 2.4 GHz, 31 chanspecs out of 31 are bw20.
The driver's HT40 branches cannot be verified here even if one wanted to,
different hardware is needed — and code comments have to say it that way, not
as "the capture is missing", which sounds as if nobody had tried.

- `cal`: `wl phy_forcecal 1`, for rcal/rccal/tx iq-lo/papd.
- a complete round of channels 1-13: there are five here (1, 2, 5, 6, 10) and on
  those nothing depends on the channel beyond the chantab, but 13 and 14 remain
  to be seen (spuravoid, for example, which never shows up here).
- the cold init **again, without the hole**: the one there is
  (`full-init-ch1-bw20.decoded`, 81397 records) loses 65285 records between
  `#32769` and `#98055` to a FIFO overflow, so only `#2-32769` can be compared
  positionally. Its record says how to take it again.

The values read at the decision points are already there: `skipphyrd` was
empty in both captures and the `RETVAL`s are on (11049 here, 11795 in the cold
capture), from which the harness's read plans — 2089 reads paired out of 2089.
