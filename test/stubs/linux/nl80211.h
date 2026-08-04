/* SPDX-License-Identifier: GPL-2.0
 * Minimo di <linux/nl80211.h> per il build in userspace: solo le enum che i
 * sorgenti N-PHY usano davvero. Serve a impedire che phy_common.h peschi
 * l'header di sistema, che collide coi tipi __u32 del kernel.
 */
#ifndef _TEST_LINUX_NL80211_H
#define _TEST_LINUX_NL80211_H

enum nl80211_band {
	NL80211_BAND_2GHZ = 0,
	NL80211_BAND_5GHZ = 1,
	NL80211_BAND_60GHZ = 2,
	NUM_NL80211_BANDS,
};

enum nl80211_channel_type {
	NL80211_CHAN_NO_HT = 0,
	NL80211_CHAN_HT20,
	NL80211_CHAN_HT40MINUS,
	NL80211_CHAN_HT40PLUS,
};

enum nl80211_chan_width {
	NL80211_CHAN_WIDTH_20_NOHT = 0,
	NL80211_CHAN_WIDTH_20,
	NL80211_CHAN_WIDTH_40,
	NL80211_CHAN_WIDTH_80,
	NL80211_CHAN_WIDTH_80P80,
	NL80211_CHAN_WIDTH_160,
};

#endif
