# 10 — Enumerazione del backplane

Board: —      Data: —      Commit tree: —      Patch: —

## Core enumerati

| idx | core id | rev | indirizzo | wrapper | driver legato |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Bring-up

| passo | esito |
|---|---|
| clock `wlan_ocp` abilitato | — |
| reset `wlan` / `wlan-ubus` rilasciati | — |
| `CcIdA` / `MacIdA` letti | — |
| `bcma_bus_register()` | — |
| IRQ assegnato e ricevuto | — |

## Criterio di accettazione

- [ ] tutti i core attesi enumerati con id e rev corretti
- [ ] nessun `synth aread32 unhandled offset` nel log
- [ ] nessun `synth awrite32 dropped` nel log
- [ ] `rmmod` + `insmod` ripetuti senza degrado (teardown corretto)

`dmesg` allegato in `bring-up-logs/`: —
