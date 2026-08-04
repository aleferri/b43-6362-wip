# b43-6362-wip

Lavoro in corso per completare in **upstream** il supporto al radio 2.4 GHz
integrato nel SoC **Broadcom BCM6362** (d11 core rev 22, N-PHY rev 8, radio
2057 rev 8), con obiettivo finale **HT20 2x2 MIMO**.

HT40 è fuori scope per scelta: i client disponibili sono 2.4 GHz e su questa
banda HT40 non porta nulla di utile. Anche il 5 GHz è fuori scope, con una
conseguenza da gestire e non da ignorare (vedi `docs/gap-inventory.md`, voce
`dev_id 0x435f`).

## Stato in una tabella

| pezzo | stato | dove |
|---|---|---|
| radio 2057 rev 8: init table, chantab, IPA tx gain, rf pwr offset | **merged upstream** (7 patch, 10 giu 2026) | `docs/upstream-status.md` |
| firmware rev22 (`ucode22_mimo`, `n0initvals22`, `n0bsinitvals22`) | mapping merged; disponibilità blob da verificare | `docs/firmware-rev22.md` |
| enumerazione bcma sul backplane del SoC | funzionante fuori albero, **da proporre** | `patches/bcma/`, `docs/soc-glue.md` |
| SPROM fallback per il core su SoC | funzionante solo con l'estensione OpenWrt, **non upstreamabile così** | `docs/upstreaming.md` |
| gain control N-PHY rev 7+ | stub vuoto in mainline, **patch in `patches/b43/0001`**: riproduce la cattura op per op nell'harness, mai girata su hardware | `test/README.md` |
| chantab rev 8, campi 5 GHz | il vendore li azzera a ogni cambio canale, b43 non li tocca | `docs/trace-init-2g.md` |
| chantab rev 8, campi 2.4 GHz | **verificata sul silicio**: 31 cambi canale su 31, cinque canali | `docs/trace-init-2g.md` |
| RF power offset rev 8 | valori sbagliati in mainline, **chiuso dalla cattura**: patch `0002` | `docs/rf-pwr-offset-rev8.md` |
| compensazione PAPD rev 7+ | mai programmata per un early return, **patch `0003`**: 256 celle identiche alla cattura | `docs/gap-inventory.md` |
| tabelle epsilon e scalare del PAPD | motore acceso su tabelle non inizializzate, **patch `0004`** | `docs/gap-inventory.md` |
| bias IPA 2 GHz sul rev 8 | registro sbagliato e valori diversi fra i core, **patch `0005`** | `docs/gap-inventory.md` |
| rumore di fondo su N-PHY | non misurato affatto, **patch `0006`** | `docs/phy-g-only.md` |
| RSSI e decodifica RX su N-PHY | rami solo per G e LP in `xmit.c`, e coefficienti RSSI diversi dal vendore | `docs/todo-nphy.md` |
| potenza target, TSSIG, RF ctl misc | scritti da entrambi con valori diversi | `docs/todo-nphy.md` |
| HT (11n) in b43 | **assente del tutto** | `docs/ht20-mimo-plan.md` |

## Come è organizzato

- `docs/` — stato, inventario dei buchi, piano HT20 2x2, questioni di
  upstreaming, protocollo di cattura, reportistica.
- `patches/bcma/` — la serie per l'enumerazione (core wrapperless big-endian,
  host driver, binding DT).
- `patches/openwrt/` — fix minori sul target bmips.
- `test/` — harness che compila i sorgenti N-PHY del tree in userspace e ne
  emette il trace, per confrontarlo con la cattura vendor.
- `reverse-tools/` — tracer `wl-diag` (due varianti, **tarate su N-PHY**),
  pipeline di decodifica, estrattore/verificatore delle tabelle dal blob OEM,
  analisi di copertura sul tree kernel.
- `router-data/`, `bring-up-logs/`, `reports/` — dati e verbali per board. La
  prima cattura c'è (70796 record, due cicli down/up su canali operativi 1 e 6,
  zero perdite) e ha già corretto una patch: `docs/trace-init-2g.md`.

## Riproducibilità dello stato

Tutto ciò che questo repo afferma sul kernel è verificato sull'albero, non sulla
documentazione (che invecchia). Riferimento: `torvalds/linux` @ `848acc8ffe1b`,
3 ago 2026. Per rifare la verifica:

```sh
./scripts/fetch-upstream-state.sh ~/src/linux      # sparse checkout
./reverse-tools/check_gaps.py --tree ~/src/linux --format md
./reverse-tools/brcmsmac_xref.py --tree ~/src/linux --format md
```

Per riverificare le tabelle merged contro il blob OEM:

```sh
./reverse-tools/blob_tables.py wlDSL-3580_EU.o_save \
    --verify regs_2057_rev8 \
    --against ~/src/linux/drivers/net/wireless/broadcom/b43/radio_2057.c:r2057_rev8_init
```

## Convenzioni

- **SALAME** in grassetto marca un'ipotesi non verificata su hardware o su
  codice. Se leggi una conclusione senza SALAME, deve esserci un riferimento
  file:riga, uno sha, o l'output di uno strumento di questo repo.
- I commenti nel codice descrivono cosa fa il codice adesso, non com'era prima:
  la storia sta nei messaggi di commit.
