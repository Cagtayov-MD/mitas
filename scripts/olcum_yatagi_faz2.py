#!/usr/bin/env python3
"""ÖLÇÜM YATAĞI — FAZ 2: İKİ KOL OKUR, BİRLEŞİM ÜRETİR (ham çıktı).

KAPSAM: yalnız OKUMA. gemma YOK, rol eşleme YOK, QC1 hükmü YOK, PDF YOK.
Amaç Çağatay'ın cümlesiyle: "kim ne getiriyor onu görmek."

KOLLAR (turnuva + Çağatay kararı, 2026-07-31):
    Kol A  FRAME   frames/cikis_jenerik → Messi kare seçimi → deepseek-ocr (Ollama)
    Kol B  MASTER  reading_master_runaware.png → dikey bantlar → qwen8 (vLLM tam ağırlık)

NEDEN İKİ AYRI AİLE: aynı modeli iki kolda kullanmak ortak kör noktayı açık
bırakıyor. Gözlenmiş kanıt (Çağatay): rodeo vakasında iki kol da deepseek olduğu
için İKİSİ BİRDEN çöktü, "Kubrick/Godfather" uydurmaları iki kolda da göründü.
Aileler ayrışınca biri uydurursa öteki teyit vermez.

MODEL TAKASI — "toplu faz" (Çağatay onayı): önce TÜM filmler Kol A ile, sonra TÜM
filmler Kol B ile. Takas batch başına BİR kez, film başına sıfır. VRAM ölçümü:
deepseek 6.7 GB + qwen8 6.1 GB = 12.8 GB (24 GB'a sığar) ama gemma 19 GB tek başına
kartı dolduruyor → okuma fazı ile rol-eşleme fazı ZORUNLU olarak ayrık.

BAYRAK: MASTER_GOZU=qwen8-vllm (varsayılan) | deepseek  — kalıcı karar üretim
verisiyle verilecek (ilk 20-30 filmde bant/KONTROL oranı izlenir).

KULLANIM:
    python3 scripts/olcum_yatagi_faz2.py --kol frame     # Kol A, tüm filmler
    python3 scripts/olcum_yatagi_faz2.py --kol master    # Kol B, tüm filmler
    python3 scripts/olcum_yatagi_faz2.py --kol birlesim  # model YOK, union üretir
    python3 scripts/olcum_yatagi_faz2.py --kol frame --film 3
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
KOK = PROJE / "outputs" / "olcum_yatagi"
KLIPLER = KOK / "klipler"

OLLAMA = (os.environ.get("MITAS_OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
VLLM = (os.environ.get("MITAS_VIDEO_VL_URL") or "http://127.0.0.1:8100").rstrip("/")

FRAME_MODEL = os.environ.get("FRAME_GOZU", "deepseek-ocr:latest")
MASTER_GOZU = os.environ.get("MASTER_GOZU", "qwen8-vllm")
VLLM_MODEL = os.environ.get("MITAS_VIDEO_VL_MODEL", "qwen3-vl-8b")

# Master bant geometrisi — pilot_hat.oku_master ile aynı
BANT_H = int(os.environ.get("OLCUM_BANT_H", "1100"))
BINDIRME = int(os.environ.get("OLCUM_BINDIRME", "120"))
# Kol A'da kaç sayfa okunacak (maliyet tavanı; _pipe_track_kunye ile aynı varsayılan)
MAX_SAYFA = int(os.environ.get("OLCUM_MAX_SAYFA", "100"))
ISTEM = "Free OCR."

sys.path.insert(0, str(PROJE / "harness" / "track_kunye"))


# ─────────────────────────── okuyucular ───────────────────────────

def ollama_oku(png: Path, model: str, timeout: int = 300) -> str:
    """Ollama /api/generate — tek görüntü, düz OCR."""
    gov = {"model": model, "prompt": ISTEM, "stream": False,
           "images": [base64.b64encode(png.read_bytes()).decode()],
           "options": {"temperature": 0.0, "num_predict": 2048, "num_ctx": 8192}}
    req = urllib.request.Request(f"{OLLAMA}/api/generate",
                                data=json.dumps(gov).encode(),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("response", "") or ""


def vllm_oku(png: Path, model: str, timeout: int = 300) -> str:
    """vLLM OpenAI-uyumlu /v1/chat/completions — image_url (data: URI)."""
    b64 = base64.b64encode(png.read_bytes()).decode()
    gov = {"model": model, "temperature": 0.0, "max_tokens": 3500,
           "messages": [{"role": "user", "content": [
               {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
               {"type": "text", "text": ISTEM}]}]}
    req = urllib.request.Request(f"{VLLM}/v1/chat/completions",
                                 data=json.dumps(gov).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read())
    return (((j.get("choices") or [{}])[0].get("message") or {}).get("content") or "")


def satirlari_ayikla(cevap: str) -> list[str]:
    """Model çıktısını satırlara indir. pilot_hat.oku_deepseek'in temizliğiyle aynı."""
    out = []
    for ln in (cevap or "").splitlines():
        ln = ln.strip().strip("`").lstrip("#").strip().strip("*").strip()
        if len(ln) >= 2:
            out.append(ln)
    return out


