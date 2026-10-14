# wl-diag — inline-detour tracer for the `wl` driver

A kernel module that hooks the PHY/radio/PMU/MAC accessors of Broadcom's `wl`
driver with no kprobes (a detour at function entry) and exposes the records.
The header of `wl_diag.c` has the details of the mechanism and its limits
(MIPS32R1, RWX module memory, reads with an UNDEFINED value).
`decode-wl-diag.py` turns the 28-byte records into text.

| variant | kernel | board | how the capture is read |
|---|---|---|---|
| `2-6-30/` | 2.6.30 | DSL-3580L, runs on the SoC itself: **the one for the integrated 6362 radio** | `/proc/wl_diag` |
| `3-4/` | >= 2.6.33 (3.4-rt) | a host with kernel 3.4 | misc device `/dev/wl_diag` |

`2-6-30/` uses a hand-made ring queue, `pr_warn` through a shim and no
`raw_spinlock`; `3-4/` wants a typed kfifo and `DEFINE_RAW_SPINLOCK`, and on an
older kernel stops with an `#error` that says so. On 2.6.30
`kallsyms_lookup_name` exists but is not exported to modules (the export comes
in 2.6.33): `2-6-30/` takes its address with `klookup=` and finds the other
symbols by itself, or an explicit list with `syms=` (`2-6-30/Makefile`).

The two variants are **not the same source** any more: the seven `wlc_bmac_*`
hooks below (`read_shm`, `write_shm`, `set_shm`, `core_phy_clk`,
`switch_macfreq`, `suspend_mac_and_wait`, `enable_mac`) are in `3-4/` only.

## Retuned on the N-PHY (this repository)

These copies are tuned on the 2.4 GHz radio **integrated in the BCM6362** (N-PHY
rev 8, radio 2057 rev 8), not on the AC-PHY. Differences from the copies in
`b43-ac-wip`, all checked on the board's blob (`wl 6.30.102.7`, symbols and
prologues read with `mips-linux-gnu-objdump`):

- tables: `wlc_phy_table_{read,write}_nphy` instead of the `_acphy` ones;
- `and_radio_reg` / `or_radio_reg` added (ops 35/36): the blob's N-PHY branch
  uses them, the AC-PHY does not;
- `si_pmu_spuravoid` added (op 37), which on a 2.4 GHz N-PHY is part of the
  channel change — with the caveat that only its prologue is checked in the
  disassembly, not which argument carries the value;
- `phy_reg_write_array` added (op 38) as a **marker**: its ops go through the
  accessors already hooked anyway, as the trace shows (after every marker the
  corresponding ops follow), so it was no coverage hole; the record only serves
  to delimit the initvals;
- the `skipphyrd` list empty by default: the DFS polling that motivated it is a
  5 GHz matter and does not exist here.

What it captures: PHY rd/wr/mod, **distinct PHY and/or** (ops 19/20), radio
rd/wr/mod (write, mod, and, or), PMU cc/rc/pll/spuravoid, ChipCommon GPIO, nphy
tables, the **control towards the MAC** (`wlc_bmac_mctrl`, `wlc_bmac_mhf`) and
the **MAC object memory** (`wlc_bmac_read_objmem16`/`_write_objmem16`, ops
`OBJ.RD`/`OBJ.WR`): among other things the ucode leaves there the noise power
sample that the `crs_min_pwr` cal reads, and that read does not go through a
PHY register.

## The `wlc_bmac_*` family, where accesses to the d11 core go (`3-4/` only)

The accessor family is large — brcmsmac has **66** `brcms_b_*`, which are the
same ones renamed — and ten of them were hooked. The missing ones were not
harmless: they are why three classes of the port's ops could not be compared
and ended up as exceptions in `test/unit/phase_compare.py`. Seven added, with
the corresponding op:

