# patches/b43 — come dividere le trentasei

Questo è un **piano per quando si spedirà**, non qualcosa da fare ora: il rollup resta
un file solo finché la SPROM non ha una strada upstream, e il perché sta in `SPLIT.md`.

Trentasei patch in un thread non si leggono. `MESSAGES.md` le tiene in ordine di
scoperta, che è l'ordine in cui sono state trovate e non l'ordine in cui hanno senso
per chi le deve guardare. Questa è la divisione per competenza: **otto serie**, ognuna
di una cosa sola, ognuna mandabile per conto suo.

Il criterio è chi la deve rivedere. Una serie di sole tabelle si controlla contro il
blob e la SPROM; una di calibrazione vuole qualcuno che sappia cosa fa quella
calibrazione. Mescolarle costringe la stessa persona a fare entrambe le cose.

## A — dati del radio 2057 rev 8 (5)

`0013` `0002` `0005` `0011` `0003`

Tabelle e valori di registro, nessun algoritmo. Si rivede contro il blob OEM e la
SPROM, con `reverse-tools/blob_tables.py`, e non richiede di sapere niente delle
calibrazioni. È la serie da mandare per prima: tutto il resto ne dipende per i dati e
niente ne dipende per il codice.

## B — workaround dell'init e soglie RX (6)

`0001` `0008` `0030` `0031` `0032` `0007`

Quello che l'init programma una volta e non tocca più: gain control RX, soglie di
carrier sense, la sequenza RF, lo spur workaround che era uno stub. Tutto dentro
`b43_nphy_workarounds_rev7plus()` e vicini.

## C — sample play e filtri di trasmissione (6)

`0010` `0022` `0027` `0028` `0036` `0026`

Il tono che ogni calibrazione usa come stimolo: generazione della tabella dei
campioni, la modalità del DAC test, gli override di banda del filtro e le righe dei
filtri digitali. `0010` è anche una delle dodici di `patches/mainline/` e qui c'è la
parte che dipende da questo hardware.

## D — controllo di potenza TX e TSSI (5)

`0033` `0034` `0035` `0021` `0025`

Il TSSI setup, l'ordine fra abilitazione e indici, il ritorno dell'indice di potenza.
`0034` è l'unica della serie che va contro il riferimento: la cattura è l'unica voce.

## E — calibrazione PAPD (6)

`0004` `0009` `0012` `0015` `0020` `0029`

Il rivelatore di potenza: tabelle, offset epsilon, il giro del motore, la parentesi
del controllo di potenza.

## F — calibrazione RX I/Q (3)

`0016` `0018` `0023`

Passaggio del PHY alla calibrazione, sweep dei gain, misura del tono e calcolo dei
coefficienti.

## G — macchina della calibrazione periodica (4)

`0014` `0017` `0019` `0024`

L'orchestrazione: chi lancia la calibrazione, se piena o parziale, il gain
d'ingresso, la coda. Non calibra niente lei, decide chi calibra.

## H — rumore di fondo (1)

`0006`

Sta da sola perché non dipende da niente e niente dipende da lei.

## L'ordine, e perché non è arbitrario

    A  →  B  →  C  →  D  →  G  →  E  →  F        H quando si vuole

A prima perché le tabelle servono a tutti. C e D prima delle calibrazioni perché il
tono e il controllo di potenza sono ciò che le calibrazioni usano. G prima di E e F
perché è chi le chiama.

## I punti di conflitto, misurati

Sei funzioni sono toccate da più di una serie. Non sono dipendenze logiche — ogni
patch sta in piedi da sola — ma sono i posti dove due serie si contendono le stesse
righe di contesto, quindi vanno applicate nell'ordine sopra o rigenerate:

| funzione | serie |
|---|---|
| `b43_nphy_txpwr_index` | C D E F |
| `b43_nphy_tx_power_fix` | C E F |
| `b43_phy_initn` | E F G |
| `b43_nphy_op_prepare_structs` | D E |
| `b43_nphy_iq_cal_gain_params` | F G |
| `b43_nphy_restore_cal` | F G |

`b43_nphy_txpwr_index` è il punto peggiore, quattro serie su una funzione. Se una
delle quattro va in review lunga, le altre tre non applicano più senza rigenerare.
Vale considerare di mandare la sola `0021` prima di tutto il resto, così il conflitto
si risolve una volta.

## Cosa non è verificato, e perché

Che le otto serie applichino una dopo l'altra come otto file separati. Questa
divisione è sui **soggetti**, non su hunk tagliati, e provando a tagliarla non regge:
dei 40 hunk di `phy_n.c` nel rollup solo **9** si attribuiscono a una serie sola, 24
stanno in funzioni che nessun messaggio nomina e 7 in funzioni contese. E c'è un buco
nella divisione stessa — il rollup ha hunk nella calibrazione TX I/Q LO
(`tx_cal_radio_setup_rev7`, `update_tx_cal_ladder`, `cal_tx_iq_lo`,
`tx_cal_phy_cleanup`) e nessuna delle otto serie la rivendica.

I numeri e la strada stanno in `SPLIT.md`. In breve: dal `0027` in poi la divisione è
un comando, perché il confine per patch sta in un commit; per le ventisei sono 37
giudizi che nessun controllo automatico può validare, e mandarle come una serie sola
divisa per competenza e' un'alternativa legittima.
