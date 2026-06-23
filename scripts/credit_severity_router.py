# -*- coding: utf-8 -*-
"""credit_severity_router.py — KÜNYE QC SINIFLANDIRMA + ROUTER (şiddet × tip)

SORUN (mevcut QC2): mitas_pipeline.py tek karar verir →
    karar = "Hazır" if not reasons else "Kontrol"
Yani HER kusur (afiş-eksik gibi HAFİF de, yanlış-yönetmen gibi AĞIR da) tek KONTROL kovasına
gider. Hafif kusurlar deterministik düzeltilebilirken insan kontrolüne sokuluyor; ağır kusurlar
da tipine göre ayrılmıyor (yönetmen sorunu = temel sorun, ayrı klasör olmalı).

ÇÖZÜM: Kusurları İKİ EKSENDE sınıflandır:
  • ŞİDDET: HAFİF (auto-fix → kontrole gitmez) | AĞIR (insan kontrolü)
  • TİP:    YÖNETMEN | KİMLİK | CAST | ÖZET | RENDER | SES   → her ağır tip AYRI klasör

KARAR:
  1) Film yalnız HAFİF kusurluysa → AUTO-FIX (corrections+render pipeline'ına; kontrole GİTMEZ).
  2) En az bir AĞIR kusur varsa → KONTROL_<en-temel-tip> (öncelik: YÖNETMEN>KİMLİK>CAST>ÖZET>RENDER).
     (Ağır filmin hafif kusurları da auto-fix listesine yazılır ama kontrol şart kalır.)
  3) Hiç kusur yoksa → TEMİZ (ONAYLI/HAZIR).

Bu modül SAF (izole). mitas_pipeline'a bağlanması: §INTEGRATION (en altta).
"""
import os, sys, json, glob, shutil, argparse, re

# ───────────────────────── TAKSONOMİ ─────────────────────────
HAFIF, AGIR = "HAFIF", "AGIR"

# Ağır tip → öncelik (küçük = daha temel/öncelikli) + açıklama. KLASÖR HEDEFLERİ TEK: "KONTROL".
# POLİTİKA (Çağatay 2026-06-21): export'ta SADECE iki uç var → ONAYLI (teslime hazır) | KONTROL (sorunlu).
# Hiçbir alt-klasör yok (eski "SADECE … KONTROL EDİLECEK" / "SORUNLU" / "SES TEYİT" kaldırıldı).
# Sorun tipi dosya adına etiket olarak yazılır (örn. "_YONETMEN", "_CAST_OZET") — reviewer ada bakar.
AGIR_TIP = {
    "YONETMEN": {"folder": "KONTROL", "oncelik": 1, "aciklama": "yönetmen — kimlik çapası, en temel"},
    "KIMLIK":   {"folder": "KONTROL", "oncelik": 2, "aciklama": "film kimliği kurulamadı / yanlış-film şüphesi"},
    "CAST":     {"folder": "KONTROL", "oncelik": 3, "aciklama": "oyuncu garble / yok, kurtarılamadı"},
    "OZET":     {"folder": "KONTROL", "oncelik": 4, "aciklama": "gerçek özet üretilemedi"},
    "RENDER":   {"folder": "KONTROL", "oncelik": 5, "aciklama": "Latin-dışı alfabe / bozuk karakter sızdı"},
    "SES":      {"folder": "KONTROL", "oncelik": 6, "aciklama": "ana_dil≠TR / belirsiz"},
}
ONCELIK_SIRASI = sorted(AGIR_TIP, key=lambda t: AGIR_TIP[t]["oncelik"])

# Hafif kusur → auto-fix aksiyonu (hepsi corrections+render ile çözülür; insan gerekmez)
HAFIF_FIX = {
    "CASING":    "render-yenile: tr_upper/ozet_v4 deterministik (büyük-harf, yabancı-ASCII, kısmi-ASCII)",
    "KEYWORD":   "render-yenile: keywords=cast otomatik senkron",
    "GENRE":     "genre canon: ASCII 'SUC'→'SUÇ' / 'AKSIYON'→'AKSİYON'",
    "AFIS":      "poster_fetch: imdb/tmdb id ile doğru afiş çek",
    "OZET_STIL": "web-özet yeniden: tarih-girişi/meta-açılış kaldır (konu-başlı)",
    "YAP_FILL":  "web/KB yapımcı-doldur (destek; OCR ezmez)",
}


