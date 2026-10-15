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
of them power data (names from `include/linux/ssb/ssb_regs.h` at `848acc8ffe1b`, unchanged at `045958acaa75`):

| words | field |
|---|---|
| 79, 80 | `SSB_SPROM8_AGAIN01`, `SSB_SPROM8_AGAIN23` |
| 96-110 | core 0 power info: `MAXP_BG`, `PA0B0..2`, `PA1*` |
| 112-126 | core 1 power info, same layout at `0xE0` |
| 161, 162 | `SSB_SPROM8_OFDM2GPO` |
| 169-176 | `SSB_SPROM8_2G_MCSPO` |

The other 182 words are identical, `boardtype`, `boardflags` and the header
included. This is data for `docs/upstreaming.md`, "The SPROM": two boards with
this core share everything but the power calibration.

## Against the image OpenWrt serves

The fork serves this core `bcm6362-sprom.bin` from `openwrt/broadcom-sprom`
(`d36f7fc`, "Import SPROMs from bmips fixups"; not copied here): 440 bytes,
220 big-endian words. It is neither board's image:

| against | words that differ | which |
|---|---|---|
| DSL-3580L `srdump.txt` | 37 | 96-126 (both cores' power info), 160-162, 169-176 |
| this `wl0_srom_raw.txt` | 21 | 79, 80, 96-99, 112-115, 160-162, 169-176 |

Power data again, and nothing else. Of the 38 words in which the two boards
differ, the reference image agrees with this board on 18, with the DSL-3580L on
2, and with neither on 18.

**None of the three images has a valid CRC.** All three end in `0xb908`, i.e.
revision 8 and CRC `0xb9`, while the contents differ; recomputed with
`bcma_sprom_crc()` of `drivers/bcma/sprom.c`, the CRC is `0x22` for the
DSL-3580L, `0xff` for this board and `0x37` for the reference image. The same
routine validates the DSL-3580L's PCIe card (`wl1`, rev 11, `0x2f` stored and
computed, `b43-ac-wip`'s `router-data/dsl3580l/wl1_srom_raw.txt`), so it is not
the routine. The stock driver builds these images from a map file and leaves the
CRC word as the map has it; see `docs/upstreaming.md` for what that means for a
SPROM served from DT.
