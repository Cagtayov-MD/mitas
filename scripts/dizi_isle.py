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
     → seri_kayit.kilitle. --geri-doldur: kilit sonrası tohum PDF'leri seri_bolum_kunye
     akışıyla kanonikten yeniden basılır.
  4) LOCKED: seri_bolum_kunye akışı (İTHAL edilir, subprocess YOK). kontrol_nedenleri doluysa
     EXPORT MUTABAKATI: export/ONAYLI'daki bölüm PDF'i KONTROL'e taşınır (shutil.move) +
     yanına <ad>.dizi_neden.json sidecar (kökler mitas_pipeline HAZIR/KONTROL sabitlerinden).
  5) FORMAT_KOPUSU — Faz-1 kararı: master sayacı 2-ardışığa ulaştıysa TESPİT + RAPOR + DUR
     ("elle tohum yenileme gerekli"); otomatik yeni tohum penceresi AÇILMAZ (sözleşmenin
     izin verdiği basit yol — otomatik versiyon_atla akışı Faz-2'ye bırakıldı).
  6) Koşu sonu: outputs/DIZI_<anahtar>_<tarih>.json özet raporu + stdout kısa özet.

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


def _pipeline_kos(video, python_exe=None) -> int:
    """mitas_pipeline subprocess'i (bölüm başına). env = os.environ KOPYASI + MITAS_SHADOW_VL=1
    (gölge-VL çapraz-tanık: seri_diff kalıcı-değişim VL teyidi gemma_kunye.json'a muhtaç).
    --no-copy-source: bayrak pipeline argparse'ında MEVCUT (mitas_pipeline.py:1491) —
    dizi bölümü hub'a KOPYALANMAZ (bölüm-sayısı × dosya-boyutu disk israfı önlenir)."""
    cmd = [str(python_exe or sys.executable), os.path.join(_SCRIPTS, "mitas_pipeline.py"),
           "--video", str(video), "--no-copy-source"]
    env = os.environ.copy()
    env["MITAS_SHADOW_VL"] = "1"
    return subprocess.run(cmd, env=env).returncode


def _okuma_topla(hub, bolum_no, trt_id=None) -> dict:
    """dizi_credit_parse.okuma_topla dikişi — fonksiyon-içi import: ağır credit_parse
    zinciri yalnız gerçek koşuda yüklenir; testler bu dikişi monkeypatch'ler."""
    import dizi_credit_parse
    return dizi_credit_parse.okuma_topla(str(hub), bolum_no, trt_id)


def _bolum_kunye_akisi(hub, anahtar, bolum_no, sadece_analiz=False) -> dict:
    """seri_bolum_kunye CLI akışı İTHAL edilerek koşulur (subprocess ŞART DEĞİL — sözleşme):
    stdout'a bastığı TEK-SATIR JSON yakalanıp dict olarak döner. Parse edilemeyen çıktı
    KONTROL nedeni üretir — sessiz-belirsizlik bırakılmaz ("okunamadı > yanlış oku")."""
    import seri_bolum_kunye
    argv = ["--clip", str(hub), "--seri-anahtar", anahtar, "--bolum-no", str(bolum_no)]
    if sadece_analiz:
        argv.append("--sadece-analiz")
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


def export_mutabakat(trt_id, bolum_no, nedenler, simdi):
    """EXPORT MUTABAKATI: bölümün PDF'i export/ONAYLI altındaysa KONTROL'e taşı (shutil.move)
    + yanına <ad>.dizi_neden.json sidecar'ı yaz. Eşleşme dosya-adı TRT-id ön-ekiyle
    (pipeline çıktı adı '<TRT-ID> <BAŞLIK>…' — mitas_pipeline.py:3300). Hedefte aynı ad
    varsa SİLİNMEZ: ' (n)' sonekiyle yan yana yazılır. Dönen liste rapora eklenir."""
    tasinan = []
    if not trt_id:
        return tasinan
    onayli, kontrol = _export_kokleri()
    onayli, kontrol = Path(onayli), Path(kontrol)
    if not onayli.is_dir():
        return tasinan
    for p in sorted(onayli.glob(f"{trt_id}*.pdf")):
        kontrol.mkdir(parents=True, exist_ok=True)
        hedef = kontrol / p.name
        n = 2
        while hedef.exists():                       # mevcut KONTROL dosyası EZİLMEZ/SİLİNMEZ
            hedef = kontrol / f"{p.stem} ({n}){p.suffix}"
            n += 1
        shutil.move(str(p), str(hedef))
        sidecar = hedef.with_suffix(".dizi_neden.json")
        sidecar.write_text(json.dumps(
            {"trt_id": trt_id, "bolum_no": bolum_no, "kontrol_nedenleri": list(nedenler),
             "ts": simdi, "kaynak": "dizi_isle export-mutabakati"},
            ensure_ascii=False, indent=2), encoding="utf-8")
        tasinan.append({"bolum_no": bolum_no, "pdf": str(hedef), "sidecar": str(sidecar)})
    return tasinan


