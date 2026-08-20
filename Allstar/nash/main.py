#!/usr/bin/env python3
"""Nash — ham kare havuzundan jenerik metnini okur. Başka hiçbir şey yapmaz.

Kule girişi. src/ burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: Allstar/nash/nash tek --kareler /yol/frames/cikis --film-id <id>
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")

KULE = Path(__file__).resolve().parent
SRC = KULE / "src"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

from sozlesme import (BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza,
                      tamam_isaretini_kaldir)  # noqa: E402

# secim.hata etiketi → (durum, ariza_sinifi). Tek harita, dağıtık if yok.
# 'havuz_bos' ICERIK GERCEGI'dir (kareler okundu, hepsi iceriksiz) —
# 'kare_okunamadi' ARIZA'dir (kareler var, hicbiri acilamadi). Bugun uretimde
# bu ikisi ayni kutuda; kule ayirir (spec 3.1).
_HATA_HARITA = {
    "dizin_bos": ("ARIZA", "GIRDI_HATASI"),
    "kare_okunamadi": ("ARIZA", "KARE_OKUNAMADI"),
    "detector_ariza": ("ARIZA", "MODEL"),
    "havuz_bos": ("METIN_YOK", None),
}
_HATA_MESAJ = {
    "dizin_bos": "kare dizini yok veya desene uyan dosya yok",
    "kare_okunamadi": "kareler var ama hicbiri acilamadi (bozuk PNG / izin / yarim yazim)",
    "detector_ariza": "metin detectoru ana havuzu guvenilir bicimde tarayamadi",
}


class ConfigHatasi(RuntimeError):
    """Kule YAML'i okunamadi; sessiz varsayilana dusmek yasak."""


class _TembelOkuyucu:
    """Toplu hibritte DeepSeek'i ilk gercek fallback'e kadar yukleme."""

    def __init__(self, kurucu):
        self._kurucu = kurucu
        self._sor = None
        self._hata = None

    def _al(self):
        if self._hata is not None:
            raise self._hata
        if self._sor is None:
            try:
                self._sor = self._kurucu()
            except Exception as exc:
                self._hata = exc
                raise
        return self._sor

    def __call__(self, *args, **kwargs):
        return self._al()(*args, **kwargs)

    def metrics(self) -> dict:
        if self._sor is None:
            return {}
        olcum = getattr(self._sor, "metrics", None)
        return olcum() if callable(olcum) else {}


