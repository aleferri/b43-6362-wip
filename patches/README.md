# patches

- `bcma/` — la serie per l'enumerazione del backplane WLAN del 6362, destinata a
  mainline. `0001` e `0002` sono le patch già funzionanti sul target bmips del
  fork OpenWrt (là numerate 801 e 803), qui con il placeholder `__DIFFSTAT__`
  rimosso e il rimando al binding corretto; `0003` è il binding DT, che alla
  serie mancava e che **non è ancora passato sotto `dt_binding_check`**.
- `openwrt/` — fix sul target bmips che non hanno senso upstream.
- `b43/` — le nuove patch b43, **in quest'ordine**:
  `0001` gain control per radio 2057 rev 8;
  `0002` gli offset di potenza corretti (i valori in mainline sbagliano 123 celle
  su 128, vedi `docs/rf-pwr-offset-rev8.md`);
  `0003` abilita la compensazione PAPD, che consuma la tabella di `0002` — con i
  valori vecchi scriverebbe 246 celle su 256 sbagliate;
  `0004` inizializza le tabelle epsilon e scalare che il motore PAPD legge;
  `0005` corregge i registri di bias IPA 2 GHz, che erano quelli sbagliati;
  `0007` marca con un TODO la voce morta della tabella override RF (`0x7b`);
  `0008` programma le soglie di carrier sense, che nessuno scriveva;
  `0006` misura il rumore di fondo su N-PHY, che non veniva misurato affatto —
  **l'unica gateata sul tipo di PHY e non sulla revisione**, quindi l'unica che
  esce dal recinto del nostro radio.
  Tutte e tre riproducono la cattura nell'harness e **nessuna** ha girato su
  hardware. Le sette già merged sono in `docs/upstream-status.md`.

Le patch si applicano con `git am`. Non contengono `Fixes:` verso commit non
merged e non vanno riordinate senza rigenerare i rimandi fra i messaggi.
