#!/usr/bin/env python3
"""
Normalizza una cattura wl-diag e la confronta col trace emesso da nphy_trace.
Si confrontano solo le righe di op (indirizzo / valore / maschera): numero di
episodio, timestamp e prefisso cpuN vengono via dal lato vendore prima del diff,
perche' l'harness non simula lo scheduling.

Uso:
    compare.py <vendor.txt> <test.out> [OPZIONI]

--range LO:HI    tiene solo le righe del vendore con episodio in [LO,HI]
--auto-align     salta il prologo dell'harness allineandosi alla prima op in
                 comune con vendor[0], e riporta l'offset trovato
--align-on OP    come --auto-align ma su un'op precisa
                 (es. 'PHY.WR   addr=0x0186 val=0xfe87')

Per confrontare una fase per volta con le finestre gia' riconosciute c'e'
phase_compare.py, che usa questo modulo per la normalizzazione.

Su N-PHY e' b43 a usare PHY.OR/PHY.AND (b43_phy_set, b43_phy_mask) e il vendore a
usare PHY.MOD (phy_reg_mod), quindi la normalizzazione porta le prime alla forma
della mod: val = valore del campo, mask = campo modificato. Vedi il commento su
SET_OP/CLR_OP piu' sotto: nelle catture AC era il contrario, e la direzione della
riduzione e' stata girata di conseguenza.
"""
import re
import sys
import argparse

VENDOR_LINE = re.compile(
    r'^\s*[0-9.]+\s+#\d+\s+cpu\d+\s+(.+?)\s*(?:;.*)?$'
)
TEST_LINE = re.compile(r'^cpu\d+\s+(.+?)\s*$')

# Vendor uses PHY.OR (set-in) and PHY.AND (clear-in) alongside PHY.MOD.
# Both are folded to the PHY.MOD single-op form that the wrapper emits:
#   phy_set(X) → PHY.MOD val=X mask=0
#   phy_mask(K) → PHY.MOD val=K mask=0    (K = ~clr in kernel terms)
# PHY.OR line looks like "PHY.OR ... val=<current_or_or_in> (set X)":
#   the (set X) group gives the OR-in bits directly → val=X mask=0.
# PHY.AND line "PHY.AND ... val=<masked> (clr X)": clr X gives the
# bits to clear → val=~X (the kmask) mask=0.
# Riposizionamento su N-PHY. Nelle catture AC era il VENDORE a emettere
# PHY.OR/PHY.AND e l'harness a emettere PHY.MOD; qui e' il contrario: il ramo
# N-PHY del blob usa phy_reg_mod, mentre b43 usa b43_phy_set e b43_phy_mask. La
# normalizzazione va quindi nell'altro verso, e vale per entrambi i lati perche'
# normalize_op e' applicata a tutti e due.
#
# Convenzione della forma canonica, quella del vendore: val = valore del campo,
# mask = campo modificato.
#   b43_phy_set(A, V)   -> PHY.OR  addr=A val=V      == mod(A, campo V, val V)
#   b43_phy_mask(A, K)  -> PHY.AND addr=A val=K      == mod(A, campo ~K, val 0)
# b43_phy_maskset gia' emette la forma canonica (wrap.c stampa mask=~mask).
# Due forme, perche' i due lati stampano la stessa op in modo diverso:
#   vendore: PHY.OR  addr=A val=<valore> (set S)
#   harness: PHY.OR  addr=A val=S
# Nel primo caso i bit li da' l'annotazione, nel secondo il campo val.
SET_OP = re.compile(r'^(PHY|RAD)\.OR\s+addr=(0x[0-9a-fA-F]+)\s+val=(0x[0-9a-fA-F]+)'
                    r'(?:\s*\(set\s+(0x[0-9a-fA-F]+)\))?\s*$')
CLR_OP = re.compile(r'^(PHY|RAD)\.AND\s+addr=(0x[0-9a-fA-F]+)\s+val=(0x[0-9a-fA-F]+)'
                    r'(?:\s*\(clr\s+(0x[0-9a-fA-F]+)\))?\s*$')

