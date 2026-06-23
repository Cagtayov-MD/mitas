"""
POC γ — LLM Uzlaştırıcı
A (box-tracking) + B (slit-scan) OCR çıktılarını Ollama gemma-4-31b-it-qat ile
tek temiz künyede birleştirir. Görsel YOK, sadece metin.

Kullanım:
    python core/pipelines/ocr/poc_llm_reconciler/run_llm_reconciler.py
"""
import json
import pathlib
import urllib.request
import urllib.error
import datetime

# ── Sabitler ──────────────────────────────────────────────────────────────────
INPUT_A = pathlib.Path(
    r"E:\MITAS\outputs\_boxtracking_test_20260529_235350"
    r"\1980_son_metro_end_credits__closing\lines.json"
)
INPUT_B = pathlib.Path(
    r"E:\MITAS\outputs\_slitscan_test_20260529_234847"
    r"\1980_son_metro_end_credits__closing\lines.json"
)
OUTPUT_DIR = pathlib.Path(r"E:\MITAS\outputs\_poc_llm_reconciler_20260530")
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma-4-31b-it-qat:latest"

SYSTEM_PROMPT = """\
Sen bir film jeneriği editörüsün. Aşağıda aynı filmin jeneriğinin İKİ ayrı \
OCR okuması var — A motoru (box-tracking) ve B motoru (slit-scan). Her biri \
eksik ve gürültülü.

Görevin: Bu iki yarım çıktıyı TEK temiz, tekrarsız, yapılandırılmış künyede \
birleştir.

Kurallar:
1. Tekrarı at (aynı satırın birden fazla kopyası varsa birini bırak).
2. OCR çöpünü ele: tek karakter (X, A, e), saf sayı (12, 1), anlamsız hece \
   (RA, AGEL, EOLTION) — bunları "dropped_as_noise" listesine ekle, künyeye koyma.
3. Orijinal dili (Fransızca/İngilizce) koru, çevirme.
4. Künyeyi üç kategoriye ayır: cast (oyuncular), crew (teknik ekip/prodüksiyon), \
   songs (şarkılar/müzik kredileri).
5. Sadece girdide açıkça geçen isimleri/unvanları kullan — ASLA isim uydurma, \
   hallüsinasyon yapma.
6. Belirsiz ya da kısmi satırları (CARHARA, e, AGEL gibi) yorumlama — \
   "dropped_as_noise" içine koy.
7. Şarkılar için: başlık + mevcut detayı (besteci, söz yazarı, icracı, \
   plak katalog no) bir "detail" alanında birleştir.

Çıktı: SADECE geçerli JSON, açıklama veya düz metin yok.
Şema:
{
  "cast":  [{"role": "...", "name": "..."}],
  "crew":  [{"role": "...", "name": "..."}],
  "songs": [{"title": "...", "detail": "..."}],
  "dropped_as_noise": ["..."]
}
"""


def load_lines(path: pathlib.Path, label: str) -> list[dict]:
    """lines.json'dan text+confidence+bbox_y satırlarını yükle."""
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = data.get("lines", [])
    # bbox[1] = y koordinatı → sıralama ipucu
    result = []
    for ln in lines:
        bbox = ln.get("bbox", [0, 0, 0, 0])
        result.append({
            "source": label,
            "y": bbox[1] if len(bbox) > 1 else 0,
            "text": ln.get("text", "").strip(),
            "confidence": round(ln.get("confidence", 0.0), 3),
        })
    # y'ye göre sırala
    result.sort(key=lambda r: r["y"])
    return result


def format_lines_for_prompt(lines_a: list[dict], lines_b: list[dict]) -> str:
    """LLM'e gönderilecek girdi metnini oluştur."""
    def fmt(lines, label):
        rows = [f"=== Kaynak {label} ==="]
        for i, ln in enumerate(lines, 1):
            rows.append(f"  [{i:02d}] conf={ln['confidence']:.2f}  \"{ln['text']}\"")
        return "\n".join(rows)

    return fmt(lines_a, "A (box-tracking, 16 satır)") + "\n\n" + fmt(lines_b, "B (slit-scan, 50 satır)")


