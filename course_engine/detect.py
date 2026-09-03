"""
Transcript triage — the SHAPE of the detectors. Every threshold, vocabulary,
charset and on/off switch arrives in `profile`.

⚠️ Whisper can be CONFIDENTLY wrong. The destruction/distraction case had an
entirely unremarkable avg_logprob, so confidence metadata alone catches nothing.
That is why flags 2-7 exist at all.

⚠️ THE FLAG LIST IS NOT THE DEFECT LIST (§3.4). Across Week 8 the two sets barely
overlapped. Nothing here is a verdict; every flag means "look at this span".

⚠️ THE REPEAT-BURST PASS IS DELIBERATELY TWO ALGORITHMS, SELECTED BY PROFILE, AND
MUST NOT BE UNIFIED. They produce genuinely different output:

  "run-start-included" (houdini-wand, English)
      Walks every adjacent pair, keys by str(start), and annotates the
      run-STARTING occurrence too (`run[0] - 1`) -- CREATING a flagged record for
      it when nothing else had flagged it. Sorts the result.

  "flagged-only" (nuke-em-all, Russian)
      Builds runs from consecutive ORIGINAL TRANSCRIPT INDICES of segments
      already flagged as near-duplicates, and annotates only records that
      already exist. Never creates one. Never sorts.
      Its index-keying is itself a bug fix: an earlier version used position
      within the filtered list and merged wk1-06's 20 genuinely separate
      near-duplicate pairs, scattered ~15 min apart, into one fake "20x burst".

  The note wording differs too. Flattening either into the other would silently
  rewrite flags on 115 finalized English or 109 finalized Russian lessons, which
  decision #1 forbids. Carry them. Delete neither.
"""

import difflib


def _near_misses(text, profile, week=None):
    """Fuzzy-match words and word-windows against the profile's risk vocabulary.

    ⚠️ Single words only match single-word vocab: a 2-word window trivially
    "matches" a single-word term through character overlap ("destruction is" ~
    "destruction"), which is the word plus its neighbour, not a mishear.
    Multi-word vocab only matches windows of the same word count, so
    "bullet solver" is still reachable."""
    words = profile["word_re"].findall(text.lower())
    vocab = profile["near_miss_vocab"]
    single_vocab = [v for v in vocab if " " not in v]
    multi_vocab = [v for v in vocab if " " in v]

    candidates = [(w, single_vocab) for w in words]
    for n in {len(v.split()) for v in multi_vocab}:
        candidates += [(" ".join(words[i:i + n]), multi_vocab) for i in range(len(words) - n + 1)]

    # §3.5 tuning debt, answered by open question 4 (2026-09-03): a PER-WEEK
    # pair suppression, not course-phase scoping and not term deletion.
    #
    # ⚠️ The measured harm was four false positives in ONE week -- Week 8, a
    # rendering/lookdev week, where "range" ~ "wrangle" fired four times and in
    # wk8-05 the flagged phrase was the literal menu entry `Sample Frame Range`;
    # plus "angle" ~ "wrangle" on a spot light's Cone Angle, and "up constraints"
    # ~ "glue constraint". In a rendering week, *range* is usually just range.
    #
    # ⚠️ SUPPRESSION IS BY PAIR, NOT BY TERM. Dropping "wrangle" from the vocab
    # for Week 8 would also lose a real wrangle mishear in that week; §3.5 is
    # explicit that the fix must not delete terms that earned their place in the
    # FX weeks. Suppressing the specific pair keeps the term live.
    suppressed = set()
    if week is not None:
        for a, b in profile.get("near_miss_suppress", {}).get(week, ()):
            suppressed.add((a.lower(), b.lower()))

    found = set()
    for cand, pool in candidates:
        if cand in pool:
            continue                      # exact match, not a mishear
        close = difflib.get_close_matches(cand, pool, n=1, cutoff=profile["near_miss_cutoff"])
        if not close:
            continue
        match = close[0]
        # Trivial morphological variants of the SAME word are correct usage:
        # "attributes"~"attribute", "solve"~"solver".
        shorter, longer = sorted([cand, match], key=len)
        if longer.startswith(shorter) and len(longer) - len(shorter) <= profile["near_miss_suffix_tolerance"]:
            continue
        if (cand.lower(), match.lower()) in suppressed:
            continue
        found.add(f"'{cand}' ~ '{match}'")
    return found


