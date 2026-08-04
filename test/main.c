/* SPDX-License-Identifier: GPL-2.0
 *
 * Monta un `struct b43_wldev` finto con la configurazione della board e lancia
 * uno dei flow pubblici del driver N-PHY, cioe' una delle voci di
 * b43_phyops_n. L'output e' un trace nel formato di wl-diag decodificato, da
 * dare a compare.py contro la cattura vendor.
 *
 *   ./nphy_trace init     dsl3580l
 *   ./nphy_trace chanset  dsl3580l 6
 *   ./nphy_trace rfkill   dsl3580l
 *
 * I valori della board vengono dalla SPROM letta sul device
 * (router-data/dsl-3580l/srdump.txt): quelli che il PHY guarda sono pochi, e
 * sono elencati qui sotto uno per uno invece di caricare un dump binario, cosi'
 * si vede subito cosa influenza il flow.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "b43.h"
#include "phy_n.h"
#include "test_harness.h"

/* Generato da reverse-tools/gen_readplans.py dalla cattura: i valori che
 * l'hardware ha restituito, per indirizzo. Senza, le read tornano il mirror e i
 * loop guidati dallo stato fanno un giro e finiscono. B43_TEST_NOPLANS=1
 * nell'ambiente li disattiva, che serve a misurare la differenza. */
#include "readplans_init.h"

extern const struct b43_phy_operations b43_phyops_n;

struct board {
	const char *name;
	u16 chip_id;
	u8 chip_rev;
	u8 core_rev;
	u16 dev_id;
	u8 phy_rev;
	u8 radio_rev;
	u16 radio_ver;
	u8 sprom_rev;
	u32 boardflags_lo;
	u16 boardflags_hi;
	u16 boardflags2_lo;
	u16 boardflags2_hi;
	u8 fem_tssipos;
	u8 fem_extpa_gain;
	u8 fem_pdet_range;
	u8 fem_tr_iso;
	u8 fem_antswlut;
};

/* BCM6362 integrato della DSL-3580L: d11 rev 22, N-PHY rev 8, radio 2057
 * rev 8. dev_id 0x435f e' quello che il fixup SPROM mette per far riconoscere
 * il chip a b43. */
static const struct board boards[] = {
	{
		.name = "dsl3580l",
		.chip_id = 0x6362,
		.chip_rev = 1,
		.core_rev = 22,
		.dev_id = 0x435f,
		.phy_rev = 8,
		.radio_rev = 8,
		.radio_ver = 0x2057,
		/* Decodificati dalla SROM del device
		 * (router-data/dsl-3580l/srdump.txt) agli offset di
		 * SSB_SPROM8_*: rev 8, boardflags_lo 0x0200, fem2g 0x0315.
		 * extpa_gain = 2 e' cio' che accende ipa2g_on, quindi il PHY
		 * prende il percorso PA interno: con 0 il flow chiedeva la
		 * tabella EPA e si fermava. */
		.sprom_rev = 8,
		.boardflags_lo = 0x0200,
		.boardflags_hi = 0x0000,
		.boardflags2_lo = 0x0000,
		.boardflags2_hi = 0x0000,
		.fem_tssipos = 1,
		.fem_extpa_gain = 2,
		.fem_pdet_range = 2,
		.fem_tr_iso = 3,
		.fem_antswlut = 0,
	},
};

static struct ssb_sprom sprom;
static struct b43_bus_dev bus;
static struct b43_wl wl;
static struct ieee80211_hw hw;
static struct ieee80211_channel chan;
static struct b43_wldev dev;
static struct bcma_bus bcma_bus;
static struct bcma_device bcma_dev;

