# router-data/d6220 — Netgear D6220, wl0 attach

`b43-ac-wip` traces the D6220's BCM4352 (`wl1`) with module reloads, and each
cold segment begins with the attach of `wl0`, the SoC's N-PHY core, under `wl`
**7.14.89.14**. `wl0-attach-cold01.txt` is that part of `cold01-ch36-bw20.txt`
(`router-data/d6220/cold-sweep.zip` in `aleferri/b43-ac-wip` at `01e1329`),
lines copied unchanged: what `reverse-tools/strip_other_core.py` of that
repository removes, the attach `[#29, #98)` and the detach after `#38431`.

Which chip `wl0` is on this board is not recorded in either repository.

The DSL-3580L captures here have no attach at all: they start from `wl up` on a
loaded module (no `OTP.*`, no shared-memory self-test). This is the only module
attach of an N core under `wl` in either repository.

## What it holds

- the OTP read and the ChipCommon read at `0x88`;
- the shared-memory self-test: read `0x0000`/`0x0002` (`0x03a0`, `0x2715`),
  write `0x55aa`/`0xaa55`, read back, swap, read back, restore;
- two blocks of AFE overrides on the N-PHY registers `0x0a6`, `0x08f`, `0x0a7`,
  `0x0a5` (first `0x000d`/`0x0000`, then `0x00fd`/`0x07ff`) with `0x078` bit 10
  cleared before each;
- the host flags (`MAC.MHF`) cleared and set;
- at rmmod, GPIO out/enable and `gpiotimeroutmask` (`0x8c`) set to zero.

## Across the 43 segments

With the return values folded (`reverse-tools/merge_retvals.py`; 21 segments
come folded, 20 do not) and timestamps, op numbers, CPU and `for=#` references
dropped, the 44 attach operations are identical in all 43 segments.
`cold42-ch132-bw80` and `cold43-ch149-bw80` lack the five detach operations:
the capture ends before the rmmod.
