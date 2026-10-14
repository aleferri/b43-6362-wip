# 10 — Backplane enumeration

Board: —      Date: —      Tree commit: —      Patches: —

## Cores enumerated

| idx | core id | rev | address | wrapper | bound driver |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Bring-up

| step | result |
|---|---|
| `wlan_ocp` clock enabled | — |
| `wlan` / `wlan-ubus` resets released | — |
| `CcIdA` / `MacIdA` read | — |
| `bcma_bus_register()` | — |
| IRQ assigned and received | — |

## Acceptance criteria

- [ ] every expected core enumerated with the right id and rev
- [ ] no `synth aread32 unhandled offset` in the log
- [ ] no `synth awrite32 dropped` in the log
- [ ] repeated `rmmod` + `insmod` with no degradation (correct teardown)

`dmesg` attached (`bringup-log-*.txt`): —
