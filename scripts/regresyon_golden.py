# -*- coding: utf-8 -*-
"""REGRESYON-GOLDEN (2026-07-06; v2 2026-07-17): künye-okuma bilinen-vaka güvenlik ağı.
Her değişiklikten SONRA koşulur → yeni-yanlış/regresyon yakalar. Metin-yolu (_pipe_credit_text →
credit_text_read rol-eşleme), gerçek OCR-çıktısı üzerinde, ollama gerektirir.

v2 (2026-07-17, Çağatay "golden'ı genişlet" talimatı):
  * CAST kilidi eklendi: `cast` (geçmesi zorunlu alt-dizgiler) + `cast_yok` (sızmaması gerekenler)
    + `xfail_cast` (BİLİNEN-AÇIK eksikler: FAIL saymaz, düzelirse XPASS uyarısı verir ki beklenti
    `cast`e taşınsın). Yön-only eski 7 vaka AYNEN korundu, davranışları değişmedi.
  * VERİ-YOK ayrımı: hub/kunye yoksa vaka FAIL değil VERİ-YOK sayılır (BAŞKAN VE MARI: 2026-07-06
    force-rerun hub-silmesi, W:-restorasyon bekliyor — sahte-FAIL üretmesin; veri dönünce otomatik
    yeniden test edilir).
  * Otomatik env: mitas.env yüklü değilse EKSİK anahtarlar ondan tamamlanır — env'siz koşuda
    KB-DuckDB yolları boş kalıp garble→KB-kanonikleştirme sessizce devre dışı kalıyor ve sahte
    sonuç üretiyordu (2026-07-17 canlı tespit: Minnelli → 'Minnati').

KARAR (Hazır/Kontrol) NOTU — araştırma 2026-07-17: karar bu metin-yolunda DEĞİL,
mitas_pipeline routing'inde üretilir (~:3558, reasons→karar). Mekanizma-düzeyi koruma zaten var
(tests/test_pipeline_skip_routing.py + fadd0795'in 44 routing testi). Uçtan-uca karar-golden'ı
istenirse AYRI betik olmalı: seçilmiş 3-5 film × `--from-hub` koşusu (frames hazır, üretime
sıfır-dokunuş) + _DURUM.json karar-assert; maliyet film-başına GPU-dakikaları olduğu için bu
hızlı güvenlik ağına bilinçli olarak katılmadı.

ETHAN HAWKE bağımsız-kanıt vakası (task_61e2ea2d) buraya ALINAMADI: kullanılabilir hub verisi yok
(TACİZ 2000-0476 kunye.txt garble, isim yalnız vl_cast_aday'da). Mekanizma korunuyor:
tests/test_credit_text_read_cast_context.py (commit 5232386).
"""
import sys, glob, os, subprocess, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROJE = os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas")
PY = os.environ.get("MITAS_PDF_PYTHON", os.path.join(PROJE, "venvs", "asr", "bin", "python"))
DB = os.path.join(PROJE, "Database")


def _env_yukle() -> None:
    """mitas.env'den YALNIZ eksik anahtarları tamamla (source edilmiş env her zaman kazanır)."""
    p = os.path.join(PROJE, "mitas.env")
    if not os.path.exists(p):
        return
    try:
        for satir in open(p, encoding="utf-8", errors="replace"):
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            k, v = satir.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


# Vaka alanları: patt, title zorunlu.
#   yon       : beklenen yönetmen alt-dizgisi | "" = boş-OLMALI | None = yön test edilmez
#   cast      : her alt-dizgi cast listesinde geçmeli (case-insensitive)
#   cast_yok  : hiçbir alt-dizgi cast'te geçmemeli (crew-sızıntı kilidi)
#   xfail_cast: bilinen-açık eksikler — yoksa XFAIL (FAIL saymaz), varsa XPASS uyarısı
# CAST kilit seçimi (2026-07-17): iki bağımsız koşuda da (env'li+env'siz) mevcut VE ham kunye.txt'te
# birebir bulunan MİNİMAL alt-küme — LLM koşudan-koşuya cast-varyansı gözlendi (kenar isimler
# gidip geliyor), kilitler yalnız kararlı çekirdek adlarda ki golden flaky olmasın.
VAKALAR = [
    dict(patt="*1990-0285*", title="TOPLU GÖSTERİLER", yon="Minnelli",
         cast=["Kerr", "Andrews"],
         aciklama="çok-varyant fuzzy: garble→KB-kanonik"),
    dict(patt="CENNETE GELD*", title="CENNETE GELDİK Mİ", yon="Caldana",
         cast=["Thorneycroft"],
         aciklama="fabrikasyon-freni: temiz KB-yok isim korunur"),
    dict(patt="BAŞKAN VE MARI*", title="BAŞKAN VE MARI", yon="Rochefoucauld",
         aciklama="FR MISE EN SCENE + soy-bağlaç token-cap (hub verisi W:-restorasyon bekliyor)"),
    dict(patt="TILSIMLI*", title="TILSIMLI DÜNYA", yon="",
         cast=["Reba West", "Tony Oliver"],
         aciklama="dublaj-freni: yön boş kalmalı (cast=dublaj kadrosu, ekranda yazılı)"),
    dict(patt="HALIFAX*", title="HALIFAX", yon="Cameron",
         cast=["Gibney", "Horler"],
         aciklama="devised-by fren + normal dolu"),
    dict(patt="BUZDAN GELEN*", title="BUZDAN GELEN SESLER", yon="Johnson",
         aciklama="rescue: DIRECTED & PHOTOGRAPHED kombine (cast ekranda yok → kilit yok)"),
    dict(patt="*1976-0184*", title="ANGOLA'DAN KAÇIŞ", yon="Martinson",
         cast=["Stan Brock", "Joe Mafela"],
         aciklama="orta/baş-harf toleransı: ekran 'Leslie Martinson' → KB 'Leslie H. Martinson' köprü"),
    # v2 cast-vakası: komşu-dışla/crew-leak kapısı (commit 5232386) uçtan-uca + bilinen-açık
    dict(patt="SANTRAL 2000*", title="SANTRAL", yon=None,
         cast=["Christa Miller", "Lori Heuring", "Michael Laurence"],
         cast_yok=["Doug Bruce", "Kelli Bingham", "Sean Britt"],   # crew (LINE PRODUCER/PM/1st AC)
         xfail_cast=["Jacqueline Kim"],
         aciklama="cast: komşu-dışla e2e; Jacqueline Kim kendi-satır-çakışması BİLİNEN-AÇIK"),
]


