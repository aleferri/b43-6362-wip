# Provenance of the data

## OEM blob

`wl 6.30.102.7.cpe4.12L07.0`, extracted from the stock firmware of the D-Link
DSL-3580L (`wlDSL-3580_EU.o`), an unstripped ELF32 MIPS big-endian relocatable.
The blob is **not in this repository**: it is proprietary D-Link/Broadcom
material. The tools take it as an argument, on a local copy.

These come from it, and can be checked with `reverse-tools/blob_tables.py`:

| b43 table | symbol in the blob | result |
|---|---|---|
| `r2057_rev8_init` (412 entries) | `regs_2057_rev8` (413 records, stride 6) | 412/412 identical |
| `b43_ntab_tx_gain_ipa_2057_rev8_2g` (128 u32) | `nphy_tpc_txgain_ipa_2g_2057rev8` | 128/128 identical |
| `b43_ntab_rf_pwr_offset_2057_rev8_2g` (32 s16) | `nphy_papd_padgain_dlt_2g_2057rev5` | 32/32 identical |
| `b43_nphy_chantab_phy_rev8_radio_rev8` (14 entries) | `chan_info_nphyrev8_2057_rev8` (123 records, stride 44) | 336/336 fields identical (`chantab_from_blob.py`) |

## GPL reference code

The in-tree `brcmsmac` (`drivers/net/wireless/broadcom/brcm80211/brcmsmac/phy/phy_n.c`)
is the legitimate reference for what the vendor programs on N-PHY rev 8 /
radio 2057 rev 8. `reverse-tools/brcmsmac_xref.py` produces the list of the
functions involved.

## What is looked at in the blob

Two things are taken from the blob, and they are limited: the symbols with
their sizes (to extract the static tables, which is what `blob_tables.py`
does), and the prologues and exits of the accessors to hook, as far as needed
to know whether the tracer's detour holds on that function — if there is a
branch in the first four words, the module corrupts it.

What ties the two together is **where the product goes**. Locating the
symbols and the call sites serves to build the measuring instrument: the
result is `wl-diag`, which observes the hardware, and without those sites the
hooks cannot be installed. Reading the body of a function to learn *what the
driver does* produces instead a statement about behaviour, and that statement
would end up in the port: that road is not taken, and for the same questions
one looks at `brcmsmac`, which is GPL and published by the same vendor.

This perimeter has been **crossed once**, and it is worth saying how: to
attribute a measurement cycle seen in a capture, function bodies were
disassembled, callers listed and a constant searched across all of `.text`.
The conclusions were right but the source was not, and they were redone on
`brcmsmac` — where they all were, one even better: `wlc_phy_aci_scan_nphy` is
in `phy/phy_int.h:1097` as a **prototype without a body**, which says more than
any disassembly that it is a policy above the PHY. The lesson: questions about
behaviour go to `brcmsmac` **first**, not afterwards.

## Data from b43-ac-wip

`router-data/dsl3580l/wl0_revinfo.txt`, `router-data/tg789vac-v2/` and
`router-data/d6220/` come from `aleferri/b43-ac-wip` at `01e1329`; each README
says from which file. Those are captures and dumps taken by the same author on
the same kind of setup, not third-party material.
