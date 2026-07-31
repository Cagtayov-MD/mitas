#!/usr/bin/env python3
"""HİBRİT OKUMA — üretim künye okuyucusu: Messi(frame) + İbrahimovic(master) → birleşim.

Çağatay kararı (2026-07-31 akşam): Paddle okuma kalitesi güvenilmez
(BOZGUNCULAR kunye.txt: 'CO SUBBING' 5 farklı bozulma, 'OAN MSIMTLRE');
deepseek aynı kareleri temiz okudu. Ana yol artık bu betik; Paddle
MITAS_OKUMA_MOTORU=paddle ile geri gelir (kill-switch, silinmedi).

SÖZLEŞME — _pipe_ocr.py ile BİREBİR (pipeline'ın geri kalanı değişmesin):
  CLI   : --frames DIR [DIR...] --out DIR --profile P
  Dosya : kunye.txt (kanonik satırlar) · ocr_ham.txt (ham, iki kol) ·
          ocr_summary.json {bucket, kunye_line_count, ...} · hibrit_iz.jsonl (kaynak izi)
  stdout: son satır JSON {status, out, summary_path, kunye_line_count,
          paddle_line_count, bucket, engine}
  bucket: GUVENILIR | BOS   (MOTOR_YOK asla — find_usable_ocr onu dışlıyor)

FAIL-SAFE (sessiz düşme YASAK — FIGO v5 dersi, 2026-07-31): zincir çökerse veya
0 satır üretirse AYNI argümanlarla _pipe_ocr.py (Paddle) koşulur, onun çıktısı
aynen akar; stderr'e HIBRIT_FALLBACK damgası basılır ve summary'ye yazılır.

SIRALAMA GERÇEKLERİ (mitas_pipeline akışına göre — çarpışma analizi):
  * OCR Popen 2399'da; pipeline 2506'da communicate() ile BLOKLAR → bu betik
    biterken pipeline'ın çıkış-havuzu süreci (2643) HENÜZ BAŞLAMAMIŞTIR.
    frames/cikis_jenerik'i burada üretmek güvenli; pipeline'ınki sonra
    kendi turunu atar (idempotent, ~20 sn).
  * GİRİŞ havuzu süreci (2177-2347) bu betikle EŞZAMANLI koşuyor olabilir →
    frames/giris_jenerik'e DOKUNULMAZ. Giriş için Messi seçimi HAM giriş
    karelerinden yapılır (salt-okur).
  * Master'ı burada üretmek DİLİM-TAZELE'yi (2783) aynı koşuda ateşler —
    "bir koşu geriden" bug'ı (2026-07-31 sabah bulgusu) yan etki olarak kapanır.

MODEL: iki kol da deepseek-ocr (Ollama) — Çağatay bayrak önerisindeki "bugünkü
kanıtlı düzen". MASTER_GOZU=qwen8-vllm çaprazı ölçüm yatağında; üretime üretim
verisiyle karar verilecek. num_ctx=8192: pipeline zaten OLLAMA'yı böyle ısıtıyor.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
PY_OCR = PROJE / "venvs" / "ocr" / "bin" / "python"
OLLAMA = (os.environ.get("MITAS_OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")

MODEL = os.environ.get("MITAS_HIBRIT_MODEL", "deepseek-ocr:latest")
ISTEM = "Free OCR."
CAGRI_TIMEOUT = int(os.environ.get("MITAS_HIBRIT_CAGRI_TIMEOUT", "300") or 300)
MAX_SAYFA_CIKIS = int(os.environ.get("MITAS_HIBRIT_MAX_SAYFA", "100") or 100)
MAX_SAYFA_GIRIS = int(os.environ.get("MITAS_HIBRIT_MAX_SAYFA_GIRIS", "40") or 40)
BANT_H, BINDIRME = 1100, 120   # pilot_hat.oku_master ile aynı geometri

sys.path.insert(0, str(PROJE / "harness" / "track_kunye"))


def _log(msg: str) -> None:
    print(f"[hibrit] {msg}", flush=True)


# ── okuyucu ──────────────────────────────────────────────────────────────────

def ollama_oku(png: Path) -> str:
    gov = {"model": MODEL, "prompt": ISTEM, "stream": False,
           "images": [base64.b64encode(png.read_bytes()).decode()],
           "options": {"temperature": 0.0, "num_predict": 2048, "num_ctx": 8192}}
    req = urllib.request.Request(f"{OLLAMA}/api/generate",
                                 data=json.dumps(gov).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=CAGRI_TIMEOUT) as r:
        return json.loads(r.read()).get("response", "") or ""


def satirlari_ayikla(cevap: str) -> list[str]:
    out = []
    for ln in (cevap or "").splitlines():
        ln = ln.strip().strip("`").lstrip("#").strip().strip("*").strip()
        if len(ln) >= 2:
            out.append(ln)
    return out


# ── HAKEM v1: sayfa-düzeyi PİKSEL KANITI (Çağatay, 2026-07-31 gece) ─────────
# "Messi ile İbra çatışırsa piksele bak" fikrinin ilk somut hali: her kaynak
# PNG'ye Paddle det-only sorulur — "bu piksellerde yazı kutusu VAR MI?"
# Kutu sayısı 0 iken satır üretilmişse o satırlar UYDURMADIR (deepseek boş
# karede '- 1' listesi uyduruyor — ölçüldü) → piksel kanıtıyla düşer.
# Det zayıflığı önemsiz: Paddle'ın kusuru REC'te, DET'te değil (varlık
# saptamak okumaktan kolay). Satır-düzeyi bbox eşleşmesi (y-koordinatlı)
# sonraki katman; bu v1 sayfa-düzeyi.
# Det motoru yüklenemezse hakem SESSİZCE DEĞİL, summary'de det_durum ile
# raporlanarak devre dışı kalır (sessiz düşme yasak).
_DET = {"denendi": False, "modul": None}


def _det_kutu_n(p: Path) -> int | None:
    """Kaynak PNG'deki det kutu sayısı; motor yoksa None (hüküm verme)."""
    if not _DET["denendi"]:
        _DET["denendi"] = True
        try:
            sys.path.insert(0, str(PROJE / "harness" / "kunye_kiyas"))
            import credit_box  # noqa: PLC0415
            _DET["modul"] = credit_box
        except Exception as e:  # noqa: BLE001
            _log(f"HAKEM det motoru yüklenemedi ({type(e).__name__}) — piksel kanıtı DEVRE DIŞI")
    cb = _DET["modul"]
    if cb is None:
        return None
    try:
        # DEJENERE KUTU FİLTRESİ (ALİE g_0153, 2026-07-31 gece): det bazen TÜM
        # KAREYİ tek kutu sayıyor — o "kutu" yazı kanıtı değildir ve boş karedeki
        # betimleme uydurmasını sahte-pikselli gösterir. Kare alanının >%60'ını
        # kaplayan kutu sayılmaz.
        import cv2  # noqa: PLC0415
        im = cv2.imread(str(p))
        if im is None:
            return None
        alan = im.shape[0] * im.shape[1]
        n = 0
        for poly in cb._polys(str(p)):
            xs = [pt[0] for pt in poly]
            ys = [pt[1] for pt in poly]
            if (max(xs) - min(xs)) * (max(ys) - min(ys)) < 0.6 * alan:
                n += 1
        return n
    except Exception:  # noqa: BLE001 — tek karenin det hatası hüküm üretmez
        return None


