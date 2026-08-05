# La calibrazione PAPD: mappa della cattura

b43 non ha questa calibrazione. Prima di scriverla serve sapere com'è fatta, e la
cattura lo dice. Questa è la mappa delle fasi, con gli intervalli di record, cosa
fa ciascuna e la funzione brcmsmac corrispondente.

La calibrazione è **`wlc_phy_a4()`** (`brcm80211/brcmsmac/phy/phy_n.c:25108`), e
gira **una volta per init**: il marcatore del suo ingresso è la scrittura della
tabella scalare, e nella cattura da 70796 record `TBL.WR id=0x20 off=0 len=64`
compare esattamente due volte, #10966 e #45690, una per init. Dentro, per ogni
core, chiama `wlc_phy_papd_cal_setup_nphy()`, poi `wlc_phy_a3_nphy()` — la
ricerca dell'indice di gain, che è il loop guidato dalle letture — poi
`wlc_phy_papd_cal_cleanup_nphy()`.

Regione del primo init: **#10962 - #14092**, ~3100 record.

## Le fasi

| record | cosa | dove sta in brcmsmac |
|---|---|---|
| #10962-10965 | ingresso: `0x1e7` and, array di workaround, `0x8f`/`0xa5` or | `wlc_phy_a4`, stay-in-carriersearch e txpwrctrl off |
| #10966-11225 | tabella scalare su 32 e 34, 64 valori per core | `wlc_phy_a4`, già portata da `patches/b43/0004` |
| #11226-11228 | RD `0x01`, MOD `0x01` bit 15 | `wlc_phy_a4`, salvataggio dello spur |
| #11229-11484 | epsilon core 0 (tabella 31): **64 scritture singole** a zero | idem, già in `0004` |
| #11485-11740 | epsilon core 1 (tabella 33), stessa forma | idem, già in `0004` |
| #11741-11755 | `0x186`-`0x194`: i **coefficienti del filtro digitale TX**, riga 3 | `wlc_phy_ipa_restore_tx_digi_filts_nphy` |
| #11756-11837 | override RF, save/mod AFE `0xa6 0x8f 0xa7 0xa5`, `TXRXCOUPLE_2G` del radio | `wlc_phy_papd_cal_setup_nphy`, core 0 |
| #11838-12159 | `TBL.WR id=0x11` (SAMPLEPLAY), 160 word: il tono, 4000 kHz ampiezza 181 | `wlc_phy_tx_tone_nphy` chiamata da `papd_cal_setup` |
| #12160-~12788 | **loop del core 0**: per ogni passo di gain, imposta, suona i campioni, rilegge 40+ volte, calcola, scrive epsilon | `wlc_phy_a3_nphy` poi `wlc_phy_a2_nphy` |
| #12789-12791 | ripristino di `0x17d`/`0x19d` a `0xaa` | `wlc_phy_papd_cal_cleanup_nphy`, core 0 |
| ~#12800-13273 | setup del core 1: stessa sequenza col core scambiato, tono a #12952 | `wlc_phy_papd_cal_setup_nphy`, core 1 |
| #13274-~13756 | **loop del core 1**, stessa forma | idem |
| #13757-13759 | ripristino, core 1 | `wlc_phy_papd_cal_cleanup_nphy` |
| #13842-13857 | **offset epsilon**: `0x298`/`0x29c` = `0xf400`, poi `0x297`/`0x29b` e `0x2a3`/`0x2a4` | coda di `wlc_phy_a4` |
| #13858 | `0x01` riscritto col valore salvato | idem |
| #13859-13918 | filtri digitali TX rimessi a quelli dell'init | `wlc_phy_ipa_set_tx_digi_filts_nphy` |
| #13921-14092 | tabelle 26/27 riscritte con gain e potenza aggiornati | `wlc_phy_txpwr_index_nphy` |

Il core 0 e il core 1 si distinguono senza ambiguità: `papd_cal_setup` scrive
`TXRXCOUPLE_2G_PWRUP`/`ATTEN` a `0xc`/`0xf0` sul core in calibrazione e a
`0x0`/`0xff` sull'altro, quindi #11834-11837 (`0x17e`/`0x17d` accesi) è il core 0
e #12948-12951 (`0x19e`/`0x19d` accesi) è il core 1.