# Klasör politikası (Çağatay 2026-06-21): export'ta SADECE iki uç → "ONAYLI" ve "KONTROL".
# Alt-klasör YOK. Sorun tipi/sayısı dosya adındaki etiketle ifade edilir.
ALL_KONTROL_FOLDERS = ["KONTROL"]


def tip_label(types) -> str:
    """Tip kümesini öncelik sırasıyla (YÖNETMEN önce) dosya-adı etiketine çevir: 'YONETMEN_KIMLIK'."""
    return "_".join(t for t in ONCELIK_SIRASI if t in set(types))


def folder_for_set(types) -> tuple:
    """TEK HEDEF: 'KONTROL'. Tip kümesi dosya-adı etiketi olarak döner (örn. '_YONETMEN_OZET').
    Yalnız SES da KONTROL'e gider; etiket 'SES' olur."""
    t = set(types) - {"SES"}
    if not t and "SES" in types:
        return "KONTROL", "SES"
    return "KONTROL", tip_label(t)


def strip_label(name: str) -> str:
    """Dosya adındaki mevcut ' _TIP_TIP' etiketini kaldır (idempotent re-sort/render)."""
    return re.sub(r"\s+_[A-Z_]+(?=\.[A-Za-z0-9]+$)", "", name)


def with_label(filename: str, label: str) -> str:
    """Dosya adına ' _LABEL' ekle (uzantıdan önce); önce eski etiketi temizler."""
    name = strip_label(filename)
    if not label:
        return name
    root, ext = os.path.splitext(name)
    return root.rstrip() + " _" + label.replace("+", "_") + ext


# ───────────────────────── ÇEKİRDEK SINIFLANDIRICI ─────────────────────────
def classify(sig: dict) -> dict:
    """sig = normalize edilmiş sinyaller (bool/int). from_durum() veya from_signals() üretir.
    Döndürür: {tier, kontrol_tip, folder, agir:[(tip,neden)], hafif:[fix-kodu], aciklama}."""
    agir, hafif = [], []

    # ===== AĞIR (insan kontrolü) =====
    # YÖNETMEN (en temel — kimlik çapası)
    if sig.get("yon_conflict"):                       # OCR-yönetmen ≠ atanan = yanlış-film sinyali (KANUN 3)
        agir.append(("YONETMEN", "OCR-yönetmen ile atanan çelişiyor (sessiz override → yanlış-film şüphesi)"))
    elif sig.get("yon_garble"):
        agir.append(("YONETMEN", "yönetmen garble (okunamadı)"))
    elif sig.get("yon_missing") and not sig.get("yon_fillable"):
        agir.append(("YONETMEN", "yönetmen yok ve KB/web ile doldurulamadı"))
    # KİMLİK
    if sig.get("identity_unlocked") or sig.get("wrongfilm_suspect"):
        agir.append(("KIMLIK", "kimlik kurulamadı (cast-örtüşmesi 0) / yanlış-film şüphesi"))
    # CAST
    if (sig.get("cast_count", 0) or 0) < 1:
        agir.append(("CAST", "oyuncu yok"))
    elif sig.get("cast_all_garble"):
        agir.append(("CAST", "cast tamamen garble, kurtarılamadı"))
    # ÖZET
    if sig.get("ozet_missing"):
        agir.append(("OZET", "gerçek özet yok/placeholder, üretilemedi"))
    # RENDER
    if sig.get("non_latin"):
        agir.append(("RENDER", "Latin-dışı alfabe (Kiril/Yunan/Arap/CJK) sızdı"))
    if sig.get("char_broken") and not sig.get("char_broken_autofixable", True):
        agir.append(("RENDER", "bozuk Türkçe karakter (auto-fix sonrası da kalıyor)"))
    # SES (kademe — mevcut)
    if sig.get("ana_dil_not_tr"):
        agir.append(("SES", "ana_dil≠TR / belirsiz"))

    # ===== HAFİF (auto-fix → kontrole gitmez) =====
    if sig.get("casing_bad") or sig.get("foreign_accent") or sig.get("partial_ascii"):
        hafif.append("CASING")
    if sig.get("keyword_desync"):
        hafif.append("KEYWORD")
    if sig.get("genre_format"):
        hafif.append("GENRE")
    if sig.get("afis_missing"):
        hafif.append("AFIS")
    if sig.get("ozet_dateintro") or sig.get("ozet_meta"):
        hafif.append("OZET_STIL")
    if sig.get("yap_missing") and sig.get("yap_fillable"):
        hafif.append("YAP_FILL")
    if sig.get("char_broken") and sig.get("char_broken_autofixable", True):
        hafif.append("CASING")

    # ===== KARAR (set-temelli — sınırlı kombine) =====
    if agir:
        types = {t for t, _ in agir}
        folder, etiket = folder_for_set(types)
        return {"tier": "KONTROL", "kontrol_tip": etiket, "folder": folder,
                "agir": agir, "hafif": sorted(set(hafif)),
                "aciklama": f"AĞIR {sorted(types)} → {folder}"}
    if hafif:
        # Çağatay 2026-06-21: iki-uç kural (ONAYLI|KONTROL). Auto-fix henüz pipeline-içi değil →
        # yalnız-HAFİF film bugün otomatik düzelmiyor; teslime hazır SAYILAMAZ → KONTROL'e gider.
        # Etiket dosya adına yazılır (HAFİF_<kod>...), reviewer 1-bakışta görür.
        lbl = "HAFIF_" + "_".join(sorted(set(hafif)))
        return {"tier": "AUTOFIX", "kontrol_tip": lbl, "folder": "KONTROL",
                "agir": [], "hafif": sorted(set(hafif)),
                "aciklama": "yalnız HAFİF kusur → KONTROL (auto-fix pipeline-içi değil)"}
    return {"tier": "TEMIZ", "kontrol_tip": None, "folder": "ONAYLI", "agir": [], "hafif": [],
            "aciklama": "kusursuz"}


