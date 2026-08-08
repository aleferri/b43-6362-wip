# La tabella RF power offset per radio 2057 rev 8

**Chiusa dalla cattura: i valori in mainline sono sbagliati.** Ricalcolando dalla
cattura le 128 celle che quella tabella alimenta, i valori rev 7 le predicono
tutte e 128, quelli in tree ne predicono 5. La correzione è
`patches/b43/MESSAGES.md#0002`, e `#0003` abilita il percorso che le scrive.

Sotto resta la storia, perché il modo in cui si è chiusa è più istruttivo del
risultato: non con una misura di potenza in laboratorio, ma ricalcolando dal
codice del driver le celle che la cattura mostra scritte.

## Cosa dice il kernel oggi

`b43_ntab_rf_pwr_offset_2057_rev8_2g` (commit `21352612198c`) contiene i valori
che il driver proprietario usa per radio rev **5**:

    -109, -109, -82, -68, -58, -50, -44, -39, ...

Il commit lo dichiara e lo motiva: la tabella di gain IPA del rev 8 condivide i
24 bit bassi con quella del rev 5, e `pad_gain` viene estratto dai bit 19..23,
che stanno in quella parte condivisa.

## Cosa dice il vendore

`get_rf_pwr_offset()` in brcmsmac (`phy_n.c:14649`) — la controparte esatta del
codice b43 che consuma questa tabella — accoppia radiorev 7 e 8 alla tabella
**rev 7**, e usa la rev 5 solo per radiorev 5. Stessa scelta nel secondo sito
d'uso, `wlc_phy_a4` (`phy_n.c:25275`). I valori rev 7 sono:

    -122, -122, -95, -80, -69, -61, -54, -49, ...

Verificato che la `nphy_papd_padgain_dlt_2g_2057rev7` di brcmsmac e quella del
blob `wl 6.30.102.7` sono identiche, quindi la fonte per una patch può essere
in-tree e GPL, senza tirare in mezzo il blob.

## Cosa dicono i dati sul blob

Verificato con `reverse-tools/blob_tables.py`:

| confronto | esito |
|---|---|
| `txgain_ipa_2g_2057rev8` vs `rev5`, 24 bit bassi | **identici** su tutte le 128 entry |
| le stesse due tabelle, entry piene | tutte diverse: cambia solo il byte alto (0x40 contro 0x30) |
| `txgain_ipa_2g_2057rev8` vs `rev7`, 24 bit bassi | **diversi** |

Quindi la premessa del commit merged è vera, e la simmetria col rev 7 non c'è.

## Come stanno le cose

Sull'asse "tabella di gain IPA" il rev 8 assomiglia al rev 5. Sulla dispatch
degli offset di potenza, il vendore accoppia il rev 8 al rev 7. Le due cose non
si contraddicono di per sé: l'offset in dB per indice è una proprietà del
PA/pad, non del passo di gain, e il vendore evidentemente considera il pad del
rev 8 simile a quello del rev 7 pur usando codici di selezione diversi.

Il peso maggiore va alla scelta del vendore, perché è il codice che gira su
questo silicio. Ma è un argomento, non una misura.

## Come si è chiusa

Il consumatore della tabella è `b43_nphy_tx_gain_table_upload()`: per ogni entry
della TX gain table estrae `pad_gain = (table[i] >> 19) & 0x1f` e scrive
`rf_pwr_offset_table[pad_gain]` nella cella PAPD corrispondente, tabelle 26 e 27
a offset 576+i. Quel percorso in mainline ritorna prima del loop, ma il calcolo
è tutto lì.

La cattura mostra il vendore scrivere tutte e 256 quelle celle durante l'init, a
32 bit, con i negativi estesi in segno. Rifacendo il conto con la TX gain table
(che è verificata identica al blob) e le due candidate:

| tabella di offset | celle predette correttamente |
|---|---|
| valori in mainline, presi dal rev 5 | **5 su 128** |
| valori rev 7 | **128 su 128** |

Non serviva il laboratorio: bastava che il driver dicesse come si calcola e la
cattura dicesse cosa ne esce. L'argomento della somiglianza fra le gain table
(i 24 bit bassi identici fra rev 8 e rev 5) resta vero e resta irrilevante: la
somiglianza sta nell'indice, non nell'offset in dB che quell'indice seleziona.

Verificato anche al contrario con l'harness: abilitando il percorso senza
correggere i valori, 246 celle su 256 escono diverse dalla cattura; con la
correzione, zero.
