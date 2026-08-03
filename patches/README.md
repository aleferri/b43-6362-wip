# patches

- `bcma/` — la serie per l'enumerazione del backplane WLAN del 6362, destinata a
  mainline. `0001` e `0002` sono le patch già funzionanti sul target bmips del
  fork OpenWrt (là numerate 801 e 803), qui con il placeholder `__DIFFSTAT__`
  rimosso e il rimando al binding corretto; `0003` è il binding DT, che alla
  serie mancava e che **non è ancora passato sotto `dt_binding_check`**.
- `openwrt/` — fix sul target bmips che non hanno senso upstream.
- `b43/` — vuota: le sette patch b43 sono già merged, vedi
  `docs/upstream-status.md`. Le nuove nasceranno qui.

Le patch si applicano con `git am`. Non contengono `Fixes:` verso commit non
merged e non vanno riordinate senza rigenerare i rimandi fra i messaggi.
