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

Due cose che il trace ha chiarito, e che hanno evitato codice inutile:

- `phy_reg_write_array(pi, tbl, n)` esegue le sue op **passando dagli accessor
  già agganciati**: dopo ogni marcatore `PHY.ARRW` nel trace compaiono le
  `PHY.MOD`/`PHY.WR` corrispondenti. Non c'era nessun buco di copertura da
  colmare con un interprete in kernel, solo da etichettare. E `n` è il numero
  di word, non di record.
- le table-op passano per i registri 0x72 (indirizzo, `(id << 10) | off`), 0x73
  e 0x74 (dati), gli stessi che usa `b43_ntab_write*`: nel trace ogni `TBL.WR`
  è seguita da quelle `PHY.WR`. I record `TBL.*` sono quindi etichette, e per
  il confronto col port vanno usate le `PHY.WR`. Verificato su 14 table-op su
  14 con `trace_tables.py`.

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

## Un secondo blob: `wlD6220.o_save`, wl 7.14.89.14

Netgear D6220, 5,4 MB, molto piu' recente del 6.30.102.7 del DSL-3580L. Serve come
controllo indipendente, e la prima cosa che ha dato e' una smentita: `regs_2057_rev8`
e' **identica** fra i due blob, 412 indirizzi, 412 valori e 39 flag senza una
differenza (vedi `gap-inventory.md` 4h).

Cosa aggiunge, sui simboli che ci interessano (679 contro 738 per il filtro
`nphy|2057`, 101 in piu' nel 7.14):

- **quattordici** tabelle `regs_2057_*` invece di cinque: `rev7v1`, `rev7v2`,
  `rev10`, `rev11`, `rev12`, `rev13`, `rev14v1` in piu';
- `chan_info` per 2057 `rev12`, `rev13`, `rev14`, `rev14v1`, e per il radio
  **20671** su phy rev 19, che e' una generazione oltre;
- le LUT di desense bphy/ofdm `rev3to6` e `rev7to15`.

Il 6.30 in compenso ha tutta la famiglia **sslpnphy** e il radio 2063, che il 7.14 ha
buttato: se serviranno, stanno solo nel vecchio.

Nessuno dei due va nel repo. Le tabelle estratte stanno in
`router-data/blob-tables/`.

### La size delle funzioni fra i due blob

Sui 578 simboli in comune col filtro `nphy|2057`, 358 hanno la stessa size e 220 no.
Ma quelli generici crescono per forza — il 7.14 supporta radio che nel 6.30 non
esistevano — quindi la domanda va posta sui simboli **per revisione**, e li' la
risposta e' netta.

**Tutti e 33 i simboli specifici del 2057 rev5-8 hanno size identica**, nei due blob:
`regs_2057_rev5/rev7/rev8`, tutte le `chan_info_nphyrev*_2057_rev*`, le
`nphy_tpc_txgain_*`, le `nphy_papd_padgain_dlt_*`, le `pad_gain_codes_used_*`. I dati
della nostra strada non si sono mossi di un byte.

Tranne tre, e sono tutti e tre codice della stessa famiglia:

| simbolo | 6.30 | 7.14 | |
|---|---|---|---|
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev5` | 572 | 1340 | +768 |
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev6` | 1692 | 1780 | **+88** |
| `wlc_phy_workarounds_nphy_gainctrl_2057_rev7` | 1096 | 1252 | +156 |

Il `rev6` e' **il corpo che manca allo stub di b43** (voce 1 di
`docs/gap-inventory.md`, `b43_nphy_gain_ctl_workarounds_rev7` vuota). Quindi quando
si andra' a ricostruirlo **conta quale blob si legge**: sono 88 byte di differenza,
una ventina di istruzioni MIPS, e la cattura che abbiamo e' del 6.30. Per quel
lavoro il blob vecchio e' il riferimento, non il nuovo.

### I nomi veri di `a2`, `a3`, `a4`

Il rilascio GPL di brcmsmac ha nomi offuscati per la cal PAPD. Il blob no:

| brcmsmac | blob | size 6.30 | righe C in brcmsmac |
|---|---|---|---|
| `wlc_phy_a4` | `wlc_phy_papd_cal_nphy` | 6088 | 276 |
| `wlc_phy_a3_nphy` | `wlc_phy_papd_cal_gctrl_nphy` | 2444 | 147 |
| `wlc_phy_papd_cal_cleanup_nphy` | stesso nome | 2124 | 124 |
| `wlc_phy_txpwr_papd_cal_nphy` | stesso nome | 1028 | 13 |

`gctrl` conferma da fuori quello che avevamo dedotto leggendo il codice: `a3` e' la
ricerca dell'indice di gain, e la size sta nel rapporto giusto con le sue 147 righe.

**`a4` invece non e' identificata.** `a2` ha 279 righe e `a4` ne ha 276: la size non
le distingue, e i 6088 byte di `wlc_phy_papd_cal_nphy` calzano a entrambe uguale, quindi
il nome e' l'unico indizio e non basta.

Cercando `a2` per size — 279 righe, e il rapporto misurato su `a3` e sul cleanup e'
16,6-17,1 byte per riga, quindi 4600-6200 — fra tutte le `wlc_phy*` del blob in quel
range **non c'e' nessun candidato**: sono `tbl_init_nphy`, `chanspec_radio2057_setup`,
`papd_cal_nphy` e roba di altri PHY. Quindi una delle due, `a2` o `a4`, sta sotto un
nome che non contiene `papd`, e quale delle due sia `wlc_phy_papd_cal_nphy` resta
aperto.

Una cosa emersa cercando, e che vale per il metodo: il blob 6.30 ha **zero** simboli
con `.isra`/`.constprop`/`.part`, il 7.14 ne ha **159**. I due sono compilati in modo
diverso e il vecchio non espone i cloni che gcc fa delle funzioni static. Non spiega
l'assenza di `a2` — `a3` e `a4` sono static anche loro in brcmsmac e nel blob ci sono —
ma spiega perche' nel 7.14 si vedono nomi come
`wlc_lcn40phy_papd_cal.isra.33.constprop.35` e nel 6.30 no.
