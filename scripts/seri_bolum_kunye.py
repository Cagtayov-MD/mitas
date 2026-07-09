#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
seri_bolum_kunye.py — DİZİ modu: master + bölüm-diff + meta → _make_pdf d-sözlüğü + bölüm PDF (CLI).

Sözleşme: scripts/dizi_SISTEM.md "Bölüm PDF birleştirme" (BAĞLAYICI).
  • birlesik_kunye(master, diff, meta, *, simdi="") → (d, kaynak_haritasi)  — SAF: IO yok,
    girdiler mutate edilmez. d = _make_pdf.build sözlüğü (tek_film_kunye.py:1174 anahtar
    seti + "bolum"; profile="DİZİ", subtitle=None, poster=None, film_notu=[]).
  • main() CLI: seri_kayit.yukle → dizi_credit_parse.okuma_topla (+bolum_kaydet)
    → seri_diff.diffle → uygula → seri_kayit.kaydet → parse_teslim_md → mp.build
    (tmp "kunye_dizi.pdf"; boyut > 10KB ise os.replace hedefe) → pdf/kunye_dizi_kaynak.json
    → stdout TEK-SATIR JSON. --sadece-analiz: uygula/kaydet + PDF + kaynak-json YAPILMAZ,
    diff raporu stdout JSON'a gömülür.

PİLOT-ÖNCESİ YAMA (dizi_SISTEM.md "PİLOT-ÖNCESİ YAMA SÖZLEŞMESİ"):
  • Madde 1 (kuyruk): master["tohum_vl_teyitsiz"] BOŞ-OLMAYAN listeyse kontrol_nedenleri'ne
    TEK satır "tohum VL-teyitsiz: N isim" eklenir (veto değil — basım değişmez; None/boş =
    VL kapsamı yok/herkes teyitli → satır YOK).
  • Madde 11: len(master["kilit_bolumler"]) < 3 ise "master <3 bölümle kuruldu (n)" eklenir.
  • Madde 6 (idempotensi): bölüm master["uygulanan_bolumler"] listesindeyse seri_diff.uygula
    ÇAĞRILMAZ ve master kaydedilmez (diffle + birlesik_kunye + PDF yine koşar; stdout status
    "yeniden_render"). --yeniden bayrağı atlamayı kapatır. Uygula başarısında bölüm listeye
    kaydet'ten ÖNCE eklenir.

SIFIR-DOKUNUŞ: mitas_pipeline / tek_film_kunye / _make_pdf / credit_parse DEĞİŞMEZ — yalnız
yeniden kullanılır (tek_film_kunye zaten mp=_make_pdf ve nn=name_normalize'ı importlib ile yükler;
eşdeğer yükleme YENİDEN YAZILMAZ). scripts-içi dizi modülleri (seri_kayit, dizi_credit_parse,
seri_diff) FONKSİYON-İÇİ import edilir: paralel geliştirme sırasında modül-yükü kırılmasın +
testler bu modüllere bağımlı olmadan CLI dikişlerini monkeypatch'leyebilsin.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import tek_film_kunye as tfk   # parse_teslim_md + ozet_v4 + mp/nn (tek yükleme noktası)

mp = tfk.mp   # _make_pdf (importlib ile yüklü) — testler bu modül-attribute'unu değiştirir
nn = tfk.nn   # name_normalize (upper_names / upper_crew / tr_upper)

# dizi_SISTEM.md "TEKİL alanlar" — crew'de kanonik BASIM SIRASI da bu demettir.
TEKIL_ALANLAR = ("Yönetmen", "Yapımcı", "Senaryo", "Müzik", "Görüntü Yönetmeni", "Kurgu")

# Bölüm PDF'i yayın eşiği (rerender_pdf_only.py:378 ile aynı): küçük/yarım render hedefi EZMEZ.
_PDF_MIN_BOYUT = 10000


def _bolum_etiketi(bolum):
    """meta['bolum'] → PDF bölüm rozeti ('14. BÖLÜM'). Değer zaten 'BÖLÜM' içeriyorsa yalnız
    Türkçe-kasalanır; boş/None → None (_make_pdf, d['bolum'] None ise rozeti hiç basmaz)."""
    if bolum is None or str(bolum).strip() == "":
        return None
    s = str(bolum).strip()
    su = nn.tr_upper(s)
    return su if "BÖLÜM" in su else f"{s}. BÖLÜM"


