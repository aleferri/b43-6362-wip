# Protocollo di cattura

Una cattura serve a due cose: sapere cosa il vendor scrive, e poter confrontare
op-per-op il port con quella sequenza. Se una cattura non permette il confronto
posizionale, è quasi inutile.

## Prima di premere insmod

1. `arm=0` (default): il modulo logga solo il piano di patch. Leggerlo. Se un
   simbolo non è stato risolto, va risolto ora, non dopo. I nomi attesi sono
   quelli in `docs/blob-inventory.md`: se manca `and_radio_reg` o `or_radio_reg`,
   quel blob usa nomi diversi e il tracer ha un buco silenzioso.
2. `insmod wl_diag.ko arm=1` basta: il modulo si cerca i simboli in
   `/proc/kallsyms` da sé. `syms=` e `klookup=` restano come ripiego se un blob
   usa nomi che la lista non prevede.
3. La cattura si legge da **`/proc/wl_diag`**, che esiste appena il modulo è
   caricato: `cat /proc/wl_diag | nc <host> 5555`. La pipe deve **drenare** prima
   di far partire la sequenza, non essere solo lanciata: la fifo tiene 32768
   record e un init a freddo ne emette più del doppio.
4. Annotare versione del blob, board, canale, banda, e se il radio è l'integrato
   (`0x14e4:0x435f` sul backplane) o una scheda PCIe.

## Cosa catturare, in che ordine

Una sequenza per volta, con il device fermo fra una e l'altra:

| flow | come si ottiene | a cosa serve |
|---|---|---|
| `attach` | reload di `wl` | init radio + initvals |
| `op_init` | `wl up` da down | sequenza di init PHY completa |
| `switch_channel` | `wl channel N` su tutti i canali 1-13 | chantab, spuravoid, loopfilter |
| `rfkill` | `wl radio on/off` | percorsi di power up/down |
| `cal` | `wl phy_forcecal 1` | rcal/rccal, tx iq/lo, papd |

Per il 6362 integrato **non c'è rescan PCI**: il ciclo attach si riottiene con
reload del modulo o `wl down; wl up`.

## Cosa rende una cattura inutile

- record persi (`OP_DROP` > 0): la fifo è andata in overflow, la sequenza ha
  buchi e il confronto posizionale salta. Ridurre il flow catturato, non
  aumentare il filtro.
- più flow nello stesso file senza marcatori: non si separano più a posteriori
  con certezza.
- filtro `skipphyrd` attivo senza averlo scritto nel verbale: si finisce a
  cercare per mezz'ora una `PHY.RD` che era stata scartata a monte.
- catture su canale diverso da quello dichiarato: metà delle differenze
  diventano inspiegabili.

## Dopo la cattura

```sh
decode-wl-diag.py < raw.bin > flow.decoded
verify_decode.py raw.bin flow.decoded    # prima di buttare il binario
merge_retvals.py flow.decoded > flow.rv
fold_mod_reads.py flow.rv > flow.folded
```

Nel repo va il **decodificato**, non il binario: è leggibile, diffabile, e
grepabile, ed è la forma che gli strumenti mangiano. Il binario si butta solo
dopo che `verify_decode.py` dice che il testo copre tutti i campi non nulli; se
segnala perdite, si sistema il decoder e si rifà, non si tiene il binario come
scusa.

Poi i controlli che non costano niente e trovano cose: `verify_chantab_trace.py`
per confrontare la chantab di b43 con tutti i cambi canale della cattura, e
`trace_tables.py` per tirare fuori i payload delle table-op.

Il confronto col port si fa sul trace **grezzo** (non collassato), con
`test/compare.py`. Il collassato serve per le analisi macro, non per il gate di
regressione.

Ogni cattura va in `router-data/<board>/` con il verbale accanto: senza il
verbale, fra tre mesi il file è un blob di byte.

## `wl down; wl up` NON basta per il download statico

Il percorso di down del blob **non azzera `hw_up` in `pub`**, quindi quel ciclo rifa'
solo un init parziale. Per l'init col download statico serve, fra il down e l'up, una
**writemem** che azzeri quel flag: il successivo up passa da `hw_up()` ->
`wlc_phy_por_inform()` e il PHY si reinizializza per intero, tabelle statiche e
rcal/rccal comprese.

Misurato su una cattura vd630 presa col solo `down`/`up`: **zero occorrenze** di
`PHY.WR addr=0x72 val=0x2800`, l'apertura della tabella 10. Il file si chiamava
`fullinit.txt` e non conteneva il download statico — il nome non e' il criterio, il
grep lo e'.

Per arrivare al flag serve il base pointer dei dati privati, che `wl_diag` stampa in
dmesg. Se le `netdev_ops` non si risolvono per nome, ora c'e' un ripiego che non usa
simboli: riconosce l'interfaccia perche' le sue `netdev_ops` cadono **dentro il
modulo wl** (`__module_address`). Gli offset per camminare da `priv` a `pub` sono
per versione: quelli annotati in `wl_diag.c` sono del blob 6.30 e su 7.14 non valgono.

### Il poke a comando

`poke=` come parametro spara a `insmod`, cioe' prima del `wl down`: per questa
sequenza non serve. Da usare invece il write handler su `/proc/wl_diag`:

```sh
insmod wl_diag.ko arm=1              # priv= in dmesg
cat /proc/wl_diag | nc host 5555 &   # drenare PRIMA
wl down
echo 'r   <priv> 64'  > /proc/wl_diag   # per trovare pub, dump in dmesg
echo 'w8  <addr> 0'   > /proc/wl_diag   # azzera hw_up
wl up
```

Larghezze: `w8`, `w16`, `w32`, piu' `r <addr> <n>` che dumpa in dmesg. Su MIPS un
`w32` su indirizzo non allineato prende un address error, quindi l'handler lo
rifiuta. Il risultato va in **dmesg** e non nella fifo, che resta la cattura.

E la scrittura va fatta da dentro il kernel e non con un writemem da userspace via
`/dev/mem`: gli indirizzi di un modulo stanno in spazio **vmalloc** (`0xc1...`,
`0xc2...` nei log), che non e' raggiungibile con l'offset fisso di KSEG0 — servirebbe
camminare le page table.
