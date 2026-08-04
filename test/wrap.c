/* SPDX-License-Identifier: GPL-2.0
 *
 * Shim per il build in userspace dei sorgenti N-PHY. Ogni accessor HW che i
 * .c del kernel chiamano e' implementato qui: emette una riga nel formato del
 * trace wl-diag decodificato e simula l'effetto minimo (mirror di memoria per
 * le write, valore programmato o mirror per le read). Nessun MMIO reale.
 *
 * Gli accessor di phy_common.c e del core b43 non vengono compilati, quindi qui
 * si definiscono e basta. Le b43_ntab_* invece stanno in tables_nphy.c, che
 * compiliamo: quelle si intercettano al linker con --wrap e poi si chiama la
 * __real_, perche' le PHY.WR che ne discendono sono il contenuto della tabella
 * e vanno nel trace esattamente come fa il vendore.
 *
 * Le read: se l'indirizzo ha un piano registrato ritorna il valore i-esimo e
 * avanza; altrimenti il mirror, cioe' l'ultima cosa scritta lì. Mai un valore
 * inventato diverso da zero.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#include "b43.h"
#include "phy_n.h"
#include "tables_nphy.h"
#include "test_harness.h"

#define MIRROR_PHY_SZ	0x1000
#define MIRROR_RADIO_SZ	0x1000
#define MIRROR_MMIO_SZ	0x1000
#define MIRROR_SHM_SZ	0x1000

static u16 mirror_phy[MIRROR_PHY_SZ];
static u16 mirror_radio[MIRROR_RADIO_SZ];
static u16 mirror_mmio[MIRROR_MMIO_SZ];
static u16 mirror_shm[MIRROR_SHM_SZ];

static FILE *out;

static FILE *trace(void)
{
	return out ? out : stdout;
}

void b43_test_trace_to(FILE *f)
{
	out = f;
}

void b43_test_log(const char *lvl, const char *fmt, ...)
{
	va_list ap;

	fprintf(stderr, "[%s] ", lvl);
	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
	fputc('\n', stderr);
}

/* ---------------- piani di lettura ---------------- */

enum plan_kind { PLAN_PHY, PLAN_RADIO, PLAN_MMIO };

struct plan {
	enum plan_kind kind;
	u16 addr;
	const u16 *vals;
	int cap;
	int iter;
};

#define MAX_PLANS 1024
static struct plan plans[MAX_PLANS];
static int nr_plans;

static void plan_add(enum plan_kind kind, u16 addr, const u16 *vals, int cap)
{
	int i;

	for (i = 0; i < nr_plans; i++) {
		if (plans[i].kind == kind && plans[i].addr == addr) {
			plans[i].vals = vals;
			plans[i].cap = cap;
			plans[i].iter = 0;
			return;
		}
	}
	if (nr_plans == MAX_PLANS) {
		b43_test_log("ERR", "troppi piani di lettura");
		return;
	}
	plans[nr_plans++] = (struct plan){ kind, addr, vals, cap, 0 };
}

void b43_test_plan_phy_reads(u16 addr, const u16 *v, int cap)
{
	plan_add(PLAN_PHY, addr, v, cap);
}

void b43_test_plan_radio_reads(u16 addr, const u16 *v, int cap)
{
	plan_add(PLAN_RADIO, addr, v, cap);
}

void b43_test_plan_mmio_reads(u16 addr, const u16 *v, int cap)
{
	plan_add(PLAN_MMIO, addr, v, cap);
}

void b43_test_plans_reset(void)
{
	nr_plans = 0;
}

void b43_test_plans_report(FILE *f)
{
	static const char *names[] = { "PHY", "RAD", "MMIO" };
	int i;

	for (i = 0; i < nr_plans; i++)
		fprintf(f, "piano %-4s 0x%04x: consumati %d/%d\n",
			names[plans[i].kind], plans[i].addr,
			plans[i].iter, plans[i].cap);
}

/* Ritorna true e riempie val se un piano copre questo indirizzo. */
static bool plan_get(enum plan_kind kind, u16 addr, u16 *val)
{
	int i;

	for (i = 0; i < nr_plans; i++) {
		if (plans[i].kind != kind || plans[i].addr != addr)
			continue;
		*val = plans[i].iter < plans[i].cap ?
			plans[i].vals[plans[i].iter] : 0;
		plans[i].iter++;
		return true;
	}
	return false;
}

