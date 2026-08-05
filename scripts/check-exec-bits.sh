#!/bin/sh
# I bit di esecuzione si perdono ogni volta che una modifica passa per un diff
# applicato a mano: `git apply` senza --index li lascia fuori dall'indice. E' gia'
# successo sei volte. Questo lo dice invece di farlo scoprire a chi prova a
# lanciare uno strumento.
#
#   sh scripts/check-exec-bits.sh
#
# Regola: ha il bit chi ha lo shebang, e nessun altro.
set -e
cd "$(dirname "$0")/.."
bad=0
for f in $(git ls-files); do
    case "$f" in *.py|*.sh) ;; *) continue ;; esac
    mode=$(git ls-files -s "$f" | awk '{print $1}')
    if [ "$(head -c2 "$f")" = '#!' ]; then
        [ "$mode" = 100755 ] || { echo "shebang ma non eseguibile: $f"; bad=1; }
    else
        [ "$mode" = 100644 ] || { echo "eseguibile senza shebang: $f"; bad=1; }
    fi
done
[ "$bad" = 0 ] && echo "bit di esecuzione: coerenti"
exit $bad
