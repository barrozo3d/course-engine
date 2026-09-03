"""
Output modules — the composition contract (ULTIMATE_PIPELINE_PLAN.md §1.4, §2.1).

⚠️ `state.json` was ALREADY a module-composition contract; this formalises it
rather than redesigning it. §1.4 read the 21 keys by group and found four:
transcription, the review gate, knowledge-base, and frames. Each output module
owns a key group; the engine owns the rest. `cmd_finalize`'s entire divergence
between the two courses was that one sets the knowledge-base keys and the other
has no knowledge-base module — the modules were always separable, just
hard-coded.

⚠️ MODULES COMPOSE, THEY DO NOT TOGGLE EACH OTHER OFF (§2.1). The endgame is one
course producing subtitles AND translation AND knowledge-base entries AND frames
in a single run. The current either/or split — houdini has knowledge-base, nuke
has translation — is an artifact of two projects, not a design.

⚠️ `transcription` and `review` are ALWAYS enabled and are not listed in a
course's `outputs`. They are the engine's own stages: every course transcribes,
and every course must pass the flag-review gate before anything is called done.
A course cannot opt out of being checked.
"""

# name -> {"keys":          every state key the module owns,
#          "done":          the subset meaning "this module finished for this lesson",
#          "finalize_sets": the subset `finalize` is allowed to assert}
#
# 🔴 "done" AND "finalize_sets" ARE NOT THE SAME SET, and conflating them is a
# data-corrupting bug I wrote and caught here before it shipped. A first version
# derived finalize's keys from "done" and produced `frames_extracted` and
# `pt_br_srt_written` — keys that `course_frames.py` and `cmd_write_pt_srt` set
# when that work ACTUALLY RUNS. Finalizing would then have asserted that frames
# were captured and a pt-BR subtitle written when neither had happened, in the
# ledger that is supposed to be the record of what happened.
#
# Finalize marks the REVIEW-AND-NOTES pass. A module whose output is produced by
# its own command marks itself, and declares `finalize_sets: ()`.
MODULES = {
    "transcription": {
        "finalize_sets": (),
        "keys": ("srt_written", "transcript_cached", "last_transcribed"),
        "done": ("srt_written",),
    },
    "review": {
        "finalize_sets": (),
        "keys": ("flagged_segments", "flagged_segments_reviewed", "flag_resolutions",
                 "safeguard_warnings", "safeguard_critical", "needs_review"),
        "done": ("flagged_segments_reviewed",),
    },
    "subtitles": {
        # The .srt is written by the transcription stage; this module exists so a
        # course can DECLARE subtitles as an output without owning a second key.
        "finalize_sets": (),
        "keys": (),
        "done": ("srt_written",),
    },
    "translation": {
        "finalize_sets": (),
        "keys": ("pt_br_srt_written",),
        "done": ("pt_br_srt_written",),
    },
    "knowledge-base": {
        # The only module finalize speaks for: writing notes and adding the INDEX
        # entry IS the pass that --finalize concludes.
        "finalize_sets": ("notes_written", "index_entry_added"),
        "keys": ("raw_md_written", "notes_written", "index_entry_added",
                 "tutorial_slug", "committed"),
        "done": ("notes_written", "index_entry_added"),
    },
    "frames": {
        "finalize_sets": (),
        "keys": ("frame_timestamps", "frames_extracted", "frame_count"),
        "done": ("frames_extracted",),
    },
}

ALWAYS_ON = ("transcription", "review")


def enabled_modules(course):
    """The modules in force for a course: the always-on stages plus its outputs."""
    out = list(ALWAYS_ON)
    for name in course.get("outputs", ()):
        if name not in MODULES:
            raise ValueError(f"unknown output module: {name!r} (known: {sorted(MODULES)})")
        if name not in out:
            out.append(name)
    return out


def finalize_keys(course):
    """Keys `finalize` should set, derived from the ENABLED modules.

    ⚠️ Derived from each enabled module's `finalize_sets`, NOT from `done` and
    NOT hand-listed. Both courses previously carried this by hand and both match
    what this computes: houdini gets the knowledge-base pair, nuke gets nothing
    because it runs no knowledge-base module. Deriving removes the chance of the
    two drifting apart silently, which is the failure this phase is about --
    but see the block comment above for why the source must be `finalize_sets`
    and never `done`.

    `review`'s own key is set by `finalize` itself, so no module declares it."""
    keys = []
    for name in enabled_modules(course):
        for k in MODULES[name].get("finalize_sets", ()):
            if k not in keys:
                keys.append(k)
    return tuple(keys)


def module_status(entry, course):
    """[(module, done, [missing keys]), ...] for one lesson."""
    rows = []
    for name in enabled_modules(course):
        missing = [k for k in MODULES[name]["done"] if not entry.get(k)]
        rows.append((name, not missing, missing))
    return rows


def seed_gaps(course):
    """State keys the enabled modules own that the course's seed does not define.

    ⚠️ This is the composition guarantee, and it is why the registry is worth
    having at all: a course that declares an output whose keys its ledger never
    seeds would half-work and only reveal it later, on the lesson where the key
    was first read. Checking it is cheap and it fails loudly at import."""
    seed = course.get("lesson_seed", {})
    gaps = []
    for name in enabled_modules(course):
        for k in MODULES[name]["keys"] + MODULES[name]["done"]:
            if k not in seed and k not in gaps:
                gaps.append(k)
    return gaps
