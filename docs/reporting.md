# Reportistica

I template stanno in `reports/`. Regole: un report si compila con numeri
misurati; le celle non misurate restano `—`, non si riempiono con stime. Un
report con stime spacciate per misure fa più danno di un report vuoto, perché
qualcuno ci costruirà sopra.

| report | quando | criterio di accettazione |
|---|---|---|
| `00-hw-inventory.md` | una volta per board | chip id, corerev, phy rev, radio rev, sprom rev letti da `dmesg`/debugfs, non da datasheet |
| `10-enumeration.md` | dopo ogni modifica al glue bcma | tutti i core enumerati con id e rev, IRQ assegnato, nessun `synth aread32 unhandled` nel log |
| `20-init-coverage.md` | dopo ogni modifica al PHY | percentuale di op del flow vendor riprodotte dal port, per funzione |
| `30-rx-sensitivity.md` | gate di M0 e M1 | PER vs livello di ingresso per rate, per catena |
| `40-tx-power.md` | gate di M0 e M4 | potenza misurata vs target per rate, per catena, con e senza tpc |
| `50-throughput-ht20.md` | gate di M4 | throughput e retry per MCS 0-15, HT20 |
| `60-regression-legacy.md` | ogni serie prima dell'invio | legacy 2.4 GHz non peggiorato: associazione, throughput, PER su tutti i canali |

## Cosa va nel verbale di bring-up

`bring-up-logs/` tiene i log grezzi con il contesto: kernel, commit del tree,
patch applicate, comandi dati, e l'esito atteso vs osservato. Un `dmesg` senza
il commit a cui si riferisce non è riproducibile.
