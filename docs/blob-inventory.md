# Inventory of the OEM blob

`wl 6.30.102.7.cpe4.12L07.0` of the D-Link DSL-3580L, an unstripped ELF32 MIPS
big-endian relocatable (4.3 MB, ~9200 symbols). The blob is not in the
repository.

It serves three purposes: checking the merged tables, knowing which accessors
to hook with the tracer, and seeing what exists for the PHY r8 / radio 2057 r8
combination that b43 does not have.

## Accessors relevant to the N-PHY

Checked with `mips-linux-gnu-objdump -d`. The "prologue" column says whether the
first 4 words are free of branches, i.e. whether the tracer's classic detour
applies.

| symbol | prologue | notes |
|---|---|---|
| `phy_reg_read` | clean | `beqz` at the 6th word, outside the window |
| `phy_reg_write` / `_mod` / `_and` / `_or` | clean | addr=a1 masked to 16 bits |
| `phy_reg_write_array` | clean | wrapper: calls the accessors above |
| `read_radio_reg` | **beq at the 3rd word** | needs the shortj variant |
| `write_radio_reg` / `mod_radio_reg` | clean | |
| `and_radio_reg` / `or_radio_reg` | clean | not hooked by the AC tracer |
| `wlc_phy_table_{read,write}_nphy` | clean | wrapper on registers 0x72/0x73/0x74 |
| `si_pmu_spuravoid` | clean | position of the argument not verified |

Two things the trace clarified, which avoided useless code:

- `phy_reg_write_array(pi, tbl, n)` performs its ops **through the accessors
  already hooked**: after every `PHY.ARRW` marker the trace shows the
  corresponding `PHY.MOD`/`PHY.WR`. There was no coverage hole to fill with an
  in-kernel interpreter, only something to label. And `n` is the number of
  words, not of records.
- the table ops go through registers 0x72 (address, `(id << 10) | off`), 0x73
  and 0x74 (data), the same ones `b43_ntab_write*` uses: in the trace every
  `TBL.WR` is followed by those `PHY.WR`s. The `TBL.*` records are therefore
  labels, and the comparison with the port has to use the `PHY.WR`s. Checked on
  14 table ops out of 14 with `trace_tables.py`.

## Data for PHY r8 / radio 2057 r8

| symbol | size | contents |
|---|---|---|
| `regs_2057_rev8` | 2478 (413 × 6) | radio init table, checked against `r2057_rev8_init` |
| `nphy_tpc_txgain_ipa_2g_2057rev8` | 512 (128 × u32) | checked against `b43_ntab_tx_gain_ipa_2057_rev8_2g` |
| `nphy_tpc_txgain_ipa_5g_2057rev8` | 512 | 5 GHz, not in b43 |
| `nphy_tpc_5GHz_txgain_epa_2057rev8` | 512 | 5 GHz external PA, not in b43 |
| `chan_info_nphyrev8_2057_rev8` | 5412 (123 × 44) | 14 records at 2.4 GHz + 109 at 5 GHz; checked against `b43_nphy_chantab_phy_rev8_radio_rev8` |
| `nphy_papd_padgain_dlt_2g_2057rev5` | 64 (32 × s16) | reused by b43 for rev 8 |
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev6` | — | the body the b43 stub lacks |

Note: there is no `nphy_papd_padgain_dlt_2g_2057rev8`, which is consistent with
the merged patch's choice of reusing the rev 5 values (`rf-pwr-offset-rev8.md`
says why those values are nonetheless wrong).

## Layout of the chan_info record

Reconstructed and checked (`reverse-tools/chantab_from_blob.py`), 44 bytes:

    u16 chan          channel number
    u16 freq          MHz
    u8  radio[28]     same fields and same order as
                      struct b43_nphy_chantabent_rev7
    u16 phy_regs[6]   struct b43_phy_n_sfo_cfg

The 44 bytes and the position of `freq` come from the blob (the known
frequencies at a stride of 44, offset +2); the order of the 28 radio fields was
a hypothesis, and the comparison confirms it: **336 fields over 14 channels**
(the 18 radio fields of the 2g subset + 6 PHY registers per channel) identical
between the blob and b43's array. A wrong order would not have produced a full
match.

Practical consequence: the 109 5 GHz records can be extracted as a C array with
`--emit-c --band 5g`, should they ever be needed. This project does not need
them, and they are not to be sent upstream without hardware to test them.

## A second blob: `wlD6220.o_save`, wl 7.14.89.14

Netgear D6220, 5.4 MB, much more recent than the DSL-3580L's 6.30.102.7. It
serves as an independent check, and the first thing it gave was a refutation:
`regs_2057_rev8` is **identical** between the two blobs, 412 addresses, 412
values and 39 flags without a single difference (see `gap-inventory.md` 4h).

What it adds, on the symbols of interest (679 against 738 for the
`nphy|2057` filter, 101 more in 7.14):

- **fourteen** `regs_2057_*` tables instead of five: `rev7v1`, `rev7v2`,
  `rev10`, `rev11`, `rev12`, `rev13`, `rev14v1` more;
- `chan_info` for 2057 `rev12`, `rev13`, `rev14`, `rev14v1`, and for radio
  **20671** on phy rev 19, which is a generation further;
- the bphy/ofdm desense LUTs `rev3to6` and `rev7to15`.

6.30 on the other hand has the whole **sslpnphy** family and radio 2063, which
7.14 dropped: if they are ever needed, they are only in the old one.

Neither goes in the repository. The extracted tables are in
`router-data/blob-tables/`.

### Function sizes between the two blobs

Of the 578 symbols in common under the `nphy|2057` filter, 358 have the same
size and 220 do not. But the generic ones grow necessarily — 7.14 supports
radios that did not exist in 6.30 — so the question has to be asked about the
**per-revision** symbols, and there the answer is clear.

**All 33 symbols specific to 2057 rev5-8 have identical sizes** in the two
blobs: `regs_2057_rev5/rev7/rev8`, all the `chan_info_nphyrev*_2057_rev*`, the
`nphy_tpc_txgain_*`, the `nphy_papd_padgain_dlt_*`, the `pad_gain_codes_used_*`.
The data on our road has not moved by one byte.

Except three, and all three are code of the same family:

| symbol | 6.30 | 7.14 | |
|---|---|---|---|
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev5` | 572 | 1340 | +768 |
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev6` | 1692 | 1780 | **+88** |
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev7` | 1096 | 1252 | +156 |

