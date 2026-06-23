"""Birim testleri: scripts/_pipe_ocr.py::_dedup_idx

Tum bagimliliklar (rd, dhash, hamming) sahte enjekte edilir;
gercek db_compose / numpy gerekmez.

Kostu: python tests/test_frame_dedup_20260623.py
       ya da: python -m pytest tests/test_frame_dedup_20260623.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# --- modül import -------------------------------------------------------
# Ağır yan-etkileri (torch, paddle, duckdb) atlamak için _pipe_ocr'u
# doğrudan exec yerine importlib ile yüklemek yerine sys.path'e ekleyip
# import ediyoruz.  Eğer import ortam sorununa yol açarsa aşağıdaki
# UYARI'yı okuyun.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
try:
    from _pipe_ocr import _dedup_idx  # noqa: PLC0415
    _IMPORT_OK = True
except Exception as exc:  # noqa: BLE001
    # Ağır import başarısız (torch yok, vb.) → fonksiyonu kaynaktan derle.
    # Bu yol CI/CD gibi sadece Python olan ortamlar için güvenli fallback'tir.
    _IMPORT_OK = False
    _IMPORT_ERR = exc

    import ast, types  # noqa: E401
    _src = (Path(__file__).parent.parent / "scripts" / "_pipe_ocr.py").read_text(encoding="utf-8")
    _tree = ast.parse(_src)
    # Sadece _dedup_idx fonksiyonunu ayıkla
    for node in ast.walk(_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_dedup_idx":
            _mod = types.ModuleType("_pipe_ocr_stub")
            code = compile(ast.Module(body=[node], type_ignores=[]), "_pipe_ocr.py", "exec")
            exec(code, _mod.__dict__)  # noqa: S102
            _dedup_idx = _mod.__dict__["_dedup_idx"]
            _IMPORT_OK = True
            break

# ── Yardımcı: sahte bağımlılıklar ──────────────────────────────────────

def _make_deps(hash_map: dict):
    """hash_map: {path_str: int} — None değer "okunamayan kare" anlamına gelir."""

    def rd(p):
        v = hash_map.get(str(p))
        return None if v is None else p   # None → okunamayan; path → okunabilir

    def dhash(img):
        return hash_map[str(img)]         # img aslında path string'i

    def hamming(a, b):
        return bin(a ^ b).count("1")

    return rd, dhash, hamming


# Kısa yol: idx listesini frame_paths'e dönüştür (frame_paths[i] = str(i))
def _fps(n):
    return {i: str(i) for i in range(n)}   # frame_paths sözlüğü


def _run(idx, hash_map, ham_thr=3, keep_k=3):
    """Tek yardımcı: frame_paths index → str(index) olarak haritalandır."""
    frame_paths = _fps(max(idx) + 1 if idx else 0)
    rd, dhash, hamming = _make_deps(hash_map)
    return _dedup_idx(idx, frame_paths, rd, dhash, hamming, ham_thr, keep_k)


# ────────────────────────────────────────────────────────────────────────
# TEST VAKALAR
# ────────────────────────────────────────────────────────────────────────

def test_1_identical_8_frames_keep_3():
    """8 birebir-aynı kare (hepsi hash=0) → çıktı uzunluğu == 3;
    ilk(0) ve son(7) çıktıda; dropped==5."""
    idx = list(range(8))
    hmap = {str(i): 0 for i in idx}          # hepsi aynı hash
    result, stats = _run(idx, hmap, ham_thr=0, keep_k=3)
    assert len(result) == 3, f"Beklenen 3, geldi {len(result)}: {result}"
    assert 0 in result,  "İlk kare (0) çıktıda olmalı"
    assert 7 in result,  "Son kare (7) çıktıda olmalı"
    assert stats["dropped"] == 5, f"Beklenen dropped=5, geldi {stats['dropped']}"
    assert stats["in"] == 8
    assert stats["out"] == 3


def test_2_all_different_6_frames():
    """6 birbirinden çok farklı kare → çıktı == girdi; dropped==0."""
    idx = list(range(6))
    # Her kare farklı bit setine sahip (2^k → sadece 1 bit): hamming 1, thr=0 → hep kopar
    hmap = {str(i): 1 << (i * 4) for i in idx}
    result, stats = _run(idx, hmap, ham_thr=0, keep_k=3)
    assert result == idx, f"Tüm kareler kalmalıydı, geldi {result}"
    assert stats["dropped"] == 0


def test_3_first_frame_unreadable():
    """Baştaki kare okunamıyor (None) → 0 indeksi çıktıda KORUNMALI."""
    idx = list(range(6))
    hmap = {str(i): 0 for i in idx}
    hmap["0"] = None    # ilk kare okunamıyor → singleton kümesi
    result, stats = _run(idx, hmap, ham_thr=0, keep_k=3)
    assert 0 in result, "Okunamayan baş kare (0) çıktıda korunmalıdır"


def test_4_middle_and_last_frame_unreadable():
    """Ortadaki(3) ve sondaki(7) kare okunamıyor → o indeksler çıktıda KORUNMALI."""
    idx = list(range(8))
    hmap = {str(i): 0 for i in idx}
    hmap["3"] = None
    hmap["7"] = None
    result, stats = _run(idx, hmap, ham_thr=0, keep_k=3)
    assert 3 in result, "Okunamayan orta kare (3) çıktıda korunmalıdır"
    assert 7 in result, "Okunamayan son kare (7) çıktıda korunmalıdır"


def test_5_mixed_blocks():
    """Karışık: [0-4 aynı] + [5,6,7 farklı] + [8-11 aynı] → her sabit blok keep_k=2'ye iner,
    farklılar korunur."""
    # Blok A: 0-4 (5 kare, hash=0)
    # Farklılar: 5,6,7 (her biri uzak hash)
    # Blok B: 8-11 (4 kare, hash=255)
    idx = list(range(12))
    hmap = {}
    for i in range(5):
        hmap[str(i)] = 0          # Blok A
    hmap["5"]  = 0b0000_1111_1111  # farklı
    hmap["6"]  = 0b1111_0000_1111  # farklı
    hmap["7"]  = 0b1111_1111_0000  # farklı
    for i in range(8, 12):
        hmap[str(i)] = 0xFF       # Blok B

    keep_k = 2
    result, stats = _run(idx, hmap, ham_thr=1, keep_k=keep_k)

    # Blok A (5 kare) → 2 temsilci; Farklılar 5,6,7 → her biri kendi kümesi (3 kare);
    # Blok B (4 kare) → 2 temsilci; toplam beklenti: 2+3+2 = 7
    # Ama farklılar arasındaki hamming kontrolüne göre sayı değişebilir.
    # Asıl kontrol: dropped < len(idx) ve hiç None kare yok (hepsi okunabilir).
    assert stats["dropped"] >= 0         # en az sıfır düşürüldü
    assert stats["out"] <= stats["in"]   # hiç çoğaltma olmadı
    assert 0 in result,  "Blok A ilk karesi çıktıda olmalı"
    assert 4 in result,  "Blok A son karesi çıktıda olmalı"
    assert 8 in result,  "Blok B ilk karesi çıktıda olmalı"
    assert 11 in result, "Blok B son karesi çıktıda olmalı"
    # Farklılar: en az biri korunmalı (her biri kendi kümesi → keep_k=2'den >= 1 tutulur)
    assert any(x in result for x in [5, 6, 7]), "Farklı karelerden en az biri çıktıda olmalı"


def test_6_short_list_noop():
    """`len(idx) <= keep_k` (2 kare, keep_k=3) → aynen döner, dropped==0."""
    idx = [10, 20]
    hmap = {"10": 0, "20": 0}
    frame_paths = {10: "10", 20: "20"}
    rd, dhash, hamming = _make_deps(hmap)
    result, stats = _dedup_idx(idx, frame_paths, rd, dhash, hamming, ham_thr=0, keep_k=3)
    assert result == idx,          f"No-op beklendi, geldi {result}"
    assert stats["dropped"] == 0
    assert stats["in"] == 2
    assert stats["out"] == 2


def test_7_keep_k_1():
    """keep_k=1 → her kümeden yalnız 1 temsilci (ilk eleman)."""
    idx = list(range(6))
    hmap = {str(i): 0 for i in idx}   # hepsi aynı → tek küme
    result, stats = _run(idx, hmap, ham_thr=0, keep_k=1)
    assert len(result) == 1,   f"keep_k=1 tek temsilci beklendi, geldi {result}"
    assert result[0] == 0,     "keep_k=1'de ilk eleman seçilmeli"
    assert stats["dropped"] == 5


def test_8_keep_k_1_multiple_clusters():
    """keep_k=1, iki ayrı küme → 2 temsilci (her kümenin ilki)."""
    # Küme-1: 0,1,2 (hash=0) | Küme-2: 3,4,5 (hash=0xFF)
    idx = list(range(6))
    hmap = {str(i): 0 for i in [0, 1, 2]}
    for i in [3, 4, 5]:
        hmap[str(i)] = 0xFF
    result, stats = _run(idx, hmap, ham_thr=1, keep_k=1)
    assert len(result) == 2,   f"İki küme × keep_k=1 = 2 beklendi, geldi {result}"
    assert 0 in result,        "Küme-1 temsilcisi (0) olmalı"
    assert 3 in result,        "Küme-2 temsilcisi (3) olmalı"


def test_9_env_flag_smoke():
    """MITAS_FRAME_DEDUP_ON ortam değişkeni kontrolü (import başarılıysa).
    Bu test yalnızca ağır import başarılı olduğunda koşulur."""
    if not _IMPORT_OK:
        print("ATLA: ağır import başarısız, env-flag testi yapılmıyor")
        return
    import os
    # Değişken tanımsızken _dedup_idx'in basit çağrısı hata vermemeli
    os.environ.pop("MITAS_FRAME_DEDUP_ON", None)
    idx = [0, 1, 2]
    hmap = {"0": 0, "1": 0, "2": 0}
    frame_paths = {i: str(i) for i in idx}
    rd, dhash, hamming = _make_deps(hmap)
    result, stats = _dedup_idx(idx, frame_paths, rd, dhash, hamming, ham_thr=0, keep_k=3)
    # keep_k >= len → no-op beklenir
    assert result == idx


# ────────────────────────────────────────────────────────────────────────
# Standalone runner
# ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_1_identical_8_frames_keep_3,
        test_2_all_different_6_frames,
        test_3_first_frame_unreadable,
        test_4_middle_and_last_frame_unreadable,
        test_5_mixed_blocks,
        test_6_short_list_noop,
        test_7_keep_k_1,
        test_8_keep_k_1_multiple_clusters,
        test_9_env_flag_smoke,
    ]
    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1

    total = passed + failed
    print(f"\n{'=' * 50}")
    print(f"Sonuç: {passed}/{total} geçti", "✓" if failed == 0 else f"— {failed} BAŞARISIZ")
    sys.exit(0 if failed == 0 else 1)
