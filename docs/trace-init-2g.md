# Il trace di init 2.4 GHz della DSL-3580L

Cattura con `wl-diag-2630` sul firmware stock, blob `wl 6.30.102.7`, radio
integrato del BCM6362 (N-PHY rev 8, radio 2057 rev 8), 2.4 GHz bw20.

Il flow sono **due cicli `wl down` / `wl up`**, non un attach: il primo con
canale operativo 1, il secondo con canale operativo 6. Fra i due, 15 s di radio
giù. In entrambi i cicli il driver esce dal canale operativo ogni 2 s — a ch5 nel
primo, a ch2 e ch10 nel secondo — e rientra subito.

Il dato sta in `router-data/dsl-3580l/opinit-ch1-ch6-bw20.decoded`, decodificato;
il binario non è nel repo (vedi il verbale accanto per sha256 e verifica di non
perdita).

## Qualità della cattura

70796 record, 39.8 s, **zero `OP_DROP` e zero discontinuità di sequenza**:
niente perdite, quindi il confronto posizionale col port è lecito.

| record | contenuto |
|---|---|
| 1 - 131 | init radio iniziale (45 `RAD.WR`) |
| 132 - 26100 | primo `up`, canale 1: init PHY completo (16834 `PHY.WR`, 771 `TBL.WR`) |
| 26101 - 34156 | 7 escursioni a ch5 e ritorno |
| 34157 - 34937 | `down` e 15 s di attesa: 781 record, `GPIO.CTL`/`GPIO.OUT`, 15 `MAC.MCTRL` |
| 34938 - 61971 | secondo `up`, canale 6: init PHY completo (16855 `PHY.WR`, 775 `TBL.WR`) |
| 61972 - 70796 | 5 cicli ch2 / ch10 / ch6 |

**Due sequenze di init, non una.** Averne due su canali operativi diversi è la
cosa più utile della cattura: permette di distinguere ciò che dipende dal canale
da ciò che è fisso.

Istogramma: 38616 `PHY.WR`, 11049 `RETVAL`, 9410 `PHY.RD`, 2314 `OBJ.WR`, 1901
`PHY.MOD`, 1606 `TBL.WR`, 1314 `RAD.WR`, 1251 `OBJ.RD`, 856 `PHY.OR`, 781
`PHY.AND`, 570 `TBL.RD`, 332 `RAD.RD`, 223 `PHY.ARRW`, 184 `RAD.MOD`, più i
marcatori.

## Cosa ha risolto sul tracer

Tre incertezze che erano annotate come tali nel codice del tracer:

- **`phy_reg_write_array`**: il secondo argomento è il numero di **word**, non
  di record. `#5 PHY.ARRW val=0x000c` seguito da 4 `PHY.WR` → 12 word, record da
  3 word. E la scelta di agganciarla come solo marcatore è confermata giusta:
  tutte le op che ne discendono sono nel trace via gli accessor.
- **ordine `len`/`off` in `wlc_phy_table_write_nphy`**: risolto. Gli offset
  osservati (0x00, 0x04, 0x08, 0x20, 0x10, 0x1c) e le lunghezze (1, 2, 4, 10)
  hanno senso solo nell'assegnazione attuale del decoder; invertite darebbero
  `len=0`.
- **`si_pmu_spuravoid`, `and_radio_reg`, `or_radio_reg`**: **zero** record in
  tutta la cattura, e zero record PMU di qualsiasi tipo. Su questo SoC il
  clocking non passa dal PMU bcma, quindi è coerente; gli hook restano perché
  non costano nulla, ma non aspettarsi record da lì.

## Cosa ha confermato del kernel

**La chantab merged è quella giusta, su tutti i canali che la cattura tocca.**
`reverse-tools/verify_chantab_trace.py` confronta i 18 campi della variante 2.4
GHz per ogni `CHANSPEC`: **31 cambi canale su 31, zero differenze**, sui cinque
canali presenti (1, 2, 5, 6, 10), con gli stessi valori e nello stesso ordine in
cui `b43_radio_2057_chantab_upload()` li scrive. Per esempio al passaggio a ch5:

    016=55 017=16 022=30 025=1b 027=0a 028=0a 029=30 02c=80 02d=09
    037=0f 041=09 047=06 05c=61 05e=73 09a=f0 0e1=61 0e3=73 11f=f0