# Il marcatore degli array di initvals del vendore non e' un'op hardware: e'
# contabilita' del suo driver. Le op che ne discendono sono nel trace per conto
# loro (vedi docs/blob-inventory.md), quindi il marcatore si scarta.
VENDOR_BOOKKEEPING = re.compile(r'^PHY\.ARRW\b')

# Op di alto livello e loro "ombra" a livello di core register: il tracer
# vendor logga entrambe, l'harness (come il driver) solo la prima. Le ombre sono
# la coppia addr/data del regcontrol del chipcommon e i registri GPIO; le altre
# SI.COREREG (0x0600, 0x0080, 0x0088, e tutto cio' che non e' core 0) sono op a
# se' stanti e non vanno scartate.
SHADOW_OFFSETS = {
    0x658, 0x65c,          # regcontrol addr/data   <- PMU.RC
    0x660, 0x664,          # pllcontrol addr/data   <- PMU.PLL
    0x064,                 # gpioout               <- GPIO.OUT
    0x068,                 # gpioouten             <- GPIO.OE / GPIO.OUTEN
    0x06c,                 # gpiocontrol           <- GPIO.CTL
    0x08c,                 # gpiopull              <- GPIO.CTL
}
# Op che il driver esegue davvero, ma da codice fuori dall'unita' sotto test:
# l'harness compila solo src/, non main.c di b43 ne' bcma. Vanno saltate, non
# riprodotte, e solo dopo aver verificato che chi le esegue le emetta *nel punto
# giusto* della sequenza -- altrimenti lo skip nasconde un errore d'ordine.
#
#   (core 3, 0x01e0) BCMA_CLKCTLST: b43_bcma_wireless_core_reset chiama
#   bcma_core_set_clockmode(BCMA_CLKMODE_FAST) prima di b43_phy_init, e la
#   cattura mette la richiesta a #37/#40, cioe' prima della prima op PHY (#60).
#   Ordine verificato. La seconda coppia (#115/#118) legge lo stesso registro
#   con HAVEHT ormai alto: assunta ripetizione della stessa richiesta, non
#   verificata separatamente.
#
#   (core 0, 0x600) BCMA_CC_PMU_CTL: il flush PLL_UPD che latcha i valori
#   PLLCTL. La patch 0007 lo emette con bcma_pmu_set32 subito dopo le due
#   bcma_chipco_pll_write, ed e' esattamente dove lo mette la cattura (#31/#34,
#   read e write del read-modify-write, immediatamente dopo le PLL a #15/#23).
#   Ordine verificato.
# Letture pure che il driver non fa: il tracer vendor le registra, ma sono
# read-back senza effetto e riprodurle vorrebbe dire aggiungere una lettura il
# cui risultato viene scartato. Si saltano, con la condizione che siano
# davvero prive di side effect (mask nulla).
FOREIGN_READBACK = re.compile(
    r'^PMU\.PLL addr=0x[23] val=0x0 mask=0x0\b')

FOREIGN_COREREG = {
    (0x3, 0x1e0),
    (0x0, 0x600),
}

SHADOW_PARENT = re.compile(r'^(?:PMU\.(?:RC|PLL)|GPIO\.(?:OUT|OE|OUTEN|CTL))\b')
SI_COREREG = re.compile(r'^SI\.COREREG\s+core=(0x[0-9a-fA-F]+)\s+off=(0x[0-9a-fA-F]+)')

def drop_shadow_ops(ops):
    """Scarta le SI.COREREG che implementano l'op di alto livello precedente."""
    out = []
    parent = False
    for op in ops:
        if FOREIGN_READBACK.match(op):
            parent = True          # le sue ombre restano ombre
            continue
        m = SI_COREREG.match(op)
        if m and (int(m.group(1), 16), int(m.group(2), 16)) in FOREIGN_COREREG:
            continue
        if m and parent and int(m.group(1), 16) == 0 \
                and int(m.group(2), 16) in SHADOW_OFFSETS:
            continue
        parent = bool(SHADOW_PARENT.match(op))
        out.append(op)
    return out

HEXNUM = re.compile(r'\b(0x[0-9a-fA-F]+)\b')

WS = re.compile(r'\s+')

def canon_ws(op: str) -> str:
    """Collassa lo spazio bianco: la spaziatura fra mnemonico e operandi non e'
    informazione, e i due lati la formattano diversamente."""
    return WS.sub(' ', op).strip()

