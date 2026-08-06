# La calibrazione RX IQ: mappa della cattura

b43 non ha questa calibrazione: `b43_nphy_rev3_cal_rx_iq()` e' **`return -1;`** per
ogni N-PHY rev 3+, e `b43_nphy_cal_rx_iq()` degrada `type` da 2 a 0 quando
`phy->rev >= 7` (vedi `gap-inventory.md` 4a bis). Dietro quello stub stanno **7510
op** della cattura, un terzo della finestra di init: e' il pezzo non portato piu'
grande del driver. Questa e' la mappa, fatta come quella della cal PAPD e per lo
stesso motivo: prima di scrivere il codice serve sapere che forma ha.

Cattura di riferimento: `opinit-ch1-ch6-bw20.decoded`, primo `up` a canale 1.

## I confini

La regione sta fra la fine di `wlc_phy_a4` (#14092) e l'inizio della seconda cal
RSSI (#22247). Non e' delimitata a occhio: le due op che la chiudono sono le
**scritture di lunghezza 2 sulla tabella 7 a `off=0x110`**, cioe' le due voci di
tx gain dei due core insieme, a **#14983** e **#21136**. Tutte le altre scritture
su quella tabella nella regione sono `len=1`, un core per volta.

**SALAME**: che quelle due `len=2` siano il salvataggio e il ripristino del gain
attorno allo sweep e' la lettura piu' naturale della posizione e della lunghezza,
non una cosa che ho verificato sui valori.

## Le funzioni di brcmsmac

`wlc_phy_cal_rxiq_nphy()` smista su `wlc_phy_cal_rxiq_nphy_rev3()`
(`brcmsmac/phy/phy_n.c:27304`), che per ogni core chiama, in ordine:

| funzione | riga | cosa fa |
|---|---|---|
| `wlc_phy_rxcal_physetup_nphy` | 26701 | setup PHY per il core in calibrazione |
| `wlc_phy_rxcal_radio_setup_nphy` | 26197 | setup del radio, per core |
| `wlc_phy_rxcal_gainctrl_nphy` | 27058 | lo sweep di gain, che inoltra a `_rev5` |
| `wlc_phy_rxcal_gainctrl_nphy_rev5` | 26855 | il corpo dello sweep |
| `wlc_phy_rxcal_radio_cleanup_nphy` | 26519 | ripristino radio |
| `wlc_phy_rxcal_phycleanup_nphy` | 26828 | ripristino PHY |

## L'unita' che si ripete

Lo sweep e' fatto di iterazioni con questa forma, leggibile nella cattura per
intero perche' sono tutte table-op:

    TBL.RD  id=0x07 off=0x110|0x111 len=1   il tx gain corrente del core
    TBL.RD  id=0x0f off=0x57 / 0x50 / 0x55  coefficienti IQLOCAL
    TBL.WR  id=0x1a off=0x40 len=84         upload gain core 0
    TBL.WR  id=0x1b off=0x40 len=84         upload gain core 1
    TBL.RD  id=0x1a|0x1b off=0x??de len=1   rilettura di controllo
    TBL.WR  id=0x07 off=0x110|0x111 len=1   il tx gain scelto
    TBL.RD  + TBL.WR id=0x0f off=0x57       read-modify-write dei coefficienti
    TBL.RD  + TBL.WR id=0x0f off=0x5f
    TBL.RD  id=0x1a off=0x15e, 0x1de, 0x25e tre celle a passo 0x80
    TBL.WR  id=0x1a off=0x40 len=84         ri-upload
    TBL.WR  id=0x1b off=0x40 len=84

I due core si distinguono dall'offset sulla tabella 7: **`0x110` e' il core 0,
`0x111` il core 1**, e la cattura alterna.

## Le iterazioni, con i record

Dieci scritture del tx gain e otto toni da 160 word:

| tx gain | core | tono che segue |
|---|---|---|
| #14305 | 0 | — |
| #14728 | 1 | — |
| #14983 | **entrambi** (`len=2`) | — |
| #15293 | 0 | #15508 |
| #16104 | 0 | #16319 |
| #16915 | 0 | #17130, #17542 |
| #18373 | 1 | #18588 |
| #19184 | 1 | #19399 |
| #19995 | 1 | #20210, #20624 |
| #21136 | **entrambi** (`len=2`) | — |

Le prime tre iterazioni non suonano un tono e stanno nella regione che
`phase_compare.py` chiama `cal RX IQ, ingresso` (#14093-15920); dalla quarta in
poi ogni iterazione ha il suo tono, ed e' il `cal RX IQ, sweep di gain`
(#15921-22246). Il tono e' lo stesso stimolo della cal PAPD: tabella 17, 160 word.

## Cosa vuol dire per il port

Non si porta a pezzi, per la stessa ragione di `a2`/`a3`: **le decisioni dipendono
da cosa misura**. Le op sono quasi tutte scritture, ma quali valori vengono
scritti nella tabella 26/27 e nei coefficienti IQLOCAL lo decide il gain trovato
dallo sweep, che a sua volta dipende dalle letture. Un port che scriva la
sequenza senza il calcolo produce le op giuste con i valori sbagliati, che e'
il modo peggiore di sembrare a posto.

Quello che questa mappa rende possibile e' l'ordine di lavoro: `physetup` e
`radio_setup` per core sono scritture pure e verificabili per intero — sono la
stessa categoria del punto 1 di `papd-cal-map.md` — mentre lo sweep vuole i piani
di lettura in ordine, e i piani ora la posizione ce l'hanno
(`test/README.md`, piani posizionali).

## Anche questa sta nella cattura a freddo, ed e' contigua

Verificato: nella parte contigua di `full-init-ch1-bw20.decoded` la fase c'e'
tutta, con lo stesso delimitatore trovato su `opinit-*` — le due scritture di
`len=2` sulla tabella 7 con le voci di tx gain dei due core, a **#25161** e
**#31364** — e in mezzo **otto toni** (#25686, #26497, #27308, #27722, #28774,
#29579, #30390, #30804) e 34 upload di gain su 26/27 a `off=0x40 len=84`. Stessa
forma e stesso conteggio di toni della regione in `opinit-*`.

Quindi **entrambe le cal si scrivono e si verificano offline**: le letture con i
loro valori ci sono, la parte e' contigua quindi il confronto posizionale e'
lecito, e non serve una cattura nuova. Per i piani e la tolleranza vedi la
sezione corrispondente in `papd-cal-map.md`.

## Perche' non si puo' mettere una finestra `pending`

Provato, e non funziona: le fasi non portate della cal PAPD hanno una finestra
`pending` in `phase_compare.py` perche' la loro ancora e' un'op che il port **non
emette affatto**, e non trovarla e' lo stato atteso. Per la cal RX IQ un'op cosi'
non c'e', fra quelle strutturali:

| ancora candidata | perche' non va |
|---|---|
| `TBL.WR id=0x7 off=0x110` (tx gain) | il port ne fa 74 sulla tabella 7, `len=1` e `len=2` comprese: vengono dalla cal TX IQ/LO e dall'indice di potenza |
| op su IQLOCAL (`id=0xf`) | 124 op del port, dalla cal TX IQ/LO |
| le tre celle a passo 0x80 su 26 (`off=0x15e`, `0x1de`, `0x25e`) | `0x25e` compare anche a #1222, fuori dalla fase, e il port ne emette una; la tripla `0x14a`/`0x1ca`/`0x24a` sta anche a #7455-7467, nella cal TX IQ/LO |

Ogni classe di op che questa fase usa la usa anche una fase che il port
implementa. Con un'ancora del genere la finestra non dice `assente`: si aggancia
nel posto sbagliato e riporta una divergenza inventata — l'ho misurata, 5/215 e
172/5596, due false "da guardare". E' la trappola 6 al rovescio, e il limite e'
dello strumento: l'aggancio e' **una** op, e a questa fase servirebbe una
sequenza. Non ritentare senza aver prima cambiato quello.

Ricaduta oltre le op: lo stub torna **-1**, e in `b43_phy_initn` la `save_cal` sta
dietro `if (b43_nphy_cal_rx_iq(...) == 0)`, quindi finche' c'e' lo stub **non
viene mai salvata una calibrazione**, ne' dal ramo `perical != 2` ne' dalla
sequenza di `0014`.
