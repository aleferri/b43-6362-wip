# patches/mainline

Difetti di mainline indipendenti dal BCM6362 e da questo lavoro. Valgono una
submission a sé, e prima del resto, perché sono corti, non gateati su nessuna
revisione e sbagliati in modo dimostrabile senza avere l'hardware davanti.

**Sono due patch separate, non una serie**, e vanno inviate come due `[PATCH]` in
due thread. Non dipendono l'una dall'altra e toccano funzioni diverse: legarle in
una serie significa che una review lunga su una tiene fermo il merge dell'altra, e
non c'è nessuna ragione tecnica per pagare quel prezzo.

| file | cosa | righe |
|---|---|---|
| `b43-fix-two-defects-in-the-n-phy-sample-table-logic` | `<<` lega più forte di `&`, e il passo di fase in una `u16` dopo un `<< 16` di troppo tronca a zero per **tutte** le frequenze che il driver chiede | 6 |
| `b43-test-the-radio-rev-for-the-n-phy-tssia-setup` | `phy->rev != 5` dentro un ramo `phy->rev >= 7`: guard morto, andava sul radio | 12 |

Ognuna applica **da sola** su mainline pulito, e si dimostra senza hardware: la
prima per precedenza C e aritmetica, la seconda perché quel guard non può essere
falso.

La prima porta due difetti insieme, e non per pigrizia: nessuna delle due metà, da
sola, produce una tabella dei campioni giusta — 140 parole sbagliate su 160 con la
sola maschera corretta, 120 col solo passo di fase. Sono due righe di una stessa
logica rotta, e separarle darebbe due patch che nessuno può verificare.

Con la prima applicata, le finestre `sampleplay-tssi` e `sampleplay-iqlo` di
`test/phase_compare.py` fanno **322/322** entrambe: le due tabelle dei campioni
diventano identiche alla cattura, parola per parola, senza niente della serie in
`patches/b43/`. Per questo `patches/b43/0010` esiste ancora e porta le stesse due
modifiche — quella serie si applica come un blocco e ne ha bisogno. Quando la patch
va in mainline, `b43/0010` esce.

La seconda non è in `patches/b43/`: cambia cosa programmano un radio 2057 rev 5 e
un phy rev 7 in 5 GHz, e non abbiamo né l'uno né l'altro. Il razionale sta in
`docs/todo-nphy.md` 3d bis.

Nessuna delle due ha girato su hardware.
