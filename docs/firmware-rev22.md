# Firmware per il d11 core rev 22

## Cosa cerca b43

Il commit `682edc28b91c` ha aggiunto i mapping per il corerev 22:
`ucode22_mimo`, `n0initvals22`, `n0bsinitvals22`. Sono i nomi che b43 chiede a
`/lib/firmware/b43/` dopo l'estrazione.

## Cosa serve per averli

`b43-fwcutter` estrae in base a un md5 del blob `wl` e a una descrizione dei
suoi contenuti. Le versioni impacchettate da OpenWrt per b43 sono vecchie
(4.150.10.5, 4.178.10.4, 5.10.56.27, 5.100.138), e nessuna di quelle contiene
un ucode per un core rev 22: quello arriva dai blob 6.30-era, come il
`wl 6.30.102.7` della DSL-3580L.

**Da verificare sul tuo setup, non l'ho fatto io:**

```sh
b43-fwcutter -w /tmp/fw wlDSL-3580_EU.o_save
ls /tmp/fw/b43/ | grep -E 'ucode22|initvals22'
```

Tre esiti possibili:

1. escono i tre file → non c'è nulla da fare, va solo documentata la
   provenienza in `router-data/dsl-3580l/`;
2. fwcutter non riconosce il blob (md5 sconosciuto) → serve una voce nuova nel
   suo elenco, patch da mandare a monte del fwcutter;
3. fwcutter riconosce il blob ma non estrae il rev22 → la descrizione del
   contenuto è incompleta per questa versione.

Nel caso 2 o 3, il blob resta la fonte: i simboli sono leggibili con
`nm`/`objdump` e il `reverse-tools/blob_tables.py` sa già estrarre regioni per
simbolo, quindi il lavoro è capire l'incapsulamento, non trovare i dati.

## Perché conta per HT20 2x2

`ucode22_mimo` è l'ucode che il vendor usa per l'11n su questo core: senza la
certezza che sia quello caricato, ogni conclusione su un TX HT che non funziona
è ambigua fra "il driver programma male il PHY" e "l'ucode non fa 11n". Va
chiuso prima di M3.
