#!/usr/bin/env python3
"""v5 üretim izleme — Database'deki jenerik_detection.json'lardan v5 telemetri özeti.

Sürekli-iyileştirme döngüsünün gözü (2026-07-23, Çağatay: "filmleri izleyip sürece
katacağız"): her üretim koşusu manifest'e v5-vs-eski-CV kaydı düşürür; bu araç
birikeni özetler ve İNCELEME ADAYLARINI (kredi_yok kuyruğu / şüpheli havuz oranı /
gevşetme yolu / koşular-arası kayma) listeler. Salt-okur — hiçbir üretim
dosyasına yazmaz.

DALGA 2 YENİDEN-KALİBRASYONU (2026-07-29, tembel-CV + manifest dürüstlüğü):
v5 kazandığı koşularda CV artık HİÇ ÇALIŞMIYOR (bkz. scripts/_jenerik_pool.py
create_pool) — bu yüzden `cv_start_pos` v5 yolunda YOK, eski
`abs(start_pos - cv_start) >= esik` "ayrışma" testi artık HİÇBİR ŞEY ÖLÇEMEZ
(kıyaslanacak ikinci bir sayı yok). Yerine ÖLÇÜYE DAYALI (149 manifest üzerinden
gözlenen dağılım, input_frames medyanı ~720) dört bağımsız triyaj sinyali:
  1) v5.karar == "kredi_yok" (motor ne olursa olsun, engine != "v5_onset" olsa
     bile — CV devralmış olabilir ama v5'in REDDİ artık görünür) → AYRI KUYRUK,
     Dalga 3'ün ("kredi_yok" politika kararı) doğrudan etkileyeceği filmler.
  2) pool_frames < 45  → geç-çapa şüphesi (cast kaybı yönü, ~p5 altı).
  3) pool_frames / input_frames > 0.80  → erken-çapa şüphesi (footage şişmesi, ~p90).
  4) v5.son_capa < 0.82  → SON_ERISIM gevşetme yolu ateşlemiş (bkz. figo.py
     SON_ERISIM_GEVSEK) — kazanan aday filmin son %18'ine ulaşmadan kabul edilmiş.

--esik ARTIK "v5 vs eski-CV" ayrışması DEĞİL — anlamı "KOŞULAR-ARASI start_pos
KAYMASI": aynı filmin jenerik_debug/events.jsonl'inde (create_pool HER koşuda
ekler, salt-okur biriken bir günlük) ardışık iki "v5_onset" (stage) BAŞARILI
(final_indeks dolu) kaydı arasındaki |final_indeks farkı| >= esik ise flakiness
şüphesi olarak raporlanır. Üretimde v5 henüz döngüye girmediği için (bu dalga
onu başlatıyor) bugün çoğu filmde bu sinyal boş dönecek — birikince anlam
kazanacak, ÖLÇÜM DEĞİL bir izleme kancasıdır.

⚠ KALİBRASYON KÖKENİ: 45/0.80/0.82 eşikleri ESKİ CV motorunun ürettiği
manifestlerden (Dalga 2 öncesi, 149 kayıt) türetildi — v5'in KENDİ üretim
dağılımı henüz yok. İlk ~30 gerçek v5-üretim manifestinden SONRA bu üç sayı
yeniden kalibre edilmeli (bkz. docs/GUNLUK.md'ye düşülecek takip notu).

Kullanım:
  v5_izleme.py                  # özet + inceleme adayları
  v5_izleme.py --esik 40        # koşular-arası start_pos kayma eşiği (kare)
  v5_izleme.py --json ÇIKTI.json
"""
import argparse
import glob
import json
import os
import sys

DB = os.environ.get("MITAS_DB", "/opt/mitas/Database")

