# Upstream status

Checked on the `torvalds/linux` tree @ `045958acaa75` (15 Oct 2026, 7.3-rc7),
not on changelogs or wikis.

## Since the previous pin, `848acc8ffe1b` (7.2-rc6)

Nothing of N-PHY rev 8 was merged, and none of the twelve in `patches/mainline/`:
`phy_n.c`, `tables_nphy.c`, `radio_2057.c` and the rest of the files in `b43/` are
byte for byte the same, and the twelve apply as before. Near the port, upstream
changed two things:

- `b43/debugfs.c`: page allocations replaced by `kzalloc()`. Not touched by the
  port.
- **bcma GPIO**: `bcma_gpio_init()` now registers a software node, `bcma-gpio`,
  as the GPIO chip's fwnode for a bus with `BCMA_HOSTTYPE_SOC` that has no
  firmware node of its own, under the assumption that there is only one SoC bus
  in the system; `bcma.h` gains `bcma_gpio_swnode`. The BCM6362 host driver
  (`patches/0002`) registers its bus as `BCMA_HOSTTYPE_SOC`, so with
  `CONFIG_BCMA_DRIVER_GPIO` its ChipCommon GPIO chip takes that node. On a
  BCM6362 there is no other bcma SoC bus, so the assumption holds; it is a point
  for the cover letter of the bcma series, see `upstreaming.md`.

## Merged (10 June 2026)

Series "b43: complete N-PHY rev 8 + radio 2057 rev 8 support", 7 patches:

| sha | title | files touched |
|---|---|---|
| `682edc28b91c` | b43: add firmware mappings for rev22 | `main.c` |
| `ee81dc7636fb` | b43: add d11 core revision 0x16 to id table | `main.c` |
| `2691a1ae6bcc` | b43: route d11 corerev 22 to 24-bit indirect radio access | `main.c` |
| `454518d95d07` | b43: support radio 2057 rev 8 | `radio_2057.c`, `main.c` |
| `894f1482b2f9` | b43: add IPA TX gain table for N-PHY r8 + radio 2057 r8 | `tables_nphy.c` |
| `631c004e5f45` | b43: add channel info table for N-PHY r8 + radio 2057 r8 | `radio_2057.c` |
| `21352612198c` | b43: add RF power offset for N-PHY r8 + radio 2057 r8 | `tables_nphy.c` |

The three tables (IPA TX gain, chan info, RF power offset) did **not** exist
in b43 before: they come from this series.

**None of the seven touches `phy_n.c`.** The list of files is `main.c`,
`radio_2057.c`, `tables_nphy.c` and nothing else; `2691a1ae6bcc` changes five
lines of `b43_phy_versioning()` in `main.c`. It matters when a defect is found
in `phy_n.c`: it does not come from this series. Checked by downloading the
seven commits:

```sh
for s in 682edc28b91c ee81dc7636fb 2691a1ae6bcc 454518d95d07 \
         894f1482b2f9 631c004e5f45 21352612198c; do
    curl -sL "https://github.com/torvalds/linux/commit/$s.patch" |
        grep '^+++ b/'
done
```

Also checkable with:

```sh
curl -s "https://github.com/torvalds/linux/commits/master/drivers/net/wireless/broadcom/b43/tables_nphy.c.atom"
```

In the fork's OpenWrt `bmips` target the same patches are backported as
`package/kernel/mac80211/patches/brcm/840-01..07`, needed as long as the target
is on kernel 6.12. They become redundant at the first bump to >= 6.16.

## Not merged, working out of tree

`patches/0001..0003`: the backplane enumeration. See `soc-glue.md` for the
contents and `upstreaming.md` for the obstacles.

## Not merged, written here and never run on hardware

There are thirty-six, in `b43/` while it is being built, with their messages in
`patches/b43/MESSAGES.md`: the list with the state of each entry is in the table
of `README.md` and the detail in `gap-inventory.md`. `b43/` also contains
`patches/mainline/` and builds in the harness, which checks it against the
capture. Two deserve a line of their own:

| series entry | what it does | state |
|---|---|---|
| `MESSAGES.md#0001` | programs the RX gain control for radio 2057 rev 8 at 2.4 GHz bw20, on the capture's values | checked op for op in the harness (`gain-control` window, 87/87), **never run on hardware**; gate `docs/reports/30-rx-sensitivity.md` |
| `MESSAGES.md#0002` | brings the rev 8 power offsets to the vendor's rev 7 values | **closed by the capture**: the rev 7 values predict 128 cells of 128, the in-tree ones 5 (`rf-pwr-offset-rev8.md`). It is no longer dead code, `0003` enables the path that reads it |

`0001` is not to be sent before the RX sensitivity measurement. It has already
changed shape once: it was written on brcmsmac, the capture showed different
values (`trace-init-2g.md`).

## Not existing anywhere

HT support in b43. No occurrence of `ht_cap` or `IEEE80211_HT` in the driver;
`b43_band_2GHz` exposes only `b43_g_ratetable`. See `ht20-mimo-plan.md`.
