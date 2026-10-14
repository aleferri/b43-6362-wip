# patches/b43 — notes on the series that are not in MESSAGES.md

This was the header of `rollup.diff`, while the series was squashed into that
file. The code is now in `b43/`, and `scripts/series-diff.sh` prints the
series as a single diff. What stays here is what the diff does not carry: what
it leaves out, the points that `reverse-tools/check_patch_gating.py` flags and
why they are fine as they are, and the rationale of the changes that came
after `0036`, which have no `MESSAGES.md` entry yet and are needed for the
split.

What it does NOT contain, and why nothing is missing:

  0010  b43: fix the N-PHY sample table generation
        Duplicate of mainline/b43-fix-two-defects-in-the-n-phy-sample-table-logic
        except for two (u32) casts on values that lie in [0, 0x3ff] after
        the and, so with no effect: cordic_iq.i and .q are s32
        (include/linux/cordic.h:36). Measured without 0010: the
        sampleplay-tssi and sampleplay-iqlo windows both do 322/322.

  0022  b43: treat the N-PHY DAC test as a mode not a flag
        Exact duplicate of mainline/b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag,
        line by line on the same five substitutions.

Nothing has ever run on hardware.

`check_patch_gating.py` on the series, with `--tree` the pinned tree plus the
mainline patches (`scripts/series-diff.sh ~/src/pin /tmp/base`), flags **six**
UNGATED points: the ones below except `b43_nphy_tx_power_ctrl`, which it no
longer flags but whose declaration still holds. The last one in the list is one
the tool does NOT flag, and it is wrong not to.

  b43_radio_2057_setup (phy_n.c)
        Shared, but here it only undergoes an extraction: the same four ops on
        the register in the same order, behind a name (b43_radio_2057_vcocal),
        because the tail of the periodic cal now wants it too. The
        chanswitch-ch6 window does not move.

  b43_nphy_op_prepare_structs (phy_n.c)
        Common to every N-PHY, so the two lines that initialise the per-core
        record to -1 run on all of them. Only one place reads that record,
        b43_nphy_txpwr_index(), which no other revision reaches: elsewhere it
        is written and never read. And it is the right value, not the
        convenient one, because zero would say that index zero is forced.

  b43_ppr_add (ppr.c)
        It is the tool seeing the new function land next to it, not a change
        to it: the hunk adds b43_ppr_apply_max_group() above and touches
        nothing existing. The new function has no revision test, like the rest
        of the file: the gate is in the caller, which checks phy rev 8, radio
        rev 8 and the 2 GHz band.

  b43_nphy_rf_ctl_override_one_to_many (phy_n.c)
        Common to every N-PHY rev 7 and up. The TX_GAIN case passes field
        0x2000 instead of 0x4000 and cuts the second argument with
        (value & 0x8000) >> 14 instead of value >> 14: that is what the
        reference does in wlc_phy_rfctrl_override_1tomany_nphy(), (0x1 << 12)
        and (0x1 << 13), and the capture agrees - it clears 0x4000 zero times.
        It is a wrong field number, not a feature of this hardware, and it
        does not go behind a gate.

  b43_nphy_update_tx_cal_ladder (phy_n.c)
        Common to every N-PHY rev 3 and up. The two ladders of the TX I/Q LO
        cal are written in two loops instead of one interleaved loop: the same
        thirty-six cells of table 15, the same values, the same order within
        each ladder, only the grouping changes. No new condition and no extra
        op. It does not go behind a gate because it is not a feature of this
        hardware, it is the order the vendor uses on every revision - the
        capture shows it twice, at #9015 and at #9735.

  b43_nphy_tx_power_ctrl (phy_n.c)
        Common to every N-PHY. The disabling branch goes through
        b43_ntab_write_bulk() on tables 26 and 27 at offset 64 instead of
        opening the data port by hand: it is the same road the enabling branch,
        ten lines below, has always taken on the same two tables at the same
        offset. The cells written are the same, zero is zero: no revision
        behaves differently. It does not go behind a gate because it is not a
        feature of this hardware, it is removing open coding.

  b43_nphy_get_tx_gains (phy_n.c)
        Common to every N-PHY rev 3 and up. The branch with power control on
        reads the per-chain index from the two status registers to fetch the
        gains from the table; here that index is also recorded in
        nphy->cal_orig_pwr_idx[], because that is the read the capture takes it
        from and the tail of the periodic cal puts it back. No extra op and no
        new condition: two assignments to a field only the tail reads, and the
        tail runs on phy rev 8 and radio rev 8. On the other revisions the
        field stays written and unread, as it was before.

  b43_nphy_poll_rssi (phy_n.c), which the tool considers gated and is not
        The read of GPIO_SEL comes out of if (phy.rev < 2), where it sat with
        the write: in the reference the read is unconditional and only the
        write is gated (wlc_phy_poll_rssi_nphy). The tool sees the rev < 2
        inside the function and counts it as gated, but the line I touch runs
        on every revision. The declaration is that the change is INERT: on
        rev >= 2 the value read only serves the rewrite, which stays gated, so
        no revision behaves differently. It costs one register read per call,
        and serves only this bench: in the capture the read of 0xca is there,
        one per poll, and without it the second RSSI cal breaks into 22 blocks
        instead of 3. For the same reason it is NOT a mainline candidate:
        there it is a wasted read.