def sayfalari_oku(sayfalar: list[Path], etiket: str) -> list[dict]:
    """Sayfa sayfa oku; KAYNAK İZİ + sayfa PİKSEL KANITI (kutu_n) korunur.
    Tek sayfa hatası kolu durdurmaz; hata SAYILIR ve summary'ye yazılır."""
    kayitlar: list[dict] = []
    hata_n = 0
    for i, p in enumerate(sayfalar, 1):
        try:
            satirlar = satirlari_ayikla(ollama_oku(p))
        except Exception as e:  # noqa: BLE001
            hata_n += 1
            _log(f"{etiket} {p.name} HATA {type(e).__name__}: {str(e)[:80]}")
            continue
        kutu_n = _det_kutu_n(p) if satirlar else None
        for sira, s in enumerate(satirlar):
            kayitlar.append({"kol": etiket, "kaynak": p.name, "sira": sira,
                             "text": s, "kutu_n": kutu_n})
    if hata_n:
        _log(f"{etiket}: {hata_n}/{len(sayfalar)} sayfa okunamadı")
    return kayitlar


# ── yapısal veto (KB'siz — halüsinasyon emniyeti) ────────────────────────────
# ronaldo.halusinasyon_mu KULLANILMAZ: >8-kelime kuralı boş KB'de her uzun
# GERÇEK künye satırını yutuyordu (denetim bulgusu; test_ronaldo.py:80-87 kanıt).

