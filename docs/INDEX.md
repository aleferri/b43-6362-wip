# Documentation index

| file | contents |
|---|---|
| `../CLAUDE.md` | the minimum to avoid repeating mistakes already made: setup, state, rules, traps |
| `init-flow.md` | the two init flows side by side, phase by phase, and why b43 does not reach the PAPD cal |
| `upstream-status.md` | what is already merged, with shas and dates checked |
| `soc-glue.md` | bcma enumeration on the BCM6362: register map, bring-up, DT, SPROM |
| `gap-inventory.md` | holes in the driver, with file:line and the brcmsmac reference |
| `todo-nphy.md` | the holes still open, one per entry, with what it takes to close them |
| `brcmsmac-xref.md` | which brcmsmac functions to look at for each hole |
| `ht20-mimo-plan.md` | the plan for HT20 2x2, in milestones with exit criteria |
| `upstreaming.md` | what can be proposed as it is and what cannot |
| `../patches/b43/SERIES.md` | how to split the thirty-six of the series: eight series by area, and the points of conflict |
| `../patches/b43/SPLIT.md` | why the series stays unsplit, the one-commit-one-patch rule, and what it has already cost |
| `../patches/b43/NOTES.md` | what the series leaves out, the ungated points, and the rationale not yet in `MESSAGES.md` |
| `firmware-rev22.md` | ucode/initvals rev22: what is needed and what is to be checked |
| `blob-inventory.md` | inventory of the N-PHY/2057 symbols in the OEM blob |
| `trace-init-2g.md` | the DSL-3580L capture: what it confirms, what it corrects, what it finds |
| `rxiq-cal-map.md` | the RX IQ cal in the capture: boundaries, iterations, brcmsmac functions |
| `papd-cal-map.md` | the PAPD cal in the capture: phases, record ranges, brcmsmac functions |
| `rf-pwr-offset-rev8.md` | the rev 8 RF power offset table: why the in-tree values are wrong |
| `phy-g-only.md` | the places where b43 has a branch for G and not for N |
| `ac-wip-xref.md` | what b43-ac-wip holds for the N core: data, common base, where the code meets, tools |
| `capture-protocol.md` | how to take a useful trace, and what makes it useless |
| `reporting.md` | the set of reports and their acceptance criteria |
