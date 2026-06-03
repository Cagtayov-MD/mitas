"""
VLM OCR Spike — 1980 Son Metro (opening + closing)
Compares qwen2.5vl:7b reads against existing PaddleOCR output.
stdlib-only, UTF-8 everywhere. No pip installs.
"""
import base64, difflib, json, math, os, re, string, time, urllib.request

# ── CONFIG ────────────────────────────────────────────────────────────────────
MODEL = "qwen2.5vl:7b"
OLLAMA_URL = "http://localhost:11434/api/generate"
MAX_FRAMES_PER_SEGMENT = 60
DEDUP_RATIO = 0.90

PROMPT = (
    "You are reading ONE frame from a film's opening or closing credits. "
    "If the frame shows any credit text (cast names, roles, crew, job titles, "
    "song/music titles) - even a single line on a plain or colored background - "
    "transcribe EVERY credit line exactly as written, full names, one line per "
    "output line. If the frame is purely a movie SCENE (people, action, locations) "
    "with NO overlaid credit text, answer exactly: NONE. Never invent text."
)

FRAME_BASE = (
    r"E:\MITAS\outputs\ocr_50films_aaaa_v21_paddle_20260525"
    r"\items\1980_son_metro_end_credits\frames"
)
OCR_BASE = r"E:\MITAS\outputs\_CREDIT_SHEETS_20260529"
OUT_BASE = r"E:\MITAS\outputs\_vlm_ocr_spike\1980_son_metro"

SEGMENTS = ["opening", "closing"]

# ── HELPERS ───────────────────────────────────────────────────────────────────