Include `R1=0x1b`, `C1=C2=0x0a`, `CP_KPD_IDAC=0x30`, cioè la conferma sul
silicio che il `case 8` mancante in `b43_radio_2057_setup()` è un no-op (vedi
`gap-inventory.md`, voce 2), e la conferma vale su cinque canali diversi, non su
uno.

## Cosa ha corretto

**I valori del gain control non sono quelli di brcmsmac.** La prima bozza della
patch veniva da `wlc_phy_workarounds_nphy_gainctrl_2057_rev6`; il device fa
altro:

| cosa | brcmsmac | device |
|---|---|---|
| LNA1 gain | 9, 14, 19, 24 | **8, 13, 18, 25** |
| W1 clip (0x300/0x301) | 13 | **24** |
| 0x283 | 0x40, poi 0x44 dal dispatcher | **solo 0x44** |
| LNA2, TIA gain, TIA gain bits in 2.4 GHz | non scritti | **scritti** |

Il ramo 2 GHz di brcmsmac è più povero di quello che il blob 6.30 esegue: LNA2
(`fc 06 0a 0f`), TIA gain (`ff 00 03 06...`) e i gain bits (`00 01 02 03...`)
vengono programmati, e ci sono anche i clip1 low gain code (0x37/0x2ad = 0x74,
0x38/0x2ae = 0x18). `patches/b43/0001` è stata riscritta su questi numeri.

I due init danno lo stesso blocco identico — stessi registri, stessi valori,
stesso ordine, a #685-#770 con canale operativo 1 e a #35491-#35576 con canale
operativo 6. Quindi questi valori **non dipendono dal canale**, ed è lecito
inchiodarli in C come fa la patch.

## Cosa ha trovato di nuovo

Sul cambio canale il vendore scrive **dieci registri in più**, tutti a zero:

    0x043 LOGEN_MX5G_TUNE          0x04a LOGEN_INDBUF5G_TUNE
    0x070 PGA_BOOST_TUNE_CORE0     0x0f5 PGA_BOOST_TUNE_CORE1
    0x073 TXMIX5G_BOOST_TUNE_CORE0 0x0f8 TXMIX5G_BOOST_TUNE_CORE1
    0x074 PAD5G_TUNE_MISC_PUS_CORE0 0x0f9 PAD5G_TUNE_MISC_PUS_CORE1
    0x0a0 LNA5G_TUNE_CORE0         0x125 LNA5G_TUNE_CORE1

Sono i campi 5 GHz e PGA della entry **dual band**: il vendore usa il record da
44 byte anche in 2.4 GHz e azzera la parte 5 GHz, mentre b43 usa la variante
`chantabent_rev7_2g` e quei registri non li tocca affatto.

**SALAME**: che lasciarli al valore precedente abbia un effetto misurabile
(corrente, perdite dal ramo 5 GHz) è un'ipotesi, non un dato. Prima di toccare
il percorso condiviso di `chantab_upload`, che riguarda anche altri device,
serve una misura. Voce aperta, non patch.

## Da catturare ancora

Nota sul 40 MHz, che nell'elenco non c'è per un motivo: su questa board il driver
vendor non usa i 40 MHz in 2.4 GHz, 31 chanspec su 31 sono bw20. I rami HT40 del
driver non si verificano qui nemmeno volendo, serve hardware diverso — e nei
commenti del codice va scritto così, non come "manca la cattura", che suona come
se non ci avessimo provato.


- `cal`: `wl phy_forcecal 1`, per rcal/rccal/tx iq-lo/papd.
- un giro completo dei canali 1-13: qui ce ne sono cinque (1, 2, 5, 6, 10) e su
  quelli nulla dipende dal canale oltre alla chantab, ma 13 e 14 restano da
  vedere (spuravoid, per esempio, che qui non compare mai).
- la stessa init con `skipphyrd` vuoto e i `RETVAL` attivi, per avere i valori
  letti nei punti di decisione.
