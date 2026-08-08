/* SPDX-License-Identifier: GPL-2.0
 *
 * Shim per il build in userspace dei sorgenti N-PHY. Ogni accessor HW che i
 * .c del kernel chiamano e' implementato qui: emette una riga nel formato del
 * trace wl-diag decodificato e simula l'effetto minimo (mirror di memoria per
 * le write, valore programmato o mirror per le read). Nessun MMIO reale.
 *
 * Le read stampano il valore che hanno SERVITO, non val=UNDEFINED. Il tracer del
 * vendore lo mette in un record RETVAL a parte e merge_retvals.py lo ripiega
 * sulla riga della read: finche' l'harness scriveva UNDEFINED, ogni read contava
 * come divergenza per costruzione e il confronto sui valori letti non esisteva.
 * Ora esiste, ed e' la parte piu' severa del confronto: dice se il port sta
 * leggendo la stessa cosa, non solo se la sta chiedendo.
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
	const u32 *recs;	/* il record della cattura da cui viene ogni valore */
	int cap;
	int iter;
	int skipped;		/* entry saltate perche' precedono il cursore */
	int misses;		/* read senza nessuna entry dal cursore in poi */
	u32 pos;		/* il cursore di QUESTO indirizzo */
};

/* Il cursore e' PER INDIRIZZO, e plan_pos e' solo il pavimento comune da cui
 * ognuno parte: l'ingresso della regione sotto misura, vedi b43_test_plans_reset.
 *
 * L'invariante che regge e' per indirizzo: le read che il port fa di UN indirizzo
 * sono una sottosequenza di quelle che il vendore fa dello stesso indirizzo, ne fa
 * meno e nello stesso ordine. Quella globale, sull'interleaving fra indirizzi
 * diversi, non regge, ed e' misurabile: con un cursore solo il primo hit e' PHY
 * 0x7a servito dal record 14999, che da un cursore a zero salta a 15000 e rende
 * irraggiungibile ogni voce sotto quel record per ogni altro indirizzo.
 *
 * Il prezzo e' l'altro verso: se il port salta una read di un indirizzo, i valori
 * successivi DI QUELL'INDIRIZZO si sfasano di uno. Sfasa un indirizzo per volta
 * invece di tutti, e un valore sfasato rompe la run come la rompe un'op mancante,
 * quindi la misura per fase lo vede.
 */
static u32 plan_pos;

/* B43_TEST_PLANDBG=1 stampa ogni hit e ogni miss con il record servito e il
 * cursore: e' il solo modo di vedere quale read porta il cursore avanti.
 */
static int plan_dbg = -1;


static const char *plan_kind_name(enum plan_kind k)
{
	static const char *n[] = { "PHY", "RAD", "MMIO" };

	return n[k];
}

#define MAX_PLANS 1024
static struct plan plans[MAX_PLANS];
static int nr_plans;

static void plan_add(enum plan_kind kind, u16 addr, const u16 *vals,
		     const u32 *recs, int cap)
{
	int i;

	for (i = 0; i < nr_plans; i++) {
		if (plans[i].kind == kind && plans[i].addr == addr) {
			plans[i].vals = vals;
			plans[i].recs = recs;
			plans[i].cap = cap;
			plans[i].iter = 0;
			plans[i].skipped = 0;
			plans[i].misses = 0;
			plans[i].pos = plan_pos;
			return;
		}
	}
	if (nr_plans == MAX_PLANS) {
		b43_test_log("ERR", "troppi piani di lettura");
		return;
	}
	plans[nr_plans++] = (struct plan){ kind, addr, vals, recs, cap, 0, 0, 0,
					   plan_pos };
}

void b43_test_plan_phy_reads(u16 addr, const u16 *v, const u32 *r, int cap)
{
	plan_add(PLAN_PHY, addr, v, r, cap);
}

void b43_test_plan_radio_reads(u16 addr, const u16 *v, const u32 *r, int cap)
{
	plan_add(PLAN_RADIO, addr, v, r, cap);
}

void b43_test_plan_mmio_reads(u16 addr, const u16 *v, const u32 *r, int cap)
{
	plan_add(PLAN_MMIO, addr, v, r, cap);
}