def canon_values(op: str) -> str:
    """Porta ogni letterale esadecimale a una forma canonica senza zeri di
    riempimento.

    Il tracer vendor stampa i valori di ritorno a 32 bit (val=0x00000000) mentre
    l'harness li stampa a 16 (val=0x0000): sono lo stesso numero e il confronto
    non deve dipendere dalla larghezza del campo. Gli indirizzi passano per la
    stessa normalizzazione, che e' innocua perche' entrambi i lati la ricevono."""
    return HEXNUM.sub(lambda m: '0x%x' % int(m.group(1), 16), op)

def normalize_op(op: str) -> str:
    m = SET_OP.match(op)
    if m:
        kind, addr, val, annotated = m.groups()
        setbits = annotated or val      # l'annotazione, se c'e', e' la verita'
        return canon_ws(canon_values(
            f"{kind}.MOD  addr={addr} val={setbits} mask={setbits}"))
    m = CLR_OP.match(op)
    if m:
        kind, addr, val, annotated = m.groups()
        # Vendore: (clr X) da' i bit azzerati. Harness: val e' cio' che resta,
        # quindi i bit azzerati sono il complemento.
        cleared = int(annotated, 16) if annotated else (~int(val, 16)) & 0xffff
        return canon_ws(canon_values(
            f"{kind}.MOD  addr={addr} val=0x0000 mask=0x{cleared:04x}"))
    # L'harness nomina l'abilitazione GPIO come il simbolo bcma
    # (bcma_chipco_gpio_outen), il tracer vendor come il registro (OE).
    op = re.sub(r'^GPIO\.OUTEN\b', 'GPIO.OE', op)
    return canon_ws(canon_values(op))

VAL_TOK = re.compile(r'val=(?:0x[0-9a-fA-F]+|UNDEFINED)')

RET_SUFFIX = re.compile(r'\s+ret=0x[0-9a-fA-F]+')

def ops_equal(v: str, t: str) -> bool:
    """Confronto op-per-op con il valore letto trattato come wildcard quando il
    vendor non lo ha registrato.

    Le catture prodotte senza "capture ret val" loggano ogni read come
    val=UNDEFINED: la' il valore non e' confrontabile e va ignorato, mentre
    indirizzo e classe di op restano vincolanti. Sulle catture con i RETVAL
    ripiegati (merge_retvals.py) il valore c'e' e viene confrontato."""
    # Le op read-modify-write di bcma (PMU.RC, GPIO.*) portano nel trace vendor
    # il valore riletto dopo la modifica; gli stub bcma dell'harness non
    # modellano quel readback, quindi il suffisso non e' confrontabile.
    v = RET_SUFFIX.sub('', v)
    if v == t:
        return True
    if 'val=UNDEFINED' in v:
        return VAL_TOK.sub('val=*', v, count=1) == VAL_TOK.sub('val=*', t, count=1)
    return False

def extract_episode(raw: str) -> int:
    m = re.search(r'#(\d+)', raw)
    return int(m.group(1)) if m else -1

RD_OP = re.compile(r'^(PHY|RAD|MAC)\.RD\s+addr=(0x[0-9a-fA-F]+)')
WR_OP = re.compile(r'^(PHY|RAD|MAC)\.WR\s+addr=(0x[0-9a-fA-F]+)')
MOD_OP = re.compile(r'^(PHY|RAD|MAC)\.MOD\s+addr=(0x[0-9a-fA-F]+)')


