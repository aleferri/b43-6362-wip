# patches/b43 — note della serie che non stanno in MESSAGES.md

Era l'intestazione di `rollup.diff`, finche' la serie stava compressa in quel
file. Il codice ora sta in `b43/`, e la serie come diff unico la stampa
`scripts/series-diff.sh`. Qui resta quello che il diff non porta: cosa non
contiene, i punti che `reverse-tools/check_patch_gating.py` segna e perche' vanno
bene cosi', e il razionale delle modifiche venute dopo `0036`, che una voce di
`MESSAGES.md` ancora non ce l'hanno e servono alla ri-divisione.

Cosa NON contiene, e perche' non manca niente:

  0010  b43: fix the N-PHY sample table generation
        Duplicato di mainline/b43-fix-two-defects-in-the-n-phy-sample-table-logic
        a meno di due cast (u32) su valori che stanno in [0, 0x3ff] dopo
        l'and, quindi senza effetto: cordic_iq.i e .q sono s32
        (include/linux/cordic.h:36). Misurato senza 0010: le finestre
        sampleplay-tssi e sampleplay-iqlo fanno 322/322 entrambe.

  0022  b43: treat the N-PHY DAC test as a mode not a flag
        Duplicato esatto di mainline/b43-treat-the-n-phy-dac-test-as-a-mode-not-a-flag,
        riga per riga sulle stesse cinque sostituzioni.

Niente ha mai girato su hardware.

`check_patch_gating.py` sulla serie, con `--tree` l'albero pinnato piu' le
mainline (`scripts/series-diff.sh ~/src/pin /tmp/base`), segna **sei** punti NON
GATEATI: questi sotto tranne `b43_nphy_tx_power_ctrl`, che non segna piu' ma la
cui dichiarazione resta valida. L'ultimo dell'elenco e' uno che il tool NON segna,
e sbaglia.

  b43_radio_2057_setup (phy_n.c)
        Condivisa, ma qui subisce solo un'estrazione: le stesse quattro op sul
        registro nello stesso ordine, dietro un nome (b43_radio_2057_vcocal),
        perche' ora la vuole anche la coda della cal periodica. La finestra
        chanswitch-ch6 non si muove.

  b43_nphy_op_prepare_structs (phy_n.c)
        Comune a ogni N-PHY, quindi le due righe che inizializzano a -1 il
        record per core girano su tutti. Quel record lo legge un solo posto,
        b43_nphy_txpwr_index(), che nessun'altra revisione raggiunge: altrove
        e' scritto e mai letto. Ed e' il valore giusto e non quello comodo,
        perche' zero direbbe che l'indice zero e' forzato.

  b43_ppr_add (ppr.c)
        E' il tool che vede la funzione nuova atterrare accanto, non una
        modifica a quella: l'hunk aggiunge b43_ppr_apply_max_group() sopra e
        non tocca niente di esistente. La funzione nuova non ha test di
        revisione, come il resto del file: il gate sta nel chiamante, che
        prova phy rev 8, radio rev 8 e la banda 2 GHz.

  b43_nphy_rf_ctl_override_one_to_many (phy_n.c)
        Comune a ogni N-PHY rev 7 e su. Il caso TX_GAIN passa il campo 0x2000
        invece di 0x4000 e taglia il secondo argomento con (value & 0x8000) >> 14
        invece di value >> 14: e' quello che fa il riferimento in
        wlc_phy_rfctrl_override_1tomany_nphy(), (0x1 << 12) e (0x1 << 13), e la
        cattura concorda - spegne 0x4000 zero volte. E' un numero di campo
        sbagliato, non una feature di questo hardware, e dietro un gate non ci va.

  b43_nphy_update_tx_cal_ladder (phy_n.c)
        Comune a ogni N-PHY rev 3 e su. Le due scale della cal TX I/Q LO si
        scrivono in due cicli invece di uno interleavato: stesse trentasei celle
        della tabella 15, stessi valori, stesso ordine dentro ciascuna scala,
        cambia solo il raggruppamento. Nessuna condizione nuova e nessuna op in
        piu'. Dietro un gate non ci va perche' non e' una feature di questo
        hardware, e' l'ordine che il vendore usa su ogni revisione - la cattura
        lo mostra due volte, a #9015 e a #9735.

  b43_nphy_tx_power_ctrl (phy_n.c)
        Comune a ogni N-PHY. Il ramo di spegnimento passa da
        b43_ntab_write_bulk() sulle tabelle 26 e 27 all'offset 64 invece di
        aprire la porta dati a mano: e' la stessa strada che il ramo di
        accensione, dieci righe sotto, prende da sempre sulle stesse due tabelle
        allo stesso offset. Le celle scritte sono le stesse, lo zero e' lo zero:
        nessuna revisione si comporta diversamente. Dietro un gate non ci va
        perche' non e' una feature di questo hardware, e' togliere un
        open-coding.

  b43_nphy_get_tx_gains (phy_n.c)
        Comune a ogni N-PHY rev 3 e su. Il ramo a controllo di potenza acceso
        legge l'indice per catena dai due registri di stato per andare a prendere
        i gain in tabella; qui quell'indice viene anche registrato in
        nphy->cal_orig_pwr_idx[], perche' e' la lettura da cui la cattura lo
        prende e la coda della cal periodica lo rimette. Nessuna op in piu' e
        nessuna condizione nuova: due assegnazioni a un campo che legge solo la
        coda, che gira su phy rev 8 e radio rev 8. Sulle altre revisioni il campo
        resta scritto e non letto, come lo era prima.

  b43_nphy_poll_rssi (phy_n.c), che il tool considera gateata e non lo e'
        La lettura di GPIO_SEL esce da if (phy.rev < 2), dove sta insieme alla
        scrittura: nel riferimento la lettura e' incondizionata e solo la
        scrittura e' gateata (wlc_phy_poll_rssi_nphy). Il tool vede il rev < 2
        dentro la funzione e la conta gateata, ma la riga che tocco gira su
        ogni revisione. La dichiarazione e' che il cambiamento e' INERTE: su
        rev >= 2 il valore letto serve solo alla riscrittura, che resta
        gateata, quindi nessuna revisione si comporta diversamente. Costa una
        lettura di registro per chiamata, e serve solo a questo banco: nella
        cattura la lettura di 0xca c'e', una per poll, e senza di lei la
        seconda cal RSSI si spezza in 22 blocchi invece di 3. Per la stessa
        ragione NON e' un candidato mainline: la' e' una lettura buttata.

