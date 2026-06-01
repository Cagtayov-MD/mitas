"""
POC alpha -- VLM panorama okuma
Son Metro closing jenerik kredit segmentini Ollama VLM ile tara.
Mevcut pipeline'a dokunmaz; sadece outputs/_poc_vlm_panorama_20260530/ yazar.
"""

import base64
import io as _io
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Windows terminal UTF-8 zorla
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from PIL import Image

# ─────────────────────────────────────────────
# KONFIG
# ─────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
# qwen2.5vl:7b -- zaten VRAM'da yuklu, model swap yok, hizli
# minicpm-v -- B_panorama icin zaten tamamlandi
MODELS = ["qwen2.5vl:7b"]
LLAMA_SAMPLE_MODEL = "minicpm-v:latest"  # B_panorama tile 1 zaten var, credit_sheet tile 1 icin ekstra ornek
TIMEOUT = 360  # saniye
MAX_RETRIES = 1

TILE_H = 1400   # dikey tile yuksekligi (px)
TILE_OVERLAP = 200  # tile bindirme (px)
MAX_DIM = 1400  # tile'in uzun kenari bu degeri gecemez (scale-down)

INPUTS = {
    "B_panorama": r"E:\MITAS\outputs\_slitscan_test_20260529_234847\1980_son_metro_end_credits__closing\panorama.png",
    "A_panorama": r"E:\MITAS\outputs\_boxtracking_test_20260529_235350\1980_son_metro_end_credits__closing\panorama.png",
    "credit_sheet": r"E:\MITAS\outputs\_CREDIT_SHEETS_20260529\1980_son_metro_end_credits__closing.png",
}

OUT_DIR = Path(r"E:\MITAS\outputs\_poc_vlm_panorama_20260530")
FRAME_DIR = Path(r"E:\MITAS\outputs\_hakim_shadow_20films_20260529_1507\items\1980_son_metro_end_credits\frames\closing")
N_SAMPLE_FRAMES = 8

EXTRACTION_PROMPT = """You are reading a film end-credits image. Extract ALL visible text into structured JSON.
Rules:
- Output ONLY valid JSON, no markdown fences, no commentary.
- Preserve original language (French/Turkish/English/other) exactly.
- Schema: {"director":null,"cast":[{"role":"...","name":"..."}],"crew":[{"role":"...","name":"..."}],"songs":[{"title":"...","detail":"..."}],"other":[...]}
- "cast" = acting roles (character names + actor names). "crew" = technical/creative roles. "songs" = song/music titles with details.
- Do NOT invent or hallucinate. Only extract what is clearly visible in this image.
- Skip single stray characters, page numbers, watermarks.
- If a section has no entries, use an empty list [].
- If you cannot read any text at all, return {"director":null,"cast":[],"crew":[],"songs":[],"other":["[unreadable]"]}
"""


# ─────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

def img_to_b64(img: Image.Image) -> str:
    """PIL Image → base64 string (no data: prefix)."""
    import io
    buf = io.BytesIO()
    # RGBA → RGB dönüşümü gerekiyorsa yap
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def scale_tile(tile: Image.Image, max_dim: int) -> Image.Image:
    """Tile'ın uzun kenarını max_dim ile sınırla."""
    w, h = tile.size
    if max(w, h) <= max_dim:
        return tile
    scale = max_dim / max(w, h)
    return tile.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def tile_image(img: Image.Image, tile_h: int, overlap: int) -> list[tuple[int, Image.Image]]:
    """Uzun görseli dikey parçalara böl. (y_start, tile) listesi döner."""
    w, h = img.size
    if h <= tile_h:
        return [(0, img.copy())]
    tiles = []
    y = 0
    while y < h:
        y_end = min(y + tile_h, h)
        tile = img.crop((0, y, w, y_end))
        tiles.append((y, tile))
        if y_end == h:
            break
        y += tile_h - overlap
    return tiles


def call_ollama(model: str, b64_image: str, prompt: str) -> str:
    """Ollama API'ye istek at, ham metin döndür. Zaman asiminda yeniden dene."""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [b64_image],
            }
        ],
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    data = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(1, MAX_RETRIES + 2):  # 1..MAX_RETRIES+1
        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            return result["message"]["content"]
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            print(f"     [Deneme {attempt}/{MAX_RETRIES+1}] HATA: {e}", flush=True)
            if attempt <= MAX_RETRIES:
                import time
                print(f"     30s bekleyip tekrar deneniyor...", flush=True)
                time.sleep(30)
    raise last_err


def extract_json_from_text(text: str) -> dict:
    """Model çıktısından JSON bloğunu parse et."""
    text = text.strip()
    # ```json ... ``` fence temizle
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        text = fence.group(1).strip()
    # İlk { ... } bloğunu bul
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {"_parse_error": True, "_raw": text[:500]}


