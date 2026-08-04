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

## Le routine condivise vanno iffate, o è un nack

Nel PHY di b43 quasi tutto è condiviso fra tutte le N-PHY: le stesse funzioni
girano su rev 1 come su rev 17. Una modifica non gateata cambia il comportamento
di hardware che non abbiamo, non possiamo provare, e di cui non abbiamo catture —
e questo è un nack immediato, a ragione.

Le due patch scritte finora sono a posto: `0001` sta in
`b43_nphy_gain_ctl_workarounds_rev7()`, che è già rev-specifica per nome, e ha in
testa un `if (phy->radio_rev != 8 || 40 MHz || 5 GHz) return`; `0002` è un cambio
di soli dati in un array che `b43_nphy_get_rf_pwr_offset_table()` ritorna solo per
`phy->rev == 8 && phy->radio_rev == 8`.

Il rischio sta nel lavoro che viene dopo. Queste sono le funzioni che le voci
aperte dell'inventario portano a toccare, tutte condivise, con il gate che
servirebbe:

| funzione | chi la usa | gate necessario |
|---|---|---|
| `b43_nphy_op_prepare_structs` | **ogni** N-PHY | è dove sta `perical = 2`: non si tocca. Il knob per girare con la cal accesa vive nell'harness (`test/main.c`), non nel driver |
| `b43_radio_2057_chantab_upload` | radio rev 5, 8, 9, 14 | i dieci registri 5 GHz azzerati (voce 5b) vanno dietro `radio_rev == 8`, o si cambia il cambio canale di 43217, 43227 e dei rev 9/14 |
| `b43_nphy_tx_pwr_ctl_init` | tutti i rev 7+ | togliere l'early return vale per rev 8 con radio rev 8, non per l'intero rev 7+: 16/17 con radio 9/14 non li abbiamo |
| `b43_nphy_workarounds_rev7plus`, `b43_nphy_gain_ctl_workarounds` | dispatcher rev 7+ | qualsiasi aggiunta va in un ramo per revisione, non nel corpo comune |
| `b43_supported_bands` | ogni device b43 | il caso `dev_id 0x435f` (voce 6) non deve cambiare le bande annunciate dagli altri dual band |

`reverse-tools/check_patch_gating.py` lo controlla meccanicamente: per ogni riga
aggiunta trova la funzione che la contiene nel file dopo la patch e cerca un gate
che la domini — nome rev-specifico, early return su rev, oppure un `if`/`case`
sulla revisione. È un'euristica su brace depth e non un parser C, quindi un
`NON GATEATA` va guardato e non ubbidito alla cieca; ma su una modifica di prova
dentro `b43_nphy_op_prepare_structs` la becca.

```sh
./reverse-tools/check_patch_gating.py --tree ~/src/linux patches/b43/*.patch
```

## Non proponibile ora: HT

Vedi `ht20-mimo-plan.md`. Prima M0-M2, e con i report in mano.