def _config() -> dict:
    y = KULE / "config.yaml"
    if not y.exists():
        raise ConfigHatasi(f"config bulunamadi: {y}")
    try:
        import yaml
        belge = yaml.safe_load(y.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigHatasi(f"config okunamadi: {type(exc).__name__}: {exc}") from exc
    if not isinstance(belge, dict):
        raise ConfigHatasi("config kok nesnesi sozluk olmali")
    return belge


def _deep_merge(taban: dict | None, ezme: dict | None) -> dict:
    if taban is not None and not isinstance(taban, Mapping):
        raise ConfigHatasi("config bolumu sozluk olmali")
    if ezme is not None and not isinstance(ezme, Mapping):
        raise ConfigHatasi("config override sozluk olmali")
    sonuc = dict(taban or {})
    for anahtar, deger in (ezme or {}).items():
        if isinstance(deger, dict) and isinstance(sonuc.get(anahtar), dict):
            sonuc[anahtar] = _deep_merge(sonuc[anahtar], deger)
        else:
            sonuc[anahtar] = deger
    return sonuc


def _mapping(deger, ad: str) -> dict:
    if deger is None:
        return {}
    if not isinstance(deger, Mapping):
        raise ConfigHatasi(f"{ad} sozluk olmali")
    return dict(deger)


def _config_dogrula(cfg) -> dict:
    cfg = _mapping(cfg, "config")
    _mapping(cfg.get("secim"), "secim")
    _mapping(cfg.get("okuma"), "okuma")
    return cfg


def _secim_ayari(cfg: dict, girdi: Girdi) -> tuple[dict, str]:
    s_cfg = _deep_merge(_mapping(cfg.get("secim"), "secim"),
                        _mapping(girdi.config.get("secim"), "Girdi.config.secim"))
    ortak = {k: v for k, v in s_cfg.items()
             if k not in {*BOLUMLER, "desen"}}
    bolum_ayari = _mapping(s_cfg.get(girdi.bolum), f"secim.{girdi.bolum}")
    return _deep_merge(ortak, bolum_ayari), s_cfg.get("desen", "*.png")


def _okuma_karari(ayar: dict) -> tuple[dict, dict]:
    """`auto` modunu olculmus kalite raporuna gore somut moda cevir.

    Rapor yok/bozuksa guvenli fallback Free OCR'dir. Grounded moda ancak
    rapor acikca kalite kapisini gecen bir token tavani onerirse girilir.
    """
    sonuc = dict(ayar or {})
    istenen = str(sonuc.get("mod", "grounded")).strip().lower()
    tani = {"istenen": istenen}
    if istenen != "auto":
        tani |= {"secilen": istenen, "sebep": "config"}
        return sonuc, tani
    rapor_yolu = Path(str(sonuc.get(
        "kalite_raporu", "raporlar/grounding_pareto.json")))
    if not rapor_yolu.is_absolute():
        rapor_yolu = KULE / rapor_yolu
    try:
        belge = json.loads(rapor_yolu.read_text(encoding="utf-8"))
        oneri = belge["recommendation"]
        mod = str(oneri["mode"]).strip().lower()
        if mod not in {"grounded", "free_ocr"}:
            raise ValueError(f"gecersiz recommendation.mode: {mod!r}")
        sonuc["mod"] = mod
        if oneri.get("max_new_tokens") is not None:
            sonuc["max_new_tokens"] = int(oneri["max_new_tokens"])
        tani |= {"secilen": mod, "sebep": "kalite_raporu",
                 "rapor": str(rapor_yolu),
                 "max_new_tokens": sonuc.get("max_new_tokens")}
    except Exception as exc:
        sonuc["mod"] = "free_ocr"
        sonuc["max_new_tokens"] = 2048
        tani |= {"secilen": "free_ocr", "sebep": "rapor_yok_veya_bozuk",
                 "rapor": str(rapor_yolu),
                 "hata": f"{type(exc).__name__}: {exc}"[:300]}
    return sonuc, tani


def _surum() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(KULE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return f"nash@{sha}" if sha else "nash@?"
    except Exception:
        return "nash@?"


def okuyucu_kur(cfg: dict):
    """Modeli BİR KEZ yükle → `sor(png) -> str`. Toplu koşuda tek çağrılır.

    Faz 1'de src/model.py henüz YOK — bu bilerek görünür bir eksiktir. Kule
    tahmin etmez: model katmanı kurulmadan çağrılırsa ARIZA(MODEL) döner ve
    diske yazılır (Kobe'nin `--bolum giris` deseni).
    """
    import model  # noqa: F401  — Faz 2
    return model.yukle(cfg.get("okuma", {}), KULE)


def tek(girdi: Girdi, kok: Path | None = None, sor=None,
        cfg: dict | None = None, detector=None) -> Cikti:
    """Bir film → bir Cikti. İstisna sızdırmaz; her yolda diske yazar."""
    import secim as secim_mod
    kok = Path(kok) if kok else OUT
    t0 = time.time()
    proof_context = {"selected": [], "accepted": [], "rejected": [],
                     "grounding": {}, "grounding_failures": [],
                     "mode": "grounded"}

    # Eski başarılı işaret yeni seçim/detector/model çalışmasından önce yoktur.
    # Böylece eşzamanlı tüketici eski ürünü yeni koşunun sonucu sanamaz.
    tamam_isaretini_kaldir(kok, girdi.film_id, girdi.bolum)

    def _bitir(c: Cikti) -> Cikti:
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        extras = {}
        if os.environ.get("MITAS_OKUMA_V2", "").lower() in {"1", "true", "yes"}:
            from proof import build_packet, fallback_packet
            try:
                extras["nash.okuma.json"] = build_packet(
                    film_id=girdi.film_id, section=girdi.bolum, legacy=c.sozluk(),
                    selected_paths=proof_context["selected"],
                    accepted=proof_context["accepted"],
                    rejected=proof_context["rejected"],
                    grounding=proof_context["grounding"],
                    grounding_failures=proof_context["grounding_failures"])
            except Exception as e:  # proof, birincil Free OCR sonucunu yok edemez
                extras["nash.okuma.json"] = fallback_packet(
                    girdi.film_id, girdi.bolum, c.sozluk(), e)
        c.yaz(kok, extras)
        return c

    def _ariza(sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
        return _bitir(ariza(girdi.film_id, sinif, mesaj[:300], kanit,
                            bolum=girdi.bolum))

    if cfg is None:
        try:
            cfg = _config()
        except ConfigHatasi as exc:
            return _ariza("YAPILANDIRMA", str(exc))

    try:
        cfg = _config_dogrula(cfg)
        ayar, desen = _secim_ayari(cfg, girdi)
    except ConfigHatasi as exc:
        return _ariza("YAPILANDIRMA", str(exc))

    try:
        s = secim_mod.sec(Path(girdi.kareler), ayar, desen, detector=detector)
    except Exception as e:  # noqa: BLE001 — secim cokerse bu bir ARIZA'dir
        return _ariza("GIRDI_HATASI", f"{type(e).__name__}: {e}")

    if s.hata:
        durum, sinif = _HATA_HARITA[s.hata]
        if durum == "ARIZA":
            mesaj = _HATA_MESAJ[s.hata]
            if s.hata == "detector_ariza" and s.kanit.get("detector_hata"):
                mesaj += f": {s.kanit['detector_hata']}"
            return _ariza(sinif, mesaj, s.kanit)
        return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                            durum="METIN_YOK", kanit=s.kanit))

    proof_context["selected"] = list(s.yollar)

    # ── okuma ────────────────────────────────────────────────────────────────
    import okuyucu as ok_mod
    try:
        o_cfg = _deep_merge(_mapping(cfg.get("okuma"), "okuma"),
                            _mapping(girdi.config.get("okuma"),
                                     "Girdi.config.okuma"))
    except ConfigHatasi as exc:
        return _ariza("YAPILANDIRMA", str(exc), s.kanit)
    o_cfg, okuma_karari = _okuma_karari(o_cfg)
    okuma_modu = str(o_cfg.get("mod", "grounded")).strip().lower()
    proof_context["mode"] = okuma_modu
    dedup_esigi = float(o_cfg.get("dedup_esigi", 0.92))
    model_yollari = list(s.yollar)
    okuma_yollari = list(s.yollar)
    paddle_satirlari: list[dict] = []
    paddle_kanit: dict = {}

    if okuma_modu == "hybrid":
        import hibrit as hibrit_mod
        try:
            hibrit_ayar = {**o_cfg, "bolum": girdi.bolum}
            # Paddle ucuz katmandir: temporal uzlasmanin gercekten calisabilmesi
            # icin yalniz text-run temsilcilerini degil, worker'in basariyla
            # taradigi ana havuzun tamamini okuruz. DeepSeek yine sadece
            # `s.yollar` icinden secilebilen sinirli fallback karelerini gorur.
            okuma_yollari = [
                p for p in sorted(Path(girdi.kareler).glob(desen))
                if p.name in s.analizler
                and not (s.analizler.get(p.name) or {}).get("error")
            ]
            (paddle_satirlari, paddle_kanit, model_yollari,
             paddle_grounding) = hibrit_mod.paddle_oku(
                okuma_yollari, s.analizler, hibrit_ayar, dedup_esigi,
                fallback_yollari=s.yollar)
            proof_context["grounding"] = paddle_grounding

            # Latin tanıyıcı düşük güvenliyse Arabic, yalnız o kabul edilmezse
            # ESlav denenir. Script kabulü bütün Latin sonucu körlemesine
            # silmez; ayrı bbox'taki güçlü/tekrarlı çift-dilli satırı korur.
            script_cfg = o_cfg.get("paddle_script_fallback") or {}
            script_tetik = int(script_cfg.get("trigger_below_lines", 8))
            script_medyan = paddle_kanit.get("paddle_skor_medyan")
            script_medyan_esik = float(script_cfg.get(
                "trigger_below_median", 0.80))
            script_tetiklendi = (
                len(paddle_satirlari) < script_tetik
                or (script_medyan is not None
                    and float(script_medyan) < script_medyan_esik))
            if bool(script_cfg.get("enabled", False)) and script_tetiklendi:
                import metin_secici
                birincil_satirlar = list(paddle_satirlari)
                birincil_grounding = dict(proof_context["grounding"])
                gereken = (max(2, len(birincil_satirlar))
                           if len(birincil_satirlar) < script_tetik
                           else max(8, math.ceil(len(birincil_satirlar) * 0.5)))
                denemeler = []
                kabul_edilen = None
                routes = script_cfg.get("routes") or [script_cfg]
                for route in routes:
                    script = str(route.get("script", "arabic"))
                    try:
                        alt_detector_cfg = _deep_merge(
                            ayar.get("detector") or {}, script_cfg)
                        alt_detector_cfg = _deep_merge(alt_detector_cfg, route)
                        alt_analizler, alt_worker_kanit = metin_secici.tara(
                            okuma_yollari, alt_detector_cfg)
                        (alt_satirlar, alt_kanit, _alt_model_yollari,
                         alt_grounding) = hibrit_mod.paddle_oku(
                            okuma_yollari, alt_analizler, hibrit_ayar,
                            dedup_esigi, fallback_yollari=s.yollar)
                        alt_ham_satirlar = list(alt_satirlar)
                        (alt_satirlar, alt_grounding,
                         script_secim_kanit) = hibrit_mod.script_satirlarini_sec(
                            alt_satirlar, alt_grounding, script=script,
                            min_oran=float(script_cfg.get(
                                "min_script_ratio", 0.35)))
                        nitelikli = len(alt_satirlar) >= gereken
                        deneme = {
                            **script_secim_kanit, "gereken_satir_n": gereken,
                            "nitelikli": nitelikli, "worker": alt_worker_kanit,
                            "okuma": alt_kanit,
                        }
                        denemeler.append(deneme)
                        if not nitelikli:
                            continue
                        (paddle_satirlari, birlesik_grounding,
                         birlesim_tani) = hibrit_mod.script_birlestir(
                            birincil_satirlar, birincil_grounding,
                            alt_satirlar, alt_grounding,
                            latin_min_score=float(script_cfg.get(
                                "latin_preserve_min_score", 0.90)),
                            latin_min_support=int(script_cfg.get(
                                "latin_preserve_min_support", 2)),
                            overlap_iou=float(script_cfg.get(
                                "latin_overlap_iou", 0.30)),
                            script_ham_satirlari=alt_ham_satirlar,
                            latin_corroboration_similarity=float(
                                script_cfg.get(
                                    "latin_corroboration_similarity", 0.82)),
                            target_script=script)
                        proof_context["grounding"] = birlesik_grounding
                        kabul_edilen = {"script": script, **birlesim_tani}
                        break
                    except Exception as exc:
                        denemeler.append({
                            "script": script, "nitelikli": False,
                            "hata": f"{type(exc).__name__}: {exc}"[:300],
                        })
                paddle_kanit["paddle_script_fallback"] = {
                    "tetiklendi": True,
                    "tetik": {"satir_n": len(birincil_satirlar),
                              "satir_esigi": script_tetik,
                              "skor_medyan": script_medyan,
                              "skor_esigi": script_medyan_esik},
                    "denemeler": denemeler,
                    "kabul": kabul_edilen,
                }
                if kabul_edilen is not None:
                    model_yollari = []
            else:
                paddle_kanit["paddle_script_fallback"] = {
                    "tetiklendi": False,
                    "tetik": {"satir_n": len(paddle_satirlari),
                              "satir_esigi": script_tetik,
                              "skor_medyan": script_medyan,
                              "skor_esigi": script_medyan_esik},
                    "denemeler": [], "kabul": None,
                }
        except Exception as exc:
            return _ariza("MODEL", f"Paddle hibrit okuma: {type(exc).__name__}: {exc}",
                          s.kanit)
    elif okuma_modu not in {"grounded", "free_ocr"}:
        return _ariza("YAPILANDIRMA", f"bilinmeyen okuma.mod: {okuma_modu!r}",
                      s.kanit)

    model_gerekli = okuma_modu != "hybrid" or bool(model_yollari)
    model_kurulum_hatasi = None
    if sor is None and model_gerekli:
        try:
            sor = okuyucu_kur(_deep_merge(cfg, {"okuma": o_cfg}))
        except ok_mod.Bellek as e:
            model_kurulum_hatasi = ("BELLEK", f"model yuklenirken OOM: {e}")
        except ok_mod.ModelYok as e:
            model_kurulum_hatasi = ("MODEL", str(e))
        except ImportError as e:
            model_kurulum_hatasi = (
                "MODEL", f"model katmani kurulmadi (Faz 2 bekliyor): {e}")
        except Exception as e:  # noqa: BLE001
            model_kurulum_hatasi = ("MODEL", f"{type(e).__name__}: {e}")

    if model_kurulum_hatasi:
        if okuma_modu != "hybrid" or not paddle_satirlari:
            return _ariza(model_kurulum_hatasi[0], model_kurulum_hatasi[1],
                          {**s.kanit, **paddle_kanit})
        paddle_kanit["deepseek_fallback_hatasi"] = model_kurulum_hatasi[1]
        proof_context["grounding_failures"].append({
            "scope": "deepseek_fallback",
            "error": model_kurulum_hatasi[1][:300],
        })
        model_yollari = []
        sor = None

    # Grounded cevap hem satiri hem bbox kanitini uretir. Hybrid'de bu yalniz
    # Paddle'in belirsiz buldugu sinirli karelere uygulanir.
    okuma_sor = sor
    if sor is not None and okuma_modu in {"grounded", "hybrid"}:
        from proof import (GROUNDING_PROMPT, grounding_bicimi_var,
                           grounding_lines, parse_grounding)

        def _grounded_sor(path: Path) -> str:
            try:
                ham = sor(path, GROUNDING_PROMPT)
                ogeler = grounding_lines(parse_grounding(ham))
                for oge in ogeler:
                    oge["label"] = ok_mod._kirp(oge["label"])
                    oge["engine"] = "deepseek"
                ogeler = [oge for oge in ogeler if oge["label"]]
                proof_context["grounding"].setdefault(path.name, []).extend(ogeler)
                if ogeler:
                    return "\n".join(o["label"] for o in ogeler)
                if grounding_bicimi_var(ham):
                    # `image` gibi metin olmayan gecerli bolge: basarili bos.
                    return ""
                if (ham or "").strip():
                    # Model nadiren bbox isaretleri olmadan duz OCR donduruyor.
                    # Metni kaybetme; packet'ta evidence bos kalir ve durum
                    # acikca PARTIAL/NONE olur, kanit uydurulmaz.
                    proof_context["grounding_failures"].append({
                        "asset": path.name,
                        "error": "grounding bicimi yok; metin bbox'siz korundu",
                    })
                return ham or ""
            except (ok_mod.Bellek, ok_mod.ModelYok):
                raise
            except Exception as exc:  # sayfa hatasi okuyucu tarafindan sayilir
                proof_context["grounding_failures"].append({
                    "asset": path.name,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                })
                proof_context["grounding"].setdefault(path.name, [])
                raise

        okuma_sor = _grounded_sor

    deepseek_satirlari: list[dict] = []
    deepseek_kanit: dict = {}
    if model_yollari and okuma_sor is not None:
        try:
            deepseek_satirlari, deepseek_kanit = ok_mod.oku(
                model_yollari, okuma_sor, dedup_esigi)
        except ok_mod.Bellek as exc:
            if okuma_modu != "hybrid" or not paddle_satirlari:
                return _ariza("BELLEK", f"CUDA OOM — caresi parca kucultmek: {exc}",
                              {**s.kanit, **paddle_kanit})
            paddle_kanit["deepseek_fallback_hatasi"] = f"Bellek: {exc}"[:300]
        except ok_mod.ModelYok as exc:
            if okuma_modu != "hybrid" or not paddle_satirlari:
                return _ariza("MODEL", str(exc), {**s.kanit, **paddle_kanit})
            paddle_kanit["deepseek_fallback_hatasi"] = str(exc)[:300]
        except Exception as exc:  # noqa: BLE001
            if okuma_modu != "hybrid" or not paddle_satirlari:
                return _ariza("MODEL", f"{type(exc).__name__}: {exc}",
                              {**s.kanit, **paddle_kanit})
            paddle_kanit["deepseek_fallback_hatasi"] = (
                f"{type(exc).__name__}: {exc}"[:300])

    if okuma_modu == "hybrid":
        satirlar, birlesim_kanit = hibrit_mod.birlestir(
            paddle_satirlari, deepseek_satirlari, okuma_yollari)
        o_kanit = {**paddle_kanit, **birlesim_kanit}
        for anahtar, deger in deepseek_kanit.items():
            o_kanit[f"deepseek_{anahtar}"] = deger
    else:
        satirlar, o_kanit = deepseek_satirlari, deepseek_kanit

    proof_context["accepted"] = list(satirlar)
    proof_context["rejected"] = list(o_kanit.get("elenen") or [])
    if okuma_modu == "hybrid":
        # Kanit paketine yuzlerce tarama karesi koyma. Paddle/DeepSeek'in
        # gercekten kaynak gosterdigi kareler ile agir model fallback girdileri
        # yeterlidir; sema ayni kalir, paket kucuk ve denetlenebilir olur.
        kaynaklar = {str(row.get("kaynak", "")) for row in satirlar}
        kaynaklar.update(p.name for p in model_yollari)
        proof_context["selected"] = [
            p for p in okuma_yollari if p.name in kaynaklar
        ] or list(s.yollar)
    if (okuma_modu == "free_ocr"
            and os.environ.get("MITAS_OKUMA_V2", "").lower() in {"1", "true", "yes"}):
        from proof import ground_pages
        kabul_kaynaklari = {str(row.get("kaynak", "")) for row in satirlar}
        hedefler = [p for p in s.yollar if p.name in kabul_kaynaklari]
        proof_context["grounding"], proof_context["grounding_failures"] = ground_pages(
            hedefler, sor)

    kanit = {**s.kanit, **o_kanit}
    kanit["okuma_modu"] = okuma_modu
    kanit["okuma_karari"] = okuma_karari
    olcum = getattr(sor, "metrics", None) if sor is not None else None
    if callable(olcum):
        try:
            kanit["model_olcum"] = olcum()
        except Exception as exc:  # tani sonucu birincil okumayi bozamaz
            kanit["model_olcum_hatasi"] = f"{type(exc).__name__}: {exc}"[:300]
    if not satirlar:
        # Tum model cagrilari patladiysa bu icerik gercegi DEGILDIR. Eski kod
        # bu yolu METIN_YOK yapip sessiz ariza uretiyordu.
        tum_model_cagrilari_hata = (
            int(o_kanit.get("sayfa_hata_n", 0))
            and int(o_kanit.get("sayfa_basarili_n", 0)) == 0)
        if okuma_modu == "hybrid" and model_yollari:
            tum_model_cagrilari_hata = (
                int(o_kanit.get("deepseek_sayfa_hata_n", 0))
                and int(o_kanit.get("deepseek_sayfa_basarili_n", 0)) == 0)
        if tum_model_cagrilari_hata:
            return _ariza("MODEL", "tum secili karelerin okuma cagrisi basarisiz",
                          kanit)
        if (okuma_modu == "hybrid"
                and int(kanit.get(
                    "deepseek_fallback_config_kapatti_dusuk_guven_n", 0))):
            return _ariza("CIKTI_BOZUK",
                          "dusuk guvenli OCR adayi DeepSeek fallback kapaliyken cozulemedi",
                          kanit)
        return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                            durum="METIN_YOK", kanit=kanit))

    _, sebep = ok_mod.saglik([s["text"] for s in satirlar], o_cfg.get("saglik"))
    kanit["saglik"] = sebep
    # SAGLIK BIR BAYRAKTIR, HUKUM DEGIL — uretimde de oyle
    # (_pipe_track_kunye manifest'e yazar, icerigi korur). Tek istisna:
    #
    #   garble_yuksek → ARIZA(CIKTI_BOZUK). Cunku elimizdeki metin YANLIS;
    #     asagi akisa birakmak kunyeyi zehirler (rodeo vakasi: iki kol da
    #     coktugu icin "Kubrick/Godfather" uydurmalari kunyeye girdi).
    #   cok_kisa → YALNIZ kanita yazilir. Kisa olmasi yanlis olmasi demek
    #     degildir; 5 satirlik gercek bir jenerik ARIZA'ya cevrilirse icerik
    #     gercegi arizaya kurban gider — sozlesmenin yasakladigi seyin aynasi.
    if sebep == "garble_yuksek":
        return _ariza("CIKTI_BOZUK",
                      "okuma garble: alfanumerik oran esigin altinda", kanit)

    return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                        durum="OKUNDU", satirlar=satirlar, kanit=kanit))