void b43_test_mirror_phy_set(u16 reg, u16 val)
{
	if (reg < MIRROR_PHY_SZ)
		mirror_phy[reg] = val;
}

void b43_test_mirror_radio_set(u16 reg, u16 val)
{
	if (reg < MIRROR_RADIO_SZ)
		mirror_radio[reg] = val;
}

/* ---------------- registri PHY ---------------- */

u16 b43_phy_read(struct b43_wldev *dev, u16 reg)
{
	u16 val;

	if (!plan_get(PLAN_PHY, reg, &val))
		val = reg < MIRROR_PHY_SZ ? mirror_phy[reg] : 0;
	fprintf(trace(), "cpu0 PHY.RD   addr=0x%04x val=UNDEFINED\n", reg);
	return val;
}

void b43_phy_write(struct b43_wldev *dev, u16 reg, u16 value)
{
	fprintf(trace(), "cpu0 PHY.WR   addr=0x%04x val=0x%04x\n", reg, value);
	if (reg < MIRROR_PHY_SZ)
		mirror_phy[reg] = value;
}

void b43_phy_mask(struct b43_wldev *dev, u16 offset, u16 mask)
{
	fprintf(trace(), "cpu0 PHY.AND  addr=0x%04x val=0x%04x\n", offset, mask);
	if (offset < MIRROR_PHY_SZ)
		mirror_phy[offset] &= mask;
}

void b43_phy_set(struct b43_wldev *dev, u16 offset, u16 set)
{
	fprintf(trace(), "cpu0 PHY.OR   addr=0x%04x val=0x%04x\n", offset, set);
	if (offset < MIRROR_PHY_SZ)
		mirror_phy[offset] |= set;
}

void b43_phy_maskset(struct b43_wldev *dev, u16 offset, u16 mask, u16 set)
{
	fprintf(trace(), "cpu0 PHY.MOD  addr=0x%04x val=0x%04x mask=0x%04x\n",
		offset, set, (u16)~mask);
	if (offset < MIRROR_PHY_SZ)
		mirror_phy[offset] = (mirror_phy[offset] & mask) | set;
}

int b43_phy_shm_tssi_read(struct b43_wldev *dev, u16 shm_offset)
{
	return 0;
}

void b43_phy_force_clock(struct b43_wldev *dev, bool force)
{
	fprintf(trace(), "cpu0 PHY.CLK  val=0x%04x\n", force ? 1 : 0);
}

void b43_phy_lock(struct b43_wldev *dev)
{
}

void b43_phy_unlock(struct b43_wldev *dev)
{
}

/* ---------------- registri radio ---------------- */

u16 b43_radio_read(struct b43_wldev *dev, u16 reg)
{
	u16 val;

	if (!plan_get(PLAN_RADIO, reg, &val))
		val = reg < MIRROR_RADIO_SZ ? mirror_radio[reg] : 0;
	fprintf(trace(), "cpu0 RAD.RD   addr=0x%04x val=UNDEFINED\n", reg);
	return val;
}

void b43_radio_write(struct b43_wldev *dev, u16 reg, u16 value)
{
	fprintf(trace(), "cpu0 RAD.WR   addr=0x%04x val=0x%04x\n", reg, value);
	if (reg < MIRROR_RADIO_SZ)
		mirror_radio[reg] = value;
}

void b43_radio_mask(struct b43_wldev *dev, u16 offset, u16 mask)
{
	fprintf(trace(), "cpu0 RAD.AND  addr=0x%04x val=0x%04x\n", offset, mask);
	if (offset < MIRROR_RADIO_SZ)
		mirror_radio[offset] &= mask;
}

void b43_radio_set(struct b43_wldev *dev, u16 offset, u16 set)
{
	fprintf(trace(), "cpu0 RAD.OR   addr=0x%04x val=0x%04x\n", offset, set);
	if (offset < MIRROR_RADIO_SZ)
		mirror_radio[offset] |= set;
}

