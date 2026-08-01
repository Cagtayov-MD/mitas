#!/usr/bin/env python3
"""HAKEM VL — çelişkide videoyu ikinci bir göze okutur ve ADRES ister.

ÇAĞATAY FİKRİ (2026-08-01): "Bu hatalarda VL modele video olarak verip
'kardeş bir de sen bak' demek. Bu bizim emniyet kemerimiz — kaza olsa da
içinden canlı çıkmamızı sağlayan şey."

NEDEN VİDEO, NEDEN YENİ HAVUZ YOK: Çağatay'ın itirazı haklıydı — kare verirsek
hakem ikinci bir KARE-OKUYUCU olur, bağımsız sensör olmaz. Kayan jeneriğin
kareler arasında bölünen satırı videoda SÜREKLİ. Kaynak mp4'ten pencere kesilir,
hiçbir şey biriktirilmez (mevcut 3 havuza dördüncüsü EKLENMEZ).

ADRES ZORUNLU (kritik tasarım kararı): hakem isim değil ADRES döner —
"kaçıncı saniyede". saniye × fps = kare indeksi → o kareye det sorulabilir.
Adressiz VL, KB'nin yerine geçen ikinci bir "bana inan" otoritesi olurdu;
adresle birlikte iddiasını PİKSELE bağlar. Bu, RONALDO'nun hakem mantığının
video koluna taşınmasıdır.

MODEL — ölçülerek seçildi (2026-08-01, aynı kart, aynı GPU):
    MiniCPM-V-4.5   105 sn kalkış · 3.1 GiB KV · 20 sn blok 2.9 sn  ✓ SEÇİLDİ
    Qwen3-VL-8B     0.62'de çöktü, 0.85'te KV 1.48 GiB (yarısı)
CANLI KANIT: KUTSAL HAZİNE'de deepseek 'JOHN CONNICK' okumuştu (örtülü kare),
MiniCPM 'JOHN HUNECK' dedi — ve AFİŞ ("Diretto da JOHN HUNECK") MiniCPM'i
doğruladı. Hakem ilk sınavında deepseek'i düzeltti.

VRAM GERÇEĞİ: video-VL ~20 GB ister, 24 GB kartta başka hiçbir şeyle BİRLİKTE
duramaz. Bu yüzden hakem AYRI FAZ: Ollama boşalt → vLLM kaldır → koş → indir.
Zaten yalnız ÇELİŞKİDE koşacak (286 filmde 7 — %2.5), hız önemsiz.

KULLANIM (tek film, elle):
    python3 scripts/hakem_vl.py --hub "Database/<film>" --alan yonetmen
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
PORT = int(os.environ.get("MITAS_HAKEM_VL_PORT", "8101") or 8101)
MODEL_AD = os.environ.get("MITAS_HAKEM_VL_MODEL", "minicpm")
SNAP_DESEN = "models--openbmb--MiniCPM-V-4_5"
FPS = 1.5                       # kare sözleşmesi (pipeline ile aynı)
BLOK_SN = 20                    # kanıtlı reçete (CICEK_TAKSI turu)
CAGRI_TIMEOUT = int(os.environ.get("MITAS_HAKEM_VL_TIMEOUT", "300") or 300)

ISTEM = (
    "Bu video bir filmin jeneriğinden bir bolum. Ekranda YAZAN metinleri oku. "
    "{alan_tarifi} "
    "Cevabi SADECE JSON ver, baska hicbir metin yok: "
    '{{"deger": "<okudugun ad, yoksa null>", "saniye": <bu blogun kacinci saniyesi>, '
    '"etiket": "<gordugun rol etiketi, yoksa null>", "tum_metin": ["..."]}}  '
    "Emin degilsen deger=null yaz. TAHMIN ETME, sadece GORDUGUNU yaz."
)
ALAN_TARIF = {
    "yonetmen": ("YONETMEN kartini ara: 'Directed by', 'A <isim> FILM', 'Yonetmen', "
                 "'Mise en scene', 'Regie', 'Realisation' gibi bir etiket ve onun "
                 "YANINDAKI/ALTINDAKI kisi adi. Yardimci/goruntu/ses/dublaj yonetmeni DEGIL."),
    "yapimci": ("YAPIMCI kartini ara: 'Produced by', 'Yapimci', 'Producer' etiketi ve "
                "yanindaki kisi adi. Yurutucu yapimci sayilir; ortak/yardimci yapimci HAYIR."),
}


def _log(m: str) -> None:
    print(f"[hakem-vl] {m}", flush=True)


def sunucu_durum() -> bool:
    """vLLM GERÇEKTEN bizim mi? (curl -f + imza — port yeter DEĞİL)"""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/models")
        with urllib.request.urlopen(req, timeout=3) as r:
            return b'"data"' in r.read()
    except Exception:  # noqa: BLE001
        return False


def sunucu_baslat(bekle: int = 300) -> bool:
    if sunucu_durum():
        _log("sunucu zaten ayakta")
        return True
    snaps = sorted((PROJE / "models" / "hf_cache" / "hub" / SNAP_DESEN / "snapshots").glob("*/"))
    if not snaps:
        _log(f"RED: {SNAP_DESEN} snapshot yok")
        return False
    # VRAM: video-VL tek başına ~20 GB → Ollama'yı BOŞALT (vlm_sunucu.sh deseni)
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=5) as r:
            for m in (json.loads(r.read()).get("models") or []):
                urllib.request.urlopen(urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=json.dumps({"model": m["name"], "keep_alive": 0}).encode(),
                    headers={"Content-Type": "application/json"}), timeout=10).read()
                _log(f"ollama boşaltıldı: {m['name']}")
    except Exception:  # noqa: BLE001 — ollama yoksa sorun değil
        pass
    log = PROJE / "outputs" / "hakem_vl.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CUDA_HOME": "/usr/local/cuda",
           "HF_HOME": str(PROJE / "models" / "hf_cache"),
           "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
    with log.open("a") as h:
        subprocess.Popen(
            [str(PROJE / "venvs" / "vllm" / "bin" / "vllm"), "serve", str(snaps[-1]),
             "--served-model-name", MODEL_AD, "--port", str(PORT),
             "--max-model-len", "16384", "--gpu-memory-utilization", "0.90",
             "--enforce-eager", "--trust-remote-code",
             "--allowed-local-media-path", "/tmp",
             "--limit-mm-per-prompt", '{"video": 1}',
             "--mm-processor-kwargs", '{"max_pixels": 125440}',
             "--max-num-batched-tokens", "16384"],
            stdout=h, stderr=subprocess.STDOUT, env=env)
    for _ in range(bekle // 5):
        time.sleep(5)
        if sunucu_durum():
            _log("sunucu HAZIR")
            return True
    _log(f"RED: sunucu {bekle} sn'de kalkmadı — log: {log}")
    return False


def sunucu_durdur() -> None:
    subprocess.run(["pkill", "-f", f"vllm serve.*--port {PORT}"], capture_output=True)


def blok_kes(kaynak: Path, bas_sn: float, sure: float, hedef: Path) -> bool:
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(bas_sn),
                        "-t", str(sure), "-i", str(kaynak),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(hedef)],
                       capture_output=True, timeout=300)
    return r.returncode == 0 and hedef.is_file() and hedef.stat().st_size > 1024


def blok_sor(video: Path, alan: str, blok_bas_sn: float) -> dict | None:
    gov = {"model": MODEL_AD, "temperature": 0, "max_tokens": 700,
           "messages": [{"role": "user", "content": [
               {"type": "video_url", "video_url": {"url": f"file://{video}"}},
               {"type": "text", "text": ISTEM.format(
                   alan_tarifi=ALAN_TARIF.get(alan, ALAN_TARIF["yonetmen"]))}]}]}
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                     data=json.dumps(gov).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=CAGRI_TIMEOUT) as r:
            cev = json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        _log(f"blok hata {type(e).__name__}: {str(e)[:80]}")
        return None
    m = re.search(r"\{.*\}", cev, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
    if not j.get("deger"):
        return None
    # ADRES: blok-içi saniye → MUTLAK saniye → kare indeksi
    try:
        ic_sn = float(j.get("saniye") or 0)
    except Exception:  # noqa: BLE001
        ic_sn = 0.0
    mutlak = blok_bas_sn + max(0.0, ic_sn)
    j["mutlak_saniye"] = round(mutlak, 1)
    j["kare_indeksi"] = int(round(mutlak * FPS))
    return j


_PAYLASIM = os.environ.get(
    "MITAS_SHARE_DIR",
    "/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,"
    "share=sas_h264/Film Kapanış")


def video_bul(hub: Path) -> Path | None:
    """Kaynak videoyu bul: hub → hub/source → PAYLAŞIM (TRT kimliğiyle).

    Üretim `--no-copy-source` ile koşuyor (disk tasarrufu) → mp4 hub'da YOK.
    Bu yüzden paylaşım yedeği ŞART; yoksa hakem hiç çalışamaz.
    """
    for aday in (sorted(hub.glob("*.mp4")), sorted((hub / "source").glob("*.mp4"))):
        if aday:
            return aday[0]
    m = re.search(r"(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)", hub.name)
    if not m:
        return None
    pay = Path(_PAYLASIM)
    if not pay.is_dir():
        _log(f"paylaşım bağlı değil: {pay}")
        return None
    try:
        for f in pay.iterdir():
            if m.group(1) in f.name and f.suffix.lower() == ".mp4":
                _log(f"video paylaşımdan: {f.name}")
                return f
    except OSError as e:
        _log(f"paylaşım okunamadı: {e}")
    return None



def _hakem_dogrula(bulgu: dict, alan: str) -> str | None:
    """HAKEMİN CEVABINI DENETLE — kusur sebebini döner, temizse None.

    İLK SINAVDA GEREKTİ (2026-08-01, KUTSAL HAZİNE): hakem 'JOSEPH CAMPANELLA'
    dedi ve etiketi 'Yonetmen' diye UYDURDU — oysa kendi verdiği tum_metin
    ['Starring TOM TAYBACK as Grizzly Adams', 'JOSEPH CAMPANELLA', ...] açıkça
    OYUNCU kartı. VL de bir dil modeli; adressiz/denetimsiz kabul edilirse
    KB'nin yerine geçen ikinci bir otorite olur.
    ÇÖZÜM: hakemin cevabı, modelin cevabına uyguladığımız AYNI rol-denetiminden
    geçer (yonetmen_kurtar.dogrula) — tek kural, iki yerde.
    """
    deger = str(bulgu.get("deger") or "").strip()
    if not deger:
        return "bos_deger"
    metin = [str(x) for x in (bulgu.get("tum_metin") or [])]
    # (a) ETİKET UYDURMA TESTİ — en güçlü sinyal (3. tur sertleştirme):
    #     Model bir etiket İDDİA ediyorsa, o etiket KENDİ OKUDUĞU metinde
    #     GEÇMEK ZORUNDA. KUTSAL HAZİNE'de 'Mise en scene' dedi ama tum_metin
    #     düpedüz oyuncu listesiydi (SELINA JAYNE, JOEL ROOKS, TOM SCHUSTER…);
    #     etiket metinde YOKTU → uydurma. Bu test, anahtar-kelime avına
    #     ('Starring' vb.) bağlı kalmadan her uydurmayı yakalar.
    et = str(bulgu.get("etiket") or "").strip()
    blok = " ".join(metin)
    if et and et.lower() not in blok.lower():
        # gevşek eşleşme: etiketin ilk anlamlı kelimesi metinde var mı
        kel = [w for w in re.split(r"\W+", et.lower()) if len(w) > 3]
        if not kel or not any(w in blok.lower() for w in kel):
            return "etiket_metinde_yok"
    # (b) OYUNCU-BLOĞU imzası: açık anahtar kelimeler
    if alan == "yonetmen" and re.search(
            r"\bstarring\b|\bas [a-z]+\b|oyuncular|\bcast\b|\brol[ae]\b", blok.lower()):
        return "oyuncu_blogu"
    # (c) İSİM LİSTESİ imzası: etiketsiz 4+ isim = kadro bloğu, kart değil
    if alan == "yonetmen":
        try:
            import sys as _s0
            _s0.path.insert(0, str(PROJE / "scripts"))
            import yonetmen_kurtar as _yk0
            isim_n = sum(1 for x in metin if _yk0.isim_mi(x))
            if isim_n >= 4 and not any(_yk0._ETIKET.search(x) for x in metin):
                return "etiketsiz_isim_listesi"
        except Exception:  # noqa: BLE001
            pass
    # (b) rol-denetimi: kendi verdiği metin bağlamında isim yönetmen-dışı bir
    #     etikete mi ait? (modelin cevabıyla AYNI süzgeç)
    try:
        import sys as _s
        _s.path.insert(0, str(PROJE / "scripts"))
        import yonetmen_kurtar as _yk
        kusur = _yk.dogrula(deger, metin)
        if kusur:
            return f"rol_denetimi:{kusur.get('sebep')}"
        if not _yk.isim_mi(deger):
            return "isim_bicimi_degil"
    except Exception:  # noqa: BLE001 — denetim yoksa hüküm YOK (kabul etmeyiz)
        return "denetim_yapilamadi"
    return None


def hakemlik(hub: Path, alan: str = "yonetmen", pencere: str = "giris",
             max_blok: int = 12) -> dict:
    """Pencereyi 20 sn bloklara böl, ilk ADRESLİ cevapta dur."""
    kaynak = video_bul(hub)
    if kaynak is None:
        return {"durum": "kaynak_video_yok", "hub": hub.name}
    bas = 0.0 if pencere == "giris" else None      # çıkış: kuyruk (süre gerekir)
    if bas is None:
        try:
            r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                                "format=duration", "-of", "csv=p=0", str(kaynak)],
                               capture_output=True, text=True, timeout=60)
            bas = max(0.0, float(r.stdout.strip()) - 480.0)
        except Exception:  # noqa: BLE001
            bas = 0.0
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"hakem_{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=True)
    bulgular, reddedilen = [], []
    try:
        for i in range(max_blok):
            b0 = bas + i * BLOK_SN
            blok = tmp / f"b{i:02d}.mp4"
            if not blok_kes(kaynak, b0, BLOK_SN, blok):
                break
            r = blok_sor(blok, alan, b0)
            blok.unlink(missing_ok=True)
            if not r:
                continue
            kusur = _hakem_dogrula(r, alan)
            if kusur:
                r["reddedildi"] = kusur
                reddedilen.append(r)
                _log(f"blok {i} ({b0:.0f}s) → {r['deger']!r} REDDEDİLDİ ({kusur})")
                continue
            bulgular.append(r)
            _log(f"blok {i} ({b0:.0f}s) → {r['deger']!r} ✓ "
                 f"etiket={r.get('etiket')!r} kare≈{r['kare_indeksi']}")
            break
    finally:
        for p in tmp.glob("*.mp4"):
            p.unlink(missing_ok=True)
        tmp.rmdir()
    if not bulgular:
        return {"durum": "bulunamadi", "alan": alan, "pencere": pencere,
                "reddedilen": reddedilen[:4]}
    return {"durum": "bulundu", "alan": alan, "pencere": pencere,
            "reddedilen_n": len(reddedilen), **bulgular[0]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", required=True)
    ap.add_argument("--alan", default="yonetmen", choices=sorted(ALAN_TARIF))
    ap.add_argument("--pencere", default="giris", choices=("giris", "cikis"))
    ap.add_argument("--birak-acik", action="store_true", help="sunucuyu kapatma")
    a = ap.parse_args()
    hub = Path(a.hub)
    if not hub.is_absolute():
        hub = PROJE / hub
    if not sunucu_baslat():
        print(json.dumps({"durum": "sunucu_kalkmadi"}, ensure_ascii=False))
        return 1
    try:
        sonuc = hakemlik(hub, a.alan, a.pencere)
    finally:
        if not a.birak_acik:
            sunucu_durdur()
    print(json.dumps(sonuc, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
