"""Media probing. No domain, no course, no language."""

import subprocess


def probe_duration(video_path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True
    ).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return None
