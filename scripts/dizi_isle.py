#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dizi_isle.py — DİZİ MODU orkestratör CLI: dizi klasörü → bölüm-bölüm işleme.

Sözleşme: scripts/dizi_SISTEM.md (BAĞLAYICI). Akış (bölüm-no SIRASINDA, leksikografik DEĞİL):
  1) Klasördeki videolar (mp4/mxf/mov/avi/mkv/ts) mitas_pipeline.parse_filename ile çözülür.
     TRT-id'siz/parse-edilemeyen VEYA bölüm-no 1..2000 aralığı dışı → KIMLIKSIZ_BOLUM
     (işlenmez, rapora yazılır); profile != "dizi" → uyarı + atla.
  2) seri_kayit.tanik_ekle idempotency kapısı: "AYNI" → pipeline ATLANIR (hub zaten işlenmiş;
     okuma adımları yine koşar); "DUPLICATE_CONFLICT" → bölüm İŞLENMEZ + rapor; "YENI" →
     mitas_pipeline subprocess. Tanık kaydı YALNIZ pipeline başarısında kalıcılaşır —
     başarısız bölüm sonraki koşuda yeniden denenir.
  3) BUILDING: dizi_credit_parse.okuma_topla + seri_kayit.bolum_kaydet. KALİTE KAPISI
     (kaynak=="master_dilim" VE cast dolu) geçen bölüm tohuma sayılır; geçemeyenin okuması
     yine saklanır. 3 kaliteli tohum (veya klasör bitti + >=1) → seri_konsensus.kur_master
     → seri_kayit.kilitle + MADDE-1 TOHUM-VL KAPISI (yama sözleşmesi): master kanonikleri
     tohum okumalarının vl birleşimiyle name_match'lenir; teyitsizler
     master["tohum_vl_teyitsiz"] + kilit olayı + koşu raporuna (VETO DEĞİL — basım değişmez);
     VL birleşimi TAMAMEN boşsa kapı atlanır, değer None + rapora "VL kapsamı yok" notu
     (yokluk ceza değil). --geri-doldur: kilit sonrası tohum PDF'leri seri_bolum_kunye
     akışıyla kanonikten yeniden basılır.
  4) LOCKED: seri_bolum_kunye akışı (İTHAL edilir, subprocess YOK). kontrol_nedenleri doluysa
     EXPORT MUTABAKATI: export/ONAYLI'daki bölüm PDF'i KONTROL'e taşınır (shutil.move) +
     yanına <ad>.dizi_neden.json sidecar (kökler mitas_pipeline HAZIR/KONTROL sabitlerinden).
  5) FORMAT_KOPUSU — Faz-1 kararı: master sayacı 2-ardışığa ulaştıysa TESPİT + RAPOR + DUR
     ("elle tohum yenileme gerekli"); otomatik yeni tohum penceresi AÇILMAZ (sözleşmenin
     izin verdiği basit yol — otomatik versiyon_atla akışı Faz-2'ye bırakıldı).
  6) Koşu sonu: outputs/DIZI_<anahtar>_<tarih>.json özet raporu + stdout kısa özet.

PİLOT-ÖNCESİ YAMA bayrakları (dizi_SISTEM.md "PİLOT-ÖNCESİ YAMA SÖZLEŞMESİ"):
  • --tohum-yenile "B1,B2,B3" (madde 3): seri_kayit.yeniden_tohumla (SAF; durum=BUILDING,
    kilit sıfır, defterler korunur) + verilen bölümlerin LEDGER okumalarıyla kur_master+kilitle
    yeniden (madde-1 kapısı dahil) + kaydet; sonra normal akış devam. Okuması ledger'da olmayan
    bölüm → açık hata + rc!=0 (koşu bölüm işlemez, master DEĞİŞMEZ).
  • --teslim-disi (madde 4): PDF'ler hub'a normal basılır; export_mutabakat taşımaları doğrudan
    outputs/pilot_karantina/<seri_anahtar>/ altına; koşu SONUNDA export ONAYLI+KONTROL
    köklerindeki bu koşunun işlenen TRT-id'li PDF'leri de karantinaya süpürülür (shutil.move;
    ad çakışmasında ' (n)' soneki) + rapora yazılır. Export iki-uç KESİN kuralı korunur —
    karantina export DIŞIDIR.
  • --yeniden (madde 6): seri_bolum_kunye idempotensi atlamasını kapatır (bölüm
    "uygulanan_bolumler" listesinde olsa da seri_diff.uygula yeniden koşar).

KISITLAR:
  • SIFIR-DOKUNUŞ: mevcut MITAS modülleri (mitas_pipeline, tek_film_kunye, ...) DEĞİŞMEZ,
    yalnız import edilir; hub artefaktları salt-okunur (yazan tek yer seri deposu + rapor).
  • Çökme yasağı: bölüm-başına try/except; hata bölümü 'hatali' listesine, koşu sürer.
  • --sadece-analiz: HİÇBİR kalıcı yazma yok (seri deposu/PDF/export dokunulmaz;
    yalnız koşu raporu yazılır).
  • Dikişler (_pipeline_kos/_okuma_topla/_bolum_kunye_akisi/_export_kokleri/hub_yolu)
    modül-fonksiyonu olarak ayrık: testler monkeypatch'ler, isle() pipeline_kos enjeksiyonu alır.

