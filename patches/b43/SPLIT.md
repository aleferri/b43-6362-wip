# The series stays unsplit, and the boundary lives in the history

The twelve in `patches/mainline/` are separate files because they leave early:
they are mainline defects, short, independent of this hardware, and they go in
twelve threads.

Everything else does not. BCM6362 support does not leave until the SPROM has a
road upstream (`docs/upstreaming.md`), so keeping thirty-six files for a series
that ships in months costs and gives nothing back: they drift. **It has
already happened.**

## What it has already cost

The twenty-six per-patch files existed until `394c9e2`. They are still in the
history and can be extracted, but **they are not usable**: applied on
`848acc8ffe1b` plus the twelve mainline patches they leave the tree **718 lines
and 37 hunks** away from the series, because `rollup.diff` was regenerated three
times after those files had been deleted, and the changes of those rounds were
only in the rollup. The files were there and lied, which is worse than not
having them.

## The rule, which costs nothing

**One commit per patch, with its `MESSAGES.md` entry in the same commit.**

The per-patch boundary lives there, not in a directory, and
`scripts/patch-from-commit.sh` extracts it when needed: for a commit on `b43/`
it is the commit's diff with the kernel paths; for a commit from before, when
the series was in `rollup.diff`, it applies the rollup of `<commit>^` and that
of `<commit>` to two copies of the pinned tree and diffs the results.

```sh
sh scripts/patch-from-commit.sh <commit> ~/src/pin > 00NN.patch
```

## What the published history holds

This file used to say that `0027` to `0036` were one commit each, nine commits
in all with `0033` and `0034` together, and that the script, run on them, gave
exactly the ten patches and a tree identical to the final rollup. That was
measured on a history that is not the one published: at `054601d` the ten
patches arrive together in `a608a33` ("patches reorg", 22 files, +5834 lines),
after `96a5a4c`, whose `MESSAGES.md` has twenty-six entries. **SALAME**: the
per-patch commits exist in a local clone that was squashed before pushing.
If so, pushing them is what makes the split below a command; if not, `0027`
to `0036` are in the same state as `0001` to `0026`.

Before `96a5a4c`, `progress`, `advance` and `reorg` are big commits, so for
`0001`-`0026` the boundary **is lost** and no tool recovers it.

## When it is really split

`SERIES.md` has the plan: eight series by area, with the order and the six
places where two series contend for the same function.

For the patches whose commit exists, the split is a command. For the others
there are **37 judgements** on as many drift hunks, and no automatic check
validates them: comparing the final tree passes even with changes attributed
to the wrong patch. If that work is not worth it, the legitimate alternative is
to send them as a single series split by area rather than by discovery, which
is what reviewers need anyway.
