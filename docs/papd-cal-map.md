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
| #10966-11225 | tabella scalare su 32 e 34, 64 valori per core | `wlc_phy_a4`, già portata da `patches/b43/MESSAGES.md#0004` |
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

### Una op del setup non spiegata

`RAD.RD 0x81` a **#11820** e **#12934** nel primo init, #46544 e #48182 nel
secondo: quattro read in 70796 record, tutte dentro `papd_cal_setup`, una per
core, sempre **fra le quattro read AFE e le quattro mod sulle stesse quattro**.
Il registro e' `TR2G_CONFIG1_CORE0_NU`, lo stesso indirizzo per entrambi i core,
scritto **una volta per init** (#83, `val=0x1`) nel blocco di init del radio e mai
piu'; le read tornano `0x1`. brcmsmac non lo tocca, e nei due driver esiste solo
come define.

Il flush generico e' **escluso**: un barrier si vedrebbe dappertutto, non quattro
volte. Restano un flag che l'init pianta in un registro libero e rilegge, o un
barrier proprio in quel punto — ultima read prima delle prime write sugli stessi
quattro registri. **SALAME** su entrambe: la cattura non le distingue. Le
distingue il blob, guardando se il return finisce in uno store o in un branch.
Nel driver non c'e': un read di cui non sappiamo se il valore serve non va in
mainline.

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

**Le prime tre fasi sono già fatte.** Scalare ed epsilon sono `patches/b43/MESSAGES.md#0004`.
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

## Ordine di lavoro

I punti 1 e 2 sono **fatti**, `patches/b43/MESSAGES.md#0015`, e sono venuti fuori insieme
perche' nessuno dei due sta in piedi da solo: un setup senza cleanup lascia
accesi gli override RF, quelli AFE e il coupler, e il filtro della cal fuori
dalla cal e' peggio che non toccarlo.

1. ~~il setup di `papd_cal_setup`~~ — piu' il **cleanup**, che il piano non
   nominava, piu' i pezzi di `wlc_phy_a4` che li circondano: il reset RX salvato e
   azzerato fra le tabelle scalare e le epsilon e riscritto in coda, il bbmult
   salvato prima del loop, il bit 13 di `PAPD_CAL_SHIFTS0/1` rispento dopo.
2. ~~`restore`/`set` dei filtri digitali~~ — finestra `papd-digifilt` **15/15**.
3. **un solo passo del loop del core 0**. I piani di lettura non servono piu'
   "attivi" ma **in ordine**: vedi sotto.
4. **la matematica di `a3_nphy` e `a2_nphy`**, ed è l'ultima perché è l'unica
   parte che non si può verificare a pezzi.

### Le tabelle epsilon si scrivono cella per cella

Non e' un vezzo di fedelta': `0015` ha cambiato il bulk di 64 in due loop di 64
scritture singole, come brcmsmac e come il vendore. Costa 64 setup di indirizzo
di tabella invece di uno, e in cambio il bulk si appoggia all'auto-incremento
dell'indirizzo, che qui nessuno ha provato. La finestra `papd-tables` e' passata
da **260/774 a 513/774**, e quello che resta e' una sola op: il valore che la
`PHY.RD` di `0x01` restituisce.

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

`patches/b43/MESSAGES.md#0009` valuta la formula — la tabella ce l'ha già `0002` — con
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

`patches/b43/MESSAGES.md#0010` chiude i due. Contro la cattura, sul tono a 2500 kHz ampiezza
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

## Contro quale cattura si verifica, e con che tolleranza

La cal **non si verifica su `opinit-*`**: quella e' un init a caldo e la cattura
della cal la contiene per intero solo nella **cattura a freddo**,
`full-init-ch1-bw20.decoded`, nella sua parte contigua `#2-32769`. Misurato:
3499 read appaiate su 3499, e i piani si generano con

```sh
./reverse-tools/gen_readplans.py router-data/dsl-3580l/full-init-ch1-bw20.decoded \
    --range 2 32769 --name full --max-len 512 > test/readplans_full.h
```

che da' **148 piani**. Il `--max-len 512` non e' opzionale: col default a 64 i
piani degli indirizzi che una cal rilegge decine di volte si troncano e la cal
media lo specchio (vedi `test/README.md`).

**Tolleranza sui valori che dipendono da rccal.** Fra un init completo e uno
parziale i valori di rccal cambiano di poche unita', e si e' visto anche su altri
device: non e' un difetto del port ne' della cattura. Quindi per le grandezze che
ne discendono il criterio non e' l'uguaglianza bit per bit ma la **magnitudo**:
una formula che produce il valore atteso **entro +-2** e' probabilmente la formula
giusta, e va trattata come tale invece di essere inseguita. L'uguaglianza esatta
resta il criterio per tutto il resto — tabelle, registri programmati da costanti,
coefficienti che non passano da rccal.

La cal PAPD nella cattura a freddo comincia a **#18662** (la tabella scalare) e i
suoi toni sono a #19534 e #21806.

## Il piano per `a2` e `a3`, con i nomi e la dimensione misurata

### I nomi

| brcmsmac | b43 | da dove viene il nome |
|---|---|---|
| `wlc_phy_a3_nphy` | `b43_nphy_papd_cal_gain_ctrl()` | dal blob: `wlc_phy_papd_cal_gctrl_nphy`. E' la ricerca dell'indice di gain, **legge** la tabella epsilon in un loop di 20 passi |
| `wlc_phy_a2_nphy` | `b43_nphy_papd_cal_epsilon()` | **nome nostro, non del vendore**: il blob non la identifica (`blob-inventory.md`). Calcola l'epsilon e lo **scrive** via `set_bbmult`. Va detto nel commento sopra la funzione, o fra sei mesi qualcuno lo cerca in brcmsmac e non lo trova |
| `wlc_phy_a4` | `b43_nphy_papd_cal()` | il nome che `0012` ha gia' introdotto: resta il livello alto, le due qui sopra ci stanno sotto |

### Quanto e', misurato e non stimato

Le due funzioni sono 279 + 147 righe, e la loro chiusura di dipendenze e'
**quattordici chiamate distinte**:

| chiamata | quante | equivalente b43 |
|---|---|---|
| `mod_phy_reg`, `write_phy_reg`, `read_phy_reg` | 38 | `b43_phy_maskset` / `b43_phy_write` / `b43_phy_read` |
| `wlc_phy_table_read_nphy`, `_write_nphy` | 4 | `b43_ntab_read_bulk`, `b43_ntab_write_bulk` |
| `wlc_phy_rfctrl_override_nphy`, `_rev7`, `_1tomany` | 9 | `b43_nphy_rf_ctl_override`, `_rev7`, `_one_to_many` — ci sono tutte e tre |
| `wlc_phy_get_tx_gain_nphy` | 1 | `b43_nphy_get_tx_gains` |
| `wlc_phy_ipa_set_bbmult_nphy` | 2 | **da verificare** |
| `wlc_phy_papd_decode_epsilon` | 2 | **da verificare** |
| `wlc_phy_a1_nphy` | 2 | **un altro nome offuscato, da identificare** |

Quindi non e' un blocco isolato: poggia quasi tutto su roba che b43 ha. Le
incognite sono **tre funzioni**. Un pomeriggio di lavoro, e chi riprende non deve
rifare questa conta.

### L'ordine, e perche' e' questo

Il prerequisito e' cambiato: non e' "separare i piani per cattura", e' **avere la
fase contigua**. I piani sono posizionali, quindi servono il valore che
l'hardware ha dato solo se il port fa le stesse read nello stesso ordine del
vendore; dentro una regione contigua quella condizione e' vera per costruzione, e
allora i valori tornano da soli senza posizionare niente per chiamata.

Misurato dentro l'unica finestra, `up-ch1` (#132-26100): nell'intervallo della cal
i blocchi contigui sono a **#10966 (847 op)**, #11822 (334), #12784 (145), #12936
(334), #13752 (90), #13856 (48), #13921 (172). Non ci sono region per fase, e non
per dimenticanza: una fase presa da sola non dice niente su cio' che le arriva
addosso da prima. La struttura:

| da | op contigue | cosa |
|---|---|---|
| #10966 | 847 | tabelle scalare, reset RX, epsilon cella per cella, filtri, bbmult, banda del filtro, override RF |
| — | buco di 1 | `RAD.RD 0x81`, non spiegata |
| #11822 | 5 | mod AFE |
| — | buco di 3 | le **atten del coupler**: vedi sotto |
| #11822 | 334 | mod AFE, coupler, il tono da 160 word |
| — | **buco di 349** | `a3`/`a2`, core 0 |
| #12792 | 74 | i 17 override spenti della cleanup |
| #12882 | 48 | coda della cleanup, AFE e bbmult |
| #12936 | 334 | core 1, stessa forma |
| — | **buco di 276** | `a3`/`a2`, core 1 |
| #13760 | 74 | cleanup core 1 |
| #13856 | 48 | coda di `a4` |

Quindi:

1. **I due buchi grossi sono `a3`/`a2`** e sono il lavoro vero. Tutto il resto e'
   contiguo, e dentro quel contiguo i piani sono in ordine.
2. ~~I 3 op della banda del filtro~~ — **chiusi, e non era ne' la cattura ne' i
   piani.** L'harness mirrorava solo PHY, radio, MMIO e SHM: una lettura di
   tabella passa dalla porta dati `0x73`, quindi il port si riprendeva l'ultima
   cella scritta da qualunque parte — le epsilon appena azzerate, cioe' 0 — invece
   di `7/0x154`. La cella la scrivono entrambi, e con lo stesso valore
   (`0x2c64`, #6996 nella cattura a freddo). Aggiunto `tbl_mirror` in `wrap.c`, il
   primo blocco e' passato da **796 a 847 op** e il totale da 1812 a 1836. Prima
   di guardarci l'ho attribuito ai piani e poi alla cattura a caldo: **TONNO**
   entrambe le volte.
3. **Poi il codice**, un passo di cal per volta, col criterio del +-2 sui valori
   che passano da rccal (sezione sopra), **contro la regione `papd-cal-freddo`**.

### Il bbmult: era un difetto dell'harness, non del port

Per una sessione questa voce ha detto che b43 non scrive mai la cella 87 della
tabella 15 e che quindi la cleanup ripristina uno zero. **TONNO**: il port ci
scrive `0x2c2c`, lo stesso valore del vendore, quattro volte prima della cal.

Il buco era nel mirror delle tabelle, aggiunto male: serviva la cella al valore di
ritorno di `b43_ntab_read` ma **non alla porta dati**, e nel trace la riga che si
confronta e' la `PHY.RD` di `0x73`, che continuava a dare il mirror del registro.
Cioe' il driver leggeva la cosa giusta e la misura diceva di no. Sistemato con
`tbl_port_get()` in `wrap.c`: `0x73` e `0x74` servono la cella indirizzata
dall'ultima scrittura su `0x72`, che porta `(id << 10) | off` per ogni larghezza.

La lezione, che e' la seconda volta in questa fase: **quando una read non torna,
guardare l'harness prima del driver**. Le due volte prima ho dato la colpa ai piani
di lettura e alla cattura sbagliata.

### Le atten del coupler: le sa solo la cattura

Restano due buchi di valore, `RAD.RD 0x17d` e `0x19d`: il vendore legge `0xaa`, il
port `0`. Quei due registri **non sono in `r2057_rev8_init`** e nessuno dei due
driver li scrive: `0xaa` e' il default del chip, e l'unico posto dove esiste e' la
cattura. Il piano ce l'ha, `{0xaa, 0xaa, 0xaa}` ai record 11828, 12946, 15083.

**Chiuso dai seed, non dai piani.** `reverse-tools/gen_seed.py` semina gli
indirizzi il cui primo accesso nella cattura e' una read, cioe' i default del chip,
e `0x17d`/`0x19d` a `0xaa` sono esattamente quello. Il criterio non e' "mai
scritto": la cal le scrive, ma dopo averle lette.

Resta il knob `B43_TEST_PLAN_FROM`, spento: posizionare il cursore all'ingresso di
una regione **misurato peggiorava** (1830 → 1816, primo blocco 847 → 843), perche'
i piani servivano valori dove il mirror era giusto. La domanda aperta e' quale read
sfasa il piano, non se posizionare il cursore.

### La stessa fase in due catture indipendenti

`papd-cal-freddo` (#18662-24096 di `full-init-ch1-bw20.decoded`) da' **3727 op del
vendore e le stesse 1830 in blocchi, 49%**, con lo stesso primo blocco da 847. Il
denominatore e' piu' grande perche' quella e' una cal completa: i due buchi di
`a3`/`a2` sono **920 e 930** op invece di 349 e 276.

Due cose per cui e' quella la cattura su cui verificare `a2`/`a3`:

- **la coda della cleanup matcha piu' a lungo**, 82 op contro 48, perche' i valori
  che ripristina sono quelli che un init completo lascia dietro;
- la struttura dei blocchi e' **la stessa** in due catture che non hanno niente in
  comune se non il driver: e' la conferma piu' forte che il guscio e' giusto, piu'
  di qualunque percentuale su una sola cattura.

### La regola del controllo

Prima di credere a qualsiasi numero di questa fase: `git -C ~/src/linux diff
--numstat`. Con `0001..0014` e la patch mainline della cal RSSI applicate deve
dire **213 inserzioni e 13 delezioni** su `phy_n.c` — la voce diceva 27, che e' il
conto di `0011` da sola e non torna su niente — e `--global-run 132 26100` sul
flow `init` deve dare **5953 op su 22951, 26%, 721 blocchi**.

Con dentro anche `0015` e le due mainline degli override RF: **249+/7-** su
`phy_n.c`, **2+/2-** su `tables_nphy.c`, e `--global-run` a **7075 su 22951, 31%**.

Se non torna, l'albero e' spoglio e ogni misura della cal e' rumore: e' la
trappola 1, e ci si ricasca.

## Perche' il resto non si porta a pezzi

Il cuore e' `a3_nphy` piu' `a2_nphy` per due core, e non si spezza in parti
verificabili singolarmente: o c'e' il passo di cal completo o non si verifica niente.
E `papd_cal_setup`, che nella scaletta e' il punto 1 perche' e' tutto scritture, sono
250 righe — verificabile non vuol dire piccolo, e finche' la ricerca di gain non c'e'
non ha un chiamante, quindi come patch a se' sarebbe codice morto.

L'offset epsilon e la tabella dei campioni erano invece calcoli isolati con valori
catturati da confrontare, ed e' per quello che si sono chiusi.
