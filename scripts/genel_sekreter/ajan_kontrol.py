"""KONTROL Analiz Ajanı — SİSTEM KALBİ

Pipeline çıktılarında KONTROL'e düşen filmlerin kök nedenini tespit eder.
Sadece raporlama — dosya değiştirmez, işlem yapmaz.

Her film için:
  - Neden KONTROL'e düştü?
  - Kimin hatası? (OCR / Parser / KB / Export / Kod bloğu)
  - Kanıt: hangi satır, hangi frame, hangi veri

Pattern analizi:
  - 25 film yönetmen kontrolüne takıldı
  - 8'i credits_parser regex hatası
  - 6'sı OCR karakter bozukluğu
  - ...
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from genel_sekreter.config import DB, KONTROL_DIR, ONAYLI_DIR


# ── Neden sınıflandırma desenleri ─────────────────────────────────────────
# Her desen: (imza, sınıf, sorumlu_modül, detay_seviyesi)
DESENLER: list[tuple[str, str, str]] = [
    # Kimlik / doğrulama
    ("kimlik doğrulanamadı", "kimlik_kaynaksiz", "QC2/kimlik — kıyas kaynağı yok"),
    ("kimlik çelişkisi", "kimlik_celiski", "QC2/kimlik — KB cross-check uyuşmazlığı"),
    ("kimlik kurulamadı", "kimlik_zayif", "QC2/qc_block — web çapası kilitlenemedi"),
    ("cast-örtüşme", "kimlik_zayif", "QC2/qc_block — cast örtüşme <2"),
    # Künye kalitesi (QC1)
    ("qc1 başarısız", "kunye_kalite_qc1", "QC1 — okuma→rol eşleme başarısız"),
    ("OCR+VL ikisi de RED", "kunye_kalite_okuma", "QC1 — hem OCR hem VL yetersiz"),
    ("düşük künye kalitesi", "kunye_kalite", "QC1 — genel kalite düşük"),
    ("OCR yetersiz", "kunye_okuma_ocr", "QC1 — OCR çıktı yetersiz"),
    # Okuma hataları
    ("okunamadı", "kunye_okuma", "OCR/okuma — metin çıkarılamadı"),
    ("yeniden-okuma", "kunye_okuma", "OCR/okuma — yeniden okuma başarısız"),
    ("motor_yok", "teknik_motor", "OCR — motor bulunamadı"),
    # Yönetmen
    ("yönetmen", "yonetmen", "Rol eşleme — yönetmen çıkarılamadı"),
    ("yön+yapımcı yok", "yonetmen_yapimci", "Qwen QC — yönetmen+yapımcı eksik"),
    # Cast / oyuncu
    ("cast", "cast", "Rol eşleme — oyuncu listesi"),
    ("oyuncu yok", "cast_bos", "Qwen QC — oyuncu bulunamadı"),
    # Özet
    ("özet", "ozet", "Özet üretimi — LLM"),
    # Afiş
    ("afiş", "afis", "Afiş doğrulama — poster_fetch"),
    ("poster", "afis", "Afiş doğrulama — poster_fetch"),
    # Ses / dil
    ("ses", "ses_dil", "ASR — kanal/dil tespiti"),
    ("dil", "ses_dil", "ASR — kanal/dil tespiti"),
    ("Latin-dışı", "render_latin", "QC — Latin-dışı alfabe romanizasyon"),
    # Render / PDF
    ("render", "render", "PDF render — çıktı kalitesi"),
    # Teknik
    ("frame", "teknik_frame", "ÇÖZ — kare çıkarma"),
    ("HATA", "teknik_hata", "Teknik — genel hata"),
]


def _siniflandir_neden(neden: str) -> tuple[str, str]:
    """Neden metnini sınıflandır → (sınıf, sorumlu_modül)."""
    n = neden.lower()
    for imza, sinif, modul in DESENLER:
        if imza.lower() in n:
            return sinif, modul
    return "siniflandirilamadi", neden[:80]


def _durum_oku(film_dir: Path) -> dict | None:
    """_DURUM.json'ı güvenli oku."""
    durum_path = film_dir / "_DURUM.json"
    if not durum_path.is_file():
        return None
    try:
        return json.loads(durum_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _export_trt_ids(export_dir: Path) -> set[str]:
    """Export klasöründeki PDF'lerden TRT ID'lerini çıkar."""
    import re
    ids = set()
    if not export_dir.is_dir():
        return ids
    for f in export_dir.iterdir():
        m = re.search(r'(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)', f.name)
        if m:
            ids.add(m.group(1))
    return ids


def _kok_neden(film_dir: Path, durum: dict) -> dict:
    """Tek film için kök neden analizi — pipeline trace'ini takip et.

    _log.jsonl → olay zaman çizelgesi
    kunye*.txt → OCR ne okudu?
    karar.pipeline.json → hangi gate reddetti?

    Returns: {
        "kok": str,          # tek cümle kök neden
        "pipeline_iz": [],   # zaman çizelgesi
        "ocr_okundu": str,   # OCR ne gördü (ilk 200 karakter)
        "kategori": str,     # JENERIK_KAYIP | OCR_HATA | PARSE_HATA | KB_EKSIK | QC_HATA | DIGER
    }
    """
    kok = "Bilinmiyor"
    kategori = "DIGER"
    pipeline_iz = []
    ocr_okundu = ""

    # ── 1. Pipeline iz (_log.jsonl) ─────────────────────────────────
    log_path = film_dir / "_log.jsonl"
    olaylar = []
    if log_path.is_file():
        try:
            for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    evt = json.loads(line.strip())
                    olaylar.append(evt)
                    kind = evt.get("kind", "")
                    summary = str(evt.get("summary", ""))[:100]
                    ts = evt.get("ts", "")[11:19]  # HH:MM:SS
                    pipeline_iz.append(f"{ts} | {kind}: {summary}")
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass

    # ── 2. OCR çıktısı (kunye*.txt) ─────────────────────────────────
    for pattern in ("*kunye3.txt", "*kunye.txt", "*kunye2.txt"):
        matches = list(film_dir.glob(pattern))
        if matches:
            try:
                txt = matches[0].read_text(encoding="utf-8", errors="replace")
                # İlk anlamlı satırları al
                satirlar = [s.strip() for s in txt.splitlines() if s.strip() and not s.startswith("#")]
                ocr_okundu = "\n".join(satirlar[:10])[:300]
            except OSError:
                pass
            break

    # ── 3. Kök neden tespiti (olay zincirini takip et) ──────────────
    nedenler = durum.get("neden") or []
    ocr_bucket = durum.get("ocr_bucket", "")
    qwen_qc = durum.get("qwen_qc", {})

    # Olay türlerini kontrol et
    kinds = [e.get("kind", "") for e in olaylar]

    # Jenerik havuz boş mu?
    jenerik_bos = any("jenerik_pool" in k and "empty" in str(e.get("summary", "")).lower()
                      for k, e in zip(kinds, olaylar))

    # QC1 red mi?
    qc1_red = "credit_qc1_red" in kinds
    qc1_failed = "credit_qc1_failed" in kinds

    # VL fallback tetiklendi mi?
    vl_fallback = "credit_vl_fallback" in kinds

    # OCR bucket kontrolü
    if ocr_bucket == "HATA":
        kok = "OCR motoru hata verdi — frame okuma tamamen başarısız"
        kategori = "OCR_HATA"
    elif ocr_bucket == "MOTOR_YOK":
        kok = "OCR motoru bulunamadı — motor konfigürasyon hatası"
        kategori = "OCR_HATA"
    elif jenerik_bos or (not ocr_okundu.strip()):
        kok = "Jenerik karesi bulunamadı — Kobe onset detection başarısız veya jenerik yok"
        kategori = "JENERIK_KAYIP"
    elif qc1_red and not vl_fallback:
        # OCR okudu ama rol eşleme başarısız
        if "yönetmen" in " ".join(nedenler).lower():
            kok = "OCR metin okudu ama yönetmen rolü eşlenemedi — parser/kelime hazinesi eksik"
            kategori = "PARSE_HATA"
        elif "oyuncu" in " ".join(nedenler).lower() or "cast" in " ".join(nedenler).lower():
            kok = "OCR metin okudu ama cast çıkarılamadı — oyuncu isimleri tanınamadı"
            kategori = "PARSE_HATA"
        else:
            kok = "QC1 reddetti — OCR çıktısı künye formatına uymuyor"
            kategori = "QC_HATA"
    elif qc1_red and vl_fallback and qc1_failed:
        kok = "Hem OCR hem VL okuma başarısız — frame kalitesi yetersiz veya jenerik yapısı bozuk"
        kategori = "JENERIK_KAYIP"
    elif "kimlik doğrulanamadı" in " ".join(nedenler).lower():
        kok = "Künye çıkarıldı ama KB doğrulama kaynağı yok — IMDb/Wikidata'da bu film bulunamadı"
        kategori = "KB_EKSIK"
    elif "kimlik çelişkisi" in " ".join(nedenler).lower():
        kok = "Künye ile KB verisi uyuşmuyor — OCR yanlış isim okumuş olabilir"
        kategori = "PARSE_HATA"
    elif any("qc_block" in n for n in nedenler):
        kok = "QC block takıldı — web çapası veya cast örtüşme yetersiz"
        kategori = "QC_HATA"
    elif not qwen_qc.get("yonetmen_var"):
        kok = "Qwen QC yönetmen bulamadı — metin çıktısında yönetmen adı yok"
        kategori = "PARSE_HATA"
    elif not qwen_qc.get("ozet_var"):
        kok = "Özet üretilemedi — ASR transkript yetersiz veya LLM hata verdi"
        kategori = "DIGER"
    else:
        # Genel fallback: ilk nedeni kök olarak al
        if nedenler:
            kok = nedenler[0]
        else:
            kok = "Neden bilgisi bulunamadı"

    return {
        "kok": kok,
        "kategori": kategori,
        "pipeline_iz": pipeline_iz,
        "ocr_okundu": ocr_okundu,
        "neden_sayisi": len(nedenler),
    }


def analiz_kontrol() -> dict:
    """KONTROL filmleri analiz et.

    Kaynak: Mitas Output/export/KONTROL (gerçek teslim durumu).
    Detay: Database/<film>/_DURUM.json (neden, timing, qc verisi).
    """
    if not DB.is_dir():
        return _bos_sonuc()

    # Export klasöründen güncel KONTROL ve ONAYLI TRT ID'leri
    kontrol_ids = _export_trt_ids(KONTROL_DIR)
    onayli_ids = _export_trt_ids(ONAYLI_DIR)

    kontrol_filmler: list[dict] = []
    toplam_film = 0

    for d in sorted(DB.iterdir()):
        if not d.is_dir():
            continue
        durum = _durum_oku(d)
        if durum is None:
            continue
        toplam_film += 1
        # SADECE export KONTROL klasöründeki filmleri al (TRT ID eşleşmesi)
        trt_id = durum.get("trt_id", "")
        if not trt_id or trt_id not in kontrol_ids:
            continue
        kontrol_filmler.append({"dir": d.name, "durum": durum})

    if not kontrol_filmler:
        return _bos_sonuc(toplam_film)

    # ── Neden sınıflandırma ───────────────────────────────────────────
    sinif_sayaci: Counter = Counter()
    sinif_ornekler: dict[str, list[str]] = {}
    sinif_modul: dict[str, str] = {}

    for film in kontrol_filmler:
        nedenler = film["durum"].get("neden") or []
        for neden in nedenler:
            sinif, modul = _siniflandir_neden(neden)
            sinif_sayaci[sinif] += 1
            sinif_modul[sinif] = modul
            if sinif not in sinif_ornekler:
                sinif_ornekler[sinif] = []
            if len(sinif_ornekler[sinif]) < 5:
                sinif_ornekler[sinif].append(neden[:120])

    toplam_neden = sum(sinif_sayaci.values())
    neden_siniflar = []
    for sinif, sayi in sinif_sayaci.most_common():
        neden_siniflar.append({
            "sinif": sinif,
            "modul": sinif_modul.get(sinif, "?"),
            "sayi": sayi,
            "yuzde": round(sayi / toplam_neden * 100, 1) if toplam_neden else 0,
            "ornekler": sinif_ornekler.get(sinif, []),
        })

    # ── kontrol_tip dağılımı ──────────────────────────────────────────
    tip_dagilim: Counter = Counter()
    for film in kontrol_filmler:
        tip = film["durum"].get("route", {}).get("kontrol_tip", "UNKNOWN")
        tip_dagilim[tip or "UNKNOWN"] += 1

    # ── Her film için detay rapor + kök neden ──────────────────────
    film_raporlari = []
    for film in kontrol_filmler:
        d = film["durum"]
        nedenler = d.get("neden") or []
        siniflar = [_siniflandir_neden(n) for n in nedenler]

        # Kök neden analizi
        film_path = DB / film["dir"]
        kok_bilgi = _kok_neden(film_path, d)

        film_raporlari.append({
            "title": d.get("title", "?"),
            "trt_id": d.get("trt_id", "?"),
            "dir": film["dir"],
            "karar": d.get("karar", "?"),
            "kontrol_tip": d.get("route", {}).get("kontrol_tip", "?"),
            "nedenler": nedenler,
            "siniflar": [{"sinif": s, "modul": m} for s, m in siniflar],
            "qwen_qc": d.get("qwen_qc", {}),
            "ocr_bucket": d.get("ocr_bucket", "?"),
            "timing_toplam": (d.get("timings_sec") or {}).get("toplam", 0),
            "kok": kok_bilgi["kok"],
            "kategori": kok_bilgi["kategori"],
            "pipeline_iz": kok_bilgi["pipeline_iz"],
            "ocr_okundu": kok_bilgi["ocr_okundu"],
        })

    # ── Sistemik bulgular ─────────────────────────────────────────────
    bulgular = _sistemik_bulgular(kontrol_filmler, neden_siniflar, toplam_film)

    return {
        "toplam_kontrol": len(kontrol_filmler),
        "toplam_film": toplam_film,
        "neden_siniflar": neden_siniflar,
        "kontrol_tip_dagilim": dict(tip_dagilim.most_common()),
        "sistemik_bulgular": bulgular,
        "film_raporlari": film_raporlari,
    }


def _bos_sonuc(toplam_film: int = 0) -> dict:
    return {
        "toplam_kontrol": 0,
        "toplam_film": toplam_film,
        "neden_siniflar": [],
        "kontrol_tip_dagilim": {},
        "sistemik_bulgular": [],
        "film_raporlari": [],
    }


def _sistemik_bulgular(
    kontrol_filmler: list[dict],
    neden_siniflar: list[dict],
    toplam_film: int,
) -> list[str]:
    """Otomatik sistemik bulgu üretimi."""
    bulgular = []
    n_kontrol = len(kontrol_filmler)

    # Baskın sınıf
    if neden_siniflar:
        en_ust = neden_siniflar[0]
        if en_ust["yuzde"] >= 30:
            bulgular.append(
                f"**Baskın sorun:** `{en_ust['sinif']}` "
                f"({en_ust['sayi']} film, %{en_ust['yuzde']}) — "
                f"Sorumlu: {en_ust['modul']}. "
                f"Bu modülde iyileştirme KONTROL sayısını ciddi düşürür."
            )

    # KONTROL oranı
    if toplam_film > 0:
        kontrol_oran = round(n_kontrol / toplam_film * 100, 1)
        if kontrol_oran > 50:
            bulgular.append(
                f"**Yüksek KONTROL oranı:** %{kontrol_oran} "
                f"({n_kontrol}/{toplam_film}) — pipeline kalite eşiği "
                f"gözden geçirilmeli."
            )

    # OCR bucket analizi
    bucket_sayaci: Counter = Counter()
    for film in kontrol_filmler:
        bucket = film["durum"].get("ocr_bucket", "UNKNOWN")
        bucket_sayaci[bucket] += 1
    hata_bucket = bucket_sayaci.get("HATA", 0)
    if hata_bucket > 3:
        bulgular.append(
            f"**OCR HATA:** {hata_bucket} filmde OCR kalitesi HATA seviyesinde "
            f"— okuma motoru sorunu."
        )

    # Kümülatif kusur (3+ neden)
    coklu = sum(1 for f in kontrol_filmler if len(f["durum"].get("neden") or []) >= 3)
    if coklu > n_kontrol * 0.2:
        bulgular.append(
            f"**Kümülatif kusur:** {coklu} film (%{round(coklu/n_kontrol*100)}) "
            f"3+ nedenden KONTROL'e düştü — zincirleme sorun."
        )

    # Aynı kod bloğunda tekrar eden hata
    if neden_siniflar:
        for ns in neden_siniflar[:3]:
            if ns["sayi"] >= 5:
                bulgular.append(
                    f"**Tekrar eden hata:** `{ns['sinif']}` → "
                    f"{ns['sayi']} film aynı sorunu yaşıyor. "
                    f"Kod düzeltmesi ile toplu çözüm mümkün."
                )

    return bulgular


def rapor_kontrol() -> str:
    """KONTROL analiz raporu üret (Markdown)."""
    analiz = analiz_kontrol()

    satirlar = [
        "# KONTROL Analiz Raporu",
        "",
        "## Özet",
        "",
        f"- **Toplam film:** {analiz['toplam_film']}",
        f"- **KONTROL:** {analiz['toplam_kontrol']}",
        f"- **ONAYLI:** {analiz['toplam_film'] - analiz['toplam_kontrol']}",
        f"- **KONTROL oranı:** %{round(analiz['toplam_kontrol'] / max(analiz['toplam_film'], 1) * 100, 1)}",
        "",
        "## Neden Dağılımı",
        "",
        "| Sınıf | Sorumlu Modül | Sayı | % | Örnek |",
        "|-------|--------------|------|---|-------|",
    ]

    for ns in analiz["neden_siniflar"][:20]:
        ornek = ns["ornekler"][0][:60] if ns["ornekler"] else "—"
        satirlar.append(
            f"| {ns['sinif']} | {ns['modul']} | {ns['sayi']} | %{ns['yuzde']} | {ornek} |"
        )

    satirlar.extend(["", "## kontrol_tip Dağılımı", ""])
    for tip, sayi in sorted(
        analiz["kontrol_tip_dagilim"].items(), key=lambda x: -x[1]
    ):
        satirlar.append(f"- **{tip}:** {sayi} film")

    if analiz["sistemik_bulgular"]:
        satirlar.extend(["", "## Sistemik Bulgular", ""])
        for b in analiz["sistemik_bulgular"]:
            satirlar.append(f"- {b}")

    # Film detayları (ilk 30)
    if analiz["film_raporlari"]:
        satirlar.extend(["", "## Film Detayları (ilk 30)", ""])
        for fr in analiz["film_raporlari"][:30]:
            sinif_list = ", ".join(s["sinif"] for s in fr["siniflar"][:3])
            satirlar.append(f"### {fr['title']} ({fr['trt_id']})")
            satirlar.append(f"- **Tip:** {fr['kontrol_tip']}")
            satirlar.append(f"- **Sınıflar:** {sinif_list}")
            if fr["nedenler"]:
                for n in fr["nedenler"][:3]:
                    satirlar.append(f"  - {n[:100]}")
            satirlar.append(f"- **OCR:** {fr['ocr_bucket']}, **Süre:** {fr['timing_toplam']:.0f}sn")
            satirlar.append("")

    return "\n".join(satirlar)