void b43_radio_maskset(struct b43_wldev *dev, u16 offset, u16 mask, u16 set)
{
	fprintf(trace(), "cpu0 RAD.MOD  addr=0x%04x val=0x%04x mask=0x%04x\n",
		offset, set, (u16)~mask);
	if (offset < MIRROR_RADIO_SZ)
		mirror_radio[offset] = (mirror_radio[offset] & mask) | set;
}

bool b43_radio_wait_value(struct b43_wldev *dev, u16 offset, u16 mask,
			  u16 value, int delay, int timeout)
{
	u16 val = b43_radio_read(dev, offset);

	/* Senza un piano il mirror non convergera' mai: si dichiara riuscita
	 * la prima lettura, e il fatto che il flow si aspettasse un poll resta
	 * visibile nel trace come una sola RAD.RD invece di N. */
	return (val & mask) == value || true;
}

/* ---------------- MMIO, MAC, SHM ---------------- */

u16 b43_read16(struct b43_wldev *dev, u16 offset)
{
	u16 val;

	if (!plan_get(PLAN_MMIO, offset, &val))
		val = offset < MIRROR_MMIO_SZ ? mirror_mmio[offset] : 0;
	fprintf(trace(), "cpu0 MMIO.RD  addr=0x%04x val=UNDEFINED\n", offset);
	return val;
}

void b43_write16(struct b43_wldev *dev, u16 offset, u16 value)
{
	fprintf(trace(), "cpu0 MMIO.WR  addr=0x%04x val=0x%04x\n", offset, value);
	if (offset < MIRROR_MMIO_SZ)
		mirror_mmio[offset] = value;
}

u32 b43_read32(struct b43_wldev *dev, u16 offset)
{
	fprintf(trace(), "cpu0 MMIO.RD  addr=0x%04x val=UNDEFINED\n", offset);
	return 0;
}

void b43_write32(struct b43_wldev *dev, u16 offset, u32 value)
{
	fprintf(trace(), "cpu0 MMIO.WR  addr=0x%04x val=0x%08x\n", offset, value);
}

void b43_maskset16(struct b43_wldev *dev, u16 offset, u16 mask, u16 set)
{
	fprintf(trace(), "cpu0 MMIO.MOD addr=0x%04x val=0x%04x mask=0x%04x\n",
		offset, set, (u16)~mask);
	if (offset < MIRROR_MMIO_SZ)
		mirror_mmio[offset] = (mirror_mmio[offset] & mask) | set;
}

void b43_maskset32(struct b43_wldev *dev, u16 offset, u32 mask, u32 set)
{
	fprintf(trace(), "cpu0 MMIO.MOD addr=0x%04x val=0x%08x mask=0x%08x\n",
		offset, set, ~mask);
}

u16 b43_shm_read16(struct b43_wldev *dev, u16 routing, u16 offset)
{
	fprintf(trace(), "cpu0 OBJ.RD   addr=0x%04x val=UNDEFINED space=0x%04x\n",
		offset, routing);
	return offset < MIRROR_SHM_SZ ? mirror_shm[offset] : 0;
}

void b43_shm_write16(struct b43_wldev *dev, u16 routing, u16 offset, u16 value)
{
	fprintf(trace(), "cpu0 OBJ.WR   addr=0x%04x val=0x%04x space=0x%04x\n",
		offset, value, routing);
	if (offset < MIRROR_SHM_SZ)
		mirror_shm[offset] = value;
}

u32 b43_shm_read32(struct b43_wldev *dev, u16 routing, u16 offset)
{
	fprintf(trace(), "cpu0 OBJ.RD   addr=0x%04x val=UNDEFINED space=0x%04x\n",
		offset, routing);
	return 0;
}

void b43_shm_write32(struct b43_wldev *dev, u16 routing, u16 offset, u32 value)
{
	fprintf(trace(), "cpu0 OBJ.WR   addr=0x%04x val=0x%08x space=0x%04x\n",
		offset, value, routing);
}

void b43_mac_suspend(struct b43_wldev *dev)
{
	fprintf(trace(), "cpu0 MAC.SUSP\n");
}

void b43_mac_enable(struct b43_wldev *dev)
{
	fprintf(trace(), "cpu0 MAC.EN\n");
}

