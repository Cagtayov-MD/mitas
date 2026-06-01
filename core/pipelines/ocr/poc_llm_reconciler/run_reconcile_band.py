"""POC β → γ köprüsü: band_motion'ın gürültülü 403-satır çıktısını
qwen3.6 ile tek temiz künyeye indirger. Tek kaynak (çok-bant dump),
yoğun tekrar + OCR bozulması içerir. Amaç: pipeline kompozisyonunu kanıtla.

Çalıştır: venvs\\core\\Scripts\\python.exe core\\pipelines\\ocr\\poc_llm_reconciler\\run_reconcile_band.py
"""
import json
import urllib.request
from pathlib import Path

BAND_LINES = Path(r"E:\MITAS\outputs\_poc_band_motion_20260530\1980_son_metro_end_credits__closing\lines.json")
OUT_DIR = Path(r"E:\MITAS\outputs\_poc_llm_reconciler_20260530")
OLLAMA = "http://localhost:11434/api/chat"
MODEL = "qwen3.6:35b-a3b"

SYSTEM = (
    "Sen bir film jeneriği OCR temizleyicisin. Sana TEK bir filmin closing jeneriğinin "
    "ÇOK-BANT, ÇOK-GEÇİŞLİ ham OCR dökümü verilecek. Bu döküm: (a) aynı satırları onlarca kez "
    "tekrar içerir, (b) ağır OCR bozulması içerir (ör. 'CathekinE DenEuve' = CATHERINE DENEUVE, "
    "'GERARU DEPARUIEU' = GÉRARD DEPARDIEU). Görevin: tekrarları birleştir, OCR karakter hatalarını "
    "AYNI tokenin tekrarları arası oydaşmayla düzelt, çöpü (tek harf, sayı, anlamsız) at, ve TEK temiz "
    "yapılandırılmış künye çıkar. KURAL: Sadece girdide DESTEĞİ olan isimleri yaz; girdide hiç geçmeyen "
    "isim UYDURMA. Çıktı yalnızca geçerli JSON."
)

USER_TMPL = (
    "Aşağıda 1980 SON METRO (Le Dernier Métro) closing jeneriğinin gürültülü çok-bant OCR dökümü var "
    "({n} satır). Bunu temizle ve birleştir.\n\n"
    "Çıktı şeması (geçerli JSON, başka metin yok):\n"
    "{{\n"
    '  "cast": [{{"name": "..."}}],\n'
    '  "crew": [{{"role": "...", "name": "..."}}],\n'
    '  "songs": [{{"title": "...", "detail": "..."}}],\n'
    '  "dropped_as_noise_count": 0\n'
    "}}\n\n"
    "Ham OCR satırları (kaynak bant etiketiyle):\n{lines}"
)


def _prefilter(lines):
    """403 gurultulu satiri kucult: exact-dedup (case-insensitive) + cop ele.
    Tekrarlar zaten LLM'e bilgi katmiyor; cop sadece yavaslatiyor."""
    seen = set()
    out = []
    for l in lines:
        t = (l.get("text") or "").strip()
        c = float(l.get("confidence", 0) or 0)
        if len(t) < 4:          # tek-harf / kisa cop
            continue
        if c < 0.5:             # dusuk guven cop
            continue
        key = t.upper().replace(" ", "")
        if key in seen:
            continue
        seen.add(key)
        out.append(l)
    return out


def main():
    data = json.loads(BAND_LINES.read_text(encoding="utf-8"))
    raw = data.get("lines", [])
    lines = _prefilter(raw)
    print(f"prefilter: {len(raw)} -> {len(lines)} satir")
    rendered = "\n".join(
        f"- {l.get('text','')}  [{l.get('source','?')} c={l.get('confidence',0):.2f}]"
        for l in lines
    )
    user = USER_TMPL.format(n=len(lines), lines=rendered)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "keep_alive": "10m",
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }
    req = urllib.request.Request(
        OLLAMA,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    parts = []
    print("stream basliyor...", flush=True)
    with urllib.request.urlopen(req, timeout=120) as r:
        for line in r:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line.decode("utf-8"))
            parts.append(obj.get("message", {}).get("content", ""))
            if obj.get("done"):
                break
    content = "".join(parts)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "merged_from_band_raw.txt").write_text(content, encoding="utf-8")

    # JSON'u ayıkla
    txt = content.strip()
    if "```" in txt:
        txt = txt.split("```")[1]
        if txt.startswith("json"):
            txt = txt[4:]
    try:
        merged = json.loads(txt.strip())
    except Exception as e:
        print("JSON parse FAIL:", e)
        print(content[:800])
        return
    (OUT_DIR / "merged_from_band.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    cast = merged.get("cast", [])
    crew = merged.get("crew", [])
    songs = merged.get("songs", [])
    print(f"GIRDI: {len(lines)} ham satir (band_motion)")
    print(f"CIKTI: cast={len(cast)} crew={len(crew)} songs={len(songs)}")
    print("\n-- CAST --")
    for c in cast:
        print("  ", c.get("name"))
    print("\n-- SONGS --")
    for s in songs:
        print("  ", s.get("title"))
    # basit halüsinasyon kontrolü: cast soyad harfleri girdide (gevşek) geçiyor mu
    blob = " ".join(l.get("text", "") for l in lines).upper().replace(" ", "")
    print("\n-- HALUSINASYON KONTROL (cast soyadi girdide var mi) --")
    for c in cast:
        nm = (c.get("name") or "").upper()
        toks = [t for t in nm.replace("-", " ").split() if len(t) >= 4]
        ok = any(t.replace(" ", "") in blob for t in toks) if toks else False
        print(f"  {'OK ' if ok else '?? '} {c.get('name')}")


if __name__ == "__main__":
    main()