# ───────────────────────── ADAPTÖR: _DURUM.json → sinyaller ─────────────────────────
def from_durum(durum: dict) -> dict:
    """Bir filmin _DURUM.json'undan (qwen_qc + neden + cross) normalize sinyaller üret.
    NOT: yon_conflict/wrongfilm_suspect/cast_all_garble sinyalleri _DURUM'da HENÜZ yok —
    yönetmen-çapası + yanlış-film denetimi pipeline'a EKLENİNCE dolar (§INTEGRATION).
    Şimdilik mevcut alanlardan türetilir; eksik sinyaller False."""
    q = durum.get("qwen_qc") or {}
    nedenler = " | ".join(durum.get("neden") or [])
    uyari = " | ".join(durum.get("qwen_uyari") or [])
    sig = {
        # cast / özet / yön / ses — mevcut qwen_qc + neden
        "cast_count": q.get("oyuncu_sayisi", 1),
        "ozet_missing": (not q.get("ozet_var", True)) or ("özet yok" in nedenler) or ("özet yok/kısa" in nedenler),
        "yon_missing": (not q.get("yonetmen_var", True)) or ("yönetmen doğrulama: okunamadı" in nedenler),
        "yon_garble": ("yönetmen okunamadı" in nedenler) or ("yön garble" in nedenler) or ("yönetmen doğrulama: okunamadı" in nedenler),
        "yon_fillable": False,   # KB/web fill bilgisi pipeline'dan gelmeli (şimdilik temkinli)
        "ana_dil_not_tr": (str(durum.get("ana_dil") or durum.get("resolution_lang") or "").upper() not in ("TR", "")),
        # kimlik
        "wrongfilm_suspect": ("kimlik çelişki" in nedenler) or ("yanlış-film" in nedenler) or ("cast kesişimi 0" in nedenler) or ("yönetmen doğrulama: kaynak-çelişkisi" in nedenler),
        # render
        "non_latin": bool(q.get("latin_disi_alfabe_var")) or ("Latin-dışı" in nedenler),
        "char_broken": bool(q.get("turkce_karakter_bozuk_var")) or ("karakter bozuk" in nedenler),
        "char_broken_autofixable": True,   # önce auto-fix dener; persist ederse pipeline RENDER'a yükseltir
        # hafif (uyarı/format)
        "casing_bad": (not q.get("hepsi_buyuk_harf", True)) or ("büyük-harf değil" in uyari),
        "foreign_accent": bool(q.get("yabanci_ad_ascii_degil")) or ("yabancı ad" in uyari),
        "afis_missing": (not q.get("afis_var", True)) or ("afiş yok" in (nedenler + uyari)),
        "yap_missing": (not q.get("yapimci_var", True)),
        "yap_fillable": True,    # yapımcı genelde KB/web ile doldurulabilir
        # bunlar _DURUM'da yok → pipeline EKLEYİNCE dolacak (§INTEGRATION):
        "yon_conflict": bool(durum.get("yon_conflict")),
        "identity_unlocked": bool(durum.get("identity_unlocked")),
        "cast_all_garble": bool(durum.get("cast_all_garble")),
        "keyword_desync": bool(durum.get("keyword_desync")),
        "genre_format": bool(durum.get("genre_format")),
        "ozet_dateintro": bool(durum.get("ozet_dateintro")),
        "ozet_meta": bool(durum.get("ozet_meta")),
        "partial_ascii": bool(durum.get("ozet_partial_ascii")),
    }
    return sig