void b43_mac_phy_clock_set(struct b43_wldev *dev, bool on)
{
	fprintf(trace(), "cpu0 MAC.PHYCLK val=0x%04x\n", on ? 1 : 0);
}

void b43_mac_switch_freq(struct b43_wldev *dev, u8 spurmode)
{
	fprintf(trace(), "cpu0 MAC.FREQ val=0x%04x\n", spurmode);
}

u64 b43_hf_read(struct b43_wldev *dev)
{
	fprintf(trace(), "cpu0 MAC.MHF.RD\n");
	return 0;
}

void b43_hf_write(struct b43_wldev *dev, u64 value)
{
	fprintf(trace(), "cpu0 MAC.MHF  val=0x%08x\n", (u32)value);
}

void b43_dummy_transmission(struct b43_wldev *dev, bool ofdm, bool pa_on)
{
	fprintf(trace(), "cpu0 DUMMYTX  val=0x%04x\n",
		(u16)((ofdm ? 2 : 0) | (pa_on ? 1 : 0)));
}

int b43_switch_channel(struct b43_wldev *dev, unsigned int new_channel)
{
	fprintf(trace(), "cpu0 CHANSPEC ch=%u\n", new_channel);
	return 0;
}

/* ---------------- helper di phy_common.c ---------------- */

enum nl80211_band b43_current_band(struct b43_wl *wl)
{
	return wl->hw->conf.chandef.chan->band;
}

bool b43_is_40mhz(struct b43_wldev *dev)
{
	return dev->phy.chandef->width == NL80211_CHAN_WIDTH_40;
}

bool b43_channel_type_is_40mhz(enum nl80211_channel_type channel_type)
{
	return channel_type == NL80211_CHAN_HT40PLUS ||
	       channel_type == NL80211_CHAN_HT40MINUS;
}

void b43_software_rfkill(struct b43_wldev *dev, bool blocked)
{
}

/* ---------------- tabelle: etichetta + esecuzione reale ---------------- */

u32 __real_b43_ntab_read(struct b43_wldev *dev, u32 offset);
void __real_b43_ntab_read_bulk(struct b43_wldev *dev, u32 offset,
			       unsigned int nr_elements, void *_data);
void __real_b43_ntab_write(struct b43_wldev *dev, u32 offset, u32 value);
void __real_b43_ntab_write_bulk(struct b43_wldev *dev, u32 offset,
				unsigned int nr_elements, const void *_data);

/* Nell'offset di b43_ntab_* l'id sta nei bit 10+ e il tipo nei bit alti, come
 * nei macro B43_NTAB8/16/32; il trace vendor riporta id e offset separati. */
static u16 ntab_id(u32 offset)
{
	return (offset & 0x0000FC00) >> 10;
}

static u16 ntab_off(u32 offset)
{
	return offset & 0x000003FF;
}

u32 __wrap_b43_ntab_read(struct b43_wldev *dev, u32 offset)
{
	fprintf(trace(), "cpu0 TBL.RD   id=0x%04x off=0x%04x len=1\n",
		ntab_id(offset), ntab_off(offset));
	return __real_b43_ntab_read(dev, offset);
}

void __wrap_b43_ntab_read_bulk(struct b43_wldev *dev, u32 offset,
			       unsigned int nr_elements, void *_data)
{
	fprintf(trace(), "cpu0 TBL.RD   id=0x%04x off=0x%04x len=%u\n",
		ntab_id(offset), ntab_off(offset), nr_elements);
	__real_b43_ntab_read_bulk(dev, offset, nr_elements, _data);
}

void __wrap_b43_ntab_write(struct b43_wldev *dev, u32 offset, u32 value)
{
	fprintf(trace(), "cpu0 TBL.WR   id=0x%04x off=0x%04x len=1\n",
		ntab_id(offset), ntab_off(offset));
	__real_b43_ntab_write(dev, offset, value);
}

void __wrap_b43_ntab_write_bulk(struct b43_wldev *dev, u32 offset,
				unsigned int nr_elements, const void *_data)
{
	fprintf(trace(), "cpu0 TBL.WR   id=0x%04x off=0x%04x len=%u\n",
		ntab_id(offset), ntab_off(offset), nr_elements);
	__real_b43_ntab_write_bulk(dev, offset, nr_elements, _data);
}

