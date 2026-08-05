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

`b43/0006` non ha citazioni, e resta senza: misura una cosa che il vendore in quella
cattura non fa.

`mainline/` sono **due patch separate**, non una serie, per difetti di mainline
indipendenti da questo hardware: vanno inviate per prime e in due thread distinti,
vedi `patches/mainline/README.md`. `b43/` e' la serie di questo lavoro, e si applica
come un blocco; `b43/0010` porta le stesse due modifiche della prima patch mainline
e uscira' quando quella entra.