Kullanım:
  python scripts/dizi_isle.py --klasor "D:\\GELEN\\BİZİM EVİN HALLERİ"
      [--sadece-analiz] [--geri-doldur] [--limit N] [--python <exe>]
      [--tohum-yenile "B1,B2,B3"] [--teslim-disi] [--yeniden]
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import seri_kayit       # noqa: E402 — depo IO (MITAS_SERILER_ROOT env'e saygılı)
import seri_konsensus   # noqa: E402 — kur_master (SAF motor; import yan-etkisiz)
from credit_crosscheck import name_match  # noqa: E402 — madde-1 tohum-VL kapısı (sıkı eşleşme)

# dizi_SISTEM.md adım 1: taranan video uzantıları + bölüm-no geçerlilik aralığı
VIDEO_UZANTILAR = (".mp4", ".mxf", ".mov", ".avi", ".mkv", ".ts")
BOLUM_NO_MIN, BOLUM_NO_MAX = 1, 2000
TOHUM_ESIK = 3              # 3 kaliteli tohum → kilit (klasör biterse >=1 ile eldekiler)

_MP = None


def _mp():
    """mitas_pipeline modülü (tembel yükleme) — parse_filename/hash_file/folder_name/
    DB_ROOT/HAZIR/KONTROL buradan okunur; eşdeğeri YENİDEN YAZILMAZ (SIFIR-DOKUNUŞ).
    Tembel: testler yalnız dikiş-mock'lu yollarda bu importu hiç tetiklemeyebilir."""
    global _MP
    if _MP is None:
        import mitas_pipeline
        _MP = mitas_pipeline
    return _MP


# ─────────────────────────────── bölüm keşfi ────────────────────────────────

def bolum_no_int(bolum):
    """parse_filename bölüm etiketi → int ('14. BÖLÜM' → 14); sayı yoksa None."""
    m = re.match(r"\s*(\d+)", str(bolum or ""))
    return int(m.group(1)) if m else None


def bolumleri_bul(klasor):
    """Klasördeki bölüm videoları → (bolumler, kimliksiz, atlanan).

    bolumler: [{"video": Path, "trt_id", "bolum_no", "baslik"}] — bolum_no ARTAN sıralı
    (dizin-listesi/leksikografik sıra OTORİTE DEĞİL; 9 < 10 < 100).
    kimliksiz: TRT-id'siz/parse-edilemeyen VEYA bölüm-no aralık dışı (KIMLIKSIZ_BOLUM).
    atlanan: profile != "dizi" (film vb.) — uyarıyla atlanır, kimliksiz SAYILMAZ.
    """
    klasor = Path(klasor)
    bolumler, kimliksiz, atlanan = [], [], []
    for p in sorted(klasor.iterdir()):
        if not p.is_file() or p.suffix.lower() not in VIDEO_UZANTILAR:
            continue
        trt, baslik, profil, bolum = _mp().parse_filename(p)
        if not trt:
            kimliksiz.append({"dosya": p.name, "neden": "TRT-id yok / parse edilemedi"})
            continue
        if profil != "dizi":
            atlanan.append({"dosya": p.name, "neden": f"profil {profil!r} != dizi — atlandı"})
            continue
        no = bolum_no_int(bolum)
        if no is None or not (BOLUM_NO_MIN <= no <= BOLUM_NO_MAX):
            kimliksiz.append({"dosya": p.name,
                              "neden": f"bölüm-no geçersiz: {bolum!r} (aralık {BOLUM_NO_MIN}-{BOLUM_NO_MAX})"})
            continue
        bolumler.append({"video": p, "trt_id": trt, "bolum_no": no, "baslik": baslik})
    bolumler.sort(key=lambda b: (b["bolum_no"], b["video"].name))  # ad yalnız eşitlik kırıcı
    return bolumler, kimliksiz, atlanan


def hub_yolu(video, trt_id, baslik):
    """Pipeline'ın ürettiği hub: Database/<BAŞLIK> <TRT>/ — mitas_pipeline.folder_name
    kuralının KENDİSİ (mitas_pipeline.py:155 + :1520). NOT: pipeline ad çakışmasında ' 2'
    soneki basabilir; dizi akışında aynı bölüm tanık kapısıyla ikinci kez işlenmediğinden
    sonek izlenmez (muhafazakâr: kök ad)."""
    mp = _mp()
    return Path(mp.DB_ROOT) / mp.folder_name(baslik or "", trt_id or "", Path(video).stem)


# ───────────────────────────────── dikişler ─────────────────────────────────

def tohum_kalite(okuma) -> bool:
    """KALİTE KAPISI: yalnız kaynak=="master_dilim" VE cast'i dolu okuma tohum adayıdır.
    Kare-fallback/boş okuma tohum penceresine SAYILMAZ (okuması yine saklanır)."""
    o = okuma or {}
    return o.get("kaynak") == "master_dilim" and bool(o.get("cast"))


