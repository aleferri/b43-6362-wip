# Record: two `wl down` / `wl up` cycles, 2.4 GHz bw20, channels 1 and 6

File: `opinit-ch1-ch6-bw20.decoded` — the decoded trace, 70796 lines.

The binary is **not in the repository**: on its own it has no value, the text is
the useful form (readable, diffable, and what the tools consume). Before
dropping it, the text was checked to lose nothing:

    reverse-tools/verify_decode.py trace.raw opinit-ch1-ch6-bw20.decoded
    70796 record confrontati
    nessuna perdita: il testo copre tutti i campi non nulli

For audit, the source binary was 1982288 bytes (70796 records of 28),
sha256 `2483e73ed10f473d71e6386e82809525c6c78aeebda0910e96d26878a3cabeba`,
decoded with `decode-wl-diag.py` at the version of the commit that added it.

| field | value |
|---|---|
| board | D-Link DSL-3580L |
| radio | integrated BCM6362, N-PHY rev 8, radio 2057 rev 8 |
| blob | `wl 6.30.102.7.cpe4.12L07.0` |
| tracer | `wl-diag/2-6-30`, the version retuned on the N-PHY |
| flow | **two `wl up` after a `wl down`**, not an attach |
| band / width | 2.4 GHz, **bw20** on all 31 channel changes |
| operating channels | **1** in the first cycle, **6** in the second |
| off-channel excursions | 5 in the first cycle; 2 and 10 in the second, every 2 s |
| `skipphyrd` filter | empty |
| `OP_DROP` | 0 |
| sequence discontinuities | 0 |
| duration | 39.8 s |

## Structure

| records | contents |
|---|---|
| 1 - 131 | initial radio init (45 `RAD.WR`) |
| 132 - 26100 | first `up`, operating channel 1: 25969 records |
| 26101 - 34156 | 7 excursions to ch5 and back to ch1, ~550-670 records each |
| 34157 - 34937 | the `down` and the 15 s until the next `up`: 781 records, with `GPIO.CTL`/`GPIO.OUT` and 15 `MAC.MCTRL` |
| 34938 - 61971 | second `up`, operating channel 6: 27034 records |
| 61972 - 70796 | 5 cycles ch2 / ch10 / ch6, ~550-670 records each |

Analysis: `docs/trace-init-2g.md`. Pipeline:

```sh
reverse-tools/trace_tables.py opinit-ch1-ch6-bw20.decoded --range 660 800
reverse-tools/verify_chantab_trace.py opinit-ch1-ch6-bw20.decoded --tree ~/src/pin
```

The fields the text does **not** carry, and why that is no loss: the `val` of
read records (the tracer does not capture it; in the binary it is zero-filled
and printed as `UNDEFINED`) and the record padding (always 0). Timestamps have
1 µs granularity at the source, so the six decimals of the text are exact.