def _kilitle(anahtar, master, okumalar, simdi):
    """Tohum kilidi: seri_konsensus.kur_master gövdesi + mevcut IO defterlerinin devri
    (tanik_kayitlari idempotency için KAYBEDİLEMEZ; kur_master sözleşme gereği boş bırakır)
    + seri_kayit.kilitle + kaydet (olay günlüğe). Döner: kilitli master."""
    govde = seri_konsensus.kur_master(
        okumalar, seri_adi=master.get("seri_adi") or "", seri_anahtar=anahtar,
        kaynak_klasor=master.get("kaynak_klasor") or "", kb=None, simdi=simdi)
    govde["tanik_kayitlari"] = copy.deepcopy(master.get("tanik_kayitlari") or {})
    for on_ek in (master.get("trt_on_ekler") or []):
        if on_ek not in govde["trt_on_ekler"]:
            govde["trt_on_ekler"].append(on_ek)
    bolumler = [o.get("bolum_no") for o in okumalar]
    kilitli = seri_kayit.kilitle(govde, bolumler, simdi)
    seri_kayit.kaydet(anahtar, kilitli,
                      olay={"ts": simdi, "olay": "kilit", "modul": "dizi_isle",
                            "bolumler": bolumler})
    return kilitli


# ──────────────────────────────── orkestrasyon ───────────────────────────────

def isle(klasor, *, sadece_analiz=False, geri_doldur=False, limit=None,
         python_exe=None, pipeline_kos=None, rapor_dizin=None, simdi=None) -> dict:
    """Dizi klasörünü uçtan uca işler → koşu raporu dict (diske de yazılır).

    pipeline_kos: enjekte edilebilir çağrı (video, python_exe) -> rc (test mock'u);
    None → _pipeline_kos (gerçek subprocess). rapor_dizin: None → E:\\MITAS\\outputs.
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
        "islenen": [], "atlanan": atlanan, "kimliksiz_bolum": kimliksiz,
        "conflict": [], "hatali": [], "uyarilar": [],
        "tohum": {"bolumler": list(master.get("kilit_bolumler") or []), "kilitlendi": False},
        "kontrol_nedenleri": {}, "export_mutabakat": [], "geri_doldur": [],
        "format_kopusu": None, "master_surum": 0, "durum": "",
    }

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
            sonuc = _bolum_kunye_akisi(str(hb), anahtar, tb, sadece_analiz=False) or {}
            nedenler = list(sonuc.get("kontrol_nedenleri") or [])
            if nedenler:
                rapor["kontrol_nedenleri"][str(tb)] = nedenler
                # tohum PDF'i daha önce ONAYLI'ya düşmüş olabilir → aynı mutabakat uygulanır
                rapor["export_mutabakat"].extend(
                    export_mutabakat(trt_map.get(tb), tb, nedenler, simdi))
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
                        rapor["tohum"] = {"bolumler": list(master.get("kilit_bolumler") or []),
                                          "kilitlendi": True}
                        if geri_doldur:
                            _geri_doldur_kos(master.get("kilit_bolumler") or [])
            else:
                # ── LOCKED aşaması: bölüm künyesi + export mutabakatı + kopuş nöbeti
                kayit["asama"] = "locked"
                sonuc = _bolum_kunye_akisi(str(hub), anahtar, bno,
                                           sadece_analiz=sadece_analiz) or {}
                kayit["status"] = sonuc.get("status")
                nedenler = list(sonuc.get("kontrol_nedenleri") or [])
                if nedenler:
                    rapor["kontrol_nedenleri"][str(bno)] = nedenler
                    if not sadece_analiz:
                        rapor["export_mutabakat"].extend(
                            export_mutabakat(trt_id, bno, nedenler, simdi))
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
            rapor["tohum"] = {"bolumler": list(master.get("kilit_bolumler") or []),
                              "kilitlendi": True}
            rapor["uyarilar"].append(
                "KILIT: klasör bitti — eldeki %d kaliteli tohumla kuruldu (N<3 ise her bölüm "
                "'master <3 bölümle kuruldu' KONTROL notu taşır)" % min(len(kaliteli), TOHUM_ESIK))
            if geri_doldur:
                _geri_doldur_kos(master.get("kilit_bolumler") or [])

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
    a = ap.parse_args(argv)
    if not os.path.isdir(a.klasor):
        print(f"HATA: klasör yok: {a.klasor}")
        return 2
    rapor = isle(a.klasor, sadece_analiz=a.sadece_analiz, geri_doldur=a.geri_doldur,
                 limit=a.limit, python_exe=a.python_exe)
    return 1 if rapor.get("hatali") else 0


if __name__ == "__main__":
    raise SystemExit(main())
