# router-data/tg789vac-v2 — Technicolor TG789vac v2, wl0

A BCM63168 gateway whose `wl0` is the same WLAN core as the BCM6362's:
`BCM435f` (`dev_id 0x435f`) on the SoC bus (`sb/0/`), driven by `wl`
**7.14.89.14** (`cpe4.16L03.0-kdb`) instead of the DSL-3580L's 6.30.102.7.
Its `wl1`, a BCM4360, is what `b43-ac-wip` traces; these two files are the
part of that board's data that concerns the N core.

| file | content |
|---|---|
| `wl0_srom_raw.txt` | `wl -i wl0 srdump`: 220 words, SROM rev 8, `boardtype 0x0566` |
| `dmesg-wl.txt` | `dmesg \| grep wl` at boot, both instances |

Source: `aleferri/b43-ac-wip` at `01e1329`, `router-data/tg789vac-v2/`, copied
unchanged.

## What the two files say about the N core

The driver finds neither SROM nor OTP for wl0 and builds the SROM image from a
file: `srom/otp not programmed, using main memory mapped srom info`, then
`loading /etc/wlan/bcm6362_map.bin` and `bcmcmn_nvramvars.bin`. The map file is
named after the 6362 on a 63168 board.

Against `../dsl3580l/srdump.txt` the image differs in **38 of 220 words**, all
of them power data (names from `include/linux/ssb/ssb_regs.h` at `848acc8ffe1b`):

| words | field |
|---|---|
| 79, 80 | `SSB_SPROM8_AGAIN01`, `SSB_SPROM8_AGAIN23` |
| 96-110 | core 0 power info: `MAXP_BG`, `PA0B0..2`, `PA1*` |
| 112-126 | core 1 power info, same layout at `0xE0` |
| 161, 162 | `SSB_SPROM8_OFDM2GPO` |
| 169-176 | `SSB_SPROM8_2G_MCSPO` |

The other 182 words are identical, `boardtype`, `boardflags` and the header
included. This is data for `docs/upstreaming.md`, "La SPROM": two boards with
this core share everything but the power calibration.