def tohum_vl_kapisi(master, okumalar):
    """MADDE 1 — Tohum-VL kapısı (SAF; VETO DEĞİL, basım değişmez).

    master kanonikleri (alanlar[*].kanonik + durum AKTIF/ZAYIF_UYE oyuncular) tohum
    okumalarının vl birleşimiyle (yonetmen+oyuncular+diger_roller) name_match'lenir.
    Dönüş: VL birleşimi TAMAMEN boşsa None (kapı atlanır — yokluk ceza değil);
    değilse teyitsiz kanonik isimlerin listesi (hepsi teyitliyse boş liste).
    kb=None BİLİNÇLİ ve KALICI: KB burada hakem değildir (sözleşme madde 1)."""
    vl_havuz = []
    for o in okumalar or []:
        v = (o or {}).get("vl") or {}
        for alan in ("yonetmen", "oyuncular", "diger_roller"):
            vl_havuz.extend(x for x in (v.get(alan) or []) if x and str(x).strip())
    if not vl_havuz:
        return None
    kanonikler = []
    for rec in ((master or {}).get("alanlar") or {}).values():
        for ad in ((rec or {}).get("kanonik") or []):
            if ad and ad not in kanonikler:
                kanonikler.append(ad)
    for ad, rec in ((master or {}).get("oyuncular") or {}).items():
        if (rec or {}).get("durum", "AKTIF") in ("AKTIF", "ZAYIF_UYE") \
                and ad and ad not in kanonikler:
            kanonikler.append(ad)
    return [ad for ad in kanonikler
            if not any(name_match(ad, v) for v in vl_havuz)]


def _pipeline_kos(video, python_exe=None) -> int:
    """mitas_pipeline subprocess'i (bölüm başına). env = os.environ KOPYASI + MITAS_SHADOW_VL=1
    (gölge-VL çapraz-tanık: seri_diff kalıcı-değişim VL teyidi gemma_kunye.json'a muhtaç).
    --no-copy-source: bayrak pipeline argparse'ında MEVCUT (mitas_pipeline.py:1491) —
    dizi bölümü hub'a KOPYALANMAZ (bölüm-sayısı × dosya-boyutu disk israfı önlenir)."""
    cmd = [str(python_exe or sys.executable), os.path.join(_SCRIPTS, "mitas_pipeline.py"),
           "--video", str(video), "--no-copy-source"]
    env = os.environ.copy()
    env["MITAS_SHADOW_VL"] = "1"
    # DİZİ PROFİLİ = hibrit-dy AÇIK (şartname G1; monitor'ün TRT-tip kilidi de aynı yöne
    # zorlar — çift güvence). Film hattı bu bayrağı hiç görmez (monitor tip=1'de '0'a kilitler).
    env["MITAS_SLIT_DY_HYBRID"] = "1"
    return subprocess.run(cmd, env=env).returncode


def _okuma_topla(hub, bolum_no, trt_id=None) -> dict:
    """dizi_credit_parse.okuma_topla dikişi — fonksiyon-içi import: ağır credit_parse
    zinciri yalnız gerçek koşuda yüklenir; testler bu dikişi monkeypatch'ler."""
    import dizi_credit_parse
    return dizi_credit_parse.okuma_topla(str(hub), bolum_no, trt_id)


def _bolum_kunye_akisi(hub, anahtar, bolum_no, sadece_analiz=False, yeniden=False) -> dict:
    """seri_bolum_kunye CLI akışı İTHAL edilerek koşulur (subprocess ŞART DEĞİL — sözleşme):
    stdout'a bastığı TEK-SATIR JSON yakalanıp dict olarak döner. Parse edilemeyen çıktı
    KONTROL nedeni üretir — sessiz-belirsizlik bırakılmaz ("okunamadı > yanlış oku").
    yeniden=True → '--yeniden' iletilir (madde 6: idempotensi atlaması kapanır)."""
    import seri_bolum_kunye
    argv = ["--clip", str(hub), "--seri-anahtar", anahtar, "--bolum-no", str(bolum_no)]
    if sadece_analiz:
        argv.append("--sadece-analiz")
    if yeniden:
        argv.append("--yeniden")
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        rc = seri_bolum_kunye.main(argv)
    satirlar = [s for s in tampon.getvalue().splitlines() if s.strip()]
    sonuc = None
    try:
        sonuc = json.loads(satirlar[-1]) if satirlar else None
    except Exception:  # noqa: BLE001 — bozuk çıktı aşağıda KONTROL nedenine çevrilir
        sonuc = None
    if not isinstance(sonuc, dict):
        sonuc = {"status": "cikti_parse_hata",
                 "kontrol_nedenleri": [f"AKIS_CIKTI_PARSE: bölüm {bolum_no} rc={rc}"]}
    sonuc["rc"] = rc
    return sonuc


def _export_kokleri():
    """(ONAYLI, KONTROL) kökleri — mitas_pipeline sabitlerinden (HAZIR=export/ONAYLI).
    Ayrı dikiş: testler tmp'ye yönlendirir, gerçek export'a dokunulmaz."""
    mp = _mp()
    return Path(mp.HAZIR), Path(mp.KONTROL)