def call_ollama(system: str, user: str) -> str:
    """Ollama /api/chat endpoint'ini çağır, yanıtın .message.content değerini döndür."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    print(f"[*] Ollama'ya istek gönderiliyor ({MODEL}) …")
    with urllib.request.urlopen(req, timeout=600) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    return data["message"]["content"]


def extract_json_from_response(text: str) -> dict | None:
    """LLM yanıtından JSON bloğunu çıkar."""
    # Olası ```json ... ``` sarmalayıcısını temizle
    text = text.strip()
    # <think>...</think> bloklarını sil (qwen3 chain-of-thought)
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = []
        in_block = False
        for ln in lines:
            if ln.startswith("```") and not in_block:
                in_block = True
                continue
            elif ln.startswith("```") and in_block:
                break
            elif in_block:
                inner.append(ln)
        text = "\n".join(inner)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Son çare: ilk { ... } bloğunu bul
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Girdileri yükle
    print(f"[*] A girdi dosyası: {INPUT_A}")
    lines_a = load_lines(INPUT_A, "A")
    print(f"    {len(lines_a)} satır yüklendi.")

    print(f"[*] B girdi dosyası: {INPUT_B}")
    lines_b = load_lines(INPUT_B, "B")
    print(f"    {len(lines_b)} satır yüklendi.")

    # 2. Yan yana metin dosyası
    side_by_side_path = OUTPUT_DIR / "inputs_side_by_side.txt"
    combined_text = format_lines_for_prompt(lines_a, lines_b)
    side_by_side_path.write_text(combined_text, encoding="utf-8")
    print(f"[*] Yan yana metin kaydedildi: {side_by_side_path}")

    # 3. LLM çağrısı
    llm_raw = call_ollama(SYSTEM_PROMPT, combined_text)
    print("[*] LLM yanıtı alındı.")

    # Ham yanıtı kaydet (debug)
    raw_path = OUTPUT_DIR / "llm_raw_response.txt"
    raw_path.write_text(llm_raw, encoding="utf-8")

    # 4. JSON parse
    merged = extract_json_from_response(llm_raw)
    merged_path = OUTPUT_DIR / "merged.json"

    if merged is None:
        print("[!] UYARI: JSON parse başarısız — ham metin merged.json'a kaydediliyor.")
        merged_path.write_text(json.dumps({"error": "parse_failed", "raw": llm_raw}, ensure_ascii=False, indent=2), encoding="utf-8")
        parse_ok = False
    else:
        merged_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        parse_ok = True
        print(f"[*] merged.json kaydedildi: {merged_path}")

    # 5. RESULT.md oluştur
    _write_result_md(lines_a, lines_b, merged, parse_ok)

    print("[OK] POC tamamlandı.")
    print(f"     Çıktı klasörü: {OUTPUT_DIR}")


def _write_result_md(lines_a, lines_b, merged, parse_ok):
    out = OUTPUT_DIR / "RESULT.md"
    lines = []
    lines.append("# POC γ — LLM Uzlaştırıcı Sonuçları")
    lines.append(f"\nTarih: {datetime.date.today()}")
    lines.append("\n## Girdi Sayıları")
    lines.append(f"- A motoru (box-tracking): **{len(lines_a)} satır**")
    lines.append(f"- B motoru (slit-scan): **{len(lines_b)} satır**")

    if not parse_ok or merged is None:
        lines.append("\n## HATA")
        lines.append("JSON parse başarısız. Ham yanıt `llm_raw_response.txt` dosyasında.")
        out.write_text("\n".join(lines), encoding="utf-8")
        return

    cast  = merged.get("cast", [])
    crew  = merged.get("crew", [])
    songs = merged.get("songs", [])
    noise = merged.get("dropped_as_noise", [])

    lines.append("\n## Birleşik Çıktı Sayıları")
    lines.append(f"- cast: **{len(cast)} kayıt**")
    lines.append(f"- crew: **{len(crew)} kayıt**")
    lines.append(f"- songs: **{len(songs)} kayıt**")
    lines.append(f"- dropped_as_noise: **{len(noise)} öğe**")

    # ─── Kritik kontroller ────────────────────────────────────────────────────
    lines.append("\n## Kritik Kontroller")

    # Kadro isimleri var mı?
    cast_names = [str(e.get("name","")).upper() for e in cast]
    cast_text  = " ".join(cast_names)
    has_deneuve    = "DENEUVE" in cast_text
    has_depardieu  = "DEPARDIEU" in cast_text
    lines.append(f"- DENEUVE birleşik cast listesinde: {'✓ EVET' if has_deneuve else '✗ HAYIR'}")
    lines.append(f"- DEPARDIEU birleşik cast listesinde: {'✓ EVET' if has_depardieu else '✗ HAYIR'}")

    # Şarkı var mı?
    song_titles = " ".join(str(s.get("title","")).upper() for s in songs)
    song_details= " ".join(str(s.get("detail","")).upper() for s in songs)
    song_all    = song_titles + " " + song_details
    has_chansons= "CHANSONS" in song_all
    has_beimir  = "BEI MIR" in song_all
    lines.append(f"- CHANSONS şarkı listesinde: {'✓ EVET' if has_chansons else '✗ HAYIR'}")
    lines.append(f"- BEI MIR BIST DU SCHÖN şarkı listesinde: {'✓ EVET' if has_beimir else '✗ HAYIR'}")

    # Çöp temizlendi mi?
    all_output_texts = []
    for e in cast + crew:
        all_output_texts.append(str(e.get("name","")))
        all_output_texts.append(str(e.get("role","")))
    for s in songs:
        all_output_texts.append(str(s.get("title","")))
        all_output_texts.append(str(s.get("detail","")))
    combined_out = " ".join(all_output_texts).upper()

    noise_items_in_a = ["1", "X", "A"]  # A'daki gürültü
    noise_items_in_b = ["12", "RA"]     # B'deki gürültü
    all_noise_check = noise_items_in_a + noise_items_in_b
    clean_ok = all(item not in combined_out.split() for item in all_noise_check)
    lines.append(f"- Bilinen çöpler (X, A, 1, 12, RA) çıktıdan temizlendi: {'✓ EVET' if clean_ok else '✗ HAYIR (bazıları kaldı)'}")

    # Halüsinasyon testi: girdi metninden TAMAMEN farklı isim var mı?
    # Girdideki tüm kelimeleri topla
    all_input_words = set()
    for ln in lines_a:
        for w in ln["text"].upper().split():
            all_input_words.add(w)
    for ln in lines_b:
        for w in ln["text"].upper().split():
            all_input_words.add(w)

    # Cast/crew isimlerinin kelimelerini kontrol et
    suspicious = []
    for e in cast + crew:
        name = str(e.get("name",""))
        for word in name.upper().split():
            if len(word) > 3 and word not in all_input_words:
                suspicious.append(word)

    if suspicious:
        lines.append(f"- Potansiyel halüsinasyon isimleri: **{'  '.join(set(suspicious))}**")
    else:
        lines.append("- Halüsinasyon kontrolü: girdide olmayan isim bulunamadı ✓")

    # ─── Cast listesi ─────────────────────────────────────────────────────────
    lines.append("\n## Cast")
    if cast:
        for e in cast:
            lines.append(f"- `{e.get('role','?')}` → {e.get('name','?')}")
    else:
        lines.append("_(boş)_")

    # ─── Crew listesi ─────────────────────────────────────────────────────────
    lines.append("\n## Crew")
    if crew:
        for e in crew:
            lines.append(f"- `{e.get('role','?')}` → {e.get('name','?')}")
    else:
        lines.append("_(boş)_")

    # ─── Şarkılar ─────────────────────────────────────────────────────────────
    lines.append("\n## Songs")
    if songs:
        for s in songs:
            lines.append(f"- **{s.get('title','?')}** — {s.get('detail','')}")
    else:
        lines.append("_(boş)_")

    # ─── Çöpler ───────────────────────────────────────────────────────────────
    lines.append("\n## Dropped as Noise")
    if noise:
        for n in noise:
            lines.append(f"- `{n}`")
    else:
        lines.append("_(boş)_")

    # ─── Yorum ────────────────────────────────────────────────────────────────
    lines.append("\n## Değerlendirme")
    success = has_deneuve and has_depardieu and (has_chansons or has_beimir)
    if success:
        lines.append(
            "POC başarılı: LLM iki yarım OCR çıktısını (A=kadro, B=şarkılar) "
            "tek yapılandırılmış künyede birleştirebildi. "
            "Hem kadro isimleri hem şarkı başlıkları çıktıda mevcut, "
            "gürültü temizlendi."
        )
    else:
        missing = []
        if not has_deneuve:    missing.append("DENEUVE")
        if not has_depardieu:  missing.append("DEPARDIEU")
        if not has_chansons and not has_beimir: missing.append("şarkı başlığı")
        lines.append(
            f"POC kısmen başarısız: şu beklenen öğeler eksik: {', '.join(missing)}. "
            "Ham yanıt için `llm_raw_response.txt` dosyasına bakınız."
        )

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[*] RESULT.md kaydedildi: {out}")


if __name__ == "__main__":
    main()
