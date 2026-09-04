# patches/b43 — messaggi della serie prima del rollup


I trentasei messaggi della serie, estratti dai rispettivi file quando la serie e'
stata compressa in `rollup.diff`. Il diff sta la', questo tiene cio' che il diff
non porta: il razionale, le misure, gli intervalli di record della cattura e i
trailer `Link:`.

**L'ordine qui sotto e' quello di scoperta, e non e' l'ordine in cui spedirle.** Per
chi le deve rivedere sono otto serie separate, una per competenza: `SERIES.md`.

Serve a due cose. Le citazioni per numero sparse nei documenti e in
`test/phase_compare.py` sono nella forma `patches/b43/MESSAGES.md#0003` e
puntano qui: i titoli sono il numero e nient'altro, cosi' l'ancora e' `#0003` e
non si sposta se il titolo cambia. E la ri-divisione ha il materiale da cui
ripartire: senza, i messaggi starebbero solo nella storia git di questo repo.

I corpi sono **verbatim**, riferimenti interni compresi: dentro parlano fra loro
per numero nudo ("0004 depends on 0002") e non sono stati riscritti, perche' un
estratto corretto a mano non e' piu' un estratto.

`0010` e `0022` sono nell'elenco ma **non** nel rollup, vedi la testa di
`rollup.diff`.


## 0001

b43: program the N-PHY RX gain control for radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: program the N-PHY RX gain control for radio 2057 rev 8

b43_nphy_gain_ctl_workarounds_rev7() has been an empty stub since N-PHY rev
7+ support was added, so the RX gain control is left at whatever the
initvals put there: LNA1, LNA2 and TIA gain tables, the CRS minimum power
thresholds, the clip1 low gain codes and the W1 clip thresholds are never
programmed.

Program them for radio 2057 rev 8 in 2.4 GHz, 20 MHz. The register and
table writes, and their order, are taken from an MMIO capture of the
proprietary wl driver 6.30.102.7 running on a BCM6362 (D-Link DSL-3580L).
The capture contains two init sequences, on operating channel 1 and on
operating channel 6, and both program the same values in the same order, so
none of them depends on the channel.

Other radio revisions keep the current behaviour. The vendor driver uses
different gain values per radio revision, and the ones brcmsmac carries for
this code path are from an older release: on radio rev 8 it would write an
LNA1 gain set of 9, 14, 19, 24 and a W1 clip threshold of 13, where the
device is programmed with 8, 13, 18, 25 and 24. Extending this to another
revision needs a capture from hardware that has it.

40 MHz and 5 GHz return early, for two different reasons. The vendor driver
does not use 40 MHz in 2.4 GHz on this board, so checking those values
needs a device that runs 40 MHz. For 5 GHz, b43 has no channel table for
radio 2057 rev 8, so the driver cannot tune there in the first place.



Verified: records #680-#770, from "PHY.MOD  addr=0x01d9 val=0x0000 mask=0x0020"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows gain-control

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0002

b43: use the rev 7 RF power offsets for radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: use the rev 7 RF power offsets for radio 2057 rev 8