static void setup(const struct board *b, unsigned int channel)
{
	memset(&sprom, 0, sizeof(sprom));
	memset(&bus, 0, sizeof(bus));
	memset(&wl, 0, sizeof(wl));
	memset(&hw, 0, sizeof(hw));
	memset(&dev, 0, sizeof(dev));

	sprom.revision = b->sprom_rev;
	sprom.dev_id = b->dev_id;
	sprom.boardflags_lo = b->boardflags_lo;
	sprom.boardflags_hi = b->boardflags_hi;
	sprom.boardflags2_lo = b->boardflags2_lo;
	sprom.boardflags2_hi = b->boardflags2_hi;
	sprom.fem.ghz2.tssipos = b->fem_tssipos;
	sprom.fem.ghz2.extpa_gain = b->fem_extpa_gain;
	sprom.fem.ghz2.pdet_range = b->fem_pdet_range;
	sprom.fem.ghz2.tr_iso = b->fem_tr_iso;
	sprom.fem.ghz2.antswlut = b->fem_antswlut;

	memset(&bcma_bus, 0, sizeof(bcma_bus));
	memset(&bcma_dev, 0, sizeof(bcma_dev));
	bcma_dev.bus = &bcma_bus;

	bus.bus_type = B43_BUS_BCMA;
	bus.bdev = &bcma_dev;
	bus.chip_id = b->chip_id;
	bus.chip_rev = b->chip_rev;
	bus.core_rev = b->core_rev;
	bus.bus_sprom = &sprom;

	chan.band = NL80211_BAND_2GHZ;
	chan.center_freq = channel == 14 ? 2484 : 2412 + (channel - 1) * 5;
	chan.hw_value = channel;
	/* mac80211 lo riempie dal regulatory; serve a recalc_txpower, che senza
	 * finisce a applicare il minimo e non dice nulla di utile. */
	chan.max_power = 20;

	hw.conf.chandef.chan = &chan;
	hw.conf.chandef.width = NL80211_CHAN_WIDTH_20;
	hw.conf.chandef.center_freq1 = chan.center_freq;
	wl.hw = &hw;

	dev.dev = &bus;
	dev.wl = &wl;
	dev.device = b->dev_id;
	dev.status = B43_STAT_INITIALIZED;

	dev.phy.ops = &b43_phyops_n;
	dev.phy.type = B43_PHYTYPE_N;
	dev.phy.rev = b->phy_rev;
	dev.phy.radio_ver = b->radio_ver;
	dev.phy.radio_rev = b->radio_rev;
	dev.phy.radio_manuf = 0x17f;
	dev.phy.analog = 4;
	dev.phy.supports_2ghz = true;
	dev.phy.supports_5ghz = false;
	dev.phy.gmode = true;
	dev.phy.do_full_init = true;
	dev.phy.radio_on = true;
	dev.phy.channel = channel;
	dev.phy.chandef = &hw.conf.chandef;
	dev.phy.desired_txpower = 20;
}

static int flow_init(void)
{
	int err;

	err = b43_phyops_n.allocate(&dev);
	if (err) {
		fprintf(stderr, "allocate: %d\n", err);
		return err;
	}
	b43_phyops_n.prepare_structs(&dev);
	err = b43_phyops_n.init(&dev);
	if (err)
		fprintf(stderr, "init: %d\n", err);
	return err;
}

/* mac80211 aggiorna hw->conf.chandef PRIMA di chiamare l'op, e il driver legge
 * la frequenza da lì: b43_nphy_op_switch_channel() usa
 * dev->wl->hw->conf.chandef.chan e l'argomento new_channel. Senza aggiornare il
 * chandef il port programma la chantab del canale vecchio -- ci sono cascato, e
 * il confronto col trace vendor l'ha fatto vedere subito (0x16 e 0x2c, cioe'
 * vcocal e mmd0, con i valori di 2412 invece di 2437). */
static void set_channel(unsigned int channel)
{
	chan.center_freq = channel == 14 ? 2484 : 2412 + (channel - 1) * 5;
	chan.hw_value = channel;
	hw.conf.chandef.center_freq1 = chan.center_freq;
	dev.phy.channel = channel;
}

static int flow_chanset(unsigned int channel)
{
	int err = flow_init();

	if (err)
		return err;
	fprintf(stderr, "--- init finita, cambio a canale %u ---\n", channel);
	set_channel(channel);
	printf("cpu0 CHANSPEC ch=%u\n", channel);
	return b43_phyops_n.switch_channel(&dev, channel);
}

