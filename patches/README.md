# patches

Every patch carries its **provenance in trailers**, with one `Link:` per URL,
one per line, which is the name the kernel tooling knows:

    Link: https://git.kernel.org/.../brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n23018
    Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/...decoded
    Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py

Kernel sources go to **git.kernel.org, pinned to the sha**: without `?id=` the
URL points at master, and the line number stops being that line at the first
commit that touches the file above it. A link into this repository is pinned
to a sha for the same reason, and because paths here move (`test/` is now
`test/unit/`, `router-data/dsl-3580l/` is now `router-data/dsl3580l/`).

The capture has its own `Link:`, but **the record range and the first op go in
the body**, not in an anchor: that file is 4.4 MB and 70796 lines, GitHub does
not render it and `#L8638-L8959` ends on a download prompt. The op is quoted
**with the file's spacing**, not normalised as the tools print it, or `grep -F`
does not find it.

`b43/MESSAGES.md#0006` has no citations, and stays without: it measures
something the vendor does not do in that capture.

`mainline/` holds **twelve separate patches**, not a series, for mainline
defects independent of this hardware: they go out first, in twelve separate
threads, see `mainline/README.md`, which is the source for the list.

The b43 series is not stored here as patches: the code is in `../b43/`, whole
files, and `../scripts/series-diff.sh` prints it as one diff over `mainline/`.
Its messages — rationale, measurements, record ranges, `Link:` trailers — are
in `b43/MESSAGES.md`, which is also where splitting it starts from. The
citations by number across the documents and in `test/unit/phase_compare.py`
resolve against that file.

That diff does not contain `0010` and `0022`, which were duplicates of two of
the mainline patches: no conflict to expect, nothing lost, see `b43/NOTES.md`.
The price is that `check_patch_gating.py` gives one verdict for the whole
series instead of one per patch, so the declared exceptions are collected in
`b43/NOTES.md` instead of one per message.

`0001`-`0003` are the bcma series, generated from `../bcma/` by
`../scripts/regen-patches.sh` on the tree in `regen-base`: edit `bcma/`, not
the patches, except for the message.

**The mainline patches are also part of the measurement baseline**: two of them
are worth 22 ops on the `up-ch1` window. That is why `b43/` contains them; see
`CLAUDE.md`, "Setup".
