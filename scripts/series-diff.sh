#!/bin/sh
# Stampa la serie b43 come un diff solo: dall'albero pinnato con
# patches/mainline/ applicate, a b43/.
#
#   ./scripts/series-diff.sh ~/src/pin [<base>]  > serie.diff
#
# Con <base> scrive li' anche l'albero di partenza del diff (i file di b43
# ai loro percorsi), che e' il --tree che vuole
# reverse-tools/check_patch_gating.py:
#
#   ./scripts/series-diff.sh ~/src/pin /tmp/base > /tmp/serie.diff
#   ./reverse-tools/check_patch_gating.py --tree /tmp/base /tmp/serie.diff
#
# Le mainline sono patch separate per upstream, ma stanno in b43/: senza, i
# numeri dell'harness non tornano (CLAUDE.md, "Setup").

set -e

KTREE=${1:?uso: $0 <albero pinnato> [<base>]}
OUT=$2
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SUB=drivers/net/wireless/broadcom/b43

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/a/$SUB" "$TMP/b/$SUB"
cp "$KTREE/$SUB"/* "$TMP/a/$SUB/"
(
	cd "$TMP/a"
	for p in "$REPO"/patches/mainline/*.patch; do
		patch -p1 --silent --forward -i "$p"
	done
)
cp "$TMP/a/$SUB"/* "$TMP/b/$SUB/"
cp "$REPO"/b43/* "$TMP/b/$SUB/"

if [ -n "$OUT" ]; then
	mkdir -p "$OUT/$SUB"
	cp "$TMP/a/$SUB"/* "$OUT/$SUB/"
fi

cd "$TMP"
git diff --no-index --no-prefix a b || [ $? -eq 1 ]
