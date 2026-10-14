# Where b43 handles G and not N

The driver was born for the B/G PHYs and N came later, so there are places where
a branch exists only for G, or where a chain of `if`s on PHY types has no N
case. On the BCM6362 those places are missing behaviour, not just different
behaviour.

List generated with `reverse-tools/phy_type_audit.py --tree ~/src/pin`, which
groups the occurrences of `B43_PHYTYPE_*` by construct and flags those where G
appears and N does not. It skips the per-PHY files, where speaking of one type
only is correct. The block below is the tool's output, unchanged, checked again
at `848acc8ffe1b`; the line numbers are the pinned tree's, not `b43/`'s.

57 costrutti che discriminano sul tipo di PHY, fuori dai file per-PHY
20 citano G e non N

```
debugfs.c      loctls_read_file                   righe 434-434   tipi: G
lo.c           b43_lo_write                       righe 58-58   tipi: G
lo.c           lo_measure_setup                   righe 412-412   tipi: G
lo.c           lo_measure_setup                   righe 450-450   tipi: G
lo.c           lo_measure_setup                   righe 459-460   tipi: B G
lo.c           lo_measure_setup                   righe 469-469   tipi: G
lo.c           lo_measure_setup                   righe 477-480   tipi: B G
lo.c           lo_measure_restore                 righe 506-506   tipi: G
main.c         b43_calculate_link_quality         righe 1409-1409   tipi: G
main.c         handle_irq_noise                   righe 1429-1429   tipi: G
main.c         b43_wireless_core_init             righe 4875-4875   tipi: G
main.c         b43_supported_bands                righe 5353-5353   tipi: G
main.c         b43_wireless_core_attach           righe 5444-5446   tipi: G HT LP
sysfs.c        b43_attr_interfmode_show           righe 49-49   tipi: G
wa.c           b43_wa_msst                        righe 142-142   tipi: G
wa.c           b43_wa_all                         righe 336-336   tipi: G
xmit.c         b43_rssi_postprocess               righe 595-595   tipi: G
xmit.c         b43_rssi_postprocess               righe 608-608   tipi: G
xmit.c         b43_rx                             righe 734-736   tipi: B G LP
xmit.c         b43_rx                             righe 780-780   tipi: G
```

## What it means, entry by entry

**Legitimate, not holes.** `lo.c` (six entries) is the G-PHY's LO calibration:
the N has its own in `phy_n.c`, and the whole file does not concern it. `wa.c`
holds the G workarounds. `debugfs.c` and `sysfs.c` expose controls that exist
only on G (`loctls`, `interfmode`).

**Real holes, with a measurable consequence:**

| entry | consequence |
|---|---|
| `main.c b43_calculate_link_quality`, `handle_irq_noise` | **no noise floor measurement**: `link_noise` stays at its initial value and mac80211 receives a constant. Closed by `patches/b43/MESSAGES.md#0006` |
| `xmit.c b43_rssi_postprocess` (two entries) | the RSSI conversion has branches for G and for LP, not for N. To be looked at: it is the number that ends up in `ieee80211_rx_status.signal` |
| `xmit.c b43_rx` (two entries) | the decoding of the PLCP and of the flags has branches for B/G/LP. To be looked at together with the point above |
| `main.c b43_calculate_link_quality` (top half) | see noise |

**To be read before calling them holes:**

`main.c b43_wireless_core_init`, `b43_supported_bands`,
`b43_wireless_core_attach` name G among other types and have to be read in
context — `b43_supported_bands` is already an open entry of the inventory for
another reason (`dev_id 0x435f`). `ppr.c` and `phy_common.c` do not appear here
because they name N too, but that does not mean the N branch is complete: the
tool sees whether the case is there, not whether it is right.

## How to redo the measurement

```sh
./reverse-tools/phy_type_audit.py --tree ~/src/pin            # suspects only
./reverse-tools/phy_type_audit.py --tree ~/src/pin --all       # all 57
./reverse-tools/phy_type_audit.py --tree ~/src/pin --context   # with the lines
```