| accessor | op | why it is needed |
|---|---|---|
| `wlc_bmac_read_shm` / `write_shm` / `set_shm` | `SHM.RD` / `SHM.WR` / `SHM.SET` | they take an offset in **bytes** into the SHARED region, which is the level of `b43_shm_{read,write}16`. With `write_objmem16` alone a word address with a space selector was compared against a byte offset — noise — and the **677 SHM offsets** the vendor touches stayed out of the comparison |
| `wlc_bmac_core_phy_clk` | `PHY.CLK` | one of the two exceptions left: as long as it was not hooked, "zero occurrences" did not say whether it was called (brcmsmac: `brcms_b_core_phy_clk`, `main.c:722`) |
| `wlc_bmac_switch_macfreq` | `MAC.FREQ` | the other one (brcmsmac: `brcms_b_switch_macfreq`, `main.c:2096`) |
| `wlc_bmac_suspend_mac_and_wait` / `enable_mac` | `MAC.SUSP` / `MAC.EN` | they delimit everything: the measured window **ends with the MAC enabled and transmitting**, and that boundary used to be guessed |

The criterion for the next ones: hook the **accessor**, at the level where b43
has its API. Where an access does not go through an accessor it stays
unobservable, and the exception in `test/unit/phase_compare.py` is declared
against that: `psm_phy_hdr_param` (0x492) is written in brcmsmac with a direct
`bcma_write16` inside `wlc_phy_chanspec_nphy_setup`, and a tracer that hooks
functions does not see it.

This holds only for **new captures**: the existing ones do not gain them.

## The perimeter, which is not a matter of style

What is hooked here are **accessors**: functions that read and write registers
and shared memory, i.e. the interface to the hardware. What comes out is a
trace of what the chip does, and the behaviour is reconstructed from it
afterwards.

The PHY's internal functions are **not** hooked, and that is a choice: marking
their entry would be convenient to delimit the phases, but it produces a map of
the structure of a third party's driver, which is something other than
observing the hardware and much easier to contest. If a phase boundary is
needed, it is derived from the accessors' ops — and with `MAC.SUSP`/`MAC.EN`
there is now an explicit one where it used to be guessed.

## Hooks that do not fit the 4-word detour

Better to know before flashing than to find out from the log:

| function | why |
|---|---|
| `wlc_bmac_mhf_get` | `beq` at word 1: not even the short j fits. Solved by patching the **call sites**, see below. |
| `wlc_bmac_read_shm` / `_write_shm` | 16- and 20-byte wrappers with a `jr` at word 2. That is why the target of the tail call, `read/write_objmem16`, with a clean prologue, is hooked. |

This table predates the seven `wlc_bmac_*` hooks above: `3-4/` hooks
`wlc_bmac_read_shm` and `_write_shm` with the plain detour. Whether that holds on
the 6.30 blob, where the table says the wrappers jump at word 2, is not checked
here; `2-6-30/` does not hook them.

Some functions have a branch inside the detour window, so neither the 4-word
detour nor the short j fit: `wlc_bmac_mhf_get` has a `beq` at word 1, which is
why `MAC.MHF.RD` is 0 out of 215 `MAC.MHF` in every capture.

**Call-site patching** (preferred). The module is `-mabicalls`: no `jal` in
`.text`, calls are `lui`/`addiu` + `jalr`, or `jr $t9` for tail calls. The pair
is rewritten to load the stub; the function stays intact and it works on both
kernels. Three conditions checked at run time: exact address, jump on the same
register, `addiu` not shared. `callsites_pic.py` in `b43-ac-wip`'s
`reverse-tools/` does the same analysis offline on a blob.

| function | 6.30 | 7.14 |
|---|---|---|
| `wlc_bmac_mhf_get` | 2 sites, 2 ok | 3 sites, 3 ok |
| object memory | `read_objmem`, 4 sites, 2 ok | `read_objmem16`, 4 sites, 2 ok |

**`break` path** (3.4 only). One word, a die notifier on `DIE_BREAK`: `do_bp`
calls it for `BRK_KPROBE_BP` outside `CONFIG_KPROBES`. On 2.6.30 it does not
exist and is compiled out — `do_bp` goes straight to `do_trap_or_bp` and
`set_except_vector` is not exported.

**Names change between versions** (`read_objmem` / `read_objmem16`, struct
offsets `0x84` / `0x88`) and hooking the wrong name gives no error: the hook is
skipped and the capture comes out without that class of ops.

## A single run over several channels

What follows was written for `b43-ac-wip`'s 5 GHz sweeps: `capture_plan.sh` and
`split_by_chanspec.py` are not in this repository, nor in `b43-ac-wip` at
`01e1329`. It is kept for what it says about the records.

The phases are **separate**, because a whole run produces too many bytes to
collect in one go. One phase at a time, each with its own file:

