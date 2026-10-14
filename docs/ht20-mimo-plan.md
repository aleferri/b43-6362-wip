# Plan for HT20 2x2

Goal: the 6362's integrated radio associates and carries traffic at MCS 0-15 in
HT20, two spatial streams, with mainline b43. HT40 and 5 GHz out of scope.

## Starting point

b43 has nothing of HT: no occurrence of `ht_cap` or `IEEE80211_HT`,
`b43_band_2GHz` sets up only `b43_g_ratetable`, `b43_generate_tx_phy_ctl1()`
handles only legacy rates with the band fixed at `B43_TXH_PHY1_BW_20`, and on RX
`b43_plcp_get_bitrate_idx_{cck,ofdm}()` does not know the HT-SIG.

What is already there and useful: `xmit.h` defines the MIMO fields of the TX
header (`B43_TXH_PHY1_MODE_{SISO,CDD,STBC,SDM}`, CRATE, MODUL), and the
`ucode22_mimo` firmware is the one the vendor uses for 11n on this core.

`b43-ac-wip` sends HT rates and A-MPDUs on the AC-PHY, on the AC TX header: a
reference for the mac80211 side, not code to reuse (`ac-wip-xref.md`).

## Milestones

### M0 — sound legacy base (prerequisite, not a line of HT)

Of the six initial entries of `gap-inventory.md` one was left to close: the
rev7 gain control, which is `patches/b43/MESSAGES.md#0001`, written on the
capture's values. The others turned out to be non-holes on reading brcmsmac and
the trace (loopfilter, rcal, rccal) or misattributed (tx cal radio setup).

Exit criterion: `docs/reports/30-rx-sensitivity.md` and
`60-regression-legacy.md` filled in, with legacy 2.4 GHz no worse than before on
every channel and RX sensitivity measured instead of hoped for. The patch has to
be built first: today it is not.

Why it comes first: if the AGC is tuned wrong, every later MIMO measurement
measures the AGC, not the MIMO.

### M1 — two chains active on receive

`rxchain = 3` stable, plausible per-core RSSI on both chains, RX diversity
working at legacy rates. Criterion: difference between the two chains within a
few dB on a known signal, and no dead chain.

### M2 — HT RX

Decoding of the HT-SIG and reporting to mac80211: `RX_ENC_HT`, MCS index, SGI
and LDPC flags where applicable. Validating it does not need HT transmission: an
11n AP transmitting and counting the frames decoded per MCS is enough.

### M3 — HT TX SISO (MCS 0-7)

MIMO PLCP, `phy_ctl1` with MCS/stream/bw, `ht_cap` announced with **one**
stream only (`rx_mask` 0xFF) to separate PLCP problems from MIMO ones.
Criterion: stable iperf at MCS 7, with no retry storm.

### M4 — HT TX 2 streams (MCS 8-15)

Switch to SDM, `rx_mask` 0xFF 0xFF, per-core TX power, calibration on two
chains. Criterion: `docs/reports/50-throughput-ht20.md` with throughput per MCS
and the distribution of retries.

### M5 — cleanup for upstream

Series split by subject, with no convenience `#ifdef`s; aggregation (AMPDU)
deliberately **out**, declared unsupported rather than half implemented.

## Things not verified that have to be clarified before M3

- whether the available `ucode22_mimo` really exposes the 11n rates through the
  same structures b43 uses for legacy (see `firmware-rev22.md`);
- whether additional initvals are needed for MIMO mode beyond
  `n0initvals22`/`n0bsinitvals22`;
- how the vendor chooses between CDD, STBC and SDM depending on the rate and the
  active chains. **SALAME**: SDM for MCS 8-15 and CDD for MCS 0-7 on two chains
  is what brcmsmac does, but it has not been traced on this blob.
