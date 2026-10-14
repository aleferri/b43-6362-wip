# patches

Ogni patch porta la propria **provenienza in trailer**, con `Link:` per ogni URL,
uno per riga, che e' il nome che il tooling del kernel conosce:

    Link: https://git.kernel.org/.../brcmsmac/phy/phy_n.c?id=848acc8ffe1b#n23018
    Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/router-data/...decoded
    Link: https://github.com/aleferri/b43-6362-wip/blob/e916c8a/test/phase_compare.py

Il sorgente del kernel va su **git.kernel.org e pinnato allo sha**: senza `?id=`
l'URL punta a master e il numero di riga smette di essere quella riga al primo
commit che tocca il file sopra.

La cattura ha il suo `Link:`, ma **l'intervallo di record e la prima op stanno nel
corpo**, non in un'ancora: quel file e' 4,4 MB e 70796 righe, GitHub non lo rende e
`#L8638-L8959` finisce su un prompt di download. L'op va citata **con la spaziatura
del file**, non normalizzata come la stampano gli strumenti, o `grep -F` non la
trova.

`b43/MESSAGES.md#0006` non ha citazioni, e resta senza: misura una cosa che il vendore in quella
cattura non fa.

`mainline/` sono **dodici patch separate**, non una serie, per difetti di mainline
indipendenti da questo hardware: vanno inviate per prime e in dodici thread distinti,
vedi `patches/mainline/README.md`, che e' la fonte per l'elenco.

La serie b43 non sta qui come patch: il codice sta in `../b43/`, file interi, e
`scripts/series-diff.sh` la stampa come diff unico sopra `mainline/`. I suoi
messaggi — razionale, misure, intervalli di record, trailer `Link:` — sono in
`b43/MESSAGES.md`, che e' anche cio' da cui ripartire per ridividere. Le citazioni
per numero sparse nei documenti e in `test/unit/phase_compare.py` risolvono contro quel
file.

Quel diff non contiene `0010` e `0022`, che erano duplicati di due delle mainline:
niente conflitto atteso da gestire, e niente di perso, vedi `b43/NOTES.md`. Il
prezzo pagato e' che `check_patch_gating.py` non da' un verdetto per patch ma uno
per tutta la serie, quindi le eccezioni dichiarate sono raccolte in `b43/NOTES.md`
invece che una per messaggio.

`0001`-`0003` sono la serie bcma, generata da `../bcma/` con
`scripts/regen-patches.sh` sull'albero di `regen-base`: si edita `bcma/`, non le
patch, tranne che per il messaggio.

**Le mainline stanno anche nel baseline delle misure**: due di loro valgono 22 op
sulla finestra `up-ch1`. Vedi `CLAUDE.md`, "Setup, ogni volta".