def merge_tile_results(results: list[dict]) -> dict:
    """Birden fazla tile sonucunu tek dict'e birleştir (tekrarları temizle)."""
    merged = {"director": None, "cast": [], "crew": [], "songs": [], "other": []}
    for r in results:
        if isinstance(r.get("director"), str) and r["director"] and not merged["director"]:
            merged["director"] = r["director"]
        for key in ("cast", "crew", "songs", "other"):
            existing = merged[key]
            for item in r.get(key, []):
                if item and item not in existing:
                    existing.append(item)
    return merged


def run_input(label: str, img_path: str, model: str, out_dir: Path, max_tiles: int = 0) -> dict:
    """Tek (girdi, model) cifti icin tum sureci calistir.
    max_tiles>0 ise cok uzun gorsellerde esit aralikli ornekleme yapar."""
    print(f"\n  -> {label} x {model}", flush=True)
    img = Image.open(img_path)
    w, h = img.size
    tiles = tile_image(img, TILE_H, TILE_OVERLAP)
    # Uzun panoramalar icin ornekleme
    if max_tiles > 0 and len(tiles) > max_tiles:
        step = len(tiles) / max_tiles
        tiles = [tiles[int(i * step)] for i in range(max_tiles)]
        print(f"     Boyut: {w}x{h}, tile ornekleme: {max_tiles} tile secildi", flush=True)
    else:
        print(f"     Boyut: {w}x{h}, tile sayisi: {len(tiles)}", flush=True)

    tile_raws = []
    tile_jsons = []
    for idx, (y_start, tile) in enumerate(tiles):
        tile_scaled = scale_tile(tile, MAX_DIM)
        b64 = img_to_b64(tile_scaled)
        print(f"     Tile {idx+1}/{len(tiles)} (y={y_start}): {tile_scaled.size} -> Ollama...", flush=True)
        try:
            raw_text = call_ollama(model, b64, EXTRACTION_PROMPT)
            parsed = extract_json_from_text(raw_text)
            print(f"     Tile {idx+1} tamam, {len(raw_text)} karakter", flush=True)
        except Exception as e:
            raw_text = f"[HATA: {e}]"
            parsed = {"_error": str(e)}
            print(f"     Tile {idx+1} HATA: {e}", flush=True)
        tile_raws.append(f"=== tile {idx+1} (y={y_start}) ===\n{raw_text}")
        tile_jsons.append(parsed)

    combined_raw = "\n\n".join(tile_raws)
    combined_json = merge_tile_results(tile_jsons)

    model_slug = model.replace(":", "_").replace("/", "_")
    raw_path = out_dir / f"{label}__{model_slug}.raw.txt"
    json_path = out_dir / f"{label}__{model_slug}.json"
    raw_path.write_text(combined_raw, encoding="utf-8")
    json_path.write_text(json.dumps(combined_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     Kaydedildi: {raw_path.name} + {json_path.name}")
    return combined_json


def run_frame_sample(model: str, frame_dir: Path, n: int, out_dir: Path) -> dict:
    """~n eşit aralıklı ham frame'i VLM ile tara, sonuçları birleştir."""
    label = "raw_frames_sample"
    print(f"\n  → {label} × {model}")
    frames = sorted(frame_dir.glob("frame_*.png"))
    if not frames:
        print("     Frame bulunamadı!")
        return {}
    step = max(1, len(frames) // n)
    selected = [frames[i] for i in range(0, len(frames), step)][:n]
    print(f"     Toplam {len(frames)} frame'den {len(selected)} seçildi")

    frame_raws = []
    frame_jsons = []
    for idx, fp in enumerate(selected):
        img = Image.open(fp)
        b64 = img_to_b64(img)
        print(f"     Frame {idx+1}/{len(selected)}: {fp.name} -> Ollama...", flush=True)
        try:
            raw_text = call_ollama(model, b64, EXTRACTION_PROMPT)
            parsed = extract_json_from_text(raw_text)
            print(f"     Frame {idx+1} tamam", flush=True)
        except Exception as e:
            raw_text = f"[HATA: {e}]"
            parsed = {"_error": str(e)}
        frame_raws.append(f"=== {fp.name} ===\n{raw_text}")
        frame_jsons.append(parsed)

    combined_raw = "\n\n".join(frame_raws)
    combined_json = merge_tile_results(frame_jsons)

    model_slug = model.replace(":", "_").replace("/", "_")
    raw_path = out_dir / f"{label}__{model_slug}.raw.txt"
    json_path = out_dir / f"{label}__{model_slug}.json"
    raw_path.write_text(combined_raw, encoding="utf-8")
    json_path.write_text(json.dumps(combined_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"     Kaydedildi: {raw_path.name} + {json_path.name}")
    return combined_json


def score_result(data: dict, label: str, model: str) -> dict:
    """Sonucu puanla: anahtar isimler var mı, yapı mevcut mu?"""
    full_text = json.dumps(data, ensure_ascii=False).lower()
    cast_names = ["deneuve", "depardieu", "ferréol", "ferriol", "ferreol"]
    song_keywords = ["chansons", "bei mir", "bist du", "secunda", "sholom", "musique"]

    cast_hits = [n for n in cast_names if n in full_text]
    song_hits = [k for k in song_keywords if k in full_text]
    has_cast_struct = bool(data.get("cast"))
    has_crew_struct = bool(data.get("crew"))
    has_songs_struct = bool(data.get("songs"))
    both_cast_and_song = bool(cast_hits and song_hits)

    # Halüsinasyon göstergesi: gerçek dışı isimler? (basit heuristik: çok uzun "other" listesi)
    hallucination_flag = len(data.get("other", [])) > 20 or "_parse_error" in data or "_error" in data

    total_entries = len(data.get("cast", [])) + len(data.get("crew", [])) + len(data.get("songs", [])) + len(data.get("other", []))

    return {
        "label": label,
        "model": model,
        "cast_found": ", ".join(cast_hits) if cast_hits else "—",
        "song_found": ", ".join(song_hits) if song_hits else "—",
        "has_cast_struct": "✓" if has_cast_struct else "—",
        "has_songs_struct": "✓" if has_songs_struct else "—",
        "both_cast_and_song": "YES" if both_cast_and_song else "no",
        "hallucination_flag": "⚠" if hallucination_flag else "ok",
        "total_entries": total_entries,
    }


# ─────────────────────────────────────────────
# ANA AKIŞ
# ─────────────────────────────────────────────

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=== POC alpha -- VLM panorama okuma ===")
    print(f"Baslangic: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Çıktı: {OUT_DIR}")

    scores = []

    # A_panorama 11969px uzun → 9 tile; ornekleme ile 6 tile yeterli
    MAX_TILES_MAP = {"A_panorama": 6}

    # 1) Ana girdiler: panoramalar + credit sheet
    # Onceden tamamlanmis dosyalari atla
    for label, img_path in INPUTS.items():
        if not os.path.exists(img_path):
            print(f"\n[ATLA] Dosya yok: {img_path}")
            continue
        max_tiles = MAX_TILES_MAP.get(label, 0)
        for model in MODELS:
            model_slug = model.replace(":", "_").replace("/", "_")
            out_json = OUT_DIR / f"{label}__{model_slug}.json"
            if out_json.exists():
                print(f"\n[ATLA] Zaten var: {out_json.name}")
                data = json.loads(out_json.read_text(encoding="utf-8"))
                scores.append(score_result(data, label, model))
                continue
            data = run_input(label, img_path, model, OUT_DIR, max_tiles=max_tiles)
            scores.append(score_result(data, label, model))

    # 2) Opsiyonel: ham frame ornegi (sadece minicpm-v)
    if FRAME_DIR.exists():
        for model in MODELS:
            model_slug = model.replace(":", "_").replace("/", "_")
            out_json = OUT_DIR / f"raw_frames_sample__{model_slug}.json"
            if out_json.exists():
                print(f"\n[ATLA] Zaten var: {out_json.name}")
                data = json.loads(out_json.read_text(encoding="utf-8"))
                scores.append(score_result(data, "raw_frames_sample", model))
                continue
            data = run_frame_sample(model, FRAME_DIR, N_SAMPLE_FRAMES, OUT_DIR)
            scores.append(score_result(data, "raw_frames_sample", model))
    else:
        print(f"\n[ATLA] Frame klasoru yok: {FRAME_DIR}")

    # 3) llama3.2-vision karsilastirma ornekleri (sadece 1 tile)
    llama_samples = [
        ("B_panorama_tile1_llama", INPUTS["B_panorama"]),
        ("credit_sheet_tile1_llama", INPUTS["credit_sheet"]),
    ]
    for label, img_path in llama_samples:
        if not os.path.exists(img_path):
            continue
        model_slug = LLAMA_SAMPLE_MODEL.replace(":", "_").replace("/", "_")
        out_json = OUT_DIR / f"{label}__{model_slug}.json"
        if out_json.exists():
            print(f"\n[ATLA] Zaten var: {out_json.name}")
            data = json.loads(out_json.read_text(encoding="utf-8"))
            scores.append(score_result(data, label, LLAMA_SAMPLE_MODEL))
            continue
        # Sadece ilk tile'i isle
        print(f"\n  -> {label} x {LLAMA_SAMPLE_MODEL} (tek tile)", flush=True)
        img = Image.open(img_path)
        tiles = tile_image(img, TILE_H, TILE_OVERLAP)
        tile = tiles[0][1]  # sadece ilk tile
        tile_scaled = scale_tile(tile, MAX_DIM)
        b64 = img_to_b64(tile_scaled)
        print(f"     Tile boyutu: {tile_scaled.size} -> Ollama...", flush=True)
        try:
            raw_text = call_ollama(LLAMA_SAMPLE_MODEL, b64, EXTRACTION_PROMPT)
            data = extract_json_from_text(raw_text)
            print(f"     Tamam, {len(raw_text)} karakter", flush=True)
        except Exception as e:
            raw_text = f"[HATA: {e}]"
            data = {"_error": str(e)}
            print(f"     HATA: {e}", flush=True)
        model_slug = LLAMA_SAMPLE_MODEL.replace(":", "_").replace("/", "_")
        (OUT_DIR / f"{label}__{model_slug}.raw.txt").write_text(raw_text, encoding="utf-8")
        out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        scores.append(score_result(data, label, LLAMA_SAMPLE_MODEL))

    # 4) RESULT.md yaz
    write_result_md(scores, OUT_DIR)
    print(f"\n=== Bitti: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===", flush=True)


def write_result_md(scores: list[dict], out_dir: Path):
    paddle_ref = {
        "A_panorama": {"lines": 16, "has_cast": True, "has_songs": False, "note": "DENEUVE/DEPARDIEU/FERRÉOL var, şarkı yok"},
        "B_panorama": {"lines": 50, "has_cast": False, "has_songs": True, "note": "CHANSONS/BEI MIR BİST DU SCHÖN var, kadro yok"},
        "credit_sheet": {"lines": "?", "has_cast": "?", "has_songs": "?", "note": "§28 composer çıktısı"},
        "raw_frames_sample": {"lines": "N/A", "has_cast": "?", "has_songs": "?", "note": "Ham ekran, 8 frame örneği"},
    }

    lines = [
        "# POC α — VLM Panorama Okuma — Sonuçlar",
        f"\nTarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "\n## Referans: PaddleOCR çıktıları",
        "| Girdi | Satır | Kadro | Şarkı | Not |",
        "|-------|-------|-------|-------|-----|",
    ]
    for k, v in paddle_ref.items():
        lines.append(f"| {k} | {v['lines']} | {v['has_cast']} | {v['has_songs']} | {v['note']} |")

    lines += [
        "\n## VLM Sonuçları",
        "| Girdi | Model | Kadro (DENEUVE/DEPARDIEU) | Şarkı (CHANSONS/BEI MIR) | Rol\\|İsim yapısı | Şarkı yapısı | **HEM kadro HEM şarkı?** | Halüsinasyon | Toplam madde |",
        "|-------|-------|--------------------------|--------------------------|----------------|--------------|--------------------------|-------------|--------------|",
    ]
    for s in scores:
        lines.append(
            f"| {s['label']} | {s['model']} | {s['cast_found']} | {s['song_found']} "
            f"| {s['has_cast_struct']} | {s['has_songs_struct']} "
            f"| **{s['both_cast_and_song']}** | {s['hallucination_flag']} | {s['total_entries']} |"
        )

    # Yorum: hem kadro hem şarkı olan var mı?
    both = [s for s in scores if s["both_cast_and_song"] == "YES"]
    lines.append("\n## Değerlendirme")
    if both:
        lines.append(f"\n**BAŞARI:** {len(both)} girdi×model kombinasyonu hem kadro hem şarkı üretti:")
        for s in both:
            lines.append(f"- `{s['label']}` × `{s['model']}` — kadro: {s['cast_found']} | şarkı: {s['song_found']}")
    else:
        lines.append("\n**BAŞARISIZ:** Hiçbir kombinasyon tek girdiden hem kadro hem şarkı çıkaramadı.")

    lines.append("\n### PaddleOCR karşılaştırması")
    lines.append("- PaddleOCR A panoramasında 16 satır kadro okudu (DENEUVE/DEPARDIEU/FERRÉOL); şarkı yok.")
    lines.append("- PaddleOCR B panoramasında 50 satır şarkı/teknik okudu; kadro yok.")
    lines.append("- VLM'lerin panoramada hangi yapıyı daha iyi yakaladığı ve `both_cast_and_song` sütunu asıl ölçüt.")

    result_path = out_dir / "RESULT.md"
    result_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRESULT.md yazıldı: {result_path}")


if __name__ == "__main__":
    main()