_PROSA_FIIL = {
    "is", "are", "was", "were", "has", "have", "had", "he", "she", "it",
    "its", "there", "appears", "appear", "seems", "seem", "looks",
    "showing", "shows", "suggests", "suggesting",
    "captures", "capturing", "depicts", "depicting", "likely",
    "gorunuyor", "goruluyor", "gosteriyor", "bulunuyor", "olabilir", "vardir",
}


def yapisal_veto(s: str, fold, garble) -> bool:
    if s.startswith("[") or s.startswith("("):
        return True                    # model sahneyi ANLATIYOR
    if s.startswith(("- ", "* ", "• ")):
        return True                    # madde imi = betimleme listesi (ALİE vakası,
                                       # 2026-07-31: '- A river flowing...' — jenerikte
                                       # madde imi olmaz; sahnedeki 1 tabela det'i sayfa-
                                       # düzeyi hakemi geçirtti, satır>kutu kuralı v1.1'de)
    if "**" in s:
        return True                    # markdown artefaktı
    harfler = [c for c in s if c.isalpha()]
    if not harfler:
        return True                    # '- 1' liste-numarası çöpü (ölçüldü: %32)
    if sum(1 for c in harfler if "一" <= c <= "鿿") / len(harfler) > 0.3:
        return True                    # CJK betimleme modu
    if any(k in _PROSA_FIIL for k in fold(s).split()):
        return True                    # düzyazı fiil imzası
    return garble(s)                   # slit çift-basımı / tekrar deseni


# ── kollar ───────────────────────────────────────────────────────────────────

def kol_frame(clip_dir: Path, frame_dirs: list[Path]) -> list[dict]:
    """Messi seçimi + okuma. Çıkış: cikis_jenerik (bu betik garanti eder);
    giriş: HAM giris karelerinden seçim (giris_jenerik'e dokunma — eşzamanlılık)."""
    import pilot_hat as ph

    kayitlar: list[dict] = []
    cikis_havuz = clip_dir / "frames" / "cikis_jenerik"
    if cikis_havuz.is_dir() and any(cikis_havuz.glob("*.png")):
        secim, ist = ph.havuz_derle_dizin(cikis_havuz, "*.png")
        if len(secim) > MAX_SAYFA_CIKIS:
            adim = len(secim) / MAX_SAYFA_CIKIS
            secim = [secim[int(i * adim)] for i in range(MAX_SAYFA_CIKIS)]
        _log(f"frame/cikis: havuz={ist.get('kare')} → {len(secim)} sayfa")
        kayitlar += sayfalari_oku(secim, "frame_cikis")

    giris_raw = next((d for d in frame_dirs if d.name == "giris"), None)
    if giris_raw and giris_raw.is_dir():
        secim, ist = ph.havuz_derle_dizin(giris_raw, "*.png")
        if len(secim) > MAX_SAYFA_GIRIS:
            adim = len(secim) / MAX_SAYFA_GIRIS
            secim = [secim[int(i * adim)] for i in range(MAX_SAYFA_GIRIS)]
        # KUYRUK SİGORTASI (ALİE vakası, 2026-07-31 gece): TRT geleneğinde
        # YÖNETMEN kartı giriş jeneriğinin SON kartıdır (senaryo→yönetmen).
        # ALİE'de giriş master'ı 'senaryo'da kesildi (havuz yarışı) ve yönetmen
        # 1632 satırın hiçbirine girmedi → QC1 RED. Ham girişin son kareleri
        # HER ZAMAN okunur — örnekleme aralığına düşmese bile.
        tum_giris = sorted(giris_raw.glob("*.png"))
        kuyruk = tum_giris[-12:]
        mevcut = {p.name for p in secim}
        secim += [p for p in kuyruk if p.name not in mevcut]
        _log(f"frame/giris(ham): {ist.get('kare')} → {len(secim)} sayfa (kuyruk sigortalı)")
        kayitlar += sayfalari_oku(secim, "frame_giris")
    return kayitlar