/* Piani per CELLA di tabella. Servono per le celle che scrive l'hardware dentro
 * la finestra - i risultati del motore di calibrazione in 15/96.. - e per quelle
 * sole: il mirror non ha modo di saperle, perche' nessuna write per porta le ha
 * mai toccate e il loro valore cambia fra una read e l'altra. Si trovano con
 * `trace_tables.py --hw-written`, che sulla finestra up-ch1 ne conta sette su 51
 * non riproducibili; le altre 44 hanno valore fisso e sono stato da prima della
 * finestra, che e' lavoro del seed e non di un piano.
 *
 * Il cursore e' per cella e nient'altro, come dice test_harness.h: non c'e' un
 * ordine globale da rispettare, perche' il motore scrive quella cella e la
 * risposta giusta e' la n-esima che il vendore ha letto da quella cella.
 *
 * Solo tabelle a 16 bit: le celle in gioco sono di IQLOCAL, che e' u16.
 */
#define MAX_CELL_PLANS 64

struct cell_plan {
	u16 id;
	u16 off;
	const u16 *vals;
	int cap;
	int iter;
	int over;		/* read oltre la fine del piano */
};

static struct cell_plan cell_plans[MAX_CELL_PLANS];
static int nr_cell_plans;

void b43_test_plan_table_cell(u16 id, u16 off, const u16 *vals, int n)
{
	int i;

	for (i = 0; i < nr_cell_plans; i++) {
		if (cell_plans[i].id == id && cell_plans[i].off == off) {
			cell_plans[i].vals = vals;
			cell_plans[i].cap = n;
			cell_plans[i].iter = 0;
			cell_plans[i].over = 0;
			return;
		}
	}
	if (nr_cell_plans == MAX_CELL_PLANS) {
		b43_test_log("ERR", "troppi piani per cella");
		return;
	}
	cell_plans[nr_cell_plans++] = (struct cell_plan){ id, off, vals, n, 0, 0 };
}

/* Vero se un piano copre questa cella e ha ancora un valore da dare. */
static bool cell_plan_get(u16 id, u16 off, u16 *val)
{
	int i;

	for (i = 0; i < nr_cell_plans; i++) {
		if (cell_plans[i].id != id || cell_plans[i].off != off)
			continue;
		if (cell_plans[i].iter >= cell_plans[i].cap) {
			cell_plans[i].over++;
			return false;
		}
		*val = cell_plans[i].vals[cell_plans[i].iter++];
		return true;
	}
	return false;
}

void b43_test_plans_reset(void)
{
	const char *from = getenv("B43_TEST_PLAN_FROM");

	nr_plans = 0;
	nr_cell_plans = 0;
	/* Il pavimento da cui parte il cursore di ogni piano: il primo record della
	 * regione sotto misura, da B43_TEST_PLAN_FROM. Serve a non far servire a una
	 * fase i valori che il vendore ha letto prima di entrarci.
	 */
	plan_pos = from ? (u32)strtoul(from, NULL, 0) : 0;
}

void b43_test_plans_report(FILE *f)
{
	static const char *names[] = { "PHY", "RAD", "MMIO" };
	int i;

	for (i = 0; i < nr_plans; i++)
		fprintf(f, "piano %-4s 0x%04x: consumati %d/%d, saltate %d, "
			"fuori posizione %d\n",
			names[plans[i].kind], plans[i].addr,
			plans[i].iter, plans[i].cap, plans[i].skipped,
			plans[i].misses);

}