def from_signals(**kw) -> dict:
    """Pipeline-canlı adaptörü: bilinen sinyalleri kwargs olarak al, classify()'a hazır sig döndür.
    (Pipeline qwen_qc/reasons/cross çıktısını bu anahtarlara map'ler — §INTEGRATION.)"""
    if "qwen_qc" in kw or "reasons" in kw:
        base = from_durum({"qwen_qc": kw.get("qwen_qc") or {}, "neden": kw.get("reasons") or [],
                           "qwen_uyari": kw.get("qwen_uyari") or [], "ana_dil": kw.get("ana_dil", "TR")})
    else:
        base = {}
    for k, v in kw.items():
        if k not in ("qwen_qc", "reasons", "qwen_uyari"):
            base[k] = v
    return base


# ───────────────────────── RE-SORT ARACI (mevcut klasörü tip-bazlı ayır) ─────────────────────────
def resort(folder_name="KONTROL", apply=False, export=r"E:\MITAS\Mitas Output\export",
           database=r"E:\MITAS\Database"):
    """Var olan bir export klasöründeki filmleri _DURUM.json'a göre yeniden sınıflandır,
    AĞIR tipine göre alt-klasörlere TAŞI (dry-run varsayılan). Hafif-only olanları işaretler
    (auto-fix kuyruğuna)."""
    import re
    src = os.path.join(export, folder_name)
    pdfs = sorted(glob.glob(os.path.join(src, "*.pdf")))
    plan = {"AUTOFIX": [], "TEMIZ": []}
    for f in pdfs:
        base = os.path.basename(f)
        m = re.match(r"(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)", base)
        trt = m.group(1) if m else None
        durum = {}
        if trt:
            for d in glob.glob(os.path.join(database, f"*{trt}*", "_DURUM.json")):
                try: durum = json.load(open(d, encoding="utf-8")); break
                except Exception: pass
        r = classify(from_durum(durum))
        if r["tier"] == "KONTROL":
            plan.setdefault(r["folder"], []).append((base, r))
        else:
            plan[r["tier"]].append((base, r))
        if apply and r["tier"] == "KONTROL" and r["folder"] != folder_name:
            dst = os.path.join(export, r["folder"]); os.makedirs(dst, exist_ok=True)
            shutil.move(f, os.path.join(dst, with_label(base, r["kontrol_tip"])))
    print(f"=== RE-SORT: {folder_name} ({len(pdfs)} film) {'[UYGULANDI]' if apply else '[DRY-RUN]'} ===")
    for k in ALL_KONTROL_FOLDERS + ["TEMIZ"]:
        rows = plan.get(k, [])
        if rows:
            print(f"\n{k} ({len(rows)}):")
            for base, r in rows[:50]:
                hf = ("+autofix:" + ",".join(r["hafif"])) if r["hafif"] else ""
                ag = ("; ".join(a[1] for a in r["agir"]))[:70]
                print(f"  {base[:55]:55s} {ag} {hf}")
    return plan


