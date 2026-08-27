# SPDX-License-Identifier: GPL-2.0
#
# Build in userspace dei sorgenti N-PHY di b43 presi da un tree kernel, con uno
# shim al linker (wrap.c) che sostituisce ogni accessor HW con un tracer che
# emette righe nel formato wl-diag. Nessun file del tree viene modificato: la
# patch da provare si applica al tree, non qui.
#
#   make KDIR=~/src/linux            costruisce
#   make KDIR=~/src/linux gainctl    esegue il flow e scrive trace.gainctl.out
#   make compare FLOW=gainctl REF=... confronta col trace vendor
#
# I sorgenti sono i .c di mainline: se ci applichi patches/b43/rollup.diff e ricostruisci,
# il diff col trace vendor ti dice se la patch riproduce il device.

KDIR  ?= $(HOME)/src/linux
B43   := $(KDIR)/drivers/net/wireless/broadcom/b43
STUBS := stubs

# I .c del kernel fanno #include "b43.h", che con le virgolette risolve nella
# loro directory: se compilassimo in loco prenderebbero il b43.h vero, che tira
# dentro mezzo kernel. Quindi si copiano in build/src/ insieme ai soli header
# che vogliamo veri, e b43.h/main.h arrivano da stubs/.
SRCDIR   := build/src
REAL_HDRS := phy_n.h phy_common.h ppr.h tables_nphy.h \
             radio_2055.h radio_2056.h radio_2057.h
COPY_SRCS := phy_n.c radio_2057.c tables_nphy.c ppr.c cordic.c

# Due set di flag, perche' i due lati hanno responsabilita' diverse.
#
# I nostri file (wrap.c, main.c) sono codice nostro: -Wall -Wextra -Werror,
# senza scuse. L'unica deroga e' -Wno-unused-parameter, perche' le firme degli
# accessor le decide il driver e non possiamo togliere gli argomenti che non
# usiamo.
#
# I sorgenti del kernel li compila un compilatore host con flag diversi da
# quelli con cui nascono, quindi un warning di stile la' non e' un difetto da
# correggere (e non potremmo: non si modifica il tree). Ma tre classi restano
# FATALI anche la', perche' non parlano del kernel: parlano dei nostri stub.
#
#   implicit-function-declaration  prototipo mancante -> il tipo di ritorno
#                                 diventa int e la funzione mente
#   implicit-int                   stessa storia sulle dichiarazioni
#   incompatible-pointer-types     struct ridotta male, campo o firma diversi
#
# Se una di queste scatta l'harness sta girando su un modello sbagliato
# dell'ambiente, e il trace che produce non vale niente.
# CONFIG_B43_BCMA acceso: senza, i rami bus-specific sparivano e con loro le op
# GPIO e ChipCommon, che nella cattura vendor ci sono (2 GPIO.CTL, 52 GPIO.OUT).
# Il -Wswitch le ha fatte notare.
CFLAGS_COMMON := -O0 -g -DCONFIG_B43_BCMA=1 -I$(STUBS) -I$(SRCDIR) -I. \
          -include stubs/linux/types.h \
          -include stubs/linux/errno.h \
          -include stubs/linux/delay.h

CFLAGS_OURS   := $(CFLAGS_COMMON) -Wall -Wextra -Werror -Wno-unused-parameter

CFLAGS_KERNEL := $(CFLAGS_COMMON) -Wall -Wextra \
          -Werror=implicit-function-declaration \
          -Werror=implicit-int \
          -Werror=incompatible-pointer-types \
          -Wno-unused-parameter -Wno-unused-function -Wno-unused-variable \
          -Wno-unused-but-set-variable -Wno-sign-compare -Wno-pointer-sign \
          -Wno-missing-field-initializers -Wno-type-limits

# Solo le b43_ntab_*: sono in tables_nphy.c, che compiliamo, quindi vanno
# intercettate al linker per emettere il record TBL e poi eseguire la vera. Gli
# altri accessor stanno in phy_common.c e nel core, che non compiliamo: quelli
# li definisce direttamente wrap.c.
WRAP_SYMS := \
    b43_ntab_read b43_ntab_read_bulk b43_ntab_write b43_ntab_write_bulk

LDFLAGS := $(foreach s,$(WRAP_SYMS),-Wl,--wrap=$(s))

SRCS := $(addprefix $(SRCDIR)/,$(COPY_SRCS)) wrap.c main.c
OBJS := $(patsubst %.c,build/%.o,$(notdir $(SRCS)))

vpath %.c $(SRCDIR):.

BIN := nphy_trace

all: $(BIN)

build:
	mkdir -p build

# Staging: sola copia, mai modifica. Una regola per file, col sorgente del tree
# come prerequisito, cosi' se applichi una patch al tree la copia si rifa' da
# sola. Non uno stamp unico: quello resta valido e la copia resta vecchia in
# silenzio, vedi README.md.
STAGED := $(addprefix $(SRCDIR)/,$(COPY_SRCS) $(REAL_HDRS))

$(SRCDIR)/cordic.c: $(KDIR)/lib/math/cordic.c | build
	@mkdir -p $(SRCDIR)
	cp $< $@

$(SRCDIR)/%: $(B43)/% | build
	@mkdir -p $(SRCDIR)
	@test -d "$(B43)" || { echo "KDIR=$(KDIR) non ha $(B43)"; exit 1; }
	cp $< $@

# I .o dei sorgenti kernel e i nostri hanno regole separate: i flag cambiano.
build/wrap.o build/main.o: build/%.o: %.c $(STAGED) | build
	$(CC) $(CFLAGS_OURS) -MMD -MP -c $< -o $@

build/%.o: %.c $(STAGED) | build
	$(CC) $(CFLAGS_KERNEL) -MMD -MP -c $< -o $@

$(BIN): $(OBJS)
	$(CC) $(LDFLAGS) $^ -o $@

-include $(OBJS:.o=.d)

FLOW ?= gainctl
BOARD ?= dsl3580l

$(FLOW): $(BIN)
	./$(BIN) $(FLOW) $(BOARD) > trace.$(FLOW).out
	@echo "trace.$(FLOW).out: $$(wc -l < trace.$(FLOW).out) righe"

compare: $(BIN)
	@test -n "$(REF)" || { echo "serve REF=<trace vendor decodificato>"; exit 1; }
	./$(BIN) $(FLOW) $(BOARD) > trace.$(FLOW).out
	python3 compare.py $(REF) trace.$(FLOW).out $(RANGE)

# I warning dei sorgenti kernel non sono difetti nostri, ma il loro INSIEME e'
# un'informazione da tenere ferma: se cambia, qualcuno ha toccato il tree o gli
# stub e va guardato. Il confronto normalizza via i numeri di riga, che si
# spostano a ogni aggiornamento del kernel.
warncheck:
	@$(MAKE) -s clean >/dev/null
	@mkdir -p build
	@$(MAKE) KDIR=$(KDIR) 2>&1 \
	  | grep 'warning:' \
	  | sed -E 's|^[^:]*/||; s|:[0-9]+:[0-9]+:| |' \
	  | sort -u > build/warnings.seen
	@if diff -u expected-warnings.txt build/warnings.seen; then \
		echo "warncheck: ok ($$(wc -l < build/warnings.seen) warning attesi)"; \
	else \
		echo "warncheck: l'insieme dei warning e' cambiato, guardalo"; \
		exit 1; \
	fi

clean:
	rm -rf build $(BIN) trace.*.out

.PHONY: all clean compare warncheck $(FLOW)
