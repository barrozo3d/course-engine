# course-engine

The shared, domain-free core of the local-course ingest pipeline used by
[houdini-wand](https://github.com/barrozo3d/houdini-wand) and
[nuke-em-all](https://github.com/barrozo3d/nuke-em-all).

Extracted 2026-09-03 per `houdini-wand/ULTIMATE_PIPELINE_PLAN.md` Phase 2,
obeying that plan's decision #2: **shared, not cloned** — one place every skill
imports from, because that is what makes a fix debuggable in one spot.

## Layout

This repo is a **sibling** of the skill repos, not a submodule of any of them:

```
~/.claude/skills/
  _shared/          <- this repo
  houdini-wand/
  nuke-em-all/
  ...
```

That is not an arbitrary convention — `validate.py::check_script_drift()`
already walks `os.path.dirname(skill_dir)` to find sibling skills, so the
codebase assumed this layout before the layout existed. Nothing here hardcodes
the name of any skill, and no skill hardcodes the name of another.

## What belongs here

**Structure**: loops, gates, state writes, the shape of a detector.

**Not**: anything tuned against one course's audio or one language. Thresholds,
prompts and vocab live in the calling skill's `PROFILE` / `COURSE` dicts and are
injected. A threshold appearing in this repo is a bug.

## Standalone clones

Each consuming skill carries a generated snapshot at `vendor/course_engine/` so
`git clone <one skill>` still runs. `course_engine_loader.py` prefers `_shared/`,
falls back to the snapshot, and **prints which one it is using every time** — a
silent fallback to a stale engine is the failure mode this whole arrangement
exists to avoid.

Regenerate snapshots after any change here:

```
python sync_vendor.py           # write
python sync_vendor.py --check   # report drift only
```
