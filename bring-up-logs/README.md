# bring-up-logs

Log grezzi con il contesto. Un `dmesg` senza il commit a cui si riferisce non è
riproducibile, quindi ogni file va nominato

    <data>-<board>-<cosa>.log

e comincia con quattro righe di intestazione:

    kernel:  <versione>
    tree:    <sha>
    patch:   <serie applicata>
    atteso:  <cosa doveva succedere>

Poi il log. In coda, una riga su cosa è effettivamente successo se diverge.
