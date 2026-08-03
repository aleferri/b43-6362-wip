# Enumerazione del backplane WLAN sul BCM6362

Il core 802.11 del 6362 non è su PCI: sta su un backplane AXI/OCP interno al
SoC, enumerabile da bcma. Mainline non lo tocca (`arch/mips/bcm63xx` non ha
nulla di wireless, e il target `bmips` di OpenWrt non ha nodo DT per la
wireless integrata). Il glue vive quindi qui, in `patches/bcma/`.

## Perché il `bcma_host_soc` generico non basta

Due differenze rispetto alla famiglia BCM47xx per cui `host_soc.c` è stato
scritto, entrambe verificate sul silicio dal funzionamento del driver:

1. i registri del backplane sono periferiche **big-endian** su CPU big-endian:
   `readl()` restituisce word scambiate, serve `ioread32be()`;
2. ChipCommon, il core 802.11 e il core SHIM **non pubblicano wrapper DMP**
   (NMW=NSW=0 nell'EROM): `bcma_get_next_core()` li rifiuterebbe, e gli accessi
   `BCMA_IOCTL`/`BCMA_RESET_CTL` vanno sintetizzati su una finestra di controllo
   a livello SoC.

Da qui i due campi `big_endian` e `wrapperless` su `struct bcma_bus` (patch
0001) e un host driver dedicato (patch 0002) invece di allargare quello
generico.

## Mappa, dai sorgenti mainline

Tutto quanto segue è già definito in mainline e non va inventato:

| cosa | valore | dove |
|---|---|---|
| ChipCommon WLAN | `0xb0004000` (fisico `0x10004000`) | `arch/mips/include/asm/mach-bcm63xx/bcm63xx_cpu.h` |
| d11 WLAN | `0xb0005000` | idem |
| SHIM WLAN | `0xb0007000` | idem |
| IRQ | `IRQ_INTERNAL_BASE + 7` | idem |
| clock gate | `CKCTL_6362_WLAN_OCP_EN` (bit 5) = `BCM6362_CLK_WLAN_OCP` | `bcm63xx_regs.h`, `dt-bindings/clock/bcm6362-clock.h` |
| reset | `BCM6362_RST_WLAN_SHIM` (11), `BCM6362_RST_WLAN_UBUS` (14) | `dt-bindings/reset/bcm6362-reset.h` |
| power domain | `BCM6362_POWER_DOMAIN_WLAN_PADS` (13) | `dt-bindings/soc/bcm6362-pm.h` |
| core SHIM | `BCMA_CORE_SHIM` = `0x837` | `include/linux/bcma/bcma.h` (commento: "SHIM component in ubus/6362") |

Il nodo DT usa due finestre: `ccb` = `0x10004000` (ChipCommon, da cui bcma
scansiona l'EROM) e `wlan-ctrl` = `0x10007000` (finestra di controllo SoC).

## Finestra di controllo

Registri usati dall'host driver (offset dalla finestra `wlan-ctrl`):

| off | nome | bit noti |
|---|---|---|
| 0x00 | MISC | `FORCE_CLK_ON` (2), `MACRO_DISABLE` (1), `MACRO_SOFT_RESET` (0) |
| 0x04 | STATUS | — |
| 0x08 | CC_CONTROL | IOCTL nei 16 bit bassi, RESET_CTL promosso a bit 16 |
| 0x0c | CC_STATUS | — |
| 0x10 | MAC_CONTROL | `SICF_FGC` (1), `SICF_CLOCK_EN` (0), + IOCTL/RESET come sopra |
| 0x14 | MAC_STATUS | — |
| 0x18 | CC_ID_A | id ChipCommon (diagnostica di bring-up) |
| 0x24 | MAC_ID_A | id core 802.11 (diagnostica di bring-up) |

`BCMA_IOST` per il core 802.11 è sintetizzato (`2G_PHY=1`, `5G_PHY=0`,
`DMA64`) perché MacStatus non è affidabile mentre il d11 è in reset. Nota che
b43 usa quel valore solo come primo tentativo e poi lo sovrascrive dal
`dev_id` della SPROM: vedi `gap-inventory.md`.

## Sequenza di bring-up

Il boot loader lascia la macro gated e in reset. L'ordine implementato:

1. `clk_prepare_enable` (wlan_ocp), attesa 10 ms;
2. assert `wlan-ubus` + `wlan`, 1 ms, deassert entrambi, 1 ms;
3. MISC = `FORCE_CLK_ON | MACRO_SOFT_RESET`, 1 ms;
4. MAC_CONTROL = `SICF_FGC | SICF_CLOCK_EN`;
5. MISC = `FORCE_CLK_ON` (rilascia il soft reset tenendo il clock forzato);
6. MISC = 0, MAC_CONTROL = `SICF_CLOCK_EN`;
7. log di `CcIdA`/`MacIdA`, poi `bcma_init_bus()` + `bcma_bus_register()`.

Lo teardown rimette la macro in `MACRO_DISABLE | MACRO_SOFT_RESET`, riasserta i
reset e spegne il clock: senza questo un `rmmod`/`insmod` di bcma riparte da uno
stato sporco.

## SPROM

Il core su SoC non ha SPROM né OTP utile: i parametri arrivano da un blob di
riferimento più fixup per board. Nel fork questo passa dal driver
`brcm,bcma-sprom` di OpenWrt esteso al match per phandle (`bcma-bus = <&wlan>`),
con `brcm/bcm6362-sprom.bin` + 38 fixup ricavati per diff da `wl srdump`.
Mainline non ha nessun meccanismo DT equivalente: è il punto aperto principale,
trattato in `upstreaming.md`.