def sayfalari_oku(sayfalar: list[Path], *, backend: str, model: str) -> list[dict]:
    """Sayfa sayfa oku, KAYNAK İZİNİ koru (JSONL yan-dosya deseni).

    İz sürme neden baştan var: bir satırın hangi PNG'den geldiğini bilmek
    (a) piksel tahkiminin ön şartı, (b) eşleşmeyen dedektör kutusu = atlanan-isim
    adayı sinyalinin ön şartı. Kaynak dosya çağrı anında ZATEN elde — pilot_hat'te
    bir satır sonra atılıyordu (satır 101).
    """
    oku = ollama_oku if backend == "ollama" else vllm_oku
    kayitlar: list[dict] = []
    for i, p in enumerate(sayfalar, 1):
        t0 = time.perf_counter()
        try:
            cevap = oku(p, model)
            hata = None
        except Exception as e:  # noqa: BLE001 — bir sayfa çuvallarsa kol durmaz
            cevap, hata = "", f"{type(e).__name__}: {e}"[:200]
        sure = round(time.perf_counter() - t0, 2)
        satirlar = satirlari_ayikla(cevap)
        for sira, s in enumerate(satirlar):
            kayitlar.append({"kaynak": p.name, "sayfa_sira": i, "satir_sira": sira,
                             "text": s})
        print(f"      {i:>3}/{len(sayfalar)} {p.name:<26} {len(satirlar):>3} satır "
              f"{sure:>6.2f} sn" + (f"  HATA {hata}" if hata else ""), flush=True)
    return kayitlar


# ─────────────────────────── kollar ───────────────────────────

def kol_frame(clip: Path) -> dict:
    """Kol A: Messi kare seçimi + deepseek okuması."""
    import pilot_hat as ph  # messi'yi kendi içinde kullanıyor

    havuz = clip / "frames" / "cikis_jenerik"
    if not havuz.is_dir() or not any(havuz.glob("*.png")):
        return {"durum": "havuz_bos", "satir_n": 0}
    secim, ist = ph.havuz_derle_dizin(havuz, "*.png")
    if not secim:
        return {"durum": "messi_secim_bos", "havuz": ist, "satir_n": 0}
    dusen = 0
    if len(secim) > MAX_SAYFA:
        adim = len(secim) / MAX_SAYFA
        secim = [secim[int(i * adim)] for i in range(MAX_SAYFA)]
        dusen = len(secim) - MAX_SAYFA
    print(f"      Messi seçimi: {len(secim)} sayfa (havuz {ist.get('kare')}) "
          f"model={FRAME_MODEL}", flush=True)
    kayitlar = sayfalari_oku(secim, backend="ollama", model=FRAME_MODEL)
    return {"durum": "ok", "model": FRAME_MODEL, "backend": "ollama",
            "sayfa_n": len(secim), "dusen": dusen, "havuz": ist,
            "satir_n": len(kayitlar), "kayitlar": kayitlar}


