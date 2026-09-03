"""
Course layout and lesson bookkeeping — the SHAPE of scanning a course tree and
seeding its ledger. Everything course-specific arrives in the `course` dict.

⚠️ TWO LAYOUTS, SELECTED BY PROFILE, and they are not unifiable into one walk:

  "flat-wk"    (houdini-wand)  week<N>/ dirs holding `..._wk<N>_<topic>.mp4`,
                               filenames pre-normalized at purchase. The week
                               number appears TWICE and is cross-checked: a file
                               whose embedded week disagrees with its directory
                               is skipped, not silently reassigned.

  "numbered"   (nuke-em-all)   `Week N`/ dirs (note the space and free-form
                               capitalisation) holding `01_topic.ext` OR
                               `01 Topic.ext` -- both naming styles appear in the
                               same course. Order comes from the leading number.

§1.3 measured `scan_course` at ~29% divergence and `ensure_lessons` at ~15%,
both attributable to layout alone. That is why this is a strategy and not a
branch inside one function.

⚠️ `cmd_finalize`'s divergence is ONLY which output-module keys it sets (§1.4).
houdini sets the knowledge-base keys, nuke does not, because nuke runs no
knowledge-base module. That is composition, not disagreement, so it is data:
`course["finalize_keys"]`.

⚠️ PROTOCOL VERSION (§1.4, Phase 4). `srt_written: True` does not mean "done
under the CURRENT protocol" -- that was the Rebelway wk3-15 lesson and the reason
decision #1 exists. Every lesson seeded from now on carries
`protocol_version: PROTOCOL_VERSION`, so the boundary between protocols stays
knowable instead of being reconstructed from commit dates later.

🔴 EXISTING LESSONS ARE NOT BACKFILLED, and that is the point, not an oversight.
An absent `protocol_version` means "seeded before stamping existed" -- which is
true, knowable, and exactly the fact a backfill would destroy. Writing the
current version onto 115 English and 109 Russian lessons finalized under an older
protocol would assert something false about all of them, and it is precisely the
ambiguity the stamp exists to end. Treat absent as its own value.
"""

import sys
from pathlib import Path

from .media import probe_duration
from .flags import unresolved_flags
from .modules import finalize_keys as _derived_finalize_keys, module_status

# Bumped when a pipeline change alters what a finalized lesson MEANS -- not
# when code moves. 1 = the protocol in force when stamping was introduced,
# 2026-09-03: caption cross-check, per-video prompt priming, the four
# structural detectors from Phase 0.
PROTOCOL_VERSION = 1


def lesson_slug(course, slugify, **fields):
    """Build a lesson slug from the course's frozen prefix and format.

    ⚠️ Uses course["lesson_slug_prefix"], NEVER course["slug"]. In nuke-em-all
    the two are not even equal (`rebelway-nuke` vs `rebelway-nuke-comp`), and in
    houdini-wand they match only by coincidence -- deriving one from the other
    would rename every finalized lesson the moment anyone passed --course-slug."""
    return slugify(course["lesson_slug_fmt"].format(prefix=course["lesson_slug_prefix"], **fields))


