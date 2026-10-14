# Reporting

The templates are in `docs/reports/`. Rules: a report is filled in with measured
numbers; cells that were not measured stay `—`, they are not filled with
estimates. A report with estimates passed off as measurements does more harm
than an empty one, because someone will build on it.

| report | when | acceptance criterion |
|---|---|---|
| `00-hw-inventory.md` | once per board | chip id, corerev, PHY rev, radio rev, SPROM rev read from `dmesg`/debugfs, not from a datasheet |
| `10-enumeration.md` | after every change to the bcma glue | every core enumerated with id and rev, IRQ assigned, no `synth aread32 unhandled` in the log |
| `20-init-coverage.md` | after every change to the PHY | percentage of the vendor flow's ops reproduced by the port, per function |
| `30-rx-sensitivity.md` | M0 and M1 gate | PER vs input level per rate, per chain |
| `40-tx-power.md` | M0 and M4 gate | measured power vs target per rate, per chain, with and without TPC |
| `50-throughput-ht20.md` | M4 gate | throughput and retries for MCS 0-15, HT20 |
| `60-regression-legacy.md` | every series before submission | legacy 2.4 GHz not worse: association, throughput, PER on every channel |

## What goes in the bring-up log

Raw logs go at the top of the repository, one per session, named

    bringup-log-<date>-<board>-<what>.txt

and start with four header lines:

    kernel:  <version>
    tree:    <sha of this repository>
    patch:   <series applied>
    expect:  <what was supposed to happen>

Then the log. At the end, one line on what actually happened if it diverges. A
`dmesg` without the commit it refers to cannot be reproduced.