/* Il TX power control: b43_nphy_op_recalc_txpower() e' l'unico ingresso
 * pubblico che arriva a b43_nphy_tx_power_ctl_setup(), cioe' alle tabelle 26 e
 * 27 (CORE1/CORE2_TXPWRCTL), che nel flow init non vengono toccate. */
static int flow_txpower(void)
{
	int err = flow_init();

	if (err)
		return err;
	fprintf(stderr, "--- init finita, recalc_txpower ---\n");
	err = b43_phyops_n.recalc_txpower(&dev, true);
	fprintf(stderr, "recalc_txpower: %d\n", err);
	return 0;
}

/* Calibrazioni. b43_nphy_op_prepare_structs() mette perical = 2 con il commento
 * "avoid additional rssi cal on init (like wl)", e quel valore salta anche il
 * ramo tx iq/lo + rx iq dentro l'init. La cattura vendor invece scrive la
 * tabella 15 (IQLOCAL) durante l'init, quindi vale la pena poter girare anche
 * con la cal accesa e confrontare: questo flow la accende dopo
 * prepare_structs, senza toccare il driver. */
static int flow_initcal(void)
{
	int err;

	err = b43_phyops_n.allocate(&dev);
	if (err)
		return err;
	b43_phyops_n.prepare_structs(&dev);
	dev.phy.n->perical = 0;
	fprintf(stderr, "--- init con perical=0 (cal accesa) ---\n");
	err = b43_phyops_n.init(&dev);
	if (err)
		fprintf(stderr, "init: %d\n", err);
	return err;
}

/* La corsa piu' lunga che il driver permette dagli ingressi pubblici: init con
 * la cal accesa, poi il TX power control, poi un cambio canale. Serve a misurare
 * quanta parte dell'init vendor il port copre, non a riprodurre una sequenza
 * reale: sul device queste cose non arrivano una dietro l'altra. */
static int flow_initcal(void);

static int flow_full(unsigned int channel)
{
	int err = flow_initcal();

	if (err)
		return err;
	fprintf(stderr, "--- recalc_txpower ---\n");
	b43_phyops_n.recalc_txpower(&dev, true);
	fprintf(stderr, "--- cambio a canale %u ---\n", channel);
	set_channel(channel);
	printf("cpu0 CHANSPEC ch=%u\n", channel);
	return b43_phyops_n.switch_channel(&dev, channel);
}

static int flow_rfkill(void)
{
	int err = flow_init();

	if (err)
		return err;
	b43_phyops_n.software_rfkill(&dev, true);
	b43_phyops_n.software_rfkill(&dev, false);
	return 0;
}

int main(int argc, char **argv)
{
	const char *flow = argc > 1 ? argv[1] : "init";
	const char *board = argc > 2 ? argv[2] : "dsl3580l";
	unsigned int channel = argc > 3 ? (unsigned int)atoi(argv[3]) : 1;
	const struct board *b = NULL;
	size_t i;
	int err;

	for (i = 0; i < sizeof(boards) / sizeof(boards[0]); i++) {
		if (!strcmp(boards[i].name, board))
			b = &boards[i];
	}
	if (!b) {
		fprintf(stderr, "board sconosciuta: %s\n", board);
		return 2;
	}

	setup(b, strcmp(flow, "chanset") ? channel : 1);
	b43_test_plans_reset();
	if (!getenv("B43_TEST_NOPLANS")) {
		b43_test_load_readplans();
		fprintf(stderr, "piani di lettura caricati\n");
	}

	if (!strcmp(flow, "init"))
		err = flow_init();
	else if (!strcmp(flow, "chanset"))
		err = flow_chanset(channel);
	else if (!strcmp(flow, "rfkill"))
		err = flow_rfkill();
	else if (!strcmp(flow, "txpower"))
		err = flow_txpower();
	else if (!strcmp(flow, "initcal"))
		err = flow_initcal();
	else if (!strcmp(flow, "full"))
		err = flow_full(channel > 1 ? channel : 6);
	else {
		fprintf(stderr, "flow sconosciuto: %s\n", flow);
		return 2;
	}

	fflush(stdout);
	b43_test_plans_report(stderr);
	return err ? 1 : 0;
}
