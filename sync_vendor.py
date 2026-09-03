"""
Regenerate every skill's vendored course_engine snapshot from this repo.

⚠️ The snapshot is GENERATED, NEVER HAND-EDITED — the same discipline
update_index_entry.py enforces for INDEX.md. An edit made in a vendor copy is
lost on the next sync and, worse, silently diverges from _shared/ until then.
Fix it here and re-run this.

    python sync_vendor.py            # write snapshots
    python sync_vendor.py --check    # report drift, write nothing (CI-safe)
"""

import argparse, filecmp, hashlib, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "course_engine"
SKILLS_ROOT = HERE.parent
# Only the skills that actually run a local-course pipeline. The other three
# have no course script, so a snapshot there would be dead weight that still
# has to be kept in sync -- add them here when they gain one.
TARGET_SKILLS = ["houdini-wand", "nuke-em-all"]


def _digest(pkg):
    h = hashlib.sha256()
    for f in sorted(pkg.rglob("*.py")):
        h.update(f.relative_to(pkg).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = ap.parse_args()

    if not SRC.exists():
        print(f"ERROR: {SRC} not found"); return 2
    src_digest = _digest(SRC)
    drift = 0
    for skill in TARGET_SKILLS:
        dest_root = SKILLS_ROOT / skill / "vendor"
        dest = dest_root / "course_engine"
        if not (SKILLS_ROOT / skill).exists():
            print(f"{skill:16} SKIPPED (not cloned on this device)")
            continue
        cur = _digest(dest) if dest.exists() else None
        if cur == src_digest:
            print(f"{skill:16} up to date ({src_digest})")
            continue
        drift += 1
        if args.check:
            print(f"{skill:16} STALE (vendor {cur or 'absent'} != shared {src_digest})")
            continue
        dest_root.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SRC, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (dest_root / "SNAPSHOT.txt").write_text(
            "GENERATED FILE - DO NOT EDIT\n"
            "Regenerate with: python _shared/sync_vendor.py\n\n"
            f"source     : https://github.com/barrozo3d/course-engine.git\n"
            f"digest     : {src_digest}\n"
            f"generated  : {datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8")
        print(f"{skill:16} synced ({cur or 'absent'} -> {src_digest})")
    if args.check and drift:
        print(f"\n{drift} skill(s) stale. Run without --check to fix.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
