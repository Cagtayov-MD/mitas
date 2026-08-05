# -*- coding: utf-8 -*-
"""retry_planner.py — RETRY yeniden-tasarımı saf çekirdeği (İP-7, 2026-07-11, plan rev.4).

NEDEN: eski /retry ÇİFT-BOZUKTU (kanıtlı): (1) worker force=true → GERÇEK hub'ı rmtree'liyordu —
BAŞKAN VE MARI veri-kaybının tam kaynağı (07-06 force-rerun hub'ı sildi, golden 3/3-FAIL); (2)
force'suz requeue → reused-skip sessiz no-op (48 ASR-failed hiç gerçek-retry görmedi). Watchdog
oto-retry fiilen işlevsizdi.

SÖZLEŞME (şartname + qwen/GLM İP6/7-turu):
  • retry HİÇBİR canonical hub'ı SİLMEZ/mutate etmez — koşu candidate-root'ta (MITAS_RUN_ROOT),
    insan promote_hub.py ile taşır. delete_existing kavramı YOK.
  • stage: OCR|ASR|SUMMARY|RENDER|FULL. v1 canlı-yol = FULL candidate-run (mitas_pipeline --run-root);
    stage-özel runner'lar (OCR-only vb.) DAG'a bağlı, aşamalı açılır.
  • Invalidation DAG: bir stage promote edilince downstream 'bayat' işaretlenir (LAZY yeniden-hesap)
    AMA backlog=0 pusulasıyla çelişmesin diye pending_recompute[] BACKLOG'a girer (GLM/qwen ortak).
  • Circuit-breaker: node-başına max invalidation → DLQ-karantina (sonsuz invalidate-retry yok).

Saf modül: FastAPI/thread YOK — asr_server bunu çağırır; testler ağsız doğrular."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

# Linux geçişi 2026-07-16: env varsa onu kullan (Windows'ta env yoksa eski davranış birebir).
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
CANDIDATE_ROOT = PROJECT_ROOT / "candidate_runs"
TRT_RE = re.compile(r"\d{4}-\d{3,4}-\d-\d{3,4}-\d{2}-\d")

STAGES = ("OCR", "ASR", "SUMMARY", "RENDER", "FULL")

# Bir stage yeniden koşulup promote edilince BAYAT olan downstream artefakt/kararlar (LAZY).
STAGE_DOWNSTREAM = {
    "OCR":     ["credit", "validation", "pdf", "qc", "karar"],
    "ASR":     ["summary", "pdf", "qc"],
    "SUMMARY": ["pdf", "qc"],
    "RENDER":  ["pdf", "qc", "karar"],
    "FULL":    [],   # FULL zaten her şeyi yeniden üretir → downstream-bayat yok
}

MAX_INVALIDATION = 3        # node-başına; aşımda DLQ-karantina (circuit-breaker)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


class RetryError(RuntimeError):
    pass


# ─────────────────────────── resolver ───────────────────────────
def trt_of(video_or_name: str) -> str | None:
    m = TRT_RE.search(_nfc(Path(str(video_or_name)).stem))
    return m.group(0) if m else None


def resolve_hub(video_or_trt: str, db_root: Path) -> Path | None:
    """0=NOT_FOUND(None) / 1=OK / >1=AMBIGUOUS_HUB hard-fail (promote_hub ile AYNI sözleşme, NFC)."""
    trt = trt_of(video_or_trt) or _nfc(video_or_trt).strip()
    hits = [d for d in db_root.iterdir()
            if d.is_dir() and trt in _nfc(d.name) and (d / "_DURUM.json").exists()]
    if len(hits) > 1:
        raise RetryError(f"AMBIGUOUS_HUB: {trt} → {len(hits)} kopya {[h.name for h in hits]} — "
                         f"önce dedup (ADI CARMEN prosedürü)")
    return hits[0] if hits else None


# ─────────────────────────── candidate koşu planı ───────────────────────────
def make_run_id(stage: str, seed: str) -> str:
    """Deterministik run_id (Math.random yok): stage+seed+kısa-hash. seed = ts/video (çağıran verir)."""
    import hashlib
    h = hashlib.sha256(f"{stage}:{seed}".encode("utf-8")).hexdigest()[:10]
    return f"retry_{stage.lower()}_{h}"


def plan_retry(video_path: str, stage: str, *, seed: str, db_root: Path) -> dict:
    """Retry planı üret (subprocess'i ÇAĞIRAN koşar). SİLME/MUTATE YOK — candidate-root'a yazar."""
    stage = (stage or "FULL").upper()
    if stage not in STAGES:
        raise RetryError(f"geçersiz stage: {stage} (izinli: {STAGES})")
    hub = resolve_hub(video_path, db_root)      # AMBIGUOUS_HUB burada hard-fail
    run_id = make_run_id(stage, seed)
    run_root = CANDIDATE_ROOT / run_id
    plan = {
        "stage": stage, "run_id": run_id, "run_root": str(run_root),
        "canonical_hub": str(hub) if hub else None,
        "delete_existing": False,               # SÖZLEŞME: retry hiçbir şey silmez
        "candidate_run": True,
    }
    if stage == "FULL":
        plan["cmd"] = ["--video", video_path, "--profile", "film_dizi",
                       "--no-copy-source", "--run-root", str(run_root)]
        plan["runner"] = "mitas_pipeline"
    else:
        # Stage-özel runner'lar (OCR-only vb.): frames'i candidate'a KOPYALAMADAN referansla
        # (GLM: junction/hardlink daha güvenli — asr_server tarafında mklink /J ile bağlanır).
        # v1: canonical frames var mı kontrol; runner asr_server'da stage'e göre seçilir.
        if hub is None:
            raise RetryError(f"stage={stage} retry için canonical hub gerekli ama bulunamadı: {video_path}")
        plan["cmd"] = None
        plan["runner"] = f"stage:{stage}"
        plan["frames_ref"] = str(hub / "frames")
        plan["note"] = "stage-özel runner asr_server'da; frames junction ile bağlanır (kopyasız)"
    return plan


def retry_env(base_env: dict, run_root: str) -> dict:
    """Subprocess env: MITAS_RUN_ROOT set → pipeline candidate moda geçer (üretim köklerine YAZMAZ).
    Çocuk-köprüsü env'leri temizlenir ki mitas_roots.export_child_env taze kursun."""
    e = dict(base_env)
    e["MITAS_RUN_ROOT"] = str(run_root)
    for k in ("MITAS_WEB_CACHE_DIR", "MITAS_OUTPUTS_DIR", "MITAS_MANIFEST_DIR"):
        e.pop(k, None)
    return e


# ─────────────────────────── invalidation DAG + backlog ───────────────────────────
def mark_stale_downstream(canonical_hub: Path, stage: str) -> list[str]:
    """Promote SONRASI çağrılır: karar.pipeline.json'a stale_downstream + backlog.pending_recompute.
    LAZY (yeniden-hesap sonraki FULL/insan-tetikli) ama backlog'da GÖRÜNÜR (pusula çelişmez)."""
    downstream = STAGE_DOWNSTREAM.get((stage or "").upper(), [])
    kp = canonical_hub / "karar.pipeline.json"
    obj = {}
    if kp.exists():
        try:
            obj = json.loads(kp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            obj = {}
    obj["stale_downstream"] = sorted(set(obj.get("stale_downstream") or []) | set(downstream))
    obj["stale_marked_at"] = datetime.now().isoformat(timespec="seconds")
    tmp = kp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(kp))
    return downstream


def bump_invalidation(counter_path: Path, key: str) -> dict:
    """Circuit-breaker: key (trt+stage) invalidation sayacı. max aşımı → DLQ-karantina.
    Döner: {count, dlq: bool}. Sonsuz invalidate-retry imkânsız."""
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if counter_path.exists():
        try:
            data = json.loads(counter_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
    n = int(data.get(key, 0)) + 1
    data[key] = n
    dlq = n > MAX_INVALIDATION
    if dlq:
        data.setdefault("_dlq", [])
        if key not in data["_dlq"]:
            data["_dlq"].append(key)
    tmp = counter_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(counter_path))
    return {"count": n, "dlq": dlq}


# ─────────────────────────── zombie/heartbeat timeout ───────────────────────────
# GLM: sabit 4h yerine progress-heartbeat. asr_server heartbeat_ts'i günceller; aşım = zombie.
STAGE_TIMEOUT_SN = {"FULL": 14400, "OCR": 1800, "ASR": 5400, "SUMMARY": 1800, "RENDER": 900}


def is_zombie(last_heartbeat_ts: float, now_ts: float, stage: str,
              idle_limit_sn: float = 900.0) -> bool:
    """Progress-heartbeat idle > idle_limit → zombie (yavaş-diskte false-kill'i önler; sabit-süre
    değil ilerleme-esaslı). Çağıran now_ts verir (Date.now yok)."""
    return (now_ts - last_heartbeat_ts) > idle_limit_sn