Aggiunta la macchina a stati mphase in b43_nphy_cal_perical_phyinit(): i passi del
riferimento - INIT, TX I/Q LO, PAPD, RX I/Q, RSSI, idle TSSI - ognuno con la
parentesi che salva lo stato del controllo di potenza, lo spegne, esegue la fase e
lo ripristina; ed e' il ripristino a programmare adj_pwr_tbl. Piu' il blocco
differito in coda a b43_phy_initn(), perche' la parentesi ripristina cio' che trova
e la' il controllo e' ancora spento: le due meta' servono insieme.

Le sei fasi TX del riferimento restano UN passo, e la cattura e' il motivo: emette
i dodici comandi di fila con una sola lettura del gain a #8505 invece di una per
fase. Divisi in sei, la run appaiata della cal cade da 428 a 331 in 28 frammenti -
misurato con la parentesi attorno a ogni pezzo e senza, quindi e' la divisione e non
la parentesi.

Portata la misura del tono della cal PAPD, che non c'era: wlc_phy_a1/a2/a3_nphy e
wlc_phy_papd_decode_epsilon del riferimento, cioe' il passo del motore su un core,
la ricerca del codice di gain che smette di clippare, e il lisciamento della
tabella epsilon a finestra scorrevole. Solo il ramo rev 7 e oltre e solo la
meta' 2 GHz: il chiamante prova phy rev 8, radio rev 8 e la banda.

MISURATO: blocchi contigui 17532 -> 17838 (76% -> 78%), che e' sopra il valore di
base per la prima volta. Il totale per fase resta 6558 contro 6602: la run piu'
lunga di cal-papd non si muove, ma la forma passa da 794 2x334 172 2x78 +14 a
794 2x334 220 178 +32, cioe' piu' op appaiate in piu' pezzi. adj_pwr_tbl resta 13.

---

