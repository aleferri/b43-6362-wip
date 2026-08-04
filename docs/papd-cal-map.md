# La calibrazione PAPD: mappa della cattura

b43 non ha questa calibrazione. Prima di scriverla serve sapere com'è fatta, e la
cattura lo dice. Questa è la mappa delle fasi, con gli intervalli di record, cosa
fa ciascuna e la funzione brcmsmac corrispondente.

Regione: **#10962 - #15920** del primo init, ~5000 record.

## Le fasi

| record | cosa | dove sta in brcmsmac |
|---|---|---|
| #10962-10965 | ingresso: `0x1e7` and, array di workaround, `0x8f`/`0xa5` or | inizio di `wlc_phy_a3_nphy` |
| #10966-11226 | tabella scalare su 32 e 34, 64 valori per core | `wlc_phy_a3_nphy`, già portata da `patches/b43/0004` |
| #11228-11484 | epsilon core 0 (tabella 31): **64 scritture singole** a zero | idem, già in `0004` |
| #11485-11740 | epsilon core 1 (tabella 33), stessa forma | idem, già in `0004` |
| #11741-11755 | `0x186`-`0x194`, 15 registri: il tono di test | `wlc_phy_tx_tone_nphy` |
| #11756-11837 | override RF (`0x342/0x343/0x346/0x347`, `0x0e7/0x0ec`, `0x07a-0x07f`) e il blocco TSSI in RMW | `wlc_phy_a4` |
| #11838-12159 | `TBL.WR id=0x11` (SAMPLEPLAY): ~320 record di dati, il buffer dei campioni | `wlc_phy_loadsampletable_nphy` |
| #12160-12952 | **loop del core 0**: per ogni passo di gain, imposta, suona i campioni, rilegge 40+ volte, calcola, scrive epsilon | `wlc_phy_ipa_set_bbmult_nphy` |
| #13274-13952 | **loop del core 1**, stessa forma | idem |
| #13921-14092 | tabelle 26/27 riscritte (gain e power aggiornati) | `wlc_phy_txpwr_papd_cal_nphy` |
| #14093-15508 | rounds di raffinamento: `0x1e7`, array, `0x8f`/`0xa5`, riletture di 26/27, scritture su 7 | `wlc_phy_a4` iterato |
| #15830-15920 | chiusura: `0x129-0x12b`, ultima riscrittura di 26 | fine di `wlc_phy_a3_nphy` |

## Cosa dice questa mappa

Tre cose che cambiano il piano di lavoro.

**Le prime tre fasi sono già fatte.** Scalare ed epsilon sono `patches/b43/0004`.
Non è una coincidenza: erano la parte senza matematica, cioè l'unica che si
poteva portare guardando solo i valori.

**Il cuore sono due loop guidati dalle letture.** Fra #12160 e #13952 il driver
alterna "imposta il gain, suona i campioni, rileggi 40 volte, calcola, scrivi
l'epsilon" per ogni passo di gain e per ogni core. Le decisioni dipendono da cosa
misura, quindi il codice non si verifica confrontando scritture: si verifica solo
se le letture gli arrivano giuste. I piani di lettura della cattura servono
esattamente a questo, ed è il motivo per cui esistono.

**Il tono e il buffer dei campioni vengono prima.** `0x186-0x194` e la tabella 17
(SAMPLEPLAY) sono il segnale di test: senza quelli il resto non ha input. b43 ha
già `b43_nphy_tx_tone()` e `b43_nphy_run_samples()`, quindi quella parte è
riuso, non scrittura da zero.

## Ordine di lavoro proposto

1. **tono e sample play**: verificare che `b43_nphy_tx_tone` produca `0x186-0x194`
   e la tabella 17 come nella cattura. È una finestra confrontabile
   posizionalmente e non richiede matematica nuova.
2. **il setup di `wlc_phy_a4`**: gli override RF e il blocco TSSI, #11756-11837.
   Anche questo è scritture, verificabile.
3. **un solo passo del loop del core 0**: la sequenza più corta fra #12160 e
   #12952, con i piani di lettura attivi. Se un passo torna, il resto è
   iterazione.
4. **la matematica di `ipa_set_bbmult`**: 722 righe in brcmsmac, ed è l'ultima
   perché è l'unica parte che non si può verificare a pezzi.

## Cosa è già portato, dopo aver letto la mappa

Leggendo `wlc_phy_a4` per intero è venuto fuori un pezzo **completo e
verificabile** che non richiede la calibrazione: l'**offset epsilon**.

b43 scrive `nphy->papd_epsilon_offset[]` nei registri EPS table adjust
(`0x298`/`0x29c`) dentro il ramo IPA di `b43_phy_initn`, ma non lo calcola mai:
scrive zero. brcmsmac lo calcola in fondo alla cal:

    offset = -60 + 27 + eps_offset - (padgain_delta[pad_gain] + 1) / 2

con `eps_offset = -1` su questo radio in 2.4 GHz. Il valore catturato è `0xf400`
con maschera `0xff80`, cioè **-24** nel campo a 9 bit segnato, da cui
`delta[i] = -21`, che nella tabella dei valori rev7 è l'**indice 15**.

`patches/b43/0009` valuta la formula — la tabella ce l'ha già `0002` — con
l'indice come costante presa dalla cattura. Il port ora scrive `0xf400`, identico
al vendore, dove prima scriveva `0`: 24 dB di differenza sulla predistorsione.
Quando arriverà la ricerca del gain (punto 3 qui sopra), l'indice arriva da lei e
la costante sparisce.

## Perché non ho portato il resto in questa sessione

Il cuore restano i due loop guidati dalle letture e le 722 righe di
`ipa_set_bbmult`. Quelli non si spezzano in pezzi verificabili singolarmente: o
c'è il passo di cal completo, o non si verifica niente. L'offset epsilon invece
era un calcolo isolato con un valore catturato da confrontare, e per quello si è
potuto chiudere subito.

La mappa qui sopra è il lavoro che serviva comunque prima di scrivere una riga.
