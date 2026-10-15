# Inventory of the holes

Generated on `torvalds/linux` @ `848acc8ffe1b`, identical at `045958acaa75`, with
`reverse-tools/check_gaps.py --tree ~/src/pin --format md`; the table is the
tool's output, unchanged, checked again on that tree. The "rev citate" column
lists the values the function discriminates on; `assente` means the target
revision (radio 8 / phy 8) does not appear, `stub` that the body is empty. The
line numbers are the pinned tree's, not `b43/`'s.

The tool gives hints, not verdicts: below are only the entries that were then
read by hand. The balance, after reading them all: of six initial entries
**three were not holes** (`b43_radio_2057_rccal`, `b43_radio_2057_setup`,
`b43_radio_2057_rcal`) and one was paired with the wrong function. The reason is
systematic: the absence of a `case` in this driver usually mirrors the fact that
the vendor, for that revision, does nothing special. It stands as a warning on
how to read the table.

| file:riga | funzione | campo | rev citate | stato |
|---|---|---|---|---|
| `phy_n.c:145` | `b43_nphy_rf_ctl_override_rev19` | `radio_rev` | — | stub |
| `phy_n.c:719` | `b43_radio_2057_setup` | `radio_rev` | 0, 1, 2, 3, 4, 6, 9, 14 | assente |
| `phy_n.c:811` | `b43_radio_2057_rcal` | `radio_rev` | 0, 1, 2, 3, 4, 5, 6, 9, 14 | assente |
| `phy_n.c:925` | `b43_radio_2057_rccal` | `radio_rev` | 3, 4, 6 | assente |
| `phy_n.c:1734` | `b43_nphy_rssi_select_rev19` | `radio_rev` | — | stub |
| `phy_n.c:2476` | `b43_nphy_gain_ctl_workarounds_rev19` | `radio_rev` | — | stub |
| `phy_n.c:2481` | `b43_nphy_gain_ctl_workarounds_rev7` | `radio_rev` | — | stub |
| `phy_n.c:4720` | `b43_nphy_tx_cal_radio_setup_rev19` | `radio_rev` | — | stub |
| `phy_n.c:4725` | `b43_nphy_tx_cal_radio_setup_rev7` | `radio_rev` | — | assente |
| `phy_n.c:6333` | `b43_nphy_set_channel` | `radio_rev` | 6, <=4 | assente |
| `phy_n.c:153` | `b43_nphy_rf_ctl_override_rev7` | `rev` | <3, >=19 | assente |
| `phy_n.c:200` | `b43_nphy_rf_ctl_override_one_to_many` | `rev` | <7 | assente |
| `phy_n.c:1301` | `b43_radio_2056_rcal` | `rev` | — | assente |
| `phy_n.c:1740` | `b43_nphy_rev3_rssi_select` | `rev` | <7 | assente |
| `phy_n.c:2571` | `b43_nphy_gain_ctl_workarounds_rev1_2` | `rev` | 2 | assente |
| `phy_n.c:3347` | `b43_nphy_workarounds_rev1_2` | `rev` | 2, <2, <3 | assente |
| `phy_n.c:4588` | `b43_nphy_spur_workaround` | `rev` | <3 | assente |
| `phy_n.c:4919` | `b43_nphy_int_pa_set_tx_dig_filters` | `rev` | 16, 17 | assente |
| `phy_n.c:5592` | `b43_nphy_rev2_cal_rx_iq` | `rev` | <2 | assente |
| `phy_n.c:6538` | `b43_nphy_op_radio_write` | `rev` | <7 | assente |
| `tables_nphy.c:3825` | `b43_nphy_get_gain_ctl_workaround_ent` | `radio_rev` | 11 | assente |
| `tables_nphy.c:3740` | `b43_nphy_get_tx_gain_table` | `rev` | 3, 4, 5, 6, <3 | assente |

## The entries that matter for the 6362

### 1. `b43_nphy_gain_ctl_workarounds_rev7` — empty stub (phy_n.c:2481)

It is the big hole. It covers the RX gain control of **every** N-PHY rev 7+, so
rev 8 too: clip thresholds, LNA gain, crsmin, RSSI gain. Current body: a single
`/* TODO */` comment.

Reference: `wlc_phy_workarounds_nphy_gainctrl` (brcmsmac `phy_n.c:15425`), which
for radiorev 3 and 8 — the branch starts at `15593` — calls
`wlc_phy_workarounds_nphy_gainctrl_2057_rev6` (`15224`) and for rev 8 alone adds
`mod_phy_reg(0x283, 0xff, 0x44)` and `mod_phy_reg(0x280, 0xff, 0x44)`.

