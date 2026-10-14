# reverse-tools

Tools for the N-PHY rev 8 / radio 2057 rev 8 support of the BCM6362. Three
families: analysis of the kernel tree, extraction from the OEM blob, decoding
and analysis of the `wl` driver's traces. The tracer itself is in
`../wl-diag/`. Each script's header says more.

## Analysis of the kernel tree

- **check_gaps.py** — for every b43 function that discriminates on
  `phy->radio_rev` or `phy->rev`, says whether the target revision is covered,
  treating `>=`/`<=` as coverage and flagging stubs (a body of comments only).
  Generates the table of `docs/gap-inventory.md`. It gives hints: an `assente`
  entry can be legitimate and has to be read by hand.
- **brcmsmac_xref.py** — lists the brcmsmac functions that discriminate on
  radiorev 8 or `NREV_IS(phy_rev, 8)`, with the line of the first match inside
  the function (not the line where the function starts). Generates
  `docs/brcmsmac-xref.md`.
- **cfuncs.py** — line→function lookup for kernel-style sources, used by the
  two above. Not a C parser: a brace-depth heuristic. **test_cfuncs.py** is its
  self-test, because the tools that rely on it fail silently when it
  attributes a line to the wrong function.
- **phy_type_audit.py** — lists the constructs where b43 discriminates on the
  PHY type and names G without N. Generates `docs/phy-g-only.md`. Textual
  heuristic: it sees whether the N case is there, not whether it is right.
- **check_patch_gating.py** — for every line a patch adds, looks for a revision
  gate that dominates it. Needed because nearly everything in b43's PHY is
  shared among all N-PHYs, and an ungated change alters hardware that cannot
  be tested. A heuristic, not a parser: a `NON GATEATA` has to be looked at.
  `docs/upstreaming.md` lists the shared functions and the gate each one
  wants. It tells a revision gate from a gate on the PHY **type**, which is
  legitimate but touches every rev of that type. It wants the tree at the
  patch's base: for the b43 series, `../scripts/series-diff.sh` writes it.
- **csanity.py** — minimal lexical check of a C file without a compiler: `*/`
  inside the prose of a comment, unterminated comments and literals,
  unbalanced brackets. The class of mistakes that hand-edited comments make and
  the compiler reports dozens of lines later.

## Extraction from the OEM blob

- **blob_tables.py** — dependency-free big-endian ELF32 reader. `--list` for the
  symbol lists, `--dump` for the hexdump, `--verify SYM --against FILE:ARRAY`
  to compare a kernel table with the blob's symbol, deducing the stride of the
  vendor record from matching the address column. It answers the question "is
  this merged table really the vendor's?": see `PROVENANCE.md` for the results.
- **chantab_from_blob.py** — the chantab is not a flat array but an array of
  structs: this tool maps the 44-byte records of
  `chan_info_nphyrev8_2057_rev8` onto the fields of
  `b43_nphy_chantabent_rev7`, compares the 2.4 GHz subset with the array in
  `radio_2057.c` (`--verify`), lists the coverage per band (`--list`) and emits C
  entries for the requested band (`--emit-c --band 5g`).

## Decoding pipeline

Order: decoding → fold RETVAL → fold MOD → (collapse) → comparison.

- **../wl-diag/decode-wl-diag.py** — binary records (28 B BE) → text lines.
- **verify_decode.py** — rebuilds the fields from the decoded text and compares
  them with the binary, record by record. It is the condition for throwing the
  binary away: if it says "nessuna perdita", the text replaces it; if it lists
  fields, the decoder needs fixing. It has found two holes so far: the space
  selector of `OBJ.RD`/`OBJ.WR` and the buffer pointer of `TPL.RAMW`, which the
  decoder's generic branch did not print.
- **merge_retvals.py** — folds the `RETVAL`s into the read that precedes them.
- **fold_mod_reads.py** — folds the implicit read of every `MOD`.
- **collapse_trace.py** — compacts the table ops (N-PHY ports 0x72/0x73/0x74).
  For the op-by-op comparison with the port use the **raw** trace, not the
  collapsed one.
- **gen_readplans.py** — pairs every read of the capture with its `RETVAL` and
  emits the harness's read plans as a C header, per address. Excludes
  0x72/0x73/0x74, which are the table port and not a status register.
  Measured: they do not move the coverage, see `test/unit/README.md`.
- **gen_seed.py** — the hardware state at the entry of the measured window,
  taken from the records that precede it (`test/unit/seed_up.h`): writes, mods
  and `RETVAL`s, register by register. Only what the window cannot know is
  seeded, never what it has to compute, or a register the port programs wrong
  would come back right by magic.
- **trace_tables.py** — reassociates every `TBL.WR` with the `PHY.WR`s on
  0x72/0x73/0x74 that implement it and prints the values, checking that header
  and data agree (address = `(id << 10) | off`, count = `len`). With
  `--c-array` it emits them as a C array. That is how the numbers of
  `patches/b43/MESSAGES.md#0001` were obtained. `--cell ID:OFF` gives the
  history of one table cell.
- **segment_marker.py** — cuts two traces on a marker, which may be a
  **sequence** of ops, and compares the segments one by one: how many, how long,
  made of which ops. It does not pair ops or compute percentages, that is
  `test/unit/phase_compare.py`'s job.
- **verify_chantab_trace.py** — for every `CHANSPEC` in the trace, compares the
  18 fields of b43's 2.4 GHz chantab with the radio writes that follow, value
  and order. It checks every channel the capture touches instead of one picked
  by hand, and lists separately the 5 GHz registers the vendor zeroes.
- **diff_traces.py** — differential between two captures, to isolate
  dependencies on board or channel.
- **mempeek.c** — 32-bit `/dev/mem` reader to inspect a backplane window from
  the device.

`test/unit/coverage.py` belongs to the same pipeline: coverage per class, and
with `--values` it compares the first value written to every register both
sides touch. It is the class of difference that presence alone does not see,
and it found the TSSI. It wants the port on the same channel as the capture,
or the chantab produces false positives.

The rest of the AC pipeline (function location, coverage, channel/BW
decorrelation, AC-PHY extractors) is in `b43-ac-wip` and is reused from there
unchanged: it was not duplicated here. `docs/ac-wip-xref.md` says which of
those tools apply to wl0.
