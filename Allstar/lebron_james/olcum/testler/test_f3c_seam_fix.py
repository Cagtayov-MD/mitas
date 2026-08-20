"""F3c — statik-kart/slit "dikiş-tekrarı" fix'i için testler (MITAS_Master_Dup_Kok_Sebep_Plani_v1.md
"F3c KARARI"). Görsel kanıt: acemiler-cetesi (data/master_ex_modfix), run=[0,1] 90px
static_page ("Harry Spikes / LEE MARVIN + Will..." kesik) HEMEN ardından run=[2,34]
scroll_slit AYNI metinle baştan başlıyor -- kayan koşunun baş ucu kısa bir "S" run'a
bölünüp TEK statik kart olarak dondurulmuş, ama slitscan() kendi run'unun TÜM karelerini
baştan taradığı için bu kartın yakaladığı an slit'in İÇİNDE de tekrar deriliyor.

Fix (db_compose_master.py, MITAS_MASTER_V2 flag-gated, F3b'nin ÜSTÜNE -- `compose_reading_
runaware`'in ana blok-döngüsünde): yeni bir scroll_slit bloğu eklenmeden hemen önce, eğer
`block_kinds[-1] == "card"` ise (hemen önceki blok bir static_page) -- `_f3c_seam_dup_check`
statik kartın TAMAMI + slit'in İLK (static_h + 1 satır) bölgesini F1c'nin det+rec
altyapısıyla (yeni motor YOK) karşılaştırır. Normalize (küçük-harf, >=3 karakter) token
kümelerinin >=%70'i örtüşüyorsa dikiş-tekrarı KANITLANMIŞ sayılır -> static_page bloklardan
düşürülür (manifest'te skip="seam-dup" + kanıt token'ları kalır). Rec boş/düşük-güven
(HERHANGİ bir tarafta) -- kanıtsız KORU (asla kanıtsız silme). Ardışık birden çok statik
kart varsa en yakından geriye tek tek sınanır, ilk KORU kararında durulur.

Test stratejisi (üç katman, F3b'nin iki-katmanlı desenini genişletir):
  1. `_f3c_seam_dup_check` SAF karar-mantığı testleri -- det/rec motorları monkeypatch'lenir
     (gerçek PaddleOCR YOK, görüntü sentezi gerekmez) -- eşik sınırları (oran, kısa-token
     eleme, düşük-güven eleme, boş-taraf koruması) izole/deterministik kanıtlanır.
  2. Gerçek-OCR birim testleri -- cv2.putText ile RENDER edilmiş GERÇEK metin, GERÇEK
     PaddleOCR det+rec (PP-OCRv5_mobile, zaten yerel önbellekte) üzerinden `_f3c_seam_dup_
     check`e doğrudan verilir -- piksel/OCR düzeyinde kanıt (bu dosyanın rigor gereksinimi).
  3. Uçtan-uca sentetik-görüntü testi -- gerçek `compose_reading_runaware` (dolayısıyla
     gerçek `split_runs_reading`/`slitscan`) çağrılır: "tutulan ilk kart" senaryosunun
     (hold-then-scroll canvas, GERÇEK render edilmiş metin) bayrak KAPALIYKEN kusuru
     ÜRETTİĞİ, bayrak AÇIKKEN düzelttiği + GERÇEK ayrı başlık kartının bayrak AÇIKKEN de
     KORUNDUĞU (yanlış-silme koruması) gösterilir.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MONITOR_PY = PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"


def _import_monitor():
    os.environ.setdefault("MITAS_PROJECT_ROOT", str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location("master_png_monitor_f3c", str(MONITOR_PY))
    mon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mon
    spec.loader.exec_module(mon)
    return mon


@pytest.fixture(scope="module")
def dc():
    return _import_monitor().dc


@pytest.fixture(autouse=True)
def _v2_flag_cleanup():
    yield
    os.environ.pop("MITAS_MASTER_V2", None)


def _dummy_block(h: int = 20, w: int = 40) -> np.ndarray:
    """Boyutu doğru, içeriği ÖNEMSİZ (monkeypatch'lenmiş det/rec pikseli okumaz)."""
    return np.zeros((h, w, 3), dtype=np.uint8)


# --------------------------------------------------------------------------- #
# 1) _f3c_seam_dup_check -- SAF karar-mantığı testleri (det/rec monkeypatch'li)
# --------------------------------------------------------------------------- #

def _patch_tokens(monkeypatch, dc, static_tokens: dict[str, float], slit_tokens: dict[str, float]):
    """`_f3c_seam_tokens`'ı, GERÇEK det+rec yerine SABİT {token: conf} sözlükleriyle
    değiştirir -- karar mantığı (oran/eşik/filtre) OCR gürültüsünden izole test edilir.
    İlk çağrı static_block için, ikinci çağrı slit_block için varsayılır (fonksiyon
    çağrı SIRASINA göre -- _f3c_seam_dup_check her zaman static'i önce çağırır)."""
    calls = {"n": 0}

    def _fake(gray, *, token_min_len=3, rec_conf_gate=0.6):
        calls["n"] += 1
        src = static_tokens if calls["n"] == 1 else slit_tokens
        return {tok for tok, conf in src.items() if conf >= rec_conf_gate and len(tok) >= token_min_len}

    monkeypatch.setattr(dc, "_f3c_seam_tokens", _fake)


def test_oran_esik_ustu_dikis_tekrari_kanitlanir(dc, monkeypatch):
    """static token'ların TAMAMI (3/3) slit-başında da varsa (oran=1.0>=0.70) --
    dikiş-tekrarı KANITLANMIŞ, dict döner (manifest'e yazılabilir kanıt)."""
    _patch_tokens(
        monkeypatch, dc,
        static_tokens={"harry": 0.9, "spikes": 0.9, "marvin": 0.9},
        slit_tokens={"harry": 0.9, "spikes": 0.9, "marvin": 0.9, "extra": 0.9, "names": 0.9},
    )
    kanit = dc._f3c_seam_dup_check(_dummy_block(), _dummy_block())
    assert kanit is not None
    assert kanit["match_ratio"] == 1.0
    assert set(kanit["matched_tokens"]) == {"harry", "marvin", "spikes"}


def test_oran_esik_altinda_korunur(dc, monkeypatch):
    """3 static token'dan yalnız 1'i (oran=0.333<0.70) slit-başında -- FARKLI kart,
    KORUNUR (None)."""
    _patch_tokens(
        monkeypatch, dc,
        static_tokens={"acme": 0.9, "studios": 0.9, "presents": 0.9},
        slit_tokens={"acme": 0.9, "cast": 0.9, "crew": 0.9},
    )
    assert dc._f3c_seam_dup_check(_dummy_block(), _dummy_block()) is None


def test_esik_siniri_yediyuzde_tetikler(dc, monkeypatch):
    """Tam sınır: 10 static token'dan 7'si (oran=0.70, >=0.70 -- KAPSAYICI eşik) eşleşirse
    TETİKLENMELİ."""
    static = {f"tok{i}": 0.9 for i in range(10)}
    slit = {f"tok{i}": 0.9 for i in range(7)}  # ilk 7 -- oran tam 0.70
    _patch_tokens(monkeypatch, dc, static_tokens=static, slit_tokens=slit)
    kanit = dc._f3c_seam_dup_check(_dummy_block(), _dummy_block())
    assert kanit is not None
    assert kanit["match_ratio"] == pytest.approx(0.70)


def test_esik_siniri_altmis_tetiklemez(dc, monkeypatch):
    """10 static token'dan 6'sı (oran=0.60<0.70) -- KORUNUR."""
    static = {f"tok{i}": 0.9 for i in range(10)}
    slit = {f"tok{i}": 0.9 for i in range(6)}
    _patch_tokens(monkeypatch, dc, static_tokens=static, slit_tokens=slit)
    assert dc._f3c_seam_dup_check(_dummy_block(), _dummy_block()) is None


def test_bos_static_token_korunur(dc, monkeypatch):
    """Statik kartta det/rec HİÇ güvenli token bulamazsa (boş küme) -- kanıt yok,
    KORUNUR (asla kanıtsız silme)."""
    _patch_tokens(monkeypatch, dc, static_tokens={}, slit_tokens={"john": 0.9, "smith": 0.9})
    assert dc._f3c_seam_dup_check(_dummy_block(), _dummy_block()) is None


def test_bos_slit_token_korunur(dc, monkeypatch):
    """Statik kartta gerçek token var ama slit-başı boş çıkarsa (rec başarısız/gürültü)
    -- KORUNUR."""
    _patch_tokens(monkeypatch, dc, static_tokens={"john": 0.9, "smith": 0.9}, slit_tokens={})
    assert dc._f3c_seam_dup_check(_dummy_block(), _dummy_block()) is None


def test_none_static_block_korunur(dc):
    """Bozuk/boş girdi (None/size=0) -- güvenli KORUMA, hiç det/rec çağrılmaz."""
    assert dc._f3c_seam_dup_check(None, _dummy_block()) is None
    assert dc._f3c_seam_dup_check(_dummy_block(), None) is None
    assert dc._f3c_seam_dup_check(np.zeros((0, 0, 3), np.uint8), _dummy_block()) is None


# --------------------------------------------------------------------------- #
# 1b) _f3c_seam_tokens -- düşük-güven ve kısa-token filtreleri (det/rec monkeypatch'li,
#     _f1b_det_boxes/_f1c_rec_boxes seviyesinde -- _f3c_seam_tokens'ın KENDİSİ test edilir)
# --------------------------------------------------------------------------- #

def test_dusuk_guvenli_token_elenir(dc, monkeypatch):
    box = (0.5, 0.5, 0.2, 0.1, 0, 0, 10, 10)
    monkeypatch.setattr(dc, "_f1b_det_boxes", lambda gray: [box])
    monkeypatch.setattr(dc, "_f1b_boxes_sorted", lambda boxes: boxes)
    monkeypatch.setattr(dc, "_f1c_rec_boxes", lambda gray, boxes: [("gizli isim", 0.2)])  # conf<0.6
    tokens = dc._f3c_seam_tokens(np.zeros((10, 10), np.uint8))
    assert tokens == set()  # düşük güven -- HİÇ token sayılmaz


def test_kisa_token_elenir(dc, monkeypatch):
    box = (0.5, 0.5, 0.2, 0.1, 0, 0, 10, 10)
    monkeypatch.setattr(dc, "_f1b_det_boxes", lambda gray: [box])
    monkeypatch.setattr(dc, "_f1b_boxes_sorted", lambda boxes: boxes)
    # "ve"/"co" (2 harf) elenir, "harry" (5 harf) kalır -- token_min_len=3
    monkeypatch.setattr(dc, "_f1c_rec_boxes", lambda gray, boxes: [("harry ve co", 0.9)])
    tokens = dc._f3c_seam_tokens(np.zeros((10, 10), np.uint8))
    assert tokens == {"harry"}


# --------------------------------------------------------------------------- #
# 2) Gerçek-OCR birim testleri -- cv2.putText render + GERÇEK PaddleOCR det+rec
#    (piksel/OCR düzeyinde kanıt -- rigor gereksinimi, monkeypatch YOK).
# --------------------------------------------------------------------------- #

def _metin_bloku(satirlar: list[str], *, w: int = 520, line_h: int = 46, pad: int = 14) -> np.ndarray:
    """Her satırı ayrı bir çizgide beyaz-üstü-siyah (gerçek jenerik kartı gibi
    yüksek kontrast) cv2.putText ile render eden BGR görüntü -- PaddleOCR
    PP-OCRv5_mobile det+rec'in okuyabileceği büyüklükte gerçek glif."""
    h = line_h * len(satirlar) + 2 * pad
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for i, satir in enumerate(satirlar):
        y = pad + (i + 1) * line_h - int(line_h * 0.3)
        cv2.putText(img, satir, (16, y), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def test_gercek_ocr_tekrar_eden_metin_dusurulur(dc):
    """GERÇEK PaddleOCR det+rec: statik kart 'JOHN SMITH' -- slit'in İLK satırı da
    AYNI 'JOHN SMITH', ardından YENİ isimler devam ediyor (gerçek dikiş-tekrarı
    senaryosu -- acemiler-cetesi'nin küçük ölçekli benzeri). Dikiş-tekrarı
    KANITLANMALI, eşleşen token'lar 'john'/'smith' içermeli."""
    static_block = _metin_bloku(["JOHN SMITH"])
    slit_block = _metin_bloku(["JOHN SMITH", "MARY JONES", "PRODUCER CREDIT"])
    kanit = dc._f3c_seam_dup_check(static_block, slit_block)
    assert kanit is not None, "gerçek OCR dikiş-tekrarını YAKALAYAMADI (rigor: OCR okumasını gözden geçir)"
    assert "john" in kanit["matched_tokens"] or "smith" in kanit["matched_tokens"]
    assert kanit["match_ratio"] >= dc.F3C_TOKEN_MATCH_RATIO


def test_gercek_ocr_farkli_metin_korunur(dc):
    """GERÇEK PaddleOCR det+rec: statik kart 'ACME STUDIOS PRESENTS' -- slit'in
    İLK satırı TAMAMEN farklı bir oyuncu listesi. Bu GERÇEK ayrı başlık kartı --
    KORUNMALI (yanlış-silme koruması, içerik kaybı YOK)."""
    static_block = _metin_bloku(["ACME STUDIOS PRESENTS"])
    slit_block = _metin_bloku(["MARY JONES", "ROBERT DALE", "PRODUCER CREDIT"])
    kanit = dc._f3c_seam_dup_check(static_block, slit_block)
    assert kanit is None, f"YANLIŞ-SİLME: gerçek ayrı kart dikiş-tekrarı sanıldı -- kanit={kanit}"


def test_gercek_ocr_bos_slit_korunur(dc):
    """Statik kartta okunabilir metin var, slit tarafı DÜZ SİYAH (metin yok) --
    kanıt yok, KORUNMALI."""
    static_block = _metin_bloku(["JOHN SMITH"])
    slit_block = np.zeros((200, 520, 3), dtype=np.uint8)
    kanit = dc._f3c_seam_dup_check(static_block, slit_block)
    assert kanit is None


def test_gercek_ocr_derinde_konumlanan_tekrar_yakalanir(dc):
    """REGRESYON KİLİDİ -- gerçek acemiler-cetesi verisinde bulunan kök-sebep
    hatasının doğrudan tekrarı: tekrar slit'in BAŞINDA (y=0) DEĞİL, karenin
    ORTASINDA/derininde konumlanıyor (statik kartın metni ekranda alt-yarıda
    duruyorsa, slitscan()'ın seed_top+ilk-şeritleri de aynı derinlikte tekrar
    üretir -- bkz. modül-üstü F3c DÜZELTME yorumu). İlk uygulama (sabit
    'static_h+1 satır' varsayımı) bunu SESSİZCE KAÇIRIYORDU (rec boş dönüyor,
    'KORU' diyordu) -- cv2.matchTemplate hiza-arama düzeltmesi bunu YAKALAMALI."""
    static_block = _metin_bloku(["JOHN SMITH", "MARY JONES"])
    # slit: ÜSTTE 300px alakasız/boş alan, SONRA aynı iki satır, SONRA yeni isimler.
    on_bosluk = np.zeros((300, 520, 3), dtype=np.uint8)
    tekrar_ve_devam = _metin_bloku(["JOHN SMITH", "MARY JONES", "NEW ACTOR NAME", "ANOTHER ROLE HERE"])
    slit_block = np.vstack([on_bosluk, tekrar_ve_devam])
    kanit = dc._f3c_seam_dup_check(static_block, slit_block, frame_h=480)
    assert kanit is not None, "derinde konumlanan GERÇEK dikiş-tekrarı kaçırıldı (regresyon!)"
    assert kanit["align_y"] >= 250, f"hiza yanlış konumda bulundu: {kanit}"
    assert kanit["match_ratio"] >= dc.F3C_TOKEN_MATCH_RATIO


def test_tek_jenerik_token_zayif_ncc_ile_korunur(dc, monkeypatch):
    """REGRESYON KİLİDİ -- dış konsey bağımsız bug-avcılığı turunun bulduğu gerçek
    risk: statik kartta yalnız 1 (jenerik) token varsa ve NCC yalnız ORTA/ZAYIF ise
    (F3C_NCC_HIGH_CONFIDENCE altı), tek-token 1/1 oranı ARTIK YETERLİ SAYILMAZ --
    KORUNUR. (GERÇEK 427-film koşusunda 'cast'-tek-tokenli 2 gerçek düşen VARDI ama
    ikisinin de NCC'si 0.95+ idi -- bu test o marjın DIŞINDaki, kanıtsız durumu
    kilitler.)"""
    _patch_tokens(monkeypatch, dc, static_tokens={"cast": 0.9}, slit_tokens={"cast": 0.9, "other": 0.9})
    monkeypatch.setattr(
        dc, "_f3c_align_static_in_slit",
        lambda static_gray, slit_gray, **kw: (17, 0.5),  # orta NCC (<0.85), tutarlı hiza
    )
    kanit = dc._f3c_seam_dup_check(_dummy_block(), _dummy_block(h=400))
    assert kanit is None, f"az-token+orta-NCC kanıtsız durumda YİNE DE düştü: {kanit}"


def test_tek_jenerik_token_yuksek_ncc_ile_dusurulur(dc, monkeypatch):
    """AYNI senaryo ama NCC YÜKSEK (>=0.85, gerçek son-yolculuk/ufaklik vakalarının
    NCC=0.95-0.98 aralığı) -- piksel-kanıtı güçlü olduğundan tek-token yeterli,
    DÜŞMELİ (bu iki gerçek vakada regresyon YARATMADIĞININ birim-test kanıtı)."""
    _patch_tokens(monkeypatch, dc, static_tokens={"cast": 0.9}, slit_tokens={"cast": 0.9, "other": 0.9})
    monkeypatch.setattr(
        dc, "_f3c_align_static_in_slit",
        lambda static_gray, slit_gray, **kw: (17, 0.95),  # yüksek NCC
    )
    kanit = dc._f3c_seam_dup_check(_dummy_block(), _dummy_block(h=400))
    assert kanit is not None, f"yüksek-NCC tek-token GERÇEK vakaya benzer örnek yanlışlıkla korundu"


# --------------------------------------------------------------------------- #
# 3) Uçtan-uca sentetik-görüntü testi -- gerçek compose_reading_runaware
#    (gerçek split_runs_reading + slitscan), GERÇEK render edilmiş metin.
# --------------------------------------------------------------------------- #

H, W = 300, 340


def _tuval_olustur(seed: int = 3) -> np.ndarray:
    """Yüksek bir 'sanal kredi tuvali': üstte TEK kısa başlık satırı (statik-kart
    adayı), altında -- kayma ile ortaya çıkacak -- birkaç YENİ isim satırı daha.
    Tümü GERÇEK render edilmiş metin (cv2.putText) -- hem tam-kare faz-korelasyonu
    (motion/S-R etiketleme) hem PaddleOCR det+rec için okunaklı. Yeterince UZUN
    (>= hold sonrası tüm kayma mesafesi + H) ki geç kareler de boşluğa düşmesin."""
    satirlar = ["HARRY SPIKES", "LEE MARVIN ROLE", "WILL PENNY CAST", "JOAN HACKETT NAME",
                "DONALD PLEASENCE", "BEN JOHNSON ACTOR", "ANTHONY ZERBE PART",
                "SLIM PICKENS CREW", "JOHN DEHNER ROLE", "CLIFF OSMOND PART"]
    return _metin_bloku(satirlar, w=W, line_h=48, pad=10)


def _kare_yaz(tmp_path: Path, tag: str, i: int, bgr: np.ndarray) -> str:
    p = tmp_path / f"{tag}_{i:03d}.png"
    ok = cv2.imwrite(str(p), bgr)
    assert ok
    return str(p)


def _hold_then_scroll_frames(tmp_path: Path, tuval: np.ndarray, *, n_hold: int = 16,
                              n_scroll: int = 14, speed: int = 8, tag: str = "seq") -> list[str]:
    """İlk n_hold kare TAMAMEN ÖZDEŞ (tuval[0:H] -- 'tutulan ilk kart' -- statik-kart
    adayı), ardından n_scroll kare tuval üzerinde speed px/kare kayar. Kayma frame
    n_hold'da 0'dan başlar (süreklilik -- gerçek footage'ta S/R sınırı KEYFİ bir
    etiketleme kararıdır, iki taraf da AYNI karede buluşabilir) -- bu yüzden slit'in
    İLK karesi tutulan statik kartla GÖRSEL OLARAK özdeştir (gerçek dikiş-tekrarı
    mekanizmasının minyatürü). n_hold >> n_scroll ki STRICT split_runs'ın (passthrough
    kapısı) tüm-zaman-çizelgesi kayma oranı 0.75 eşiğinin ALTINDA kalsın -- aksi halde
    compose_reading_runaware passthrough'a (compose_slit) düşer, mixed-mode döngüsü
    (F3c'nin yaşadığı yer) hiç çalışmaz."""
    th, tw = tuval.shape[:2]
    frames: list[str] = []
    for i in range(n_hold):
        bgr = np.zeros((H, W, 3), dtype=np.uint8)
        bgr[: min(H, th), : min(W, tw)] = tuval[: min(H, th), : min(W, tw)]
        frames.append(_kare_yaz(tmp_path, tag, i, bgr))
    for j in range(n_scroll):
        y0 = j * speed
        bgr = np.zeros((H, W, 3), dtype=np.uint8)
        src = tuval[y0: y0 + H, : min(W, tw)]
        bgr[: src.shape[0], : src.shape[1]] = src
        frames.append(_kare_yaz(tmp_path, tag, n_hold + j, bgr))
    return frames


def _manifest_kind_skip(manifest: dict) -> list[tuple[str, str | None]]:
    return [(b.get("kind"), b.get("skip")) for b in manifest.get("blocks", []) if isinstance(b, dict)]


def test_ucdan_uca_tutulan_ilk_kart_bayrak_acikken_dusurulur_kapaliyken_kalir(dc, tmp_path):
    """Kök-senaryo (acemiler-cetesi'nin sentetik minyatürü): GERÇEK compose_reading_
    runaware, GERÇEK split_runs_reading/slitscan. Bayrak KAPALI: eski (kusurlu)
    davranış -- statik kart KORUNUR (dikiş-tekrarı hiç kontrol edilmez). Bayrak
    AÇIK: F3c bunu yakalar, 'seam-dup' ile düşürür."""
    mon = _import_monitor()
    args = mon.make_args()
    p = dc.derive_params(H, W, args)
    tuval = _tuval_olustur()
    frames = _hold_then_scroll_frames(tmp_path, tuval)

    os.environ["MITAS_MASTER_V2"] = "0"
    dc.clear_cache()
    master_off, manifest_off, _ = dc.compose_reading_runaware(frames, p, args)
    assert manifest_off["status"] == "OK"
    kinds_off = _manifest_kind_skip(manifest_off)
    static_kept_off = [k for k, s in kinds_off if k == "static_page" and not s]
    assert static_kept_off, (
        f"ÖN-KOŞUL BAŞARISIZ: sentetik senaryo bayrak kapalıyken bile statik-kart üretmedi "
        f"-- runs/manifest ayarlanmalı: {manifest_off.get('runs')}"
    )

    os.environ["MITAS_MASTER_V2"] = "1"
    dc.clear_cache()
    master_on, manifest_on, _ = dc.compose_reading_runaware(frames, p, args)
    assert manifest_on["status"] == "OK"
    seam_dup_entries = [b for b in manifest_on.get("blocks", []) if b.get("skip") == "seam-dup"]
    assert seam_dup_entries, (
        f"F3c beklenen 'seam-dup' düşüşünü üretmedi -- blocks={manifest_on.get('blocks')}"
    )
    assert "harry" in seam_dup_entries[0]["seam_kanit"]["matched_tokens"] \
        or "spikes" in seam_dup_entries[0]["seam_kanit"]["matched_tokens"]
    os.environ.pop("MITAS_MASTER_V2", None)


def test_ucdan_uca_gercek_ayri_baslik_karti_bayrak_acikken_de_korunur(dc, tmp_path):
    """YANLIŞ-SİLME koruması (uçtan-uca): 'tutulan ilk kart' GERÇEKTEN ayrı bir
    başlık ('STUDIO PRESENTS FILM') -- slit'in kayan içeriğinde (baştan farklı isim
    listesi) HİÇ tekrar etmiyor. Bayrak AÇIK olsa bile bu kart KORUNMALI -- içerik
    kaybı YOK."""
    mon = _import_monitor()
    args = mon.make_args()
    p = dc.derive_params(H, W, args)

    baslik_tuval = _metin_bloku(["STUDIO PRESENTS FILM"], w=W, line_h=48, pad=10)
    liste_tuval = _tuval_olustur(seed=9)  # farklı/yeni isim listesi -- başlıkla örtüşmüyor

    th, tw = baslik_tuval.shape[:2]
    frames: list[str] = []
    n_hold, n_scroll, speed = 16, 14, 8  # bkz. _hold_then_scroll_frames: n_hold>>n_scroll (passthrough kapısı)
    for i in range(n_hold):
        bgr = np.zeros((H, W, 3), dtype=np.uint8)
        bgr[: min(H, th), : min(W, tw)] = baslik_tuval[: min(H, th), : min(W, tw)]
        frames.append(_kare_yaz(tmp_path, "sep", i, bgr))
    lh, lw = liste_tuval.shape[:2]
    for j in range(n_scroll):
        y0 = j * speed
        bgr = np.zeros((H, W, 3), dtype=np.uint8)
        src = liste_tuval[y0: y0 + H, : min(W, lw)]
        bgr[: src.shape[0], : src.shape[1]] = src
        frames.append(_kare_yaz(tmp_path, "sep", n_hold + j, bgr))

    os.environ["MITAS_MASTER_V2"] = "1"
    dc.clear_cache()
    master_on, manifest_on, _ = dc.compose_reading_runaware(frames, p, args)
    assert manifest_on["status"] == "OK"
    seam_dup_entries = [b for b in manifest_on.get("blocks", []) if b.get("skip") == "seam-dup"]
    assert not seam_dup_entries, (
        f"YANLIŞ-SİLME: gerçek ayrı başlık kartı dikiş-tekrarı sanılıp düşürüldü -- "
        f"kanit={seam_dup_entries}"
    )
    kinds_on = _manifest_kind_skip(manifest_on)
    assert any(k == "static_page" and not s for k, s in kinds_on), (
        f"başlık kartı hiç KORUNMADI (başka bir yoldan da düştü?) -- blocks={manifest_on.get('blocks')}"
    )
    os.environ.pop("MITAS_MASTER_V2", None)