def kunye_oku(patt, title):
    """(json|None, neden). None dönerse neden ∈ {hub-yok, kunye-yok, json-yok}."""
    g = glob.glob(os.path.join(DB, patt))
    if not g:
        return None, "hub-yok"
    # "-fb" SUFFIX kontrolü (2026-07-07 fix): substring yerine suffix — rastgele job-hash "fb…"
    # klasörünü yanlışlıkla dışlayıp sahte-FAIL üretmesin (bkz _pipe_credit_text.py aynı desen).
    ks = sorted([q for q in glob.glob(os.path.join(g[0], "ocr", "ocr-*", "kunye.txt"))
                 if not os.path.basename(os.path.dirname(q)).endswith("-fb")],
                key=os.path.getmtime)
    if not ks:
        return None, "kunye-yok"
    r = subprocess.run([PY, os.path.join(PROJE, "scripts", "_pipe_credit_text.py"), "--ocr", ks[-1],
                        "--title", title, "--profile", "film"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    for l in (r.stdout or "").strip().splitlines()[::-1]:
        try:
            return json.loads(l), "ok"
        except Exception:
            pass
    return None, "json-yok"


def _iceriyor(liste, aranan):
    return any(aranan.lower() in (ad or "").lower() for ad in (liste or []))


def vaka_degerlendir(v, j):
    """(ok, notlar) — yön + cast kilitlerinin tamamı."""
    notlar = []
    ok = True
    yon = j.get("yonetmen") or []
    if v.get("yon") is not None:
        if v["yon"] == "":
            y_ok = not yon
        else:
            y_ok = _iceriyor(yon, v["yon"])
        ok &= y_ok
        notlar.append(f"yön={'✓' if y_ok else 'YANLIŞ:' + (', '.join(yon) or '(boş)')}")
    cast = j.get("cast") or []
    for ad in v.get("cast", []):
        c_ok = _iceriyor(cast, ad)
        ok &= c_ok
        notlar.append(f"cast+{ad}={'✓' if c_ok else 'YOK'}")
    for ad in v.get("cast_yok", []):
        c_ok = not _iceriyor(cast, ad)
        ok &= c_ok
        notlar.append(f"cast-{ad}={'✓' if c_ok else 'SIZDI'}")
    for ad in v.get("xfail_cast", []):
        if _iceriyor(cast, ad):
            notlar.append(f"XPASS! {ad} artık bulunuyor → beklentiyi cast'e taşı")
        else:
            notlar.append(f"xfail {ad} (bilinen-açık)")
    return ok, notlar


def main():
    _env_yukle()
    print("=== REGRESYON-GOLDEN v2 (künye-okuma: yön + cast) ===")
    gecti, kaldi, veri_yok = 0, 0, []
    for v in VAKALAR:
        j, neden = kunye_oku(v["patt"], v["title"])
        if j is None:
            if neden in ("hub-yok", "kunye-yok"):
                veri_yok.append(v["title"])
                print(f"  VERİ-YOK {v['title']:20s} ({neden}) | {v['aciklama']}")
                continue
            kaldi += 1
            print(f"  FAIL {v['title']:22s} ({neden}) | {v['aciklama']}")
            continue
        ok, notlar = vaka_degerlendir(v, j)
        gecti += ok
        kaldi += (not ok)
        print(f"  {'PASS' if ok else 'FAIL':4s} {v['title']:22s} {'; '.join(notlar)} | {v['aciklama']}")
    toplam = gecti + kaldi
    vy = f"  ({len(veri_yok)} VERİ-YOK: {', '.join(veri_yok)})" if veri_yok else ""
    print(f"\n=== SONUÇ: {gecti}/{toplam}{vy} — {'TEMİZ' if kaldi == 0 else 'REGRESYON VAR!'}")
    return 0 if kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
