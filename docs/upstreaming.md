# What can be proposed and what cannot

## Proposable almost as is

`patches/0001` and `0002`. They are self-contained, do not touch the behaviour
of existing hosts (the two new fields are `false` for everyone else) and the
technical motivation can be verified on silicon. To do before sending:

- run `0003` (the binding) through `dt_binding_check`, which has not been done;
- decide whether to keep the reference to the BCM63268 in the description: the
  chip has a similar block, but if it is not tested it is better not to name it
  as supported;
- check that the teardown is right on `rmmod bcma` with the d11 still bound,
  not only on the happy path.

## Not proposable as is: the SPROM

This is the real obstacle. In the fork the SPROM of the core on the SoC comes
from `brcm,bcma-sprom` with `bcma-bus = <&wlan>`, which is an **OpenWrt-only**
driver (`target/linux/generic/files/drivers/bcma/fallback-sprom.c`): mainline
has no mechanism to serve a SPROM from the device tree. The only upstream hook
is `bcma_arch_register_fallback_sprom()`, used by bcm47xx from arch-specific
code.

Three roads, in order of increasing cost for whoever has to get them accepted:

1. **an arch-specific fallback for bmips**, on the model of
   `arch/mips/bcm47xx/sprom.c`: it reads the parameters from the CFE NVRAM and
   turns them into a `struct ssb_sprom`. It follows an accepted precedent, but
   on bmips, which is DT-only, it adds arch code the target has avoided so far.
2. **a new DT binding** for a SPROM provided by nvmem/firmware: the clean road,
   and the longest, because it has to be discussed with the DT maintainers and
   not only with the bcma/b43 ones.
3. **no SPROM**: derive everything from per-chip defaults. It does not hold: the
   DSL-3580L's 38 fixups include per-chain PA calibrations, i.e. per-board data.
   A second instance of the same core, wl0 of the TG789vac v2, has a SROM that
   differs from the DSL-3580L's in 38 words of 220, all power data: antenna
   gain, maxpower and PA per chain, 2.4 GHz per-rate offsets. The other 182,
   `boardtype` and `boardflags` included, are the same
   (`router-data/tg789vac-v2/README.md`).

To be decided before writing code, because it changes where the parsing lives.

## Shared routines have to be gated, or it is a nack

Nearly everything in b43's PHY is shared among all N-PHYs: the same functions
run on rev 1 as on rev 17. An ungated change alters the behaviour of hardware
we do not have, cannot test, and have no captures of — and that is an immediate
nack, rightly.

The first two patches written are fine: `0001` sits in
`b43_nphy_gain_ctl_workarounds_rev7()`, which is already rev-specific by name,
and has at its head an `if (phy->radio_rev != 8 || 40 MHz || 5 GHz) return`;
`0002` is a data-only change in an array that `b43_nphy_get_rf_pwr_offset_table()`
returns only for `phy->rev == 8 && phy->radio_rev == 8`.

The risk is in the work that comes after. These are the functions the open
entries of the inventory lead to touch, all shared, with the gate each would
need:

| function | who uses it | gate needed |
|---|---|---|
| `b43_nphy_op_prepare_structs` | **every** N-PHY | it is where `perical = 2` lives: not to be touched. The knob to run with the cal on lives in the harness (`test/unit/main.c`), not in the driver |
| `b43_radio_2057_chantab_upload` | radio rev 5, 8, 9, 14 | the ten 5 GHz registers cleared (entry 5b) are behind `radio_rev == 8` in `0011`, so as not to change the channel change of 43217, 43227 and revs 9/14 |
| `b43_nphy_tx_pwr_ctl_init` | every rev 7+ | removing the early return holds for rev 8 with radio rev 8, not for all of rev 7+: we do not have 16/17 with radio 9/14 |
| `b43_nphy_workarounds_rev7plus`, `b43_nphy_gain_ctl_workarounds` | rev 7+ dispatchers | any addition goes in a per-revision branch, not in the common body |
| `b43_supported_bands` | every b43 device | the `dev_id 0x435f` case (entry 6) must not change the bands announced by the other dual-band devices |

`reverse-tools/check_patch_gating.py` checks it mechanically: for every added
line it finds the function that contains it in the file after the patch and
looks for a gate that dominates it — a rev-specific name, an early return on
rev, or an `if`/`case` on the revision. It is a heuristic on brace depth and
not a C parser, so a `NON GATEATA` has to be looked at and not obeyed blindly;
but it catches a test change inside `b43_nphy_op_prepare_structs`.

```sh
./scripts/series-diff.sh ~/src/pin /tmp/base > /tmp/serie.diff
./reverse-tools/check_patch_gating.py --tree /tmp/base /tmp/serie.diff
```

Until the series is split the verdict is **one for the whole series**, and it is
taken over the mainline patches, not on the clean tree — on the clean tree the
tool dismisses it with `(patch non applicabile)`, which the final counter does
not count: `series-diff.sh` writes exactly that starting tree into `/tmp/base`.

It gives **six** ungated points, all declared in `patches/b43/NOTES.md`. The
per-patch verdict comes back with the split; the dependency chain needed to
redo it (`0002 -> 0004 -> 0009`, and `0012` behind `0009`) is in `CLAUDE.md`.

## Not proposable now: HT

See `ht20-mimo-plan.md`. M0-M2 first, and with the reports in hand.

## A note on the tool

`reverse-tools/check_patch_gating.py` used to trust the line numbers in the
patch's `@@`. `patch(1)` however relocates hunks when the tree is not exactly
the one the patch was made on, and does so silently because it is invoked with
`--silent`: on a multi-hunk patch the error accumulates and the added lines end
up attributed to the wrong function. Which is the worst way for a tool like
this to be wrong, because the name it prints exists.

Now the numbers come from the diff between the content before and after. Three
verdicts of the series changed then, and all three were corrections:

| patch | before | after |
|---|---|---|
| `0004` | only `b43_phy_initn`, line 6031 | `b43_nphy_papd_tables_init` new function **plus** `b43_phy_initn` at line 6101 |
| `0005` | `b43_nphy_workarounds_rev3plus` (3138-3344) | `b43_nphy_workarounds_rev7plus` (2693-3135), which is where the lines are |
| `0012` | `b43_chantab_phy_upload` NON GATEATA | `b43_nphy_papd_cal` new function, `b43_phy_initn` gated |

The two `NON GATEATA` left at that point were both from `0010`, and they were
right: that patch is a mainline fix for every N-PHY and must not be gated.