def kol_master(clip: Path) -> dict:
    """Kol B: master PNG'yi dikey bantlara böl + qwen8-vLLM okuması."""
    import cv2  # yalnız bant kesmek için

    master = clip / "reading_master_runaware.png"
    if not master.is_file():
        return {"durum": "master_yok", "satir_n": 0}
    im = cv2.imread(str(master))
    if im is None:
        return {"durum": "master_okunamadi", "satir_n": 0}

    bant_dir = clip / "olcum_master_bantlar"
    bant_dir.mkdir(parents=True, exist_ok=True)
    yollar, ofsetler = [], []
    y, i, H = 0, 0, im.shape[0]
    while y < H:
        bant = im[y:min(y + BANT_H, H)]
        if bant.shape[0] >= 40:
            p = bant_dir / f"bant_{i:03d}.png"
            cv2.imwrite(str(p), bant)
            yollar.append(p)
            # Bant y-ofseti TAŞINIYOR — pilot_hat.oku_master bunu atıyordu (satır 213-217),
            # atılınca bbox bant-yerel kalıyor ve master koordinatına çevrilemiyor.
            ofsetler.append(y)
            i += 1
        if y + BANT_H >= H:
            break
        y += BANT_H - BINDIRME

    if MASTER_GOZU == "deepseek":
        backend, model = "ollama", "deepseek-ocr:latest"
    else:
        backend, model = "vllm", VLLM_MODEL
    print(f"      master {im.shape[1]}x{H} → {len(yollar)} bant  "
          f"model={model} ({backend})", flush=True)

    kayitlar = sayfalari_oku(yollar, backend=backend, model=model)
    ofs = {p.name: o for p, o in zip(yollar, ofsetler)}
    for k in kayitlar:
        k["bant_y0"] = ofs.get(k["kaynak"])
    return {"durum": "ok", "model": model, "backend": backend,
            "bant_n": len(yollar), "master_boyut": [int(im.shape[1]), int(H)],
            "satir_n": len(kayitlar), "kayitlar": kayitlar}


# ─────────────────────────── birleşim ───────────────────────────

def birlesim(clip: Path) -> dict:
    """İki kolun ham çıktısını BİRLEŞTİR (kesişim DEĞİL). Model çağırmaz.

    Bu adım kasten SADE: yapısal filtreler + fold-eşleşme. KB varlık kapısı YOK
    (Çağatay: KB yalnız imlacı). Tahkim bir sonraki adım — burada yalnız
    'kim ne getirdi' görünür kılınıyor.
    """
    import ronaldo as rn

    fa = clip / "olcum_kol_frame.json"
    fb = clip / "olcum_kol_master.json"
    if not fa.is_file() or not fb.is_file():
        return {"durum": "kollar_eksik",
                "frame_var": fa.is_file(), "master_var": fb.is_file()}
    A = json.loads(fa.read_text(encoding="utf-8"))
    B = json.loads(fb.read_text(encoding="utf-8"))
    a_sat = [k["text"] for k in (A.get("kayitlar") or [])]
    b_sat = [k["text"] for k in (B.get("kayitlar") or [])]

    # Yapısal filtreler — şekle bakar, KB'ye DEĞİL. Tahkimden ÖNCE, mutlak veto:
    # '**YÖNETMEN**' hakeme sorulursa hakem pikselde 'YÖNETMEN' görür ve ONAYLAR.
    #
    # DİKKAT — halusinasyon_mu ÇAĞRILMIYOR (denetim bulgusu, 2026-07-31, KRİTİK):
    # o fonksiyonun >8-kelime kuralı 'hiç KB token'ı yok mu' diye bakıyor;
    # boş kb_tok ile HER 9+ kelimeli satır halüsinasyon sayılıp atılıyordu.
    # Reponun kendi testi kanıt (test_ronaldo.py:80-87): iki GERÇEK 10-token'lık
    # künye satırı yalnız dolu KB sayesinde hayatta kalıyor. Çok isimli oyuncu
    # satırları ('AYHAN IŞIK · BELGİN DORUK · ...') tam bu sınıfta → 'isim
    # atlanmasın' şartının doğrudan ihlaliydi. Burada yalnız KB'siz yapısal
    # kurallar uygulanır; KB'li karar Aşama 5'in (birleştirme politikası) işi.
    def yapisal_veto(s: str) -> bool:
        if s.startswith("[") or s.startswith("("):
            return True          # model sahneyi ANLATIYOR, okumuyor
        if "**" in s:
            return True          # markdown artefaktı — ekranda yıldız yok
        harfler = [c for c in s if c.isalpha()]
        if harfler and sum(1 for c in harfler if "一" <= c <= "鿿") / len(harfler) > 0.3:
            return True          # CJK betimleme modu
        # LİSTE-NUMARASI ÇÖPÜ (ilk Kol A koşusunda ölçüldü, 2026-07-31:
        # BOZGUNCULAR 140 satırın 45'i '- 1' / '- 2' tipi — deepseek boş/az
        # içerikli karede numaralı liste uyduruyor). Harf içermeyen satır künye
        # olamaz; Çağatay kuralının uygulaması: 'tek kelime ya da sayılar isim
        # değildir'. Yıl/telif satırları harf taşır ('© 1955 Universal'),
        # onlara dokunmaz.
        if not harfler:
            return True
        kelimeler = rn.fold_tr(s).split()
        if any(k in rn._PROSA_FIIL for k in kelimeler):
            return True          # düzyazı fiil imzası ('appears', 'showing', …)
        return False

    def temiz(satirlar):
        tut, at = [], []
        for s in satirlar:
            if rn.garble_mi(s) or yapisal_veto(s):
                at.append(s)
            else:
                tut.append(s)
        return rn.ic_dedup(tut), at

    a_t, a_at = temiz(a_sat)
    b_t, b_at = temiz(b_sat)

    # Eşleşme: fold + token örtüşmesi (kb_tok BOŞ → saf şekil, KB kararı yok)
    kb: set[str] = set()
    eslesen, a_only, b_only = [], [], []
    b_kullanildi = [False] * len(b_t)
    for s in a_t:
        idx = next((j for j, t in enumerate(b_t)
                    if not b_kullanildi[j] and rn.satir_esle(s, t, kb)), None)
        if idx is None:
            a_only.append(s)
        else:
            b_kullanildi[idx] = True
            eslesen.append({"frame": s, "master": b_t[idx]})
    b_only = [t for j, t in enumerate(b_t) if not b_kullanildi[j]]

    birlesik = [e["frame"] for e in eslesen] + a_only + b_only
    return {"durum": "ok",
            "frame_satir": len(a_t), "master_satir": len(b_t),
            "eslesen_n": len(eslesen), "frame_only_n": len(a_only),
            "master_only_n": len(b_only), "birlesik_n": len(birlesik),
            "atilan_frame": a_at, "atilan_master": b_at,
            "eslesen": eslesen, "frame_only": a_only, "master_only": b_only,
            "birlesik": birlesik}


