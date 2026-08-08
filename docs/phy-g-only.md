# Dove b43 tratta la G e non la N

Il driver è nato per le PHY B/G e la N è arrivata dopo, quindi ci sono punti in cui
un ramo esiste solo per G, o in cui una catena di `if` sui tipi di PHY non ha il
caso N. Sul BCM6362 quei punti sono comportamento assente, non solo diverso.

Elenco generato con `reverse-tools/phy_type_audit.py --tree ~/src/linux`, che
raggruppa le occorrenze di `B43_PHYTYPE_*` per costrutto e segnala quelli dove G
compare e N no. Salta i file per-PHY, dove parlare di un tipo solo è corretto.

57 costrutti che discriminano sul tipo di PHY, fuori dai file per-PHY
20 citano G e non N

```
debugfs.c      loctls_read_file                   righe 434-434   tipi: G
lo.c           b43_lo_write                       righe 58-58   tipi: G
lo.c           lo_measure_setup                   righe 412-412   tipi: G
lo.c           lo_measure_setup                   righe 450-450   tipi: G
lo.c           lo_measure_setup                   righe 459-460   tipi: B G
lo.c           lo_measure_setup                   righe 469-469   tipi: G
lo.c           lo_measure_setup                   righe 477-480   tipi: B G
lo.c           lo_measure_restore                 righe 506-506   tipi: G
main.c         b43_calculate_link_quality         righe 1409-1409   tipi: G
main.c         handle_irq_noise                   righe 1429-1429   tipi: G
main.c         b43_wireless_core_init             righe 4875-4875   tipi: G
main.c         b43_supported_bands                righe 5353-5353   tipi: G
main.c         b43_wireless_core_attach           righe 5444-5446   tipi: G HT LP
sysfs.c        b43_attr_interfmode_show           righe 49-49   tipi: G
wa.c           b43_wa_msst                        righe 142-142   tipi: G
wa.c           b43_wa_all                         righe 336-336   tipi: G
xmit.c         b43_rssi_postprocess               righe 595-595   tipi: G
xmit.c         b43_rssi_postprocess               righe 608-608   tipi: G
xmit.c         b43_rx                             righe 734-736   tipi: B G LP
xmit.c         b43_rx                             righe 780-780   tipi: G
```

## Cosa vuol dire, voce per voce

**Legittime, non sono buchi.** `lo.c` (sei voci) è la calibrazione LO della
G-PHY: la N ha la sua in `phy_n.c`, e il file intero non la riguarda.
`wa.c` sono i workaround G. `debugfs.c` e `sysfs.c` espongono controlli che
esistono solo su G (`loctls`, `interfmode`).

**Buchi veri, con conseguenza misurabile:**

| voce | conseguenza |
|---|---|
| `main.c b43_calculate_link_quality`, `handle_irq_noise` | **nessuna misura del rumore di fondo**: `link_noise` resta al valore iniziale e mac80211 riceve una costante. Chiuso da `patches/b43/MESSAGES.md#0006` |
| `xmit.c b43_rssi_postprocess` (due voci) | la conversione del RSSI ha rami per G e per LP, non per N. Da guardare: è il numero che finisce in `ieee80211_rx_status.signal` |
| `xmit.c b43_rx` (due voci) | la decodifica del PLCP e dei flag ha rami per B/G/LP. Da guardare insieme al punto sopra |
| `main.c b43_calculate_link_quality` (top half) | vedi rumore |

**Da leggere prima di dire che sono buchi:**

`main.c b43_wireless_core_init`, `b43_supported_bands`, `b43_wireless_core_attach`
citano G in mezzo ad altri tipi e vanno letti nel contesto — `b43_supported_bands`
è già una voce aperta dell'inventario per un altro motivo (`dev_id 0x435f`).
`ppr.c` e `phy_common.c` non compaiono qui perché citano anche N, ma non è detto
che il ramo N sia completo: lo strumento vede la presenza del caso, non la sua
correttezza.

## Come rifare la misura

```sh
./reverse-tools/phy_type_audit.py --tree ~/src/linux            # solo i sospetti
./reverse-tools/phy_type_audit.py --tree ~/src/linux --all       # tutti i 57
./reverse-tools/phy_type_audit.py --tree ~/src/linux --context   # con le righe
```