def kol_master(clip_dir: Path, out_dir: Path) -> list[dict]:
    """Master bantlara böl + oku. Bant y-ofseti İZDE taşınır (bbox ön şartı)."""
    import cv2

    kayitlar: list[dict] = []
    for png_ad, etiket in (("reading_master_runaware.png", "master_cikis"),
                           ("giris_reading_master_runaware.png", "master_giris")):
        mp = clip_dir / png_ad
        if not mp.is_file():
            continue
        im = cv2.imread(str(mp))
        if im is None:
            continue
        bant_dir = out_dir / "hibrit_bantlar" / etiket
        bant_dir.mkdir(parents=True, exist_ok=True)
        H = im.shape[0]
        yollar, ofs = [], []
        y = i = 0
        while y < H:
            bant = im[y:min(y + BANT_H, H)]
            if bant.shape[0] >= 40:
                p = bant_dir / f"bant_{i:03d}.png"
                cv2.imwrite(str(p), bant)
                yollar.append(p)
                ofs.append(y)
                i += 1
            if y + BANT_H >= H:
                break
            y += BANT_H - BINDIRME
        _log(f"{etiket}: {im.shape[1]}x{H} → {len(yollar)} bant")
        okunan = sayfalari_oku(yollar, etiket)
        ofmap = {p.name: o for p, o in zip(yollar, ofs)}
        for k in okunan:
            k["bant_y0"] = ofmap.get(k["kaynak"])
        kayitlar += okunan
    return kayitlar


def havuz_garanti(clip_dir: Path, frame_dirs: list[Path]) -> None:
    """cikis_jenerik yoksa FIGO ile üret (pipeline'ınki daha sonra; çakışmaz)."""
    havuz = clip_dir / "frames" / "cikis_jenerik"
    if havuz.is_dir() and any(havuz.glob("*.png")):
        return
    kaynak = next((d for d in frame_dirs if d.name == "cikis"), None)
    if kaynak is None:
        return
    _log("cikis_jenerik yok → FIGO havuzu üretiliyor")
    r = subprocess.run(
        [str(PY_OCR), str(HERE / "_jenerik_pool.py"),
         "--frames", str(kaynak), "--pool", str(havuz),
         "--debug-root", str(clip_dir / "jenerik_debug"), "--segment", "cikis"],
        capture_output=True, text=True, timeout=1800)
    n = len(list(havuz.glob("*.png"))) if havuz.is_dir() else 0
    _log(f"FIGO: {n} kare (rc={r.returncode})")


def master_garanti(clip_dir: Path) -> None:
    """reading_master_runaware.png yoksa üret. YAN ETKİ: DİLİM-TAZELE (2783)
    aynı koşuda ateşlenir — dilim korpusu artık bir koşu geride kalmaz."""
    if (clip_dir / "reading_master_runaware.png").is_file():
        return
    runner = PROJE / "OCR-worktree" / "master_png_monitor.py"
    base = clip_dir.name
    _log("master yok → master_png_monitor --once")
    r = subprocess.run([str(PY_OCR), str(runner), "--once", str(clip_dir), "--base", base],
                       capture_output=True, text=True, timeout=900)
    _log(f"master: cikis={'VAR' if (clip_dir / 'reading_master_runaware.png').is_file() else 'YOK'} "
         f"(rc={r.returncode})")


# ── birleşim ─────────────────────────────────────────────────────────────────

def birlesim(frame_k: list[dict], master_k: list[dict]) -> dict:
    """BİRLEŞİM (kesişim değil) + yapısal veto + fold-dedup.
    KB YOK: varlık kararı piksele/QC'ye ait; KB yalnız imlacı (aşağı katman)."""
    import ronaldo as rn

    def temizle(kayitlar):
        tut, at = [], []
        for k in kayitlar:
            # HAKEM v1 — piksel kanıtı: kaynak sayfada det kutusu SIFIR ise
            # satır ekranda YOKTUR (uydurma). None = motor yok/hata → hüküm verme.
            if k.get("kutu_n") == 0:
                at.append("[piksel0] " + k["text"])
                continue
            if yapisal_veto(k["text"], rn.fold_tr, rn.garble_mi):
                at.append(k["text"])
            else:
                tut.append(k)
        return tut, at

    f_t, f_at = temizle(frame_k)
    m_t, m_at = temizle(master_k)

    kb: set[str] = set()
    gorulen: set[str] = set()
    birlesik: list[dict] = []
    eslesen_n = 0
    for k in f_t + m_t:                       # sıra: frame omurga, master doldurur
        fold = rn.fold_tr(k["text"])
        if fold in gorulen:
            eslesen_n += 1
            continue
        es = next((b for b in birlesik if rn.satir_esle(k["text"], b["text"], kb)), None)
        if es is not None:
            eslesen_n += 1
            continue
        gorulen.add(fold)
        birlesik.append(k)
    return {"birlesik": birlesik, "eslesen_n": eslesen_n,
            "frame_n": len(f_t), "master_n": len(m_t),
            "veto_n": len(f_at) + len(m_at), "veto_ornek": (f_at + m_at)[:20]}