Expected impact: RX sensitivity and AGC behaviour. **SALAME**: that it is the
first bottleneck on 2x2 is a reading, to be measured
(see `docs/reports/30-rx-sensitivity.md`) before treating it as such.

Patch: `patches/b43/MESSAGES.md#0001`, written on the capture's values and not
on brcmsmac's, because the two diverge: LNA1 `8, 13, 18, 25` instead of
`9, 14, 19, 24`, W1 clip 24 instead of 13, and at 2.4 GHz the device also
programs LNA2, TIA and the gain bits, which brcmsmac's 2 GHz branch does not
touch. Details in `docs/trace-init-2g.md`. Limited to radio rev 8, 2.4 GHz,
20 MHz. Other revisions would need a capture from that hardware; 40 MHz needs a
device that turns it on, because the vendor driver does not use it at 2.4 GHz on
this board (31 chanspecs out of 31 are bw20). It builds in the harness from
`b43/`, **not tried on hardware**.

### 2. `b43_radio_2057_setup` — no `case 8`, but NOT a hole (phy_n.c:719)

Correction to the first draft of this document: the missing branch for radiorev
5/7/8 is a no-op on the 6362 at 2.4 GHz. The chain is this:

1. `b43_radio_2057_setup()` calls `b43_radio_2057_chantab_upload()` **before**
   the switch on `radio_rev`;
2. the upload writes `RFPLL_LOOPFILTER_R1`, `_C2`, `_C1` and `CP_KPD_IDAC` from
   the fields of the chantab entry;
3. in `b43_nphy_chantab_phy_rev8_radio_rev8` all 14 entries carry
   `r1=0x1b, c2=0x0a, c1=0x0a, cp_kpd=0x30`;
4. which are exactly the values brcmsmac writes in the override for radiorev
   5/7/8 at 2.4 GHz (`phy_n.c:20960`);
5. and they are the same ones the capture shows on silicon, `025=1b 027=0a 028=0a
   029=30` at every channel change (`docs/trace-init-2g.md`).

So the registers end up right by another road. It holds for radio rev 5 too
(`chantab_phy_rev8_radio_rev5`, the same four values on all 14 entries). The
override mechanism serves elsewhere: for radio rev 14 the chantab carries
`r1=0x2b, cp_kpd=0x30` and `case 14` changes them to `0x1b`/`0x3f`.

What remains is a real difference in the same function: b43 implements **only**
the `b43_nphy_ipa()` branch, while brcmsmac also has the `else` (non-IPA), which
for radiorev != 5 writes `pad2g_tune_pus = 0x3` and
`txmix2g_tune_boost_pu = 0x61`. Relevant only on boards with an external PA: the
DSL-3580L is not one of them, so for this project it is a note, not work.

### 3. `b43_radio_2057_rcal` — no `case 8`, and that is fine (phy_n.c:811)

Second correction: in `wlc_phy_radio205x_rcal` (brcmsmac `phy_n.c:19766`) the
radiorev-specific branches are only three — radiorev 5 (pre and post, `0x342` and
`IQTEST_SEL_PU`) and radiorev <= 4 or 6 (the tempsense/bandgap trim at the end).
For radiorev 8 the vendor runs **only** the common `RCAL_CONFIG` sequence, which
is exactly what b43 does by falling outside its `case 5/9/14`. Checked line by
line: nothing to add.

### 4. `b43_nphy_tx_cal_radio_setup_rev7` — not what it looked like (phy_n.c:4725)

The `phy->radio_rev != 5` in this function concerns the existence of the
`TSSIA` register, not a missing branch for rev 8. The three radiorev 8 sites of
`wlc_phy_a4` that the tool had paired with this function are elsewhere: they are
the choice of the PAPD pad-gain table, i.e. the question of
`rf-pwr-offset-rev8.md`. Entry closed, and replaced by that one.

### 4a bis. `b43_nphy_rev3_cal_rx_iq()` is a stub — the RX IQ cal does not exist

It is not in the table above, and the reason is a limit of the tool:
`check_gaps.py` looks at the functions that discriminate on `rev` or
`radio_rev`, and the body of this one is **`return -1;`** with no revision test,
so it does not see it. A second place to look is the functions called and never
written.

The whole body, in mainline:

    static int b43_nphy_rev3_cal_rx_iq(struct b43_wldev *dev,
                    struct nphy_txgains target, u8 type, bool debug)
    {
            return -1;
    }

