"""
The flag REVIEW mechanism — not the detectors.

⚠️ Read the split carefully, it is the §2.1 rule in miniature: deciding *what to
flag* is language-tuned and stays in the caller's PROFILE. Deciding *whether a
flag has been signed off* is pure bookkeeping and lives here. The two copies of
this bookkeeping were byte-identical apart from dropped docstrings.

⚠️ `flag_key()` is `str(flag["start"])` and must stay exactly that. It is the
identity that ties a flag in state.json to its resolution across rescans, and
115 English + 109 Russian finalized lessons already carry resolutions keyed this
way. Changing the key format silently orphans every one of them — they would
read as unresolved, and a --bulk-resolve would then paper over real findings.
"""

import sys


def flag_key(flag):
    """Stable identity for a flagged segment across rescans of the same cached
    transcript (start time is deterministic since rescans never re-run Whisper)."""
    return str(flag["start"])


def unresolved_flags(entry):
    """Flags with no matching entry in flag_resolutions (keyed by flag_key)."""
    resolutions = entry.get("flag_resolutions", {})
    return [f for f in entry.get("flagged_segments", []) if flag_key(f) not in resolutions]


def check_flags(state, slug_filter):
    """Print unresolved flags for one lesson or all. Read-only; writes nothing.

    ⚠️ The old houdini-wand copy took a `course_slug` argument it never used.
    Dropped here rather than carried — an unused parameter in shared code is a
    future caller's wrong assumption."""
    lessons = state["lessons"] if slug_filter in (None, "all") else {slug_filter: state["lessons"].get(slug_filter)}
    if slug_filter not in (None, "all") and lessons.get(slug_filter) is None:
        print(f"ERROR: '{slug_filter}' not found.")
        sys.exit(1)
    any_unresolved = False
    for slug, entry in lessons.items():
        if entry is None:
            continue
        unresolved = unresolved_flags(entry)
        if not unresolved:
            continue
        any_unresolved = True
        print(f"{slug}: {len(unresolved)} unresolved flag(s)")
        for f in unresolved:
            mm, ss = int(f["start"]) // 60, int(f["start"]) % 60
            print(f"    [{mm}:{ss:02d}] {f['text'][:90]}")
            print(f"        reasons: {f['reasons']}")
    if not any_unresolved:
        print("[CLEAN] No unresolved flags.")