# Dalga 2 kalibrasyonu (bkz. modül docstring'i) — eski CV manifestlerinden türetildi.
POOL_FRAMES_MIN = 45      # altında → geç-çapa şüphesi (~p5)
POOL_INPUT_ORAN_MAX = 0.80  # üstünde → erken-çapa şüphesi (~p90)
SON_CAPA_MIN = 0.82        # altında → SON_ERISIM gevşetme yolu ateşlemiş


def _events_v5_gecmisi(film_dir: str) -> list[dict]:
    """`<film>/jenerik_debug/events.jsonl`'den BAŞARILI ("final_indeks" dolu)
    v5_onset kayıtlarını ts sırasıyla döndürür. Dosya yoksa/bozuksa [] — salt-okur,
    hiçbir zaman yazmaz/oluşturmaz."""
    p = os.path.join(film_dir, "jenerik_debug", "events.jsonl")
    kayitlar = []
    try:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("stage") == "v5_onset" and d.get("final_indeks") is not None:
                    kayitlar.append(d)
    except Exception:
        return []
    kayitlar.sort(key=lambda d: d.get("ts") or "")
    return kayitlar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esik", type=int, default=40,
                    help="koşular-arası start_pos kayma eşiği (kare) — aynı filmin "
                         "events.jsonl'inde ardışık iki başarılı v5_onset kaydı arasında")
    ap.add_argument("--baslangic", default="2026-07-23T19:00",
                    help="v5 aktivasyon anı — bundan ESKİ eski-motor koşuları tarihi sayılır, aday olmaz")
    ap.add_argument("--json", help="özeti JSON olarak da yaz")
    a = ap.parse_args()

    kayitlar = []
    for p in sorted(glob.glob(f"{DB}/*/frames/jenerik_detection.json")):
        try:
            m = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        film_dir = os.path.dirname(os.path.dirname(p))
        film = os.path.basename(film_dir)
        kayitlar.append({"film": film, "film_dir": film_dir, "engine": m.get("engine"),
                         "status": m.get("status"), "start_pos": m.get("start_pos"),
                         "pool_frames": m.get("pool_frames"), "input_frames": m.get("input_frames"),
                         "v5": m.get("v5"), "ts": m.get("ts")})

    v5li = [k for k in kayitlar if k["engine"] == "v5_onset"]
    eski = [k for k in kayitlar if k["engine"] != "v5_onset"]
    print(f"TOPLAM manifest: {len(kayitlar)}  |  v5_onset: {len(v5li)}  |  eski-motor: {len(eski)}")

    # ── 1) kredi_yok kuyruğu (Dalga 3'ün etkileyeceği filmler) ──────────────
    kredi_yok_kuyrugu = [k for k in kayitlar if (k.get("v5") or {}).get("karar") == "kredi_yok"]

    # ── 0) ŞÜPHE KUYRUĞU (2026-07-30, şüphe katmanı: gec/erken/parcalanma
    # imzaları, bkz. credit_onset.Sonuc.suphe). v5.suphe dolu (herhangi bir
    # imza tetiklenmiş) manifestleri AYRI listele — Çağatay: "tespit edemesek
    # bile şüpheyi bilelim". Hiçbir imza onset kararını DEĞİŞTİRMEDİ, yalnız
    # görünürlük/triyaj için işaretlendi (kredi_yok kuyruğuyla ÇAKIŞABİLİR —
    # ayrık kümeler değil, ikisi de bağımsız birer sinyal).
    suphe_kuyrugu = []
    for k in kayitlar:
        v5d = k.get("v5") or {}
        suphe_liste = v5d.get("suphe") or []
        if suphe_liste:
            suphe_kuyrugu.append({**k, "sebep": f"suphe={','.join(suphe_liste)} (kare={v5d.get('kare')})"})

    # ── 2-4) ölçüye dayalı triyaj (yalnız kredi_yok kuyruğu DIŞINDakiler) ───
    triyaj = []
    for k in kayitlar:
        if k in kredi_yok_kuyrugu:
            continue
        sebepler = []
        pf, inf = k.get("pool_frames"), k.get("input_frames")
        if pf is not None and pf < POOL_FRAMES_MIN:
            sebepler.append(f"geç-çapa şüphesi (pool_frames={pf} < {POOL_FRAMES_MIN})")
        if pf is not None and inf:
            oran = pf / inf
            if oran > POOL_INPUT_ORAN_MAX:
                sebepler.append(f"erken-çapa şüphesi (pool/input={oran:.2f} > {POOL_INPUT_ORAN_MAX})")
        v5d = k.get("v5") or {}
        if v5d.get("karar") == "found" and v5d.get("son_capa") is not None and v5d["son_capa"] < SON_CAPA_MIN:
            sebepler.append(f"SON_ERISIM gevşetme yolu ateşlemiş (son_capa={v5d['son_capa']:.2f} < {SON_CAPA_MIN})")
        for sebep in sebepler:
            triyaj.append({**k, "sebep": sebep})

    # ── run-to-run start_pos kayması (events.jsonl geçmişi, --esik) ─────────
    kayma_adaylari = []
    for k in kayitlar:
        gecmis = _events_v5_gecmisi(k["film_dir"])
        if len(gecmis) < 2:
            continue
        son, onceki = gecmis[-1], gecmis[-2]
        fark = int(son["final_indeks"]) - int(onceki["final_indeks"])
        if abs(fark) >= a.esik:
            kayma_adaylari.append({**k, "sebep": f"koşular-arası kayma {fark:+d} kare "
                                    f"(son={son['final_indeks']} önceki={onceki['final_indeks']})"})

    # ── eski-motor bilgilendirmesi (v5 aktivasyonundan SONRA CV'ye düşenler) ─
    eski_aday = []
    tarihi = 0
    for k in eski:
        if (k.get("ts") or "") < a.baslangic:
            tarihi += 1
            continue
        eski_aday.append({**k, "sebep": f"v5 devre dışı kaldı (engine={k['engine']}, status={k['status']})"})
    if tarihi:
        print(f"(aktivasyon-öncesi tarihi koşu: {tarihi} — aday sayılmadı)")

    def _yazdir(baslik, liste):
        if not liste:
            return
        print(f"\n{baslik} ({len(liste)}):")
        for k in liste:
            print(f"  {k['film'][:52]:<53} start={str(k.get('start_pos')):>5}  {k['sebep']}")

    kredi_yok_kuyrugu_liste = [
        {**k, "sebep": f"v5 kredi_yok dedi (engine={k['engine']}, yontem={(k.get('v5') or {}).get('yontem')})"}
        for k in kredi_yok_kuyrugu]
    _yazdir("ŞÜPHE KUYRUĞU (gec_riski/erken_riski/parcalanma_riski imzaları)", suphe_kuyrugu)
    _yazdir("KREDİ_YOK KUYRUĞU (Dalga 3 kararının etkileyeceği filmler)", kredi_yok_kuyrugu_liste)
    _yazdir("ÖLÇÜYE-DAYALI TRİYAJ ADAYLARI", triyaj)
    _yazdir("KOŞULAR-ARASI KAYMA ADAYLARI", kayma_adaylari)
    _yazdir("ESKİ-MOTOR ADAYLARI (v5 aktivasyonu sonrası CV'ye düştü)", eski_aday)

    if not (suphe_kuyrugu or kredi_yok_kuyrugu or triyaj or kayma_adaylari or eski_aday):
        print("\nİnceleme adayı yok.")

    if a.json:
        json.dump({"toplam": len(kayitlar), "v5": len(v5li), "eski": len(eski),
                   "suphe_kuyrugu": suphe_kuyrugu,
                   "kredi_yok_kuyrugu": kredi_yok_kuyrugu_liste, "triyaj": triyaj,
                   "kayma_adaylari": kayma_adaylari, "eski_aday": eski_aday},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\nJSON yazıldı: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
