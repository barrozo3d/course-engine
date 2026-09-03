"""
state.json — the stage contract (§1.4).

⚠️ This file is already a module-composition contract and is being formalized as
one, NOT redesigned. Each output module owns a key group; the engine owns the
rest. Do not add keys here on a whim.

⚠️ `srt_written: True` does not mean "done under the current protocol" — the
lesson learned on Rebelway wk3-15, and the reason decision #1 (no retroactive
re-runs) exists. Any NEW state key must carry a protocol version stamp or the
same ambiguity returns with the next pipeline improvement.
"""

import copy, json, os
from datetime import datetime, timezone


def load_state(path, course_root, defaults):
    """Read state.json, or build a fresh one from the caller's `defaults`.

    The defaults dict is the ONLY thing that differed between the two copies of
    this function — course title, instructor, and one skill's extra
    `houdini_version_taught` / `version_bridge_doc_status` keys. That is course
    identity, so it is injected rather than branched on."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # ⚠️ DEEP copy, not dict(). The pre-engine code built a fresh dict LITERAL on
    # every call, so its nested "lessons": {} was new each time. A shallow copy
    # shares that nested dict with the caller's module-level COURSE dict: the
    # first fresh course's lessons then leak into the next one AND mutate the
    # defaults in place. Caught 2026-09-03 by testing two fresh load_state calls
    # in one process -- main() only calls it once, so nothing in production had
    # tripped it yet, and it would have surfaced as impossible state instead.
    state = copy.deepcopy(defaults)
    state["source_root"] = course_root
    state.setdefault("lessons", {})
    state.setdefault("last_updated", None)
    return state


def save_state(path, state):
    """Atomic write (temp file + os.replace) so a second process reading/writing
    state.json concurrently (e.g. a --rescan-flags pass while a transcription
    batch is still running) never sees a truncated/partial file — a real risk
    observed once already when two course_transcribe.py runs briefly overlapped."""
    state["last_updated"] = datetime.now(timezone.utc).isoformat() + "Z"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
