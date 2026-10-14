#!/bin/sh
# Prende l'albero kernel su cui stanno b43/ e bcma/, o lo stato di upstream.
#
#   ./scripts/fetch-upstream-state.sh ~/src/pin            albero pinnato
#   ./scripts/fetch-upstream-state.sh ~/src/linux master   stato di upstream
#
# Senza `ref` prende lo sha di patches/regen-base, che e' la base di b43/,
# bcma/ e delle patch: e' l'albero che vogliono test/unit (KDIR) e gli script
# di rigenerazione, e va lasciato senza patch. Lo prende dal tarball, perche'
# uno sha abbreviato non si fetcha (una want-line vuole i 40 caratteri), e ne
# fa un repo git di un commit, cosi' `git -C <dir> status` dice se qualcuno
# l'ha toccato.
#
# Con `ref` (un nome di ref: master, un tag) fa uno sparse checkout di quel
# ref, per misurare upstream con check_gaps.py e brcmsmac_xref.py. Quei
# numeri non hanno motivo di tornare con quelli presi sull'albero pinnato.
#
# lib/math c'e' perche' l'harness compila il cordic vero del kernel.

set -e

DEST=${1:?uso: $0 <dir> [ref]}
REF=$2
REPO=${REPO:-https://github.com/torvalds/linux}
TOP=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

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
Documentation/devicetree/bindings/bus
lib/math"

if [ -z "$REF" ]; then
	PIN=$(sed -n 's/^pin[[:space:]]\{1,\}//p' "$TOP/patches/regen-base")
	[ -n "$PIN" ] || { echo "patches/regen-base: manca pin" >&2; exit 1; }
	[ ! -e "$DEST" ] || { echo "$DEST esiste gia'" >&2; exit 1; }
	mkdir -p "$DEST"
	WILD=
	for p in $PATHS Makefile include/linux/cordic.h; do
		case $p in
		*.h|Makefile) WILD="$WILD linux-*/$p" ;;
		*) WILD="$WILD linux-*/$p/*" ;;
		esac
	done
	# shellcheck disable=SC2086
	curl -sSfL "$REPO/archive/$PIN.tar.gz" |
		tar -xz -C "$DEST" --strip-components=1 --wildcards $WILD
	git -C "$DEST" init -q
	git -C "$DEST" add -A
	git -C "$DEST" -c user.name=pin -c user.email=pin@localhost \
		commit -qm "$PIN"
	echo "tree: $PIN (tarball)"
	exit 0
fi

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
"$TOP/reverse-tools/check_gaps.py" --tree "$DEST"
echo
echo "--- xref brcmsmac ---"
"$TOP/reverse-tools/brcmsmac_xref.py" --tree "$DEST"