def birlesik_kunye(master, diff, meta, *, simdi=""):
    """master (seri_master.json) + diff (seri_diff.diffle çıktısı) + meta (parse_teslim_md
    + trt_id/bolum) → (d, kaynak_haritasi). SAF: IO/ağ yok; girdiler mutate edilmez;
    simdi verilirse tamamen deterministik.

    kaynak_haritasi: alan → "master:v<surum>" | "bolum:<no>(override)" | "bolum:<no>(konuk)"
    | "meta". Sabit alanlar (profile/date/subtitle/poster/film_notu) haritaya girmez —
    dört etiketten hiçbiri onları tanımlamaz.
    """
    master, diff, meta = master or {}, diff or {}, meta or {}
    surum = int(master.get("master_surum") or 0)
    m_et = f"master:v{surum}"
    bolum_no = diff.get("bolum_no", meta.get("bolum"))
    ozel = diff.get("bolum_ozel") or {}
    override = ozel.get("alan_override") or {}
    konuklar = [k for k in (ozel.get("konuk_oyuncular") or []) if (k or {}).get("isim")]
    kh = {}

    # CAST — master oyuncular: durum AKTIF + ZAYIF_UYE, 'sira' (ilk-görünme) düzeninde, kanonik
    # yazım (dict anahtarı). AYRILDI basılMAZ (seri_diff kural 3: eşikten sonra o bölümden itibaren
    # yok). "Bölümde yok" ALARM DEĞİLDİR — eksik isim kanondan basılır, o yüzden kaynak=master.
    oyuncular = master.get("oyuncular") or {}
    aktif = [(ad, rec or {}) for ad, rec in oyuncular.items()
             if (rec or {}).get("durum", "AKTIF") in ("AKTIF", "ZAYIF_UYE")]
    aktif.sort(key=lambda kv: kv[1].get("sira", 10 ** 9))   # kararlı sıralama: eşitlikte master sırası
    cast_ham = [ad for ad, _ in aktif]
    castU = nn.upper_names(cast_ham) if cast_ham else []
    kh["cast"] = m_et
    kh["keywords"] = m_et                                   # keywords cast'ten türetilir (aynı köken)

    # CREW — TEKİL alanlar kanonik sırada; kanonik listesi BOŞ alan atlanır. alan_override varsa
    # o alan İÇİN o bölümde override basılır — master'da alan boş olsa bile (seri_diff kural 4:
    # DEGISIM_ADAYI garble-siz yolu override üretir; override = bölümün alan değeri, kalıcı değil).
    crew, yon_ham = [], []
    for alan in TEKIL_ALANLAR:
        ov = [x for x in (override.get(alan) or []) if x]
        kanonik = [x for x in (((master.get("alanlar") or {}).get(alan) or {}).get("kanonik") or []) if x]
        isimler = ov or kanonik
        if not isimler:
            continue
        crew.append((alan, list(isimler)))
        kh[alan] = f"bolum:{bolum_no}(override)" if ov else m_et
        if alan == "Yönetmen":
            yon_ham = list(isimler)                          # ozet_v4 isim-farkındalığı için
    for rol, kisiler in (master.get("teknik_ekip") or {}).items():
        isimler = [ad for ad in (kisiler or {}) if ad]
        if not isimler:
            continue
        crew.append((rol, isimler))
        kh[rol] = m_et
    if konuklar:
        # EN SON satır; kesin=true (jenerik-başlığı tanıklı) önce, grup-içi sıra korunur.
        knames = ([k["isim"] for k in konuklar if k.get("kesin")]
                  + [k["isim"] for k in konuklar if not k.get("kesin")])
        crew.append(("Konuk Oyuncular", knames))
        kh["Konuk Oyuncular"] = f"bolum:{bolum_no}(konuk)"
    crewU = nn.upper_crew(crew) if crew else [("Yönetmen", ["—"])]   # tek_film boş-crew kalıbı

    # META alanları — başlık master.seri_adi otorite (dizi kanonu); yoksa md başlığına düş.
    title_ham = master.get("seri_adi") or meta.get("title") or "—"
    kh["title"] = m_et if master.get("seri_adi") else "meta"
    tur = nn.tr_upper(meta.get("tur") or "") or "—"
    # SES kanalı: tek_film Fix 4 aynası — EFEKT/EF kanalı dil listesine girmez.
    sk = [x for x in (meta.get("ses_kanallari") or [])
          if x and str(x).strip().upper() not in ("EFEKT", "EF")]
    kh.update(specs="meta", ozet="meta", ses_kanallari="meta",
              ana_dil="meta", altyazi="meta", bolum="meta")

    tarih = simdi or datetime.datetime.now().strftime("%d.%m.%Y · %H:%M")
    d = dict(
        profile="DİZİ", date=tarih,
        title=nn.tr_upper(title_ham), subtitle=None,
        specs=[("ÇÖZÜNÜRLÜK", meta.get("res") or "—"), ("TÜR", tur),
               ("TOPLAM SÜRE", meta.get("dur") or "—"), ("TRT KİMLİK", meta.get("trt_id") or "—")],
        keywords="; ".join(castU) if castU else "—",
        cast=castU or ["—"], crew=crewU,
        ozet=tfk.ozet_v4(meta.get("ozet", ""), names=cast_ham + yon_ham),
        ses_kanallari=sk,
        ana_dil=meta.get("ana_dil") or "—", altyazi=meta.get("altyazi") or "—",
        poster=None, film_notu=[],
        bolum=_bolum_etiketi(meta.get("bolum") if meta.get("bolum") is not None else bolum_no),
    )
    return d, kh


