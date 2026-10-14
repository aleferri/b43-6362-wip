#!/bin/sh
# Rigenera patches/0001-0003 da bcma/.
#
#   ./scripts/regen-patches.sh ~/src/pin
#
# bcma/ e' la fonte di verita': file del kernel interi, ai loro percorsi,
# sull'albero di patches/regen-base. Le patch sono un prodotto: di ognuna si
# tiene l'intestazione (autore, data, oggetto, messaggio, fino al primo `---`)
# e si rifa' il diff, sull'albero pinnato, dei file che quella patch toccava.
# Un file nuovo in bcma/ che nessuna patch tocca fa fermare lo script: va
# assegnato a mano a una patch, aggiungendone il diff, e poi si rilancia.
#
# L'albero dato deve essere quello pinnato e pulito
# (scripts/fetch-upstream-state.sh senza ref).

set -e

KTREE=${1:?uso: $0 <albero pinnato>}
REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

PIN=$(sed -n 's/^pin[[:space:]]\{1,\}//p' "$REPO/patches/regen-base")
HEAD=$(git -C "$KTREE" log -1 --format=%s 2>/dev/null || true)
[ "$HEAD" = "$PIN" ] ||
	{ echo "$KTREE non e' l'albero pinnato $PIN" >&2; exit 1; }
[ -z "$(git -C "$KTREE" status --porcelain)" ] ||
	{ echo "$KTREE non e' pulito" >&2; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp -r "$KTREE" "$TMP/tree"

# percorsi nel kernel che le patch toccano, con la patch che li porta
for p in "$REPO"/patches/000[0-9]-*.patch; do
	sed -n 's|^+++ b/||p' "$p" | sed "s|\$| $(basename "$p")|"
done > "$TMP/map"

(cd "$REPO/bcma" && find . -type f | sed 's|^\./||') | sort > "$TMP/files"
awk '{print $1}' "$TMP/map" | sort > "$TMP/mapped"
orphans=$(comm -23 "$TMP/files" "$TMP/mapped")
[ -z "$orphans" ] ||
	{ echo "file di bcma/ che nessuna patch porta: $orphans" >&2; exit 1; }

while read -r f; do
	mkdir -p "$TMP/tree/$(dirname "$f")"
	cp "$REPO/bcma/$f" "$TMP/tree/$f"
done < "$TMP/files"
git -C "$TMP/tree" add -A

for p in "$REPO"/patches/000[0-9]-*.patch; do
	n=$(basename "$p")
	paths=$(awk -v n="$n" '$2 == n {print $1}' "$TMP/map")
	{
		sed '/^---$/q' "$p"
		# shellcheck disable=SC2086
		git -C "$TMP/tree" diff --cached --stat=72 -- $paths
		echo
		# shellcheck disable=SC2086
		git -C "$TMP/tree" diff --cached -- $paths
	} > "$TMP/$n"
	mv "$TMP/$n" "$p"
done
git -C "$REPO" diff --stat -- patches/