I confini con la tilde sono quelli fra la fine di `a3_nphy` e l'inizio del
cleanup: le due non hanno un'op che le separi in modo univoco, e non è servito
trovarla.

## Cosa NON è la cal

**#14093-15920 non è un secondo giro di `wlc_phy_a4`.** Ricomincia con lo stesso
prologo (`0x1e7`, array, `0x8f`/`0xa5`), ma la tabella scalare non c'è, e `a4` la
scrive sempre.
Quella regione legge la tabella 15 (IQLOCAL) 13 volte e la scrive 7, tocca 26 e
27, e suona un tono a **2000 kHz ampiezza 181** (#15508, periodo 10 campioni).
**Non è attribuita**: né ad `a4` né a un'altra funzione precisa di brcmsmac.

## Una scrittura in più che non cambia nulla

Il blob scrive `0x195`-`0x1a3` con la riga 1 **due volte**: la prima nel giro sui
tre tipi, la seconda subito dopo `0x2c5`-`0x2d3`. I 15 valori della seconda sono
**identici** alla prima, quindi lo stato della tabella è lo stesso e la
differenza col port sta solo nel numero di op. Lo fa in due punti indipendenti
della cattura, #334-348 all'init e #13904-13918 in coda alla cal, quindi non è un
artefatto della cattura.

b43 la stessa riscrittura ce l'ha, gateata su phy rev 17 (`phy_n.c:4938`, con il
commento "Verified with BCM43131 and BCM43217"), dove è altrettanto idempotente.
Sul rev 8 non serve e non va aggiunta: la finestra `txdigi-filts` la riporta come
divergenza nota, non come buco.

## Cosa dice questa mappa

**Le prime tre fasi sono già fatte.** Scalare ed epsilon sono `patches/b43/0004`.
Non è una coincidenza: erano la parte senza matematica, cioè l'unica che si
poteva portare guardando solo i valori.

**Il cuore sono `a3_nphy` e `a2_nphy`, e sono due cose diverse.** Fra #12160 e
#13756, per core, il driver alterna "imposta il gain, suona i campioni, rileggi 40
volte, calcola, scrivi l'epsilon". Il lavoro è diviso: `wlc_phy_a3_nphy` (147
righe) è la ricerca dell'indice di gain e **legge** la tabella epsilon in un loop
di 20 passi; `wlc_phy_a2_nphy` (279 righe), chiamata subito dopo per lo stesso
core, **scrive** la tabella epsilon via `set_bbmult`. `a2` non era nemmeno
nominata qui, e non per distrazione: `cfuncs.py` non la vedeva, quindi non
compariva né nell'xref né nei conteggi (vedi `docs/todo-nphy.md` punto 5).

Le decisioni dipendono da cosa misura, quindi il codice non si verifica
confrontando scritture: si verifica solo se le letture gli arrivano giuste. I
piani di lettura della cattura servono esattamente a questo, ed è il motivo per
cui esistono.