def _karantina_koku(anahtar):
    """MADDE 4 — --teslim-disi karantina kökü: outputs/pilot_karantina/<seri_anahtar>/.
    Ayrı dikiş: testler tmp'ye yönlendirir (export iki-uç kuralı: karantina export DIŞI)."""
    return Path(_ROOT) / "outputs" / "pilot_karantina" / anahtar


def _pdf_tasi(p, hedef_dizin):
    """PDF'i hedef dizine shutil.move ile taşır; hedefte aynı ad varsa SİLİNMEZ/EZİLMEZ,
    ' (n)' sonekiyle yan yana yazılır. Dönen değer: hedef Path."""
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    hedef = hedef_dizin / p.name
    n = 2
    while hedef.exists():
        hedef = hedef_dizin / f"{p.stem} ({n}){p.suffix}"
        n += 1
    shutil.move(str(p), str(hedef))
    return hedef


def export_mutabakat(trt_id, bolum_no, nedenler, simdi, hedef_kok=None):
    """EXPORT MUTABAKATI: bölümün PDF'i export/ONAYLI altındaysa KONTROL'e taşı (shutil.move)
    + yanına <ad>.dizi_neden.json sidecar'ı yaz. Eşleşme dosya-adı TRT-id ön-ekiyle
    (pipeline çıktı adı '<TRT-ID> <BAŞLIK>…' — mitas_pipeline.py:3300). Hedefte aynı ad
    varsa SİLİNMEZ: ' (n)' sonekiyle yan yana yazılır. Dönen liste rapora eklenir.
    hedef_kok verilirse (--teslim-disi, madde 4) taşıma KONTROL yerine DOĞRUDAN o köke
    (pilot karantinası) yapılır; sidecar yine taşınan PDF'in yanına yazılır."""
    tasinan = []
    if not trt_id:
        return tasinan
    onayli, kontrol = _export_kokleri()
    onayli = Path(onayli)
    hedef_dizin = Path(hedef_kok) if hedef_kok is not None else Path(kontrol)
    if not onayli.is_dir():
        return tasinan
    for p in sorted(onayli.glob(f"{trt_id}*.pdf")):
        hedef = _pdf_tasi(p, hedef_dizin)
        sidecar = hedef.with_suffix(".dizi_neden.json")
        sidecar.write_text(json.dumps(
            {"trt_id": trt_id, "bolum_no": bolum_no, "kontrol_nedenleri": list(nedenler),
             "ts": simdi, "kaynak": "dizi_isle export-mutabakati"},
            ensure_ascii=False, indent=2), encoding="utf-8")
        tasinan.append({"bolum_no": bolum_no, "pdf": str(hedef), "sidecar": str(sidecar)})
    return tasinan


def teslim_disi_karantina(trt_idler, karantina):
    """MADDE 4 — --teslim-disi koşu-sonu süpürmesi: export ONAYLI+KONTROL köklerinde bu
    koşunun işlenen TRT-id'leriyle BAŞLAYAN PDF'ler karantinaya taşınır (shutil.move;
    ad çakışmasında ' (n)' soneki — mevcut dosya EZİLMEZ). Dönen liste rapora yazılır."""
    tasinan = []
    karantina = Path(karantina)
    for kok in (Path(k) for k in _export_kokleri()):
        if not kok.is_dir():
            continue
        for tid in sorted({t for t in (trt_idler or []) if t}):
            for p in sorted(kok.glob(f"{tid}*.pdf")):
                kaynak = str(p)
                hedef = _pdf_tasi(p, karantina)
                tasinan.append({"trt_id": tid, "kaynak": kaynak, "pdf": str(hedef)})
    return tasinan


def _kilitle(anahtar, master, okumalar, simdi):
    """Tohum kilidi: seri_konsensus.kur_master gövdesi + mevcut IO defterlerinin devri
    (tanik_kayitlari idempotency için KAYBEDİLEMEZ; kur_master sözleşme gereği boş bırakır;
    surum_gecmisi denetim izi için devredilir — yeniden_tohum olayları kaybolmasın)
    + seri_kayit.kilitle + MADDE-1 tohum-VL kapısı + kaydet (teyitsizler kilit olayına da
    yazılır). Döner: kilitli master."""
    govde = seri_konsensus.kur_master(
        okumalar, seri_adi=master.get("seri_adi") or "", seri_anahtar=anahtar,
        kaynak_klasor=master.get("kaynak_klasor") or "", kb=None, simdi=simdi)
    govde["tanik_kayitlari"] = copy.deepcopy(master.get("tanik_kayitlari") or {})
    govde["surum_gecmisi"] = (copy.deepcopy(master.get("surum_gecmisi") or [])
                              + list(govde.get("surum_gecmisi") or []))
    for on_ek in (master.get("trt_on_ekler") or []):
        if on_ek not in govde["trt_on_ekler"]:
            govde["trt_on_ekler"].append(on_ek)
    bolumler = [o.get("bolum_no") for o in okumalar]
    kilitli = seri_kayit.kilitle(govde, bolumler, simdi)
    # MADDE 1: kanonikler tohum VL birleşimiyle çapraz-tanıklanır (None = VL kapsamı yok)
    kilitli["tohum_vl_teyitsiz"] = tohum_vl_kapisi(kilitli, okumalar)
    seri_kayit.kaydet(anahtar, kilitli,
                      olay={"ts": simdi, "olay": "kilit", "modul": "dizi_isle",
                            "bolumler": bolumler,
                            "tohum_vl_teyitsiz": kilitli["tohum_vl_teyitsiz"]})
    return kilitli


