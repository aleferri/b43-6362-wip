# CLAUDE.md

Cosa serve sapere prima di toccare qualcosa. Corto di proposito: il dettaglio sta
in `docs/INDEX.md`, qui c'è solo ciò che serve per non ripetere errori già fatti.

## Il progetto

Portare in b43 il supporto **BCM6362 / N-PHY rev 8 / radio 2057 rev 8**, guidati
da una cattura MMIO del driver proprietario `wl 6.30.102.7`. Sette patch già
merged in mainline (`docs/upstream-status.md`), quattordici in `patches/b43/`. **Niente
ha mai girato su hardware**: tutto è verificato riproducendo la cattura in un
harness che compila il vero `phy_n.c`.

## Setup, ogni volta

```sh
sh scripts/fetch-upstream-state.sh ~/src/linux      # sparse, ~60 MB, sha 848acc8ffe1b
cd ~/src/linux && for p in .../patches/b43/0*.patch; do git apply "$p"; done
cd test && make KDIR=~/src/linux && make KDIR=~/src/linux warncheck
./phase_compare.py --vendor ../router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded
```

Le patch **vanno applicate in ordine**. La catena di dipendenze, misurata con
`git apply` sull'albero pulito: 0004 dipende da **0002** (contesto in
`tables_nphy.c`), 0009 da 0004, 0012 da **0009**. 0003 non serve a nessuna delle
tre.

## Strumenti

| cosa | dove |
|---|---|
| harness, flow `init initpor initcal full chanset rfkill txpower` | `test/nphy_trace` |
| confronto per fase, 14 finestre | `test/phase_compare.py` |
| confronto globale + per regione | `test/phase_compare.py --global-run DA A --flow F` |
| copertura per insiemi di celle | `test/coverage.py` |
| normalizzazione, `Op` con `.ep` | `test/compare.py` |
| buchi di dispatch, xref brcmsmac, gating delle patch | `reverse-tools/*.py` |

## Stato

`14 finestre: 0 da guardare, 5 divergenze note, 2 fasi non ancora portate`

Run intera: flow `full` contro `opinit-ch1-ch6-bw20.decoded` #132-26100, cioe'
il suo primo `up` a canale 1. **5398 op su 22951, 24%**. Per regione:

| regione | record | appaiate |
|---|---|---|
| init vero e proprio | #132-10961 | 36% |
| cal PAPD (`a4`) | #10962-14092 | 26% |
| cal RX IQ, ingresso | #14093-15920 | 5% |
| cal RX IQ, sweep di gain | #15921-22246 | **9%**, 5812 op, la più grande |
| seconda cal RSSI | #22247-23771 | **0%** |
| coda | #23772-26100 | 29% |

## La struttura della cattura

`wlc_phy_a4` è la cal PAPD e gira **una volta per init**; `a3_nphy` (147 righe)
cerca l'indice di gain e **legge** la tabella epsilon, `a2_nphy` (279) la
**scrive**. Mappa completa in `docs/papd-cal-map.md`, flusso affiancato dei due
driver in `docs/init-flow.md`.

`do_full_init` (b43) == `phy_init_por` (brcmsmac): dietro ci stanno il download
delle tabelle statiche e rcal/rccal.

**Le catture sono due e servono a cose diverse.** `opinit-ch1-ch6-bw20.decoded`
(70796 record) e' il riferimento di tutto quello che sta qui sopra: e' un init **a
caldo** e non contiene il download statico — l'apertura della tabella 10 non
compare in nessuno dei suoi due init — e per questo il flow `init` fa due init e
traccia solo il secondo. `full-init-ch1-bw20.decoded` (81397 record) e' un init **a
freddo**, ed e' la sola che contenga le tabelle di init: contro quella, col flow
`initpor`, il port **le riproduce op per op** — 1424/1424 sulla tabella 13 e
806/806 sulla 18, finestre `static-tables` e `static-tables-2`, le uniche due che
dichiarano `capture=`. Ha un buco da 65285 record oltre #32769, quindi solo
#2-32769 e' confrontabile posizionalmente.