**`0x186`-`0x194` non è il tono.** Sono `B43_NPHY_TXF_20CO_S*`, i coefficienti
del filtro digitale TX a 20 MHz, e i 15 valori catturati sono la riga 3 di
`tbl_tx_filter_coef_rev4` (`tables_nphy.c:3126`), la stessa di
`NPHY_IPA_REV4_txdigi_filtcoeffs[3]` in brcmsmac. La cal li mette per la propria
durata (`restore_tx_digi_filts`, #11741) e li rimette come all'init quando
finisce (`set_tx_digi_filts`, #13859). Per una sessione ho creduto fossero il
tono e ci ho appoggiato sopra il primo punto dell'ordine di lavoro; l'ancora
sbagliata in `phase_compare.py` (`val=0x100`, che nella cattura non esiste) era
la conseguenza.

**Il tono vero è la tabella 17**, e b43 ha già `b43_nphy_tx_tone()` e
`b43_nphy_run_samples()`. Quel pezzo però era rotto: vedi sotto.

## Ordine di lavoro proposto

1. **il setup di `papd_cal_setup`**, #11756-11837: override RF, save/mod AFE e i
   due `TXRXCOUPLE_2G` per core. Sono solo scritture, quindi verificabile per
   intero e senza matematica nuova. La finestra `papd-calsetup` di
   `phase_compare.py` è già lì e aspetta.
2. **`restore`/`set` dei filtri digitali** attorno alla cal: 15 op più 45, la
   tabella c'è già. Non si può portare da solo — lasciare acceso fuori dalla cal
   il filtro della cal è peggio che non toccarlo — quindi va insieme al punto 1.
3. **un solo passo del loop del core 0**, con i piani di lettura attivi. Se un
   passo torna, il resto è iterazione.
4. **la matematica di `a3_nphy` e `a2_nphy`**, ed è l'ultima perché è l'unica
   parte che non si può verificare a pezzi.

## Cosa è già portato, dopo aver letto la mappa

### L'offset epsilon

Leggendo la coda di `wlc_phy_a4` è venuto fuori un pezzo **completo e
verificabile** che non richiede la calibrazione.

b43 scrive `nphy->papd_epsilon_offset[]` nei registri EPS table adjust
(`0x298`/`0x29c`) dentro il ramo IPA di `b43_phy_initn`, ma non lo calcola mai:
scrive zero. brcmsmac lo calcola in fondo alla cal:

    offset = -60 + 27 + eps_offset - (padgain_delta[pad_gain] + 1) / 2

con `eps_offset = -1` su questo radio in 2.4 GHz. Il valore catturato è `0xf400`
con maschera `0xff80` (#13842 e #13847 in coda alla cal, e lo stesso valore
all'init in #286 e #288), cioè **-24** nel campo a 9 bit segnato, da cui
`delta[i] = -21`, che nella tabella dei valori rev7 è l'**indice 15**.

`patches/b43/0009` valuta la formula — la tabella ce l'ha già `0002` — con
l'indice come costante presa dalla cattura. Il port ora scrive `0xf400`, identico
al vendore, dove prima scriveva `0`: 24 dB di differenza sulla predistorsione.
Quando arriverà la ricerca del gain (punto 3 qui sopra), l'indice arriva da lei e
la costante sparisce.

### La tabella dei campioni

Il tono è lo stimolo di ogni cal che suona campioni, e in b43 non era un tono.
`b43_nphy_gen_load_samples()` calcolava il passo di fase come
`(((freq * 36) / bw) << 16) / 100` dentro una `u16`, mentre `cordic_calc_iq()`
vuole gradi interi e scala da sé: il `<< 16` è di troppo e rende il risultato un
multiplo di 65536 per **tutte** le frequenze che il driver chiede (2500 e 5000
dalla cal TX IQ/LO, 4000 dall'idle TSSI e dalla cal RX IQ rev 2), quindi il passo
troncava a zero e i 160 campioni uscivano tutti uguali. In più
`b43_nphy_load_samples()` scriveva `samples[i].i & 0x3FF << 10`, dove `<<` lega
più forte di `&`, buttando via la componente in fase.

`patches/b43/0010` chiude i due. Contro la cattura, sul tono a 2500 kHz ampiezza
250 della cal TX IQ/LO (#8638):

| | parole sbagliate su 160 |
|---|---|
| mainline | 160, tutte zero |
| solo la maschera corretta | 140, `0x3e800` costante |
| solo il passo di fase corretto | 120, componente in fase persa |
| `0010` | **0** |

Nessuna delle due metà da sola avvicina, ed è la ragione per cui è una patch e
non due.
Le finestre `sampleplay-tssi` e `sampleplay-iqlo` di `phase_compare.py` reggono
il risultato: 322/322 entrambe con la patch, 2/322 la seconda senza.

## Perche' il resto non si porta a pezzi

Il cuore e' `a3_nphy` piu' `a2_nphy` per due core, e non si spezza in parti
verificabili singolarmente: o c'e' il passo di cal completo o non si verifica niente.
E `papd_cal_setup`, che nella scaletta e' il punto 1 perche' e' tutto scritture, sono
250 righe — verificabile non vuol dire piccolo, e finche' la ricerca di gain non c'e'
non ha un chiamante, quindi come patch a se' sarebbe codice morto.

L'offset epsilon e la tabella dei campioni erano invece calcoli isolati con valori
catturati da confrontare, ed e' per quello che si sono chiusi.
