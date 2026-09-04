#!/bin/sh
# Sparse checkout del minimo necessario per rifare le verifiche di questo repo:
# b43, bcma, brcmsmac (riferimento GPL), le dt-bindings e il platform bcm63xx.
#
#   ./scripts/fetch-upstream-state.sh ~/src/linux [ref]
#
# Un clone completo di Linux non serve e costa: con --filter=blob:none e il
# cone mode restano ~60 MB. lib/math c'e' perche' l'harness di test/ compila il
# cordic vero del kernel, non uno stub.
#
# SENZA `ref` prende master, che si muove. Uno sha qui NON si puo' passare: il
# clone vuole un nome di ref, e un fetch di 848acc8ffe1b lo rifiuta perche' una
# want-line vuole i 40 caratteri e non i 12. Per l'albero pinnato, che e' quello
# su cui questo repo afferma tutto, la strada che funziona e' il tarball, che
# l'abbreviato lo accetta:
#
#   mkdir -p ~/src/pin && cd ~/src/pin
#   curl -sL https://codeload.github.com/torvalds/linux/tar.gz/848acc8ffe1b |
#       tar -xz --strip-components=1 --wildcards \
#         'linux-*/drivers/net/wireless/broadcom/b43/*' \
#         'linux-*/drivers/net/wireless/broadcom/brcm80211/*' \
#         'linux-*/drivers/bcma/*' 'linux-*/drivers/ssb/*' \
#         'linux-*/include/linux/bcma/*' 'linux-*/include/linux/ssb/*' \
#         'linux-*/include/dt-bindings/*' 'linux-*/arch/mips/bcm63xx/*' \
#         'linux-*/arch/mips/include/asm/mach-bcm63xx/*' \
#         'linux-*/drivers/clk/bcm/*' 'linux-*/drivers/soc/bcm/*' \
#         'linux-*/lib/math/*' 'linux-*/Makefile'
#   git init -q . && git add -A && git commit -qm 848acc8ffe1b
#
# Il `git init` in coda non e' un ornamento: senza, `git -C ~/src/linux diff
# --stat` non risponde, ed e' il controllo della trappola 2 -- misurare su un
# albero senza le patch e leggere il risultato come una regressione.

set -e

DEST=${1:?uso: $0 <dir> [ref]}
REF=${2:-master}
REPO=${REPO:-https://github.com/torvalds/linux}

if [ -z "$2" ]; then
	echo "ATTENZIONE: nessun ref, prendo master. Questo repo afferma tutto su" >&2
	echo "848acc8ffe1b: per quello serve il tarball, vedi la testa di questo" >&2
	echo "script." >&2
fi

PATHS="drivers/net/wireless/broadcom/b43
drivers/net/wireless/broadcom/brcm80211
drivers/bcma
drivers/ssb
include/linux/bcma
include/linux/ssb
include/dt-bindings
arch/mips/bcm63xx
arch/mips/include/asm/mach-bcm63xx
drivers/clk/bcm
drivers/soc/bcm
lib/math"

if [ -d "$DEST/.git" ]; then
	git -C "$DEST" fetch --filter=blob:none --depth 1 origin "$REF"
	git -C "$DEST" checkout -q FETCH_HEAD
else
	git clone --filter=blob:none --no-checkout --depth 1 \
		--branch "$REF" "$REPO" "$DEST"
	git -C "$DEST" sparse-checkout init --cone
	# shellcheck disable=SC2086
	git -C "$DEST" sparse-checkout set $PATHS
	git -C "$DEST" checkout -q
fi

echo "tree: $(git -C "$DEST" log -1 --format='%H %cd' --date=short)"
echo
echo "--- buchi di dispatch (radio rev 8 / phy rev 8) ---"
"$(dirname "$0")/../reverse-tools/check_gaps.py" --tree "$DEST"
echo
echo "--- xref brcmsmac ---"
"$(dirname "$0")/../reverse-tools/brcmsmac_xref.py" --tree "$DEST"