I numeri di record qui e nei documenti sono di `opinit-*` quando non e' detto
altrimenti: gli intervalli esistono in entrambi i file e **non si
autoidentificano**.

In mainline la cal periodica non parte: `perical = 2`, e il ramo che ne consegue in
`b43_phy_initn` è un `;/* TODO */`. `0012` ci mette l'init delle tabelle PAPD e
`0014` la sequenza del vendore — TX IQ/LO, PAPD, RX IQ, coefficienti di potenza,
RSSI — gateata su phy rev 8 e radio rev 8, e dipende da `0012`. Misurato sul flow
`init`: seconda cal RSSI da **0% a 46%**, coda da 8% a 32%, totale da 4434 a 5949
op su 22951. Il flow `full` non si muove, perché mette `perical = 0` e prende
l'altro ramo. Resta fuori il cuore, `a2`/`a3`, e con lui la cal PAPD vera:
`b43_nphy_papd_cal()` è il segnaposto di `0012`.

## Regole

- **Le misure stanno negli strumenti**, non in script usa-e-getta: vanno rifatte.
- **La doc può essere stale.** Ne ho corretta parecchia; non fidarsi, riverificare.
- I riferimenti `file:riga` vanno controllati sul tree **pristine**, non su quello
  con le patch applicate.
- **Delimitare la fase** prima di contare, con un'op che la chiuda (es. il primo
  `CHANSPEC` per l'init del radio), non a occhio su un intervallo di record.
- **`Op.ep` è l'unico modo** di sapere da che record viene un'op: `load_vendor`
  scarta bookkeeping e ombre, quindi indice ≠ numero di record.
- Ogni patch dietro un gate di revisione, verificato con `check_patch_gating.py`.
  Eccezione dichiarata: `0010`, fix di mainline per ogni N-PHY.
- Niente commenti "prima era così": quelli vanno nel messaggio di commit.
- **Provenienza in trailer**: `Link:` per ogni URL, uno per riga — e' il nome che
  il kernel conosce, non `Reference:`/`Capture:`/`Tool:`. Il sorgente del kernel si
  cita su **git.kernel.org** pinnato allo sha: `...phy_n.c?id=848acc8ffe1b#n23018`,
  o la riga scivola. La cattura ha un `Link:` al file e, **nel corpo**, l'intervallo
  di record e la prima op con la spaziatura del file, che si ritrova con `grep -F`:
  4,4 MB e 70796 righe, GitHub non la rende e un'ancora di riga non porta da nessuna
  parte. `From:` e `Signed-off-by` vanno **entrambi** su
  `alessio.ferri@mythread.it`, che e' l'indirizzo da cui le patch partono e quello
  dei sette commit gia' merged; il gmail non si usa. Corpo a 75 colonne.
- **SALAME** in grassetto sulle ipotesi non verificate sul comportamento del
  codice, **TONNO** sulle risposte infondate.

## Trappole in cui sono già caduto

1. Costruito l'harness contro un tree **senza le patch** e letto i risultati come
   regressioni. Controllare `git -C ~/src/linux diff --stat` prima di credere a un
   numero. (Idea aperta: farlo fallire in `make`.)
2. Citato numeri di riga presi dal tree patchato: `phy_n.c:4021` invece di `3950`.
3. Contata una fase su una finestra a occhio che ne mescolava tre, e concluso il
   falso ("70 registri sottoinsieme dei 412" — 32 su 70 avevano valore diverso).
4. Ricostruito a mano la corrispondenza op→record: deriva fino a 230 op, e la
   seconda cal RSSI risultava al 5% invece di 0%.
5. Attribuito al "core non compilato" op che erano in codice compilato e non
   chiamato (`b43_software_rfkill` era uno stub vuoto in `wrap.c`).
6. Creduto a un'ancora di `phase_compare.py` mai trovata (`0x186 val=0x100`, che
   nella cattura non esiste): una finestra `pending` con ancora impossibile non
   falisce mai e non dice niente.