def _yeniden_tohumla(anahtar, master, bolumler, simdi):
    """seri_kayit.yeniden_tohumla dikişi (madde 3 — SAF: durum=BUILDING, kilit/format_kopusu
    sıfır, defterler korunur). Paralel yazılan modülün imzası iki biçimde dolaşıyor:
    (anahtar, master, bolumler, simdi) [dizi_SISTEM.md] ve (master, bolumler, simdi)
    [yama sözleşmesi] — parametre ADINA göre inspect ile UYARLANIR (TypeError yutma YOK;
    _uygula_ve_kaydet'teki yerleşik kalıbın aynısı)."""
    import inspect
    prm = list(inspect.signature(seri_kayit.yeniden_tohumla).parameters)
    if prm and prm[0] == "anahtar":
        return seri_kayit.yeniden_tohumla(anahtar, master, bolumler, simdi)
    return seri_kayit.yeniden_tohumla(master, bolumler, simdi)


def _kilit_raporla(rapor, master):
    """Kilit sonrası koşu-raporu güncellemesi (madde 1): tohum bölümleri + VL-teyitsizler.
    vl_teyitsiz None = VL kapsamı yok → uyarı notu (yokluk ceza değil, KONTROL üretmez)."""
    rapor["tohum"] = {"bolumler": list(master.get("kilit_bolumler") or []),
                      "kilitlendi": True,
                      "vl_teyitsiz": master.get("tohum_vl_teyitsiz")}
    if master.get("tohum_vl_teyitsiz") is None:
        rapor["uyarilar"].append(
            "TOHUM_VL: VL kapsamı yok — madde-1 kapısı atlandı (yokluk ceza değil)")


# ──────────────────────────────── orkestrasyon ───────────────────────────────