The table added by commit 21352612198c ("b43: add RF power offset for N-PHY
r8 + radio 2057 r8") carries the values the proprietary driver uses for
radio revision 5. That driver, and brcmsmac in get_rf_pwr_offset(), select
a different table for revisions 7 and 8:

	else if ((pi->pubpi.radiorev == 7) || (pi->pubpi.radiorev == 8))
		rfpwr_offset = (s16) nphy_papd_padgain_dlt_2g_2057rev7[pad_gn];

get_rf_pwr_offset() is the counterpart of the b43 code that consumes this
table, so follow its dispatch and use the rev 7 offsets. The values are
taken from brcmsmac's nphy_papd_padgain_dlt_2g_2057rev7.

An MMIO capture of wl 6.30.102.7 on a BCM6362 settles it: the driver writes
128 PAPD compensation cells per core during init, each one an entry of this
table indexed by the pad gain of the TX gain table. Recomputing them from
the values in tree reproduces 5 cells out of 128; recomputing them from the
rev 7 values reproduces all 128.

Fixes: 21352612198c ("b43: add RF power offset for N-PHY r8 + radio 2057 r8")


Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n17788

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0003

b43: program the PAPD compensation table on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: program the PAPD compensation table on radio 2057 rev 8

b43_nphy_tx_gain_table_upload() bails out for phy rev 7+ right after
fetching the RF power offset table, leaving the PAPD compensation table
(tables 26 and 27 at offset 576, 128 entries each) untouched.

An MMIO capture of the proprietary wl driver 6.30.102.7 on a BCM6362 (N-PHY
rev 8, radio 2057 rev 8) shows it writing all 256 of those cells during
init, one 32-bit entry at a time, with the value taken from the RF power
offset table indexed by the pad gain of the corresponding TX gain table
entry. That is what the loop below already computes, so let radio 2057 rev
8 reach it.

Every value the loop produces matches the capture, all 256 of them, so the
computation and the table it indexes are both right for this radio.

Other rev 7+ radios keep the current behaviour: their offsets have not been
checked against hardware, and writing a wrong compensation table is worse
than writing none.

Depends on the RF power offset values from the previous patch: with the
ones currently in tree, 246 of the 256 cells come out wrong.



Verified: records #2688-#2703, from "TBL.WR   id=0x001a off=0x0240 len=1"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows papd-comp

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0004

b43: initialise the PAPD tables on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: initialise the PAPD tables on radio 2057 rev 8

b43_phy_initn() enables the PAPD engine on every device with an internal
PA, by setting PAPD_EN0 and PAPD_EN1, but never touches the tables that
engine reads: the scalar lookup (tables 32 and 34) and the epsilon
coefficients (tables 31 and 33). They keep whatever they happened to
contain.

An MMIO capture of the proprietary wl driver 6.30.102.7 on a BCM6362 (N-PHY
rev 8, radio 2057 rev 8) shows it writing the scalar lookup with a fixed
set of 64 values per core, and clearing the 64 epsilon entries per core,
during init. The constants are the ones brcmsmac carries in
nphy_papd_scaltbl, and they match the capture exactly.

Do the same when enabling PAPD on radio 2057 rev 8. Other radios keep the
current behaviour, since the state their PAPD engine expects has not been
checked against hardware.

This does not add the PAPD calibration, which would compute the epsilon
values: it gives the engine a defined starting state instead of whatever
was left in the tables.



Verified: records #10966-#11740, from "TBL.WR   id=0x0020 off=0x0000 len=64"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows papd-tables

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0005

b43: fix the IPA 2 GHz bias registers on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: fix the IPA 2 GHz bias registers on radio 2057 rev 8

The rev 7 and rev 8 arm of the internal PA workarounds writes 0x5F and
0xE8, which are IPA2G_GAIN_CORE0 and IPA2G_IMAIN_CORE1: one register from
each pair, on different cores. The core offset between the two cores of
this radio is 0x85, so the counterpart of IPA2G_IMAIN_CORE1 is
IPA2G_IMAIN_CORE0 at 0x63, not 0x5F.

An MMIO capture of the proprietary wl driver 6.30.102.7 on a BCM6362 (N-PHY
rev 8, radio 2057 rev 8) writes, at the same point of the init and in both
of the two init sequences it contains:

	0x63 = 0x14	IPA2G_IMAIN_CORE0
	0xE8 = 0x14	IPA2G_IMAIN_CORE1

that is, IMAIN on both cores with the same value, and never touches 0x5F.
b43 instead leaves IMAIN_CORE0 alone, writes the core 0 gain register with
a value meant for the bias, and programs the two cores differently.

Give rev 8 its own case and program IMAIN on both cores there, using the
symbolic names. Radio rev 7 keeps its own case and its current behaviour:
there is no capture from hardware with that radio, the pattern may well be
wrong there too, and whoever gets to look at it should not have to reason
about rev 8 at the same time.

Both cases keep the 20 MHz and 40 MHz arms separate. The 40 MHz values are
unchanged in both, and carry a TODO: the vendor driver does not use 40 MHz
in 2.4 GHz on the board the capture comes from, so checking them needs a
device that runs 40 MHz, not more work on this one.



Verified: records #605-#607, from "PHY.WR   addr=0x032f val=0x0003"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows ipa-bias

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0006

b43: measure the background noise on N-PHY

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: measure the background noise on N-PHY

Both halves of the link quality calculation return early unless the PHY is
a G, so on an N-PHY dev->stats.link_noise keeps the value it was
initialised with and mac80211 is handed a constant as the noise floor.

The N-PHY reports through the power indication block rather than through
JSSI: the ucode leaves one 32-bit complex power value per core in shared
memory, and brcmsmac turns it into dBm by scaling it down by the number of
samples the ucode averaged, converting to dB, and adding the fixed offset
of this chip family. Do the same, and clear the block before asking for a
sample so a stale one cannot be read as fresh.

Verified against an MMIO capture of the proprietary wl driver 6.30.102.7 on
a BCM6362: it reads the same four shared memory words, and running its
sampled values through this computation gives noise floors between -82 and
-88 dBm, per core.

The mechanism is per PHY type, not per revision: brcmsmac uses this same
path for every N-PHY revision, and the capture only covers rev 8. The
change is still bounded for the untested ones, since what they report today
is a value that is never measured at all.

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0007

b43: mark the unused RF control override field on N-PHY rev 7+

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: mark the unused RF control override field on N-PHY rev 7+

The rev 7+ RF control override table has an entry for field 0x0800, which
drives PHY registers 0x07B and 0x07E, the RX gain 1 and 2 controls. No code
path in the driver ever passes that field.

An MMIO capture of the proprietary wl driver 6.30.102.7 on a BCM6362 shows
it writing both registers during calibration, twelve times each. What b43
should do with them is not clear from the capture alone, since the driver
has no equivalent calibration to hang them off. Leave a marker so the next
person does not have to rediscover that the entry is dead.

Comment only.



Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n16165

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0008

b43: program the carrier sense thresholds on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: program the carrier sense thresholds on radio 2057 rev 8

The N-PHY carrier sense threshold and control registers have names in
phy_n.h and no writer: the driver leaves them at whatever the initvals put
there.

An MMIO capture of the proprietary wl driver 6.30.102.7 on a BCM6362 (N-PHY
rev 8, radio 2057 rev 8) clears bit 5 of both control registers and sets
both threshold 2 registers to 0x55, in the rev 7+ workarounds and
immediately before the gain control ones. Do the same.

Only for radio 2057 rev 8 in 2.4 GHz at 20 MHz, which is what the capture
covers. Note that neither brcmsmac nor the bcm-v4 notes write these
registers at all, so the capture is the only source here.



Verified: records #680-#770, from "PHY.MOD  addr=0x01d9 val=0x0000 mask=0x0020"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows gain-control

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0009

b43: program the PAPD epsilon offset on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: program the PAPD epsilon offset on radio 2057 rev 8

b43_phy_initn() writes nphy->papd_epsilon_offset[] into the EPS table
adjust registers, but nothing ever computes it, so the PAPD engine gets an
offset of zero.

brcmsmac computes it at the end of its PAPD calibration:

	offset = -60 + 27 + eps_offset - (padgain_delta[pad_gain] + 1) / 2

with eps_offset -1 for this radio in 2 GHz, and pad_gain the index its PAPD
gain search settles on. b43 has no PAPD calibration, so take the index the
vendor driver settles on: an MMIO capture of wl 6.30.102.7 on a BCM6362
shows 15 for both cores, and the -24 that comes out of the formula is what
it writes. b43 currently writes 0, which is 24 dB off.

The pad gain delta table is the one the previous patches already carry, so
the formula is evaluated rather than its result hardcoded: when the gain
search arrives, only the index has to come from it.




Verified: records #286-#288, from "PHY.MOD  addr=0x0298 val=0xf400 mask=0xff80"
Verified: records #13842-#13847, from "PHY.MOD  addr=0x0298 val=0xf400 mask=0xff80"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0010

b43: fix the N-PHY sample table generation

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: fix the N-PHY sample table generation

b43_nphy_gen_load_samples() is meant to fill the SAMPLEPLAY table with one
period of a tone, which is the stimulus every N-PHY calibration that plays
samples depends on. It does not: the table it writes carries no tone at
all, and the samples it does write lose their in-phase component.

Two independent slips, in the two functions that build the table.

The phase step is computed as

	rot = (((freq * 36) / bw) << 16) / 100;

into a u16, while cordic_calc_iq() takes whole degrees and scales its
argument itself. The pre-scaling by 2^16 is therefore not needed, and it
also makes the result a multiple of 65536 whenever (freq * 36) / bw is a
multiple of 100 - which holds for every frequency the driver asks for: 2500
and 5000 kHz from the TX IQ/LO calibration, 4000 kHz from the idle TSSI
measurement and from the rev 2 RX IQ calibration. So rot truncates to
exactly 0, the angle never advances, and all len samples come out equal.
What should be a tone is a DC level.

The second is a precedence slip in the packing:

	data[i] = (samples[i].i & 0x3FF << 10);

<< binds tighter than &, so this masks with 0x3FF << 10 instead of shifting
the masked value into place. For the amplitudes actually used the in-phase
field lands in the low ten bits and is masked away to zero; negative values
leave the sign extension behind instead.

Neither slip is visible without the other fixed, which is why this is one
patch. Against an MMIO capture of wl 6.30.102.7 on a BCM6362 (N-PHY rev 8,
radio 2057 rev 8), for the 2500 kHz 250-amplitude tone the TX IQ/LO
calibration plays:

	mainline			160 of 160 words wrong (all zero)
	packing fixed alone		140 of 160 wrong (constant 0x3e800)
	phase step fixed alone		120 of 160 wrong (in-phase lost)
	both				160 of 160 identical

The zero-amplitude tone the idle TSSI measurement plays is 160 zero words
either way, and stays identical to the capture.



Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n23018
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n23057
Verified: records #1288-#1609, from "TBL.WR   id=0x0011 off=0x0000 len=160"
Verified: records #8638-#8959, from "TBL.WR   id=0x0011 off=0x0000 len=160"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows sampleplay-tssi, sampleplay-iqlo

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0011

b43: tune the 5 GHz radio registers on the 2 GHz channel

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: tune the 5 GHz radio registers on the 2 GHz channel
 tables for radio 2057 rev 8

b43 carries two shapes of rev 7+ channel table: the full one, and a 2
GHz-only one that drops the ten 5 GHz tuning fields to save space. Dropping
the fields also dropped their writes, so a channel switch on a board that
uses a 2 GHz table leaves LOGEN_MX5G_TUNE, LOGEN_INDBUF5G_TUNE,
PGA_BOOST_TUNE, and the TXMIX5G, PAD5G and LNA5G registers of both cores
holding whatever the previous channel left there.

They are not left alone by the hardware's own drivers. brcmsmac keeps one
table for both bands, and in chan_info_nphyrev8_2057_rev8 every 2 GHz row
holds zero in those ten columns, so it writes ten zeroes on each switch. An
MMIO capture of wl 6.30.102.7 on a BCM6362 (N-PHY rev 8, radio 2057 rev 8)
does the same: each of the ten is written, with the value zero, at all 31
channel switches in the capture, across five channels and two interface
cycles.

The order matters and is not the obvious one - the ten are interleaved with
the 2 GHz writes, not appended: 0x43 right after 0x41, 0x4a after 0x47, the
three core-0 registers between PAD2G and LNA2G. That is the order b43's own
full-table path already uses, and the order used here.

Gated on radio 2057 rev 8, the only combination the capture covers. Two
other boards take the 2 GHz path, phy rev 8 with radio rev 5 and phy rev 17
with radio rev 14; brcmsmac has no 2 GHz rows for either radio, so there is
nothing to compare them against and they keep their current behaviour.

With this the channel switch to channel 6 reproduces the capture with no
missing operation: the first 33 of the window's 39 match position by
position, and the remainder are the same operations with the same values
three positions out, because the harness records three MMIO accesses the
vendor tracer does not. Before, 11 of 39 matched and ten operations were
missing.



Verified: records #34940-#34990, from "RAD.WR   addr=0x0016 val=0x0058"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows chanswitch-ch6

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0012

b43: initialise the PAPD tables from the calibration, not from

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Tue, 4 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: initialise the PAPD tables from the calibration, not from
 PHY init

The scalar and epsilon tables the PAPD engine reads were being written from
b43_phy_initn(). That is not where the hardware's own driver writes them.
In an MMIO capture of wl 6.30.102.7 on a BCM6362 (N-PHY rev 8, radio 2057
rev 8), the scalar table appears exactly twice in 70796 records, once per
interface init, and both times inside the PAPD calibration - never during
the PHY init. Same for the two epsilon tables.

brcmsmac agrees: wlc_phy_a4(), its PAPD calibration, writes all four, and
wlc_phy_init_nphy() writes none of them.

So put them behind a b43_nphy_papd_cal(), which is where the rest of the
calibration will go, and call it where brcmsmac calls wlc_phy_a4(): from
wlc_phy_cal_perical_nphy_run()'s position between the TX IQ/LO and the RX
IQ calibrations, and from the periodic-calibration branch of the init,
which is the one b43 takes by default since b43_nphy_op_prepare_structs()
sets perical to 2 - PHY_PERICAL_MPHASE - and which was an empty statement
with a TODO.

The revision test moves into the new function, so nothing changes for any
radio other than 2057 rev 8, and nothing changes for a non-IPA board.

Against the capture this is worth 1030 more operations in common over the
whole init, 3404 to 4434, and the offset between the two sequences drops
from 738 to 218 because the block is no longer in the wrong place. The
scalar tables now match for 260 consecutive operations starting at the
capture's #10966, inside the calibration, where before they matched
nothing.



Verified: records #10966-#11740, from "TBL.WR   id=0x0020 off=0x0000 len=64"
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py, windows papd-tables

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0013

b43: write only the radio 2057 rev 8 registers the blob flags

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Wed, 5 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: write only the radio 2057 rev 8 registers the blob flags
 for init

r2057_rev8_init[] carries all 412 entries of the proprietary driver's
regs_2057_rev8 table, and r2057_upload_inittabs() writes every one of them.
The table has a third field that says which of them are for init, and it
was lost on the way in: each record in the blob is six bytes, u16 address,
u16 init, u8 do_init, u8 pad, and only 39 have do_init set.

The values were transcribed perfectly - all 412 match the blob's init
column. What was dropped is which ones to write. brcmsmac keeps the same
field, as u8 do_init in struct radio_20xx_regs, and honours it in
wlc_phy_init_radio_regs_allbands().

The capture agrees with the flag exactly: in the radio init phase,
everything before the first channel switch, the vendor writes all 39 of the
flagged registers and nothing else from this table, with the flagged value
in every case and no exceptions. The four further radio registers it
touches there - 0x11, 0x2e, 0xce, 0x164 - are written with values this
table does not hold, so they come from elsewhere.

Filtered rather than given a third column, because that is what the six
other r2057 tables in this file already are: rev4 has 42 entries against
the 42 brcmsmac flags, rev5 44 against 44, rev7 54 against 54. Only rev 8
departed from it.

Note for the archives: b43 previously had a 54-entry r2057_rev8_init inside
a TODO block, which hangs the radio with a "Microcode not responding"
timeout and whose origin was unclear. It is brcmsmac's do_init set, and it
disagrees with the blob's - 21 registers brcmsmac flags that the blob does
not, and 6 the blob flags that brcmsmac does not. brcmsmac's flags are
older than this radio.

NOT TESTED ON HARDWARE, and the failure mode of getting this wrong is the
radio hanging at init, so it wants a boot on a BCM6362 before it goes
anywhere.

Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_cmn.c?id=848acc8ffe1b#n897
Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0014

b43: run the periodic calibration from the N-PHY init

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: run the periodic calibration from the N-PHY init

b43_phy_initn() ends with a two way branch on nphy->perical. The driver
sets perical to 2 during the init, so on every device the branch that is
taken is the one that tests nphy->mphase_cal_phase_id, and that one only
initialises the PAPD tables: the TX IQ/LO, RX IQ and RSSI calibrations,
which the other branch performs, never run.

brcmsmac reaches the same point through wlc_phy_cal_perical() with
PHY_PERICAL_PHYINIT and, with no multi-phase calibration pending, runs
the whole sequence in one go: TX IQ/LO, then PAPD, then RX IQ, then the
TX power control coefficients, then RSSI. The RSSI calibration is part of
the sequence because the calibration type is not PHY_PERICAL_AUTO, and it
is the reason the vendor driver calibrates the RSSI twice per init.

An MMIO capture of wl 6.30.102.7 on a BCM6362 (N-PHY rev 8, radio 2057
rev 8) shows exactly that order, and the second RSSI calibration is a
region of the capture that the port did not reproduce at all.

Do the same, limited to phy rev 8 with radio 2057 rev 8, which is the
combination the capture covers.

Verified: records #22247-#23771 (second RSSI calibration) and #23772-#26100
Link: https://github.com/aleferri/b43-6362-wip/blob/58458f8/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n25386

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0015

b43: run the frame of the PAPD calibration on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: run the frame of the PAPD calibration on radio 2057 rev 8

b43_nphy_papd_cal() writes the tables the PAPD engine reads and stops
there. What the vendor driver does around them is hold the receive reset
off, take the transmit chain of one core and point it at the receive chain
through the coupler, put a tone into it, and hand all of it back
afterwards. That is the frame the gain index search runs inside, and
without it the search would have nothing to measure.

Add the frame, which is brcmsmac's wlc_phy_papd_cal_setup_nphy() and
wlc_phy_papd_cal_cleanup_nphy() for N-PHY rev 7 and up, together with the
parts of wlc_phy_a4() itself that surround them: the receive reset saved
and cleared between the scalar tables and the epsilon tables and written
back at the end, the baseband multipliers saved before the per core loop,
the comparison shift switched off again after it, and the transmit digital
filter the calibration runs behind - row 3 of tbl_tx_filter_coef_rev4
while it runs, the filters the PHY init programmed once it is over.

Neither the filter nor the cleanup is separable from the setup. Leaving
the calibration's filter in place outside the calibration is worse than
not touching it, and a setup with no cleanup leaves the RF control
overrides, the AFE overrides and the coupler forced on.

The epsilon tables now go out one cell at a time instead of as a bulk of
64. brcmsmac and the hardware's own driver both do it that way; a bulk
leaves the same tables behind and costs one table address setup instead of
64, but it also leans on the table address incrementing by itself, which
nothing here has ever tested.

Only the 2 GHz path is here. The 5 GHz coupler takes different constants
and no capture of it exists, so the calibration returns before the frame
outside 2 GHz, and the existing revision test keeps every other radio on
what it did before.

What measures the tone and writes the epsilon table, brcmsmac's
wlc_phy_a3_nphy() and wlc_phy_a2_nphy(), is still missing, so between the
setup and the cleanup nothing happens yet and the engine keeps running on
the cleared tables. The calibration is a no-op with a cost, and it is
worth landing in this shape because it is the part that can be checked
against a capture without any new arithmetic.

Checked as one contiguous region rather than per function, because the
harness's read plans are positional and only serve the value the hardware
gave if the port makes the same reads in the same order. Of the 2486
operations wl 6.30.102.7 issues between the scalar table and the filters
at the end, 1830 are in blocks common to both sequences, in the same order
and with the same values read back, the first of them 847 long. The two
gaps that are left, 349 and 276 operations, are the gain index search for
the two cores.

The same shape comes out of a second, independent capture, the one of a
cold init: the same 1830 operations in blocks, the same first block of 847,
and gaps of 920 and 930 where that one runs a full gain search instead of a
soft one.

Two gaps are values and not sequences, and both are on registers nothing
writes: the transmit/receive coupling attenuation of the two cores, which
the vendor reads as 0xaa and the port as a zero. That value is the chip's
own default - it is in neither driver's radio table, and the vendor never
writes it either - so the only place it exists is the capture. The third is
the read of radio 0x81 described above.

One operation of the vendor's has no counterpart: a read of radio 0x81,
TR2G_CONFIG1_CORE0_NU, which it makes once per core inside the setup,
between the four AFE reads and the four modifications of the same
registers. The register is written once per init, with 1, and read four
times in 70796 records, always in that one place; brcmsmac never touches
it. Whether the value is used for anything is not visible in a capture, so
nothing here reads it.

Verified: records #10966-#13918, from
"TBL.WR   id=0x0020 off=0x0000 len=64"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n25108
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n24242
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n24496
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n14735
Link: https://github.com/aleferri/b43-6362-wip/blob/04e05f5/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/04e05f5/test/phase_compare.py, region papd-cal

While the frame is going in, name the two registers the channel measurement
reads. On N-PHY rev 8 the addresses 0x1C9 and 0x1CA are not the GPIO output
latches the existing names say: the capture reads them 3400 times in 70796
records and writes them never, and what comes back is a pair of
sign-extended 6 bit fields with one of them noise around zero. The old
names stay for the revisions that do use them as output latches; the new
ones sit beside them.

The measurement itself, 100 samples of one core then 100 of the other
inside the same eight register save and restore that frames
b43_nphy_poll_rssi(), is here but has no caller, and that is a measured
result rather than an omission: putting it at the end of the channel switch
costs 74 operations of the window this patch is verified against, because
the vendor driver does not take the measurement while an interface comes
up. It takes it on the channel switches of a scan. So it belongs above the
PHY, and this is not the patch that finds out where.

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0016

b43: hand the PHY to the RX IQ calibration and take it back

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: hand the PHY to the RX IQ calibration and take it back

b43_nphy_rev3_cal_rx_iq() returns an error for every N-PHY rev 3 and up,
so the RX IQ calibration does not run at all. Behind that stub sit 7510
operations of an MMIO capture of wl 6.30.102.7 on a BCM6362 (N-PHY rev 8,
radio 2057 rev 8), a third of an interface coming up.

Add the frame the gain sweep runs inside, which is brcmsmac's
wlc_phy_rxcal_physetup_nphy(), wlc_phy_rxcal_radio_setup_nphy() and the two
cleanups for rev 7 and up: fifteen PHY registers saved and put back, the PAPD
comparison off on both cores, the transmit chain pointed at the core being
calibrated and the receive chain at the other one - which is the way round
rev 7 does it, earlier revisions swap them - the AFE handed over, nine RF
control overrides, a receive to transmit sequence, and the TR switch
forced on the core being calibrated. On the radio side rev 7 and up touch
the two transmit/receive coupling registers of that core and nothing else,
the rest of that function being the radio 2056 path; the values differ from
the ones the PAPD calibration writes, 0x3 and 0x7f against 0xc and 0xf0,
because this one couples a receive chain rather than driving a tone into
it.

The four extra registers rev 7 saves, the RF control override enables
0x342, 0x343, 0x346 and 0x347, need four more slots in
tx_rx_cal_phy_saveregs, which was sized for the eleven the earlier
revisions use. Nothing else indexes past ten, so the earlier revisions are
unaffected.

What measures the tones and computes the IQ coefficients is not here, so
the function still returns an error: that is deliberate, because
b43_phy_initn() only calls b43_nphy_save_cal() when this returns zero and
there is no calibration to save.

Say plainly what this buys against the capture: nothing yet. The PAPD
frame in the previous patch showed up as matching operations because the
tone and the table writes around it lined up; here the setup is followed
immediately by its own cleanup, while in the capture seven thousand
operations of gain sweep sit between them, so there is nothing to line up
with. It is the frame the sweep needs, verified to build and to run in the
position the capture puts it - after the PAPD calibration - and no more
than that.

Verified: records #14093-#22246, from
"TBL.WR   id=0x0007 off=0x0110 len=2"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n26701
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n26828
Link: https://github.com/aleferri/b43-6362-wip/blob/88456cb/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0017

b43: choose full or partial calibration instead of always full

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: choose full or partial calibration instead of always full

The periodic calibration sequence the previous patch reaches from the PHY
init asks for a full TX IQ/LO calibration every time. brcmsmac decides:
wlc_phy_cal_perical_nphy_run() calibrates fully when the channel is not the
one the calibration last ran on and partially when it is, which is the same
test b43_nphy_restore_cal() already makes before it reuses the stored
coefficients. Make the same choice from the same state.

The type the RX IQ calibration is asked for stays 2, the full one, and that
is not an oversight: brcmsmac asks for 2 on the first calibration after an
association and 0 afterwards, and b43 tracks nothing equivalent. Of the two
constants 2 is the conservative one, since 0 skips most of the work.

There is no operation count to show for this against the capture, and the
reason is worth stating: both captures are of an interface coming up on a
channel nothing has calibrated yet, so the test comes out full in both and
the sequence does not change. What changes is the second and later times,
which no capture covers. It goes in because the constant was wrong, not
because it moves a number.

Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n25386

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0018

b43: run the RX IQ calibration gain sweep on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: run the RX IQ calibration gain sweep on radio 2057 rev 8

b43_nphy_rev3_cal_rx_iq() had the per-core setup and cleanup of the RX IQ
calibration and nothing in between. Behind that sit 7510 operations of an
MMIO capture of wl 6.30.102.7 on a BCM6362 (N-PHY rev 8, radio 2057 rev
8), a third of an interface coming up. Fill in the three pieces that were
missing, which arrive together because none of them measures anything on
its own.

First, the frame around the per-core loop, which is the rest of
brcmsmac's wlc_phy_cal_rxiq_nphy_rev3(): clear the receive reset bit of
the baseband configuration and put the register back, hold the PHY in
carrier search for the whole calibration, save the transmit gain of the
two cores and program the gain the calibration asks for in its place,
skip a receive core that is switched off, reset the receive chain after
each core, and on the way out reset the carrier sense, drop the receive
gain override and put the saved gain back. Every piece of this is already
in b43: the gain comes from b43_nphy_iq_cal_gain_params(), which the
transmit IQ/LO calibration in this file uses for the same purpose, and
the state of the receive cores from b43_nphy_get_rx_core_state().

Second, b43_nphy_txpwr_index(), which is brcmsmac's
wlc_phy_txpwr_index_nphy() for a non-negative index: the sweep drives its
tone at a transmit power index its gain ladder names, and b43 had no way
to program one. b43_nphy_tx_power_fix() is a different job - it takes the
index from the SPROM, or hardcodes 30 on rev 7 and up, and does both
cores. The index selects one cell in each of four tables 128 cells apart
in the per-core power control table: the transmit gain at 192, the IQ
compensation at 320, the local oscillator compensation at 448, and on an
internal PA the RF power offset at 576. The capture shows all four reads
with the same index, so the layout is not taken on trust - the sweep uses
index 10, giving offsets 0xca, 0x14a, 0x1ca and 0x24a, and the tail of
the PAPD calibration uses index 30, giving 0xde, 0x15e, 0x1de and 0x25e.

Third, the sweep itself, brcmsmac's wlc_phy_rxcal_gainctrl_nphy_rev5() on
its rev 7 and up path: zero the receive IQ compensation, then walk a six
step ladder of receive gains - the two low pass filter biquad stages, the
second and first low noise amplifier - driving a tone at each step and
reading the power back from the IQ estimator. Above a threshold it steps
down, below it steps up, and it stops on the first step that crosses.
Then it trims the second biquad stage by the difference between the power
it wanted and the power it got, programs that, and puts the saved
compensation back.

Three things the reference has are deliberately not here. Its rxgain
output argument, because both of its call sites pass NULL and nothing
reads what it would return. Its 5 GHz ladder, because four of those six
steps ask for a fixed transmit gain rather than a power control index,
and that gain is built from a value b43 does not keep - the reference
reads it out of the transmit gain table, and the one line that would
store it in this file sits inside an #if 0. The caller is restricted to
2 GHz for that reason: a ladder step that cannot be programmed is worse
than a ladder that stops at the band the capture covers. And the negative
index of txpwr_index(), which replays state the reference saves on the
first call and that nothing in b43 asks for.

One difference from b43's own tx_power_fix is worth naming rather than
hiding: it narrows the DAC gain to three bits on rev 7 and up, where the
reference takes six. This takes six, because it is a port of the
reference. The capture cannot tell them apart - the field reads zero on
every call in it - so it is not decided by measurement.

Measured with test/phase_compare.py on the two contiguous-block windows:
up-ch1 goes from 5791 of 22951 to 11552 (25% to 50%), up-ch1-freddo from
8746 of 27571 to 13511 (32% to 49%), and PHY registers covered from 194
of 218 to 203. The shape matches too, and that is the stronger statement:
the capture has three iterations per core, each a transmit index followed
by a tone, and the port produces the same three per core, each as a run
of 85, 103, 85 and 420 matching operations.

One block of the previous measurement changes hands and it is not a
regression: the 172 operations at #13921, the two 84-cell clears of the
power control table, lose their assignment to one of the six identical
clears the sweep now performs, because the block assignment is exclusive
and greedy. Measured on that region alone the port is unchanged before
and after - the same 172 operations from the same position, 178 of 183.

What is still missing is the measurement the sweep sets the gain up for:
the tone at the requested calibration type and b43_nphy_calc_rx_iq_comp()
after it. So this still returns an error, deliberately - b43_phy_initn()
only calls b43_nphy_save_cal() when this returns zero, and there is no
calibration to save.

Verified: records #14951-#21136, from
"TBL.RD   id=0x0007 off=0x0110 len=2"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n27304
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n28295
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n26855
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n241
Link: https://github.com/aleferri/b43-6362-wip/blob/23190a0/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/23190a0/test/phase_compare.py

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0019

b43: set the pre-calibration transmit gain on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: set the pre-calibration transmit gain on radio 2057 rev 8

b43_nphy_periodic_calibration() reads the gains the calibrations aim for
and hands them to all of them, but it reads them off whatever gain
happens to be programmed. The reference programs a gain first and reads
back after, and this file has said so for years: the line before the
second read is /* TODO N PHY Pre Calibrate TX Gain */.

The consequence is measurable, and it is a wrong value rather than a
missing operation, which is why nothing had caught it. With the current
gain of 0x4027 the calibration gain works out to 0x4027 as well - a round
trip - so b43 writes 0x4027 into the two RFSEQ gain cells. The capture
writes 0x4077 in the same place, twice: at #8511 for the transmit IQ/LO
calibration and at #14983 for the RX IQ one. Decomposed with the rev 7
and up formula, txgm, pga and ipa agree and pad is 4 against 14.

Neither the decode nor the gain formula is at fault: b43_nphy_get_tx_gains()
and b43_nphy_iq_cal_gain_params() are line for line the reference's
wlc_phy_get_tx_gain_nphy() and wlc_phy_iqcal_gainparams_nphy(), and both
drivers read the same 0x4027 out of the table. What differs is that the
reference calls wlc_phy_precal_txgain_nphy() in between and reads the
gains a second time, and by then the table holds the gain of a chosen
power control index. The capture shows both reads: 0x4027 at #7038, then
0x4077 at #8080.

Add that step. It is three lines now that b43 can program a power control
index.

The index is 10, and it is not the one the reference would pick: it keeps
10 for radio 2057 rev 3, 4 and 6 and 0 for everything else, which puts
rev 8 on the 0. The capture reads offset 0xca of the per-core power
control table, which is 192 + 10, so on this radio the vendor driver uses
10. That grouping in brcmsmac predates this radio - the same way its rccal
grouping does, where radio rev 8 also does not belong to the 3/4/6 group -
so the capture decides it. Gated on phy rev 8 and radio rev 8 for that
reason, in both calibration branches.

With it the two gain cells become 0x4077, identical to the capture.
Measured with test/phase_compare.py on the contiguous-block windows:
up-ch1 goes from 11552 of 22951 to 12363 (50% to 54%), up-ch1-freddo from
13511 of 27571 to 14353 (49% to 52%).

There is a cost and it is not an assignment artifact, so it gets said
plainly. Measured on the PAPD calibration region alone, #10962-#14092,
the port goes from 2023 of 2662 matching operations to 2014, and from 16
contiguous blocks to 25. Two sub-regions carry it: #12700-#12950 loses 6
of 164 and #13700-#13870 loses 6 of 114. Nine operations against 811
gained is a trade worth taking, but why the PAPD calibration matches
slightly worse when it runs at the gain the vendor uses is not explained
here, and it is the next thing to look at rather than something to round
away.

Verified: records #7038-#8085, from
"TBL.RD   id=0x001a off=0x00ca len=1"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n17949
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n18345
Link: https://github.com/aleferri/b43-6362-wip/blob/23190a0/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/23190a0/test/phase_compare.py

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0020

b43: put the transmit power index back after the PAPD calibration

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: put the transmit power index back after the PAPD calibration

The PAPD calibration turns the transmit power control off and programs
its own gain, and brcmsmac puts the index back at the end of wlc_phy_a4(),
one core at a time, from the internal index it keeps per core. b43 does
neither, so whatever the previous patch programmed for the calibrations
stays programmed afterwards.

Add both halves. The internal index has been sitting in this file behind a
comment - the two lines that store it in b43_nphy_tx_power_fix() were
commented out, reasonably enough while nothing could program an index at
all - so uncomment them and put the restore at the end of the PAPD
calibration, gated on the power control being off, which on this radio it
is because the calibration turned it off itself.

It matters beyond the two gain cells. The next tone saves the baseband
multiplier before it plays and puts it back when it stops, so leaving the
calibration's index programmed leaks its multiplier into everything
downstream: the capture restores 0x2c2c into the multiplier cell at #12785
and #12867, and without this the port restores 0x2e2e there, which is the
multiplier of the index the calibration ran at.

The two operations are in the capture where the reference puts them, one
core each: #14305 writes the gain cell of core 0 and #14728 that of core
1, both reading offset 0xde of the per-core power control table, which is
192 + 30. Thirty is what b43_nphy_tx_power_fix() already picks for phy rev
7 and up, so the value is not new, only the storing of it.

Measured with test/phase_compare.py on the contiguous-block windows:
up-ch1 goes from 12363 of 22951 to 13134 (54% to 57%), up-ch1-freddo from
14353 of 27571 to 15087 (52% to 55%). No block of the previous measurement
is lost or shortened, which is worth saying because the previous patch did
shorten some.

It does not close the nine operations that patch cost inside the PAPD
calibration region, and it was expected to: those sit at #12785 and
#12867, which is before this restore runs, so the port is still on the
calibration's index there while the vendor is already back on 30. What
puts it back that early in the vendor driver is not any of the four
restore sites brcmsmac has - all of them are either on the rev below 7
path or after the PAPD calibration - so the answer is not in the
reference's control flow and has to come from the capture: it wants the
history of that one multiplier cell across the whole run, which no tool
here produces yet.

Two things check_patch_gating.py flags, both declared rather than worked
around. It marks b43_nphy_papd_cal() as ungated: the gate is the early
return on phy rev 8 and radio rev 8 at the top of that function, which
arrived with the PAPD frame, and the tool looks for one near the hunk
rather than at the top of the function the hunk is in. And it points at
b43_nphy_tx_power_fix(), which is shared by every N-PHY: the uncommented
lines run everywhere. What they store is read in exactly two places -
cal_orig_pwr_idx, which this file writes and never reads, and the restore
this patch adds, which is gated - so on any other revision the store has
no observable effect.

Verified: records #14297-#14340, from
"TBL.RD   id=0x001a off=0x00de len=1"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n25370
Link: https://github.com/aleferri/b43-6362-wip/blob/8491752/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/8491752/test/phase_compare.py

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0021

b43: hand the transmit power index back after reading the gains

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: hand the transmit power index back after reading the gains

The pre-calibration index was added two patches ago to make the gains the
calibrations aim for come out right, and it left the index programmed. The
vendor driver does not: it forces the index, reads the gains off it, and
hands the chain straight back what it had - the radio gain, the DAC gain,
the baseband multiplier and the IQ and local oscillator compensations. The
calibrations then run on the hardware they would have run on anyway, with
the gains read at the forced index.

That is worth stating plainly because it is the opposite of what the name
suggests: the forced index is a measurement, not a setting.

Add the other direction of b43_nphy_txpwr_index(), a negative index, along
with the save it needs on the first forced index and the per-core record
of whether one is forced at all. That record starts at -1 rather than
zero, which would mean index zero rather than none.

Where the body comes from and where the position comes from are different,
and both are named: the body is brcmsmac's wlc_phy_txpwr_index_nphy() for
a negative index, which that driver has in full. The call site is not -
brcmsmac hands the index back at the end of its periodic calibration, not
before it, and the four other places it does so are all on the phy rev
below 7 path. So the position is the capture's: #8086-#8110 for core 0 and
#8286-#8310 for core 1, each the exact operation sequence of that branch -
the two override bits, the DAC gain, the radio gain cell going back to
0x4027 which is the value from before the forced index, and the read
modify write of the multiplier cell.

This closes the nine operations the pre-calibration patch cost, and it was
found by looking at the history of one table cell rather than by reading
the reference: reverse-tools/trace_tables.py --cell 0xf:0x57 shows the
multiplier going 0x2c2c, then 0x2e2c and 0x2e2e as the index is forced on
each core, then back to 0x2c2e and 0x2c2c at #8096 and #8294, and staying
there through the PAPD calibration. The port was staying at 0x2e2e.

Measured with test/phase_compare.py on the contiguous-block windows:
up-ch1 goes from 13134 of 22951 to 13625 (57% to 59%), up-ch1-freddo from
15087 of 27571 to 15513 (55% to 56%). The PAPD calibration region is back
to where it was before the pre-calibration patch, 2023 of 2662 matching
operations in 16 contiguous blocks rather than 2014 in 25.

Five blocks of the previous measurement no longer appear at their record,
and all five are merges into a longer block starting earlier, checked one
at a time: #12788 of 78 and #12870 of 59 become the single 145 at #12784,
which is the run the pre-calibration patch had split in two; #13756 of 78
becomes 90 at #13752; #8983 of 22 becomes 25 at #8979. The fifth, #11760
of 55, has no neighbour, so it was measured on its own region: 120 of 122
in three blocks before, 121 of 122 in two blocks after.

check_patch_gating.py marks two things ungated and both are declared.
b43_nphy_txpwr_index() itself carries no revision test, and did not when it
arrived either: its gate is in its callers, all of which test phy rev 8 and
radio rev 8. And b43_nphy_op_prepare_structs() is common to every N-PHY, so
the two lines that start the per-core record at -1 run everywhere. That
record is read in exactly one place, b43_nphy_txpwr_index(), which no other
revision reaches, so on anything else it is written and never read. It is
also the correct value rather than a convenient one: zero would claim index
zero is forced.

Verified: records #8086-#8310, from
"TBL.WR   id=0x000f off=0x0057 len=1"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n28325
Link: https://github.com/aleferri/b43-6362-wip/blob/8491752/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/8491752/reverse-tools/trace_tables.py

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0022

b43: treat the N-PHY DAC test as a mode, not a flag

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: treat the N-PHY DAC test as a mode, not a flag

wlc_phy_gen_load_samples_nphy() and wlc_phy_runsamples_nphy() take a u8
dac_test_mode and test it against one: the short sample table and the
sample command of 5 are for mode 1 alone, and every other value, including
2, takes the ordinary path. b43 narrowed that argument to bool all the way
down, so any mode above 1 turns the special path on.

Three places, all mechanical: the parameter of
b43_nphy_gen_load_samples(), b43_nphy_load_samples() and b43_nphy_tx_tone()
becomes a u8, the table length test becomes == 1, and so does the sample
command.

No caller in tree passes anything but 0 or 1, so nothing changes today -
this is the kind of latent narrowing that only bites the first caller with
a real mode. That caller is the RX IQ calibration, which is handed a
calibration type of 2 and passes it straight through, and the two are not
interchangeable: with the flag, mode 2 builds the 160 word tone off a
bandwidth of 80 or 82 instead of 20, so every sample is wrong.

Measured on an MMIO capture of wl 6.30.102.7 on a BCM6362, with the RX IQ
calibration in place and passing its real type: without this the port
matches 13875 of 22951 operations of an interface coming up, with it 14351,
and the difference is the two measurement tones, which appear as 336 and
334 operation contiguous runs. Alone it changes nothing, as above.

This is the same change as
patches/mainline/b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag, carried
here because this series applies as a block and the patch after this one
needs it. It leaves when that one lands, the way 0010 will.

Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n23043
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n23149

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0023

b43: measure the tone and compute the RX IQ coefficients

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: measure the tone and compute the RX IQ coefficients

The gain sweep exists to set a receive gain the tone comes back at a
workable power on, and until now nothing used it: the frame swept and then
threw the result away. Play the tone at the calibration type asked for,
compute the compensation from what the IQ estimator reports, and stop the
playback - brcmsmac's wlc_phy_cal_rxiq_nphy_rev3() again, the three calls
after its gain control. b43 already has all three.

With that the calibration succeeds, so it returns zero instead of an error,
and b43_phy_initn() calls b43_nphy_save_cal() for the first time on this
hardware. That is the point of the whole sequence: without it no
calibration is ever saved and b43_nphy_restore_cal() has nothing to reuse
on the next channel.

Stop degrading the calibration type as well. b43_nphy_cal_rx_iq() forced it
to 0 on phy rev 7 and up, which mattered because the type is what the tone
is generated with. It is not a gated change in form - the line was common
to every rev 7 and up - but it is in effect: the type is used in exactly
one place downstream, and that place returns an error immediately for
anything but radio 2057 rev 8.

That degrading looked like a defect and measuring it said the opposite at
first: keeping the real type made the port match 476 operations worse. The
reason is the previous patch - b43 tested the DAC test mode as a flag, so a
type of 2 built the tone off the wrong bandwidth. With the mode fixed, a
type of 2 and a type of 0 produce identical operations, which is what the
reference does, and the port carries the real type without paying for it.

Measured with test/phase_compare.py on the contiguous-block windows:
up-ch1 goes from 13625 of 22951 to 14351 (59% to 63%), up-ch1-freddo from
15513 of 27571 to 16231 (56% to 59%). The shape is the check that matters:
the capture plays a measurement tone after each core's sweep, at #17542 and
#20624, and those turn up as two new contiguous runs of 336 and 334
operations at #17538 and #20622. No block of the previous measurement is
lost or shortened.

Verified: records #17538-#20956, from
"TBL.WR   id=0x0011 off=0x0000 len=160"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n27351
Link: https://github.com/aleferri/b43-6362-wip/blob/d07e029/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/d07e029/test/phase_compare.py

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0024

b43: run the tail of the periodic calibration on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: run the tail of the periodic calibration on radio 2057 rev 8

The sequence this driver runs from the N-PHY init stopped at the RSSI
calibration. brcmsmac's wlc_phy_cal_perical_nphy_run() has three more steps
on the first calibration after an association, which an interface coming up
is: measure the idle TSSI again now that the calibrations have run, program
the transmit power control off it, and recalibrate the VCO. Add them.

All three are already in this file, run once from the init before the
calibrations; the vendor driver runs them in both places, and the capture
agrees - it writes the 64 cell power control table at #1740 and #5726 on
the way up and again at #24391, after the calibrations.

The VCO calibration needed extracting first: it sat inline at the end of
b43_radio_2057_setup(), which is the only thing that wanted it until now.
Same four register operations, one caller more.

While here, put b43_nphy_tx_pwr_ctrl_coef_setup() behind the same test the
reference has it behind - the RX IQ calibration having succeeded - instead
of running it either way. Now that the calibration can succeed the two
differ.

Measured with test/phase_compare.py: up-ch1 goes from 14351 of 22951 to
14807 (63% to 65%), and no block of the previous measurement is lost or
shortened. Five new contiguous runs, and two of them are the point: 334
operations at #23928, the idle TSSI tone, and 266 at #24391, the power
control table.

up-ch1-freddo goes the other way, 16231 of 27571 to 16156, and that number
is not a regression: the cold capture does not contain this phase inside
the window at all. Its window ends at #32769, which is where a 65285 record
hole starts, and the late power control table write is at #106217, on the
far side of it. So the operations this patch adds have nothing to match in
that window and can only redistribute the assignment, which is exclusive
and greedy. Checked rather than assumed: the three blocks that stop
appearing are all at the very end of the window, #32507, #32613 and
#32685, and measured on that region alone the port is identical before and
after - 183 of 217 in 29 contiguous blocks both ways.

check_patch_gating.py marks two things ungated and both are declared.
b43_nphy_cal_perical_phyinit() has no revision test of its own and never had:
its only caller tests phy rev 8 and radio rev 8. And b43_radio_2057_setup() is
shared, but what happens to it here is an extraction and nothing else - the
same four register operations in the same order, now behind a name. The
channel switch window of phase_compare.py is unchanged by it.

Verified: records #23928-#25000, from
"TBL.WR   id=0x001a off=0x0000 len=64"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n25476
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n20802
Link: https://github.com/aleferri/b43-6362-wip/blob/d07e029/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/d07e029/test/phase_compare.py

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0025

b43: limit the two-chain rate groups separately on radio 2057 rev 8

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: limit the two-chain rate groups separately on radio 2057 rev 8

The per-rate transmit power table the previous patch started filling comes
out wrong, and not by a little: computed from the SPROM offsets alone the
84 entries match 4 of the vendor driver's on one board and would match
none on another. What is missing is a ceiling, and not one ceiling.

The groups that use both transmit chains - CDD, STBC and SDM - are limited
3 dB below the same rates on one chain, and both ceilings sit below what the
SPROM asks for on some rates and above it on others.

The 3 dB is arithmetic and not a measurement: two chains radiating together
put out twice the power of one, so each has to come down by 10*log10(2) to
leave the total where the limit is. 68 - 56 = 12 quarter-dB is that factor
to two decimal places. So the difference does not need a table - it needs
the number of chains, which the driver knows.

Add b43_ppr_apply_max_group(), which is b43_ppr_apply_max() over one group
instead of all 52 rates - the same shape brcmsmac's
wlc_phy_txpwr_nphy_po_apply() has - and apply the two ceilings. Both are
minimums, so this can only ask for less power than the limit already
applied, never more.

The numbers are measured and not derived, so they are gated on the radio
they were measured on. Against captures of wl 6.30.102.7 and wl 7.14 on
two boards whose SPROM offsets differ by a factor of four, the 84 entries
now come out 84 of 84 on the first board and 82 of 84 on the second. The
two that differ are one group apart from the vendor's in the single-chain
column, which is an indexing difference and not a value one: the ceiling
decides, and the group that reads it is off by one. That is visible on one
board only - the other has SPROM offsets that are all equal, so its column
is uniform and cannot show it - so it is left alone rather than changed on
one board's evidence.

Two things this explains that the SPROM alone cannot. The two-chain
columns come out identical on both boards although their SPROM offsets do
not, because 56 is below the SPROM value for every rate in those groups
and so decides all of them - a driver computing from the SPROM produces
four different values there and the vendor produces one. And the zeros in
the single-chain column are not a clamp at zero but rates flattened onto
the ceiling, which is why the CCK entries are zero too.

The 68 is the part that is not settled, and it looks like regulatory data
rather than a property of the radio. The vendor driver carries its own
per-country limit tables compiled in - locales_2g_base and locales_2g_ht,
5744 and 7782 bytes on this board - and their contents are power limits in
quarter-dBm: the bytes read 76, 66, 60, 56, 48, 45. In the MIMO one, 56
appears 252 times and is one of the commonest values, which is where the
lower of these two ceilings comes from. The legacy table centres on higher
values.

So the absolute ceiling is a locale limit, and hardcoding it in a driver is
putting regulatory policy where Linux deliberately does not keep it. It is a
stopgap: the honest home for it is the regulatory database, and what the
driver should take from there is one EIRP per channel, then subtract the
antenna gain and the chain count itself. That does not work out yet -
Linux's 20 dBm less this board's 2 dB antenna gain is 72 quarter-dBm and not
68 - so what closes the gap is still missing, and until it is found this
patch programs a measured number on one radio rather than a derived one
everywhere.

check_patch_gating.py points at b43_ppr_add() in ppr.c, and that is the tool
seeing the new function land next to it rather than a change to it: the hunk
adds b43_ppr_apply_max_group() above, and touches nothing existing. The new
function carries no revision test, like the rest of that file - its gate is
in the caller, which tests phy rev 8, radio rev 8 and the 2 GHz band.

Verified: records #5986-#6157, from
"TBL.WR   id=0x001a off=0x0040 len=84"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n27900
Link: https://github.com/aleferri/b43-6362-wip/blob/2bc1a22/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
Link: https://github.com/aleferri/b43-6362-wip/blob/2bc1a22/router-data/vd630/fullinit.txt

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```


## 0026

b43: keep both baseband multiplier cells in step on N-PHY rev 7

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Thu, 6 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: keep both baseband multiplier cells in step on N-PHY rev 7

The baseband multiplier lives in two cells of the IQ/LO table, 87 and 95,
and b43_nphy_txpwr_index() was writing only the first. brcmsmac keeps them
together in wlc_phy_ipa_set_bbmult_nphy(), which writes the same value to
both, and this driver has that helper too - it arrived with the PAPD
calibration and has one caller.

The helper is not what this wants though, and the capture is why: it shows
the second cell being read before it is written, with the previous value
still in it, and only the calling core's half changed - the same
read-modify-write the first cell gets, not a copy of it. So do that, on
both.

Which callers touch both cells is measured and it is not by phase. Of the
70 writes to 87 in the capture, 40 have a write to 95 beside them and 30 do
not, and inside the gain sweep alone five are paired and seven are not. The
paired ones are the calls to this function - twelve of them, the
pre-calibration index, the handing back, the PAPD tail and the six sweep
iterations - and the PAPD calibration's own six. The bare ones are stopping
the sample playback and b43_nphy_tx_power_fix(), which are left alone.

Verified positionally rather than by eye, with a window on one call:
the operation sequence now matches the vendor driver's, the
read-modify-write on the second cell included. What still differs inside
that window is values and not operations, and they are the harness's: the
per-index cells of the power control table have no read plan, so the mirror
answers with the last thing written to the data port. That is why this does
not lengthen a matching run - a run breaks on any difference, a value one
included - and why the gain is 57 operations rather than the 240 the six
extra operations per call would suggest.

check_patch_gating.py marks b43_nphy_txpwr_index() ungated and it was when it
arrived: its gate is in the callers, all of which test phy rev 8 and radio
rev 8. The two helpers move up in the file so the function can reach them and
are otherwise unchanged.

Verified: records #15296-#15310, from
"TBL.RD   id=0x000f off=0x005f len=1"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n24234
Link: https://github.com/aleferri/b43-6362-wip/blob/2e298fc/router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0027

b43: read the two lpf bandwidth misc registers when playing samples

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: read the two lpf bandwidth misc registers when playing samples

On N-PHY rev 7 and up, b43_nphy_run_samples() reads the two rf control
override registers to find out whether the lpf bandwidth override is already
set, and stops there. The reference reads two more and throws both values
away, with a comment naming them: lpf_bw_ctl_miscreg3 and miscreg4.

The device does the same. Of the 28 reads of 0x340 in the capture, 22 are
preceded by exactly a read of 0x342 and a read of 0x343 - that is, every
sample play. The remaining six belong to two other sites, the override path
and the one that saves the registers around a temperature measurement, and
both of those b43 already has.

A discarded value is not a reason to drop the access: a read of a PHY
register is not free of side effects, and neither the reference nor the
capture gives any way to find out whether these two matter. They stay reads.

The measurement wants a note, because the headline number goes the wrong way.
Contiguous blocks on the up-ch1 region fall from 21110 to 19454, and the gain
sweep of the RX IQ calibration falls from 5784 paired operations to 4112. That
count answers "in what order", not "are they there": of the operations that
stop being paired, the port still emits every one somewhere - they move from
the displaced column to it, 58 to 1744 - while the absent column, which is
the one that measures this driver, goes DOWN in every region: 403 to 366 in
total, and 75 to 61 in the sweep itself. coverage.py over the same region is
identical before and after, 46 PHY registers of 46 and 332 table cells of 844.
Five phases improve: the RX IQ entry window from 57 declared divergences to
37, the second RSSI calibration from 940 paired operations to 960 of 960, the
idle TSSI run from 357 to 432, and the per-phase run total from 8779 to 8896.

Nothing here ran on hardware.

Verified: records #15843-#15847, from
"PHY.WR   addr=0x00a1 val=0x0000"
Link: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n23109

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0028

b43: rewrite the second transmit filter row on the BCM6362

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: rewrite the second transmit filter row on the BCM6362

b43_nphy_int_pa_set_tx_dig_filters() writes the first three rows of
tbl_tx_filter_coef_rev4 to 0x186, 0x195 and 0x2c5, fifteen registers each, and
then writes the second row to 0x195 a second time only when the PHY revision
is 17.

This device is N-PHY rev 8 and does it too. The capture shows the write twice
over, at two independent points: records #304 and #334 during init, and #13874
and #13904 at the tail of the power detector calibration. Both times the
fifteen values are the same as the first pass, so the register file ends up in
the same state whether the second write happens or not.

Leaving it out is still wrong, and the reason is the shape rather than the
state. The three rows are written back to back as one block of forty-five
registers; a missing group of fifteen in the middle of it means nothing after
that point sits where the device puts it. With the write in place the window
that covers this function goes from fifteen operations short to matching the
capture exactly, sixty of sixty, and the whole init region gains fifteen
paired operations.

The gate is the revision this was measured on. brcmsmac does not write 0x195
twice in the 20 MHz path, so the capture is the only evidence, and it is not
evidence about any other revision.

Nothing here ran on hardware.

Verified: records #13874-#13918, from
"PHY.WR   addr=0x0195 val=0xffb3"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0029

b43: bracket the whole power detector calibration once, not once per pass

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: bracket the whole power detector calibration once, not once per pass

b43_nphy_papd_cal() turns the transmit power control off and back on around
each pass of the engine, two passes per chain, four brackets in all. What the
restore does is reprogramme the adjusted power table, eighty-four cells on each
of two tables, and the capture disagrees about how often that should happen: in
the whole region the device writes that table exactly once, at the end.

The count is worth spelling out because it is the only place where it does not
line up. Attributing each of the driver's writes to a region of the capture
through the paired operations, so the record numbers are the capture's own
rather than guessed:

  region              device   driver
  init                    13       13
  power detector cal       1        8
  receive I/Q entry        7        7
  receive I/Q gain sweep   9        9
  second RSSI cal          0        0
  tail                     6        6

Every region matches write for write except this one, and the seven extra are
all here.

So bracket once, around the whole calibration, and close it after the filter
rows at the end - which is where the device writes the table, immediately after
the last of those rows. The passes still need the control off and still get it:
the disable only touches the table when the control is on in the hardware, so
the brackets inside b43_nphy_txpwr_index() find the bits already clear and emit
nothing.

The comment this replaces claimed the capture opens a bracket per pass and that
an open bracket is what lets the close reprogramme the table. The first half is
right and the second is not: the brackets are there, and they reprogramme
nothing.

Measured, on the warm init capture: the calibration region goes from 2573 paired
operations to 2644 of 2662, and its displaced operations - present in the driver
but in the wrong place - from 75 to 4. The gain sweep reaches 100%. Across the
whole window the displaced total falls from 153 to 76 and the contiguous blocks
rise from 21239 to 21316 of 23060. Nothing regresses; the absent count does not
move, which is the point: this changes when the driver does something, not
whether.

Nothing here ran on hardware.

Verified: records #13842-#13921, from
"PHY.MOD  addr=0x0298 val=0xf400 mask=0xff80"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0030

b43: program the transmit to receive sequence a second time on the BCM6362

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: program the transmit to receive sequence a second time on the BCM6362

The device programs the transmit to receive RF sequence twice during the PHY
init, with the same seven events and the same seven delays both times, and the
second pass comes after the auxiliary ADC tables at the end of the workarounds
and is preceded by eight masksets on the two AFE control registers.

In the capture the first pass is at records #390-#420 and the second at
#796-#874, with the masksets at #796-#803 and the auxiliary ADC writes above
them at #771-#789. Counting the table writes over the whole warm init window:
the device writes table 7 offset 0x10 twice, and offset 0x90, and each of the
nine single cells that pad the sequence; this driver writes each once. The values
are identical between the two passes and between the device and the driver, which
is why this shows up as missing operations rather than as wrong ones.

Neither this driver nor the reference has the second pass. The masksets did
already exist here but in the wrong pass, ahead of the first one, where the
capture has nothing of the sort.

This is the largest single hole that was left in the init. Measured on the warm
init capture, with the operations the harness cannot emit excluded: the init
region goes from 8217 paired operations to 8297 of 9696, and its absent ones -
present in the capture and nowhere in the driver - from 254 to 183. Over the
whole window the absent total falls from 332 to 261 and the contiguous blocks
rise from 21316 to 21396 of 23060. On the cold init capture the blocks rise from
21177 to 21257.

What remains of that stretch is a separate thing and starts at #877: a readback
sequence over 0x20 and 0x2a7, 0x21 and 0x2a8, 0x22 and 0x2a9, and the four
shared memory writes at 0x1570-0x1576 that name 0x8f, 0xa6, 0xa5 and 0xa7 to the
microcode. Fifty-one operations, and none of them is in this patch.

Nothing here ran on hardware.

Verified: records #796-#874, from
"PHY.MOD  addr=0x00a6 val=0x0004 mask=0x0004"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0031

b43: fill in the N-PHY spur workaround for the BCM6362

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: fill in the N-PHY spur workaround for the BCM6362

b43_nphy_spur_workaround() is a stub: it opens and closes the carrier search
bracket and does nothing in between. The device does something there, and it is
the first hole in the whole initialisation - records #203 to #234, immediately
after the write of 0x3830 to the duplicate 40 MHz data tone count, which is the
call site.

The reference emits nothing here for a 20 MHz channel on radio revision 8, and
that is why the stub was never noticed: the analogue receive filter adjustment
applies to PHY revisions below 7, the minimum noise variance list is empty
outside the 40 MHz channels 3 to 10, and the carrier sense minimum power path
only restores what an earlier adjustment saved. So the capture is the only
voice, and both captures agree.

What it does: the same value, 0x1591, into the two STR address 2 registers, then
a readback - one pair of cells from table 7 at offset 0x106, and then twice over
three cells of table 0 at 0x0b, 0x13 and 0x23 and the transmit/receive loss
register.

The read values are dropped. That is not a reason to leave the reads out: a read
of a PHY register is not free of side effects, and these sit between two writes
the device does keep.

Measured on the warm init capture: the init region goes from 8297 paired
operations to 8351 of 9696 and its absent ones from 183 to 129, so this closes
fifty-four - the twenty-seven of its own stretch and twenty-seven more further
on that were only unpaired because the alignment had drifted. Over the whole
window the absent total falls from 261 to 207, the contiguous blocks rise from
21396 to 21450 of 23060, and on the cold init capture from 21257 to 21299.

Nothing here ran on hardware.

Verified: records #203-#234, from
"PHY.WR   addr=0x01df val=0x1591"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0032

b43: read the gain control baseline back after the workarounds

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: read the gain control baseline back after the workarounds

Once the workarounds are in, the device reads its whole gain control and carrier
sense baseline back, between the second transmit to receive pass and the
baseband reset that follows. Records #877 to #987, and this driver emitted
nothing there at all: it went from #876 straight to #988.

Every register read is one that the gain control workarounds and the gain
control tables have just written - the four initial gain and clip thresholds on
each core, the narrowband clip thresholds, the two carrier sense minimum power
registers, the twelve energy detect carrier sense thresholds, two blocks of the
gain table, and the master and RSSI IDAC registers on both radio cores. Reading
back exactly what was just programmed is what a driver does before something is
allowed to change it, and the something here is the adjacent channel
interference scan, which the capture runs later and which this driver does not
have.

The values are dropped for now. That is not a reason to skip the reads: a read
of a PHY register is not free of side effects, and the sequence sits between two
things the device does keep.

What is deliberately not in this patch is the rest of that stretch: the shared
memory list at 0x1570 to 0x1576, which names 0x8f, 0xa6, 0xa5 and 0xa7 to the
microcode, and a bit in hostflag word 4. That bit has no name in this driver nor
in the reference, and setting an unnamed microcode flag on the strength of a
capture alone would be a guess about firmware behaviour.

Measured on the warm init capture: the init region goes from 8351 paired
operations to 8406 of 9696, which is 99% of the operations the harness can
compare, and its absent ones from 129 to 76. Over the whole window the absent
total falls from 207 to 154 and the contiguous blocks rise from 21450 to 21505
of 23060; on the cold init capture from 21299 to 21350.

Nothing here ran on hardware.

Verified: records #877-#987, from
"PHY.RD   addr=0x0020 val=0x007e"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0033

b43: read the four TSSI registers back before setting them up

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: read the four TSSI registers back before setting them up

b43_nphy_ipa_internal_tssi_setup() writes seven radio registers per core on
N-PHY revision 7 and up. The device reads four of them first, in this order -
the TSSI VCM, the transmit SSI mux, and the two TSSI band registers - once per
core: records #1251 to #1257 for core 0 and #1266 to #1272 for core 1, both
immediately ahead of the writes.

The values are dropped, which is not a reason to skip the reads: a read of a
radio register is not free of side effects.

Measured on the warm init capture: the init region goes from 8406 paired
operations to 8414 of 9696 and its absent ones from 76 to 68.

Nothing here ran on hardware.

Verified: records #1251-#1257, from
"RAD.RD   addr=0x0178 val=0x00000003"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0034

b43: leave the G band TSSI register alone on the BCM6362

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: leave the G band TSSI register alone on the BCM6362

In b43_nphy_ipa_internal_tssi_setup(), on the 2 GHz path, this driver writes 1
to the G band TSSI register of each core for any PHY revision but 7, and 0x31
for revision 7. That follows the reference exactly.

The device does neither. It reads that register - the read is in the patch
before this one - finds 2, and leaves it: records #1251 to #1281 for core 0
contain no write of 0x17b, and none of 0x19b for core 1. The value 2 is still
there later, when the transmit I/Q LO calibration sets 0x31 at #8537 and puts 2
back at #10743, so nothing in between changes it either.

So the capture is the only voice against the reference here, and what it says is
not an operation out of place but a wrong value left in the radio for the whole
initialisation. Gate the write out on the radio revision this was measured on.

With this the window that covers the function matches the capture exactly, 19
operations of 19, and the count of windows with declared divergences goes from
six to five.

Nothing here ran on hardware.

Verified: records #1259-#1281, from
"RAD.WR   addr=0x0175 val=0x0005"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0035

b43: turn the transmit power control on after the indices, not before

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: turn the transmit power control on after the indices, not before

On the path that turns the transmit power control on, this driver sets the
coefficient bit and the two enable bits in one write and only then puts the saved
power indices back. The device does the opposite: it clears the two enable bits,
puts the indices back, and sets all three bits afterwards.

Four operations, twice over in the warm init capture with the same values both
times - #4958 to #4961 and #6330 to #6333:

  clear 0xc000 of the command register, the hardware and software enables
  the index for core 0 into the low seven bits of the same register
  the index for core 1 into the low byte of the init register
  set 0xe000, the two enables and the coefficient bit

The order matters on its own terms and not only for the trace: as it was, the
control ran with the previous indices for the length of two register writes.

This patch does the two bit operations. The two index writes still do not
appear, because they are gated on both saved indices differing from 128 and
because the values this driver has there are not the ones the device writes -
0x19 against 0xa and 0xc - which is a separate question about what the index
save keeps.

Measured on the warm init capture: the absent operations fall from 138 to 135
and the contiguous blocks rise from 21522 to 21525 of 23060.

Nothing here ran on hardware.

Verified: records #4958-#4961, from
"PHY.MOD  addr=0x01e7 val=0x0000 mask=0xc000"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```

## 0036

b43: turn the low pass filter override off where the calibration turned it on

```
From: Alessio Ferri <alessio.ferri@mythread.it>
Date: Mon, 31 Aug 2026 00:00:00 +0000
Subject: [PATCH] b43: turn the low pass filter override off where the calibration turned it on

b43_nphy_tx_cal_phy_setup() turns the low pass filter bandwidth override on and
nothing turns it back off, so it stays on for the rest of the initialisation.

The counts say it plainly. Over the warm init window the device turns that
override on nine times and off nine times; this driver turned it on nine times
and off eight. The pair it lost is the long one, records #8629 to #10715: the
override goes on in the transmit I/Q LO calibration setup and comes off at the
end of the matching cleanup, twenty-one records after the sample playback stops
and after the rest of that cleanup has run.

b43_nphy_stop_playback() cannot be the one to do it, and adding a counter there
would be the wrong fix. That function reverts the override it owns - the one a
sample play sets - and a single bool is enough for that. This override belongs to
the calibration and outlives several plays: between the two records above the
capture has exactly one playback stop, at #10693, and the override survives it.

So turn it off at the end of b43_nphy_tx_cal_phy_cleanup(), where its owner
finishes.

Measured on the warm init capture: nine on and nine off on both sides now, the
init region goes from 8416 paired operations to 8420 of 9696 and its absent ones
from 66 to 62, and the contiguous blocks rise from 21525 to 21529 of 23060.

Nothing here ran on hardware.

Verified: records #10693-#10717, from
"PHY.AND  addr=0x00c3 val=0xfffb"

Signed-off-by: Alessio Ferri <alessio.ferri@mythread.it>
```
