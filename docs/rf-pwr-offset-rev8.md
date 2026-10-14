# The RF power offset table for radio 2057 rev 8

**Closed by the capture: the values in mainline are wrong.** Recomputing from
the capture the 128 cells that table feeds, the rev 7 values predict all 128,
the in-tree ones predict 5. The fix is `patches/b43/MESSAGES.md#0002`, and
`#0003` enables the path that writes them.

The history stays below, because the way it was closed teaches more than the
result: not with a power measurement in a lab, but by recomputing from the
driver's code the cells the capture shows written.

## What the kernel says today

`b43_ntab_rf_pwr_offset_2057_rev8_2g` (commit `21352612198c`) contains the
values the proprietary driver uses for radio rev **5**:

    -109, -109, -82, -68, -58, -50, -44, -39, ...

The commit states it and gives the reason: the rev 8 IPA gain table shares the
low 24 bits with the rev 5 one, and `pad_gain` is extracted from bits 19..23,
which are in that shared part.

## What the vendor says

`get_rf_pwr_offset()` in brcmsmac (`phy_n.c:14649`) — the exact counterpart of
the b43 code that consumes this table — pairs radiorev 7 and 8 with the **rev 7**
table, and uses rev 5 only for radiorev 5. Same choice at the second place of
use, `wlc_phy_a4` (`phy_n.c:25275`). The rev 7 values are:

    -122, -122, -95, -80, -69, -61, -54, -49, ...

Checked that brcmsmac's `nphy_papd_padgain_dlt_2g_2057rev7` and the one in the
`wl 6.30.102.7` blob are identical, so the source for a patch can be in tree
and GPL, without bringing in the blob.

## What the data in the blob say

Checked with `reverse-tools/blob_tables.py`:

| comparison | result |
|---|---|
| `txgain_ipa_2g_2057rev8` vs `rev5`, low 24 bits | **identical** on all 128 entries |
| the same two tables, full entries | all different: only the high byte changes (0x40 against 0x30) |
| `txgain_ipa_2g_2057rev8` vs `rev7`, low 24 bits | **different** |

So the premise of the merged commit is true, and the symmetry with rev 7 is not
there.

## Where things stand

On the "IPA gain table" axis rev 8 resembles rev 5. On the dispatch of the
power offsets, the vendor pairs rev 8 with rev 7. The two do not contradict
each other in themselves: the offset in dB per index is a property of the
PA/pad, not of the gain step, and the vendor evidently considers the rev 8 pad
similar to the rev 7 one while using different selection codes.

The vendor's choice weighs more, because it is the code that runs on this
silicon. But it is an argument, not a measurement.

## How it was closed

The consumer of the table is `b43_nphy_tx_gain_table_upload()`: for every entry
of the TX gain table it extracts `pad_gain = (table[i] >> 19) & 0x1f` and writes
`rf_pwr_offset_table[pad_gain]` into the corresponding PAPD cell, tables 26 and
27 at offset 576+i. In mainline that path returns before the loop, but the
computation is all there.

The capture shows the vendor writing all 256 of those cells during the init, at
32 bits, with negatives sign-extended. Redoing the computation with the TX gain
table (checked identical to the blob) and the two candidates:

| offset table | cells predicted correctly |
|---|---|
| values in mainline, taken from rev 5 | **5 of 128** |
| rev 7 values | **128 of 128** |

No lab was needed: it was enough that the driver said how it is computed and
the capture said what comes out. The argument of the similarity between the
gain tables (the low 24 bits identical between rev 8 and rev 5) stays true and
stays irrelevant: the similarity is in the index, not in the offset in dB that
index selects.

Also checked the other way round with the harness: enabling the path without
correcting the values, 246 cells of 256 come out different from the capture;
with the correction, zero.