def scan_course(course_root, course):
    """Walk the course tree and return [{week, ..., path}, ...] sorted for ingest."""
    root = Path(course_root)
    layout = course["layout"]
    found = []

    if layout == "flat-wk":
        for week_dir in sorted(root.glob("week*")):
            if not week_dir.is_dir():
                continue
            m = course["week_dir_re"].match(week_dir.name)
            if not m:
                continue
            week = int(m.group(1))
            for f in sorted(p for ext in course["video_exts"] for p in week_dir.glob(f"*{ext}")):
                wm = course["file_re"].search(f.stem)
                # ⚠️ The week number is checked against the DIRECTORY, not just
                # parsed. A file carrying a different week is a naming mistake and
                # is skipped loudly rather than filed under the wrong week.
                if not wm or int(wm.group(1)) != week:
                    print(f"[WARN] Filename doesn't match expected wk{week}_<topic> pattern: {f.name} - skipping")
                    continue
                found.append({"week": week, "topic_stub": wm.group(2), "path": f})
        found.sort(key=lambda x: (x["week"], x["topic_stub"]))
        return found

    if layout == "numbered":
        for week_dir in sorted(root.iterdir()):
            if not week_dir.is_dir():
                continue
            m = course["week_dir_re"].match(week_dir.name)
            if not m:
                continue
            week = int(m.group(1))
            for f in sorted(week_dir.iterdir()):
                if not f.is_file() or f.suffix.lower() not in course["video_exts"]:
                    continue
                fm = course["file_re"].match(f.stem)
                if not fm:
                    print(f"[WARN] Filename doesn't start with a lesson number: {f.name} - skipping")
                    continue
                found.append({"week": week, "order": int(fm.group(1)),
                              "topic_raw": fm.group(2), "path": f})
        found.sort(key=lambda x: (x["week"], x["order"]))
        return found

    raise ValueError(f"unknown course layout: {layout!r}")


def ensure_lessons(state, course_root, course, slugify):
    """Idempotent merge: add newly-discovered lessons, touch no existing progress.

    ⚠️ Idempotence is the whole contract. This runs on every invocation, across
    sessions and days, over a ledger that already holds finalized work. A lesson
    already in `state["lessons"]` is left completely alone -- never re-seeded,
    never merged into. Re-seeding would silently clear flag resolutions."""
    videos = scan_course(course_root, course)
    for v in videos:
        fields = {k: val for k, val in v.items() if k != "path"}
        slug = lesson_slug(course, slugify, **fields)
        if slug in state["lessons"]:
            continue
        rel_path = str(v["path"].relative_to(Path(course_root))).replace("\\", "/")
        entry = dict(course["lesson_seed"])
        # Identity fields first, in the order the layout produced them, so a
        # fresh state.json keeps the key order the pre-engine code wrote.
        seeded = {}
        for k, val in fields.items():
            seeded[k] = val
        seeded["source_file"] = rel_path
        seeded["duration_sec"] = probe_duration(v["path"])
        seeded.update(entry)
        # Appended last so every pre-existing key keeps its position.
        seeded["protocol_version"] = PROTOCOL_VERSION
        state["lessons"][slug] = seeded
    return state, videos


def finalize(state, slug, course, save):
    """Mark a lesson's review pass complete. Refuses on any unresolved flag.

    ⚠️ This is the ACTUAL enforcement mechanism. A boolean anyone can set by hand
    is not one -- the gate is that every flagged segment must carry a resolution
    before the lesson can be called done."""
    entry = state["lessons"].get(slug)
    if entry is None:
        print(f"ERROR: '{slug}' not found.")
        sys.exit(1)
    unresolved = unresolved_flags(entry)
    if unresolved:
        print(f"[BLOCKED] {slug} has {len(unresolved)} unresolved flag(s). "
              f"Run --check-flags {slug} to see them, then --resolve-flag or --bulk-resolve each before finalizing.")
        sys.exit(1)
    # ⚠️ DERIVED from the course's enabled output modules, not hand-listed
    # (§1.4). Both courses previously carried this by hand and both matched what
    # modules.finalize_keys() computes; deriving removes the chance of the two
    # drifting apart without anything noticing.
    for key in _derived_finalize_keys(course):
        entry[key] = True
    entry["flagged_segments_reviewed"] = True
    save(state)
    print(f"[FINALIZED] {slug}: {len(entry.get('flagged_segments', []))} flag(s), all resolved.")
    # Report what each enabled module still owes, so "finalized" cannot quietly
    # mean "the review gate passed and nothing else ran".
    for name, done, missing in module_status(entry, course):
        if not done:
            print(f"           module '{name}' incomplete: missing {', '.join(missing)}")
