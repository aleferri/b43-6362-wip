# Stato upstream

Verificato sull'albero `torvalds/linux` @ `848acc8ffe1b` (3 ago 2026), non su
changelog o wiki.

## Merged (10 giugno 2026)

Serie "b43: complete N-PHY rev 8 + radio 2057 rev 8 support", 7 patch:

| sha | titolo | file toccati |
|---|---|---|
| `682edc28b91c` | b43: add firmware mappings and remove comments wondering about rev22 initvals | `main.c` |
| `ee81dc7636fb` | b43: add d11 core revision 0x16 to id table | `main.c` |
| `2691a1ae6bcc` | b43: route d11 corerev 22 to 24-bit indirect radio access | `phy_n.c`, `main.c` |
| `454518d95d07` | b43: support radio 2057 rev 8 | `radio_2057.c`, `main.c` |
| `894f1482b2f9` | b43: add IPA TX gain table for N-PHY r8 + radio 2057 r8 | `tables_nphy.c` |
| `631c004e5f45` | b43: add channel info table for N-PHY r8 + radio 2057 r8 | `radio_2057.c` |
| `21352612198c` | b43: add RF power offset for N-PHY r8 + radio 2057 r8 | `tables_nphy.c` |

Le tre tabelle (IPA tx gain, chan info, rf pwr offset) **non** pre-esistevano in
b43: sono di questa serie. Verificabile con:

```sh
curl -s "https://github.com/torvalds/linux/commits/master/drivers/net/wireless/broadcom/b43/tables_nphy.c.atom"
```

Nel target OpenWrt `bmips` del fork le stesse patch sono backportate come
`package/kernel/mac80211/patches/brcm/840-01..07`, necessarie fino a che il
target sta su kernel 6.12. Diventano ridondanti al primo bump a >= 6.16.

## Non merged, funzionante fuori albero

`patches/bcma/0001..0003`: enumerazione del backplane. Vedi `soc-glue.md` per il
contenuto e `upstreaming.md` per gli ostacoli.

## Non esistente da nessuna parte

Il supporto HT in b43. Nessuna occorrenza di `ht_cap` o `IEEE80211_HT` nel
driver; `b43_band_2GHz` espone solo `b43_g_ratetable`. Vedi `ht20-mimo-plan.md`.
