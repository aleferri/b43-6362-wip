# reverse-tools

Strumenti per lavorare sul supporto N-PHY rev 8 / radio 2057 rev 8 del BCM6362.
Tre famiglie: analisi del tree kernel, estrazione dal blob OEM, cattura e
decodifica delle tracce del driver `wl`.

## Analisi del tree kernel

- **check_gaps.py** — per ogni funzione b43 che discrimina su `phy->radio_rev` o
  `phy->rev`, dice se la revisione target è coperta, trattando `>=`/`<=` come
  copertura e segnalando gli stub (corpo di soli commenti). Genera la tabella di
  `docs/gap-inventory.md`. Dà indizi: una voce `assente` può essere legittima,
  va letta a mano.
- **brcmsmac_xref.py** — elenca le funzioni brcmsmac che discriminano radiorev 8
  o `NREV_IS(phy_rev, 8)`, con la riga del primo match dentro la funzione (non
  quella in cui la funzione comincia). Genera
  `docs/brcmsmac-xref.md`.
- **cfuncs.py** — localizzazione riga→funzione per sorgenti in stile kernel,
  usata dai due sopra. Non è un parser C: euristica a profondità di graffe.

- **phy_type_audit.py** — elenca i costrutti dove b43 discrimina sul tipo di PHY
  e cita la G senza la N. Genera `docs/phy-g-only.md`. Euristica testuale: vede la
  presenza del caso N, non la sua correttezza.
- **check_patch_gating.py** — per ogni riga aggiunta da una patch cerca un gate di
  revisione che la domini. Serve perché nel PHY di b43 quasi tutto è condiviso fra
  tutte le N-PHY, e una modifica non iffata cambia hardware che non possiamo
  provare. Euristica, non parser: un `NON GATEATA` va guardato. Vedi
  `docs/upstreaming.md` per l'elenco delle funzioni condivise e il gate che
  ciascuna vuole. Distingue il gate sulla revisione da quello sul **tipo** di PHY,
  che è legittimo ma tocca tutte le rev di quel tipo. Vuole un albero **pulito**:
  se la patch è già applicata lo dice invece di fallire in modo oscuro.

## Estrazione dal blob OEM

- **blob_tables.py** — lettore ELF32 big-endian senza dipendenze. `--list` per
  gli elenchi di simboli, `--dump` per l'hexdump, `--verify SYM --against
  FILE:ARRAY` per confrontare una tabella del kernel col simbolo del blob
  deducendo lo stride del record vendor dal matching della colonna indirizzi.
  È il modo di rispondere alla domanda "questa tabella merged è davvero quella
  del vendor?": vedi `PROVENANCE.md` per gli esiti.
- **chantab_from_blob.py** — la chantab non è un array piatto, è un array di
  struct: questo strumento mappa i record da 44 byte di
  `chan_info_nphyrev8_2057_rev8` sui campi di `b43_nphy_chantabent_rev7`,
  confronta il sottoinsieme 2.4 GHz con l'array in `radio_2057.c` (`--verify`),
  elenca la copertura per banda (`--list`) ed emette entry C per la banda
  richiesta (`--emit-c --band 5g`).

## Tracer sul device

- **wl-diag/** — modulo tracer a detour inline (niente kprobe) per un host con
  kernel 3.4-rt.
- **wl-diag-2630/** — stesso sorgente per il kernel 2.6.30 dello stock firmware
  della DSL-3580L. **È questa la variante per il radio integrato**, perché gira
  sul SoC stesso.

Entrambe sono tarate su N-PHY: vedi la sezione "Riposizionamento su N-PHY" nella
loro README per l'elenco delle differenze rispetto alla copia AC-PHY di
`b43-ac-wip`, tutte verificate sul blob di questa board.

## Pipeline di decodifica

Ordine: decodifica → fold RETVAL → fold MOD → (collapse) → confronto.

- **decode-wl-diag.py** — record binari (28 B BE) → righe testuali.
- **gen_readplans.py** — appaia ogni read della cattura col suo `RETVAL` ed emette
  i piani di lettura dell'harness come header C, per indirizzo. Esclude 0x72/0x73/
  0x74, che sono la porta delle tabelle e non un registro di stato. Misurato: non
  spostano la copertura, vedi `test/README.md`.
- **verify_decode.py** — ricostruisce i campi dal testo decodificato e li
  confronta col binario record per record. È la condizione per buttare il
  binario: se dice "nessuna perdita", il testo lo sostituisce; se elenca campi,
  il decoder va sistemato. Ha già trovato due buchi: il selettore di spazio
  delle `OBJ.RD`/`OBJ.WR` e il puntatore al buffer delle `TPL.RAMW`, che la
  branch generica del decoder non stampava.
- **merge_retvals.py** — ripiega i `RETVAL` nella lettura che li precede.
- **fold_mod_reads.py** — ripiega la read implicita di ogni `MOD`.
- **collapse_trace.py** — compatta le table-op (porte N-PHY 0x72/0x73/0x74). Per
  il confronto op-per-op col port usare il trace **grezzo**, non il collassato.
- **test/coverage.py** — copertura per classe, e con `--values` confronta il primo
  valore scritto su ogni registro toccato da entrambi: è la classe di differenza
  che la sola presenza non vede, e ha trovato il TSSI. Vuole il port sullo stesso
  canale della cattura, altrimenti la chantab produce falsi positivi.
- **trace_tables.py** — riassocia ogni `TBL.WR` alle `PHY.WR` su 0x72/0x73/0x74
  che la implementano e stampa i valori, con controllo di coerenza fra
  intestazione e dati (indirizzo = `(id << 10) | off`, conteggio = `len`). Con
  `--c-array` li emette come array C. È così che sono stati ricavati i numeri di
  `patches/b43/MESSAGES.md#0001`.
- **verify_chantab_trace.py** — per ogni `CHANSPEC` del trace confronta i 18
  campi della chantab 2.4 GHz di b43 con le scritture radio che seguono, valore
  e ordine. Verifica su tutti i canali che la cattura tocca invece che su uno
  scelto a mano, ed elenca a parte i registri 5 GHz che il vendore azzera.
- **diff_traces.py** — differenziale fra due catture, per isolare le dipendenze
  da board o da canale.
- **mempeek.c** — lettore `/dev/mem` a 32 bit per ispezionare una finestra del
  backplane dal device.

Il resto della pipeline AC (localizzazione funzioni, copertura, decorrelazione
canale/BW, estrattori AC-PHY) sta in `b43-ac-wip` e si riusa da lì senza
modifiche: non è stato duplicato qui.
