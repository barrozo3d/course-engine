"""SRT emission. Byte-for-byte identical to the two copies it replaces — the
Phase 2 success criterion is that a finalized lesson re-emits its existing .srt
unchanged, so nothing here may be 'improved' in passing."""


def format_srt_timestamp(seconds):
    if seconds < 0:
        seconds = 0
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments, srt_path):
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = format_srt_timestamp(seg["start"])
        end = format_srt_timestamp(seg["end"])
        text = seg["text"].strip()
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    srt_path.write_text("\n".join(lines), encoding="utf-8")