It holds for **every N-PHY rev 3+**, not only rev 8. And the caller adds its
own: `b43_nphy_cal_rx_iq()` forces `type = 0` when `phy->rev >= 7`, so the
`type = 2` the vendor uses at init does not reach its destination anyway.

What is behind it, measured on the capture: **7510 ops**, #14093-22246, a third
of the init window. That it is the RX IQ cal shows in three countable things:
eight writes of the 160-word sample table (#15508, #16319, #17130, #17542,
#18588, #19399, #20210, #20624), two 84-cell clearings on tables 26 and 27 at
`off=0x40 len=84` for every tone, and seventeen read/write pairs on IQLOCAL one
cell at a time.

Those 84-cell writes **are not a gain upload**, as this entry used to say: they
are `wlc_phy_txpwrctrl_enable_nphy` turning the power control off inside
`wlc_phy_txpwr_index_nphy`, and b43 has that code in `b43_nphy_tx_power_ctrl()`.
See `docs/rxiq-cal-map.md`.

**CLOSED.** `patches/b43/MESSAGES.md#0018` brings the shell, the per-core power
index and the gain sweep, and `up-ch1` goes from 5791 to **11552 ops of 22951**;
`0019` adds the pre-calibration gain (**12363**), `0020` puts the index back
after the PAPD cal (**13134**), `0021` hands it back after reading the gains
(**13625**), and `0022`+`0023` close with the **measurement** — tone,
coefficients, and the function returning 0: **14351, 63%**.

The consequence is closed too: the cal succeeds, so `b43_nphy_save_cal()` is
called, and for the first time on this hardware a calibration is saved. Before
`0018` the stub returned -1, and in `b43_phy_initn` the `save_cal` sits behind
`if (b43_nphy_cal_rx_iq(...) == 0)`, so **no calibration was ever saved** —
either from the sequence of `0014` or from the `perical != 2` branch.

And the `type = 2 -> 0` downgrade this entry called a defect **was not one**:
removing it the port gets worse by 476 ops. The defect was upstream of it, in
the DAC test mode narrowed to `bool`
(`patches/mainline/b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag`); with that
fixed, type 2 and type 0 give the same ops and the downgrade can be removed at
no cost.

It cannot be ported in pieces like the tables: it is a loop driven by the reads,
like `a2`/`a3`. The map of the phase exists, made like the one of the PAPD cal:
`docs/rxiq-cal-map.md`.

### 4i. Three object memory regions the port does not touch

Measured on the two captures, with `OBJ.RD`/`OBJ.WR` (the `*_objmem16`
accessors):

| offset | in b43 | in brcmsmac | reads | writes seen |
|---|---|---|---|---|
| `0x1c0`-`0x1df` | `B43_SHM_SH_OFDMDIRECT` | **`M_RT_DIRMAP_A`** = `(0xe0 * 2)` | 192 / 176 | **0** |
| `0x300`-`0x31f` | `B43_SHM_SH_PWRIND_BLKS` (`0x308`) | power indication | 128 / 118 | 104 / 92 |
| `0x6c0`-`0x6df` | **no name** | — | 448 / 416 | **0** |

`M_RT_DIRMAP_A` is a map of **pointers**, not of values: the numbers read
(`0x384, 0x38f, 0x39a, ...`, stride 11) point at the per-rate entries, and
`M_RT_OFDM_PCTL1_POS = 18` is the offset of the power control word inside the
entry. brcmsmac uses it as `read_shm(entry_ptr + M_RT_OFDM_PCTL1_POS)` and the
corresponding `write_shm` (`main.c:1646` and `1653`). It is the per-rate power
path, and it lives in the **core**, not in the PHY.

**Zero writes prove nothing, and for two rounds the opposite was believed.** The
accessors hooked by `wl-diag` were `write_objmem16`/`read_objmem16`; object
memory is also written with `write_objmem` (single word with the space selector)
and in bulk with `copyto_objmem`, which internally calls `write_objmem` and
**not** the `*16` variant. So a bulk write did not show up. It is trap 1 in its
general form: *before saying something is not written, look at which accessor
the write goes through.* The exception here is declared **against the missing
hook**, not against the count.

The four hooks were added (`wlc_bmac_read_objmem`, `write_objmem`,
`copyto_objmem`, `copyfrom_objmem`, from the blob's symbols: 236, 160, 160, 156
bytes; the homonymous `wlapi_*` are 16-byte trampolines and are not hooked).

**And which ones exist depends on the build**, measured on three artefacts:

| symbol | `wl.ko` vd630 | D6220 blob (7.14) | 3580L blob (6.30) |
|---|---|---|---|
| `read_objmem` / `write_objmem` | **absent** | absent | present (236 / 160) |
| `read_objmem16` / `write_objmem16` | **absent** | present | absent |
| `copyto_objmem` | **568 B** | 160 | 160 |
| `copyfrom_objmem` | **612 B** | 156 | — |
| `wl_netdev_ops` / `wl_dslcpe_netdev_ops` | **no symbol** | 136 | 80 |

On the vd630 the single-word accessors are **inlined**, and the size says so:
`copyto_objmem` is 568 bytes there against 160 in the blob, i.e. it ate them. So
on that device **the only observable access to object memory is the bulk one**,
and a capture showing no single-word writes says nothing about that class. 43
hooks of 47 resolve; the 4 missing are exactly those.

The `netdev_ops` have no symbol at all in that build, so the base pointer cannot
be obtained by name: `wl_diag` (`3-4/`) now finds it with the
`__module_address` fallback, which uses no symbols.

A dead end, so as not to walk it again: `wlc_phy_txpower_update_shm` (748 bytes
in the blob, `phy_cmn.c:1615` in brcmsmac) looked like the producer of the
per-rate values, and it is not: its first line is `if (ISNPHY(pi)) return;`. On
the N-PHY it does nothing, and b43 rightly has no equivalent.

### 4j. The two caps of the power table, and where they come from

`patches/b43/MESSAGES.md#0025` applies two caps by number of chains — 68 qdBm
for one, 56 for two — and with them the 84 cells of the adjusted power table
come out **84 of 84** on the 3580L and **82 of 84** on the vd630, which have SROM
offsets differing by a factor of four. The 2 left are a **one-group shift** in
the one-chain column, not a wrong value, and it shows only on the vd630 because
the other has all nibbles equal.

**The 3 dB between the two caps is arithmetic, not measurement**: two chains
radiating together make twice the power of one, so each has to go down by
`10*log10(2)`. `68 - 56 = 12` qdBm is that factor to two decimals. It needs the
number of chains, not a table.

**The 68 on the other hand is regulatory data**, and it has to be said because it
changes where it should live: the vendor carries per-country tables,
`locales_2g_base` (5744 B) and `locales_2g_ht` (7782 B), and the bytes are limits
in qdBm — 76, 66, 60, 56, 48, 45 can be read. In the MIMO table **56 appears 252
times** and is among the dominant values; the legacy one is centred higher. So
the low cap comes from there.

And `maxpwr20[BRCMS_MAXPWR_MIMO_TBL_SIZE]` with `SIZE = 14` **is not per
modulation group**: brcmsmac's comment says «index by channel for 2.4 GHz
limits», so they are the 14 channels, not fourteen modulation groups.

What is missing to derive it instead of measuring it: Linux's EIRP (20 dBm) minus
this board's antenna gain (`ag0 = 2`) makes 72 qdBm, not 68. The 4 qdBm left are
not explained — and the `#if 0` block of `b43_nphy_op_recalc_txpower`, which would
subtract `hw_gain = 6 + antenna_gain`, would give 72 too.

### 4b. The rev 8 RF power offset table uses the rev 5 values — CLOSED

For radiorev 7 and 8 the vendor uses `nphy_papd_padgain_dlt_2g_2057rev7`, the
merged table uses the rev 5 values. **Decided by the capture**: recomputing the
128 PAPD cells that table feeds, the rev 7 values predict all of them, the
in-tree ones predict 5. Fix in `patches/b43/MESSAGES.md#0002`, details in
`docs/rf-pwr-offset-rev8.md`.

### 4c. The PAPD path is never run on rev 7+

`b43_nphy_tx_gain_table_upload()` fetches the offset table and then returns for
`phy->rev >= 7` with a `/* TODO: Enable this once we have gains configured */`,
so tables 26 and 27 at offset 576 (128 cells per core, the PAPD compensation)
stay unprogrammed. The loop that computes them is already there and in the
harness produces exactly the capture's 256 cells. `patches/b43/MESSAGES.md#0003`
enables it for radio 2057 rev 8 and leaves the other rev 7+ as they are. To be
sent after `0002`: with the wrong values it writes 246 cells of 256 different
from the vendor's.

### 5. `b43_radio_2057_rccal` — not a hole

The tool flags it because the "special" branch names only 3/4/6, but for rev 8
the right road is the other one: in brcmsmac's `wlc_phy_radio2057_rccal`
(`19874`) the `chip43226_6362A0` group is radiorev 3/4/6, and rev 8 goes on the
v7 branch with `MASTER 0x61/0x69/0x73`, `TRC0 0xe9/0xd5/0x99`, `X1 0x6e`. The
constants match those in b43: **checked, nothing to do**.

### 5b. The chantab did not write the 5 GHz fields the vendor clears — CLOSED

b43 has two forms of the rev 7+ channel table: the full one and a **2 GHz only**
one that leaves out ten fields to save space. Leaving out the fields it left out
their writes too, so a channel change on a board that uses the 2 GHz table leaves
`LOGEN_MX5G_TUNE`, `LOGEN_INDBUF5G_TUNE`, `PGA_BOOST_TUNE` and the
`TXMIX5G`/`PAD5G`/`LNA5G` of both cores at the previous channel's value.

Three independent sources say they have to be written, and with zero:

- the **capture**: each of the ten is written with value 0, at **all 31**
  channel changes, on five channels and two interface cycles;
- **brcmsmac**, which keeps a single table for the two bands: in
  `chan_info_nphyrev8_2057_rev8` every 2.4 GHz row has zero in those ten
  columns, so it writes ten zeros at every change;
- **b43 itself**, in the full-table branch, writes them in position.

And the position is not the obvious one: the ten are **interleaved** with the
2 GHz ones, not at the end — `0x43` right after `0x41`, `0x4a` after `0x47`, the
three of core 0 between `PAD2G` and `LNA2G`. It is the same order as b43's full
branch.

`patches/b43/MESSAGES.md#0011` writes them, gated on radio 2057 rev 8, the only
combination the capture covers. The other two boards that go through the 2 GHz
table (phy rev 8 with radio rev 5, phy rev 17 with radio rev 14) stay as they
are: brcmsmac has no 2.4 GHz rows for those radios, so there is nothing to
compare them against.

After the patch the `chanswitch-ch6` window has **no missing op**: the first 33
of 39 match positionally, and the rest are the same ops with the same values
three out of step, because the harness records three MMIO accesses the vendor
tracer does not. Before, 11 of 39 matched and ten ops were missing.

### 4d. The PAPD engine runs on uninitialised tables — CLOSED

`b43_phy_initn()` turns PAPD on for every device with an internal PA
(`PAPD_EN0` and `PAPD_EN1`), but does not touch the tables that engine reads:
the scalar one (32 and 34) and the epsilon ones (31 and 33). They stay with
whatever was there.

The capture shows the vendor writing the scalar table with 64 values per core —
the same brcmsmac has in `nphy_papd_scaltbl`, checked identical — and clearing
the 64 epsilons per core. `patches/b43/MESSAGES.md#0004` does the same for radio
2057 rev 8: in the harness the 256 cells coincide with the capture, zero
divergent.

It does not add the PAPD calibration, which is what would fill the epsilons with
real values: it gives the engine a defined state instead of whatever happens to
be there.

### 4e. The 2 GHz IPA bias registers are wrong on rev 8 — CLOSED

Found by the **reverse** list of `test/unit/coverage.py`, i.e. the registers the
port writes and the vendor does not. It was a single line, `r05f`.

The rev 7/8 branch of the IPA workarounds writes `0x5F` and `0xE8`, which are
`IPA2G_GAIN_CORE0` and `IPA2G_IMAIN_CORE1`: one register of each pair, on
different cores. The offset between the two cores of this radio is 0x85, so the
twin of `IPA2G_IMAIN_CORE1` is `IPA2G_IMAIN_CORE0` at `0x63`, not `0x5F`.

The capture, at the same point and in both inits, writes `0x63 = 0x14` and
`0xE8 = 0x14` — IMAIN on both cores, same value — and never touches `0x5F`. b43
instead leaves IMAIN_CORE0 at its value, writes core 0's gain register with a
value meant for the bias, and programs the two cores differently.

`patches/b43/MESSAGES.md#0005` gives rev 8 a `case` of its own and programs
IMAIN on both cores. Rev 7 keeps its `case` and its behaviour: it probably has
the same problem, but there is no hardware capture with that radio, nor of the
40 MHz branch. The two `case`s are separate on purpose, with 20 and 40 MHz split
inside each: whoever comes with a capture from a 2057 rev 7 touches their own
branch and does not have to carry ours. The price is duplicating the two 40 MHz
lines, and it is paid gladly.

### 4f. No noise floor measurement on N-PHY — CLOSED

`b43_calculate_link_quality()` and `handle_irq_noise()` return at once if the
PHY is not a G, so on N-PHY `dev->stats.link_noise` stays at its initial value
and mac80211 receives a constant as the noise floor.

The mechanism for N is in brcmsmac: the ucode leaves a complex power per core in
the power indication block in SHM (`M_PWRIND_BLKS = 0x308`), the driver clears
the four words, raises `MCMD_BG_NOISE`, and on the answer builds
`(hi << 16) | lo` per core, divides by 512, converts to dB and adds −103. The
noise reported is the maximum over the cores.

The capture reads exactly those four words, 96 times, and putting its values
through the conversion gives **−82, −86, −88 dBm** per core: plausible and
consistent between the two cores. `patches/b43/MESSAGES.md#0006` wires it in.

Mind the fence: it is not gated on the revision but on the PHY **type**, so it
touches every N-PHY. The argument for accepting it is that today those report a
number that was never measured. The other patch that leaves the fence is
`0010`, see 4g. `b43-ac-wip` reaches the same place with a PHY op,
`noise_sample_done`, which the N noise sample could use too
(`docs/ac-wip-xref.md`).

The rest of the places where b43 handles G and not N are in
`docs/phy-g-only.md`: twenty constructs, of which the two of the noise and four
in `xmit.c` on RSSI and RX decoding are real holes, the others legitimate.

### 4g. The sample table does not contain a tone — CLOSED

Found by the `sampleplay-*` windows of `test/unit/phase_compare.py`, comparing
the 160 words of table 17 op by op with the capture.

The SAMPLEPLAY table is the stimulus of every calibration that plays samples:
the TX IQ/LO cal, the idle TSSI measurement, the rev 2 RX IQ cal, and the PAPD
cal. Two typos in mainline make it unusable, and they go together because
neither shows without the other fixed.

**The phase step.** `b43_nphy_gen_load_samples()` (phy_n.c:1530) keeps `rot` and
`angle` in `u16` and computes `rot = (((freq * 36) / bw) << 16) / 100`, then
passes `CORDIC_FIXED(angle)`. The reference is `wlc_phy_gen_load_samples_nphy`
(`brcmsmac/phy/phy_n.c:23030`), where `rot` and `theta` are `s32` and
`rot = ((f_kHz * 36) / phy_bw) / 100`, i.e. integer degrees, because
`cordic_calc_iq()` scales its argument by itself. b43's `<< 16` is therefore one
too many, and on top of that makes the result an exact multiple of 65536 whenever
`(freq * 36) / bw` is a multiple of 100 — which holds for **every** frequency the
driver asks for: 2500 and 5000 from the TX IQ/LO cal (phy_n.c:5389), 4000 from
the idle TSSI (phy_n.c:3950) and from the rev 2 RX IQ cal (phy_n.c:5718). In the
`u16` the step becomes 0: the angle does not advance and the samples are all
equal. Instead of the tone there is a constant level.

**The packing.** `b43_nphy_load_samples()` (phy_n.c:1518) writes
`data[i] = (samples[i].i & 0x3FF << 10)`, and `<<` binds tighter than `&`: it
masks with `0x3FF << 10` instead of shifting the masked value. For the
amplitudes in use the in-phase component sits in the low ten bits and gets
cleared; on negative values the sign extension remains.

The capture gives the format without ambiguity — `((i & 0x3ff) << 10) | (q & 0x3ff)`,
as in `wlc_phy_loadsampletable_nphy` — and three tones to compare: amplitude 0 at
#1288 (idle TSSI), amplitude 250 at 2500 kHz at #8638 (TX IQ/LO cal, period 8
samples), amplitude 181 at 4000 kHz at #11838 (PAPD cal, period 5).