```sh
sh capture_plan.sh 20a          # on the device, with arm=1
sh capture_plan.sh 20b
sh capture_plan.sh 40
sh capture_plan.sh 80
python3 reverse-tools/split_by_chanspec.py trace-20a.txt split/
```

At 40 and 80 MHz the **command** wants the low channel of the block
(`5g36/40`, not `5g38/40`), while the resulting **chanspec** carries the
**centre** channel (`ch=38 bw=40`). They are two different levels, both true.

Two things seen in the first captures make the `CHANSPEC` records useless as a
boundary:

- they are **one cycle late**: in phase 20b `ch=40`, `ch=36`, `ch=60` appear,
  which belong to 20a. `wlc_phy_chanspec_set` is called with the current
  chanspec, not the new one. Marking the boundaries would need
  `wlc_phy_chanspec_set_nphy` hooked too.
- **only one per phase** arrives, or none.

So `split_by_chanspec.py` cuts on **time jumps** and takes the names from the
order of the phase, reporting the `CHANSPEC`s found for verification. Default
threshold 1.03 s: the `sleep 1` between cycles leaves 1.06 s, while the
periodic noise sampling leaves gaps of exactly 1.00 s between two `OBJ.RD`, and
by duration they would be indistinguishable.

**The listener must not be stopped between channels.** The FIFO holds
`FIFO_RECS` = 32768 records; at about 2500 records/s that is ~13 seconds of
margin. If it is stopped, the queue fills up and the module emits an `OP_DROP`
record with the count: useful to know how much was lost, but lost it stays.

The cycle is `{chanspec; up; wait; down}`, so every channel gets a
**down->up**, not an attach. On 3.4 the trace may contain 1 initial attach
(from the re-probe) + N down->up; on 2.6.30 only N down->up, because the rescan
unloads `wl` and the attach cannot be captured that way.

The segments are all in the same phase and so comparable among themselves, but
they have to be compared with the `switch_channel` gate and `AC_FIRST_INIT=0`,
not with `full`, which models the attach. The distinction is not cosmetic: the
`crs_min_pwr` cal, the first block of bank `0x0910` and the double programming
of the analog part behave differently in the two phases.

The wait after `up` lets the asynchronous calibrations complete — crsmin, PAPD,
fdiqi — which are the ones that read from shared memory and template RAM.

`wlc_phy_chanspec_set` is hooked and emits `CHANSPEC` at every change, with the
raw chanspec in `addr`. The decoder expands it:

    CHANSPEC ch=36 bw=20 band=5g raw=0xd024

That way a single capture can cover 36/20, 36/40, 36/80 ... 140/20, 140/40,
140/80 and is cut afterwards on the `CHANSPEC` records. The generic function is
hooked and not the per-PHY variant because it fires for every PHY and is small
(96B on 6.30, 324B on 7.14, clean prologue on both).

The decoding uses the standard 802.11ac format (`chan` bits 0-7, `bw` 0x3800,
`band` 0xc000). **An assumption, not verified on a capture** — none of the
current captures contains `CHANSPEC` records. The `raw` field is there on
purpose: if the decoding does not add up, the raw value stays readable.

## I/O coverage

By memory space, not by function name:

| space | state |
|---|---|
| PHY registers, radio, PHY tables | covered |
| object memory / SHM | covered (`OBJ.*`) |
| MAC mctrl + MHF, PMU, GPIO, core reg | covered |
| **template RAM** | covered (`TPL.*`) |
| **OTP** | covered (`OTP.*`) |
| inline I/O through `R_REG`/`W_REG` | **not hookable**: they are macros, not functions |

Template RAM is where the PHY loads the tone waveforms, input to RXIQ, PAPD and
`do_dummy_tx` (for the N-PHY: `wlc_phy_loadsampletable_nphy`,
`wlc_phy_runsamples_nphy`). No class of op covered it, so that data was missing
from the captures altogether — the same kind of hole as SHM.

On 6.30 the `templateptr`/`templatedata` accessors do not exist: there only
`write_template_ram` is hooked.

OTP is hooked at the **generic level** (`otp_init`, `otp_read_word`,
`otp_read_region`), which has the same names on 6.30 and 7.14 and a clean
prologue, while `hndotp_*`/`ipxotp_*` change between versions. The content is
the SROM image — static and already known from the raw dumps — so it serves to
know **when** it is read and **which words**, i.e. where the values are
consumed. The value ends up behind a pointer, not in the return, so the record
holds the word count and not the data.

