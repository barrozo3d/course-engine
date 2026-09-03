"""
CourseEngine — binds a skill's own location and course identity to the shared,
domain-free operations, so the skill scripts stay thin adapters.

⚠️ Everything course- or language-specific arrives through the constructor. If a
method here ever needs to ask *which course am I*, the split has been drawn in
the wrong place.
"""

import sys
from pathlib import Path

from . import flags as _flags
from . import state as _state


class CourseEngine:
    def __init__(self, skill_dir, state_defaults):
        self.skill_dir = Path(skill_dir)
        self.state_defaults = dict(state_defaults)

    # ── paths ────────────────────────────────────────────────────────────────
    def course_ingest_dir(self, course_slug):
        return self.skill_dir / "course-ingest" / course_slug

    def state_path(self, course_slug):
        return self.course_ingest_dir(course_slug) / "state.json"

    # ── state ────────────────────────────────────────────────────────────────
    def load_state(self, course_slug, course_root):
        return _state.load_state(self.state_path(course_slug), course_root, self.state_defaults)

    def save_state(self, course_slug, state):
        _state.save_state(self.state_path(course_slug), state)

    # ── flag review ──────────────────────────────────────────────────────────
    def cmd_check_flags(self, state, slug_filter):
        _flags.check_flags(state, slug_filter)

    def cmd_resolve_flag(self, state, course_slug, slug, start, note):
        entry = state["lessons"].get(slug)
        if entry is None:
            print(f"ERROR: '{slug}' not found.")
            sys.exit(1)
        matches = [f for f in entry.get("flagged_segments", []) if abs(f["start"] - start) < 0.5]
        if not matches:
            print(f"ERROR: no flagged segment near start={start} in {slug}.")
            sys.exit(1)
        entry.setdefault("flag_resolutions", {})
        for f in matches:
            entry["flag_resolutions"][_flags.flag_key(f)] = note
        self.save_state(course_slug, state)
        print(f"Resolved {len(matches)} flag(s) at ~{start}s in {slug}: {note}")

    def cmd_resolve_range(self, state, course_slug, slug, start, end, note):
        entry = state["lessons"].get(slug)
        if entry is None:
            print(f"ERROR: '{slug}' not found.")
            sys.exit(1)
        entry.setdefault("flag_resolutions", {})
        matches = [f for f in entry.get("flagged_segments", []) if start <= f["start"] <= end]
        if not matches:
            print(f"ERROR: no flagged segments in [{start}, {end}]s in {slug}.")
            sys.exit(1)
        for f in matches:
            entry["flag_resolutions"][_flags.flag_key(f)] = note
        self.save_state(course_slug, state)
        print(f"Resolved {len(matches)} flag(s) in [{start}, {end}]s in {slug}: {note}")

    def cmd_bulk_resolve(self, state, course_slug, slug, note):
        entry = state["lessons"].get(slug)
        if entry is None:
            print(f"ERROR: '{slug}' not found.")
            sys.exit(1)
        entry.setdefault("flag_resolutions", {})
        unresolved = _flags.unresolved_flags(entry)
        for f in unresolved:
            entry["flag_resolutions"][_flags.flag_key(f)] = note
        self.save_state(course_slug, state)
        print(f"Bulk-resolved {len(unresolved)} flag(s) in {slug}: {note}")
