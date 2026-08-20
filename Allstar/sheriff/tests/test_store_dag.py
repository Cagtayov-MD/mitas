from __future__ import annotations

from src.config import load_config
from src.engine import Engine
from src.store import Store

DAG = load_config().raw["dag"]


def create_run(store: Store):
    return store.enqueue(film_id="film", title="Film", source_path="/tmp/film.mp4",
                         source_sha256="a" * 64, pipeline_version="test/v1",
                         max_attempts=2, dag=DAG)


def test_enqueue_idempotent_ve_force_yeni_run(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    first, created = create_run(store)
    same, second_created = create_run(store)
    assert created and not second_created and same == first
    forced, forced_created = store.enqueue(
        film_id="film", title="Film", source_path="/tmp/film.mp4",
        source_sha256="a" * 64, pipeline_version="test/v1", max_attempts=2,
        dag=DAG, force=True)
    assert forced_created and forced != first
    assert len(store.tasks(first)) == 13


def test_ayni_hash_farkli_film_id_yanlis_run_dondurmez(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    first, _ = create_run(store)
    second, created = store.enqueue(
        film_id="baska-film", title=None, source_path="/tmp/film.mp4",
        source_sha256="a" * 64, pipeline_version="test/v1", max_attempts=2,
        dag=DAG)
    assert created and second != first
    assert store.get_run(second)["film_id"] == "baska-film"


def test_dag_kule_rolleri_koda_gomulu_degil_configden_olusturulur(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    dag = {**DAG, "boundary_role": "sinir_yedek",
           "independent_reader_role": "ham_okuyucu_yedek",
           "boundary_frame_reader_role": "master_okuyucu_yedek",
           "boundary_video_reader_role": "video_okuyucu_yedek"}
    run_id, created = store.enqueue(
        film_id="film", title=None, source_path="/tmp/film.mp4",
        source_sha256="d" * 64, pipeline_version="test/configurable",
        max_attempts=2, dag=dag)
    assert created
    roles = {task["logical_role"] for task in store.tasks(run_id)
             if task["kind"] == "tower"}
    assert roles == {"sinir_yedek", "ham_okuyucu_yedek",
                     "master_okuyucu_yedek", "video_okuyucu_yedek"}


def test_kobe_no_content_bagimli_okuyuculari_acmaz_nash_bagimsizdir(tmp_path,
                                                                   monkeypatch):
    monkeypatch.setenv("SHERIFF_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("SHERIFF_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("SHERIFF_LOG_DIR", str(tmp_path / "logs"))
    cfg = load_config()
    store = Store(cfg.db_path)
    run_id, _ = store.enqueue(film_id="film", title=None, source_path="/tmp/x.mp4",
                              source_sha256="b" * 64, pipeline_version=cfg.pipeline_version,
                              max_attempts=2, dag=cfg.raw["dag"])
    media = next(t for t in store.tasks(run_id) if t["kind"] == "media_prep")
    store.set_status(media["task_id"], "SUCCEEDED", result={})
    engine = Engine(cfg, store)
    engine.reconcile()
    section = [t for t in store.tasks(run_id) if t["section"] == "giris"]
    boundary = next(t for t in section if t.get("logical_role") == "boundary")
    nash = next(t for t in section if t.get("logical_role") == "reader_frame")
    assert boundary["status"] == "READY" and nash["status"] == "READY"
    store.set_status(boundary["task_id"], "NO_CONTENT", result={"durum": "KREDI_YOK"})
    engine.reconcile()
    section = [t for t in store.tasks(run_id) if t["section"] == "giris"]
    assert next(t for t in section if t.get("logical_role") == "reader_master")["status"] == "NO_CONTENT"
    assert next(t for t in section if t.get("logical_role") == "reader_video")["status"] == "NO_CONTENT"
    assert next(t for t in section if t.get("logical_role") == "reader_frame")["status"] == "READY"


def test_retry_upstream_descendantlari_waiting_yapar(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    run_id, _ = create_run(store)
    tasks = store.tasks(run_id)
    boundary = next(t for t in tasks if t["section"] == "cikis" and
                    t.get("logical_role") == "boundary")
    store.set_status(boundary["task_id"], "FAILED", result={"reason": "x"})
    for task in store.tasks(run_id):
        if task["section"] == "cikis" and task["kind"] != "media_prep":
            if task["task_id"] != boundary["task_id"]:
                store.set_status(task["task_id"], "FAILED", result={"reason": "upstream_failed"})
    assert store.retry("film", "boundary") == 1
    refreshed = store.tasks(run_id)
    assert next(t for t in refreshed if t["task_id"] == boundary["task_id"])["status"] == "READY"
    descendants = [t for t in refreshed if t["section"] == "cikis" and
                   t["task_id"] != boundary["task_id"] and t.get("logical_role") != "reader_frame"]
    assert descendants and all(t["status"] == "WAITING" for t in descendants)


def test_iptal_edilen_gorevli_run_succeeded_olamaz(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    run_id, _ = create_run(store)
    for task in store.tasks(run_id):
        store.set_status(task["task_id"], "CANCELLED")
    assert store.get_run(run_id)["status"] == "CANCELLED"


def test_terminal_gorevin_yetim_kaynak_rezervasyonu_kapanir(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    run_id, _ = create_run(store)
    task = next(item for item in store.tasks(run_id) if item["kind"] == "media_prep")
    store.set_status(task["task_id"], "READY")
    attempt = store.claim(task["task_id"], "owner", "2999-01-01T00:00:00+00:00")
    store.reserve(task["task_id"], "cpu_media", {
        "vram_mb": 0, "ram_mb": 1, "cpu_threads": 1,
        "exclusive_gpu": False, "family": "ffmpeg"})
    store.finish_attempt(task["task_id"], attempt, "SUCCEEDED")
    assert len(store.active_reservations()) == 1
    assert store.release_orphan_reservations() == 1
    assert store.active_reservations() == []


def test_retry_kule_hata_belgesini_kaybetmez(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    run_id, _ = create_run(store)
    task = next(item for item in store.tasks(run_id)
                if item["logical_role"] == "boundary" and item["section"] == "giris")
    store.set_status(task["task_id"], "READY")
    attempt = store.claim(task["task_id"], "owner", "2999-01-01T00:00:00+00:00")
    detail = {"document": {"durum": "ARIZA", "mesaj": "model coktu"}}
    store.retry_or_fail(task["task_id"], attempt, error_class="TOWER",
                        error_message="x", result=detail, retry_delay_seconds=0)
    current = store.task(task["task_id"])
    assert current["result"]["last_result"] == detail


def test_retry_varsayilan_yalniz_en_yeni_run_ve_attempt_no_cakisma_yapmaz(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    old, _ = create_run(store)
    new, _ = store.enqueue(film_id="film", title=None, source_path="/tmp/film.mp4",
                           source_sha256="a" * 64, pipeline_version="test/v1",
                           max_attempts=2, dag=DAG, force=True)
    for run_id in (old, new):
        task = next(t for t in store.tasks(run_id)
                    if t["logical_role"] == "boundary" and t["section"] == "giris")
        store.set_status(task["task_id"], "READY")
        attempt = store.claim(task["task_id"], "owner", "2999-01-01T00:00:00+00:00")
        store.finish_attempt(task["task_id"], attempt, "FAILED")
    assert store.retry("film", "boundary") == 1
    old_task = next(t for t in store.tasks(old)
                    if t["logical_role"] == "boundary" and t["section"] == "giris")
    new_task = next(t for t in store.tasks(new)
                    if t["logical_role"] == "boundary" and t["section"] == "giris")
    assert old_task["status"] == "FAILED"
    second_attempt = store.claim(new_task["task_id"], "owner", "2999-01-01T00:00:00+00:00")
    assert second_attempt


def test_task_claim_edilince_run_aninda_running_olur(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    run_id, _ = create_run(store)
    task = next(t for t in store.tasks(run_id) if t["status"] == "READY")
    attempt = store.claim(task["task_id"], "owner", "2999-01-01T00:00:00+00:00")
    assert attempt
    assert store.get_run(run_id)["status"] == "RUNNING"
    store.abandon(task["task_id"], attempt, "test")
    assert store.get_run(run_id)["status"] == "READY"