## Keeping the FIFO on DFS channels

On DFS channels the radar detector polls `PHY.RD 0x0253` and `0x0254`
continuously: **192000 and 194000 reads** in the four phases, 85% of all PHY
reads, and twice that with `retcap` on. They have nothing to do with the channel
configuration, so for the bulk sweep they are filtered before the FIFO:

```sh
insmod wl_diag.ko arm=1 skipphyrd="0x253,0x254"
```

Two deliberate restrictions, both from checks on the data.

The filter applies **only to `OP_PHY_R`**: the address spaces are separate per
class, and in the same captures there are 32 `OBJ.WR` at `0x252` and 32 at
`0x254` which are object memory offsets, not PHY registers. A filter on the
address alone would have dropped them silently.

And **only `0x253`/`0x254`** are filtered. The head of the block — `0x251` and
`0x252`, read 1558 times in all, once per block — is plausibly the pulse status
and data, i.e. the useful part: it costs little and is kept.

Filtered records have a counter separate from the lost ones, so `OP_DROP`s
stay an indicator of real loss. At the end of the run:

    wl_diag: scaricato (persi: 0, filtrati: 148392)

**DFS captures have to be taken without the filter**, two or three, because
those reads are the only material on the detector. More is not needed: Linux's
ETSI/FCC classifier already has it in
`drivers/net/wireless/ath/dfs_pattern_detector.c` (377 lines), which consumes
`struct pulse_event {ts, freq, width, rssi, chirp}` — and the fields the
Broadcom driver prints (`min_pw`, `pri`, `fm_min`/`fm_max`, `nconsecq_pulses`)
map onto those. So of the 24 KB of `wlc_phy_radar_detect_run` only the
**format of the four registers** is needed, not the classification.

Mind the units: `pri=44258` is too large to be microseconds, since the
regulatory PRIs lie between 200 and 3000 us. To be established from the
capture, not by hypothesis.

## If no RETVAL arrives

Symptom: every read has `val=UNDEFINED` and there is not a single `RETVAL`
record in the trace, so there is the sequence of the reads but not the values.

First check, one line:

```sh
dmesg | grep 'trampolino ritorno'
```

Missing -> no eligible hook was `retcap`, and the trampoline was not built.
Present -> it is built but not reached, and the suspect is the
`wl_diag_enter_ret` pool, which silently returns `orig_ra` when its entries run
out.

**It really happened**, cause: three state fields (`use_bp`, `use_sites`,
`bp_stub`) inserted in `struct hook` **between `shortj` and `retcap`**. The
table uses positional initialisers, so the `true` meant for `retcap` ended up in
`use_bp` and `retcap` stayed false for every hook. The new fields now sit at the
end, and the initialisers use the designated form (`.retcap = true`), which is
immune to reordering.

## Noise goes through object memory

    wlc_phy_noise_read_shmem -> wlapi_bmac_read_shm -> wlc_bmac_read_shm
                             -> wlc_bmac_read_objmem[16]

So `OBJ.RD` also captures the noise sample of the `crs_min_pwr` cal. In 7.14
`noise_read_shmem` calls the PHY's crs_min_pwr_cal, in 6.30 it does not: that
is why the DSL always writes zero in bank `0x0910`.

`MAC.MHF.RD` on the other hand is redundant: `mhf_get` is a pure getter and
every write is already captured (215 records, indices 0..4), so the state is
rebuilt offline.

## Parameters

| param | default | variant | effect |
|-------|---------|---------|--------|
| `arm` | `0` | both | `0` = dry run (logs the hook plan only); `1` = applies the patches |
| `delay` | `0` | both | `1` = also hooks `osl_delay` (noisy, usec unreliable) |
| `skipphyrd` | empty | both | **PHY register** reads not to record, e.g. `"0x253,0x254"` |
| `poke` | empty | both | writes one byte of kernel memory: `<hexaddr>:<value>`, see below |
| `klookup` | — | `2-6-30/` | address of `kallsyms_lookup_name` (from `/proc/kallsyms`) |
| `syms` | — | `2-6-30/` | explicit addresses: `'name:hexaddr,name:hexaddr,...'` |

### `poke=`: forcing a full PHY init

