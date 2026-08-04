# D-Link DSL-3580L

BCM6362 con radio 2.4 GHz integrato (N-PHY rev 8, radio 2057 rev 8) e una
scheda PCIe BCM4352 per il 5 GHz. Qui interessa solo il radio integrato.

Blob OEM di riferimento: `wl 6.30.102.7.cpe4.12L07.0` (`wlDSL-3580_EU.o`), non
incluso nel repo perché proprietario.

## Cosa mettere in questa cartella

| file | contenuto |
|---|---|
| `srdump.txt` | output di `wl srdump` dallo stock firmware |
| `nvram.txt` | NVRAM CFE rilevante (chiavi wl*) |
| `kallsyms.txt` | `/proc/kallsyms` dello stock, per `gen_syms.py` |
| `<flow>.decoded` | catture del tracer decodificate, una per flow |
| `<flow>.md` | verbale della cattura: comandi, canale, banda, filtri attivi |

I binari del tracer **non si committano**: il testo decodificato è la forma
utile e il binario non aggiunge nulla, purché prima si verifichi che il testo
non perda campi (`reverse-tools/verify_decode.py`). Nel verbale vanno la
dimensione e lo sha256 del binario di partenza, così la conversione resta
verificabile a posteriori.

Le catture vanno accompagnate dal verbale. Un `.raw` senza verbale non è un
dato, è un file.

Vuota di proposito: niente dati inventati.