`patches/b43/MESSAGES.md#0010` fixes both, and is the mainline patch
`b43-fix-two-defects-in-the-n-phy-sample-table-logic`. On the #8638 tone, wrong
words of 160: 160 in mainline (all zero), 140 with only the mask fixed, 120 with
only the step fixed, **0** with the patch.

This one too leaves our radio's fence: it is gated on nothing, it touches every
N-PHY. The argument for accepting it is that today those calibrations run on a
stimulus that is not the signal they believe they are playing.

### 4h. The radio init wrote 412 registers where the blob flags 39 — CLOSED

In the radio init phase, up to the first `CHANSPEC` (#132), the vendor writes 43
radio registers and b43 wrote 412. The dump of the blob explains everything.

The record of `regs_2057_rev8` is **six bytes**, not four:

    { u16 address; u16 init; u8 do_init; u8 pad; }      /* 413 records, 2478 bytes */

and **39 records have `do_init` set**. The third `u16` is only `0x0000` (374
times) or `0x0100` (39), i.e. `do_init = 1, pad = 0` in big-endian.

b43's `r2057_rev8_init` inherited address and value — **412 values of 412
identical to the blob's `init` column**, a perfect transcription — and lost the
column that says *which* to write. brcmsmac keeps that field (`u8 do_init` in
`struct radio_20xx_regs`) and honours it (`phy_cmn.c:897`).

The capture matches the flag **exactly**: in the init phase the vendor writes all
39 flagged registers, with the flagged value, **zero exceptions**, and no other of
that table. The four extra radio registers it touches there — `0x11`, `0x2e`,
`0xce`, `0x164` — it writes with values this table does not contain, so they come
from other code.

And this also closes the question of the merged commit, which said it had not
found the origin of the 54-entry stub that **hangs the radio** with "Microcode
not responding": it is **brcmsmac**'s `do_init` set, which is not the blob's — 21
registers brcmsmac flags and the blob does not, 6 the blob flags and brcmsmac
does not. brcmsmac's flags are older than this radio, and that is why the stub
matched neither.

### Where the 373 entries without the flag end up

| | |
|---|---|
| never written in 70796 records, by anyone | **322** |
| written, sooner or later with the table's value | 15 |
| written, only with other values | 36 |

The 51 someone touches are **per channel**, and they are recognised by the
count: 31 writes each, which are the capture's 31 channel changes, the same ones
that write `R2057_LOGEN_MX2G_TUNE`. They are the chantab and PLL registers —
`VCOCAL_COUNTVAL0/1`, `RFPLL_REFMASTER_SPAREXTALSIZE`,
`RFPLL_LOOPFILTER_R1/C1/C2`, `CP_KPD_IDAC`, `RFPLL_MMD0/1`, `VCOBUF_TUNE`, the
`LOGEN_*_TUNE` — plus two that move more often, `RFPLL_MISC_CAL_RESETN` 70
times and `RFPLL_MISC_EN` 66, because the vcocal touches them too.

Which explains the flag and confirms the patch: those 51 are reprogrammed by the
channel change with the chantab's values, not the init table's, and the first
channel change comes right after (`CHANSPEC` #132). Writing them at init meant,
at best, throwing away 51 writes; at worst, keeping the PLL on wrong values until
the first channel change.

### The line across the 412

The four classes partition the table without overlapping:

| class | n | what they are |
|---|---|---|
| `init` | **39** | the blob's flag: written at radio init, they are what `0013` brings into b43 |
| `chan` | **51** | reprogrammed by the channel change or a cal, from the chantab and not from here — vcocal, RFPLL loopfilter, MMD, the `LOGEN_*_TUNE`; 31 writes each, one per channel change |
| `altrarev` | **42** | flagged in brcmsmac's `regs_2057_rev4`/`rev5`/`rev5v1`/`rev7` but not in rev8: **the table is a superset shared among revisions** and the flag selects |
| `ignota` | **280** | no revision flags them and nobody writes them, ever, in 70796 records |

So 132 of the 412 have an identified purpose, and 280 do not. The per-bank
distribution of the 280 is **to be recomputed**: the numbers that were here (190
SYN, 91 core0, 50 core1) add up to 331, not 280, and b43's `radio_2057.h` is not
enough to redo it — its `*_CORE0`/`*_CORE1` names do not partition the address
space into contiguous ranges, so the blob's bank map is needed.

And a detail that closes the circle on the stub: the **21** registers brcmsmac's
rev8 flags and the blob does not fall **all 21 in `altrarev`**. The stub wrote
another radio's init at the BCM6362's init, and that is why it hangs the chip
with "Microcode not responding". Zero of those 21 are per channel.

### The only asymmetry between the two cores, and why it is not a bug

`regs_2057_rev8` is symmetric between the cores: 112 consecutive registers,
`0x04f-0x0cc`, copied identically to `0x0d4-0x151` with offset `0x85`. Of 129
pairs carrying the same value, **only one** has an asymmetric flag:

    0x062  R2057_IPA2G_TUNEV_CASCV_PTAT_CORE0   val 0x33  do_init=1
    0x0e7  R2057_IPA2G_TUNEV_CASCV_PTAT_CORE1   val 0x33  do_init=0

wl writes core 0 and never core 1, in 70796 records. It is not a missed
copy-paste in the blob, and that can be checked.

The Netgear D6220's blob, `wl 7.14.89.14` — much more recent than 6.30.102.7 —
carries the same `regs_2057_rev8` symbol, and it is not "slightly different": it
is **identical**, 412 addresses of 412, 412 values of 412, 39 flags of 39, zero
differences. And it has fourteen `regs_2057_*` tables instead of five, so the
test can be done per revision:

| table | `0x062` | `0x0e7` |
|---|---|---|
| rev4, rev5, rev7, rev7v1, rev8, rev12 | `flag=1` | **`flag=0`** |
| rev5v1, rev9, rev11, rev13, rev14, rev14v1 | `flag=0` | `flag=0` |

The value is `0x33` in all twelve. **There is no revision, in either blob, that
flags `0x0e7`**: where core 0 is flagged core 1 never is, and where core 0 is not,
core 1 is not either. A typo does not survive fourteen tables and two
generations of blobs years apart.

**SALAME** on what justifies it: that the PTAT reference is shared between the
two cores, and so that `0x0e7` is a dead alias, is the only reading at hand, but
it cannot be falsified from the tables and has not been verified. What matters
here is that `patches/b43/MESSAGES.md#0013` does the right thing by not writing
it: no version of the proprietary driver writes it.

The whole table, with the `do_init` column and the class, is in
`router-data/blob-tables/regs_2057_rev8.txt`: `0013` brings only 39 into b43,
but the remaining 373 values are data extracted from the blob and some will be
needed — the 51 per-channel ones to compare the chantab, and the 322 if someone
works out what they are for.

The other **322 nobody programs, ever**: the blob carries the value and nothing
else uses it.

Why is not known, and the only plausible explanation does not hold: they are not
"the 5 GHz registers". The chip **has** the 5 GHz band — entry 6 of this same
document says so, and the blob has `nphy_tpc_txgain_ipa_5g_2057rev8` and 109
5 GHz channels in the chantab; it is this board that has no 5 GHz antennas wired
to the integrated wlan. And the numbers do not add up anyway: among the 322 never
written, 50 have `5G` in the name and 40 have `2G`, i.e. the same ratio as the
whole table (70 and 63). The only part explained is that 50 of the 70 registers
with `5G` in the name are not written in a capture that stays on 2.4 GHz. The
remaining **272 stay unexplained**.

`patches/b43/MESSAGES.md#0013` filters the table to the 39 entries. **No value
changes**: of the 39 that remain, all keep the address and value they had, and no
new one appears — 373 deleted, 0 added, 0 modified. The diff looks like a rewrite
only because the entries sit four per line, so removing 373 of 412 reflows every
line and `git diff` can only say "104 lines out, 11 in". The patch carries the
command to check it without reading the table.

Filtering instead of adding a third column is what the other six
`r2057_rev*_init` tables of this file **already are**: rev4 42 against the 42
brcmsmac flags, rev5 44 against 44, rev7 54 against 54. Only rev 8 had departed
from it.

The count of ops in common on the init **does not move**, 4434 before and after:
those 373 writes matched nothing anyway. The value of the patch is correctness,
not the metric.

**Not tried on hardware**, and getting this wrong hangs the radio at init, so it
wants a boot on a BCM6362 before going anywhere.

### 6. `dev_id 0x435f` and the 5 GHz band

It is not a dispatch hole but a claiming problem. In
`b43_wireless_core_attach()` (main.c:5410) the bands are first guessed from
`BCMA_IOST` — and our host driver synthesises `2G_PHY=1, 5G_PHY=0` — but right
after `b43_supported_bands()` (main.c:5313) **overrides** them starting from the
`dev_id`, and `0x435f` is in the dual-band list. The DSL-3580L's SPROM fixup sets
exactly `0x435f` (b43 needs it to recognise the chip), so b43 registers a 5 GHz
band too.

The silicon is not the issue: the blob has `nphy_tpc_5GHz_txgain_epa_2057rev8`,
`nphy_tpc_txgain_ipa_5g_2057rev8`, and `chan_info_nphyrev8_2057_rev8` contains
**109 5 GHz channels** (4920..5900 MHz) besides the 14 at 2.4 GHz — checked with
`reverse-tools/chantab_from_blob.py --list`. The PHY rev 8 / radio 2057 rev 8
combination is dual band for the vendor.

The point is that **b43 does not have** those tables:
`r2057_get_chantabent_rev7()` for `case 8` returns only the 14 2.4 GHz entries
(of the vendor's 123), so a 5 GHz channel ends in an error. To be decided, and to
be measured first: if `iw list` shows the 5 GHz band and a scan in it produces
errors, the upstream patch is to make the band depend on the IOST (or on a
dedicated case) instead of on the `dev_id` alone.

