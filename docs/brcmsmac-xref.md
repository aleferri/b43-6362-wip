# brcmsmac xref for N-PHY rev 8 / radio 2057 rev 8

Generated with `reverse-tools/brcmsmac_xref.py --tree ~/src/pin --format md`
(the table below is the tool's output, unchanged, checked again at
`848acc8ffe1b`). brcmsmac is in tree and GPL: it is the reference source for
every hole in the inventory.

| funzione brcmsmac | primo match | radiorev==8 | NREV_IS(rev,8) |
|---|---|---|---|
| `wlc_phy_workarounds_nphy_gainctrl` | 15593 | 2 | 0 |
| `wlc_phy_workarounds_nphy_rev7` | 16165 | 4 | 0 |
| `wlc_phy_get_ipa_gaintbl_nphy` | 17788 | 2 | 0 |
| `wlc_phy_radio_init_2057` | 19737 | 0 | 2 |
| `wlc_phy_chan2freq_nphy` | 20244 | 0 | 1 |
| `wlc_phy_chanspec_radio2057_setup` | 20961 | 1 | 0 |
| `wlc_phy_papd_cal_setup_nphy` | 24266 | 4 | 0 |
| `wlc_phy_a2_nphy` | 24741 | 2 | 0 |
| `wlc_phy_a3_nphy` | 24991 | 1 | 0 |
| `wlc_phy_a4` | 25191 | 3 | 0 |

The `primo match` column is the line of the **first occurrence of the pattern**
inside the function, not the line where the function starts: the tool records
it while it walks the matches. For the definition line there is the table
below, and the two do not coincide — `wlc_phy_workarounds_nphy_gainctrl`
starts at `15425` and its first `radiorev == 8` is at `15593`.

`reverse-tools/cfuncs.py` used not to recognise the signatures kernel style
wraps (`static void` on one line, name and parameters on the next), and
attributed those functions' lines to the previous function: the table above is
generated after the fix, and `reverse-tools/test_cfuncs.py` keeps it fixed.

Useful 2057-specific functions, from the same file:

| function | line | what it is for |
|---|---|---|
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev6` | 15224 | the body the b43 stub lacks (radiorev 3 and 8) |
| `wlc_phy_radio_init_2057` | 19731 | init table + dispatch by phy rev |
| `wlc_phy_radio2057_rccal` | 19874 | rccal, groups by radiorev |
| `wlc_phy_radio_postinit_2057` | 19957 | post-init |
| `wlc_phy_chanspec_radio2057_setup` | 20821 | per channel, and the RFPLL loopfilter block for radiorev 5/7/8 (line 20960) |
| `wlc_phy_radio205x_vcocal_nphy` | 20802 | vcocal, 20 lines, called by the two `chanspec_radio205x_setup` and by the periodic cal |
| `wlc_phy_papd_cal_setup_nphy` | 24242 | per-core setup of the PAPD cal, 250 lines |
| `wlc_phy_papd_cal_cleanup_nphy` | 24496 | and its restore, 124 lines |
| `wlc_phy_a3_nphy` | 24959 | the gain index search: **reads** the epsilon table in a 20-step loop, 147 lines |
| `wlc_phy_a2_nphy` | 24676 | the epsilon computation: **writes** the epsilon table through `set_bbmult`, 279 lines |
| `wlc_phy_a4` | 25108 | the top level of the PAPD cal, 276 lines |