def drop_rmw_shadows(ops):
    """Scarta la read e la write che implementano una MOD del vendore.

    Il tracer aggancia sia gli accessor di alto livello (phy_reg_mod,
    mod_radio_reg) sia quelli bassi che loro chiamano, quindi una sola
    read-modify-write finisce nel trace come tre op:

        RAD.MOD addr=0x2b val=0x0 mask=0x1     <- l'intenzione
        RAD.RD  addr=0x2b val=0x9              <- la sua lettura interna
        RAD.WR  addr=0x2b val=0x8              <- la sua scrittura interna

    b43 fa la stessa cosa con b43_radio_mask e ne registra una sola. Le due
    ombre sono artefatto di strumentazione e vanno via, come gia' si fa per le
    SI.COREREG di PMU e GPIO. Si scartano SOLO se seguono immediatamente una MOD
    sullo stesso indirizzo e famiglia: una RD o una WR isolata resta, perche'
    la' e' l'op vera.
    """
    out = []
    pending = None          # (famiglia, indirizzo) della MOD appena vista
    for op in ops:
        m = MOD_OP.match(op)
        if m:
            pending = (m.group(1), m.group(2))
            out.append(op)
            continue
        if pending:
            r = RD_OP.match(op) or WR_OP.match(op)
            if r and (r.group(1), r.group(2)) == pending:
                continue    # ombra della MOD precedente
        pending = None
        out.append(op)
    return out


class Op(str):
    """Un'op che si porta dietro il numero di record da cui viene.

    E' una str a tutti gli effetti -- i filtri la riappendono cosi' com'e' e
    difflib la confronta per uguaglianza -- quindi non cambia niente per chi la
    usa. Serve solo per poter dire, DOPO, da quale record veniva un'op: fra il
    file e la lista finale ci sono drop_shadow_ops e drop_rmw_shadows, che ne
    scartano parecchie, quindi l'indice nella lista non e' il numero di record e
    ricostruire la corrispondenza a posteriori vuol dire sbagliarla.
    """

    __slots__ = ('ep',)


def load_vendor(path, ep_range):
    lo, hi = ep_range or (0, 10**9)
    out = []
    for line in open(path):
        m = VENDOR_LINE.match(line)
        if not m:
            continue
        ep = extract_episode(line)
        if not (lo <= ep <= hi):
            continue
        if VENDOR_BOOKKEEPING.match(m.group(1).strip()):
            continue
        op = Op(normalize_op(m.group(1)))
        op.ep = ep
        out.append(op)
    return drop_rmw_shadows(drop_shadow_ops(out))

def load_test(path):
    out = []
    for line in open(path):
        m = TEST_LINE.match(line)
        if m:
            out.append(normalize_op(m.group(1)))
    return out

def find_offset(test, target_op):
    """Return the index of `target_op` in test, or -1.

    Usa ops_equal, non l'uguaglianza esatta: se il vendor non ha registrato il
    valore letto l'ancora non deve dipendere da quello."""
    for i, op in enumerate(test):
        if ops_equal(target_op, op):
            return i
    return -1

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument('vendor')
    ap.add_argument('test')
    ap.add_argument('--range', help='LO:HI vendor episode range')
    ap.add_argument('--auto-align', action='store_true',
                    help='skip test prologue by aligning on vendor[0]')
    ap.add_argument('--align-on', help='align test on this exact op string')
    args = ap.parse_args()

    rng = None
    if args.range:
        lo, hi = args.range.split(':')
        rng = (int(lo), int(hi))

    vendor = load_vendor(args.vendor, rng)
    test = load_test(args.test)

    if args.align_on:
        off = find_offset(test, args.align_on)
        if off < 0:
            print(f"align-on: op not found in test: {args.align_on}")
            return 2
        print(f"aligning test at offset {off} (--align-on)")
        test = test[off:]
    elif args.auto_align and vendor:
        off = find_offset(test, vendor[0])
        if off < 0:
            print(f"auto-align: vendor[0] not found in test: {vendor[0]}")
        else:
            print(f"aligning test at offset {off} (auto: '{vendor[0]}')")
            test = test[off:]

    print(f"vendor: {len(vendor)} ops")
    print(f"test:   {len(test)} ops")

    n = min(len(vendor), len(test))
    mismatches = 0
    for i in range(n):
        if not ops_equal(vendor[i], test[i]):
            mismatches += 1
            if mismatches <= 20:
                print(f"  @{i}:")
                print(f"    vendor: {vendor[i]}")
                print(f"    test:   {test[i]}")
    if len(vendor) != len(test):
        print(f"length differs: vendor={len(vendor)} test={len(test)}")

    if mismatches == 0 and len(vendor) == len(test):
        print("MATCH")
        return 0
    print(f"total mismatches (compared prefix): {mismatches}")
    return 1

if __name__ == '__main__':
    sys.exit(main())