The blob's down path does not clear `hw_up`, so `wl down; wl up` only redoes a
partial init. Clearing that byte, the next up goes through `hw_up()` ->
`wlc_phy_por_inform()` and the PHY reinitialises in full, static tables and
`rcal`/`rccal` included:

```sh
insmod wl_diag.ko arm=1 poke=82a4bcac:0
wl up
```

The address belongs to **that** instance and changes at every load of `wl`. The
chain, checked by reading the device's memory and not deduced from brcmsmac:

    netdev_priv(dev)  = wl_if        <- from the wd_dump_privs log
    wl_if  + 0x04     = radio obj.   (same for wl0 and wl0.1, different for wl0 and wl1)
    radio  + 0x04     = pub
    radio  + 0x08     = wlc          (wlc and pub point at each other at offset 0)
    pub    + 0x2c     = hw_up

`poke=` prints the value before and after, so a wrong address shows at once
instead of silently doing nothing. The write is done by the kernel and not
through `/dev/mem`, because on MIPS that maps uncached and might not be coherent
with the KSEG0 view the driver uses.

The proof that it worked is not the byte: it is `PHY.WR addr=0x0072 val=0x2800`
showing up in the trace, the opening of table 10 with which the static download
starts. If it is not there, the init was partial again.

## Build

Out of tree, against the device's kernel (same `.config`, same
`Module.symvers`, otherwise vermagic/CRC do not match and `insmod` refuses):

```sh
make -C 2-6-30 KDIR=/path/to/kernel-2.6.30 ARCH=mips CROSS_COMPILE=mips-linux- -j
make -C 3-4    KDIR=/path/to/kernel-3.4-rt ARCH=mips CROSS_COMPILE=mips-linux-gnu- -j
```

`2-6-30/` does not need `CONFIG_KPROBES` (the tracer uses inline detours, not
kprobes); both need `CONFIG_KALLSYMS=y`. Copy `wl_diag.ko` to the device and
`decode-wl-diag.py` to the collecting host.

## Capture workflow

**For the integrated radio** (`0x14e4:0x435f` on the SoC backplane) there is no
PCI to rescan: the attach/init/up cycle comes back with `wl down; wl up` or by
unloading and reloading `wl`, and `router-data/dsl3580l/README.md` has the
sequence actually used, with `hw_up` cleared for a cold init. The rest (pipe to
the host, start order of the capture, decoding) is the same.

The steps below were written for a PCIe card, `b43-ac-wip`'s `wl1`.

The `wl` module stays **loaded** for the whole procedure: `kallsyms` has to see
its symbols at `insmod` time. The *device* (PCI function) is detached, not the
module. The golden rule: **arm while the device is down**, so the next re-probe
runs the attach through the hooks.

**On 2.6.30 the rescan unloads `wl`.** It is not the kernel: removing a PCI
function calls the driver's `remove()` but does not unload the module — which
is why on 3.4 `wl` stays loaded when the device is removed. On 2.6.30 it is the
vendor's userspace (hotplug or `rc` scripts) that does `rmmod wl`.

Two defences, in order:

**A reference on the target.** When arming, `wl_diag` takes a reference on
`wl`, so `rmmod wl` fails with `-EBUSY` and the module does not go away; device
remove/probe keep working. The vendor's script will log an error on its
`rmmod`: that is expected. To unload `wl`, unload `wl_diag` first.

**Fallback notifier**, if the reference could not be taken: on
`MODULE_STATE_GOING` of the target the hooks are abandoned **without
restoring** — the memory is about to be freed and rewriting it would be worse.

After a re-`insmod` of `wl`, `wl_diag` has to be reloaded anyway: the addresses
change.

### Windows checkout: CRLF

`.gitattributes` forces `eol=lf`. If the clone predates it, the scripts reach
the router with CRLF and do not run: `set -u` followed by CR is an illegal
option, and the CR moves the cursor back to column 0, eating the start of the
messages. It shows as errors like `: not foundn.sh: line 27:` instead of
`capture_plan.sh: line 27: X: not found`, or a
`syntax error: unexpected end of file (expecting "done")` on a correct script.
Remedy:

```sh
tr -d '\r' < capture_plan.sh > /tmp/cp.sh && sh /tmp/cp.sh 20a
```

### 0. Host: listener ready FIRST

TCP, not UDP: busybox's `nc` on the router has no `-u`, and with TCP no record
is lost or split in half.