def flag_segments(segments, profile, duration_sec=None, week=None):
    """Return [{start, end, text, reasons}, ...] for segments worth a second look.

    `duration_sec` is optional so older callers keep working; without it the
    duration-overrun flag is silently unavailable. `week` is likewise optional
    and only enables the profile's per-week near-miss suppression (§3.5)."""
    flagged = []
    dup_at = {}

    for i, seg in enumerate(segments):
        reasons = []

        # 1. Whisper's own confidence signals.
        if seg.get("avg_logprob", 0) <= profile["avg_logprob_max"]:
            reasons.append(f"low avg_logprob ({seg['avg_logprob']:.2f})")
        if seg.get("no_speech_prob", 0) >= profile["no_speech_prob_min"]:
            reasons.append(f"high no_speech_prob ({seg['no_speech_prob']:.2f})")
        if seg.get("compression_ratio", 0) >= profile["compression_ratio_min"]:
            reasons.append(f"high compression_ratio ({seg['compression_ratio']:.2f})")
        if profile["flag_temperature_fallback"] and seg.get("temperature", 0) and seg["temperature"] > 0:
            reasons.append(f"temperature fallback ({seg['temperature']:.2f})")

        text = seg.get("text", "")

        # 2. Accent-driven near-miss against the profile's vocabulary.
        nm = _near_misses(text, profile, week)
        if nm:
            reasons.append("possible mishear: " + ", ".join(sorted(nm)))

        # 3. Adjacent near-duplicate: Whisper re-transcribing the tail of one
        #    ~30s decode window into the head of the next.
        if i > 0:
            prev_text = segments[i - 1].get("text", "").strip()
            ratio = difflib.SequenceMatcher(None, prev_text.lower(), text.strip().lower()).ratio()
            if ratio >= profile["near_duplicate_ratio"] and prev_text:
                dup_at[i] = True
                reasons.append(f"near-duplicate of previous segment ({ratio:.2f} similarity) — likely decode-window repeat")

        start = seg.get("start")

        # 4. Duration overrun. A segment starting at/after the media ends
        #    transcribes audio that does not exist: no threshold, and no false
        #    positive is available by construction.
        if profile.get("flag_duration_overrun") and duration_sec and start is not None and start >= duration_sec:
            reasons.append(f"starts {start - duration_sec:.1f}s PAST the end of the media "
                           f"({duration_sec:.1f}s) — fabricated by construction")

        # 5/6. Impossible speech rate, and its look-alike. Two reasons, not one:
        #      a clamped 1.00s span is REAL text with wrong timing, and calling
        #      it fabrication would be a false positive.
        rate_cps = profile.get("impossible_rate_cps")
        if rate_cps is not None:
            span = (seg.get("end") or 0) - (start or 0)
            n_chars = len(text.strip())
            if span > 0 and n_chars >= profile["min_text_for_rate"]:
                rate = n_chars / span
                clamped = profile.get("clamped_span")
                if clamped is not None and abs(span - clamped) < profile["clamped_span_eps"]:
                    if rate > rate_cps / 2:
                        reasons.append(f"span is exactly {clamped:.2f}s for {n_chars} chars "
                                       f"— Whisper's clamped-duration artifact; the TIMING is wrong, "
                                       f"the text is usually real (check the SRT cue, not the words)")
                elif rate > rate_cps:
                    reasons.append(f"{rate:.0f} chars/sec — {n_chars} characters in {span:.2f}s "
                                   f"is not speakable (measured median for this course: "
                                   f"{profile['observed_median_cps']})")

        if reasons:
            flagged.append({
                "start": start, "end": seg.get("end"),
                "text": text.strip(), "reasons": reasons, "_idx": i,
            })

    # 7. Repeat-loop bursts — see the module note. A lone near-duplicate pair is
    #    usually genuine repetition; a RUN of them is a decode loop, and the run
    #    LENGTH is the evidence, so it cannot be judged one segment at a time.
    strategy = profile["repeat_burst_strategy"]
    run_min = profile["repeat_run_min"]

    if strategy == "run-start-included":
        by_start = {str(f["start"]): f for f in flagged}
        run = []
        for i in range(1, len(segments) + 1):
            joined = False
            if i < len(segments):
                a = (segments[i - 1].get("text") or "").strip().lower()
                b = (segments[i].get("text") or "").strip().lower()
                joined = bool(a and b and difflib.SequenceMatcher(None, a, b).ratio() >= profile["near_duplicate_ratio"])
            if joined:
                run.append(i)
                continue
            if len(run) >= run_min:
                total = len(run) + 1          # + the first occurrence that started it
                for idx in [run[0] - 1] + run:
                    seg = segments[idx]
                    note = (f"part of a {total}x repeat-loop burst — re-decode this span "
                            f"in isolation before deleting (a flat block logprob is a "
                            f"property of the decode window, not a verdict on the speech)")
                    key = str(seg.get("start"))
                    if key in by_start:
                        by_start[key]["reasons"].append(note)
                    else:
                        rec = {"start": seg.get("start"), "end": seg.get("end"),
                               "text": (seg.get("text") or "").strip(), "reasons": [note]}
                        flagged.append(rec)
                        by_start[key] = rec
            run = []
        for f in flagged:
            f.pop("_idx", None)
        flagged.sort(key=lambda f: (f["start"] is None, f["start"]))
        return flagged

    if strategy == "flagged-only":
        runs, run = [], []
        for idx in sorted(dup_at):
            if run and idx == run[-1] + 1:
                run.append(idx)
            else:
                if len(run) >= run_min:
                    runs.append(run)
                run = [idx]
        if len(run) >= run_min:
            runs.append(run)
        by_idx = {f["_idx"]: f for f in flagged}
        for r in runs:
            total_repeats = len(r) + 1    # + the un-flagged first occurrence
            for idx in r:
                by_idx[idx]["reasons"].append(
                    f"part of a {total_repeats}x repeat-loop burst — check with --lesson --force")
        for f in flagged:
            f.pop("_idx", None)
        return flagged

    raise ValueError(f"unknown repeat_burst_strategy: {strategy!r}")
