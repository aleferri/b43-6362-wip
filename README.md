# b43-6362-wip

Work in progress to complete **upstream** support for the 2.4 GHz radio
integrated in the **Broadcom BCM6362** SoC (d11 core rev 22, N-PHY rev 8, radio
2057 rev 8), with **HT20 2x2 MIMO** as the end goal.

HT40 is out of scope by choice: the available clients are 2.4 GHz, and on this
band HT40 brings nothing useful. 5 GHz is out of scope too, with a consequence
that has to be handled rather than ignored (see `docs/gap-inventory.md`, entry
`dev_id 0x435f`).

## State in one table

| piece | state | where |
|---|---|---|
| radio 2057 rev 8: init table, chantab, IPA TX gain, RF power offset | **merged upstream** (7 patches, 10 Jun 2026) | `docs/upstream-status.md` |
| firmware rev22 (`ucode22_mimo`, `n0initvals22`, `n0bsinitvals22`) | mapping merged; availability of the blobs to be checked | `docs/firmware-rev22.md` |
| bcma enumeration on the SoC backplane | works out of tree, **to be proposed** | `patches/`, `docs/soc-glue.md` |
| SPROM fallback for the core on the SoC | works only with the OpenWrt extension, **not upstreamable as is** | `docs/upstreaming.md` |
| N-PHY rev 7+ gain control | empty stub in mainline, **in `b43/`, `patches/b43/MESSAGES.md#0001`**: reproduces the capture op for op in the harness, never run on hardware | `test/unit/README.md` |
| chantab rev 8, 5 GHz fields | the vendor zeroes them on every channel change, b43's 2 GHz table did not have them: **patch `0011`**, 31 channel changes out of 31 in the capture | `docs/gap-inventory.md` |
| chantab rev 8, 2.4 GHz fields | **verified on silicon**: 31 channel changes out of 31, five channels | `docs/trace-init-2g.md` |
| RF power offset rev 8 | wrong values in mainline, **closed by the capture**: patch `0002` | `docs/rf-pwr-offset-rev8.md` |
| PAPD compensation rev 7+ | never programmed because of an early return, **patch `0003`**: 256 cells identical to the capture | `docs/gap-inventory.md` |
| PAPD epsilon and scalar tables | engine started on uninitialised tables, **patch `0004`** | `docs/gap-inventory.md` |
| 2 GHz IPA bias on rev 8 | wrong register and values that differ between the cores, **patch `0005`** | `docs/gap-inventory.md` |
| carrier sense thresholds | nobody wrote them, **patch `0008`** | `docs/todo-nphy.md` |
| noise floor on N-PHY | not measured at all, **patch `0006`** | `docs/phy-g-only.md` |
| RSSI and RX decoding on N-PHY | branches only for G and LP in `xmit.c`, and RSSI coefficients different from the vendor's | `docs/todo-nphy.md` |
| target power, TSSIG, RF ctl misc | written by both sides with different values | `docs/todo-nphy.md` |
| PAPD epsilon offset | written as zero by b43, **patch `0009`**: 24 dB apart | `docs/papd-cal-map.md` |
| sample table, i.e. the test tone | phase step truncated to zero in a `u16` and in-phase component lost to an operator precedence: b43 has never played a tone, on any N-PHY. **Patch `0010`**, 160 words out of 160 identical to the capture | `docs/papd-cal-map.md` |
| PAPD calibration, the rest | the two `wlc_phy_a3_nphy` driven by the reads; phases mapped and attributed | `docs/papd-cal-map.md` |
| periodic cal: TX IQ/LO, RX IQ, second RSSI cal | in mainline the branch that calls them is a `;/* TODO */`, so they never run: **patch `0014`**. The second RSSI cal, measured on its own, is at 956 ops out of 960 | `CLAUDE.md` |
| VCM search in the RSSI cal | `Q * I` instead of `Q²` in the distance, and the winner programmed with the loop counter instead of the winner: **two mainline patches**, they apply from N-PHY rev 3 | `CLAUDE.md` |
| HT (11n) in b43 | **entirely absent** | `docs/ht20-mimo-plan.md` |

The patch numbers in the table are the entries of `patches/b43/MESSAGES.md`.

## Repository layout

```
b43/                 the b43 files the port changes, whole, on the pinned tree
                     with patches/mainline/ applied
bcma/                the bcma files and the DT binding, at their kernel paths
patches/             0001-0003, the bcma series generated from bcma/ on the tree
                     in regen-base; mainline/ (twelve separate patches);
                     openwrt/; b43/ (messages, notes and split plan of the
                     b43 series)
test/unit/           harness that builds the N-PHY sources of b43/ in
                     userspace and emits their trace, against the vendor capture
docs/                state, the two init flows side by side, gap inventory,
                     HT20 2x2 plan, upstreaming, capture protocol
docs/reports/        templates of the on-hardware bring-up reports
reverse-tools/       decoding pipeline, extractor/verifier of the tables in the
                     OEM blob, coverage analysis on the kernel tree
wl-diag/             on-device tracer for the wl driver (2-6-30/ and 3-4/),
                     tuned on the N-PHY, and its decoder
router-data/         captures and static dumps per board
scripts/             pinned tree, patch regeneration, the series as a diff
bringup-log-*.txt    on-hardware bring-up logs, by date (docs/reporting.md)
```

There are two captures, in `router-data/dsl3580l/`. `opinit-ch1-ch6-bw20`
(70796 records, two down/up cycles on operating channels 1 and 6, no loss) has
already corrected a patch (`docs/trace-init-2g.md`) and found four mainline
defects (`patches/b43/MESSAGES.md#0005`, `0010`, `0011`, `0012`) plus the two
in the VCM search. `full-init-ch1-bw20` (81397 records, cold init, with a hole
of 65285 records from a FIFO overflow) is the only one with the download of
the static tables. `router-data/tg789vac-v2/` and `router-data/d6220/` hold
what `b43-ac-wip` has on the same core, see `docs/ac-wip-xref.md`.

## Reproducing the state

Everything this repository says about the kernel is checked on the tree, not on
the documentation, which ages. Reference: `torvalds/linux` @ `045958acaa75`,
15 Oct 2026 (7.3-rc7), in `patches/regen-base`.

```sh
./scripts/fetch-upstream-state.sh ~/src/pin             # the pinned tree
./scripts/fetch-upstream-state.sh ~/src/linux master    # upstream, with the two reports
cd test/unit && make KDIR=~/src/pin && make KDIR=~/src/pin warncheck
```

To check the merged tables against the OEM blob again:

```sh
./reverse-tools/blob_tables.py wlDSL-3580_EU.o_save \
    --verify regs_2057_rev8 \
    --against ~/src/pin/drivers/net/wireless/broadcom/b43/radio_2057.c:r2057_rev8_init
```

## Conventions

- **SALAME** in bold marks a hypothesis not verified on hardware or in the
  code. A conclusion without SALAME must come with a file:line reference, a
  sha, or the output of a tool of this repository.
- Code comments describe what the code does now, not what it used to do: the
  history goes in the commit messages.
