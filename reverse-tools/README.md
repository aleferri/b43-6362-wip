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
  o `NREV_IS(phy_rev, 8)`, con la riga di partenza. Genera
  `docs/brcmsmac-xref.md`.
- **cfuncs.py** — localizzazione riga→funzione per sorgenti in stile kernel,
  usata dai due sopra. Non è un parser C: euristica a profondità di graffe.

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

- **gen_syms.py** — costruisce la riga `syms=` per l'insmod da un
  `/proc/kallsyms` copiato dal device. La lista `WANTED` deve combaciare con gli
  `hooks[]` del modulo: se divergono, il tracer ha buchi silenziosi.
- **csanity.py** — controlli su file C senza compilatore (commenti non chiusi,
  parentesi sbilanciate, dichiarazione dopo statement per i target C90). Da
  passare sui `wl_diag.c` **prima** di buildare sul router. Non usarlo sul
  codice destinato a mainline: là la regola C90 segnalerebbe casi legittimi.

## Pipeline di decodifica

Ordine: decodifica → fold RETVAL → fold MOD → (collapse) → confronto.

- **decode-wl-diag.py** — record binari (28 B BE) → righe testuali.
- **merge_retvals.py** — ripiega i `RETVAL` nella lettura che li precede.
- **fold_mod_reads.py** — ripiega la read implicita di ogni `MOD`.
- **collapse_trace.py** — compatta le table-op. Per il confronto op-per-op col
  port usare il trace **grezzo**, non il collassato.
- **diff_traces.py** — differenziale fra due catture, per isolare le dipendenze
  da board o da canale.
- **mempeek.c** — lettore `/dev/mem` a 32 bit per ispezionare una finestra del
  backplane dal device.

Il resto della pipeline AC (localizzazione funzioni, copertura, decorrelazione
canale/BW, estrattori AC-PHY) sta in `b43-ac-wip` e si riusa da lì senza
modifiche: non è stato duplicato qui.
