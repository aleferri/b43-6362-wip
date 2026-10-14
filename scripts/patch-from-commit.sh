#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
#
# Estrae il diff di UNA patch della serie b43 dal commit che la porta.
#
#   ./scripts/patch-from-commit.sh <commit> [<albero pinnato>]
#
# Vale a una condizione, che e' la regola: UN commit per patch, con la sua voce
# di patches/b43/MESSAGES.md nello stesso commit. Se un commit ne porta due, il
# diff che esce e' la somma e va diviso a mano (e' successo con 0033 e 0034).
#
# Due epoche, riconosciute dal commit:
#
#   - un commit che tocca b43/ (la serie sta li' come file interi): il diff
#     e' quello del commit su b43/, coi percorsi del kernel. Non serve
#     l'albero.
#   - un commit che tocca patches/b43/rollup.diff (la serie compressa in un
#     file, fino alla riorganizzazione): applica il rollup di <commit>^ e
#     quello di <commit> a due copie dell'albero pinnato, con le mainline, e
#     diffa i risultati. Le mainline sono quelle del working tree.
#
# Verifica finale della divisione, quando si fa: applicare in sequenza tutte le
# patch estratte sull'albero pinnato con le mainline e confrontare con b43/.

set -e

COMMIT=${1:?uso: $0 <commit> [<albero kernel>]}
KTREE=${2:-$HOME/src/pin}
REPO=$(git rev-parse --show-toplevel)
SUB=drivers/net/wireless/broadcom/b43

if ! git -C "$REPO" rev-parse --verify -q "$COMMIT" >/dev/null; then
	echo "$COMMIT non e' un commit di questo repo" >&2
	exit 1
fi

TOUCHED=$(git -C "$REPO" show "$COMMIT" --name-only --pretty=format:)

if echo "$TOUCHED" | grep -q '^b43/'; then
	git -C "$REPO" diff \
		--src-prefix=a/drivers/net/wireless/broadcom/ \
		--dst-prefix=b/drivers/net/wireless/broadcom/ \
		"$COMMIT^" "$COMMIT" -- b43/
	exit 0
fi

if ! echo "$TOUCHED" | grep -qx patches/b43/rollup.diff; then
	echo "$COMMIT non tocca b43/ ne' patches/b43/rollup.diff: non e' una patch della serie" >&2
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