# ───────────────────────── DEMO ─────────────────────────
def _demo():
    ornek = {
        "TEMİZ film": {"qwen_qc": {"ozet_var": True, "oyuncu_sayisi": 8, "yapimci_var": True,
                       "yonetmen_var": True, "ses_dil_var": True, "afis_var": True,
                       "hepsi_buyuk_harf": True}, "ana_dil": "TR"},
        "Afiş-yok (HAFİF→auto-fix)": {"qwen_qc": {"ozet_var": True, "oyuncu_sayisi": 8, "yapimci_var": True,
                       "yonetmen_var": True, "ses_dil_var": True, "afis_var": False,
                       "hepsi_buyuk_harf": True}, "ana_dil": "TR"},
        "Yönetmen-yok (AĞIR→KONTROL_YONETMEN)": {"qwen_qc": {"ozet_var": True, "oyuncu_sayisi": 8,
                       "yapimci_var": True, "yonetmen_var": False, "ses_dil_var": True, "afis_var": True,
                       "hepsi_buyuk_harf": True}, "neden": ["yönetmen okunamadı"], "ana_dil": "TR"},
        "Yanlış-film (yon_conflict→KONTROL_YONETMEN)": {"qwen_qc": {"ozet_var": True, "oyuncu_sayisi": 8,
                       "yapimci_var": True, "yonetmen_var": True, "ses_dil_var": True, "afis_var": True,
                       "hepsi_buyuk_harf": True}, "yon_conflict": True, "ana_dil": "TR"},
        "Kimlik-çelişki+afiş-yok (AĞIR kazanır)": {"qwen_qc": {"ozet_var": True, "oyuncu_sayisi": 6,
                       "yapimci_var": True, "yonetmen_var": True, "ses_dil_var": True, "afis_var": False,
                       "hepsi_buyuk_harf": False}, "neden": ["kimlik çelişki (KB cross-check)"], "ana_dil": "TR"},
        "Özet-yok (AĞIR→KONTROL_OZET)": {"qwen_qc": {"ozet_var": False, "oyuncu_sayisi": 8,
                       "yapimci_var": True, "yonetmen_var": True, "ses_dil_var": True, "afis_var": True,
                       "hepsi_buyuk_harf": True}, "neden": ["özet yok/kısa"], "ana_dil": "TR"},
    }
    print("DEMO — şiddet×tip sınıflandırma\n" + "=" * 70)
    for ad, durum in ornek.items():
        r = classify(from_durum(durum))
        print(f"\n[{ad}]")
        print(f"  → {r['tier']:8s} | {r['aciklama']}")
        if r["hafif"]:
            print(f"  auto-fix: {r['hafif']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--resort", metavar="FOLDER", help="export klasörünü tip-bazlı yeniden ayır (ör. KONTROL)")
    ap.add_argument("--apply", action="store_true", help="resort'u gerçekten taşı (varsayılan dry-run)")
    a = ap.parse_args()
    if a.resort:
        resort(a.resort, apply=a.apply)
    else:
        _demo()


# ═══════════════════════════ §INTEGRATION (mitas_pipeline.py'ye bağlama) ═══════════════════════════
#
# MEVCUT (mitas_pipeline.py:1514):
#     karar = "Hazır" if not reasons else "Kontrol"
#     dest_root = HAZIR if karar == "Hazır" else KONTROL
#
# YENİ:
#     import credit_severity_router as router
#     sig = router.from_signals(                      # aşağıdaki ek sinyalleri pipeline ZATEN biliyor:
#         qwen_qc=qwen_qc, reasons=reasons,
#         yon_conflict=<director_decision verdict=='ÇELİŞKİ'>,        # ← director_decision'ı BAYRAKLA-modunda bağla
#         identity_unlocked=<cross.cast_ortusme < 2>,                # ← cross-check zaten var
#         cast_all_garble=<identity_first_cast.temiz_cast boş>,      # ← gate çıktısı
#         keyword_desync=..., genre_format=..., ozet_dateintro=..., ozet_meta=...,
#         ana_dil_not_tr=<ana_dil!='TR'>)
#     r = router.classify(sig)
#     if r["tier"] == "TEMIZ":
#         dest_root = HAZIR                            # ONAYLI/  (teslime hazır)
#     else:
#         dest_root = EXPORT / r["folder"]            # her zaman "KONTROL/" (flat — alt-klasör yok)
#     karar = r["tier"]; durum["route"] = r
#
# KRİTİK BAĞLANTILAR (QC2'nin kapalı parçalarını AÇ — ama BAYRAKLA modunda, KANUN 3):
#   1) director_decision'ı bağla ama "KB-DEĞİŞTİR" yerine verdict=='ÇELİŞKİ' → yon_conflict=True → KONTROL_YONETMEN
#      (sessiz override yok; insan görsün).
#   2) web_identity'yi cast-KİLİTLİYKEN DE koştur: OCR-yönetmeni, kilitlenen filmin yönetmeniyle
#      çelişiyorsa → wrongfilm_suspect=True → KONTROL_KIMLIK (same-title tuzağı yakalanır).
#   3) HAFİF sinyaller (afiş/casing/keyword/genre/özet-stil) artık KONTROL TETİKLEMEZ → auto-fix kuyruğu.
