# La tabella RF power offset per radio 2057 rev 8

Questione aperta su dati già merged. Non è urgente e non va chiusa a intuito:
qui ci sono le prove, da entrambi i lati, e il modo di decidere.

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

## Perché non è urgente

La tabella è codice morto: `b43_nphy_tx_pwr_ctl_init()` la recupera e poi
ritorna subito per `phy->rev >= 7` (`/* TODO: Enable this once we have gains
configured */`). Diventa viva quando quel ramo verrà abilitato, sulla strada
verso M4.

## Come si decide

Quando il ramo è attivo, si misura la potenza in uscita per indice di gain
(`reports/40-tx-power.md`) e si guarda quale delle due serie di offset predice
il misurato. Fino a quel momento `patches/b43/0002` resta una bozza: sostituire
un valore non verificato con un altro valore non verificato non è un progresso.