def toplu(girdi_dizini: Path, kok: Path | None = None,
          bolum: str = "cikis") -> list[Cikti]:
    """Her kare dizinini işle; `_TAMAM` olanı atla. Model BİR KEZ yüklenir."""
    kok = Path(kok) if kok else OUT
    ogeler = sorted(p for p in Path(girdi_dizini).iterdir() if p.is_dir())
    bekleyen = [p for p in ogeler if not (kok / p.name / bolum / "_TAMAM").exists()]
    for p in ogeler:
        if p not in bekleyen:
            print(f"[atla] {p.name}")

    try:
        cfg = _config()
        cfg = _config_dogrula(cfg)
    except ConfigHatasi as exc:
        sonuc = []
        for p in bekleyen:
            c = ariza(p.name, "YAPILANDIRMA", str(exc), bolum=bolum)
            c.yaz(kok)
            sonuc.append(c)
            print(f"[ARIZA] {p.name} sinif=YAPILANDIRMA")
        return sonuc

    # Toplu yolda eski sira model -> detector idi; boylece Paddle ve Torch ayni
    # anda VRAM tutuyordu. Tum full-OCR isleri once kendi alt sureclerinde
    # tamamlanir; DeepSeek ilk gercek fallback gelirse tembel ve bir kez yuklenir.
    detector_sonuclari: dict[str, object] = {}
    for p in bekleyen:
        g = Girdi(film_id=p.name, kareler=str(p), bolum=bolum)
        try:
            secim_ayari, desen = _secim_ayari(cfg, g)
        except ConfigHatasi as exc:
            c = ariza(p.name, "YAPILANDIRMA", str(exc), bolum=bolum)
            c.yaz(kok)
            sonuc = [c]
            # Kalan filmler de tek tek görünür ARIZA almalıdır.
            for kalan in bekleyen[bekleyen.index(p) + 1:]:
                cc = ariza(kalan.name, "YAPILANDIRMA", str(exc), bolum=bolum)
                cc.yaz(kok)
                sonuc.append(cc)
            return sonuc
        if str(secim_ayari.get("strateji", "legacy")).lower() != "text_run":
            continue
        try:
            import metin_secici
            detector_sonuclari[p.name] = metin_secici.tara(
                sorted(p.glob(desen)), secim_ayari.get("detector") or {})
        except Exception as exc:  # sec() bunu detector_ariza olarak gorur
            detector_sonuclari[p.name] = exc

    toplu_o_cfg, _ = _okuma_karari(cfg.get("okuma") or {})
    cfg = _deep_merge(cfg, {"okuma": toplu_o_cfg})
    sor = None
    if bekleyen and str(toplu_o_cfg.get("mod", "grounded")).lower() == "hybrid":
        # Paddle tum filmleri ucuz worker'larda tarar. DeepSeek nesnesi ancak
        # bir filmin temporal uzlasmasi gercekten fallback isterse kurulur ve
        # sonraki filmlerde ayni nesne kullanilir.
        sor = _TembelOkuyucu(lambda: okuyucu_kur(cfg))
    elif bekleyen:
        try:
            sor = okuyucu_kur(cfg)
        except Exception as e:  # noqa: BLE001 — ayni hata her filme yazilacak
            print(f"[!] okuyucu kurulamadi: {type(e).__name__}: {e}")

            def _kurulum_hatasi(*_args, _hata=e, **_kwargs):
                raise _hata

            sor = _kurulum_hatasi

    sonuc = []
    for p in bekleyen:
        detector = None
        if p.name in detector_sonuclari:
            hazir = detector_sonuclari[p.name]

            def _hazir_detector(_yollar, _ayar, _hazir=hazir):
                if isinstance(_hazir, Exception):
                    raise _hazir
                return _hazir

            detector = _hazir_detector
        c = tek(Girdi(film_id=p.name, kareler=str(p), bolum=bolum), kok, sor, cfg,
                detector=detector)
        sonuc.append(c)
        n = len(c.satirlar)
        ek = f" sinif={c.sinif}" if c.durum == "ARIZA" else ""
        print(f"[{c.durum}] {p.name} satir={n} sure={c.sure_sn}s{ek}")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="nash",
                                 description="ham kare havuzundan jenerik okuma")
    alt = ap.add_subparsers(dest="komut", required=True)
    BOLUM_YRD = "cikis = kapanis jenerigi (varsayilan) | giris = giris jenerigi"

    a = alt.add_parser("start", help="toplu: girdi yolundaki her kare dizinini isle")
    a.add_argument("--input", required=True)
    a.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    a.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")

    b = alt.add_parser("tek", help="tek film")
    b.add_argument("--kareler", required=True)
    b.add_argument("--film-id", required=True)
    b.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    b.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")

    n = ap.parse_args(argv)
    kok = Path(n.out) if n.out else None
    if n.komut == "start":
        try:
            sonuclar = toplu(Path(n.input), kok=kok, bolum=n.bolum)
        except Exception as exc:  # girdi koku dahi okunamiyorsa gorunur CLI hatasi
            print(f"ARIZA: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        return 2 if any(c.durum == "ARIZA" for c in sonuclar) else 0
    try:
        g = Girdi(film_id=n.film_id, kareler=n.kareler, bolum=n.bolum)
    except GirdiHatasi as e:
        print(json.dumps({"durum": "ARIZA", "sinif": "GIRDI_HATASI",
                          "mesaj": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    c = tek(g, kok=kok)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
