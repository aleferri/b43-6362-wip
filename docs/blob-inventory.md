# Inventario del blob OEM

`wl 6.30.102.7.cpe4.12L07.0` della D-Link DSL-3580L, ELF32 MIPS big-endian
relocatable non strippato (4.3 MB, ~9200 simboli). Il blob non sta nel repo.

Serve per tre cose: verificare le tabelle merged, sapere quali accessor
agganciare col tracer, e vedere cosa esiste per la combinazione PHY r8 /
radio 2057 r8 che b43 non ha.

## Accessor rilevanti per N-PHY

Verificati con `mips-linux-gnu-objdump -d`. La colonna "prologo" dice se le
prime 4 parole sono prive di branch, cioè se il detour classico del tracer è
applicabile.

| simbolo | prologo | note |
|---|---|---|
| `phy_reg_read` | pulito | `beqz` alla 6a parola, fuori dalla finestra |
| `phy_reg_write` / `_mod` / `_and` / `_or` | pulito | addr=a1 mascherato a 16 bit |
| `phy_reg_write_array` | pulito | wrapper: chiama gli accessor qui sopra |
| `read_radio_reg` | **beq alla 3a parola** | richiede la variante shortj |
| `write_radio_reg` / `mod_radio_reg` | pulito | |
| `and_radio_reg` / `or_radio_reg` | pulito | non agganciati dal tracer AC |
| `wlc_phy_table_{read,write}_nphy` | pulito | wrapper sui registri 0x72/0x73/0x74 |
| `si_pmu_spuravoid` | pulito | posizione dell'arg non verificata |

Due cose che il trace mostra, e che hanno evitato codice inutile:

- `phy_reg_write_array(pi, tbl, n)` esegue le sue op **passando dagli accessor
  già agganciati**: dopo ogni marcatore `PHY.ARRW` nel trace compaiono le
  `PHY.MOD`/`PHY.WR` corrispondenti. Non c'era nessun buco di copertura da
  colmare con un interprete in kernel, solo da etichettare.
- le table-op passano per i registri 0x72 (indirizzo), 0x73 e 0x74 (dati), gli
  stessi che usa `b43_ntab_write*`: nel trace ogni `TBL.WR` è seguita da quelle
  `PHY.WR`. I record `TBL.*` sono quindi etichette, e per il confronto col port
  vanno usate le `PHY.WR`.

## Dati per PHY r8 / radio 2057 r8

| simbolo | size | contenuto |
|---|---|---|
| `regs_2057_rev8` | 2478 (413 × 6) | init table radio, verificata contro `r2057_rev8_init` |
| `nphy_tpc_txgain_ipa_2g_2057rev8` | 512 (128 × u32) | verificata contro `b43_ntab_tx_gain_ipa_2057_rev8_2g` |
| `nphy_tpc_txgain_ipa_5g_2057rev8` | 512 | 5 GHz, non in b43 |
| `nphy_tpc_5GHz_txgain_epa_2057rev8` | 512 | 5 GHz PA esterno, non in b43 |
| `chan_info_nphyrev8_2057_rev8` | 5412 (123 × 44) | 14 record 2.4 GHz + 109 di 5 GHz; verificata contro `b43_nphy_chantab_phy_rev8_radio_rev8` |
| `nphy_papd_padgain_dlt_2g_2057rev5` | 64 (32 × s16) | riusata da b43 per il rev 8 |
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev6` | — | il corpo che manca allo stub b43 |

Nota: non esiste `nphy_papd_padgain_dlt_2g_2057rev8`, il che conferma la scelta
fatta nella patch merged di riusare i valori rev 5.

## Layout del record chan_info

Ricostruito e verificato (`reverse-tools/chantab_from_blob.py`), 44 byte:

    u16 chan          numero di canale
    u16 freq          MHz
    u8  radio[28]     stessi campi e stesso ordine di
                      struct b43_nphy_chantabent_rev7
    u16 phy_regs[6]   struct b43_phy_n_sfo_cfg

Le 44 byte e la posizione di `freq` vengono dal blob (le frequenze note a passo
44, offset +2); l'ordine dei 28 campi radio era un'ipotesi, ed è confermata dal
confronto: **336 campi su 14 canali** (18 radio del sottoinsieme 2g + 6 registri
PHY per canale) identici fra blob e array b43. Un ordine sbagliato non avrebbe
prodotto un match pieno.

Ricaduta pratica: i 109 record 5 GHz sono estraibili come array C con
`--emit-c --band 5g`, se un giorno servissero. Non servono a questo progetto e
non vanno mandati upstream senza hardware per provarli.
