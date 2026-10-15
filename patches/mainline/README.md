# patches/mainline

Mainline defects independent of the BCM6362 and of this work. They are worth a
submission of their own, and before the rest, because they are short, not gated
on any revision and demonstrably wrong without the hardware in front of you.

**They are separate patches, not a series**, and go out as as many `[PATCH]`es
in as many threads: none needs another to be correct, and tying them into a
series means a long review on one holds up the merge of the others. Only one
pair touches, and only for context — `treat-the-n-phy-dac-test` and
`fix-two-defects-in-the-n-phy-sample-table-logic` change neighbouring lines of
`b43_nphy_gen_load_samples()`, see below.

| file | what | lines |
|---|---|---|
| `b43-fix-two-defects-in-the-n-phy-sample-table-logic` | `<<` binds tighter than `&`, and the phase step in a `u16` after one `<< 16` too many truncates to zero for **every** frequency the driver asks for | 6 |
| `b43-test-the-radio-rev-for-the-n-phy-tssia-setup` | `phy->rev != 5` inside a `phy->rev >= 7` branch: a dead guard, it was meant for the radio | 12 |
| `b43-fix-the-rounding-of-the-negative-rssi-cal-offsets` | the parenthesis of `abs()` in the wrong place: the `+4` ends up inside the negative value instead of on its magnitude, and every offset below -4 rounds towards zero. The same file gets it right twice | 2 |
| `b43-fix-two-rf-control-override-value-masks-on-n-phy-rev-7` | two `val_mask`s of `tbl_rf_control_override_rev7_over1` do not cover the field of their own shift. With field `0x0100` the port clears bit 8 of `0x340`, which belongs to the filter band programmed a few ops earlier | 4 |
| `b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7` | `one_to_many`, `TX_PU` case: four calls against brcmsmac's five, `(0x1 << 2)` on override 2 is missing | 1 |
| `b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag` | the DAC test mode is a `u8` tested `== 1`, b43 narrows it to `bool` in three places: any mode above 1 takes the wrong road | 5 |
| `b43-wait-for-the-n-phy-tx-iq-lo-calibration-to-finish` | the polling on `IQLOCAL_CMD` exits when bits 15/14 are **set**, i.e. while the cal runs, instead of waiting for them to clear: `SPINWAIT` in the reference loops *while* the expression is true. The driver reads the coefficients back ~10 us after the command, twelve times, and saves what was there before | 1 |
| `b43-take-the-n-phy-tx-iq-lo-results-out-instead-of-overwriting-them` | at the end of the cal, `write(96)` and `read(80)` have their direction **swapped**: the driver overwrites the engine's result with the old buffer and reads 80 instead of writing it. The three pairs that follow in the same block are right, which is what makes it look like a typo | 2 |
| `b43-fill-the-per-rate-transmit-power-offsets-on-n-phy` | `nphy->tx_power_offset[]` has **no writer**: declared, read in two places and filled nowhere, so the 84 cells of the adjusted power table come out at zero whatever the SPROM says, and every rate transmits at the same power. **It also carries a move of `b43_nphy_tx_pwr_ctrl_coef_setup()` that does not belong and must be split off**, see below | 20 |
| `b43-square-both-terms-of-the-n-phy-rssi-vcm-search` | the narrowband VCM search minimises `I² + Q²` and the second term is written `Q * I`: not a distance, and negative whenever the two rails have opposite signs, so the minimum falls where that product is most negative. The chosen VCM and the offsets that follow from it are both wrong | 2 |
| `b43-program-the-best-n-phy-rssi-vcm-instead-of-the-loop-bound` | the rev 7+ branch of the choice of the best VCM programs `vcm`, which at the loop exit is 8: the field is three bits wide, so it writes a bit out of the field and throws away the result of the search. The rev 3 branch below and brcmsmac both pass `vcm_final` | 2 |
| `b43-save-the-right-field-of-the-n-phy-tx-power-index` | when it turns power control off, it saves the index each chain was on by taking the **seven low bits** of the status instead of bits 8..14, which are the index — `B43_NPHY_TXPCTL_STAT_BIDX` of this same driver says so, and twenty lines below `b43_nphy_get_tx_gains()` reads it right. The restore puts that wrong field back into the index, so the hardware restarts from wherever | 12 |

The last two are proved **three ways**: brcmsmac, the capture and b43 say
different things, and the first two say the same thing. The capture lines are in
the body of the patches.

`reverse-tools/check_patch_gating.py --tree` on `045958acaa75` (as on
`848acc8ffe1b`: the b43 files are the same) flags **seven
points in five** of these patches, not two. Six are fine, and for the same
reason — a transcription or C precedence typo does not go behind a revision
gate, because it is not a feature of this hardware, and it is the exception
already declared in `b43/MESSAGES.md#0010`:

