# D-Link DSL-3580L

BCM6362 with an integrated 2.4 GHz radio (N-PHY rev 8, radio 2057 rev 8) and a
BCM4352 PCIe card for 5 GHz. Only the integrated radio matters here; the
BCM4352 is `b43-ac-wip`'s board (`docs/ac-wip-xref.md`).

Reference OEM blob: `wl 6.30.102.7.cpe4.12L07.0` (`wlDSL-3580_EU.o`), not
included in the repository because it is proprietary.

## What goes in this directory

The tracer's binaries **are not committed**: the decoded text is the useful
form and the binary adds nothing, provided it is first checked that the text
loses no field (`reverse-tools/verify_decode.py`). The record of the capture
carries the size and the sha256 of the source binary, so the conversion stays
verifiable afterwards.

Captures come with their record. A `.raw` without one is not data, it is a file.

There are two decoded captures with their record next to them —
`opinit-ch1-ch6-bw20` (hot init, two cycles, no loss) and `full-init-ch1-bw20`,
described below — plus the device's `nvram.txt` and `srdump.txt`, and
`wl0_revinfo.txt`, the version block of `b43-ac-wip`'s `router_info.txt` at
`01e1329` (see `docs/ac-wip-xref.md`).

## `full-init-ch1-bw20.decoded`

**Cold** init on channel 1, 20 MHz, integrated radio, wl 6.30.102.7. 81397
records.

Taken by clearing `hw_up` with `setmem` and doing `wl up` again, so the PHY
initialises in full: it contains the **download of the static tables**, which
`opinit-*` does not have because it is a hot init. The marker is
`PHY.WR addr=0x0072 val=0x2800`, the opening of table 10, at #3569.

**It has a hole**: 65285 records lost in a single jump between `#32769` and
`#98055`, from a FIFO overflow — the reader was not draining during the burst,
and `#32769` is exactly `FIFO_RECS + 1`. Records **#2 to #32769 are
contiguous** and contain the whole init including the PAPD cal (scalar table at
#18662), so that part can be compared positionally. Beyond the hole there is a
second cycle, not contiguous with the first.

To take it again without the hole: the reading pipe has to be running **and
draining** before the `setmem`, not just started.

### How it was taken

The driver was **up** and then down: `hw_up` stays at 1 because the blob's down
path does not clear it, so a `wl up` from there only redoes a partial init.
Clearing it by hand, the next up goes through `hw_up()` ->
`wlc_phy_por_inform()` and the PHY reinitialises in full.

The order matters: the reading pipe has to **drain** before the burst starts,
or the FIFO (32768 records) overflows — which is how this capture got its
hole.

```sh
# 1. tracer armed. dmesg prints the instances' base pointers:
insmod wl_diag.ko arm=1
#    wl_diag: wl0: priv=82ac34e0 (netdev=82ac3180, ops=wl_dslcpe_netdev_ops)

# 2. from wl0's priv, walk to hw_up. The addresses belong to THAT
#    instance and change at every load of wl: redo the dumpmem every time.
dumpmem 0x82ac34e0 8      # priv -> wl_if            = 0x83af4e00
dumpmem 0x83af4e00 8      # wl_if + 0x04 -> radio    = 0x82a49000
dumpmem 0x82a49000 32     # radio + 0x04 -> pub      = 0x82a4bc80
dumpmem 0x82a4bc80 48     # pub + 0x2c = hw_up, must read 01

# 3. the pipe, and check that the file on the host GROWS before going on
cat /proc/wl_diag | nc <HOST> 5555 &

# 4. clear hw_up, and read it back
setmem 0x82a4bcac 0 1
dumpmem 0x82a4bcac 4      # the first byte must be 00

# 5. go
wl up
```

On the host: `wl-diag/decode-wl-diag.py < raw > capture.decoded`.

Keep **`wl1` down**: its hooks write into the same FIFO, the two sequences get
interleaved, and the positional comparison rests entirely on not having them
interleaved.

The proof that the init was cold is not the byte read back, it is
`PHY.WR addr=0x0072 val=0x2800` in the trace — the opening of table 10, with
which the static download starts. If it is not there, the init was partial
again.

The pointer chain was checked by reading the device's memory, not deduced from
brcmsmac: `wl_if+0x8` is the netdev and matches the log, `pub` and `wlc` point
at each other at offset 0, and `hw_up` at `pub+0x2c` read 01 with the interface
up and 00 after the `setmem`. The offsets deduced from the brcmsmac disassembly
were wrong.
