"""mitas_pipeline track_kunye gölge bloğu — kaynak-denetim testleri.

4187 satırlık main() runtime'da koşturulamaz; bu testler bloğun varlığını,
sıralamasını (MASTER-PNG'den SONRA) ve fail-safe desenini kaynak üzerinde
doğrular (emsal: test_prod_defaults_ps1_mirror).
"""
from pathlib import Path

KAYNAK = Path("/opt/mitas/scripts/mitas_pipeline.py").read_text(encoding="utf-8")


def test_blok_var_ve_betigi_cagiriyor():
    assert "_pipe_track_kunye.py" in KAYNAK
    assert 'os.environ.get("MITAS_TRACK_KUNYE", "1")' in KAYNAK


def test_blok_master_sonrasi_legacy_oncesi():
    master_i = KAYNAK.index("KANONİK MASTER-PNG")
    blok_i = KAYNAK.index("_pipe_track_kunye.py")
    legacy_i = KAYNAK.index("LEGACY GÖLGE VL")
    assert master_i < blok_i < legacy_i


def test_blok_fail_safe_ve_timeout():
    i = KAYNAK.index("TRACK-KUNYE GÖLGE")
    parca = KAYNAK[i:i + 4000]
    assert "except Exception" in parca
    assert 'MITAS_TRACK_KUNYE_TIMEOUT", "1200"' in parca
    assert "track_kunye_failed" in parca


def test_event_adlari():
    for ad in ("track_kunye_completed", "track_kunye_skipped",
               "ronaldo_band_red", "ronaldo_band_null", "ronaldo_common_blind"):
        assert ad in KAYNAK, ad


def test_master_bloguna_dokunulmadi():
    # dokunulmaz bölgenin imza satırları aynen duruyor
    assert '_mp_runner = PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"' in KAYNAK
    assert 'os.environ.get("MITAS_MASTER_PNG_TIMEOUT", "300")' in KAYNAK
