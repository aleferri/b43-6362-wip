# 20 — Copertura dell'init PHY

Confronto fra la cattura vendor grezza e l'harness del port, per sequenza.

Board: —      Flow: —      Canale: —      Commit tree: —
Cattura vendor: `router-data/…`      Blob: `wl —`

| funzione | op vendor | op port | match posizionale | note |
|---|---|---|---|---|
| — | — | — | — | — |

Totale: — / — op.

Le funzioni che scrivono tabelle vanno confrontate **per contenuto**, non per
sequenza: il vendor intercala le table-op in ordine diverso. Segnare quali sono
state confrontate così.

## Criterio di accettazione

- [ ] nessun `OP_DROP` nella cattura di riferimento
- [ ] gap fra funzioni spiegati uno per uno (non "rumore")
