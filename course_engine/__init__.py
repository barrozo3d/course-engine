"""
course_engine — the shared, domain-free core of the local-course ingest pipeline.

Extracted 2026-09-03 per houdini-wand/ULTIMATE_PIPELINE_PLAN.md Phase 2, obeying
decision #2: **shared, NOT cloned** — one place every skill imports from, stated
reason "easier to debug and fix things".

⚠️ What belongs here (§2.1): STRUCTURE — a loop, a gate, a state write, the shape
of a detector. Nothing that was tuned against one course's audio or one language
belongs here; that lives in the caller's PROFILE / COURSE dicts and is INJECTED.
If you find yourself adding a threshold to this package, it is in the wrong file.

⚠️ The clone that decayed is the reason this exists. course_subtitles.py was a
copy of course_transcribe.py; four of its eleven divergent functions differed
ONLY because the copy had dropped the original's docstrings — the explanations of
why a threshold exists are what a clone loses first, and the most expensive part
to reconstruct.
"""

__version__ = "0.2.0"

from .srt import format_srt_timestamp, write_srt
from .media import probe_duration
from .flags import flag_key, unresolved_flags
from .detect import flag_segments
from .engine import CourseEngine

__all__ = [
    "__version__",
    "format_srt_timestamp", "write_srt",
    "probe_duration",
    "flag_key", "unresolved_flags",
    "flag_segments",
    "CourseEngine",
]