Piu' le due parentesi per core attorno ai due passi del motore PAPD, ai quattro
punti che la cattura apre (#12197 #12331 core 0, #13311 #13383 core 1), con la
parentesi fattorizzata in b43_nphy_pwr_ctl_open/close() e usata anche dalla cal
periodica. NON FANNO QUELLO CHE DOVEVANO: adj_pwr_tbl resta 13, i segmenti vanno
da 14 a 20 contro i 9 del vendore, blocchi contigui 17838 -> 17831, totale 6558 ->
6555. Le venti aperture leggono il gain, quindi il controllo era acceso, ma le
chiusure non riprogrammano la tabella: dentro b43_nphy_tx_power_ctrl() c'e' una
condizione sul ramo di abilitazione che non ho letto, ed e' il prossimo posto.

---

get_tx_gains() e' una lettura sola per tutta la sequenza invece di una per passo:
il riferimento la rifa a ogni invocazione, la cattura no. Vale +3 su cal-papd e sul
totale per fase, 6555 -> 6558, blocchi contigui 17831 -> 17830.

---

E la RX IQ con la RSSI sono un passo solo, perche' la cattura le ha contigue: fra la
rilettura dei coefficienti di save_cal (#21169) e quella che apre coef_setup (#21187)
ci sono diciotto op e nient'altro. In due passi, fra i due passa la chiusura e la
riapertura della parentesi, cioe' due riprogrammazioni da 84 celle, e la sequenza si
spezza. coeff-setup-2 torna a 1066 su 1073 in UN blocco (era 1037 piu' frammenti) e
il totale per fase va a 6587.

---

E la parentesi si chiude UNA volta, alla fine della sequenza, non a ogni passo: il
controllo resta spento per tutta la cal. L'audit dei confini nella cattura non trova
una sola accensione fra le fasi - solo spegnimenti, che sono le aperture. Blocchi
contigui 17830 -> 18254 (78% -> 80%), totale per fase fermo a 6587.

---

E la restituzione dell'indice sta fra la PAPD e la RX IQ, non dopo: la cattura ha
la' due chiamate a txpwr_index, una per core, ognuna col suo salva e riapplica.
Numeri neutri - 18254 e 6587 identici - con i frammenti di cal-papd da 34 a 31: sta
dentro per l'evidenza, non per il numero.

---

E il test della restituzione e' sullo stato all'INGRESSO della sequenza, non su
quello del passo, che con la chiusura unica alla fine e' falso dopo la prima
apertura. Verificato: le TBL.RD 7/0x110 len=1 passano da 1 a 2 come il vendore. Verificato: le TBL.RD 7/0x110 len=1
passano da 1 a 2 come il vendore.

E l'indice da restituire si prende al passo INIT. Il ramo perical != 2 lo prende
nello stesso punto, subito prima di precal_txgain, ma questo hardware ha
perical == 2 - che e' la ragione della macchina a stati - quindi la' non passa e
cal_orig_pwr_idx restava a zero: la restituzione forzava l'indice 0 invece di
rimettere quello di partenza, e spezzava i sotto-blocchi dello sweep RX IQ.
Rimessa, la forma di cal-rx-iq torna 6x420 2x360 6x119 12x85 con 21 frammenti
invece di 42.

Stato: blocchi contigui 18258 (80%) contro 17532 del baseline, totale per fase 6587
contro 6602.

---

E la coda della sequenza non restituisce l'indice: le due coppie di txpwr_index stanno
entrambe PRIMA delle cal, dentro perical-ingresso - il vendore forza a #7445 e #7868 e
restituisce a #8096 e #8294 - e il blocco differito le fa gia'. Le write di 15/0x57 che
combaciano passano da cinque a sette e il conteggio va a 35 come il vendore, a run
invariate (6587) e blocchi 18254.

---
---

E precal_txgain lo fa solo il blocco differito, non anche il passo INIT: rifarlo
forzava l'indice una seconda volta, dove il vendore ne ha una sola. Le prime dodici
write di 15/0x57 combaciano esatte, e il totale per fase passa a 6658 - SOPRA il 6602
del baseline - con blocchi contigui 18309 (80%), cal-papd 850 contro 847 del baseline
e cal-tx-iqlo 443.

---

E la sequenza differita non gira in coda a b43_phy_initn() ma dalla coda di
b43_nphy_op_recalc_txpower(), dietro nphy->perical_pending: la cattura la mette DOPO
recalc, non prima - init, recalc a #5726-6500, poi la cal da #7034. Chiamata da initn,
le op di recalc uscivano diciassettemila record oltre la loro finestra e la fase faceva
zero su 716.

  recalc-txpower       0 -> 604 su 716 (84%), un blocco solo
  totale per fase   6658 -> 7205 (38%)
  blocchi contigui 18309 -> 18462 (80%)
  a freddo         18022 -> 18163 (66%)

---
---

E la coda della sequenza rimette i due indici, uno per core, prima della
chiusura unica: la cattura legge 26/0xca a #25017 e 27/0xcc a #25418, e fra le
due chiamate il controllo di potenza resta spento - i quattro payload da 84
zeri di #24841, #25064, #25242, #25465 - con l'unica accensione dopo, a
#25641, che e' la chiusura. Gli indici non sono uno: si leggono dai bit 8..14
di C1/C2_TXPCTL_STAT, a #7034 e #7036, e sono 10 sul core 0 e 12 sul core 1,
quindi non possono essere quello che le cal forzano.

  blocchi contigui 18462 -> 19224 (80% -> 84%)
  totale per fase  fermo a 7205

Aggiungendola la finestra recalc-txpower sembrava rompersi, da 519/519 a
432/519. Era la sua ancora: prendeva la TERZA apertura di 26/0x0, che era la
recalc del port finche' la sequenza girava altrove e che con la sequenza in
coda a recalc e' diventata il power setup della coda. Confrontava la recalc
del vendore con la coda del port. Corretta l'ancora alla seconda, la finestra
torna 519/519 con la modifica dentro.

---

E la lettura di GPIO_SEL in b43_nphy_poll_rssi() esce dal gate della
scrittura. Vedi la dichiarazione sopra: e' inerte e non e' un candidato
mainline. Con le due mainline nuove sulla cal RSSI, la seconda cal RSSI
misurata da sola passa da 623 a 956 op su 960 (65% -> 100%) e da 22 blocchi a
3, con una run singola da 940.

  blocchi contigui 19224 -> 19247 (84%)
  totale per fase   7205 -> 7206 (38%)
  a freddo         18163 -> 18167 (66%)

---

E la lettura dei due indici di base sale in testa a
b43_nphy_cal_perical_phyinit(), fuori dal passo INIT, dove il riferimento la
mette: in testa a ogni invocazione, prima che qualcosa possa muoverli. Nella
cattura sta a #7034 e #7036, i primi due record della fase, prima della
lettura del tx gain. Numero neutro: perical-ingresso misurata da sola resta a
1295 op su 1402 (92%) in 31 blocchi. Sta dentro per l'ordine, non per il
numero.

---

---

E le letture d'ingresso vanno prima del blocco differito. Il riferimento in testa a
wlc_phy_cal_perical_nphy_run() legge l'indice per catena, poi il gain, poi
get_tx_gain, poi spegne il controllo, e SOLO DOPO fa il precal; il port faceva il
precal per primo. Ora target si prende prima del precal, e l'indice che la coda
riforza lo registra get_tx_gains(), che e' la lettura da cui la cattura lo prende
(#7044 e #7046, 10 e 12). NON e' nphy_cal_orig_pwr_idx del riferimento, che a
#7034/#7036 rende 25 e 25: quel ramo di brcmsmac non descrive questa coda, come
l'indice di precal e il raggruppamento dell'rccal.

  blocchi contigui 19247 -> 19254 (84%)
  a freddo         18167 -> 18169 (66%)
  perical-ingresso  divergenze 905 -> 885
  totale per fase  fermo a 7206

---

---

E il blocco differito gira DENTRO la parentesi. Il riferimento spegne il controllo
di potenza in testa alla run, prima che qualcosa forzi un indice; il port lo
spegneva solo entrando nel primo passo, quindi il precal e i due hand-back
restituivano il controllo ACCESO e ognuno riprogrammava la tabella di potenza
aggiustata. La sequenza ora riceve lo stato d'ingresso come argomento invece di
rileggerlo dopo che il blocco differito lo ha girato.

  blocchi contigui 19254 -> 19804 (84% -> 86%)
  a freddo         18169 -> 18750 (66% -> 68%)
  perical-ingresso  divergenze 885 -> 323, op mancanti 675 -> 42
  txpwr-index       divergenze note 11 -> 6

---

E il ramo di spegnimento di b43_nphy_tx_power_ctrl() passa da
b43_ntab_write_bulk() come fa quello di accensione, invece di aprire la porta dati
a mano e scrivere 84 celle in un ciclo. Le celle scritte sono le stesse per la
stessa tabella allo stesso offset: cambia la strada, non l'effetto. Ma il tracer
del vendore aggancia la funzione di tabella, quindi la sua op c'e' e quella del
port no, e l'op mancante sfasava di uno tutto quello che seguiva - il che spiega
perche' i blocchi uguali dentro perical-ingresso si accorciavano di uno a ogni
scrittura da 84 celle.

  blocchi contigui  19804 -> 19977 (86% -> 87%)
  totale per fase    7206 -> 7578 (38% -> 40%)
  perical-ingresso   run 119 -> 401, divergenze 323 -> 286
  rxiq-ingresso      run 306 -> 401, divergenze 805 -> 722
  cal-rx-iq          run 420 -> 510
  a freddo          18750 -> 18711, cioe' 39 in meno: l'assegnazione dei blocchi
                    e' esclusiva e golosa, e nessuna finestra si e' rotta

---

---

E le due letture d'ingresso del riferimento tornano, nell'ordine suo: l'indice per
catena e, se il controllo di potenza girava, i gain. Il riferimento le fa e poi non
le rilegge - la coda rimette l'indice preso CON i gain, non questo - ma l'hardware
le vede, e senza di loro tutto quello che segue in questa fase sta sei op in
anticipo. Erano proprio quelle sei: due della coppia e quattro della table-read.
Da qui i campi cal_orig_pwr_idx[] e cal_orig_tx_gain[], che portano i nomi del
riferimento e come la' non li legge nessuno; l'indice che la coda usa sta in
pwr_idx_at_gain[], scritto da b43_nphy_get_tx_gains().

  blocchi contigui 19977 -> 20013 (87%)
  totale per fase   7578 -> 7586 (40%)
  a freddo         18711 -> 18715 (68%)
  perical-ingresso  divergenze 286 -> 95, run 401 -> 409

Cosa resta in quella finestra, 95 op in tre gruppi: 4 op di rilettura a 9 bit delle
tabelle 26/27 oltre l'offset 576, che e' hardware e sta dichiarato; 27 op in una
parentesi di txpwr_index dove il port apre il blocco di salvataggio mentre il
vendore e' gia' a metà; e 64 op che sono lo sfasamento che ne consegue.

---

---

E b43_nphy_precal_txgain() scrive nphy->txcal_bbmult, che in mainline e' letto e
mai scritto. Lo legge b43_nphy_update_tx_cal_ladder(), che ci scala i 36 gradini
della scala che la cal TX I/Q LO usa: senza scrittore vale zero, quindi ogni
gradino esce ad ampiezza zero. Il riferimento lo riempie in coda a
wlc_phy_precal_txgain_nphy(), quando save_bbmult, che sul rev 7 e su e' sempre, e
di nuovo in coda a wlc_phy_cal_txgainctrl_nphy(). Nella cattura e' la TBL.RD
15/0x57 a #8076, subito dopo il forzamento dell'indice.

Questo e' un difetto di mainline e non di questo hardware: va in
patches/mainline/ appena si e' misurato cosa cambia sulla cal, che qui non si
vede perche' i piani servono i valori del vendore.

E i gain al forzamento si prendono dove la cattura li prende, fra il forzamento e
la restituzione (#8080), non dentro il passo INIT della macchina a stati. Il
riferimento fa cal_target_gain = get_tx_gain() subito dopo precal_txgain(), nello
stesso passo.

  blocchi contigui 20013 -> 20022 (87%)
  totale per fase   7586 -> 7750 (41%)
  a freddo         18715 -> 18724 (68%)
  perical-ingresso  divergenze 95 -> 19, run 409 -> 573

Le 19 che restano sono dichiarate nella finestra: quattro di rilettura a 9 bit,
inerti, e quindici di confine con la fase dopo.

---

---

E la parentesi per passo se ne va da tutti i passi tranne uno. Il controllo di
potenza e' gia' spento da prima del blocco differito, quindi
b43_nphy_pwr_ctl_open() dentro il ciclo non spegne niente e la lettura del gain la
salta: restano 172 op per passo che l'hardware non vede. Il port ne emetteva 48 di
parentesi da 84 celle contro le 36 del vendore, dodici in piu', e sono queste.

Quale tenere lo dice l'audit dei confini, non un'intuizione: fra perical e TX I/Q LO
nessuna transizione, fra TX I/Q LO e PAPD UNA, fra PAPD e RX IQ quattro (che sono le
due per core della cal PAPD, che le apre da se'), fra RX IQ e idle TSSI nessuna.
Quindi resta la sola apertura in testa al passo PAPDCAL. Togliendole tutte e sei si
guadagnava sull'ingresso della RX IQ e si perdevano 172 op contigue altrove:
misurato, non dedotto.

  blocchi contigui 20022 -> 20025 (87%)
  rxiq-ingresso     run 401 -> 500, divergenze 722 -> 542, op mancanti 184 -> 19
  perical-ingresso  op mancanti 19 -> 10
  cal-rx-iq         forma da 510 5x507 a 2x510 4x507

---

---

E b43_nphy_cal_perical_phyinit() non sovrascrive piu' il parametro che ha appena
ricevuto. Rileggeva i gain in testa alla propria funzione, con il controllo di
potenza gia' spento, quindi b43_nphy_get_tx_gains() prendeva il ramo che legge
7/0x110 invece di quello che indicizza la tabella: i gain d'ingresso calcolati dal
chiamante finivano nel cestino tre righe dopo. Misurato con una stampa temporanea:
il chiamante passava pad 14,12 e la funzione usava pad 4,4.

E la cal RX IQ riceve i gain all'indice FORZATO, non quelli d'ingresso. La cattura
scrive 0x4077 su entrambe le catene a #14985 e #14986, che e' il cal_gain della
voce 10 di b43_ntab_tx_gain_ipa_2057_rev8_2g (0x4077002e: ipa 7, pad 14, pga 0,
txgm 4) - l'indice che il precal forza su entrambe. Coi gain d'ingresso, che hanno
gli indici per catena 10 e 12, escono 0x4077 e 0x4067.

  blocchi contigui 20025 -> 20027 (87%)
  totale per fase   7750 -> 7752 (41%)
  a freddo         18724 -> 18726 (68%)
  perical-ingresso  divergenze 19 -> 17, run 573 -> 575
  rxiq-ingresso     i due valori scritti in 7/0x110 ora combaciano

---

---

E la cal PAPD tiene la carrier search aperta per tutto, come fa wlc_phy_a4() dalla
riga 25133 alla 25380. Il hold e' a contatore: senza quello esterno, le parentesi
che i passi interni prendono escono come coppie ingresso-uscita per conto loro. Si
contano: il port emetteva 8 coppie contro le 6 del vendore, e le due in piu' erano
corte, 27 e 34 op, cioe' proprio inner che il vendore ha gratis.

  blocchi contigui 20027 -> 20029 (87%)
  a freddo         18726 -> 18729 (68%)
  rxiq-ingresso     divergenze 542 -> 530
  cal-papd          run 850 -> 847, forma da 850 2x334 a 847 2x342
  totale per fase   7752 -> 7749

E la cattura lo conferma direttamente, che e' la verifica che conta: le sei coppie
del vendore sono #1620-1666 (34 op, init), #8492-10756 (1601, cal TX I/Q LO),
#10771-14946 (3658, cal PAPD - la regione e' #10962-14092), #14964-21143 (5615,
ingresso e sweep della RX IQ), #22245-23900 (1052, coeff setup e cal RSSI),
#24271-24317 (34, idle TSSI). La terza copre la cal PAPD per intero ed esce a
#14946, che e' l'uscita che si vedeva nel gruppo da 25 op di rxiq-ingresso.

Il hold del port risulta 5112 op contro i 3658 del vendore, ma non e' fuori posto:
le due estremita' combaciano op per op sui due lati, e la lunghezza differisce
perche' il port emette 1454 op dentro la cal PAPD che il vendore non emette - cosa
nota, cal-papd fa 847 su 2662 e a3/a2 non ci sono. Contare la lunghezza di un hold
non misura il hold, misura cio' che ci sta dentro.

Sui confini restano due numeri: una coppia in piu' (7 contro 6) e nove letture di
0xb0 in piu' (25 contro 16), coi valori scritti che combaciano. E' un conteggio di
chiamate a b43_nphy_classifier(), non un valore sbagliato.

---

---

E il blocco di salvataggio della cal RX IQ salva un registro in piu', 0x2ff. La
cattura lo legge a #15015, subito dopo i quattro registri di override rev 7 e prima
di 0x297 e 0x29b: PHY.RD addr=0x02ff val=0x00001000. brcmsmac non lo legge MAI -
tocca solo i bit 0, 13, 14 e 15 di quell'indirizzo nel percorso di override rev 7 -
quindi qui decide la cattura, come per l'indice di precal e il raggruppamento
dell'rccal. Salvato e non ripristinato, che e' quello che la cattura fa: la lettura
c'e', una write in questa fase no.

Vale un'op, e chiude quattrocentosessantasei divergenze:

  rxiq-ingresso     divergenze 530 -> 64
  blocchi contigui 20029 -> 20031 (87%)
  a freddo         18729 -> 18730 (68%)
  cal-rx-iq         forma da 2x510 4x507 2x360 285 a 2x510 4x507 2x360 288

Il perche' e' l'unica cosa interessante: la lettura mancante sfasava di UNO tutto
quello che seguiva, e dopo non si riallineava mai, perche' da li' in poi sono corse
lunghe di zeri identici e di contenuto identico della tabella dei campioni. I
gruppi da 357, 46, 21, 16, 5 e le quattro coppie da 2 erano tutti quello.

Delle 64 che restano, UNA non e' dichiarabile e va corretta nel driver: la OBJ.WR
addr=0xb8 val=0x2710, che e' write_shm(M_CTS_DURATION, 10000) - M_PSM_SOFT_REGS +
0x5c*2 = 0xb8 - e che b43 non fa da nessuna parte, mentre il riferimento la fa in
entrambi i rami che portano alla cal RX IQ (phy_n.c:25413 e 25460). L'avevo
archiviata dentro la deroga OBJ.WR, e la deroga dice un'altra cosa: che l'harness
non puo' EMETTERE object memory in modo confrontabile, non che il driver possa non
FARE la scrittura. wrap.c ha b43_shm_write16() e la stampa, quindi si vedrebbe
anche nel trace.

Le altre 63: sei di rilettura a 9 bit, due MAC.MCTRL che sono mac_enable e
mac_suspend e che l'harness stubba, due PHY.CLK del port col rimescolamento che ne
segue - e quelle il port le fa GIUSTE, b43_nphy_reset_cca() e
wlc_phy_resetcca_nphy() sono identiche, fgc(ON)/BBCFG/fgc(OFF)/RESET2RX: e' il
tracer che non le vede, perche' aggancia wlc_bmac_core_phy_clk e l'accessor dietro
b43_phy_force_clock() e' brcms_b_phyclk_fgc, un'altra funzione. Poi tre di
allineamento dei piani a valle della coppia di carrier search in piu' e ventotto di
confine con la fase dopo.

---

---

E la fase RXCAL scrive M_CTS_DURATION. La calibrazione trasmette a lungo, quindi il
mezzo va protetto per altrettanto: il riferimento imposta la durata del CTS che la
ucode manda, in testa a QUESTA fase e a nessun'altra, e va fatto col MAC acceso
(phy_n.c:25413 nella macchina a stati, 25460 nell'altro ramo). In b43 quella cella
non la scriveva nessuno: grep CTS_DURATION su tutto il driver non trovava niente.
M_CTS_DURATION = M_PSM_SOFT_REGS + 0x5c*2 = 0xb8, ed e' la OBJ.WR addr=0xb8
val=0x2710 di #14949.

Serve una define nuova, B43_SHM_SH_CTSDUR, e la stessa in test/stubs/b43_defs.h,
che e' generato dal b43.h del tree e non ha uno script che lo rigeneri.

  blocchi contigui 20031 -> 20035 (87%)
  a freddo         18730 -> 18734 (68%)
  totale per fase  fermo a 7749

La finestra rxiq-ingresso passa da 64 a 555 divergenze, e va detto perche' non e'
una regressione: con le tre op al loro posto la parita' dell'allineamento cambia, e
riemerge uno sfasamento che era mascherato - il piano di lettura di 0xb0. Le op
restano le stesse (mancano 18, in piu' 18 su 1503) e le due misure grandi salgono.
Si chiude togliendo la coppia di carrier search di troppo, che e' voce a se'.

---

---

E la pulizia della cal PAPD spegne anche il campo 0x2000, e le due prime le fa
PRIMA di fermare il tono. La cattura, a #13741-#13748: e7 e 0x7c per il core 0 e
ec e 0x7f per il core 1 (campo 0x1000), poi e7 e 0x348, ec e 0x349 (campo 0x2000,
il cui valore sta nei quattro bit bassi di quei due registri e non in un registro
intero). Il port il 0x2000 non lo spegneva affatto e il 0x1000 lo spegneva dopo.
Ora le otto op sono op per op quelle della cattura.

Numeri fermi: quel vicinato resta dentro un buco da 167 op che non si e' chiuso, e
serve capire il resto della sequenza di spegnimento prima che la metrica lo veda.
Sta dentro perche' e' giusto, non perche' paga.

---

---

E le tabelle dell'ADC ausiliario non sono piu' un /* TODO */. In
b43_nphy_workarounds_rev7plus() le quattro write bulk su tabella 8, offset 0x08,
0x18, 0x0c e 0x1c, erano commentate via perche' gli array non c'erano. La cattura
le ha a #771-#794: quattro celle per blocco, 0x8e 0x96 0x96 0x8b per il core 0,
0x8f 0x9f 0x9f 0x96 per il core 1, 0x02 0x02 0x02 0x00 per i due di gain.

Il riferimento sceglie l'ultimo elemento di ognuno dal power detector range e dalla
banda. Solo la combinazione di questa board sta qui - range 2, radio 2057 rev 8,
2 GHz - perche' le altre non hanno cattura dietro. E la' brcmsmac scrive 0x8c su
entrambi i core dove la cattura scrive 0x8b sul core 0 e lascia il core 1 a 0x96,
che e' il default dell'array; l'elemento di gain concorda a 0. Quarta volta che
brcmsmac e' piu' vecchio.

  blocchi contigui 20402 -> 20426 (89%)
  a freddo         18734 -> 18758 (68%)
  buco portabile    1193 -> 1169 op

---

---

E la scala della cal TX I/Q LO si scrive in due corse, non interleavata.
b43_nphy_update_tx_cal_ladder() scriveva 0, 32, 1, 33, 2, 34... e la cattura scrive
0x00-0x11 e poi 0x20-0x31, due blocchi consecutivi (#9015-#9123 e #9735-#9843, la
stessa cosa due volte). Stesse trentasei celle e stessi valori: cambia solo il
raggruppamento, e brcmsmac interleava anche lui - quinta volta che e' piu' vecchio
del driver delle catture.

  blocchi contigui 20426 -> 20632 (89% -> 90%)
  a freddo         18758 -> 18965 (68% -> 69%)
  buco portabile    1169 -> 963 op
  cal-tx-iqlo        forma da 443 333 268 80 a 443 333 268 110

Due sole corse per 206 op: e' il rapporto migliore fra righe toccate e op
recuperate di tutta la serie.

---

---

E il primo ritardo della sequenza TX2RX e' 0x46, non 8. La cattura lo scrive a
#806, dentro il bulk da sette celle su tabella 7 offset 0x90. Per rev 7 e su il
riferimento non aiuta: wlc_phy_workarounds_nphy_rev7() non programma affatto la
sequenza TX2RX, quindi l'8 che stava qui non aveva niente dietro. I sei ritardi
che seguono e tutti e sette gli eventi combaciavano gia'.

Costa UNA op (20952 -> 20951 e 18965 -> 18964) perche' quella cella sta dentro un
buco che comincia prima, sui maskset di 0xa6/0xa7. Sta dentro perche' il valore ha
una fonte e il precedente no.

---

---

E l'override uno-a-molti del TX gain usa il campo 0x2000, non 0x4000. Il
riferimento, nel caso txgain di wlc_phy_rfctrl_override_1tomany_nphy(), fa
(0x1 << 12) per il gain e (0x1 << 13) per il lpf gain; b43 faceva 0x1000 e
0x4000. E il conteggio degli spegnimenti su 0xe7/0xec lo conferma da solo: il
vendore spegne 0x4000 ZERO volte e 0x2000 otto, il port spegneva 0x4000 quattro
volte e 0x2000 due.

Corretto anche il taglio del secondo argomento: (value & 0x8000) >> 14 invece di
value >> 14, che si portava dietro anche il bit 14 - lo stesso bit che la prima
chiamata prende dentro tgain.

  blocchi contigui 20951 -> 20971 (91%)
  a freddo         18964 -> 18972 (69%)
  cal-papd          i frammenti piccoli da 19 a 9, forma 847 2x344 224 182

E' la stessa funzione che b43_nphy_rf_ctl_override_one_to_many() ha gia' rotta
altrove: la mainline b43-program-the-fifth-tx-power-up-override-on-n-phy-rev-7
mette la quinta delle cinque chiamate di TX_PU. Vale la pena rileggerla tutta.

---

E otto maskset su AFECTL_C1/C2, gateate su radio rev 8. La cattura le ha a
#796-#803: bit 2, 3 e 6 a uno e bit 7 a zero, core 0 poi core 1 ogni volta, e
senza toccare la coppia di override accanto. Il riferimento quei bit li tocca solo
nel percorso della tempsense, e la' sempre insieme a 0x8f e 0xa5.

Numeri fermi: la posizione nel port non e' ancora quella del vendore, che le mette
FRA le tabelle dell'ADC ausiliario e le sequenze RF. Spostare le tabelle dell'aux
ADC prima delle sequenze, che e' l'ordine della cattura, costa 24 op: qualcosa in
mezzo dipende dall'ordine e non e' capito. Le otto op stanno dentro perche' la
cattura le ha.

---

---

E la cal TX I/Q LO interna spegne l'override che accende. Al setup fa
rf_ctl_override_rev7(0x8, 0, 0x3, false, 0) - accende il campo 0x8 su tabella 0 - e
niente lo rispegneva: l'override restava acceso su entrambi i core dopo la
calibrazione. Non e' una questione di op: e' stato dell'hardware lasciato dietro.

La cattura lo spegne a #10729 e #10731, subito prima che i gain tornino al loro
posto, e il punto conta: messo dopo stop_playback costa 13 op sulla run di
cal-tx-iqlo, messo attaccato al ntab_write_bulk(7, 0x110, save) ne vale quattro.

  blocchi contigui 20971 -> 20975 (91%)
  a freddo         18972 -> 18976 (69%)
  cal-tx-iqlo       run 443 intatta, un frammento piccolo in meno

Restano due conteggi sul campo 0x2000: il port lo spegne sei volte, il vendore
quattro (#12321, #12777, #13373, #13745). Il port ne fa due per passo con due
passi per core piu' due pulizie; il vendore uno per core piu' due. Prossima voce.

---

---

E la pulizia della cal PAPD rispegne 0x1000 una seconda volta, da solo. L'avevo
togliato io due incrementi fa credendolo un doppione della coppia che ho messo in
testa: non lo e'. La cattura lo ha a #12820 e #13788, dopo 0x800/tabella 0 e prima
di 0x4/tabella 1, e la classificazione dei suoi otto spegnimenti di 0x1000 su 0xe7
lo dice senza ambiguita' - quattro in coppia con 0x2000 e quattro da soli.

  blocchi contigui 20975 -> 20979 (91%)
  a freddo         18976 -> 18980 (69%)

---

---

E lo smoothing della tabella epsilon se ne va. b43_nphy_papd_smooth_epsilon()
leggeva le 64 celle in blocco, mediava su una finestra scorrevole e riscriveva le
prime 41. Non ha NESSUNA fonte: brcmsmac non ha uno smoothing dell'epsilon da
nessuna parte - zero letture bulk delle tabelle 31 e 33 in tutto phy_n.c - e la
cattura non lo fa. Confrontando tutto il traffico sulle due tabelle epsilon, i due
lati differiscono per due sole op per core, ed entrambe sono del port: la TBL.RD
31/0x0 len=64 e la TBL.WR 31/0x0 len=41. Tutto il resto combacia cella per cella,
compreso il curioso off=0x19 che compare tre volte su entrambi i lati.

E non e' una questione di conteggio: quelle 41 celle sono stato dell'hardware, e le
riscrivevamo sopra a quello che la calibrazione aveva prodotto. Un'op che il vendore
non fa e che sovrascrive il risultato della cal e' peggio di un'op mancante.

Numeri fermi - erano op che non appaiavano niente - e il trace perde 213 righe.
Niente nel MESSAGES.md, niente nella nota, niente in docs/: codice senza fonte.

---

---

E la seconda M_CTS_DURATION. Il vendore scrive la durata del CTS DUE volte per
init: 31000 a #10759, prima della cal PAPD, e 10000 a #14949, prima della RX I/Q.
Ha senso fisico - la PAPD trasmette piu' a lungo - e il riferimento ne scrive solo
quella da 10000, e solo nella fase RXCAL. Aggiunta in testa al passo PAPDCAL, con
mac_enable e mac_suspend attorno come l'altra.

  blocchi contigui 20979 -> 20982 (91%)
  a freddo         18980 -> 18983 (69%)

---

E la coppia 0x1000/0x2000 che avevo messo in testa a b43_nphy_papd_cal_cleanup()
se ne va: quelle op non sono della pulizia, sono la CODA di papd_run_one(), che le
emette gia'. La classificazione l'avevo letta male e il confronto posizionale delle
sedici op contestate lo dice senza appello: allineando la coda del passo 2 del core
1, senza la coppia in testa alla pulizia fa 16 su 16, compreso il 0x1000/0x2000 di
#13741-#13748 che avevo attribuito alla pulizia.

Quindi i quattro spegnimenti di 0x2000 del vendore sono due per core NEI PASSI, e
la pulizia non ne fa nessuno. Con la coppia togliata i conteggi combaciano tutti:
0x2000 quattro e quattro, 0x1000 otto e otto, e la classificazione per presenza di
un 0x2000 accanto e' identica op per op - solo, E, E, solo, E, E, solo, solo.

Numeri fermi, otto op spurie in meno. E cade anche l'idea di gatare la coda di
run_one su gain_ctrl: il vendore la fa in entrambi i passi.

---

---

E la pulizia della cal PAPD va DENTRO la seconda parentesi, prima che si chiuda.
Il port faceva run_one, pwr_ctl_close, cleanup; la cattura ferma il tono, rimette
il moltiplicatore e il coupler, cammina la lista degli override a #13749-#13918, e
SOLO DOPO riprogramma la tabella di potenza aggiustata. Trovato col confronto
posizionale: allineando dopo la coda del passo 2, il vendore fa PHY.RD 0xc7
(stop_playback) dove il port faceva PHY.RD 0x1e7 e le 84 celle.

Due righe scambiate:

  blocchi contigui 20982 -> 21074 (91% -> 92%)
  a freddo         18983 -> 19333 (69% -> 70%)
  cal-papd          forma da 847 2x344 224 182 a 847 2x344 316 274
  buco portabile     616 -> 524 op

E' il rapporto migliore fra righe toccate e op recuperate di tutta la serie, meglio
delle due corse della scala TX I/Q LO.

---

---

E in coda alla cal PAPD gli offset epsilon tornano dentro e il motore si accende,
con le riletture di stato che la cattura ha in mezzo. A #13842-#13854: l'adjust per
il core 0, le due letture di 0x2bf e 0x2c0, l'adjust per il core 1, le due letture
di 0x2b1 e 0x2b2, poi il bit di enable su entrambe le catene. Servono quattro nomi
nuovi in phy_n.h per le celle di stato, che b43 non aveva.

Contando registro per registro, ora TUTTI e dieci quelli del motore combaciano:
0x297, 0x298, 0x29b, 0x29c, 0x2a3, 0x2a4, 0x2b1, 0x2b2, 0x2bf, 0x2c0.

Numeri fermi: quelle op cadono dentro un blocco che il matcher non appaia comunque.
Sta dentro perche' e' il bit che ACCENDE il motore, e la cal PAPD senza quello non
serve a niente.

---

---

E la cal PAPD pulsa il reset della valutazione di canale libero. Subito dopo il hold
della carrier search e molto prima delle tabelle, la cattura a #10773-#10776 legge
BBCFG, lo riscrive col bit RSTCCA a uno e poi con RSTCCA e RSTRX a zero. Il port
non lo faceva: aveva solo la write che salva e azzera il reset RX, che la cattura ha
anch'essa ma DENTRO la finestra papd-tables, come PHY.MOD mask=0x8000. Sono due
scritture distinte in due punti distinti, e il port ne aveva una.

Il posto conta e l'ho sbagliato due volte prima di trovarlo: messo al posto della
write esistente, o prima delle tabelle scalari, la run per fase perde 262 op e la
finestra papd-tables passa da ok a noto - perche' il confronto la' e' posizionale e
l'op in piu' sposta tutto. Dopo il hold e prima delle tabelle, tutto torna pieno.

Numeri fermi (21074, 8756, 19333) e papd-tables di nuovo ok. Sta dentro perche' una
singola write del valore azzerato, che e' quello che c'era, lascia lo stesso valore
dietro e non resetta mai la valutazione.

---

---

E la cal TX I/Q LO rimette i registri radio che si prende. b43_nphy_tx_cal_radio_
setup_rev7() salva nove celle per core - TX_SSI_MASTER, IQCAL_VCM_HG, IQCAL_IDAC,
TSSI_VCM, TX_SSI_MUX, TSSIA, TSSIG, TSSI_MISC1 - le riscrive coi valori della
calibrazione, e NIENTE le rimetteva: restavano sporche per tutto il tempo che
l'interfaccia stava su. Sedici registri del radio.

La cattura le ripristina in ordine di indirizzo a #10737-#10752, subito dopo che i
gain di trasmissione tornano al loro posto e prima che il hold della carrier search
si rilasci, coi valori 5, 0, 0, 3, 0xe, 0, 2, 0 sul core 0.

  blocchi contigui 21074 -> 21090 (92%)
  a freddo         19333 -> 19349 (70%)

Sedici op esatte, che e' il numero delle write. Non e' fedelta': e' stato del radio
lasciato dietro da una calibrazione.

---

