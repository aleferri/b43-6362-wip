# What b43-ac-wip holds for the N core

`aleferri/b43-ac-wip` ports the AC-PHY of the BCM4352/4360 to b43. It runs on
the same DSL-3580L, where `wl1` is the BCM4352 and `wl0` is the BCM6362 core
this repository is about, under the same `wl 6.30.102.7`. Everything below was
checked against `b43-ac-wip` at `8c234e6`; where that repository moves, these
notes do not follow by themselves. The data were copied at `01e1329`, and
`router-data/` has not changed there since.

## Data, copied here

| here | what | from |
|---|---|---|
| `router-data/dsl3580l/wl0_revinfo.txt` | wl0's revinfo: corerev `0x16`, phyrev 8, radiorev `0x82057000`, ucoderev `0x3100002`, boardid `0x513` | `router-data/dsl3580l/router_info.txt`, the version block |
| `router-data/tg789vac-v2/` | a second board with the same core (`BCM435f`) under `wl 7.14.89.14`: its SROM and its boot log | `router-data/tg789vac-v2/` |
| `router-data/d6220/` | the only module attach of an N core under `wl` in either repository | `router-data/d6220/cold-sweep.zip` |

Each directory's README says what the data shows. The DSL-3580L captures of
`b43-ac-wip` hold nothing of wl0: `reverse-tools/strip_other_core.py` finds
no second attach in `cold01-ch36-bw20.txt` nor in the hot sweep segments
checked (`20a/seg00`, `20a/seg04`, `40/seg00`). The capture protocol here keeps
wl1 down for the same reason the other way round (`router-data/dsl3580l/README.md`).

## Same kernel base

`b43-ac-wip` builds its patches on `v7.2`, this repository on `045958acaa75`
(`7.3-rc7`). Of the 62 files of `drivers/net/wireless/broadcom/b43/` only
`debugfs.c` differs between the two points (7.3 replaced its page allocations
with `kzalloc()`), and neither port touches it. Upstream also added, in
`include/linux/ssb/ssb.h`, one declaration at the end that `b43-ac-wip`'s copy
of that header will have to take when it moves to 7.3.

The two ports change two b43 files in common, `main.c` and `b43.h`. A
three-way `git merge-file` with the pinned files as base merges both with no
conflict (this port: +57 and +6 lines; `b43-ac-wip`: +1751 and +198). That is
a textual result: the merged tree has not been built.

In bcma no file is changed by both: this port touches `main.c`, `scan.c`,
`bcma_private.h`, `Kconfig`, `Makefile`, `bcma.h` and adds the host driver;
`b43-ac-wip` touches `core.c`, the ChipCommon and PMU drivers, `driver_pcie2.c`,
`host_pci.c`, `sprom.c` and the ssb SPROM headers.

## Where the two meet in the code

- **Noise sample.** `b43-ac-wip` added a PHY op, `noise_sample_done`, which
  `handle_irq_noise()` calls for the AC-PHY; this port adds a
  `B43_PHYTYPE_N` branch in `main.c` that calls `b43_nphy_noise_sample()`.
  After the merge both branches sit next to each other in
  `handle_irq_noise()`. The N one could be the N-PHY's `noise_sample_done`
  in `phy_n.c`, and `main.c` would lose its PHY-type branch. Not done.
- **Error reporting.** In `b43-ac-wip`, after `B43_STAT_STARTED` every
  `b43dbg`/`b43info`/`b43warn`/`b43err` goes through `net_ratelimit()`, and
  controller restarts through `b43err_restart()`, which does not. This is not
  gated on the PHY type, so after a merge it applies to the N-PHY as well.
- **TX path.** `b43-ac-wip` sends HT and VHT rates and A-MPDUs, but all of it is
  built on the AC TX header (`b43_txhdr_ac_*` in `xmit.c`). For HT on the
  N-PHY (`docs/ht20-mimo-plan.md`) it is a reference for the mac80211 side
  (HT capability checks, A-MPDU density and factor), not code to reuse.
- **Microcode.** `docs/ucode42/` in `b43-ac-wip` maps the corerev 42 ucode; the
  core here is corerev 22 (`docs/firmware-rev22.md`). The method carries over,
  the maps do not.

- **Hardware keys across a controller restart.** `b43-ac-wip`'s `ea8a6ce`
  makes `b43_chip_reset()` copy the key slots before the core goes down and
  write them back afterwards: a core init clears the key memory and mac80211 is
  not told. It is not gated on the PHY type, so it holds for the N-PHY too, and
  the N-PHY restarts its controller as well (on error, and on band changes on
  dual-band boards).
- **HT on 2.4 GHz.** `bba92f0` gives the AC-PHY a 2.4 GHz band of its own with
  HT capabilities derived from the board's chains, 20 MHz only, A-MPDU on: the
  per-device band copy in `struct b43_wl` and its setup in `b43_setup_bands()`
  are the shape `docs/ht20-mimo-plan.md` M3 needs on the N-PHY, behind an N-PHY
  test instead of the AC one.

## Tools

- **`wl-mmio-trap/`** traces the register accesses that have no accessor to
  hook, which is exactly what `wl-diag` misses here: the `0x492` writes that
  `test/unit/phase_compare.py` declares as a known gap on `chanswitch-ch6`.
  As its README documents, it finds the register window through the PCI BAR,
  and a window below 512 MB comes back from `__ioremap()` in KSEG1 with no pte
  to trap; its `redirect=1` handles that case for a PCI device. wl0 sits on
  the SoC bus at `0x10004000`: it would need another way to find the window.
- **`wl-diag/`** in the two repositories shares the record format and options
  such as `skipphyrd` and the return-value capture, but the sources differ.
  The 3.4 variant here hooks `wlc_bmac_suspend_mac_and_wait`, `enable_mac`,
  `switch_macfreq` and `core_phy_clk`, which neither variant of `b43-ac-wip`
  hooks; the 2.6.30 variant here, the one for the DSL-3580L, has none of them
  either.
- **`reverse-tools/strip_other_core.py`** separates the two cores in a capture
  that has both, by the OTP reads that open each attach and by five
  registers only the N-PHY writes (`0x078`, `0x08f`, `0x0a5`, `0x0a6`,
  `0x0a7`). It is how `router-data/d6220/` was extracted.
