# Stato upstream

Verificato sull'albero `torvalds/linux` @ `848acc8ffe1b` (3 ago 2026), non su
changelog o wiki.

## Merged (10 giugno 2026)

Serie "b43: complete N-PHY rev 8 + radio 2057 rev 8 support", 7 patch:

| sha | titolo | file toccati |
|---|---|---|
| `682edc28b91c` | b43: add firmware mappings for rev22 | `main.c` |
| `ee81dc7636fb` | b43: add d11 core revision 0x16 to id table | `main.c` |
| `2691a1ae6bcc` | b43: route d11 corerev 22 to 24-bit indirect radio access | `main.c` |
| `454518d95d07` | b43: support radio 2057 rev 8 | `radio_2057.c`, `main.c` |
| `894f1482b2f9` | b43: add IPA TX gain table for N-PHY r8 + radio 2057 r8 | `tables_nphy.c` |
| `631c004e5f45` | b43: add channel info table for N-PHY r8 + radio 2057 r8 | `radio_2057.c` |
| `21352612198c` | b43: add RF power offset for N-PHY r8 + radio 2057 r8 | `tables_nphy.c` |

Le tre tabelle (IPA tx gain, chan info, rf pwr offset) **non** pre-esistevano in
b43: sono di questa serie.

**Nessuna delle sette tocca `phy_n.c`.** L'elenco dei file è `main.c`,
`radio_2057.c`, `tables_nphy.c` e nient'altro; qui la riga di `2691a1ae6bcc`
diceva anche `phy_n.c` e non è vero, quel commit cambia cinque righe di
`b43_phy_versioning()` in `main.c`. Serve saperlo quando si trova un difetto in
`phy_n.c`: non viene da questa serie. Verificato scaricando i sette commit:

```sh
for s in 682edc28b91c ee81dc7636fb 2691a1ae6bcc 454518d95d07 \
         894f1482b2f9 631c004e5f45 21352612198c; do
    curl -sL "https://github.com/torvalds/linux/commit/$s.patch" |
        grep '^+++ b/'
done
```

Verificabile anche con:

```sh
curl -s "https://github.com/torvalds/linux/commits/master/drivers/net/wireless/broadcom/b43/tables_nphy.c.atom"
```

Nel target OpenWrt `bmips` del fork le stesse patch sono backportate come
`package/kernel/mac80211/patches/brcm/840-01..07`, necessarie fino a che il
target sta su kernel 6.12. Diventano ridondanti al primo bump a >= 6.16.

## Non merged, funzionante fuori albero

`patches/bcma/0001..0003`: enumerazione del backplane. Vedi `soc-glue.md` per il
contenuto e `upstreaming.md` per gli ostacoli.

## Non merged, scritte qui e mai girate su hardware

Sono quattordici, `patches/b43/0001..0014`: l'elenco con lo stato per voce sta nella
tabella del `README.md` e il dettaglio in `gap-inventory.md`. Applicano tutte
pulito su `848acc8ffe1b` e compilano nell'harness, che le verifica contro la
cattura. Due meritano una riga a parte:

| patch | cosa fa | stato |
|---|---|---|
| `patches/b43/0001` | programma il gain control RX per radio 2057 rev 8 in 2.4 GHz bw20, sui valori della cattura | verificata op per op nell'harness (finestra `gain-control`, 87/87), **mai girata su hardware**; gate `reports/30-rx-sensitivity.md` |
| `patches/b43/0002` | porta gli offset di potenza del rev 8 sui valori rev 7 del vendore | **chiusa dalla cattura**: i valori rev 7 predicono 128 celle su 128, quelli in tree 5 (`rf-pwr-offset-rev8.md`). Non è più codice morto, `0003` abilita il percorso che la legge |

`0001` non va spedita prima della misura di sensibilità RX. Ha già cambiato forma
una volta: era scritta su brcmsmac, la cattura ha mostrato valori diversi
(`trace-init-2g.md`).

## Non esistente da nessuna parte

Il supporto HT in b43. Nessuna occorrenza di `ht_cap` o `IEEE80211_HT` nel
driver; `b43_band_2GHz` espone solo `b43_g_ratetable`. Vedi `ht20-mimo-plan.md`.
