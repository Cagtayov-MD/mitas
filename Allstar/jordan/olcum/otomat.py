#!/usr/bin/env python3
"""OTOMAT — Jordan config matrisini insan olmadan koşar.

NEDEN: her varyant icin `jordan tek` cagirmak modeli (14-19 GB) her seferinde
yeniden yukluyordu. Burada model MODEL BASINA BIR KEZ yuklenir, tum varyant x
klip kombinasyonlari o yuklemeyle kosar.

DAYANIKLILIK: her sonuc satiri ANINDA `sonuc.jsonl`'e eklenir. Kosu kesilirse
(guc, OOM, oturum kapanmasi) yeniden baslatildiginda bitmis satirlari ATLAR.
Yani "baslat ve unut" — token bitse de makine bos kalmaz.

KULLANIM
  nohup venv/bin/python olcum/otomat.py > logs/otomat.log 2>&1 &
  venv/bin/python olcum/otomat.py --durum      # ilerlemeyi goster
  venv/bin/python olcum/otomat.py --rapor      # siralanmis sonuc tablosu
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

SONUC = KULE / "olcum" / "kosular" / "sonuc.jsonl"
KLIP_DIZIN = Path("/home/cagatay/Belgeler/test")

SHARP = "flags=lanczos,hqdn3d=2:2:2,unsharp=5:5:1.0"
SCENE = "select='gt(scene,0.2)'"

# ── MATRİS ───────────────────────────────────────────────────────────────
# Çağatay'ın "Qwen2.5-VL-7B FP16 MAX" tarifi — TEK config, TÜM klipler.
# ffmpeg klibi hazırlar (fps=2), model ondan kendi hızıyla örnekler (fps=1.0).
# İkisi ayrı kaldıraç; karıştırılmamalı.
ISTEM_MAX = (KULE / "olcum" / "current_ocr_prompt.txt").read_text(encoding="utf-8")

VARYANTLAR = [
    ("FP16MAX", f"scale=720:-2:{SHARP}", 2, 30, False),   # 30 sn parca
]
# max_pixels=640*640 OLCULDU ve BU ICERIKTE ETKISIZ: kare 720x540=388.800 px,
# butce 409.600 px — tavan zaten asilmiyor, token sayisi birebir ayni kaliyor
# (2206). Isleyen tek kaldirac size.longest_edge. Uydurmamak icin cikarildi.
# 30 sn parcadan 12 anahtar kare → model tarafi fps = 12/30 = 0.4
GORSEL = {"video_fps": 0.4}
URETIM = {"max_new_tokens": 1024, "temperature": 0.01, "do_sample": False}

MODELLER = [
    ("qwen2.5vl", "model/qwen2.5-vl-7b", "float16"),
]

KLIPLER = [f"{i:02d}" for i in range(1, 29)]        # 28 klibin TAMAMI


def _cfg(varyant, model_yolu, dtype) -> dict:
    import yaml
    c = yaml.safe_load((KULE / "config.yaml").read_text(encoding="utf-8"))
    ad, suz, fps, psn, greedy = varyant
    c["model"] = {"yol": model_yolu, "dtype": dtype, "dusunme": False}
    c["video"] = {**c.get("video", {}), "suzgec": suz, "fps": fps}
    c["parca"] = {**c.get("parca", {}), "sure_sn": psn, "bindirme_sn": 5,
                  "kare_tavani": int(psn * fps) + 2}
    c["birlestir"] = {"esik": 0.85}
    c["uretim"] = dict(URETIM)
    c["istem"] = {**c.get("istem", {}), "okuma": ISTEM_MAX}
    return c


def bitmisler() -> set:
    if not SONUC.exists():
        return set()
    out = set()
    for satir in SONUC.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(satir)
            if d.get("klip") in (None, "-") or "durum" not in d:
                continue          # yukleme-hatasi kaydi, kosu degil
            out.add((d["model"], d["varyant"], d["klip"]))
        except Exception:
            continue
    return out


def yaz(kayit: dict) -> None:
    SONUC.parent.mkdir(parents=True, exist_ok=True)
    with SONUC.open("a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def puanla_varsa(txt: Path, klip: str) -> dict:
    gt = KULE / "olcum" / "gt" / klip / "gt.txt"
    if not (gt.exists() and txt.exists()):
        return {}
    sys.path.insert(0, str(KULE / "olcum"))
    import puanla as P
    g, gtr = P.gt_oku(gt)
    p = P.puanla(P.cikti_oku(txt), g, gtr)
    p["skor"] = P.skor(p)
    return {k: v for k, v in p.items() if not k.startswith("_")}


def kos() -> int:
    from model import Motor
    from okuyucu import oku, parcala
    from ciftleyici import ciftle

    done = bitmisler()
    toplam = len(MODELLER) * len(VARYANTLAR) * len(KLIPLER)
    print(f"[otomat] matris {toplam} koşu · bitmiş {len(done)}", flush=True)

    for mad, myol, dtype in MODELLER:
        kalan = [(v, k) for v in VARYANTLAR for k in KLIPLER
                 if (mad, v[0], k) not in done]
        if not kalan:
            print(f"[{mad}] hepsi bitmiş, atlanıyor", flush=True)
            continue
        yol = KULE / myol
        if not (yol / "config.json").exists():
            print(f"[{mad}] MODEL YOK ({yol}) — atlanıyor", flush=True)
            continue

        print(f"[{mad}] model yükleniyor ({len(kalan)} koşu bekliyor)", flush=True)
        t0 = time.time()
        try:
            motor = Motor(yol, dtype=dtype, dusunme=False, uretim={},
                          gorsel=dict(GORSEL)).yukle()
        except Exception as e:
            # OOM genelde GECICIDIR (baska is GPU'yu tutuyor). Temiz cikis
            # verirsek systemd "basardi" sanip yeniden denemez — o yuzden
            # HATA KODUYLA cikiyoruz ki Restart=on-failure devreye girsin.
            print(f"[{mad}] YÜKLENEMEDİ: {e}", flush=True)
            print("[otomat] GPU dolu olabilir — hata koduyla çıkılıyor, "
                  "systemd yeniden deneyecek", flush=True)
            return 75
        print(f"[{mad}] yüklendi ({time.time()-t0:.0f} sn)", flush=True)

        for varyant in VARYANTLAR:
            ad = varyant[0]
            for klip in KLIPLER:
                if (mad, ad, klip) in done:
                    continue
                video = KLIP_DIZIN / f"cag_output{klip}.mp4"
                if not video.exists():
                    continue
                fid = f"{mad}__{ad}__{klip}"
                scratch = KULE / "scratch" / fid
                t1 = time.time()
                kayit = {"model": mad, "varyant": ad, "klip": klip,
                         "zaman": time.strftime("%F %T")}
                try:
                    cfg = _cfg(varyant, myol, dtype)
                    motor.uretim = cfg.get("uretim", {})
                    parcalar = parcala(str(video), scratch, cfg)
                    bloklar, kanit = oku(motor, parcalar, cfg)
                    ciftler, kanit2 = ciftle(motor, bloklar, cfg)
                    d = KULE / "out" / fid / "cikis"
                    d.mkdir(parents=True, exist_ok=True)
                    satirlar = [s for b in bloklar for s in b["satirlar"]]
                    (d / "jordan.txt").write_text("\n".join(satirlar), encoding="utf-8")
                    (d / "jordan.json").write_text(json.dumps(
                        {"bloklar": bloklar, "ciftler": ciftler,
                         "kanit": {**kanit, **kanit2}},
                        ensure_ascii=False, indent=1), encoding="utf-8")
                    kayit |= {"durum": "OKUNDU" if bloklar else "METIN_YOK",
                              "sure_sn": round(time.time() - t1, 1),
                              "satir": len(satirlar), "cift": len(ciftler),
                              "parca": len(parcalar),
                              **{f"p_{k}": v for k, v in
                                 puanla_varsa(d / "jordan.txt", klip).items()}}
                except Exception as e:                       # noqa: BLE001
                    kayit |= {"durum": "ARIZA", "hata": f"{type(e).__name__}: {e}"[:300],
                              "sure_sn": round(time.time() - t1, 1)}
                    traceback.print_exc()
                finally:
                    shutil.rmtree(scratch, ignore_errors=True)
                yaz(kayit)
                print(f"  [{mad}/{ad}/{klip}] {kayit.get('durum')} "
                      f"{kayit.get('sure_sn')}sn satır={kayit.get('satir','-')} "
                      f"skor={kayit.get('p_skor','-')}", flush=True)

        del motor
        try:
            import torch, gc
            gc.collect(); torch.cuda.empty_cache()
        except Exception:
            pass
    print("[otomat] MATRİS BİTTİ", flush=True)
    return 0


def rapor() -> int:
    if not SONUC.exists():
        print("sonuç yok"); return 1
    rows = [json.loads(s) for s in SONUC.read_text(encoding="utf-8").splitlines() if s.strip()]
    puanli = [r for r in rows if r.get("p_skor") is not None]
    print(f"toplam koşu: {len(rows)} · puanlanan: {len(puanli)}\n")
    grup: dict = {}
    for r in puanli:
        grup.setdefault((r["model"], r["varyant"]), []).append(r)
    print(f"{'MODEL':<12} {'VARYANT':<14} {'n':>2} {'skor':>6} {'recall':>7} "
          f"{'tr':>6} {'uydurma':>8} {'satır':>6} {'sn':>6}")
    ort = lambda v, k: round(sum(x[k] for x in v) / len(v), 3)   # noqa: E731
    for (m, a), v in sorted(grup.items(), key=lambda x: -ort(x[1], "p_skor")):
        print(f"{m:<12} {a:<14} {len(v):>2} {ort(v,'p_skor'):>6} "
              f"{ort(v,'p_recall'):>7} {ort(v,'p_tr_dogru'):>6} "
              f"{ort(v,'p_uydurma_oran'):>8} {ort(v,'satir'):>6.0f} {ort(v,'sure_sn'):>6.0f}")
    return 0


def durum() -> int:
    done = bitmisler()
    toplam = len(MODELLER) * len(VARYANTLAR) * len(KLIPLER)
    print(f"{len(done)}/{toplam} koşu bitti (%{100*len(done)/toplam:.0f})")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapor", action="store_true")
    ap.add_argument("--durum", action="store_true")
    n = ap.parse_args()
    sys.exit(rapor() if n.rapor else durum() if n.durum else kos())