def _kunye_kaynagi(okuma):
    """Provenans etiketi (kunye_dizi_kaynak.json): BolumOkuma.kaynak → master_dilim='master',
    kare='kare', yok/eksik='kanon-devir' (bölüm okuması yok — her şey kanondan devredildi)."""
    return {"master_dilim": "master", "kare": "kare"}.get((okuma or {}).get("kaynak"), "kanon-devir")


# ── CLI dikişleri: scripts-içi dizi modülleri FONKSİYON-İÇİ import (testler monkeypatch'ler) ──

def _master_yukle(seri_anahtar):
    """seri_kayit.yukle — kanonik seri master'ı (depo/dosya yoksa None)."""
    import seri_kayit
    return seri_kayit.yukle(seri_anahtar)


def _okuma_yap(clip, bolum_no, seri_anahtar):
    """dizi_credit_parse.okuma_topla → BolumOkuma; anlık görüntü seri_kayit.bolum_kaydet ile
    saklanır. Saklama hatası PDF akışını ÖLDÜRMEZ (stderr uyarı) — depo tali, künye asıl iştir."""
    import dizi_credit_parse
    okuma = dizi_credit_parse.okuma_topla(clip, bolum_no)
    try:
        import seri_kayit
        seri_kayit.bolum_kaydet(seri_anahtar, bolum_no, okuma)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[seri_bolum_kunye][UYARI] bolum_kaydet başarısız: {e}\n")
    return okuma


def _diffle(master, okuma):
    """seri_diff.diffle — SAF diff (LOCKED master vs BolumOkuma)."""
    import seri_diff
    return seri_diff.diffle(master, okuma)