# ─────────────────────────── sürücü ───────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kol", required=True, choices=["frame", "master", "birlesim"])
    ap.add_argument("--yatak", default=str(KOK / "yatak_15.json"))
    ap.add_argument("--film", type=int, default=None)
    a = ap.parse_args()

    yatak = json.loads(Path(a.yatak).read_text(encoding="utf-8"))
    filmler = yatak["filmler"]
    if a.film:
        filmler = [f for f in filmler if f["sira"] == a.film]

    print(f"=== FAZ 2 · KOL={a.kol.upper()} · {len(filmler)} film ===")
    if a.kol == "frame":
        print(f"    model={FRAME_MODEL} (Ollama) · max_sayfa={MAX_SAYFA}")
    elif a.kol == "master":
        print(f"    MASTER_GOZU={MASTER_GOZU} · bant={BANT_H}px bindirme={BINDIRME}px")

    ozet = []
    for f in filmler:
        tid = f["trt_id"]
        eslesenler = list(KLIPLER.glob(f"{tid}*"))
        if not eslesenler:
            print(f"[{f['sira']:>2}] {tid} — klip dizini YOK (Faz 1 koşmadı mı?)")
            continue
        clip = eslesenler[0]
        print(f"\n[{f['sira']:>2}/{len(filmler)}] {clip.name}", flush=True)
        if (KOK / "DURDUR").exists():
            print("DURDUR görüldü — duruyorum.")
            break
        t0 = time.perf_counter()
        try:
            if a.kol == "frame":
                r = kol_frame(clip)
                (clip / "olcum_kol_frame.json").write_text(
                    json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            elif a.kol == "master":
                r = kol_master(clip)
                (clip / "olcum_kol_master.json").write_text(
                    json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            else:
                r = birlesim(clip)
                (clip / "olcum_birlesim.json").write_text(
                    json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
                if r.get("durum") == "ok":
                    (clip / "kunye_ham.txt").write_text(
                        "\n".join(r["birlesik"]) + "\n", encoding="utf-8")
        except Exception as e:  # noqa: BLE001 — bir film çuvallarsa yatak durmaz
            r = {"durum": "hata", "hata": f"{type(e).__name__}: {e}"[:300]}
            print(f"    HATA: {r['hata']}")
        r["sure_sn"] = round(time.perf_counter() - t0, 1)
        print(f"    durum={r.get('durum')} satır={r.get('satir_n', r.get('birlesik_n'))} "
              f"({r['sure_sn']} sn)", flush=True)
        ozet.append({"sira": f["sira"], "trt_id": tid,
                     **{k: v for k, v in r.items() if k not in
                        ("kayitlar", "eslesen", "frame_only", "master_only",
                         "birlesik", "atilan_frame", "atilan_master")}})

    rap = KOK / f"faz2_{a.kol}_ozet.json"
    rap.write_text(json.dumps({"kol": a.kol, "filmler": ozet},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {rap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