# ── ana akış ─────────────────────────────────────────────────────────────────

def paddle_fallback(argv: list[str], sebep: str) -> int:
    """Zincir çuvalladı → Paddle. YÜKSEK SESLE: stderr damgası + stdout akışı."""
    print(f"HIBRIT_FALLBACK_PADDLE sebep={sebep}", file=sys.stderr, flush=True)
    _log(f"FALLBACK → _pipe_ocr.py (sebep: {sebep})")
    r = subprocess.run([str(PY_OCR), str(HERE / "_pipe_ocr.py"), *argv],
                       capture_output=False, timeout=3000)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", default="film")
    a, _bilinmeyen = ap.parse_known_args()

    argv_gecis = ["--frames", *a.frames, "--out", a.out, "--profile", a.profile]
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    clip_dir = out_dir.parent.parent
    frame_dirs = [Path(f) for f in a.frames]
    t0 = time.perf_counter()

    try:
        havuz_garanti(clip_dir, frame_dirs)
        master_garanti(clip_dir)

        frame_k = kol_frame(clip_dir, frame_dirs)
        master_k = kol_master(clip_dir, out_dir)
        b = birlesim(frame_k, master_k)
        satirlar = [k["text"] for k in b["birlesik"]]

        if not satirlar:
            return paddle_fallback(argv_gecis, "sifir_satir")

        # ── sözleşme dosyaları ──
        (out_dir / "kunye.txt").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
        ham = [k["text"] for k in frame_k] + [k["text"] for k in master_k]
        (out_dir / "ocr_ham.txt").write_text("\n".join(ham) + "\n", encoding="utf-8")
        with (out_dir / "hibrit_iz.jsonl").open("w", encoding="utf-8") as h:
            for k in frame_k + master_k:
                h.write(json.dumps(k, ensure_ascii=False) + "\n")

        sure = round(time.perf_counter() - t0, 1)
        bucket = "GUVENILIR" if len(satirlar) >= 3 else "BOS"
        piksel_veto = sum(1 for v in b["veto_ornek"] if str(v).startswith("[piksel0]"))
        ozet = {
            "engine": "hibrit-deepseek(messi+ibra)",
            "model": MODEL, "bucket": bucket,
            "kunye_line_count": len(satirlar),
            "frame_satir": b["frame_n"], "master_satir": b["master_n"],
            "eslesen_n": b["eslesen_n"], "veto_n": b["veto_n"],
            "hakem_det": ("aktif" if _DET["modul"] is not None else "devre_disi"),
            "piksel_veto_ornek_n": piksel_veto,
            "veto_ornek": b["veto_ornek"], "sure_sn": sure,
        }
        summary_path = out_dir / "ocr_summary.json"
        summary_path.write_text(json.dumps(ozet, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        _log(f"bitti: {len(satirlar)} satır (frame {b['frame_n']} + master {b['master_n']}, "
             f"veto {b['veto_n']}) {sure} sn")
        print(json.dumps({
            "status": "done", "out": str(out_dir),
            "summary_path": str(summary_path),
            "kunye_line_count": len(satirlar), "paddle_line_count": 0,
            "bucket": bucket, "engine": ozet["engine"],
        }, ensure_ascii=False), flush=True)
        return 0
    except Exception as e:  # noqa: BLE001 — üst duvar: sessiz düşme YASAK, Paddle'a yüksek sesle
        return paddle_fallback(argv_gecis, f"{type(e).__name__}:{str(e)[:120]}")


if __name__ == "__main__":
    raise SystemExit(main())
