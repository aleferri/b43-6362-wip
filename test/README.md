# test

`compare.py` (importato da `b43-ac-wip`) è il confronto canonico: match
posizionale per sequenza fra l'output dell'harness e la cattura vendor
**grezza**. È la misura di correttezza del port e il gate di regressione.

Per il 6362 non c'è ancora un harness: va costruito quando ci sarà la prima
patch PHY da validare (M0 del piano). Fino a quel momento questa cartella
contiene solo lo strumento di confronto.

Nota: usare il trace grezzo, non il collassato. Il collassato serve alle analisi
macro e produce falsi disallineamenti nel confronto op-per-op.
