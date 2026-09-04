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
#include "readplans_ch6.h"
#include "readplans_ch11.h"
/* Generato da reverse-tools/gen_seed.py: lo stato che op_init e rfkill lasciano
 * dietro, cioe" cio' che la finestra sotto misura non puo' avere. */
#include "seed_up.h"

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
	/* Per core, dalla SROM: maxpwr in Q5.2, itssi, e i tre coefficienti del
	 * PA. Senza questi il calcolo della potenza target esce zero, e nel
	 * confronto col vendore si vede subito (0x1ea = TXPCTL_TPWR). */
	u8 maxpwr_2g[2];
	u8 itssi_2g[2];
	/* Gli offset di potenza per rate, dalla NVRAM. Senza questi il PPR esce
	 * tutto zero e adj_pwr_tbl - le 84 celle a 26/27 off 0x40 - esce zeri,
	 * dove il vendore scrive un pattern: la finestra recalc-txpower si
	 * fermava a 266 op su 519 esattamente li'. */
	u16 cck2gpo;
	u32 ofdm2gpo;
	u16 mcs2gpo[8];
	u16 cddpo, stbcpo;
	u16 pa_2g[2][3];
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
		/* srom[0xC0/2] e srom[0xE0/2] e seguenti: maxp 74 (18.5 dBm in
		 * Q5.2), itssi 32, e i pa_2g dei due core. */
		.maxpwr_2g = { 74, 74 },
		/* nvram.txt: cck2gpo=0 ofdm2gpo=1145324612 mcs2gpo0..7=26214
		 * cddpo=0 stbcpo=0 */
		.cck2gpo = 0x0000,
		.ofdm2gpo = 0x44444444,
		.mcs2gpo = { 0x6666, 0x6666, 0x6666, 0x6666,
			     0x6666, 0x6666, 0x6666, 0x6666 },
		.cddpo = 0x0000,
		.stbcpo = 0x0000,
		.itssi_2g = { 32, 32 },
		.pa_2g = { { 0xff71, 0x1740, 0xfb17 },
			   { 0xff81, 0x1784, 0xfb1b } },
	},
	{
		/* La vd630, aggiunta per FALSIFICARE una previsione: sulla
		 * 3580L le colonne CDD/STBC/SDM della tabella di potenza
		 * aggiustata tornano (0x0c), ma la' le nibble di mcs2gpo sono
		 * tutte 6 e 2*6 = 12 = 0x0c, quindi potrebbe essere una
		 * coincidenza. Qui le nibble MCS vanno da 2 a 8 e nella cattura
		 * quelle colonne restano 0x0c COSTANTI: se il calcolo di b43 le
		 * fa variare, la coincidenza e' dimostrata.
		 *
		 * Valori da router-data/vd630/nvram.txt. Solo cio' che serve al
		 * calcolo della potenza: il resto della board non e' verificato
		 * contro la sua cattura, che e' un init parziale.
		 */
		.name = "vd630",
		/* Stesso PHY e stesso radio della 3580L: il blob D6220 ha i 33
		 * simboli dati del 2057 rev5-8 con size identiche e
		 * regs_2057_rev8 uguale byte per byte (docs/blob-inventory.md).
		 * Il chip pero' e' un altro, e questi quattro campi non sono
		 * verificati contro la cattura: servono solo a far prendere al
		 * PHY il percorso del 2057 rev 8. Cio' che si sta misurando qui
		 * e' il calcolo della potenza dalla SROM, che da questi non
		 * dipende.
		 */
		.chip_id = 0x6362,
		.chip_rev = 1,
		.core_rev = 22,
		.dev_id = 0x435f,
		.phy_rev = 8,
		.radio_rev = 8,
		.radio_ver = 0x2057,
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
		.maxpwr_2g = { 74, 74 },
		/* ofdm2gpo=1715741218 = 0x66442222, mcs2gpo0..7 alternano
		 * 0x4422 e 0x8866: nibble MCS 2,2,4,4,6,6,8,8 */
		.cck2gpo = 0x0000,
		.ofdm2gpo = 0x66442222,
		.mcs2gpo = { 0x4422, 0x8866, 0x4422, 0x8866,
			     0x4422, 0x8866, 0x4422, 0x8866 },
		.cddpo = 0x0000,
		.stbcpo = 0x0000,
		.itssi_2g = { 32, 32 },
		.pa_2g = { { 0xff43, 0x1778, 0xfab3 },
			   { 0xff82, 0x1838, 0xfab0 } },
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
	int i;

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
	sprom.cck2gpo = b->cck2gpo;
	sprom.ofdm2gpo = b->ofdm2gpo;
	for (i = 0; i < 8; i++)
		sprom.mcs2gpo[i] = b->mcs2gpo[i];
	sprom.cddpo = b->cddpo;
	sprom.stbcpo = b->stbcpo;
	for (i = 0; i < 2; i++) {
		sprom.core_pwr_info[i].maxpwr_2g = b->maxpwr_2g[i];
		sprom.core_pwr_info[i].itssi_2g = b->itssi_2g[i];
		sprom.core_pwr_info[i].pa_2g[0] = b->pa_2g[i][0];
		sprom.core_pwr_info[i].pa_2g[1] = b->pa_2g[i][1];
		sprom.core_pwr_info[i].pa_2g[2] = b->pa_2g[i][2];
	}

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

/* Un init a freddo: `do_full_init` vero, come dopo l'attach o un power-on reset.
 * E' quello che l'harness faceva sempre, ed e' il motivo per cui il confronto
 * sull'init INTERO non si allineava. */
/* La sequenza di b43_phy_init() in phy_common.c, nel suo ordine:
 *
 *	ops->switch_analog(dev, true);
 *	b43_software_rfkill(dev, false);	 <- da qui l'init del radio
 *	ops->init(dev);
 *	phy->do_full_init = false;
 *	b43_switch_channel(dev, phy->channel);
 *
 * `radio_on` va falso in ingresso: sull'hardware ci arriva sempre cosi', perche'
 * b43_phy_exit() fa software_rfkill(true). Con `radio_on` vero
 * b43_nphy_op_software_rfkill() salta b43_radio_2057_init() e il trace perde la
 * tabella di init del radio. */
static int init_once(bool full)
{
	int err;

	dev.phy.do_full_init = full;
	dev.phy.radio_on = false;
	b43_phyops_n.switch_analog(&dev, true);
	b43_software_rfkill(&dev, false);
	err = b43_phyops_n.init(&dev);
	if (err) {
		fprintf(stderr, "init(full=%d): %d\n", full, err);
		return err;
	}
	dev.phy.do_full_init = false;
	return b43_switch_channel(&dev, dev.phy.channel);
}

/* Il flow che si confronta con la cattura.
 *
 * `do_full_init` in b43 e' `phy_init_por` in brcmsmac, stessa semantica: vero
 * all'attach e dopo `b43_phy_exit()`, azzerato da `b43_phy_init()` appena
 * `ops->init()` e' andata bene. Dietro quel flag stanno il download delle
 * tabelle statiche (quattro siti in tables_nphy.c) e rcal/rccal del radio
 * (phy_n.c:1053).
 *
 * La cattura NON e' un init a freddo: `PHY.WR addr=0x72 val=0x2800`, cioe'
 * l'apertura della tabella 10 con cui comincia il download statico, non compare
 * in nessuno dei due init dei 70796 record, e le aperture di tabella sono 950 e
 * 1226 contro le ~2400 di un download completo. Quando il tracer e' partito il
 * driver aveva gia' fatto il suo init a freddo.
 *
 * Quindi qui si fanno due init: il primo a freddo e NON tracciato, che porta le
 * tabelle statiche nello specchio e fa rcal/rccal come l'attach; il secondo con
 * il flag azzerato, tracciato, ed e' quello confrontabile. I piani di lettura si
 * ricaricano fra i due, perche' rappresentano le read del secondo: le consuma
 * anche il primo, che gira per davvero. */
static int flow_init(void)
{
	int err;
	FILE *null;

	err = b43_phyops_n.allocate(&dev);
	if (err) {
		fprintf(stderr, "allocate: %d\n", err);
		return err;
	}
	b43_phyops_n.prepare_structs(&dev);

	null = fopen("/dev/null", "w");
	if (!null) {
		fprintf(stderr, "/dev/null: non apribile\n");
		return -1;
	}
	b43_test_trace_to(null);
	err = init_once(true);
	/* E un recalc, ancora non tracciato: e' quello che riempie
	 * nphy->tx_power_offset[], e senza di lui la tabella di potenza
	 * aggiustata esce a zeri per tutto l'init tracciato. Il vendore quegli
	 * offset ce li ha, perche' la cattura e' un init a caldo e il suo driver
	 * li ha calcolati al boot prima: a #2000 e a #2086 scrive le 84 celle col
	 * contenuto, `0 0 0 0` e poi `2 c c c` ripetuto, dove il port scriveva
	 * ottantaquattro zeri.
	 */
	if (!err) {
		/* Senza spegnere il pending, il recalc si tira dietro anche la
		 * sequenza differita della cal periodica, che rifa' la cal RSSI
		 * e riscrive la cache: il secondo init restaurerebbe quella e non
		 * quella del primo init. Qui serve solo il calcolo degli offset.
		 */
		dev.phy.n->perical_pending = false;
		b43_phyops_n.recalc_txpower(&dev, false);
	}
	b43_test_trace_to(stdout);
	fclose(null);
	if (err)
		return err;
	fprintf(stderr, "--- init a freddo fatto e non tracciato, ora quello "
			"che la cattura contiene ---\n");

	/* La cattura e' un init a caldo che rifa' la cal TX I/Q LO e la RX I/Q -
	 * le parentesi a #8492 e #14964 lo dicono - e NON la RSSI, che restaura.
	 * Il primo init qui sopra lascia le chanspec di cal valorizzate; azzerare
	 * le tre delle cal che la cattura contiene e' cio' che rende il secondo
	 * init lo stesso init che la cattura contiene. Quella della RSSI resta
	 * valorizzata, vedi sotto.
	 */
	dev.phy.n->iqcal_chanspec_2G.center_freq = 0;
	dev.phy.n->iqcal_chanspec_5G.center_freq = 0;
	dev.phy.n->rssical_chanspec_5G.center_freq = 0;

	/* Quella RSSI in 2 GHz NO, e va lasciata valorizzata: la cattura e' un
	 * init a caldo e il vendore la' non calibra, RESTAURA. Fra #132 e #8000
	 * legge 0x219 una volta sola - zero poll - e a #3712-#3731 scrive di
	 * fila i due registri radio e i dodici PHY, che e' esattamente il corpo
	 * di b43_nphy_restore_rssi_cal(). Azzerando la chanspec il port prendeva
	 * la strada della calibrazione: 1052 op che il vendore non ha.
	 *
	 * I valori NON si seminano: ce li mette il primo init, che la
	 * calibrazione la fa. Ne escono tutti e due i registri radio e undici
	 * dei dodici PHY identici alla cattura; l'unico che differisce e' quello
	 * di 0x1ac, l'offset fine narrowband del core 0 sulla rail Q, che il
	 * banco calcola 0 dove la cattura ha 1. Costa UNA op sulla finestra
	 * up-ch1, e vale meno di quattordici costanti copiate dalla cattura
	 * dentro il banco.
	 */
	dev.phy.n->rssical_chanspec_2G.center_freq = chan.center_freq;
	/* E anche questa, che serve per la stessa ragione e mancava. Da quando
	 * b43_nphy_cal_perical_phyinit() calcola full/parziale invece di
	 * inchiodare `true` — come fa il riferimento, sul confronto fra il canale
	 * e quello dell'ultima cal TX IQ/LO — un secondo init che trova questa
	 * valorizzata prende la strada PARZIALE, e la cattura contiene un init
	 * completo. Misurato: senza azzerarla la finestra up-ch1 perde 24 op.
	 */
	dev.phy.n->txiqlocal_coeffsvalid = false;
	dev.phy.n->txiqlocal_chanspec.center_freq = 0;

	b43_test_plans_reset();
	if (!getenv("B43_TEST_NOPLANS"))
		b43_test_load_readplans_init();

	/* I seed: lo stato che op_init e rfkill hanno prodotto e che la finestra
	 * misurata non puo' avere. Si applicano DOPO l'init a freddo e prima del
	 * secondo init, che e' quello tracciato: cosi' correggono solo gli
	 * indirizzi di cui la cattura sa e il port no, senza coprire niente di
	 * quello che il codice sotto misura programma da se'.
	 */
	if (!getenv("B43_TEST_NOSEED"))
		b43_test_seed_up();

	return init_once(false);
}

/* L'init a freddo da solo, per guardare cosa fa il download statico e rcal. Non
 * si confronta con questa cattura: non c'e' una cattura che parta dal power-on
 * reset. */
static int flow_initpor(void)
{
	int err = b43_phyops_n.allocate(&dev);

	if (err)
		return err;
	b43_phyops_n.prepare_structs(&dev);
	err = init_once(true);
	if (err)
		return err;
	/* mac80211 chiama recalc_txpower dopo l'init, sempre, e il driver ci
	 * appende la sequenza differita della cal periodica: senza questa
	 * chiamata il flow a freddo non la fa girare affatto e la finestra
	 * up-ch1-freddo perde undicimila op.
	 */
	b43_phyops_n.recalc_txpower(&dev, false);
	return 0;
}

/* mac80211 aggiorna hw->conf.chandef PRIMA di chiamare l'op, e il driver legge
 * la frequenza da lì: b43_nphy_op_switch_channel() usa
 * dev->wl->hw->conf.chandef.chan e l'argomento new_channel. Senza aggiornare il
 * chandef il port programma la chantab del canale vecchio, e si vede sul trace
 * come 0x16 e 0x2c -- vcocal e mmd0 -- coi valori di 2412 invece di 2437. */
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
	/* Il riferimento non ha cortocircuito: wlc_phy_txpower_recalc_target_nphy
	 * fa limit_to_tbl + pwr_setup + txpwrctrl_enable ogni volta. b43 invece
	 * esce alla prima riga se frequenza e limite sono quelli dell'ultimo
	 * calcolo, e l'init li ha appena impostati, quindi la chiamata non emette
	 * niente e la fase recalc-txpower misurava 1 op su 716. Qui si invalida
	 * la cache per far girare la fase: modella "qualcosa e' cambiato", che
	 * nella cattura e' cio' che succede fra l'init e #5726 - in mezzo il core
	 * scrive la template RAM.
	 */
	dev.phy.n->tx_pwr_last_recalc_freq = 0;
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

/* La corsa piu' lunga che il driver permette dagli ingressi pubblici: l'init che
 * la cattura contiene, poi il TX power control, poi un cambio canale. Parte da
 * flow_init come chanset e txpower, non da initcal: initcal fa un init a freddo
 * senza seed e senza il primo init non tracciato, quindi non e' l'init che la
 * cattura contiene e non si confronta con lei.
 *
 * Copre op_init fino alla fine di op_switch_channel, che nella cattura sono
 * #132-26100 per l'init e #34938-61971 per il periodo su ch6. In mezzo la
 * cattura ha quattordici salti dell'ACI scan, che e' una politica sopra il PHY e
 * il port non li fa: quel pezzo non e' confrontabile per costruzione.
 */
/* Il periodo su ch6 provato da solo. Il vendore, dopo il cambio canale,
 * ricalibra da zero; b43 non ha niente che lo schedula, perche' il riferimento
 * la ricalibrazione la fa arrivare dal watchdog e quel pezzo non e' portato.
 * Qui la si fa arrivare dal banco, azzerando le chanspec di cal prima del
 * cambio: e' la stessa cosa che flow_init fa prima dell'init tracciato, e serve
 * a misurare se il CODICE della calibrazione sa fare il canale nuovo, che e' una
 * domanda diversa da "chi la chiama".
 *
 * Con perical == 2, che e' quello che l'init lascia, chanspec_setup mette
 * perical_pending invece di calibrare in linea, e il recalc in coda la tira:
 * e' la stessa sequenza differita di flow_initpor.
 */
static int flow_chancal_from(int (*base)(void), unsigned int channel,
			     void (*load_plans)(void), const char *tag)
{
	int err = base();

	if (err)
		return err;

	dev.phy.n->iqcal_chanspec_2G.center_freq = 0;
	dev.phy.n->txiqlocal_coeffsvalid = false;
	dev.phy.n->txiqlocal_chanspec.center_freq = 0;

	fprintf(stderr, "--- cambio a canale %u ---\n", channel);
	set_channel(channel);
	printf("cpu0 CHANSPEC ch=%u\n", channel);
	err = b43_phyops_n.switch_channel(&dev, channel);
	if (err)
		return err;

	/* E poi l'init da capo sul canale nuovo, che e' cio' che la cattura
	 * contiene: il blocco su ch6 e' il 94% della stessa sequenza dell'init
	 * su ch1, misurato con la sottosequenza comune piu' lunga fra i due
	 * pezzi di cattura, 22308 op su 23649. Non e' una scorciatoia del
	 * banco per far girare qualcosa: e' la forma che il device ha.
	 */
	/* I piani di lettura di up-ch1 finiscono con up-ch1. Senza quelli del
	 * range nuovo ogni attesa cade sul mirror e gira a vuoto fino al suo
	 * limite: misurato, 181338 letture di 0x2be in un solo poll della cal
	 * PAPD e quattro milioni di op in tutto.
	 */
	b43_test_plans_reset();
	if (!getenv("B43_TEST_NOPLANS")) {
		load_plans();
		fprintf(stderr, "piani di lettura %s caricati\n", tag);
	}

	fprintf(stderr, "--- init da capo su ch%u ---\n", channel);
	err = init_once(false);
	if (err)
		return err;

	/* Con perical == 2 l'init mette perical_pending e non calibra in linea;
	 * il recalc e' cio' che la tira, come in flow_initpor.
	 */
	dev.phy.n->tx_pwr_last_recalc_freq = 0;
	/* Il valore di ritorno e' un enum B43_TXPWR_RES_*, non un errno: 1 e'
	 * NEED_ADJUST e non e' un errore. Come in flow_txpower, si scarta.
	 */
	b43_phyops_n.recalc_txpower(&dev, true);
	return 0;
}

/* Il gemello a caldo e quello a freddo. Le due basi c'erano gia' e sono le
 * stesse che le finestre usano: flow_txpower per la cattura opinit-*, che e' un
 * init a caldo, e flow_initpor per full-init-*, che e' un init da power-on. Cio'
 * che mancava era un set di piani di lettura per il range nuovo, uno per
 * cattura, perche' quelli dell'init finiscono con l'init.
 */
static int flow_chancal(unsigned int channel)
{
	return flow_chancal_from(flow_txpower, channel,
				 b43_test_load_readplans_ch6, "ch6");
}

static int flow_chancalpor(unsigned int channel)
{
	return flow_chancal_from(flow_initpor, channel,
				 b43_test_load_readplans_ch11, "ch11");
}

static int flow_full(unsigned int channel)
{
	int err = flow_txpower();

	if (err)
		return err;
	fprintf(stderr, "--- cambio a canale %u ---\n", channel);
	set_channel(channel);
	printf("cpu0 CHANSPEC ch=%u\n", channel);
	/* Si ferma qui, e le sue 60 op sono quante b43 ne fa davvero al cambio
	 * canale: la calibrazione sul canale nuovo non e' schedulata da nessuno
	 * (vedi la voce in CLAUDE.md), quindi appendere un recalc non emette
	 * niente. Per misurare il blocco del canale nuovo c'e' chancal.
	 */
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
		b43_test_load_readplans_init();
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
	else if (!strcmp(flow, "initpor"))
		err = flow_initpor();
	else if (!strcmp(flow, "initcal"))
		err = flow_initcal();
	else if (!strcmp(flow, "full"))
		err = flow_full(channel > 1 ? channel : 6);
	else if (!strcmp(flow, "chancal"))
		err = flow_chancal(channel > 1 ? channel : 6);
	else if (!strcmp(flow, "chancalpor"))
		err = flow_chancalpor(channel > 1 ? channel : 11);
	else {
		fprintf(stderr, "flow sconosciuto: %s\n", flow);
		return 2;
	}

	fflush(stdout);
	b43_test_plans_report(stderr);
	b43_test_tables_report(stderr);
	return err ? 1 : 0;
}
