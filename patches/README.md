# patches

- `bcma/` — la serie per l'enumerazione del backplane WLAN del 6362, destinata a
  mainline. `0001` e `0002` sono le patch già funzionanti sul target bmips del
  fork OpenWrt (là numerate 801 e 803), qui con il placeholder `__DIFFSTAT__`
  rimosso e il rimando al binding corretto; `0003` è il binding DT, che alla
  serie mancava e che **non è ancora passato sotto `dt_binding_check`**.
- `openwrt/` — fix sul target bmips che non hanno senso upstream.
- `b43/` — le nuove patch b43. `0001` implementa il gain control rev 7+ per
  2.4 GHz (applica pulito, non compilata, non provata); `0002` è una **bozza**
  sugli offset di potenza del rev 8, da non mandare prima della misura, vedi
  `docs/rf-pwr-offset-rev8.md`. Le sette già merged sono in
  `docs/upstream-status.md`.

Le patch si applicano con `git am`. Non contengono `Fixes:` verso commit non
merged e non vanno riordinate senza rigenerare i rimandi fra i messaggi.
