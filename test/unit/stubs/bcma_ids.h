/* SPDX-License-Identifier: GPL-2.0
 * Le sole define bcma/ssb che i sorgenti N-PHY citano, copiate dai rispettivi
 * header del kernel. Elenco generato: se il driver ne cita una nuova, il build
 * si ferma e la si aggiunge.
 */
#ifndef _TEST_BCMA_IDS_H
#define _TEST_BCMA_IDS_H

#define BCMA_BOARD_TYPE_BCM943224M93     0X008B
#define BCMA_CC_CHIPCTL                  0x0028
#define BCMA_CHIP_ID_BCM43224            43224
#define BCMA_CHIP_ID_BCM43225            43225
#define BCMA_CHIP_ID_BCM43421            43421
#define BCMA_CHIP_ID_BCM4716             0x4716
#define BCMA_CHIP_ID_BCM47162            47162
#define BCMA_PKG_ID_BCM43224_FAB_SMIC    0xa
#define SSB_BOARD_CB2_4321               0x046D
#define SSB_CHIPCO_CHIPCTL               0x0028

/* SSB_BUSTYPE_PCI e' un valore di enum in ssb.h, non una define */
#define SSB_BUSTYPE_PCI                  1

#endif