Added the mphase state machine in b43_nphy_cal_perical_phyinit(): the steps of
the reference - INIT, TX I/Q LO, PAPD, RX I/Q, RSSI, idle TSSI - each with the
bracket that saves the power control state, turns it off, runs the phase and
restores it; and it is the restore that programs adj_pwr_tbl. Plus the
deferred block at the end of b43_phy_initn(), because the bracket restores what
it finds and there the control is still off: the two halves are needed
together.

The six TX phases of the reference stay ONE step, and the capture is the reason:
it emits the twelve commands in a row with a single gain read at #8505 instead of
one per phase. Split in six, the paired run of the cal drops from 428 to 331 in
28 fragments - measured with the bracket around every piece and without, so it
is the split and not the bracket.

Ported the tone measurement of the PAPD cal, which was missing:
wlc_phy_a1/a2/a3_nphy and wlc_phy_papd_decode_epsilon of the reference, that
is the engine's step on one core, the search for the gain code that stops
clipping, and the sliding-window smoothing of the epsilon table. Only the rev 7
and later branch and only the 2 GHz half: the caller checks phy rev 8, radio
rev 8 and the band.

MEASURED: contiguous blocks 17532 -> 17838 (76% -> 78%), which is above the
baseline for the first time. The per-phase total stays 6558 against 6602: the
longest run of cal-papd does not move, but its shape goes from
794 2x334 172 2x78 +14 to 794 2x334 220 178 +32, that is more paired ops in
more pieces. adj_pwr_tbl stays 13.

---

