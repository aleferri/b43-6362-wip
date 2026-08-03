# Cosa è proponibile e cosa no

## Proponibile quasi così

`patches/bcma/0001` e `0002`. Sono contenute, non toccano il comportamento
degli host esistenti (i due nuovi campi sono `false` per tutti gli altri) e la
motivazione tecnica è verificabile sul silicio. Da fare prima dell'invio:

- passare `0003` (binding) sotto `dt_binding_check`, che io non ho eseguito;
- decidere se tenere il riferimento al BCM63268 nella descrizione: il chip ha
  un blocco analogo ma se non è testato è meglio non citarlo come supportato;
- verificare che il teardown sia corretto su `rmmod bcma` con il d11 ancora
  legato, non solo sul percorso felice.

## Non proponibile così: la SPROM

Questo è l'ostacolo vero. Nel fork la SPROM del core su SoC arriva da
`brcm,bcma-sprom` con `bcma-bus = <&wlan>`, che è un driver **solo OpenWrt**
(`target/linux/generic/files/drivers/bcma/fallback-sprom.c`): mainline non ha
nessun meccanismo per servire una SPROM da device tree. L'unico gancio upstream
è `bcma_arch_register_fallback_sprom()`, usato da bcm47xx da codice
arch-specifico.

Tre strade, in ordine di costo crescente per chi le deve far accettare:

1. **fallback arch-specifico per bmips**, sul modello di
   `arch/mips/bcm47xx/sprom.c`: legge i parametri dalla NVRAM CFE e li
   trasforma in `struct ssb_sprom`. Segue un precedente accettato, ma su bmips
   che è DT-only aggiunge codice arch che il target ha evitato finora.
2. **binding DT nuovo** per una SPROM fornita da nvmem/firmware: la strada
   pulita, e la più lunga, perché va discussa con i maintainer del DT e non solo
   con quelli di bcma/b43.
3. **niente SPROM**: derivare tutto da default per chip. Non regge: i 38 fixup
   della DSL-3580L includono calibrazioni PA per catena, cioè roba per board.

Da decidere prima di scrivere codice, perché cambia dove vive il parsing.

## Non proponibile ora: HT

Vedi `ht20-mimo-plan.md`. Prima M0-M2, e con i report in mano.
