#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
#
# Estrae il diff di UNA patch della serie dal commit che ha rigenerato
# patches/b43/rollup.diff.
#
#   ./scripts/patch-from-commit.sh <commit> [<albero kernel>]
#
# Il rollup e' un file solo finche' la serie non si spedisce, e i file per patch
# non si tengono: si sono gia' desincronizzati una volta (i ventisei di
# 394c9e2^ sono 718 righe dietro il rollup, vedi patches/b43/SPLIT.md). Il
# confine per patch sta nella storia, non in una directory, e questo script lo
# tira fuori: applica il rollup di <commit>^ e quello di <commit> a due alberi
# identici e diffa i due risultati.
#
# Vale a una condizione, che e' la regola: UN commit per patch, con la sua voce
# di MESSAGES.md nello stesso commit. Se un commit ne porta due, il diff che
# esce e' la somma e va diviso a mano (e' successo con 0033 e 0034).
#
# Verifica finale della divisione, quando si fa: applicare in sequenza tutte le
# patch estratte sopra il rollup di partenza e confrontare l'albero col rollup
# di arrivo. Se una e' tagliata male quel confronto fallisce.

set -e

COMMIT=${1:?uso: $0 <commit> [<albero kernel>]}
KTREE=${2:-$HOME/src/linux}
REPO=$(git rev-parse --show-toplevel)
SUB=drivers/net/wireless/broadcom/b43

if ! git -C "$REPO" rev-parse --verify -q "$COMMIT" >/dev/null; then
	echo "$COMMIT non e' un commit di questo repo" >&2
	exit 1
fi

if ! git -C "$REPO" show "$COMMIT" --name-only --pretty=format: |
		grep -qx patches/b43/rollup.diff; then
	echo "$COMMIT non tocca patches/b43/rollup.diff: non e' una patch della serie" >&2
	exit 1
fi

if [ ! -d "$KTREE/$SUB" ]; then
	echo "$KTREE non ha $SUB: passa l'albero come secondo argomento" >&2
	exit 1
fi

BASE=$(git -C "$KTREE" rev-list --max-parents=0 HEAD 2>/dev/null || true)
if [ -z "$BASE" ]; then
	echo "$KTREE non e' un repo git: serve per ripristinare il pristine" >&2
	exit 1
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

git -C "$REPO" show "$COMMIT^:patches/b43/rollup.diff" > "$TMP/prima.diff"
git -C "$REPO" show "$COMMIT:patches/b43/rollup.diff"  > "$TMP/dopo.diff"

for stato in prima dopo; do
	cp -r "$KTREE" "$TMP/$stato"
	(
		cd "$TMP/$stato"
		git checkout -q "$BASE" -- "$SUB"
		for p in "$REPO"/patches/mainline/*.patch; do
			git apply "$p"
		done
		git apply "$TMP/$stato.diff"
	)
done

for f in "$TMP/dopo/$SUB"/*; do
	n=$(basename "$f")
	diff -u --label "a/$SUB/$n" --label "b/$SUB/$n" \
		"$TMP/prima/$SUB/$n" "$f" || true
done