def vlm_call(img_path: str) -> str:
    with open(img_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.loads(resp.read().decode())
    return out.get("response", "").strip()


_PUNCT = str.maketrans("", "", string.punctuation)

def normalize(line: str) -> str:
    return " ".join(line.upper().translate(_PUNCT).split())


def is_none_response(resp: str) -> bool:
    return normalize(resp) in ("NONE", "")


def dedup_lines(raw_lines: list[str]) -> list[str]:
    """Deduplicate preserving first-seen order; keep longest variant per group."""
    groups: list[list[str]] = []   # list of clusters
    group_norms: list[str] = []    # representative norm per cluster

    for line in raw_lines:
        norm = normalize(line)
        if not norm:
            continue
        matched = -1
        for i, gnorm in enumerate(group_norms):
            ratio = difflib.SequenceMatcher(None, norm, gnorm).ratio()
            if norm == gnorm or ratio >= DEDUP_RATIO:
                matched = i
                break
        if matched == -1:
            groups.append([line])
            group_norms.append(norm)
        else:
            groups[matched].append(line)

    # keep longest variant from each group
    result = []
    for grp in groups:
        best = max(grp, key=len)
        result.append(best)
    return result


def load_ocr_text(seg: str) -> list[str]:
    path = os.path.join(OCR_BASE, f"1980_son_metro_end_credits__{seg}.txt")
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        # skip header/separator/section-label lines
        if not s:
            continue
        if s.startswith("---") or s.startswith("==="):
            continue
        if re.match(r"^1980_son_metro", s):
            continue
        lines.append(s)
    return lines


def write_side_by_side(seg: str, ocr_lines: list[str], vlm_lines: list[str]):
    out_path = os.path.join(OUT_BASE, f"side_by_side_{seg}.md")

    ocr_set = {normalize(l) for l in ocr_lines}
    vlm_set = {normalize(l) for l in vlm_lines}

    # notable differences
    vlm_only_norms = vlm_set - ocr_set
    ocr_only_norms = ocr_set - vlm_set

    # classify ocr-only as noise vs real
    noise_pattern = re.compile(r"^[\d\s\W]+$")  # lines that are purely numbers/punct
    ocr_noise = [l for l in ocr_lines if normalize(l) in ocr_only_norms and len(normalize(l)) <= 3]
    ocr_real_only = [l for l in ocr_lines if normalize(l) in ocr_only_norms and len(normalize(l)) > 3]

    # VLM-only: flag potential hallucinations (lines with no partial overlap with any OCR norm)
    hallucination_risk = []
    certain_adds = []
    for vl in vlm_lines:
        vn = normalize(vl)
        if vn not in vlm_only_norms:
            continue
        # check partial overlap with any OCR line (ratio >= 0.5)
        best = max((difflib.SequenceMatcher(None, vn, on).ratio() for on in ocr_set), default=0.0)
        if best < 0.40:
            hallucination_risk.append(vl)
        else:
            certain_adds.append(vl)

    max_rows = max(len(ocr_lines), len(vlm_lines))
    col_w = 48

    rows = []
    for i in range(max_rows):
        lc = ocr_lines[i] if i < len(ocr_lines) else ""
        rv = vlm_lines[i] if i < len(vlm_lines) else ""
        rows.append(f"| {lc[:col_w]:<{col_w}} | {rv[:col_w]:<{col_w}} |")

    header = f"| {'Existing OCR':<{col_w}} | {'VLM (qwen2.5vl:7b)':<{col_w}} |"
    sep    = f"|{'-'*(col_w+2)}|{'-'*(col_w+2)}|"

    bullets = []
    if certain_adds:
        bullets.append("**VLM captured (not in OCR):**")
        for l in certain_adds:
            bullets.append(f"  - `{l}`")
    if ocr_noise:
        bullets.append("**OCR noise lines VLM dropped (short/garbled):**")
        for l in ocr_noise:
            bullets.append(f"  - `{l}`")
    if ocr_real_only:
        bullets.append("**OCR-only lines (VLM missed or merged):**")
        for l in ocr_real_only[:20]:
            bullets.append(f"  - `{l}`")
    if hallucination_risk:
        bullets.append("**HALLUCINATION RISK — VLM lines with no OCR anchor (verify manually):**")
        for l in hallucination_risk:
            bullets.append(f"  - `{l}`")
    else:
        bullets.append("**Hallucination risk:** none flagged by automated check.")

    md = "\n".join([
        f"# Side-by-Side: {seg.upper()} — 1980 Son Metro",
        "",
        header,
        sep,
        *rows,
        "",
        "---",
        "",
        "## Notable Differences",
        "",
        *bullets,
    ])

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"  [written] {out_path}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def run_segment(seg: str):
    frame_dir = os.path.join(FRAME_BASE, seg)
    all_frames = sorted(
        f for f in os.listdir(frame_dir) if f.lower().endswith(".png")
    )
    frames_total = len(all_frames)

    stride = max(1, math.ceil(frames_total / MAX_FRAMES_PER_SEGMENT))
    sampled = all_frames[::stride]
    frames_sampled = len(sampled)

    print(f"\n=== {seg.upper()} ===")
    print(f"  frames_total={frames_total}  stride={stride}  frames_sampled={frames_sampled}")

    raw_lines_all: list[str] = []
    none_count = 0
    vlm_calls = 0
    t0 = time.time()

    for idx, fname in enumerate(sampled):
        img_path = os.path.join(frame_dir, fname)
        print(f"  [{idx+1:3d}/{frames_sampled}] {fname} ... ", end="", flush=True)
        try:
            resp = vlm_call(img_path)
            vlm_calls += 1
            if is_none_response(resp):
                none_count += 1
                print("NONE")
            else:
                lines = [l.strip() for l in resp.splitlines() if l.strip()]
                raw_lines_all.extend(lines)
                print(f"{len(lines)} lines")
        except Exception as exc:
            print(f"ERR: {exc!r}")

    elapsed = time.time() - t0
    raw_line_count = len(raw_lines_all)
    deduped = dedup_lines(raw_lines_all)
    unique_line_count = len(deduped)

    print(f"  raw={raw_line_count}  unique={unique_line_count}  none={none_count}  t={elapsed:.1f}s")

    # write vlm text
    os.makedirs(OUT_BASE, exist_ok=True)
    txt_path = os.path.join(OUT_BASE, f"vlm_{seg}.txt")
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(deduped) + "\n")
    print(f"  [written] {txt_path}")

    # write meta json
    meta = {
        "segment": seg,
        "frames_total": frames_total,
        "frames_sampled": frames_sampled,
        "stride": stride,
        "vlm_calls": vlm_calls,
        "none_count": none_count,
        "raw_line_count": raw_line_count,
        "unique_line_count": unique_line_count,
        "seconds": round(elapsed, 1),
    }
    meta_path = os.path.join(OUT_BASE, f"meta_{seg}.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(f"  [written] {meta_path}")

    # compare vs existing OCR
    ocr_lines = load_ocr_text(seg)
    write_side_by_side(seg, ocr_lines, deduped)

    return meta, deduped


if __name__ == "__main__":
    print("VLM OCR Spike — 1980 Son Metro")
    print(f"Model: {MODEL}  MaxFrames/seg: {MAX_FRAMES_PER_SEGMENT}")
    print(f"Output dir: {OUT_BASE}")

    for seg in SEGMENTS:
        run_segment(seg)

    print("\nDone.")