def isle(klasor, *, sadece_analiz=False, geri_doldur=False, limit=None,
         python_exe=None, pipeline_kos=None, rapor_dizin=None, simdi=None,
         tohum_yenile=None, teslim_disi=False, yeniden=False) -> dict:
    """Dizi klasörünü uçtan uca işler → koşu raporu dict (diske de yazılır).

    pipeline_kos: enjekte edilebilir çağrı (video, python_exe) -> rc (test mock'u);
    None → _pipeline_kos (gerçek subprocess). rapor_dizin: None → E:\\MITAS\\outputs.
    tohum_yenile: bölüm-no listesi (madde 3 — ledger okumalarıyla master yeniden kurulur).
    teslim_disi: madde 4 — export taşımaları pilot karantinasına. yeniden: madde 6 —
    seri_bolum_kunye idempotensi atlaması kapanır (akışa '--yeniden' iletilir).
    """
    klasor = Path(klasor)
    simdi = simdi or datetime.datetime.now().isoformat(timespec="seconds")
    kos = pipeline_kos or _pipeline_kos

    bolumler, kimliksiz, atlanan = bolumleri_bul(klasor)
    tum_islendi = True
    if limit is not None and 0 <= limit < len(bolumler):
        for b in bolumler[limit:]:
            atlanan.append({"dosya": b["video"].name, "neden": f"LIMIT: --limit {limit} kırptı"})
        bolumler = bolumler[:limit]
        tum_islendi = False   # klasör BİTMEDİ → ">=1 ile eldekiler" kilit fallback'i KAPALI

    anahtar = seri_kayit.seri_anahtar(klasor.name)
    # seri adı: klasör adından TRT parçaları temizlenir (klasör otorite — dizi_SISTEM.md)
    seri_adi = re.sub(r"\s{2,}", " ", seri_kayit.TRT_RE.sub("", klasor.name)).strip(" -_") \
        or klasor.name

    master = seri_kayit.yukle(anahtar)
    if master is None:
        master = seri_kayit.bos_master(anahtar, seri_adi, str(klasor), simdi)
        if bolumler and not sadece_analiz:
            seri_kayit.kaydet(anahtar, master)      # boş klasörde depo AÇILMAZ

    rapor = {
        "seri_anahtar": anahtar, "seri_adi": master.get("seri_adi") or seri_adi,
        "klasor": str(klasor), "ts": simdi, "sadece_analiz": sadece_analiz,
        "teslim_disi": bool(teslim_disi),
        "islenen": [], "atlanan": atlanan, "kimliksiz_bolum": kimliksiz,
        "conflict": [], "hatali": [], "uyarilar": [],
        "tohum": {"bolumler": list(master.get("kilit_bolumler") or []), "kilitlendi": False},
        "kontrol_nedenleri": {}, "export_mutabakat": [], "geri_doldur": [],
        "karantina": [], "format_kopusu": None, "master_surum": 0, "durum": "",
    }
    # --teslim-disi: export_mutabakat taşımaları KONTROL yerine doğrudan karantinaya (madde 4)
    mutabakat_kok = _karantina_koku(anahtar) if teslim_disi else None

    # ── MADDE 3: --tohum-yenile — ledger okumalarıyla master yeniden kurulur (loop ÖNCESİ)
    if tohum_yenile:
        tohum_yenile = sorted({int(b) for b in tohum_yenile})
        led = {}
        for o in seri_kayit.bolum_okumalari(anahtar):
            if o.get("bolum_no") is not None:
                led[int(o["bolum_no"])] = o
        eksik = [b for b in tohum_yenile if b not in led]
        hata = None
        if sadece_analiz:
            hata = "TOHUM_YENILE: --sadece-analiz ile birleşemez (yeniden tohum kalıcı yazar)"
        elif eksik:
            hata = (f"TOHUM_YENILE: ledger okuması yok: bölüm {eksik} — bu bölümler önce "
                    "normal akışla işlenmeli (seri deposunda bolumler/bolum_*.json bekleniyor)")
        if hata:
            # açık hata + rc!=0 (main 'hatali' üzerinden 1 döner); bölüm İŞLENMEZ, master DEĞİŞMEZ
            rapor["hatali"].append({"bolum_no": None, "dosya": "--tohum-yenile", "hata": hata})
            print(f"[dizi_isle] HATA: {hata}")
            bolumler = []
            tum_islendi = False
        else:
            m2 = _yeniden_tohumla(anahtar, master, list(tohum_yenile), simdi)
            master = _kilitle(anahtar, m2, [led[b] for b in tohum_yenile], simdi)
            _kilit_raporla(rapor, master)
            rapor["uyarilar"].append(
                f"TOHUM_YENILE: master bölümler {tohum_yenile} ile yeniden kuruldu "
                "(eski kilit sürüm-geçmişinde)")

    hub_map = {b["bolum_no"]: hub_yolu(b["video"], b["trt_id"], b["baslik"]) for b in bolumler}
    trt_map = {b["bolum_no"]: b["trt_id"] for b in bolumler}
    analiz_tohum = []
    kopus_dur = False

    def _geri_doldur_kos(tohum_bolumler):
        # kilit sonrası tohum PDF'leri kanonikten yeniden basılır (seri_bolum_kunye akışı)
        for tb in tohum_bolumler:
            hb = hub_map.get(tb)
            if hb is None:
                rapor["uyarilar"].append(f"GERI_DOLDUR: bölüm {tb} bu koşunun klasöründe yok "
                                         "— hub çözülemedi, atlandı")
                continue
            sonuc = _bolum_kunye_akisi(str(hb), anahtar, tb,
                                       sadece_analiz=False, yeniden=yeniden) or {}
            nedenler = list(sonuc.get("kontrol_nedenleri") or [])
            if nedenler:
                rapor["kontrol_nedenleri"][str(tb)] = nedenler
                # tohum PDF'i daha önce ONAYLI'ya düşmüş olabilir → aynı mutabakat uygulanır
                rapor["export_mutabakat"].extend(
                    export_mutabakat(trt_map.get(tb), tb, nedenler, simdi,
                                     hedef_kok=mutabakat_kok))
            rapor["geri_doldur"].append({"bolum_no": tb, "status": sonuc.get("status"),
                                         "pdf": sonuc.get("pdf")})

    for b in bolumler:
        video, trt_id, bno = b["video"], b["trt_id"], b["bolum_no"]
        try:
            # ── COKLU_SERI takibi: farklı ön-ek uyarı üretir ama seri BÖLÜNMEZ (klasör otorite)
            on_ek = seri_kayit.trt_seri_on_ek(trt_id)
            mevcut_ekler = list(master.get("trt_on_ekler") or [])
            if on_ek and on_ek not in mevcut_ekler:
                if mevcut_ekler:
                    rapor["uyarilar"].append(f"COKLU_SERI: yeni ön-ek {on_ek} (bölüm {bno})")
                master["trt_on_ekler"] = mevcut_ekler + [on_ek]

            # ── tanık kapısı (idempotency; hash = mitas_pipeline.hash_file sha256)
            m2, tdurum = seri_kayit.tanik_ekle(
                master, trt_id, bno, _mp().hash_file(Path(video)), simdi)
            if tdurum == "DUPLICATE_CONFLICT":
                # aynı id FARKLI içerik: mevcut kayıt EZİLMEZ, bölüm işlenmez, rapora düşer
                rapor["conflict"].append({"trt_id": trt_id, "bolum_no": bno,
                                          "dosya": video.name})
                continue

            pipeline_sonuc = "atlandi"              # AYNI: hub zaten işlenmiş → pipeline yok
            if tdurum == "YENI":
                if sadece_analiz:
                    pipeline_sonuc = "analiz-atlandi"
                else:
                    rc = kos(video, python_exe)
                    if rc not in (0, None):
                        # tanık KAYDEDİLMEZ → sonraki koşu bölümü sıfırdan dener
                        rapor["hatali"].append({"bolum_no": bno, "dosya": video.name,
                                                "hata": f"pipeline rc={rc}"})
                        continue
                    pipeline_sonuc = "kosuldu"
            master = m2
            if not sadece_analiz:
                seri_kayit.kaydet(anahtar, master)  # tanık + ön-ek kalıcı (akış öncesi senkron)

            hub = hub_map[bno]
            kayit = {"bolum_no": bno, "trt_id": trt_id, "dosya": video.name,
                     "tanik": tdurum, "pipeline": pipeline_sonuc}

            if master.get("durum") == "BUILDING":
                # ── TOHUM aşaması
                kayit["asama"] = "tohum"
                okuma = _okuma_topla(str(hub), bno, trt_id)
                kayit["okuma_kaynak"] = (okuma or {}).get("kaynak")
                kalite = tohum_kalite(okuma)
                kayit["tohum_kalite"] = kalite
                if sadece_analiz:
                    if kalite:
                        analiz_tohum.append(bno)
                else:
                    seri_kayit.bolum_kaydet(anahtar, bno, okuma)   # kaliteden BAĞIMSIZ saklanır
                    kaliteli = [o for o in seri_kayit.bolum_okumalari(anahtar)
                                if tohum_kalite(o)]
                    if len(kaliteli) >= TOHUM_ESIK:
                        master = _kilitle(anahtar, master, kaliteli[:TOHUM_ESIK], simdi)
                        _kilit_raporla(rapor, master)
                        if geri_doldur:
                            _geri_doldur_kos(master.get("kilit_bolumler") or [])
            else:
                # ── LOCKED aşaması: bölüm künyesi + export mutabakatı + kopuş nöbeti
                kayit["asama"] = "locked"
                sonuc = _bolum_kunye_akisi(str(hub), anahtar, bno,
                                           sadece_analiz=sadece_analiz,
                                           yeniden=yeniden) or {}
                kayit["status"] = sonuc.get("status")
                nedenler = list(sonuc.get("kontrol_nedenleri") or [])
                if nedenler:
                    rapor["kontrol_nedenleri"][str(bno)] = nedenler
                    if not sadece_analiz:
                        rapor["export_mutabakat"].extend(
                            export_mutabakat(trt_id, bno, nedenler, simdi,
                                             hedef_kok=mutabakat_kok))
                if not sadece_analiz:
                    # akış uygula+kaydet yaptı → master depodan tazelenir (bayat-durum tuzağı)
                    master = seri_kayit.yukle(anahtar) or master
                    fk = master.get("format_kopusu") or {}
                    if int(fk.get("ardisik") or 0) >= 2:
                        rapor["format_kopusu"] = {"ardisik": int(fk.get("ardisik") or 0),
                                                  "ilk_bolum": fk.get("ilk_bolum"),
                                                  "bolum": bno}
                        kopus_dur = True
            rapor["islenen"].append(kayit)
        except Exception as exc:  # noqa: BLE001 — çökme yasağı: bölüm 'hatali', koşu sürer
            rapor["hatali"].append({"bolum_no": bno, "dosya": video.name,
                                    "hata": f"{type(exc).__name__}: {exc}"})
        if kopus_dur:
            for x in bolumler:
                if x["bolum_no"] > bno:
                    atlanan.append({"dosya": x["video"].name,
                                    "neden": "FORMAT_KOPUSU (2 ardışık) — koşu durdu, "
                                             "elle tohum yenileme gerekli"})
            break

    # ── klasör bitti + hâlâ BUILDING + >=1 kaliteli tohum → eldekilerle kilit (sözleşme)
    if (not sadece_analiz) and (not kopus_dur) and tum_islendi \
            and master.get("durum") == "BUILDING":
        kaliteli = [o for o in seri_kayit.bolum_okumalari(anahtar) if tohum_kalite(o)]
        if kaliteli:
            master = _kilitle(anahtar, master, kaliteli[:TOHUM_ESIK], simdi)
            _kilit_raporla(rapor, master)
            rapor["uyarilar"].append(
                "KILIT: klasör bitti — eldeki %d kaliteli tohumla kuruldu (N<3 ise her bölüm "
                "'master <3 bölümle kuruldu' KONTROL notu taşır)" % min(len(kaliteli), TOHUM_ESIK))
            if geri_doldur:
                _geri_doldur_kos(master.get("kilit_bolumler") or [])

    # ── MADDE 4: --teslim-disi koşu-sonu süpürmesi — işlenen TRT-id'lerin export PDF'leri
    #    (ONAYLI + KONTROL) pilot karantinasına taşınır; --sadece-analiz HİÇBİR şey taşımaz.
    if teslim_disi and not sadece_analiz:
        trt_idler = sorted({k.get("trt_id") for k in rapor["islenen"] if k.get("trt_id")})
        rapor["karantina"] = teslim_disi_karantina(trt_idler, _karantina_koku(anahtar))

    if sadece_analiz and analiz_tohum:
        rapor["tohum"]["analiz_adaylari"] = analiz_tohum
    rapor["master_surum"] = int(master.get("master_surum") or 0)
    rapor["durum"] = master.get("durum") or ""

    # ── koşu raporu: outputs/DIZI_<anahtar>_<tarih>.json (atomik: .tmp + os.replace)
    tarih = "".join(ch for ch in simdi if ch.isdigit()) \
        or datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    rdir = Path(rapor_dizin) if rapor_dizin else (Path(_ROOT) / "outputs")
    rdir.mkdir(parents=True, exist_ok=True)
    ryol = rdir / f"DIZI_{anahtar}_{tarih}.json"
    rapor["rapor_yolu"] = str(ryol)
    tmp = ryol.with_suffix(ryol.suffix + ".tmp")
    tmp.write_text(json.dumps(rapor, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    os.replace(tmp, ryol)

    # ── stdout kısa özet
    print(f"[dizi_isle] seri={rapor['seri_adi']!r} anahtar={anahtar} "
          f"durum={rapor['durum']} surum={rapor['master_surum']}")
    print(f"[dizi_isle] islenen={len(rapor['islenen'])} atlanan={len(atlanan)} "
          f"kimliksiz={len(kimliksiz)} conflict={len(rapor['conflict'])} "
          f"hatali={len(rapor['hatali'])} kontrol-bolum={len(rapor['kontrol_nedenleri'])}")
    if rapor["format_kopusu"]:
        print("[dizi_isle] FORMAT_KOPUSU (2 ardışık) tespit edildi — koşu durduruldu; "
              "elle tohum yenileme gerekli (Faz-1 kararı).")
    if teslim_disi:
        print(f"[dizi_isle] TESLIM-DISI: {len(rapor['export_mutabakat']) + len(rapor['karantina'])} "
              f"PDF pilot karantinasında ({_karantina_koku(anahtar)})")
    print(f"[dizi_isle] rapor: {ryol}")
    return rapor


# ──────────────────────────────────── CLI ────────────────────────────────────

def main(argv=None) -> int:
    # Windows konsol codec tuzağı (mitas_pipeline ile aynı gerekçe): Türkçe/ok karakteri
    # print'i çökertmesin diye stdout/stderr utf-8'e sabitlenir.
    for _std in (sys.stdout, sys.stderr):
        try:
            _std.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — pipe değilse/eski py ise sessiz geç
            pass
    ap = argparse.ArgumentParser(
        description="DİZİ MODU orkestratörü: dizi klasörü → bölümler (dizi_SISTEM.md)")
    ap.add_argument("--klasor", required=True, help="dizi klasörü (bölüm videoları)")
    ap.add_argument("--sadece-analiz", dest="sadece_analiz", action="store_true",
                    help="kalıcı yazma YOK (depo/PDF/export dokunulmaz); yalnız koşu raporu")
    ap.add_argument("--geri-doldur", dest="geri_doldur", action="store_true",
                    help="kilit sonrası tohum bölümlerinin PDF'lerini kanonikten yeniden bas")
    ap.add_argument("--limit", type=int, default=None, help="en çok N bölüm işle")
    ap.add_argument("--python", dest="python_exe", default=None,
                    help="pipeline subprocess python yolu (default: sys.executable)")
    ap.add_argument("--tohum-yenile", dest="tohum_yenile", default=None, metavar="B1,B2,B3",
                    help="madde 3: verilen bölümlerin LEDGER okumalarıyla master'ı yeniden "
                         "tohumla+kilitle (seri_kayit.yeniden_tohumla; defterler korunur)")
    ap.add_argument("--teslim-disi", dest="teslim_disi", action="store_true",
                    help="madde 4: bu serinin export ONAYLI/KONTROL PDF'leri koşu sonunda "
                         "outputs/pilot_karantina/<seri>/ altına taşınır (export dışı pilot)")
    ap.add_argument("--yeniden", dest="yeniden", action="store_true",
                    help="madde 6: idempotensi atlamasını kapat — bölüm daha önce uygulanmış "
                         "olsa da seri_diff.uygula yeniden koşar")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.klasor):
        print(f"HATA: klasör yok: {a.klasor}")
        return 2
    tohum_yenile = None
    if a.tohum_yenile is not None:
        parcalar = [p for p in re.split(r"[,\s]+", a.tohum_yenile.strip()) if p]
        if not parcalar or not all(p.isdigit() for p in parcalar):
            print(f"HATA: --tohum-yenile bölüm listesi çözülemedi: {a.tohum_yenile!r} "
                  "(beklenen: '1,2,3')")
            return 2
        tohum_yenile = sorted({int(p) for p in parcalar})
        if a.sadece_analiz:
            print("HATA: --tohum-yenile --sadece-analiz ile birleşemez "
                  "(yeniden tohum kalıcı yazar)")
            return 2
    rapor = isle(a.klasor, sadece_analiz=a.sadece_analiz, geri_doldur=a.geri_doldur,
                 limit=a.limit, python_exe=a.python_exe, tohum_yenile=tohum_yenile,
                 teslim_disi=a.teslim_disi, yeniden=a.yeniden)
    return 1 if rapor.get("hatali") else 0


if __name__ == "__main__":
    raise SystemExit(main())