Linux/macOS — `ncat` (package `nmap-ncat`); netcat-openbsd's `nc` is fine too
over TCP:

```sh
ncat -l 5555 | python3 decode-wl-diag.py | tee trace.txt
```

Windows: `ncat` exists for Windows too and is the simplest way. Without it, a
PowerShell `TcpListener` that writes a raw `.bin` — the PowerShell pipe passes
**objects**, not bytes, so python cannot be put straight into it:

```powershell
$l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, 5555)
$l.Start(); $c = $l.AcceptTcpClient(); $ns = $c.GetStream()
$fs = [System.IO.File]::Create("$PWD\trace.bin")
$buf = New-Object byte[] 4096
try {
    while (($n = $ns.Read($buf, 0, $buf.Length)) -gt 0) {
        $fs.Write($buf, 0, $n); $fs.Flush()
    }
} finally { $fs.Close(); $c.Close(); $l.Stop() }
```

then:

```powershell
python decode-wl-diag.py < trace.bin > trace.txt
```

### 1. Dry run: check the hook plan

```sh
insmod wl_diag.ko                 # arm=0
dmesg | grep wl_diag              # "piano hook '<name>' @..." for each one
rmmod wl_diag
```

Check that the expected symbols come out hookable (no "non trovato" / "branch
non rilocabile" / "stub fuori regione j 256MB" on the symbols you need — in
particular the new `phy_reg_and/or`, `wlc_bmac_*`).

### 2. Take the device down (PCI down)

Find wl1's PCI function and remove it (on BCM63xx the bus is 1 — adapt the
path to your SoC):

```sh
grep -il 14e4 /sys/bus/pci/devices/*/vendor        # find the node
echo 1 > /sys/bus/pci/devices/0000:01:00.0/remove  # detach: wl.remove() runs
```

### 3. Arm the tracer (device still down)

```sh
insmod wl_diag.ko arm=1           # + delay=1 if the timing is needed
dmesg | tail                      # "wl_diag: ARMATO (N hook) -> /dev/wl_diag"
```

### 4. mknod in /tmp (no udev on this userspace)

The misc device has major 10 and a dynamic minor; the rootfs is often
read-only, which is why the node goes in `/tmp` (tmpfs):

```sh
minor=$(awk '$2=="wl_diag"{print $1}' /proc/misc) # or: cat /sys/class/misc/wl_diag/dev
mknod /tmp/wl_diag c 10 "$minor"
```

### 5. Start the pipe to the host (BEFORE the rescan, not to lose records)

```sh
cat /tmp/wl_diag | nc <HOST> 5555 &
```

### 6. PCI rescan: the re-probe runs the attach under the hooks

```sh
echo 1 > /sys/bus/pci/rescan      # wl re-probes 0x43b3 -> wlc_attach/init/up
```

For the "down-to-bss-up" variant instead of the rescan, with the device already
up. Careful: `wl up` alone does **only the attach** (equivalent to the first
scan), it does NOT bring the BSS up. The set-ssid and then `bss up` are needed
in sequence:

```sh
wl -i wl1 down
wl -i wl1 up          # attach only (like the first scan): no BSS yet
wl -i wl1 ssid <SSID> # set the SSID (without bringing it up)
wl -i wl1 bss up      # THIS brings the BSS up (beacon/join)
```

### 7. Close and decode

```sh
rmmod wl_diag                     # restores the prologues + synchronize_sched
```

On the host, `Ctrl-C` on `nc`: `trace.txt` holds the decoded trace. If
`** DROP ** persi=N` lines show up, the kernel FIFO (32768 records) overran:
reader too slow or burst too dense.

## Notes

- **Sacrificial.** `arm=1` writes into the module's memory (RWX) and does
  `flush_icache_range`; MIPS32R1 assumption, to be confirmed on the device.
- **Read = UNDEFINED.** The hooks capture only the entry arguments: the value
  returned by reads is not there (never an invented `0x0000`). For the PHY
  and/or this is not a problem: the operand is `a2`, captured, and the decoder
  prints the effective mask (`clr ~val` / `set val`).
- **Order.** Listener up, then arm with the device down, then the pipe, then
  the rescan. Arming with the device already up loses the start of the attach.
- **Downstream consumer.** `decode-wl-diag.py` (28 B stream).
