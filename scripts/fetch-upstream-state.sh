#!/bin/sh
# Sparse checkout del minimo necessario per rifare le verifiche di questo repo:
# b43, bcma, brcmsmac (riferimento GPL), le dt-bindings e il platform bcm63xx.
#
#   ./scripts/fetch-upstream-state.sh ~/src/linux [ref]
#
# Un clone completo di Linux non serve e costa: con --filter=blob:none e il
# cone mode restano ~40 MB.

set -e

DEST=${1:?uso: $0 <dir> [ref]}
REF=${2:-master}
REPO=${REPO:-https://github.com/torvalds/linux}

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
drivers/soc/bcm"

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