/* Ritorna true e riempie val se un piano copre questo indirizzo. */
static bool plan_get(enum plan_kind kind, u16 addr, u16 *val)
{
	int i;

	if (plan_dbg < 0)
		plan_dbg = getenv("B43_TEST_PLANDBG") ? 1 : 0;

	for (i = 0; i < nr_plans; i++) {
		int j;

		if (plans[i].kind != kind || plans[i].addr != addr)
			continue;

		/* La prima entry che nella cattura viene dal cursore in poi. */
		for (j = plans[i].iter; j < plans[i].cap; j++)
			if (plans[i].recs[j] >= plans[i].pos)
				break;
		plans[i].skipped += j - plans[i].iter;
		plans[i].iter = j;
		if (j == plans[i].cap) {
			/* Niente da servire: il mirror e' meno bugiardo di uno
			 * zero, e il contatore lo rende visibile.
			 */
			plans[i].misses++;
			if (plan_dbg)
				fprintf(stderr, "planmiss %s 0x%04x cursore %u "
					"ultima %u\n", plan_kind_name(kind), addr,
					plans[i].pos,
					plans[i].cap ?
					plans[i].recs[plans[i].cap - 1] : 0);
			return false;
		}
		*val = plans[i].vals[j];
		if (plan_dbg)
			fprintf(stderr, "planhit %s 0x%04x rec %u cursore %u\n",
				plan_kind_name(kind), addr, plans[i].recs[j],
				plans[i].pos);
		plans[i].pos = plans[i].recs[j] + 1;
		plans[i].iter = j + 1;
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

/* Mirror delle TABELLE, non dei registri.
 *
 * Serviva: mirror_phy tiene i registri, e una lettura di tabella passa dalla
 * porta dati 0x73, quindi senza questo il port si riprendeva **l'ultima cella
 * scritta da qualunque parte** invece di quella che aveva chiesto. Si vedeva
 * sulla banda del filtro passa-basso, che la cal PAPD rilegge da 7/0x154: il
 * port aveva appena azzerato le tabelle epsilon, quindi leggeva 0 dove il
 * vendore legge 0x2c64. Non era ne' un difetto del driver ne' un problema dei
 * piani di lettura, ed e' stato attribuito a entrambi prima di essere guardato.
 *
 * I piani non c'entrano e non devono: per una cella di tabella il valore giusto
 * e' quello che la tabella contiene, che e' la stessa ragione per cui 0x72,
 * 0x73 e 0x74 stanno fuori dai piani.
 */
#define TBL_MIRROR_IDS	64
#define TBL_MIRROR_OFFS	1024

static u32 tbl_mirror[TBL_MIRROR_IDS][TBL_MIRROR_OFFS];
static u16 tbl_hi_pending;
static int tbl_hi_valid;
/* Il lato lettura: la cella agganciata dall'ultima 0x73, da cui 0x74 prende la
 * word alta. Vedi tbl_port_get. */
static u32 tbl_latch;
static int tbl_latch_valid;
/* Letture di 0x74 senza una 0x73 che le preceda: non ne fa nessuna larghezza di
 * b43_ntab_read, quindi se il contatore sale c'e' un accesso alla porta dati che
 * non passa da la' e va guardato invece di cadere sul mirror in silenzio. */
static int tbl_hi_unlatched;
/* Vero mentre gira il corpo vero di una b43_ntab_*: quelle passano anche loro da
 * 0x72/0x73/0x74, e il mirror l'hanno gia' aggiornato per offset, quindi
 * riapplicarlo dalla porta lo farebbe due volte, con l'auto-incremento che sposta
 * la seconda applicazione sulla cella dopo. */
static int in_ntab;

/* Il valore che una cella di tabella aveva all'ingresso della finestra. Come gli
 * altri mirror_set: si applica dopo l'init a freddo e prima di quello misurato,
 * quindi dice cio' che la finestra non puo' sapere e non copre niente di cio' che
 * il codice sotto misura programma da se'.
 */
void b43_test_mirror_table_set(u16 id, u16 off, u32 val)
{
	if (id < TBL_MIRROR_IDS && off < TBL_MIRROR_OFFS)
		tbl_mirror[id][off] = val;
}

static void tbl_mirror_set(u32 offset, u32 value)
{
	u16 id = (offset & 0x0000FC00) >> 10, off = offset & 0x000003FF;

	if (id < TBL_MIRROR_IDS && off < TBL_MIRROR_OFFS)
		tbl_mirror[id][off] = value;
}

/* Le tre larghezze che b43_ntab_* distingue stanno nei bit alti dell'offset,
 * come in tables_nphy.c: 8, 16 o 32 bit per cella.
 */
static void tbl_mirror_set_bulk(u32 offset, unsigned int nr, const void *data)
{
	const u8 *d8 = data;
	const u16 *d16 = data;
	const u32 *d32 = data;
	unsigned int i;

	for (i = 0; i < nr; i++) {
		u32 v;

		switch (offset & B43_NTAB_TYPEMASK) {
		case B43_NTAB_8BIT:
			v = d8[i];
			break;
		case B43_NTAB_16BIT:
			v = d16[i];
			break;
		default:
			v = d32[i];
			break;
		}
		tbl_mirror_set(offset + i, v);
	}
}

/* Il simmetrico di tbl_port_get: una scrittura diretta su 0x73 o 0x74 aggiorna la
 * cella indirizzata dall'ultima 0x72, non solo il mirror del registro.
 *
 * Serve perche' non tutto il driver passa dalle b43_ntab_*:
 * b43_nphy_tx_pwr_ctrl_coef_setup() apre la porta a mano e scrive 128 celle di
 * fila su 0x74/0x73. Senza questo quelle celle non finiscono nel mirror, e la
 * prima cosa che le rilegge - b43_nphy_txpwr_index(), che prende la
 * compensazione IQ a 320+indice e quella dell'oscillatore a 448+indice - si
 * riprende l'ultima cella scritta da un'altra parte. Misurato nella finestra
 * txpwr-index: le letture di 26/0x14a e 26/0x1ca tornavano 0x2e2e, cioe' il
 * moltiplicatore appena scritto su 15/0x57.
 *
 * L'auto-incremento e' quello dell'hardware, ed e' come funzionano le scritture
 * in blocco: l'indirizzo si scrive una volta e i dati si versano. Per una tabella
 * a 32 bit la cella e' completa quando arriva la word bassa (0x73), che il driver
 * scrive per seconda.
 */
static void tbl_port_put(int high, u16 val)
{
	u32 sel = mirror_phy[0x72];
	u16 id = (sel & 0xFC00) >> 10, off = sel & 0x3FF;

	if (in_ntab)
		return;
	if (id >= TBL_MIRROR_IDS || off >= TBL_MIRROR_OFFS)
		return;
	if (high) {
		tbl_hi_pending = val;
		tbl_hi_valid = 1;
		return;
	}
	tbl_mirror[id][off] = tbl_hi_valid ? ((u32)tbl_hi_pending << 16) | val
					   : val;
	tbl_hi_valid = 0;
	if (off + 1 < TBL_MIRROR_OFFS)
		mirror_phy[0x72] = (sel & 0xFC00) | (off + 1);
}

/* La cella indirizzata dall'ultima scrittura su 0x72, che porta (id << 10) | off
 * per ogni larghezza di tabella: 0x3c57 e' 15/0x57, 0x1d54 e' 7/0x154.
 * `high` distingue la porta 0x74 (word alta di una cella a 32 bit) da 0x73.
 *
 * Il modello e' il simmetrico di tbl_port_put, e le due larghezze si servono
 * senza sapere quale sia: la lettura di 0x73 aggancia la cella INTERA e fa
 * avanzare l'indirizzo, quella di 0x74 rende la word alta agganciata e non
 * avanza. Serve perche' le due porte si visitano in ordine opposto nei due
 * versi - b43_ntab_read fa 0x73 e poi 0x74, b43_ntab_write 0x74 e poi 0x73
 * (tables_nphy.c) - e senza l'aggancio l'incremento sulla word bassa
 * spingerebbe la lettura della word alta sulla cella dopo.
 *
 * L'incremento e' quello dell'hardware, ed e' cio' che rende una read in blocco
 * un indirizzo e N letture: la cattura lo mostra su ogni cella a 32 bit, per
 * esempio #7430-7435, dove 26/0xca si legge con una 0x72, una 0x73 (0x002e) e
 * una 0x74 (0x4077) per la cella 0x4077002e.
 *
 * La cella si serve sempre, anche se nessuno l'ha scritta: tbl_mirror parte a
 * zero e zero e' la risposta giusta, perche' 0x73 e 0x74 sono SOLO la porta dati
 * e il mirror del registro li' non significa niente. Servirlo era il buco: una
 * cella intoccata si riprendeva l'ultima word scritta sulla porta da qualunque
 * tabella.
 */
int tbl_port_get(int high, u16 *val)
{
	u32 sel = mirror_phy[0x72];
	u16 id = (sel & 0xFC00) >> 10, off = sel & 0x3FF, pv;

	if (high) {
		if (!tbl_latch_valid) {
			tbl_hi_unlatched++;
			return 0;
		}
		*val = tbl_latch >> 16;
		return 1;
	}
	if (id >= TBL_MIRROR_IDS || off >= TBL_MIRROR_OFFS)
		return 0;
	/* Se l'hardware ha scritto questa cella, il piano dice cosa ci ha messo, e
	 * il mirror lo impara: da qui in avanti una read senza piano rende
	 * l'ultimo valore del motore invece di zero.
	 */
	if (cell_plan_get(id, off, &pv))
		tbl_mirror[id][off] = pv;
	tbl_latch = tbl_mirror[id][off];
	tbl_latch_valid = 1;
	*val = tbl_latch & 0xFFFF;
	if (off + 1 < TBL_MIRROR_OFFS)
		mirror_phy[0x72] = (sel & 0xFC00) | (off + 1);
	return 1;
}

void b43_test_tables_report(FILE *f)
{
	int i;

	for (i = 0; i < nr_cell_plans; i++)
		fprintf(f, "piano cella %2u/0x%03x: consumati %d/%d, oltre la "
			"fine %d\n", cell_plans[i].id, cell_plans[i].off,
			cell_plans[i].iter, cell_plans[i].cap,
			cell_plans[i].over);

	if (tbl_hi_unlatched)
		fprintf(f, "porta dati: %d letture di 0x74 senza la 0x73 che le "
			"aggancia, servite dal mirror del registro\n",
			tbl_hi_unlatched);
}

u16 b43_phy_read(struct b43_wldev *dev, u16 reg)
{
	u16 val;

	if ((reg == 0x73 || reg == 0x74) && tbl_port_get(reg == 0x74, &val)) {
		/* La porta dati di una tabella: il valore giusto e' la cella
		 * indirizzata, non l'ultima cosa scritta sul registro. I piani
		 * qui non entrano di proposito, ed e' la stessa ragione.
		 */
	} else if (!plan_get(PLAN_PHY, reg, &val)) {
		val = reg < MIRROR_PHY_SZ ? mirror_phy[reg] : 0;
	}
	fprintf(trace(), "cpu0 PHY.RD   addr=0x%04x val=0x%04x\n", reg, val);
	return val;
}

void b43_phy_write(struct b43_wldev *dev, u16 reg, u16 value)
{
	fprintf(trace(), "cpu0 PHY.WR   addr=0x%04x val=0x%04x\n", reg, value);
	if (reg == 0x73 || reg == 0x74)
		tbl_port_put(reg == 0x74, value);
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
	fprintf(trace(), "cpu0 RAD.RD   addr=0x%04x val=0x%04x\n", reg, val);
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

/* Fedele a main.c: la parte che ci riguarda e' che chiama l'op del PHY. Con un
 * return 0 secco mancavano dal trace l'upload della chantab e tutto cio' che il
 * cambio canale fa, sia quello dentro software_rfkill sia quello in coda a
 * b43_phy_init(). */
int b43_switch_channel(struct b43_wldev *dev, unsigned int new_channel)
{
	fprintf(trace(), "cpu0 CHANSPEC ch=%u\n", new_channel);
	dev->phy.channel = new_channel;
	return dev->phy.ops->switch_channel(dev, new_channel);
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

/* Fedele a phy_common.c meno mac_suspend/mac_enable, che non tracciamo.
 *
 * Era uno stub vuoto, e da qui passa l'init del radio:
 * b43_nphy_op_software_rfkill() -> b43_radio_2057_init() -> la tabella di init
 * del radio e il primo cambio canale. Con lo stub vuoto quelle op non erano nel
 * trace, e sono le prime ~84 della cattura. */
void b43_software_rfkill(struct b43_wldev *dev, bool blocked)
{
	dev->phy.ops->software_rfkill(dev, blocked);
	dev->phy.radio_on = !blocked;
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
	/* Il valore lo serve la porta dati, in b43_phy_read: vedi tbl_port_get.
	 * Servirlo qui invece che li' aggiustava il valore che il driver usa e
	 * lasciava nel trace la lettura del registro col mirror sbagliato, cioe'
	 * un buco che sembrava un difetto del port e non lo era.
	 */
	{
		u32 v;

		in_ntab = 1;
		v = __real_b43_ntab_read(dev, offset);
		in_ntab = 0;
		return v;
	}
}

void __wrap_b43_ntab_read_bulk(struct b43_wldev *dev, u32 offset,
			       unsigned int nr_elements, void *_data)
{
	fprintf(trace(), "cpu0 TBL.RD   id=0x%04x off=0x%04x len=%u\n",
		ntab_id(offset), ntab_off(offset), nr_elements);
	in_ntab = 1;
	__real_b43_ntab_read_bulk(dev, offset, nr_elements, _data);
	in_ntab = 0;
}

void __wrap_b43_ntab_write(struct b43_wldev *dev, u32 offset, u32 value)
{
	fprintf(trace(), "cpu0 TBL.WR   id=0x%04x off=0x%04x len=1\n",
		ntab_id(offset), ntab_off(offset));
	tbl_mirror_set(offset, value);
	in_ntab = 1;
	__real_b43_ntab_write(dev, offset, value);
	in_ntab = 0;
}

void __wrap_b43_ntab_write_bulk(struct b43_wldev *dev, u32 offset,
				unsigned int nr_elements, const void *_data)
{
	fprintf(trace(), "cpu0 TBL.WR   id=0x%04x off=0x%04x len=%u\n",
		ntab_id(offset), ntab_off(offset), nr_elements);
	tbl_mirror_set_bulk(offset, nr_elements, _data);
	in_ntab = 1;
	__real_b43_ntab_write_bulk(dev, offset, nr_elements, _data);
	in_ntab = 0;
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