Plus the two per-core brackets around the two steps of the PAPD engine, at the
four points the capture opens (#12197 #12331 core 0, #13311 #13383 core 1), with
the bracket factored into b43_nphy_pwr_ctl_open/close() and used by the
periodic cal too. THEY DO NOT DO WHAT THEY WERE MEANT TO: adj_pwr_tbl stays 13,
the segments go from 14 to 20 against the vendor's 9, contiguous blocks
17838 -> 17831, total 6558 -> 6555. The twenty openings read the gain, so the
control was on, but the closings do not reprogram the table: inside
b43_nphy_tx_power_ctrl() there is a condition on the enabling branch that I
have not read, and it is the next place.

---

get_tx_gains() is a single read for the whole sequence instead of one per step:
the reference redoes it at every call, the capture does not. Worth +3 on
cal-papd and on the per-phase total, 6555 -> 6558, contiguous blocks
17831 -> 17830.

---

And RX IQ with RSSI are a single step, because the capture has them
contiguous: between the reread of the save_cal coefficients (#21169) and the one
that opens coef_setup (#21187) there are eighteen ops and nothing else. In two
steps, the bracket closes and reopens between them, that is two reprogrammings
of 84 cells, and the sequence breaks. coeff-setup-2 is back to 1066 of 1073 in
ONE block (it was 1037 plus fragments) and the per-phase total goes to 6587.

---

And the bracket closes ONCE, at the end of the sequence, not at every step: the
control stays off for the whole cal. The boundary audit in the capture does not
find a single enabling between the phases - only disablings, which are the
openings. Contiguous blocks 17830 -> 18254 (78% -> 80%), per-phase total still
at 6587.

---

And handing the index back sits between PAPD and RX IQ, not after: the capture
has two calls to txpwr_index there, one per core, each with its save and
reapply. Neutral numbers - 18254 and 6587 identical - with the cal-papd
fragments from 34 to 31: it is in for the evidence, not for the number.

---

And the hand-back test is on the state at the ENTRY of the sequence, not on the
step's, which with the single closing at the end is false after the first
opening. Checked: the TBL.RD 7/0x110 len=1 go from 1 to 2, like the vendor.

And the index to hand back is taken at the INIT step. The perical != 2 branch
takes it at the same point, just before precal_txgain, but this hardware has
perical == 2 - which is the reason for the state machine - so it does not go
through there and cal_orig_pwr_idx stayed at zero: the hand-back forced index 0
instead of restoring the starting one, and broke the sub-blocks of the RX IQ
sweep. Restored, the shape of cal-rx-iq is back to 6x420 2x360 6x119 12x85 with
21 fragments instead of 42.

State: contiguous blocks 18258 (80%) against the baseline's 17532, per-phase
total 6587 against 6602.

---

And the tail of the sequence does not hand the index back: both txpwr_index
pairs are BEFORE the cals, inside perical-ingresso - the vendor forces at #7445
and #7868 and hands back at #8096 and #8294 - and the deferred block already
does them. The matching writes of 15/0x57 go from five to seven and the count
reaches 35 like the vendor, with runs unchanged (6587) and blocks 18254.

---
---

And precal_txgain is done only by the deferred block, not by the INIT step as
well: doing it again forced the index a second time, where the vendor has a
single one. The first twelve writes of 15/0x57 match exactly, and the per-phase
total goes to 6658 - ABOVE the baseline's 6602 - with contiguous blocks 18309
(80%), cal-papd 850 against the baseline's 847 and cal-tx-iqlo 443.

---

And the deferred sequence does not run at the end of b43_phy_initn() but from
the end of b43_nphy_op_recalc_txpower(), behind nphy->perical_pending: the
capture puts it AFTER recalc, not before - init, recalc at #5726-6500, then the
cal from #7034. Called from initn, the recalc ops came out seventeen thousand
records past their window and the phase scored zero out of 716.

  recalc-txpower       0 -> 604 of 716 (84%), a single block
  per-phase total   6658 -> 7205 (38%)
  contiguous blocks 18309 -> 18462 (80%)
  cold             18022 -> 18163 (66%)

---
---

And the tail of the sequence puts back the two indices, one per core, before
the single closing: the capture reads 26/0xca at #25017 and 27/0xcc at #25418,
and between the two calls the power control stays off - the four payloads of 84
zeros at #24841, #25064, #25242, #25465 - with the only enabling after them, at
#25641, which is the closing. The indices are not one: they are read from bits
8..14 of C1/C2_TXPCTL_STAT, at #7034 and #7036, and they are 10 on core 0 and 12
on core 1, so they cannot be what the cals force.

  contiguous blocks 18462 -> 19224 (80% -> 84%)
  per-phase total  still at 7205

Adding it, the recalc-txpower window seemed to break, from 519/519 to 432/519.
It was its anchor: it took the THIRD opening of 26/0x0, which was the port's
recalc as long as the sequence ran elsewhere, and which with the sequence at the
end of recalc became the tail's power setup. It was comparing the vendor's
recalc with the port's tail. With the anchor corrected to the second one, the
window is back to 519/519 with the change in.

---

And the read of GPIO_SEL in b43_nphy_poll_rssi() comes out of the write's gate.
See the declaration above: it is inert and it is not a mainline candidate. With
the two new mainline patches on the RSSI cal, the second RSSI cal measured on
its own goes from 623 to 956 ops of 960 (65% -> 100%) and from 22 blocks to 3,
with a single run of 940.

  contiguous blocks 19224 -> 19247 (84%)
  per-phase total   7205 -> 7206 (38%)
  cold             18163 -> 18167 (66%)

---

And the read of the two base indices moves to the head of
b43_nphy_cal_perical_phyinit(), out of the INIT step, where the reference puts
it: at the head of every call, before anything can move them. In the capture it
is at #7034 and #7036, the first two records of the phase, before the read of
the tx gain. Neutral number: perical-ingresso measured on its own stays at 1295
ops of 1402 (92%) in 31 blocks. It is in for the order, not for the number.

---

---

And the entry reads go before the deferred block. The reference, at the head of
wlc_phy_cal_perical_nphy_run(), reads the per-chain index, then the gain, then
get_tx_gain, then turns the control off, and ONLY AFTER does the precal; the
port did the precal first. Now target is taken before the precal, and the index
the tail forces again is recorded by get_tx_gains(), which is the read the
capture takes it from (#7044 and #7046, 10 and 12). It is NOT the reference's
nphy_cal_orig_pwr_idx, which at #7034/#7036 gives 25 and 25: that brcmsmac
branch does not describe this tail, like the precal index and the grouping of
the rccal.

  contiguous blocks 19247 -> 19254 (84%)
  cold             18167 -> 18169 (66%)
  perical-ingresso  divergences 905 -> 885
  per-phase total  still at 7206

---

---

And the deferred block runs INSIDE the bracket. The reference turns the power
control off at the head of the run, before anything forces an index; the port
turned it off only on entering the first step, so the precal and the two
hand-backs returned the control ON and each one reprogrammed the adjusted power
table. The sequence now gets the entry state as an argument instead of reading
it again after the deferred block has turned it.

  contiguous blocks 19254 -> 19804 (84% -> 86%)
  cold             18169 -> 18750 (66% -> 68%)
  perical-ingresso  divergences 885 -> 323, missing ops 675 -> 42
  txpwr-index       known divergences 11 -> 6

---

And the disabling branch of b43_nphy_tx_power_ctrl() goes through
b43_ntab_write_bulk() like the enabling one does, instead of opening the data
port by hand and writing 84 cells in a loop. The cells written are the same for
the same table at the same offset: the road changes, not the effect. But the
vendor's tracer hooks the table function, so its op is there and the port's is
not, and the missing op put everything that followed one out of step - which
explains why the equal blocks inside perical-ingresso got one shorter at every
84-cell write.

  contiguous blocks  19804 -> 19977 (86% -> 87%)
  per-phase total     7206 -> 7578 (38% -> 40%)
  perical-ingresso    run 119 -> 401, divergences 323 -> 286
  rxiq-ingresso       run 306 -> 401, divergences 805 -> 722
  cal-rx-iq           run 420 -> 510
  cold               18750 -> 18711, i.e. 39 fewer: block assignment is
                     exclusive and greedy, and no window broke

---

---

And the reference's two entry reads come back, in its order: the per-chain
index and, if the power control was running, the gains. The reference does them
and then does not read them again - the tail puts back the index taken WITH the
gains, not this one - but the hardware sees them, and without them everything
that follows in this phase is six ops early. It was exactly those six: two of
the pair and four of the table read. Hence the fields cal_orig_pwr_idx[] and
cal_orig_tx_gain[], which carry the reference's names and, as there, nobody
reads; the index the tail uses is in pwr_idx_at_gain[], written by
b43_nphy_get_tx_gains().

  contiguous blocks 19977 -> 20013 (87%)
  per-phase total   7578 -> 7586 (40%)
  cold             18711 -> 18715 (68%)
  perical-ingresso  divergences 286 -> 95, run 401 -> 409

What is left in that window, 95 ops in three groups: 4 ops of 9-bit reread of
tables 26/27 beyond offset 576, which is hardware and declared; 27 ops in a
txpwr_index bracket where the port opens the save block while the vendor is
already halfway; and 64 ops that are the resulting shift.

---

---

And b43_nphy_precal_txgain() writes nphy->txcal_bbmult, which in mainline is
read and never written. b43_nphy_update_tx_cal_ladder() reads it, and scales
with it the 36 rungs of the ladder the TX I/Q LO cal uses: with no writer it is
zero, so every rung comes out at zero amplitude. The reference fills it at the
end of wlc_phy_precal_txgain_nphy(), when save_bbmult, which on rev 7 and up is
always, and again at the end of wlc_phy_cal_txgainctrl_nphy(). In the capture
it is the TBL.RD 15/0x57 at #8076, right after the index is forced.

This is a mainline defect and not one of this hardware: it goes into
patches/mainline/ as soon as what it changes on the cal has been measured,
which cannot be seen here because the read plans serve the vendor's values.

And the gains at the forcing are taken where the capture takes them, between
the forcing and the hand-back (#8080), not inside the INIT step of the state
machine. The reference does cal_target_gain = get_tx_gain() right after
precal_txgain(), in the same step.

  contiguous blocks 20013 -> 20022 (87%)
  per-phase total   7586 -> 7750 (41%)
  cold             18715 -> 18724 (68%)
  perical-ingresso  divergences 95 -> 19, run 409 -> 573

The 19 left are declared in the window: four of 9-bit reread, inert, and
fifteen at the boundary with the next phase.

---

---

And the per-step bracket goes from every step but one. The power control is
already off since before the deferred block, so b43_nphy_pwr_ctl_open() inside
the loop turns nothing off and skips the gain read: 172 ops per step remain that
the hardware does not see. The port emitted 48 brackets of 84 cells against the
vendor's 36, twelve more, and these are they.

Which one to keep is said by the boundary audit, not by intuition: between
perical and TX I/Q LO no transition, between TX I/Q LO and PAPD ONE, between
PAPD and RX IQ four (which are the two per core of the PAPD cal, which opens
them itself), between RX IQ and idle TSSI none. So only the opening at the head
of the PAPDCAL step stays. Removing all six gained on the RX IQ entry and lost
172 contiguous ops elsewhere: measured, not deduced.

  contiguous blocks 20022 -> 20025 (87%)
  rxiq-ingresso     run 401 -> 500, divergences 722 -> 542, missing ops 184 -> 19
  perical-ingresso  missing ops 19 -> 10
  cal-rx-iq         shape from 510 5x507 to 2x510 4x507

---

---

And b43_nphy_cal_perical_phyinit() no longer overwrites the parameter it has
just received. It read the gains again at the head of its own function, with
the power control already off, so b43_nphy_get_tx_gains() took the branch that
reads 7/0x110 instead of the one that indexes the table: the entry gains
computed by the caller ended up in the bin three lines later. Measured with a
temporary print: the caller passed pad 14,12 and the function used pad 4,4.

And the RX IQ cal gets the gains at the FORCED index, not the entry ones. The
capture writes 0x4077 on both chains at #14985 and #14986, which is the cal_gain
of entry 10 of b43_ntab_tx_gain_ipa_2057_rev8_2g (0x4077002e: ipa 7, pad 14,
pga 0, txgm 4) - the index the precal forces on both. With the entry gains,
which have per-chain indices 10 and 12, 0x4077 and 0x4067 come out.

  contiguous blocks 20025 -> 20027 (87%)
  per-phase total   7750 -> 7752 (41%)
  cold             18724 -> 18726 (68%)
  perical-ingresso  divergences 19 -> 17, run 573 -> 575
  rxiq-ingresso     the two values written to 7/0x110 now match

---

---

And the PAPD cal holds the carrier search for its whole length, as wlc_phy_a4()
does from line 25133 to 25380. The hold is counted: without the outer one, the
brackets the inner steps take come out as entry-exit pairs of their own. They
can be counted: the port emitted 8 pairs against the vendor's 6, and the two
extra were short, 27 and 34 ops, that is exactly inner ones the vendor gets for
free.

  contiguous blocks 20027 -> 20029 (87%)
  cold             18726 -> 18729 (68%)
  rxiq-ingresso     divergences 542 -> 530
  cal-papd          run 850 -> 847, shape from 850 2x334 to 847 2x342
  per-phase total   7752 -> 7749

And the capture confirms it directly, which is the check that counts: the
vendor's six pairs are #1620-1666 (34 ops, init), #8492-10756 (1601, TX I/Q LO
cal), #10771-14946 (3658, PAPD cal - the region is #10962-14092), #14964-21143
(5615, RX IQ entry and sweep), #22245-23900 (1052, coeff setup and RSSI cal),
#24271-24317 (34, idle TSSI). The third covers the whole PAPD cal and exits at
#14946, which is the exit seen in the 25-op group of rxiq-ingresso.

The port's hold comes out at 5112 ops against the vendor's 3658, but it is not
misplaced: the two ends match op for op on both sides, and the length differs
because the port emits 1454 ops inside the PAPD cal that the vendor does not -
a known thing, cal-papd does 847 of 2662 and a3/a2 are not there. Counting the
length of a hold does not measure the hold, it measures what is inside it.

At the boundaries two numbers remain: one extra pair (7 against 6) and nine
extra reads of 0xb0 (25 against 16), with the written values matching. It is a
count of calls to b43_nphy_classifier(), not a wrong value.

---

---

And the save block of the RX IQ cal saves one more register, 0x2ff. The capture
reads it at #15015, right after the four rev 7 override registers and before
0x297 and 0x29b: PHY.RD addr=0x02ff val=0x00001000. brcmsmac NEVER reads it -
it only touches bits 0, 13, 14 and 15 of that address in the rev 7 override
path - so here the capture decides, as for the precal index and the grouping
of the rccal. Saved and not restored, which is what the capture does: the read
is there, a write in this phase is not.

It is worth one op, and it closes four hundred and sixty-six divergences:

  rxiq-ingresso     divergences 530 -> 64
  contiguous blocks 20029 -> 20031 (87%)
  cold             18729 -> 18730 (68%)
  cal-rx-iq         shape from 2x510 4x507 2x360 285 to 2x510 4x507 2x360 288

The why is the only interesting thing: the missing read put everything that
followed ONE out of step, and afterwards it never realigned, because from there
on there are long runs of identical zeros and of identical sample table
content. The groups of 357, 46, 21, 16, 5 and the four pairs of 2 were all that.

Of the 64 left, ONE cannot be declared and has to be fixed in the driver: the
OBJ.WR addr=0xb8 val=0x2710, which is write_shm(M_CTS_DURATION, 10000) -
M_PSM_SOFT_REGS + 0x5c*2 = 0xb8 - and which b43 does nowhere, while the
reference does it in both branches that lead to the RX IQ cal (phy_n.c:25413
and 25460). I had filed it under the OBJ.WR exception, and the exception says
something else: that the harness cannot EMIT object memory in a comparable way,
not that the driver may skip DOING the write. wrap.c has b43_shm_write16() and
prints it, so it would show in the trace too.

The other 63: six of 9-bit reread, two MAC.MCTRL which are mac_enable and
mac_suspend and which the harness stubs, two PHY.CLK of the port with the
reshuffle that follows - and those the port does RIGHT, b43_nphy_reset_cca()
and wlc_phy_resetcca_nphy() are identical, fgc(ON)/BBCFG/fgc(OFF)/RESET2RX: it
is the tracer that does not see them, because it hooks wlc_bmac_core_phy_clk
and the accessor behind b43_phy_force_clock() is brcms_b_phyclk_fgc, another
function. Then three of read-plan alignment downstream of the extra carrier
search pair and twenty-eight at the boundary with the next phase.

---

---

And the RXCAL phase writes M_CTS_DURATION. The calibration transmits for a long
time, so the medium has to be protected for as long: the reference sets the
duration of the CTS the ucode sends, at the head of THIS phase and no other, and
it has to be done with the MAC on (phy_n.c:25413 in the state machine, 25460 in
the other branch). In b43 nobody wrote that cell: grep CTS_DURATION over the
whole driver found nothing. M_CTS_DURATION = M_PSM_SOFT_REGS + 0x5c*2 = 0xb8,
and it is the OBJ.WR addr=0xb8 val=0x2710 at #14949.

It needs a new define, B43_SHM_SH_CTSDUR, and the same one in
test/unit/stubs/b43_defs.h, which is generated from the tree's b43.h and has no
script to regenerate it.

  contiguous blocks 20031 -> 20035 (87%)
  cold             18730 -> 18734 (68%)
  per-phase total  still at 7749

The rxiq-ingresso window goes from 64 to 555 divergences, and it has to be said
why that is not a regression: with the three ops in their place the parity of
the alignment changes, and a shift that was masked comes back up - the read plan
of 0xb0. The ops stay the same (18 missing, 18 extra out of 1503) and the two
big measures go up. It closes by removing the extra carrier search pair, which
is an entry of its own.

---

---

And the PAPD cal cleanup also turns off field 0x2000, and does the first two
BEFORE stopping the tone. The capture, at #13741-#13748: e7 and 0x7c for core 0
and ec and 0x7f for core 1 (field 0x1000), then e7 and 0x348, ec and 0x349
(field 0x2000, whose value sits in the four low bits of those two registers
and not in a whole register). The port did not turn 0x2000 off at all and
turned 0x1000 off later. Now the eight ops are op for op the capture's.

Numbers unchanged: that neighbourhood stays inside a 167-op hole that has not
closed, and the rest of the shutdown sequence has to be understood before the
metric sees it. It is in because it is right, not because it pays.

---

---

And the tables of the auxiliary ADC are no longer a /* TODO */. In
b43_nphy_workarounds_rev7plus() the four bulk writes to table 8, offsets 0x08,
0x18, 0x0c and 0x1c, were commented out because the arrays were not there. The
capture has them at #771-#794: four cells per block, 0x8e 0x96 0x96 0x8b for
core 0, 0x8f 0x9f 0x9f 0x96 for core 1, 0x02 0x02 0x02 0x00 for the two gain
ones.

The reference picks the last element of each from the power detector range and
the band. Only this board's combination is here - range 2, radio 2057 rev 8,
2 GHz - because the others have no capture behind them. And there brcmsmac
writes 0x8c on both cores where the capture writes 0x8b on core 0 and leaves
core 1 at 0x96, which is the array's default; the gain element agrees at 0.
Fourth time brcmsmac is older.

  contiguous blocks 20402 -> 20426 (89%)
  cold             18734 -> 18758 (68%)
  portable hole     1193 -> 1169 ops

---

---

And the ladder of the TX I/Q LO cal is written in two runs, not interleaved.
b43_nphy_update_tx_cal_ladder() wrote 0, 32, 1, 33, 2, 34... and the capture
writes 0x00-0x11 and then 0x20-0x31, two consecutive blocks (#9015-#9123 and
#9735-#9843, the same thing twice). The same thirty-six cells and the same
values: only the grouping changes, and brcmsmac interleaves too - fifth time it
is older than the driver of the captures.

  contiguous blocks 20426 -> 20632 (89% -> 90%)
  cold             18758 -> 18965 (68% -> 69%)
  portable hole     1169 -> 963 ops
  cal-tx-iqlo        shape from 443 333 268 80 to 443 333 268 110

Only two runs for 206 ops: the best ratio of lines touched to ops recovered in
the whole series.

---

---

And the first delay of the TX2RX sequence is 0x46, not 8. The capture writes
it at #806, inside the seven-cell bulk on table 7 offset 0x90. For rev 7 and up
the reference does not help: wlc_phy_workarounds_nphy_rev7() does not program
the TX2RX sequence at all, so the 8 that was here had nothing behind it. The six
delays that follow and all seven events already matched.

It costs ONE op (20952 -> 20951 and 18965 -> 18964) because that cell sits
inside a hole that starts earlier, on the masksets of 0xa6/0xa7. It is in
because the value has a source and the previous one did not.

---

---

And the one-to-many override of the TX gain uses field 0x2000, not 0x4000. The
reference, in the txgain case of wlc_phy_rfctrl_override_1tomany_nphy(), does
(0x1 << 12) for the gain and (0x1 << 13) for the lpf gain; b43 did 0x1000 and
0x4000. And the count of the disablings on 0xe7/0xec confirms it on its own:
the vendor turns 0x4000 off ZERO times and 0x2000 eight, the port turned 0x4000
off four times and 0x2000 two.

Also corrected the cut of the second argument: (value & 0x8000) >> 14 instead
of value >> 14, which carried bit 14 along too - the same bit the first call
takes inside tgain.

  contiguous blocks 20951 -> 20971 (91%)
  cold             18964 -> 18972 (69%)
  cal-papd          the small fragments from 19 to 9, shape 847 2x344 224 182

It is the same function that b43_nphy_rf_ctl_override_one_to_many() already
has broken elsewhere: the mainline
b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7 adds the fifth of the
five TX_PU calls. It is worth reading it again in full.

---

And eight masksets on AFECTL_C1/C2, gated on radio rev 8. The capture has them
at #796-#803: bits 2, 3 and 6 to one and bit 7 to zero, core 0 then core 1 each
time, and without touching the override pair next to them. The reference
touches those bits only in the tempsense path, and there always together with
0x8f and 0xa5.

Numbers unchanged: the position in the port is not yet the vendor's, which puts
them BETWEEN the auxiliary ADC tables and the RF sequences. Moving the aux ADC
tables before the sequences, which is the capture's order, costs 24 ops:
something in between depends on the order and is not understood. The eight ops
are in because the capture has them.

---

---

And the internal TX I/Q LO cal turns off the override it turns on. At setup it
does rf_ctl_override_rev7(0x8, 0, 0x3, false, 0) - turns on field 0x8 on table
0 - and nothing turned it off again: the override stayed on on both cores after
the calibration. It is not a matter of ops: it is hardware state left behind.

The capture turns it off at #10729 and #10731, right before the gains go back
in place, and the spot matters: put after stop_playback it costs 13 ops on the
cal-tx-iqlo run, put right next to ntab_write_bulk(7, 0x110, save) it is worth
four.

  contiguous blocks 20971 -> 20975 (91%)
  cold             18972 -> 18976 (69%)
  cal-tx-iqlo       run 443 intact, one small fragment fewer

Two counts on field 0x2000 remain: the port turns it off six times, the vendor
four (#12321, #12777, #13373, #13745). The port does two per step with two steps
per core plus two cleanups; the vendor one per core plus two. Next entry.

---

---

And the PAPD cal cleanup turns 0x1000 off a second time, on its own. I had
removed it myself two increments ago, taking it for a duplicate of the pair I
put at the head: it is not. The capture has it at #12820 and #13788, after
0x800/table 0 and before 0x4/table 1, and the classification of its eight
disablings of 0x1000 on 0xe7 says so without ambiguity - four paired with
0x2000 and four on their own.

  contiguous blocks 20975 -> 20979 (91%)
  cold             18976 -> 18980 (69%)

---

---

And the smoothing of the epsilon table goes. b43_nphy_papd_smooth_epsilon() read
the 64 cells in bulk, averaged over a sliding window and rewrote the first 41.
It has NO source: brcmsmac has no epsilon smoothing anywhere - zero bulk reads
of tables 31 and 33 in all of phy_n.c - and the capture does not do it.
Comparing all the traffic on the two epsilon tables, the two sides differ by
only two ops per core, and both are the port's: the TBL.RD 31/0x0 len=64 and
the TBL.WR 31/0x0 len=41. Everything else matches cell by cell, including the
curious off=0x19 that shows up three times on both sides.

And it is not a matter of counting: those 41 cells are hardware state, and we
rewrote them on top of what the calibration had produced. An op the vendor does
not do and that overwrites the cal's result is worse than a missing op.

Numbers unchanged - they were ops that paired nothing - and the trace loses 213
lines. Nothing in MESSAGES.md, nothing in the note, nothing in docs/: code with
no source.

---

---

And the second M_CTS_DURATION. The vendor writes the CTS duration TWICE per
init: 31000 at #10759, before the PAPD cal, and 10000 at #14949, before the RX
I/Q. It makes physical sense - PAPD transmits longer - and the reference writes
only the 10000 one, and only in the RXCAL phase. Added at the head of the
PAPDCAL step, with mac_enable and mac_suspend around it like the other.

  contiguous blocks 20979 -> 20982 (91%)
  cold             18980 -> 18983 (69%)

---

And the 0x1000/0x2000 pair I had put at the head of b43_nphy_papd_cal_cleanup()
goes: those ops do not belong to the cleanup, they are the TAIL of
papd_run_one(), which already emits them. I had read the classification wrong,
and the positional comparison of the sixteen contested ops settles it:
aligning the tail of core 1's step 2, without the pair at the head of the
cleanup it does 16 of 16, including the 0x1000/0x2000 of #13741-#13748 that I
had attributed to the cleanup.

So the vendor's four disablings of 0x2000 are two per core IN THE STEPS, and the
cleanup does none. With the pair removed the counts all match: 0x2000 four and
four, 0x1000 eight and eight, and the classification by presence of a 0x2000
next to it is identical op for op - alone, P, P, alone, P, P, alone, alone.

Numbers unchanged, eight spurious ops fewer. And the idea of gating the tail of
run_one on gain_ctrl falls too: the vendor does it in both steps.

---

---

And the PAPD cal cleanup goes INSIDE the second bracket, before it closes. The
port did run_one, pwr_ctl_close, cleanup; the capture stops the tone, puts back
the multiplier and the coupler, walks the list of overrides at #13749-#13918,
and ONLY AFTER reprograms the adjusted power table. Found with the positional
comparison: aligning after the tail of step 2, the vendor does PHY.RD 0xc7
(stop_playback) where the port did PHY.RD 0x1e7 and the 84 cells.

Two lines swapped:

  contiguous blocks 20982 -> 21074 (91% -> 92%)
  cold             18983 -> 19333 (69% -> 70%)
  cal-papd          shape from 847 2x344 224 182 to 847 2x344 316 274
  portable hole      616 -> 524 ops

It is the best ratio of lines touched to ops recovered in the whole series,
better than the two runs of the TX I/Q LO ladder.

---

---

And at the end of the PAPD cal the epsilon offsets go back in and the engine is
turned on, with the status rereads the capture has in between. At
#13842-#13854: the adjust for core 0, the two reads of 0x2bf and 0x2c0, the
adjust for core 1, the two reads of 0x2b1 and 0x2b2, then the enable bit on both
chains. It needs four new names in phy_n.h for the status cells, which b43 did
not have.

Counting register by register, now ALL ten of the engine's match: 0x297, 0x298,
0x29b, 0x29c, 0x2a3, 0x2a4, 0x2b1, 0x2b2, 0x2bf, 0x2c0.

Numbers unchanged: those ops fall inside a block the matcher does not pair
anyway. It is in because it is the bit that TURNS ON the engine, and the PAPD
cal is useless without it.

---

---

And the PAPD cal pulses the reset of the clear channel assessment. Right after
the carrier search hold and well before the tables, the capture at
#10773-#10776 reads BBCFG, writes it back with the RSTCCA bit set and then with
RSTCCA and RSTRX clear. The port did not do it: it had only the write that saves
and clears the RX reset, which the capture has too but INSIDE the papd-tables
window, as PHY.MOD mask=0x8000. They are two distinct writes at two distinct
points, and the port had one.

The spot matters and I got it wrong twice before finding it: put in place of
the existing write, or before the scalar tables, the per-phase run loses 262
ops and the papd-tables window goes from ok to known - because the comparison
there is positional and the extra op shifts everything. After the hold and
before the tables, everything is full again.

Numbers unchanged (21074, 8756, 19333) and papd-tables ok again. It is in
because a single write of the cleared value, which is what was there, leaves
the same value behind and never resets the assessment.

---

---

And the TX I/Q LO cal puts back the radio registers it takes.
b43_nphy_tx_cal_radio_setup_rev7() saves nine cells per core - TX_SSI_MASTER,
IQCAL_VCM_HG, IQCAL_IDAC, TSSI_VCM, TX_SSI_MUX, TSSIA, TSSIG, TSSI_MISC1 -
rewrites them with the calibration's values, and NOTHING put them back: they
stayed dirty for as long as the interface was up. Sixteen radio registers.

The capture restores them in address order at #10737-#10752, right after the
transmit gains go back in place and before the carrier search hold is released,
with the values 5, 0, 0, 3, 0xe, 0, 2, 0 on core 0.

  contiguous blocks 21074 -> 21090 (92%)
  cold             19333 -> 19349 (70%)

Sixteen exact ops, which is the number of writes. It is not fidelity: it is
radio state left behind by a calibration.

---
