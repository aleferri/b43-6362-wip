# Firmware for the d11 core rev 22

## What b43 looks for

Commit `682edc28b91c` added the mappings for corerev 22: `ucode22_mimo`,
`n0initvals22`, `n0bsinitvals22`. Those are the names b43 asks
`/lib/firmware/b43/` for after extraction.

## What it takes to have them

`b43-fwcutter` extracts based on an md5 of the `wl` blob and on a description of
its contents. The versions OpenWrt packages for b43 are old (4.150.10.5,
4.178.10.4, 5.10.56.27, 5.100.138), and none of them contains a ucode for a rev
22 core: that comes from the 6.30-era blobs, like the DSL-3580L's
`wl 6.30.102.7`.

**To be checked on your setup, not done here:**

```sh
b43-fwcutter -w /tmp/fw wlDSL-3580_EU.o_save
ls /tmp/fw/b43/ | grep -E 'ucode22|initvals22'
```

Three possible outcomes:

1. the three files come out → nothing to do, only the provenance has to be
   documented in `router-data/dsl3580l/`;
2. fwcutter does not recognise the blob (unknown md5) → it needs a new entry in
   its list, a patch to send upstream of fwcutter;
3. fwcutter recognises the blob but does not extract rev22 → the description of
   the contents is incomplete for this version.

In case 2 or 3 the blob stays the source: the symbols are readable with
`nm`/`objdump` and `reverse-tools/blob_tables.py` already extracts regions by
symbol, so the work is understanding the encapsulation, not finding the data.

## Why it matters for HT20 2x2

`ucode22_mimo` is the ucode the vendor uses for 11n on this core: without the
certainty that it is the one loaded, every conclusion about an HT TX that does
not work is ambiguous between "the driver programs the PHY wrong" and "the ucode
does not do 11n". It has to be closed before M3.
