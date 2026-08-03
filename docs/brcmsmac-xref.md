# Xref brcmsmac per N-PHY rev 8 / radio 2057 rev 8

Generato con `reverse-tools/brcmsmac_xref.py --tree ~/src/linux --format md`.
brcmsmac è in-tree e GPL: è la fonte di riferimento per ogni buco dell'
inventario.

| funzione brcmsmac | prima riga | radiorev==8 | NREV_IS(rev,8) |
|---|---|---|---|
| `wlc_phy_workarounds_nphy_gainctrl` | 15593 | 2 | 0 |
| `wlc_phy_workarounds_nphy_rev7` | 16165 | 4 | 0 |
| `wlc_phy_get_ipa_gaintbl_nphy` | 17788 | 2 | 0 |
| `wlc_phy_radio_init_2057` | 19737 | 0 | 2 |
| `wlc_phy_switch_radio_nphy` | 20244 | 0 | 1 |
| `wlc_phy_radio205x_vcocal_nphy` | 20961 | 1 | 0 |
| `wlc_phy_ipa_set_bbmult_nphy` | 24266 | 6 | 0 |
| `wlc_phy_a3_nphy` | 24991 | 1 | 0 |
| `wlc_phy_a4` | 25191 | 3 | 0 |

Funzioni 2057-specifiche utili, dallo stesso file:

| funzione | riga | a cosa serve |
|---|---|---|
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev6` | 15224 | il corpo che manca allo stub b43 (radiorev 3 e 8) |
| `wlc_phy_radio_init_2057` | 19731 | init table + dispatch per phy rev |
| `wlc_phy_radio2057_rccal` | 19874 | rccal, gruppi per radiorev |
| `wlc_phy_radio_postinit_2057` | 19957 | post-init |
| `wlc_phy_chanspec_radio2057_setup` | 20822 | per-canale, incluso il loopfilter |
| `wlc_phy_radio205x_vcocal_nphy` | 20961 | vcocal, e il blocco loopfilter per radiorev 5/7/8 |