def _uygula_ve_kaydet(seri_anahtar, master, diff, okuma, simdi, bolum_no=None):
    """seri_diff.uygula + madde-6 uygulanan-defteri + seri_kayit.kaydet (olaylar gecmis.jsonl'e).

    seri_diff paralel yazılıyor — imza inspect ile UYARLANIR (parametre adına göre; TypeError
    yutma YOK): 'okuma' parametresi varsa geçilir, 'simdi' varsa geçilir. uygula dönüşü esnek:
    (master, olaylar) | yeni master dict | None (yerinde mutasyon). Nihai imza dizi_isle
    pilotunda (görev 7) sabitlenir; testler bu dikişi bütünüyle monkeypatch'ler.

    MADDE 6: uygula başarısında bolum_no, master["uygulanan_bolumler"] listesine (yoksa boş
    başlatılır) kaydet'ten ÖNCE eklenir — ikinci koşu uygula'yı atlayıp yalnız render eder."""
    import inspect
    import seri_diff
    import seri_kayit
    prm = inspect.signature(seri_diff.uygula).parameters
    args = [master, diff]
    if "okuma" in prm:
        args.append(okuma)
    kwargs = {"simdi": simdi} if "simdi" in prm else {}
    sonuc = seri_diff.uygula(*args, **kwargs)
    olaylar = []
    if isinstance(sonuc, tuple) and len(sonuc) == 2:
        master, olaylar = sonuc
        olaylar = list(olaylar or [])
    elif isinstance(sonuc, dict):
        master = sonuc
    if bolum_no is not None:                       # madde 6: kaydet'ten ÖNCE deftere işle
        uygulanan = master.setdefault("uygulanan_bolumler", [])
        if bolum_no not in uygulanan:
            uygulanan.append(bolum_no)
    if olaylar:
        for olay in olaylar:                       # append-only günlük: olay sırası korunur
            seri_kayit.kaydet(seri_anahtar, master, olay)
    else:
        seri_kayit.kaydet(seri_anahtar, master)
    return master


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="DİZİ bölüm künyesi: LOCKED master + bölüm-diff + meta → v4 PDF")
    ap.add_argument("--clip", required=True, help="bölüm hub klasörü (Database/<klip>)")
    ap.add_argument("--seri-anahtar", dest="seri_anahtar", required=True)
    ap.add_argument("--bolum-no", dest="bolum_no", type=int, required=True)
    ap.add_argument("--out", default=None, help="hedef PDF (yoksa <clip>/pdf/kunye.pdf)")
    ap.add_argument("--sadece-analiz", dest="sadece_analiz", action="store_true",
                    help="uygula/kaydet + PDF + kaynak-json YOK; diff raporu stdout JSON'da")
    ap.add_argument("--yeniden", action="store_true",
                    help="madde 6: idempotensi atlamasını kapat — bölüm 'uygulanan_bolumler' "
                         "listesinde olsa da seri_diff.uygula yeniden koşar")
    a = ap.parse_args(argv)
    simdi = datetime.datetime.now().isoformat(timespec="seconds")

    # 1) master — LOCKED değilse künye üretilmez ("okunamadı > yanlış oku": kanon yoksa basma).
    master = _master_yukle(a.seri_anahtar)
    if not master or master.get("durum") != "LOCKED":
        durum = (master or {}).get("durum") or "YOK"
        sys.stderr.write(f"[seri_bolum_kunye][UYARI] master hazır değil (durum={durum}) "
                         f"— künye üretilmedi\n")
        print(json.dumps({"status": "master_hazir_degil",
                          "kontrol_nedenleri": [f"master hazır değil (durum={durum})"],
                          "master_surum": int((master or {}).get("master_surum") or 0),
                          "pdf": None}, ensure_ascii=False))
        return 2

    # 2) bölüm okuması (+ depoya anlık görüntü)  3) diff
    okuma = _okuma_yap(a.clip, a.bolum_no, a.seri_anahtar)
    diff = _diffle(master, okuma) or {}
    nedenler = list(diff.get("kontrol_nedenleri") or [])
    # MADDE 1 (kuyruk): tohum-VL kapısı teyitsizleri — her bölümde TEK satır (veto değil;
    # None/boş liste = VL kapsamı yok / herkes teyitli → satır YOK, yokluk ceza değil).
    vl_teyitsiz = master.get("tohum_vl_teyitsiz") or []
    if vl_teyitsiz:
        nedenler.append(f"tohum VL-teyitsiz: {len(vl_teyitsiz)} isim")
    # MADDE 11: eksik tohumla kurulan master her bölümde işaretlenir (N<3 kilit notu).
    kilit_b = master.get("kilit_bolumler") or []
    if len(kilit_b) < 3:
        nedenler.append(f"master <3 bölümle kuruldu ({len(kilit_b)})")

    if a.sadece_analiz:
        # Kalıcı hiçbir şey değişmez: uygula/kaydet YOK, adım 5-6 atlanır; diff rapora gömülür.
        print(json.dumps({"status": "analiz", "kontrol_nedenleri": nedenler,
                          "master_surum": int(master.get("master_surum") or 0),
                          "pdf": None, "diff": diff}, ensure_ascii=False, default=str))
        return 0

    # MADDE 6 — idempotensi: bölüm daha önce uygulandıysa uygula ÇAĞRILMAZ ve master
    # kaydedilmez; diff + birleşim + PDF yine koşar (status "yeniden_render").
    # --yeniden bayrağı atlamayı kapatır (dizi_isle --yeniden buraya taşır).
    yeniden_render = (not a.yeniden) and a.bolum_no in (master.get("uygulanan_bolumler") or [])
    if not yeniden_render:
        master = _uygula_ve_kaydet(a.seri_anahtar, master, diff, okuma, simdi,
                                   a.bolum_no) or master

    # 4) meta — kunye_teslim.md (yoksa parse_teslim_md güvenli boş döner) + trt_id/bolum doldur.
    meta = tfk.parse_teslim_md(os.path.join(a.clip, "pdf", "kunye_teslim.md"))
    if not meta.get("trt_id"):
        meta["trt_id"] = (okuma or {}).get("trt_id")
    meta["bolum"] = a.bolum_no

    # 5) d-sözlüğü + render: tmp "kunye_dizi.pdf" → boyut > 10KB ise os.replace hedefe
    #    (küçük/yarım render mevcut kunye.pdf'i ASLA ezmez — güvenli-replace kuralı).
    d, kaynak_haritasi = birlesik_kunye(
        master, diff, meta, simdi=datetime.datetime.now().strftime("%d.%m.%Y · %H:%M"))
    pdf_dir = os.path.join(a.clip, "pdf")
    os.makedirs(pdf_dir, exist_ok=True)
    tmp_pdf = os.path.join(pdf_dir, "kunye_dizi.pdf")
    hedef = a.out or os.path.join(pdf_dir, "kunye.pdf")
    pdf_yolu = None
    try:
        mp.build(tmp_pdf, d)
        if os.path.exists(tmp_pdf) and os.path.getsize(tmp_pdf) > _PDF_MIN_BOYUT:
            os.makedirs(os.path.dirname(os.path.abspath(hedef)), exist_ok=True)
            os.replace(tmp_pdf, hedef)
            pdf_yolu = hedef
            try:                                   # fitz varsa önizleme PNG tazele — akışı bozmaz
                import fitz
                fitz.open(pdf_yolu)[0].get_pixmap(dpi=130).save(pdf_yolu[:-4] + "_onizleme.png")
            except Exception:  # noqa: BLE001
                pass
        else:
            nedenler.append("PDF_KUCUK: kunye_dizi.pdf <= 10KB — hedefe yazılmadı")
            sys.stderr.write("[seri_bolum_kunye][UYARI] render küçük PDF üretti (<=10KB) "
                             "— replace atlandı\n")
    except Exception as e:  # noqa: BLE001 — render hatası akışı öldürmez; sinyal JSON'da taşınır
        nedenler.append(f"PDF_RENDER_HATA: {type(e).__name__}: {e}")
        sys.stderr.write(f"[seri_bolum_kunye][UYARI] render hatası: {e}\n")

    # 6) provenans — PDF görünümünde kaynak işareti YOK (sözleşme); harita yan-dosyada taşınır.
    diff_ozet = {"bolum_no": diff.get("bolum_no"),
                 "eslesen_oyuncu": len((diff.get("eslesen") or {}).get("oyuncular") or []),
                 "eksik": len(diff.get("eksik") or []),
                 "yeni": len(diff.get("yeni") or []),
                 "kalici_degisim": len(diff.get("kalici_degisim") or []),
                 "terfi": len(diff.get("terfi") or []),
                 "format_kopusu": bool(diff.get("format_kopusu")),
                 "bolum_ozel": diff.get("bolum_ozel") or {},
                 "kontrol_nedenleri": list(diff.get("kontrol_nedenleri") or [])}
    try:
        with open(os.path.join(pdf_dir, "kunye_dizi_kaynak.json"), "w", encoding="utf-8") as f:
            json.dump({"kaynak_haritasi": kaynak_haritasi, "diff_ozet": diff_ozet,
                       "master_surum": int(master.get("master_surum") or 0),
                       "kunye_kaynagi": _kunye_kaynagi(okuma)},
                      f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:  # noqa: BLE001 — provenans tali; PDF'i geriye almaz
        sys.stderr.write(f"[seri_bolum_kunye][UYARI] kaynak-json yazılamadı: {e}\n")

    # 7) stdout TEK-SATIR JSON (dizi_isle orkestratörü bunu parse eder)
    print(json.dumps({"status": "yeniden_render" if yeniden_render else "ok",
                      "kontrol_nedenleri": nedenler,
                      "master_surum": int(master.get("master_surum") or 0),
                      "pdf": pdf_yolu}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
