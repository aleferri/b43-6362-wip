# D-Link DSL-3580L

BCM6362 con radio 2.4 GHz integrato (N-PHY rev 8, radio 2057 rev 8) e una
scheda PCIe BCM4352 per il 5 GHz. Qui interessa solo il radio integrato.

Blob OEM di riferimento: `wl 6.30.102.7.cpe4.12L07.0` (`wlDSL-3580_EU.o`), non
incluso nel repo perché proprietario.

## Cosa mettere in questa cartella

I binari del tracer **non si committano**: il testo decodificato è la forma
utile e il binario non aggiunge nulla, purché prima si verifichi che il testo
non perda campi (`reverse-tools/verify_decode.py`). Nel verbale vanno la
dimensione e lo sha256 del binario di partenza, così la conversione resta
verificabile a posteriori.

Le catture vanno accompagnate dal verbale. Un `.raw` senza verbale non è un
dato, è un file.

Dentro ci sono due catture decodificate col verbale accanto — `opinit-ch1-ch6-bw20`
(init a caldo, due cicli, senza perdite) e `full-init-ch1-bw20`, descritta qui
sotto — piu' `nvram.txt` e `srdump.txt` del device.

## `full-init-ch1-bw20.decoded`

Init **a freddo** su canale 1, 20 MHz, radio integrato, wl 6.30.102.7. 81397 record.

Ottenuta azzerando `hw_up` con `setmem` e rifacendo `wl up`, cosi' il PHY
reinizializza per intero: contiene il **download delle tabelle statiche**, che la
`opinit-*` non ha perche' e' un init a caldo. Il marcatore e' `PHY.WR addr=0x0072
val=0x2800`, l'apertura della tabella 10, a #3569.

**Ha un buco**: 65285 record persi in un solo salto fra `#32769` e `#98055`, per
overflow della fifo -- il lettore non drenava durante la raffica, e `#32769` e'
esattamente `FIFO_RECS + 1`. I record **da #2 a #32769 sono contigui** e contengono
l'init intero compresa la cal PAPD (tabella scalare a #18662), quindi quella parte e'
confrontabile posizionalmente. Oltre il buco c'e' un secondo ciclo, non contiguo col
primo.

Per rifarla senza il buco: la pipe di lettura deve essere attiva **e drenare** prima
del `setmem`, non solo lanciata.

### Come e' stata ottenuta

Il driver era **su** e poi giu': `hw_up` resta a 1 perche' il percorso di down del blob
non lo azzera, quindi un `wl up` da la' rifa' solo un init parziale. Azzerandolo a mano
il successivo up passa da `hw_up()` -> `wlc_phy_por_inform()` e il PHY reinizializza per
intero.

L'ordine conta: la pipe di lettura deve **drenare** prima che parta la raffica, o la
fifo (32768 record) va in overflow — che e' come si e' preso il buco di questa cattura.

```sh
# 1. tracer armato. In dmesg escono i base pointer delle istanze:
insmod wl_diag.ko arm=1
#    wl_diag: wl0: priv=82ac34e0 (netdev=82ac3180, ops=wl_dslcpe_netdev_ops)

# 2. dal priv di wl0 si cammina fino a hw_up. Gli indirizzi sono di QUELLA
#    istanza e cambiano a ogni caricamento di wl: rifare i dumpmem ogni volta.
dumpmem 0x82ac34e0 8      # priv -> wl_if            = 0x83af4e00
dumpmem 0x83af4e00 8      # wl_if + 0x04 -> radio    = 0x82a49000
dumpmem 0x82a49000 32     # radio + 0x04 -> pub      = 0x82a4bc80
dumpmem 0x82a4bc80 48     # pub + 0x2c = hw_up, deve valere 01

# 3. la pipe, e verificare che il file sull'host CRESCA prima di procedere
cat /proc/wl_diag | nc <HOST> 5555 &

# 4. azzerare hw_up, e rileggerlo
setmem 0x82a4bcac 0 1
dumpmem 0x82a4bcac 4      # il primo byte deve essere 00

# 5. e via
wl up
```

Sull'host: `reverse-tools/decode-wl-diag.py < grezzo > cattura.decoded`.

Tenere **`wl1` giu'**: i suoi hook scrivono nella stessa fifo e le due sequenze si
mescolano, e il confronto posizionale si regge tutto sul non averle mescolate.

La prova che l'init e' stato a freddo non e' il byte riletto, e'
`PHY.WR addr=0x0072 val=0x2800` nel trace — l'apertura della tabella 10, con cui
comincia il download statico. Se non c'e', l'init e' stato di nuovo parziale.

La catena di puntatori e' verificata leggendo la memoria del device, non dedotta da
brcmsmac: `wl_if+0x8` e' il netdev e combacia col log, `pub` e `wlc` si puntano a
vicenda a offset 0, e `hw_up` a `pub+0x2c` valeva 01 con l'interfaccia su e 00 dopo il
`setmem`. Gli offset che avevo dedotto dal disassemblato di brcmsmac erano sbagliati.