7. Scritto "serve una lettura su hardware" quando il valore era nella cattura.
8. I **bit di esecuzione** si perdono a ogni merge fatto applicando il diff
   (`git apply` senza `--index` non li mette nell'indice). Sette volte finora:
   `sh scripts/check-exec-bits.sh`.

## Difetti trovati in mainline, per ricordare cosa cercare

`patches/mainline/` sono i due indipendenti da questo hardware, da mandare per primi
e come **due `[PATCH]` separate in due thread**, non come serie: non dipendono l'una
dall'altra, e legarle vuol dire che una review lunga su una blocca il merge
dell'altra. Con la prima sola, `sampleplay-tssi` e `sampleplay-iqlo` fanno 322/322.


Refusi di trascrizione da brcmsmac e di precedenza C, non buchi di feature:
`0005` registro sbagliato, `0010` `<<` che lega più forte di `&` più un passo di
fase troncato in una `u16`, `0011` dieci campi persi con la tabella "solo 2 GHz",
`0012` tabelle inizializzate nel posto sbagliato. Vale sempre la pena confrontare
il **gate** oltre al corpo: b43 ha `phy->rev != 5` dove brcmsmac ha
`radiorev != 5` (`docs/todo-nphy.md` 3d bis).

## L'init del radio, chiuso

Il record del blob e' `{u16 address; u16 init; u8 do_init; u8 pad}`, sei byte, e **39
voci su 412 hanno il flag**. b43 aveva ereditato indirizzo e valore (412 su 412
identici) e perso la colonna. La cattura combacia col flag esattamente: 39 su 39, e i
4 registri in piu' vengono da altro codice. Lo stub da 54 che impianta il radio e' il
set `do_init` di **brcmsmac**, che e' piu' vecchio. `patches/b43/0013`, non provata su
hardware. Vedi `docs/gap-inventory.md` 4h.

## Due blob, e quale usare

`wlDSL-3580_EU.o_save` e' wl 6.30.102.7 (DSL-3580L, da cui viene la cattura),
`wlD6220.o_save` e' wl 7.14.89.14. Tutti e 33 i simboli **dati** del 2057 rev5-8 hanno
size identica fra i due, `regs_2057_rev8` e' identica byte per byte. Differiscono tre
funzioni `wlc_phy_workarounds_nphy_gainctrl_2057_rev5/6/7`, e la `rev6` e' il corpo che
manca allo stub di b43: per quella **si legge il 6.30**, che e' il blob della cattura.
Il blob da' i nomi veri di brcmsmac: `a3` = `wlc_phy_papd_cal_gctrl_nphy` (2444 byte,
147 righe, il rapporto torna). `wlc_phy_papd_cal_nphy` (6088) e' `a2` **o** `a4`: hanno
279 e 276 righe, la size non le distingue, e `a2` per size non si trova. Vedi `docs/blob-inventory.md`.

## Prossimo passo

1. **`b43_nphy_rev3_cal_rx_iq()`**, che e' `return -1;` per ogni N-PHY rev 3+.
   Dietro ci stanno le due regioni prima non attribuite, **7510 op** fra
   #14093 e #22246, un terzo della finestra: sono la cal RX IQ, e si riconosce
   dai sette toni da 160 word (#16319, #17130, #17542, #18588, #19399, #20210,
   #20624), dagli upload di gain su 26/27 a `off=0x40 len=84` fra un tono e
   l'altro, e dalle coppie read/write su IQLOCAL cella per cella. In piu'
   `b43_nphy_cal_rx_iq()` degrada `type` da 2 a 0 su rev >= 7, e siccome lo stub
   torna -1 non parte nemmeno `b43_nphy_save_cal()`, che nella sequenza di `0014`
   sta dietro quel controllo. **Non** sono "scritture pure verificabili per
   intero" come diceva questa voce: gli upload li decide la cal.
2. I **piani di lettura per chiamata di cal**: con `0014` il port fa la cal RSSI
   due volte per init, i piani ne coprono una sola, e la finestra `rssi-cal`
   scende da 11/16 a 1/16 con coefficienti a zero. Finché non è sistemato, `0014`
   non è verificata e il resto della cal non si misura.
3. Init del radio: 412 voci contro 43 del vendore, dentro il 36% dell'init.