`rev6` is **the body the b43 stub lacks** (entry 1 of `docs/gap-inventory.md`,
`b43_nphy_gain_ctl_workarounds_rev7` empty). So when it comes to rebuilding it
**which blob one reads matters**: 88 bytes of difference, about twenty MIPS
instructions, and the capture we have is of 6.30. For that work the old blob is
the reference, not the new one.

### The real names of `a2`, `a3`, `a4`

brcmsmac's GPL release has obfuscated names for the PAPD cal. The blob does not:

| brcmsmac | blob | size 6.30 | C lines in brcmsmac |
|---|---|---|---|
| `wlc_phy_a4` | `wlc_phy_papd_cal_nphy` | 6088 | 276 |
| `wlc_phy_a3_nphy` | `wlc_phy_papd_cal_gctrl_nphy` | 2444 | 147 |
| `wlc_phy_papd_cal_cleanup_nphy` | same name | 2124 | 124 |
| `wlc_phy_txpwr_papd_cal_nphy` | same name | 1028 | 13 |

`gctrl` confirms from outside what had been deduced reading the code: `a3` is
the gain index search, and its size is in the right ratio to its 147 lines.

**`a4` on the other hand is not identified.** `a2` has 279 lines and `a4` 276:
the size does not tell them apart, and the 6088 bytes of `wlc_phy_papd_cal_nphy`
fit both equally, so the name is the only clue and it is not enough.

Looking for `a2` by size — 279 lines, and the ratio measured on `a3` and on the
cleanup is 16.6-17.1 bytes per line, so 4600-6200 — among all the `wlc_phy*` of
the blob in that range **there is no candidate**: they are `tbl_init_nphy`,
`chanspec_radio2057_setup`, `papd_cal_nphy` and other PHYs' stuff. So one of the
two, `a2` or `a4`, is under a name that does not contain `papd`, and which of the
two is `wlc_phy_papd_cal_nphy` stays open.

One thing that came out of the search, and that holds for the method: the 6.30
blob has **zero** symbols with `.isra`/`.constprop`/`.part`, 7.14 has **159**.
The two are compiled differently and the old one does not expose the clones gcc
makes of static functions. It does not explain the absence of `a2` — `a3` and
`a4` are static too in brcmsmac and they are in the blob — but it explains why
names like `wlc_lcn40phy_papd_cal.isra.33.constprop.35` show up in 7.14 and not
in 6.30.
