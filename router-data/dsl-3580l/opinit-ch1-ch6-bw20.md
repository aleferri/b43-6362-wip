# Verbale: due cicli `wl down` / `wl up`, 2.4 GHz bw20, canali 1 e 6

File: `opinit-ch1-ch6-bw20.decoded` — il trace decodificato, 70796 righe.

Il binario **non è nel repo**: di per sé non ha valore, il testo è la forma
utile (leggibile, diffabile, e quella che mangiano gli strumenti). Prima di
buttarlo è stato verificato che il testo non perda nulla:

    reverse-tools/verify_decode.py trace.raw opinit-ch1-ch6-bw20.decoded
    70796 record confrontati
    nessuna perdita: il testo copre tutti i campi non nulli

Per audit, il binario di partenza era 1982288 byte (70796 record da 28),
sha256 `2483e73ed10f473d71e6386e82809525c6c78aeebda0910e96d26878a3cabeba`,
decodificato con `decode-wl-diag.py` alla versione di questo commit.

| campo | valore |
|---|---|
| board | D-Link DSL-3580L |
| radio | integrato BCM6362, N-PHY rev 8, radio 2057 rev 8 |
| blob | `wl 6.30.102.7.cpe4.12L07.0` |
| tracer | `wl-diag-2630`, versione riposizionata su N-PHY |
| flow | **due `wl up` dopo un `wl down`**, non un attach |
| banda / larghezza | 2.4 GHz, **bw20** su tutti i 31 cambi canale |
| canali operativi | **1** nel primo ciclo, **6** nel secondo |
| escursioni fuori canale | 5 nel primo ciclo; 2 e 10 nel secondo, ogni 2 s |
| filtro `skipphyrd` | vuoto |
| `OP_DROP` | 0 |
| discontinuità di sequenza | 0 |
| durata | 39.8 s |

## Struttura

| record | contenuto |
|---|---|
| 1 - 131 | init radio iniziale (45 `RAD.WR`) |
| 132 - 26100 | primo `up`, canale operativo 1: 25969 record |
| 26101 - 34156 | 7 escursioni a ch5 e ritorno a ch1, ~550-670 record ciascuna |
| 34157 - 34937 | il `down` e i 15 s fino allo `up` successivo: 781 record, con `GPIO.CTL`/`GPIO.OUT` e 15 `MAC.MCTRL` |
| 34938 - 61971 | secondo `up`, canale operativo 6: 27034 record |
| 61972 - 70796 | 5 cicli ch2 / ch10 / ch6, ~550-670 record ciascuno |

Analisi: `docs/trace-init-2g.md`. Pipeline:

```sh
reverse-tools/trace_tables.py opinit-ch1-ch6-bw20.decoded --range 660 800
reverse-tools/verify_chantab_trace.py opinit-ch1-ch6-bw20.decoded --tree ~/src/linux
```

I campi che il testo **non** porta, e perché non è una perdita: il `val` dei
record di read (il tracer non lo cattura, nel binario è zero-filled e viene reso
`UNDEFINED`) e il padding del record (sempre 0). I timestamp hanno granularità
1 µs nella sorgente, quindi le sei cifre decimali del testo sono esatte.
