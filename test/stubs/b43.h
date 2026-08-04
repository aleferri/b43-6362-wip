/* SPDX-License-Identifier: GPL-2.0
 *
 * Minimo di b43.h per il build in userspace dei sorgenti N-PHY. Il b43.h vero
 * tira dentro spinlock, bcma, ssb, ieee80211: qui servono solo i tipi che
 * phy_n.c, radio_2057.c e tables_nphy.c toccano davvero, piu' i prototipi
 * degli accessor, che al link vengono sostituiti dallo shim in wrap.c.
 *
 * struct ssb_sprom sta in sprom.h, copiata verbatim dal kernel: i nomi dei
 * campi devono combaciare con quelli che il driver legge.
 *
 * Le struct qui sono ridotte ai soli campi usati, e la riduzione e' verificata
 * dal compilatore: se il driver ne tocca uno che manca, il build si ferma.
 */
#ifndef _TEST_B43_H
#define _TEST_B43_H

#include <linux/types.h>
#include <linux/kernel.h>
#include <linux/nl80211.h>

#include "sprom.h"
#include "bcma_ids.h"
#include "b43_defs.h"

enum b43_bus_type {
	B43_BUS_SSB = 0,
	B43_BUS_BCMA = 1,
};

/* Catena bcma ridotta: al PHY serve arrivare a dev->dev->bdev->bus->drv_cc per
 * i tre accessi a ChipCommon che fa nel ramo CONFIG_B43_BCMA. */
struct bcma_drv_cc {
	int dummy;
};

struct bcma_bus {
	struct bcma_drv_cc drv_cc;
};

struct bcma_device {
	struct bcma_bus *bus;
};

struct ssb_device;

void bcma_chipco_gpio_control(struct bcma_drv_cc *cc, u32 mask, u32 value);
void bcma_cc_set32_stub(struct bcma_drv_cc *cc, u16 offset, u32 set);
void bcma_pmu_spuravoid_pllupdate(struct bcma_drv_cc *cc, int spuravoid);
#define bcma_cc_set32(cc, offset, set) bcma_cc_set32_stub(cc, offset, set)

struct b43_bus_dev {
	enum b43_bus_type bus_type;
	union {
		struct bcma_device *bdev;
		struct ssb_device *sdev;
	};

	u16 board_vendor;
	u16 board_type;
	u16 board_rev;

	u16 chip_id;
	u8 chip_rev;
	u8 chip_pkg;

	struct ssb_sprom *bus_sprom;

	u16 core_id;
	u8 core_rev;
};

/* mac80211, ridotto ai campi che il PHY guarda */
#define IEEE80211_CHAN_NO_IR	(1 << 1)

struct ieee80211_channel {
	enum nl80211_band band;
	u16 center_freq;
	u8 hw_value;
	u32 flags;
	int max_power;
};

struct cfg80211_chan_def {
	struct ieee80211_channel *chan;
	enum nl80211_chan_width width;
	u32 center_freq1;
};

#define PCI_VENDOR_ID_BROADCOM	0x14e4

struct ieee80211_conf {
	struct cfg80211_chan_def chandef;
};

struct ieee80211_hw {
	struct ieee80211_conf conf;
};

struct b43_wl {
	struct ieee80211_hw *hw;
	bool radiotap_enabled;
};

#include "phy_common.h"

struct b43_wldev {
	struct b43_bus_dev *dev;
	struct b43_wl *wl;
	struct b43_phy phy;

	u16 device;
	int status;
};

static inline int b43_status(struct b43_wldev *dev)
{
	return dev->status;
}

/* Le macro Q5.2 di b43.h: non hanno il prefisso B43_, quindi il generatore di
 * b43_defs.h non le prende. */
#define INT_TO_Q52(i)	((i) << 2)
#define Q52_TO_INT(q52)	((q52) >> 2)

/* --- diagnostica --- */
#define B43_DEBUG 0
#define B43_WARN_ON(x) ({ int __w = !!(x); __w; })
#define b43err(wl, fmt, ...)	b43_test_log("ERR", fmt, ##__VA_ARGS__)
#define b43warn(wl, fmt, ...)	b43_test_log("WARN", fmt, ##__VA_ARGS__)
#define b43info(wl, fmt, ...)	b43_test_log("INFO", fmt, ##__VA_ARGS__)
#define b43dbg(wl, fmt, ...)	do { } while (0)
void b43_test_log(const char *lvl, const char *fmt, ...);

enum b43_verbosity { B43_VERBOSITY_ERROR, B43_VERBOSITY_WARN,
		     B43_VERBOSITY_INFO, B43_VERBOSITY_DEBUG };
enum b43_dyndbg { B43_DBG_XMITPOWER, B43_DBG_LO, B43_DBG_FIRMWARE,
		  B43_DBG_KEYS, B43_DBG_VERBOSESTATS, B43_NR_DYNDBG };
static inline bool b43_debug(struct b43_wldev *dev, enum b43_dyndbg f)
{
	return false;
}

/* --- accessor MMIO, MAC e host flags: intercettati al link --- */
u16 b43_read16(struct b43_wldev *dev, u16 offset);
void b43_write16(struct b43_wldev *dev, u16 offset, u16 value);
u32 b43_read32(struct b43_wldev *dev, u16 offset);
void b43_write32(struct b43_wldev *dev, u16 offset, u32 value);
void b43_maskset16(struct b43_wldev *dev, u16 offset, u16 mask, u16 set);
void b43_maskset32(struct b43_wldev *dev, u16 offset, u32 mask, u32 set);
static inline void b43_write16f(struct b43_wldev *dev, u16 offset, u16 value)
{
	b43_write16(dev, offset, value);
}

void b43_mac_suspend(struct b43_wldev *dev);
void b43_mac_enable(struct b43_wldev *dev);
void b43_mac_phy_clock_set(struct b43_wldev *dev, bool on);
void b43_mac_switch_freq(struct b43_wldev *dev, u8 spurmode);
u16 b43_shm_read16(struct b43_wldev *dev, u16 routing, u16 offset);
u32 b43_shm_read32(struct b43_wldev *dev, u16 routing, u16 offset);
void b43_shm_write16(struct b43_wldev *dev, u16 routing, u16 offset, u16 value);
void b43_shm_write32(struct b43_wldev *dev, u16 routing, u16 offset, u32 value);
/* Definite in wrap.c: senza il prototipo il chiamante le vede tornare int, e
 * -Werror=implicit-function-declaration lo prende come l'errore che e'. */
enum nl80211_band b43_current_band(struct b43_wl *wl);
enum nl80211_channel_type cfg80211_get_chandef_type(
				const struct cfg80211_chan_def *chandef);
void b43_wireless_core_phy_pll_reset(struct b43_wldev *dev);

u64 b43_hf_read(struct b43_wldev *dev);
void b43_hf_write(struct b43_wldev *dev, u64 value);
void b43_dummy_transmission(struct b43_wldev *dev, bool ofdm, bool pa_on);
int b43_switch_channel(struct b43_wldev *dev, unsigned int new_channel);

#endif /* _TEST_B43_H */
