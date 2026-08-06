# patches/mainline

Difetti di mainline indipendenti dal BCM6362 e da questo lavoro. Valgono una
submission a sé, e prima del resto, perché sono corti, non gateati su nessuna
revisione e sbagliati in modo dimostrabile senza avere l'hardware davanti.

**Sono patch separate, non una serie**, e vanno inviate come tanti `[PATCH]` in
altrettanti thread. Non dipendono l'una dall'altra e toccano funzioni diverse:
legarle in una serie significa che una review lunga su una tiene fermo il merge
delle altre, e non c'è nessuna ragione tecnica per pagare quel prezzo.

| file | cosa | righe |
|---|---|---|
| `b43-fix-two-defects-in-the-n-phy-sample-table-logic` | `<<` lega più forte di `&`, e il passo di fase in una `u16` dopo un `<< 16` di troppo tronca a zero per **tutte** le frequenze che il driver chiede | 6 |
| `b43-test-the-radio-rev-for-the-n-phy-tssia-setup` | `phy->rev != 5` dentro un ramo `phy->rev >= 7`: guard morto, andava sul radio | 12 |
| `b43-fix-the-rounding-of-the-negative-rssi-cal-offsets` | la parentesi di `abs()` nel posto sbagliato: il `+4` finisce dentro il valore negativo invece che sul suo modulo, e ogni offset sotto -4 arrotonda verso lo zero. Lo stesso file la scrive giusta due volte | 2 |
| `b43-fix-two-rf-control-override-value-masks-on-n-phy-rev-7` | due `val_mask` di `tbl_rf_control_override_rev7_over1` non coprono il campo del proprio shift. Col campo `0x0100` il port azzera il bit 8 di `0x340`, che appartiene alla banda del filtro programmata poche op prima | 4 |
| `b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7` | `one_to_many`, caso `TX_PU`: quattro chiamate contro cinque di brcmsmac, manca `(0x1 << 2)` su override 2 | 1 |
| `b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag` | il modo del test DAC e' un `u8` testato `== 1`, b43 lo restringe a `bool` in tre punti: qualunque modo sopra 1 accende la strada sbagliata | 5 |

Le ultime due si dimostrano **a tre voci**: brcmsmac, la cattura e b43 dicono cose
diverse, e le prime due dicono la stessa. Le righe della cattura stanno nel corpo
delle patch.

`b43-program-the-fifth-tx-power-up-override` e
`b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag` sono le due qui che
`reverse-tools/check_patch_gating.py` segna `NON GATEATA`, e **è corretto**: sta in
`b43_nphy_rf_ctl_override_one_to_many()`, che gira su ogni N-PHY rev 7 e su. È la
stessa eccezione dichiarata di `b43/0010` e per la stessa ragione — un refuso di
trascrizione da brcmsmac non si mette dietro un gate di revisione, perché non è una
feature di questo hardware. Le altre quattro non toccano codice condiviso: tre sono
dati o aritmetica, una un guard.

Ognuna applica **da sola** su mainline pulito, e si dimostra senza hardware: per
precedenza C e aritmetica, perché un guard non può essere falso, o perché brcmsmac
e la cattura concordano contro b43.

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

`b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag` e' latente: nessun chiamante in
tree passa un modo diverso da 0 o 1, quindi da sola non cambia niente. Morde il
primo chiamante con un modo vero, che e' la cal RX IQ — e la misura c'e': col
`bool`, un tipo 2 costruisce le 160 word del tono su una banda di 80 o 82 invece di
20, e il port perde **476 op** su `up-ch1`. Duplicata in `b43/0022` perche' quella
serie si applica come un blocco.

Nessuna ha girato su hardware.