/* ---------------- attese ----------------
 *
 * Silenziose di proposito: nella cattura vendor non c'e' un solo record DELAY
 * (l'hook su osl_delay non scatta su questo blob), quindi emetterli qui
 * introdurrebbe righe che il riferimento non ha e ogni confronto posizionale
 * partirebbe sfasato.
 */
void udelay(unsigned long us) { }
void mdelay(unsigned long ms) { }
void msleep(unsigned int ms) { }
void usleep_range(unsigned long min_us, unsigned long max_us) { }

/* ---------------- helper del core b43 ---------------- */

enum nl80211_channel_type cfg80211_get_chandef_type(
				const struct cfg80211_chan_def *chandef)
{
	switch (chandef->width) {
	case NL80211_CHAN_WIDTH_20_NOHT:
		return NL80211_CHAN_NO_HT;
	case NL80211_CHAN_WIDTH_20:
		return NL80211_CHAN_HT20;
	case NL80211_CHAN_WIDTH_40:
		return chandef->center_freq1 > chandef->chan->center_freq ?
			NL80211_CHAN_HT40PLUS : NL80211_CHAN_HT40MINUS;
	default:
		return NL80211_CHAN_NO_HT;
	}
}

void b43_wireless_core_phy_pll_reset(struct b43_wldev *dev)
{
	fprintf(trace(), "cpu0 PHYPLL.RST\n");
}

/* ---------------- percorsi radio 2055 e 2056 ----------------
 *
 * Radio 2055 e' N-PHY rev 1-2, il 2056 rev 3-6: sul rev 8 non vengono mai
 * chiamati. Abortiscono invece di ritornare zero: se il flow ci finisce, il
 * device e' montato male e voglio saperlo subito, non leggerlo in un diff.
 */
static void wrong_radio(const char *fn)
{
	fprintf(stderr,
		"%s chiamata: il device e' montato male (radio rev %s)\n",
		fn, "atteso 2057 rev 8");
	abort();
}

void b2055_upload_inittab(struct b43_wldev *dev, bool ghz5, bool ignore_uploadflag)
{
	wrong_radio("b2055_upload_inittab");
}

void b2056_upload_inittabs(struct b43_wldev *dev, bool ghz5, bool ignore_uploadflag)
{
	wrong_radio("b2056_upload_inittabs");
}

void b2056_upload_syn_pll_cp2(struct b43_wldev *dev, bool ghz5)
{
	wrong_radio("b2056_upload_syn_pll_cp2");
}

const struct b43_nphy_channeltab_entry_rev2 *
b43_nphy_get_chantabent_rev2(struct b43_wldev *dev, u8 channel)
{
	wrong_radio("b43_nphy_get_chantabent_rev2");
	return NULL;
}

const struct b43_nphy_channeltab_entry_rev3 *
b43_nphy_get_chantabent_rev3(struct b43_wldev *dev, u16 freq)
{
	wrong_radio("b43_nphy_get_chantabent_rev3");
	return NULL;
}

/* ---------------- ChipCommon via bcma ----------------
 *
 * Nella cattura vendor le GPIO ci sono (GPIO.CTL e GPIO.OUT), quindi questi
 * record servono al confronto. bcma_pmu_spuravoid_pllupdate invece nella
 * cattura non compare mai: se l'harness la emette, e' b43 che fa qualcosa che
 * il vendore non fa, ed e' un'informazione, non rumore.
 */
void bcma_chipco_gpio_control(struct bcma_drv_cc *cc, u32 mask, u32 value)
{
	fprintf(trace(), "cpu0 GPIO.CTL val=0x%08x mask=0x%08x\n", value, mask);
}

void bcma_cc_set32_stub(struct bcma_drv_cc *cc, u16 offset, u32 set)
{
	fprintf(trace(), "cpu0 CC.SET32 addr=0x%04x val=0x%08x\n", offset, set);
}

void bcma_pmu_spuravoid_pllupdate(struct bcma_drv_cc *cc, int spuravoid)
{
	fprintf(trace(), "cpu0 PMU.SPUR val=0x%08x\n", (u32)spuravoid);
}
