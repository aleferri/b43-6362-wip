# La serie resta un file solo, e il confine sta nella storia

Le dodici di `patches/mainline/` sono file separati perché partono presto: sono
difetti di mainline, corti, indipendenti da questo hardware, e vanno in dodici thread.

Tutto il resto no. Il supporto al BCM6362 non parte finché la SPROM non ha una strada
upstream (`docs/upstreaming.md`), quindi tenere trentasei file per una serie che si
spedisce fra mesi costa e non rende: si desincronizzano. **È già successo.**

## Cosa è già costato

I ventisei file per patch sono esistiti, fino a `394c9e2`. Sono ancora in storia e si
estraggono, ma **non sono usabili**: applicati su `848acc8ffe1b` più le dodici mainline
lasciano l'albero a **718 righe e 37 hunk** dal rollup, perché `rollup.diff` è stato
rigenerato tre volte dopo che quei file erano stati cancellati e le modifiche di quei
giri stanno solo nel rollup. I file c'erano e mentivano, che è peggio del non averli.

## La regola, che costa niente

**Un commit per patch, con la sua voce di `MESSAGES.md` nello stesso commit.**

Il confine per patch sta lì, non in una directory, e `scripts/patch-from-commit.sh` lo
tira fuori quando serve: applica il rollup di `<commit>^` e quello di `<commit>` a due
alberi identici e diffa i risultati.

```sh
sh scripts/patch-from-commit.sh 15599ec ~/src/linux > 0031.patch
```

Verificato: sui nove commit da `0027` a `0036` lo script dà esattamente le dieci patch,
e applicate in sequenza sopra il rollup di partenza danno un albero **identico byte per
byte** a quello del rollup di arrivo. `0033` e `0034` stavano in un commit solo e vanno
divise a mano — un commit che porta due patch è l'unico modo di rompere la regola.

Da `96a5a4c` in poi la storia rispetta la regola. Prima no: `progress`, `advance`,
`reorg` sono commit grossi, quindi per `0001`-`0026` il confine **è perso** e nessuno
strumento lo recupera.

## Quando si dividerà per davvero

`SERIES.md` ha il piano: otto serie per competenza, con l'ordine e i sei punti dove due
serie si contendono la stessa funzione.

Per le patch dal `0027` in poi la divisione è un comando. Per le ventisei sono **37
giudizi** su altrettanti hunk di deriva, e nessun controllo automatico li valida: il
confronto dell'albero finale passa anche con le modifiche attribuite alla patch
sbagliata. Se quel lavoro non vale la pena, l'alternativa legittima è mandarle come una
serie sola divisa per competenza e non per scoperta, che è comunque quello che serve a
chi le rivede.
