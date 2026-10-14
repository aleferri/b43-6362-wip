# Capture protocol

A capture serves two purposes: knowing what the vendor writes, and being able
to compare the port op by op with that sequence. If a capture does not allow the
positional comparison, it is nearly useless.

## Before pressing insmod

1. `arm=0` (default): the module only logs the patch plan. Read it. If a symbol
   was not resolved, resolve it now, not later. The expected names are those in
   `docs/blob-inventory.md`: if `and_radio_reg` or `or_radio_reg` is missing,
   that blob uses different names and the tracer has a silent hole.
2. `insmod wl_diag.ko arm=1` is enough: the module looks the symbols up in
   `/proc/kallsyms` by itself. `syms=` and `klookup=` (`2-6-30/`) stay as a
   fallback if a blob uses names the list does not expect.
3. The capture is read from **`/proc/wl_diag`**, which exists as soon as the
   module is loaded: `cat /proc/wl_diag | nc <host> 5555`. The pipe has to
   **drain** before the sequence is started, not just be launched: the FIFO
   holds 32768 records and a cold init emits more than twice that.
4. Write down the blob version, board, channel, band, and whether the radio is
   the integrated one (`0x14e4:0x435f` on the backplane) or a PCIe card.

## What to capture, in which order

One sequence at a time, with the device stopped between one and the next:

| flow | how to get it | what it is for |
|---|---|---|
| `attach` | reload of `wl` | radio init + initvals |
| `op_init` | `wl up` from down | complete PHY init sequence |
| `switch_channel` | `wl channel N` on all channels 1-13 | chantab, spuravoid, loopfilter |
| `rfkill` | `wl radio on/off` | power up/down paths |
| `cal` | `wl phy_forcecal 1` | rcal/rccal, tx iq/lo, papd |

For the integrated 6362 **there is no PCI rescan**: the attach cycle comes back
by reloading the module or with `wl down; wl up`. No `attach` capture of this
core exists here yet; `router-data/d6220/` has one of an N core under `wl` 7.14.

## What makes a capture useless

- lost records (`OP_DROP` > 0): the FIFO overflowed, the sequence has holes and
  the positional comparison breaks. Reduce the flow captured, do not raise the
  filter.
- several flows in the same file without markers: they can no longer be told
  apart afterwards with certainty.
- a `skipphyrd` filter on without writing it in the record: one ends up looking
  for half an hour for a `PHY.RD` that was dropped upstream.
- captures on a channel other than the one declared: half the differences
  become unexplainable.

## After the capture

```sh
wl-diag/decode-wl-diag.py < raw.bin > flow.decoded
reverse-tools/verify_decode.py raw.bin flow.decoded    # before throwing the binary away
reverse-tools/merge_retvals.py flow.decoded > flow.rv
reverse-tools/fold_mod_reads.py flow.rv > flow.folded
```

What goes in the repository is the **decoded** text, not the binary: it is
readable, diffable and greppable, and it is the form the tools consume. The
binary is thrown away only after `verify_decode.py` says the text covers every
non-zero field; if it reports losses, the decoder is fixed and the decoding
redone, the binary is not kept as an excuse.

Then the checks that cost nothing and find things: `verify_chantab_trace.py` to
compare b43's chantab with every channel change of the capture, and
`trace_tables.py` to pull out the payloads of the table ops.

The comparison with the port is done on the **raw** trace (not collapsed), with
`test/unit/compare.py`. The collapsed one serves macro analyses, not the
regression gate.

Every capture goes in `router-data/<board>/` with its record next to it:
without the record, in three months the file is a blob of bytes.

## `wl down; wl up` is NOT enough for the static download

The blob's down path **does not clear `hw_up` in `pub`**, so that cycle only
redoes a partial init. For the init with the static download, a **writemem**
that clears that flag is needed between the down and the up: the next up goes
through `hw_up()` -> `wlc_phy_por_inform()` and the PHY reinitialises in full,
static tables and rcal/rccal included.

Measured on a vd630 capture taken with just `down`/`up`: **zero occurrences** of
`PHY.WR addr=0x72 val=0x2800`, the opening of table 10. The file was called
`fullinit.txt` and did not contain the static download — the name is not the
criterion, the grep is.

Reaching the flag needs the base pointer of the private data, which `wl_diag`
prints in dmesg. If the `netdev_ops` do not resolve by name, `3-4/` has a
fallback that uses no symbols: it recognises the interface because its
`netdev_ops` fall **inside the wl module** (`__module_address`). The offsets to
walk from `priv` to `pub` are per version: those noted in `wl_diag.c` are the
6.30 blob's and do not hold on 7.14.

### The poke on command

`poke=` as a parameter fires at `insmod`, that is before the `wl down`: for this
sequence it is no use. Use the write handler on `/proc/wl_diag` instead, which
only `3-4/` has (on the DSL-3580L, `2-6-30/`, the board's own `dumpmem`/`setmem`
do the same job, see `router-data/dsl3580l/README.md`):

```sh
insmod wl_diag.ko arm=1              # priv= in dmesg
cat /proc/wl_diag | nc host 5555 &   # drain FIRST
wl down
echo 'r   <priv> 64'  > /proc/wl_diag   # to find pub, dump in dmesg
echo 'w8  <addr> 0'   > /proc/wl_diag   # clear hw_up
wl up
```

Widths: `w8`, `w16`, `w32`, plus `r <addr> <n>`, which dumps into dmesg. On MIPS
a `w32` on an unaligned address takes an address error, so the handler refuses
it. The result goes to **dmesg** and not into the FIFO, which stays the capture.

And the write has to be done from inside the kernel and not with a userspace
writemem through `/dev/mem`: a module's addresses are in **vmalloc** space
(`0xc1...`, `0xc2...` in the logs), which cannot be reached with KSEG0's fixed
offset — the page tables would have to be walked.