| patch | function | why no gate is right |
|---|---|---|
| `program-the-fifth-tx-power-up-override` | `b43_nphy_rf_ctl_override_one_to_many()` | fifth call missing, runs on every rev 7 and up |
| `treat-the-n-phy-dac-test-as-a-mode-not-a-flag` | `b43_nphy_gen_load_samples()`, `b43_nphy_run_samples()` | `u8` → `bool` narrowing, wrong on every rev |
| `fix-two-defects-in-the-n-phy-sample-table-logic` | `b43_nphy_load_samples()`, `b43_nphy_gen_load_samples()` | `<<` binding tighter than `&` and a truncated phase step: truncates on every rev |
| `wait-for-the-n-phy-tx-iq-lo-calibration-to-finish` | `b43_nphy_cal_tx_iq_lo()` | polarity of the `SPINWAIT`; the loop is under no gate, and the defect is not per rev |

The seventh is **not** covered by that exception, and has to be looked at
before sending: `b43-fill-the-per-rate-transmit-power-offsets-on-n-phy` in
`b43_nphy_op_recalc_txpower()`. Filling an array nobody writes changes what
every N-PHY rev 3 and up programs, and it is not a typo: it is new behaviour on
hardware we do not have. The tool's verdict on the **other** hunk of the same
patch, `b43_phy_initn` "dentro if (rev >= 3 &&", is a false positive of its
heuristic — the added line is indented **one tab**, so it is at function level,
after the `if (phy->rev >= 3) ... else ...` block has closed.

And that hunk is a problem of its own, unrelated to the rest of the patch: it
moves `b43_nphy_tx_pwr_ctrl_coef_setup()` **before** the calibrations. The
comment justifies it by saying that in the reference that call is the last thing
of the init and that what precedes it only schedules a calibration. **That is
not so**: in `wlc_phy_init_nphy` the non-mphase branch calls
`wlc_phy_cal_txiqlo_nphy` and `wlc_phy_cal_rxiq_nphy` **inline**
(`phy_n.c:19516` and `19519`) and `wlc_phy_txpwrctrl_coeff_setup_nphy` comes
**after** (`19534`), that is exactly where b43 has it now. Only the mphase
branch schedules. So the written justification contradicts the reference it
quotes; the real reason is the capture, and a reason that is the capture does
not belong in `patches/mainline/`, which by definition collects defects
independent of this hardware. It has to be split off into the series, or gated,
before sending the rest.

They are proved without hardware: by C precedence and arithmetic, because a
guard cannot be false, or because brcmsmac and the capture agree against b43.

Eleven apply **on their own** on clean mainline. The twelfth is
`b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag`, and it is not a defect of
the patch but a context dependency: its first hunk has `u16 bw, len;` among the
context lines, and on the clean tree that line is `u16 bw, len, rot, angle;`.
It is `sample-table-logic` that splits it in two (`u16 bw, len;` plus
`s32 rot, angle;`). With that one applied first, the dac-test one goes in with
offsets -43 and -113. **Whoever takes it alone from the thread cannot apply
it**, and the body of the patch has to say so.

The defect does not show when they are applied in alphabetical order, as
`scripts/series-diff.sh` does: `fix-two-defects-in-the-n-phy-sample-table-logic`
comes before `treat-`.

`b43-fill-the-per-rate-transmit-power-offsets-on-n-phy` **applies** on
`045958acaa75`, and without fuzz — `git apply` allows none — but with offsets
**-643, -643, -1027 and -1054**: it was generated on top of the series, which
makes `phy_n.c` ~1000 lines longer. It has to be regenerated on the clean
baseline before sending anyway, because four offsets of a thousand lines on a
moving tree are a patch that expires on its own, not because it does not go in
today.

  for p in patches/mainline/*.patch; do git apply --check "$p"; done

The first one carries two defects together, and not out of laziness: neither
half alone produces a right sample table — 140 wrong words of 160 with only the
mask fixed, 120 with only the phase step. They are two lines of one broken
logic, and separating them would give two patches nobody can verify.

With the first one applied, the `sampleplay-tssi` and `sampleplay-iqlo` windows
of `test/unit/phase_compare.py` both do **322/322**: the two sample tables
become identical to the capture, word for word, with nothing of the series. The
series in `b43/` no longer carries those two changes: it sits on top of these,
which already have them.

The second one is not in the series: it changes what a radio 2057 rev 5 and a
phy rev 7 program at 5 GHz, and we have neither. The rationale is in
`docs/todo-nphy.md` 3d bis.

`b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag` is latent: no in-tree caller
passes a mode other than 0 or 1, so on its own it changes nothing. It bites the
first caller with a real mode, which is the RX IQ cal — and the measurement is
there: with the `bool`, a type 2 builds the 160 words of the tone over a band of
80 or 82 instead of 20, and the port loses **476 ops** on `up-ch1`. The series
in `b43/` sits on top of this one and does not duplicate it.

None has run on hardware.
