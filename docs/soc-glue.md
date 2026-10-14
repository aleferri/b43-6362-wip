# Enumeration of the WLAN backplane on the BCM6362

The 6362's 802.11 core is not on PCI: it sits on an AXI/OCP backplane inside the
SoC, which bcma can enumerate. Mainline does not touch it (`arch/mips/bcm63xx`
has nothing wireless, and OpenWrt's `bmips` target has no DT node for the
integrated wireless). So the glue lives here: the files in `bcma/`, and the
series generated from them in `patches/0001-0003`.

## Why the generic `bcma_host_soc` is not enough

Two differences from the BCM47xx family `host_soc.c` was written for, both
verified on silicon by the driver working:

1. the backplane registers are **big-endian** peripherals on a big-endian CPU:
   `readl()` returns swapped words, `ioread32be()` is needed;
2. ChipCommon, the 802.11 core and the SHIM core **publish no DMP wrapper**
   (NMW=NSW=0 in the EROM): `bcma_get_next_core()` would reject them, and the
   `BCMA_IOCTL`/`BCMA_RESET_CTL` accesses have to be synthesised on a SoC-level
   control window.

Hence the two fields `big_endian` and `wrapperless` on `struct bcma_bus` (patch
0001) and a dedicated host driver (patch 0002) instead of widening the generic
one.

## Map, from the mainline sources

Everything below is already defined in mainline and is not to be invented:

| what | value | where |
|---|---|---|
| WLAN ChipCommon | `0xb0004000` (physical `0x10004000`) | `arch/mips/include/asm/mach-bcm63xx/bcm63xx_cpu.h` |
| WLAN d11 | `0xb0005000` | same |
| WLAN SHIM | `0xb0007000` | same |
| IRQ | `IRQ_INTERNAL_BASE + 7` | same |
| clock gate | `CKCTL_6362_WLAN_OCP_EN` (bit 5) = `BCM6362_CLK_WLAN_OCP` | `bcm63xx_regs.h`, `dt-bindings/clock/bcm6362-clock.h` |
| reset | `BCM6362_RST_WLAN_SHIM` (11), `BCM6362_RST_WLAN_UBUS` (14) | `dt-bindings/reset/bcm6362-reset.h` |
| power domain | `BCM6362_POWER_DOMAIN_WLAN_PADS` (13) | `dt-bindings/soc/bcm6362-pm.h` |
| SHIM core | `BCMA_CORE_SHIM` = `0x837` | `include/linux/bcma/bcma.h` (comment: "SHIM component in ubus/6362") |

The DT node uses two windows: `ccb` = `0x10004000` (ChipCommon, from which bcma
scans the EROM) and `wlan-ctrl` = `0x10007000` (the SoC control window).

## Control window

Registers used by the host driver (offsets from the `wlan-ctrl` window):

| off | name | known bits |
|---|---|---|
| 0x00 | MISC | `FORCE_CLK_ON` (2), `MACRO_DISABLE` (1), `MACRO_SOFT_RESET` (0) |
| 0x04 | STATUS | — |
| 0x08 | CC_CONTROL | IOCTL in the low 16 bits, RESET_CTL promoted to bit 16 |
| 0x0c | CC_STATUS | — |
| 0x10 | MAC_CONTROL | `SICF_FGC` (1), `SICF_CLOCK_EN` (0), + IOCTL/RESET as above |
| 0x14 | MAC_STATUS | — |
| 0x18 | CC_ID_A | ChipCommon id (bring-up diagnostics) |
| 0x24 | MAC_ID_A | 802.11 core id (bring-up diagnostics) |

`BCMA_IOST` for the 802.11 core is synthesised (`2G_PHY=1`, `5G_PHY=0`,
`DMA64`) because MacStatus is not reliable while the d11 is in reset. Note that
b43 uses that value only as a first attempt and then overrides it from the
SPROM's `dev_id`: see `gap-inventory.md`.

## Bring-up sequence

The boot loader leaves the macro gated and in reset. The order implemented:

1. `clk_prepare_enable` (wlan_ocp), wait 10 ms;
2. assert `wlan-ubus` + `wlan`, 1 ms, deassert both, 1 ms;
3. MISC = `FORCE_CLK_ON | MACRO_SOFT_RESET`, 1 ms;
4. MAC_CONTROL = `SICF_FGC | SICF_CLOCK_EN`;
5. MISC = `FORCE_CLK_ON` (releases the soft reset keeping the clock forced);
6. MISC = 0, MAC_CONTROL = `SICF_CLOCK_EN`;
7. log of `CcIdA`/`MacIdA`, then `bcma_init_bus()` + `bcma_bus_register()`.

The teardown puts the macro back in `MACRO_DISABLE | MACRO_SOFT_RESET`,
reasserts the resets and turns the clock off: without it an `rmmod`/`insmod` of
bcma restarts from a dirty state.

## SPROM

The core on the SoC has no SPROM and no useful OTP: the parameters come from a
reference blob plus per-board fixups. In the fork this goes through OpenWrt's
`brcm,bcma-sprom` driver extended to match by phandle (`bcma-bus = <&wlan>`),
with `brcm/bcm6362-sprom.bin` + 38 fixups derived by diffing against
`wl srdump`. Mainline has no equivalent DT mechanism: it is the main open
point, dealt with in `upstreaming.md`. The stock `wl` on another board with this
core builds the image from a map file, `bcm6362_map.bin`
(`router-data/tg789vac-v2/README.md`).
