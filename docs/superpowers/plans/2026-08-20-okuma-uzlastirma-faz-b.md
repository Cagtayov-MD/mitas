# Okuma Uzlaştırma Faz B — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Üç okuyucunun çıktısını karşılaştırılabilir birime getirip N-kanal uzlaştırma ile her satırı güven etiketiyle yazmak; anlaşmazlıkları kontrol kuyruğuna koyup **gerçek anlaşmazlık oranını ölçmek**.

**Architecture:** Nash kendi içinde OCR kutu parçalarını satıra toplar (parça bbox'ları korunarak). Shaq 1–3 kanal kabul eder, satır silmez, muhalif okumayı saklar ve `KONTROL_BEKLIYOR` satırları için Nash bbox'ından kör kırpım isteği yazar — sağlayıcı bağlanmaz. Son adım, ölçüm script'i ile fazın asıl çıktısını üretir: anlaşmazlık oranı.

**Tech Stack:** Python 3, pytest, saf stdlib (yeni bağımlılık yok). Nash venv: `Allstar/nash/venv`, Shaq venv: `Allstar/shaq/venv`.

## Global Constraints

- **Hiçbir satır silinmez.** Elenen/düşürülen her şey kanıta yazılır. Sessiz düşürme yasak.
- **Kule izolasyonu:** Shaq `harness/` veya başka kulenin kodundan import ETMEZ. Shaq kendi `src/normalizasyon.py`'sini kullanır.
- **Shaq model çağırmaz.** `src/kontrol.py:1` sınırı korunur: kuyruk yazılır, sağlayıcı bağlanmaz.
- **`ARIZA` asla `METIN_YOK`'a dönüşmez** (Allstar değişmezi).
- **"Aynı" = normalleştirme sonrası BİREBİR eşitlik.** Fuzzy yakınlık "aynı" değildir, ayrı sınıftır.
- Nash mevcut testleri (163) yeşil kalmalı. Shaq mevcut testleri (36) yeşil kalmalı.
- Türkçe kod/yorum, mevcut dosyaların üslubuna uy. ASCII commit gövdesi.

---

## Dosya yapısı

| dosya | sorumluluk |
|---|---|
| `Allstar/nash/src/satir_topla.py` | **YENİ.** Saf fonksiyon: bbox'lı kutu satırlarını görsel satıra toplar. I/O yok. |
| `Allstar/nash/tests/test_satir_topla.py` | **YENİ.** Sentetik bbox kümeleriyle birim testi. |
| `Allstar/nash/src/proof.py` | **DEĞİŞİR.** `build_packet` sonunda toplama çağrılır. |
| `Allstar/shaq/src/coklu.py` | **YENİ.** N-kanal uzlaştırma + güven. Mevcut `karar.reconcile` bozulmaz. |
| `Allstar/shaq/tests/test_coklu.py` | **YENİ.** Karar tablosunun altı satırı. |
| `Allstar/shaq/olcum/anlasmazlik.py` | **YENİ.** Ölçüm script'i — fazın asıl çıktısı. |
| `Allstar/shaq/README.md`, `DURUM.md` | **DEĞİŞİR.** Alan adları ve okuma.json sayısı gerçeğe uydurulur. |

---

### Task 1: Nash — satır toplama fonksiyonu

**Files:**
- Create: `Allstar/nash/src/satir_topla.py`
- Test: `Allstar/nash/tests/test_satir_topla.py`

**Interfaces:**
- Consumes: yok (saf fonksiyon, stdlib).
- Produces: `topla(lines: list[dict], *, esik: float = 0.5) -> list[dict]` —
  girdi ve çıktı öğeleri `build_packet`'in ürettiği satır sözlüğüdür:
  `{"line_id": str, "order": int, "raw_text": str, "normalized_text": str,
  "source_label": str, "evidence": list[dict]}`. Çıktıdaki toplanmış satırlara
  ek olarak `"bilesenler": list[dict]` alanı eklenir.

- [ ] **Step 1: Write the failing test**

```python
# Allstar/nash/tests/test_satir_topla.py
"""Kutu -> satir toplama. Bbox'lar piksel xyxy: [x0, y0, x1, y1]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from satir_topla import topla


def _satir(no, metin, asset, bbox):
    return {"line_id": f"line-{no:06d}", "order": no, "raw_text": metin,
            "normalized_text": metin.upper(), "source_label": "f.png",
            "evidence": [{"asset_id": asset, "bbox": bbox,
                          "coordinate_space": "pixel_xyxy"}]}


def test_ayni_satirdaki_kutular_birlesir():
    """Aynı asset, dikeyde ortusen iki kutu -> tek satir, soldan saga."""
    gelen = [_satir(0, "MURPHY", "a1", [300, 100, 400, 130]),
             _satir(1, "Audie", "a1", [100, 102, 280, 132])]
    cikan = topla(gelen)
    assert len(cikan) == 1
    assert cikan[0]["raw_text"] == "Audie MURPHY"


def test_birlesik_bbox_bilesenleri_kapsar():
    gelen = [_satir(0, "Audie", "a1", [100, 102, 280, 132]),
             _satir(1, "MURPHY", "a1", [300, 100, 400, 130])]
    kutu = topla(gelen)[0]["evidence"][0]["bbox"]
    assert kutu == [100, 100, 400, 132]


def test_parca_bboxlari_KORUNUR():
    """Kontrol kuyrugu parcaya inebilmeli; bilesenler kaybolmaz."""
    gelen = [_satir(0, "Audie", "a1", [100, 102, 280, 132]),
             _satir(1, "MURPHY", "a1", [300, 100, 400, 130])]
    bilesen = topla(gelen)[0]["bilesenler"]
    assert len(bilesen) == 2
    assert [b["raw_text"] for b in bilesen] == ["Audie", "MURPHY"]


def test_ayri_satirlar_birlesmez():
    """Dikeyde ortusmeyen kutular ayri kalir."""
    gelen = [_satir(0, "Audie MURPHY", "a1", [100, 100, 400, 130]),
             _satir(1, "Scott BRADY", "a1", [100, 200, 400, 230])]
    assert len(topla(gelen)) == 2


def test_farkli_asset_birlesmez():
    """Ayni y'de olsalar bile farkli kareler birlestirilemez."""
    gelen = [_satir(0, "Audie", "a1", [100, 100, 280, 130]),
             _satir(1, "MURPHY", "a2", [300, 100, 400, 130])]
    assert len(topla(gelen)) == 2


def test_bboxsuz_satir_oldugu_gibi_gecer():
    """Koordinati olmayan satir gruplanamaz; ASLA dusurulmez."""
    yalin = {"line_id": "line-000000", "order": 0, "raw_text": "PRESENTS",
             "normalized_text": "PRESENTS", "source_label": "f.png",
             "evidence": []}
    cikan = topla([yalin])
    assert len(cikan) == 1
    assert cikan[0]["raw_text"] == "PRESENTS"
    assert "bilesenler" not in cikan[0]


def test_tek_kutu_bilesen_almaz():
    """Tek basina kalan kutu toplanmis sayilmaz."""
    cikan = topla([_satir(0, "PRESENTS", "a1", [100, 100, 400, 130])])
    assert len(cikan) == 1
    assert "bilesenler" not in cikan[0]


def test_order_yeniden_numaralanir():
    gelen = [_satir(0, "Audie", "a1", [100, 100, 280, 130]),
             _satir(1, "MURPHY", "a1", [300, 100, 400, 130]),
             _satir(2, "Scott BRADY", "a1", [100, 200, 400, 230])]
    cikan = topla(gelen)
    assert [c["order"] for c in cikan] == [0, 1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/mitas/Allstar/nash && ./venv/bin/python -m pytest tests/test_satir_topla.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'satir_topla'`

- [ ] **Step 3: Write minimal implementation**

```python
# Allstar/nash/src/satir_topla.py
"""OCR kutu parcalarini gorsel satira toplar.

NEDEN: DeepSeek grounding kutu basina metin dondurur — 'Audie' ve 'MURPHY'
ayri kutulardir. LeBron ve Jordan ise birlestirilmis satir uretir. Uc okuyucu
karsilastirilamaz birimdeydi; uzlastirma bu yuzden calisamiyordu (olculdu
2026-08-19: ham uzlasma %26,3, ama bu sayi birim uyusmazligini olcuyordu).

Toplama Nash'in ICINDE yapilir: kendi ciktisinin biriminden kule sorumludur.

DEGISMEZ: parca bbox'lari kaybolmaz, 'bilesenler' altinda korunur — kontrol
kuyrugu gerekirse parcaya inebilmeli.
"""
from __future__ import annotations

from typing import Any


def _kutu(satir: dict[str, Any]) -> tuple[str, list[int]] | None:
    """Satirin ilk gecerli (asset_id, bbox) ciftini dondur; yoksa None."""
    for kanit in satir.get("evidence") or []:
        bbox = kanit.get("bbox")
        asset = kanit.get("asset_id")
        if asset and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            return str(asset), [int(v) for v in bbox]
    return None


def _dikey_ortusme(a: list[int], b: list[int]) -> float:
    """Iki kutunun dikey ortusmesi / KUCUK olanin yuksekligi."""
    ust, alt = max(a[1], b[1]), min(a[3], b[3])
    if alt <= ust:
        return 0.0
    kucuk = min(a[3] - a[1], b[3] - b[1])
    return (alt - ust) / kucuk if kucuk > 0 else 0.0


def topla(lines: list[dict[str, Any]], *, esik: float = 0.5) -> list[dict[str, Any]]:
    """Ayni asset uzerinde dikeyde ortusen kutulari tek satira topla.

    Bbox'i olmayan satir gruplanamaz ve OLDUGU GIBI gecer — dusurulmez.
    """
    gruplar: list[dict[str, Any]] = []
    for satir in lines:
        yer = _kutu(satir)
        if yer is None:
            gruplar.append({"asset": None, "uyeler": [satir], "kutu": None})
            continue
        asset, bbox = yer
        for grup in gruplar:
            if (grup["asset"] == asset and grup["kutu"] is not None
                    and _dikey_ortusme(grup["kutu"], bbox) >= esik):
                grup["uyeler"].append(satir)
                k = grup["kutu"]
                grup["kutu"] = [min(k[0], bbox[0]), min(k[1], bbox[1]),
                                max(k[2], bbox[2]), max(k[3], bbox[3])]
                break
        else:
            gruplar.append({"asset": asset, "uyeler": [satir], "kutu": list(bbox)})

    cikti: list[dict[str, Any]] = []
    for sira, grup in enumerate(gruplar):
        uyeler = grup["uyeler"]
        if len(uyeler) == 1:
            tek = dict(uyeler[0])
            tek["order"] = sira
            tek["line_id"] = f"line-{sira:06d}"
            cikti.append(tek)
            continue
        uyeler = sorted(uyeler, key=lambda s: (_kutu(s) or ("", [0, 0, 0, 0]))[1][0])
        metin = " ".join(u["raw_text"] for u in uyeler if u.get("raw_text"))
        ornek = dict(uyeler[0]["evidence"][0])
        ornek["bbox"] = grup["kutu"]
        cikti.append({"line_id": f"line-{sira:06d}", "order": sira,
                      "raw_text": metin, "normalized_text": metin.upper(),
                      "source_label": uyeler[0].get("source_label"),
                      "evidence": [ornek],
                      "bilesenler": [dict(u) for u in uyeler]})
    return cikti
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/mitas/Allstar/nash && ./venv/bin/python -m pytest tests/test_satir_topla.py -q`
Expected: PASS — `8 passed`

- [ ] **Step 5: Nash regresyonu**

Run: `cd /opt/mitas/Allstar/nash && ./venv/bin/python -m pytest tests/ -q`
Expected: `163 passed, 1 skipped` (yeni 8 ile birlikte `171 passed, 1 skipped`)

- [ ] **Step 6: Commit**

```bash
cd /opt/mitas
git add Allstar/nash/src/satir_topla.py Allstar/nash/tests/test_satir_topla.py
git commit -m "feat(nash): kutu->satir toplama fonksiyonu (parca bbox'lari korunur)"
```

---

### Task 2: Nash — toplamayı pakete bağla

**Files:**
- Modify: `Allstar/nash/src/proof.py:146-148` (satır listesi kurulduktan sonra)
- Test: `Allstar/nash/tests/test_satir_topla.py` (aynı dosyaya ek)

**Interfaces:**
- Consumes: `satir_topla.topla` (Task 1).
- Produces: `build_packet(...)` çıktısındaki `packet["lines"]` artık satır
  birimlidir; imza değişmez.

- [ ] **Step 1: Write the failing test**

```python
# Allstar/nash/tests/test_satir_topla.py — dosyanin SONUNA ekle

def test_paket_satir_birimli_cikar(tmp_path, monkeypatch):
    """build_packet artik kutu degil satir birimi yazmali."""
    import proof

    monkeypatch.setattr(proof, "_identity", lambda: {"tool": "test"})
    monkeypatch.setattr(proof, "_frame_manifest", lambda: {})
    monkeypatch.setattr(proof, "_png_size", lambda p: (1000, 1000))
    monkeypatch.setattr(proof, "_asset", lambda aid, p, w, h, m: {
        "asset_id": aid, "path": str(p), "width": w, "height": h,
        "frame_sequence": 1, "source_time_s": 0.5})
    monkeypatch.setattr(proof, "_sha", lambda p: "0" * 64)

    kare = tmp_path / "f.png"
    kare.write_bytes(b"x")
    grounding = {"f.png": [
        {"label": "Audie", "boxes_999": [[100, 102, 280, 132]], "engine": "t", "score": 1.0},
        {"label": "MURPHY", "boxes_999": [[300, 100, 400, 130]], "engine": "t", "score": 1.0}]}
    paket = proof.build_packet(
        film_id="F", section="cikis", legacy={"durum": "OKUNDU"},
        selected_paths=[kare],
        accepted=[{"text": "Audie", "kaynak": "f.png"},
                  {"text": "MURPHY", "kaynak": "f.png"}],
        rejected=[], grounding=grounding, grounding_failures=[])

    assert len(paket["lines"]) == 1
    assert paket["lines"][0]["raw_text"] == "Audie MURPHY"
    assert len(paket["lines"][0]["bilesenler"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/mitas/Allstar/nash && ./venv/bin/python -m pytest tests/test_satir_topla.py::test_paket_satir_birimli_cikar -q`
Expected: FAIL — `assert 2 == 1` (toplama henüz bağlı değil)

- [ ] **Step 3: Write minimal implementation**

`Allstar/nash/src/proof.py` başındaki import bloğuna ekle:

```python
from satir_topla import topla as _satir_topla
```

`build_packet` içinde, `lines` döngüsü bittikten hemen sonra — yani şu satırın
**önüne**:

```python
    execution = "FAILED" if legacy.get("durum") == "ARIZA" else "SUCCEEDED"
```

şunu ekle:

```python
    # Kutu parcalari gorsel satira toplanir; parca bbox'lari 'bilesenler'de
    # korunur. Bkz. satir_topla.py — uc okuyucunun birimini esitler.
    lines = _satir_topla(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/mitas/Allstar/nash && ./venv/bin/python -m pytest tests/test_satir_topla.py -q`
Expected: PASS — `9 passed`

- [ ] **Step 5: Nash tam regresyon**

Run: `cd /opt/mitas/Allstar/nash && ./venv/bin/python -m pytest tests/ -q`
Expected: `172 passed, 1 skipped`

Kırılan test varsa DUR ve raporla — `proof_status` hesabı `lines` üzerinden
yapıldığı için toplama onu etkileyebilir.

- [ ] **Step 6: Commit**

```bash
cd /opt/mitas
git add Allstar/nash/src/proof.py Allstar/nash/tests/test_satir_topla.py
git commit -m "feat(nash): satir toplama build_packet'e baglandi"
```

---

### Task 3: Shaq — N-kanal uzlaştırma ve güven

**Files:**
- Create: `Allstar/shaq/src/coklu.py`
- Test: `Allstar/shaq/tests/test_coklu.py`

**Interfaces:**
- Consumes: `Allstar/shaq/src/normalizasyon.py` → `normalize(text) -> str`,
  `near(left, right, max_edits=3) -> bool` (kendi kulesinden; `harness/`'tan
  import YASAK).
- Produces: `uzlastir(paketler: dict[str, dict]) -> list[dict]` — her öğe
  `{"metin": str, "durum": str, "guven": str, "kanallar": dict[str, str],
  "muhalif": dict[str, str]}`. `durum` ∈ `{"GECTI", "KONTROL_BEKLIYOR"}`,
  `guven` ∈ `{"yuksek", "orta", "dusuk"}`.

- [ ] **Step 1: Write the failing test**

```python
# Allstar/shaq/tests/test_coklu.py
"""N-kanal uzlastirma. Karar tablosunun ALTI satiri da burada."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coklu import uzlastir


def _paket(*metinler):
    return {"lines": [{"raw_text": m} for m in metinler]}


def test_uc_kanal_birebir_ayni_yuksek_guven():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("AUDIE MURPHY"),
                      "jordan": _paket("AUDIE MURPHY")})
    assert len(sonuc) == 1
    assert sonuc[0]["durum"] == "GECTI"
    assert sonuc[0]["guven"] == "yuksek"


def test_iki_kanal_ayni_ucuncu_yok_orta_guven():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("AUDIE MURPHY")})
    assert sonuc[0]["durum"] == "GECTI"
    assert sonuc[0]["guven"] == "orta"


def test_iki_ayni_ucuncu_farkli_muhalif_SAKLANIR():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("AUDIE MURPHY"),
                      "jordan": _paket("AUDIE MURPHYY")})
    kabul = [s for s in sonuc if s["metin"] == "AUDIE MURPHY"][0]
    assert kabul["guven"] == "orta"
    assert kabul["muhalif"] == {"jordan": "AUDIE MURPHYY"}


def test_yalniz_diakritikte_ayrisma_kontrole_gider():
    """UMIT vs UMIT(noktali) — fuzzy yakin ama biri YANLIS. Ayni sayilmaz."""
    sonuc = uzlastir({"nash": _paket("ÜMİT YESİN"),
                      "lebron": _paket("ÜMIT YESIN")})
    assert sonuc[0]["durum"] == "KONTROL_BEKLIYOR"
    assert sonuc[0]["guven"] == "dusuk"


def test_metinde_ayrisma_kontrole_gider():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("SCOTT BRADY")})
    assert all(s["durum"] == "KONTROL_BEKLIYOR" for s in sonuc)


def test_tek_kanal_dusuk_guvenle_TUTULUR():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY")})
    assert sonuc[0]["durum"] == "GECTI"
    assert sonuc[0]["guven"] == "dusuk"


def test_hicbir_satir_SILINMEZ():
    """Her kanaldaki her benzersiz metin ciktida bulunmali."""
    sonuc = uzlastir({"nash": _paket("A ISMI", "B ISMI"),
                      "lebron": _paket("B ISMI", "C ISMI")})
    metinler = {s["metin"] for s in sonuc}
    assert metinler == {"A ISMI", "B ISMI", "C ISMI"}


def test_nash_yoksa_cozumsuz():
    """Nash zorunlu: bbox yoksa kontrol kuyrugu kurulamaz."""
    sonuc = uzlastir({"lebron": _paket("AUDIE MURPHY")})
    assert sonuc[0]["durum"] == "COZUMSUZ"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/mitas/Allstar/shaq && ./venv/bin/python -m pytest tests/test_coklu.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'coklu'`

- [ ] **Step 3: Write minimal implementation**

```python
# Allstar/shaq/src/coklu.py
"""N-kanal uzlastirma (1..3) + guven etiketi.

NEDEN N: 'tam iki paket' sarti gercege uymuyor — 76 bolumde LeBron
49 SUCCEEDED / 21 NO_CONTENT / 6 FAILED, yani %36'sinda hic satir yok
(olculdu 2026-08-19). Sabit iki kanal Shaq'i o bolumlerde calisamaz kilardi.

DEGISMEZLER:
  * Satir SILINMEZ. Her kanaldaki her benzersiz metin ciktida kalir.
  * Muhalif okuma saklanir; cogunluk karari DOGRULUK IDDIASI DEGIL, yalnizca
    guven seviyesidir — uc okuyucu ayni pikselleri okudugu icin ortak hataya
    da dusebilir.
  * 'Ayni' = normalize sonrasi BIREBIR esitlik. Fuzzy yakinlik ayni degildir:
    'UMIT' ile 'UMIT'(noktali) yakin ama biri yanlistir; ayni saymak yanlis
    yazimi sessizce kabul etmek olur.
  * Nash zorunlu kanaldir: bbox yalniz onda var (%100; lebron %1, jordan %0),
    kontrol kuyrugu onun koordinatlarina bagli.
"""
from __future__ import annotations

from typing import Any

from normalizasyon import normalize

CAPA = "nash"


def uzlastir(paketler: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Kanal adi -> okuma paketi. Her benzersiz satir icin bir karar dondurur."""
    kanal_metin: dict[str, dict[str, str]] = {}
    for kanal, paket in paketler.items():
        esle: dict[str, str] = {}
        for satir in (paket or {}).get("lines") or []:
            ham = str(satir.get("raw_text") or "").strip()
            if not ham:
                continue
            esle.setdefault(normalize(ham), ham)
        kanal_metin[kanal] = esle

    capa_var = CAPA in paketler
    tum_anahtarlar: list[str] = []
    for esle in kanal_metin.values():
        for anahtar in esle:
            if anahtar not in tum_anahtarlar:
                tum_anahtarlar.append(anahtar)

    sonuc: list[dict[str, Any]] = []
    for anahtar in tum_anahtarlar:
        diyen = {k: v[anahtar] for k, v in kanal_metin.items() if anahtar in v}
        demeyen = {k: v for k, v in kanal_metin.items() if anahtar not in v}
        muhalif: dict[str, str] = {}
        for kanal, esle in demeyen.items():
            if esle:
                muhalif[kanal] = next(iter(esle.values()))

        metin = next(iter(diyen.values()))
        if not capa_var:
            durum, guven = "COZUMSUZ", "dusuk"
        elif len(diyen) >= 3:
            durum, guven = "GECTI", "yuksek"
        elif len(diyen) == 2:
            durum, guven = "GECTI", "orta"
        elif len(diyen) == 1 and len(paketler) == 1:
            durum, guven = "GECTI", "dusuk"
        else:
            durum, guven = "KONTROL_BEKLIYOR", "dusuk"

        sonuc.append({"metin": metin, "durum": durum, "guven": guven,
                      "kanallar": diyen,
                      "muhalif": muhalif if durum == "GECTI" else {}})
    return sonuc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/mitas/Allstar/shaq && ./venv/bin/python -m pytest tests/test_coklu.py -q`
Expected: PASS — `8 passed`

- [ ] **Step 5: Shaq regresyonu**

Shaq venv'inde pytest yoksa önce kur:

```bash
cd /opt/mitas/Allstar/shaq && ./venv/bin/python -m pip install -q pytest
```

Run: `cd /opt/mitas/Allstar/shaq && ./venv/bin/python -m pytest tests/ -q`
Expected: mevcut 36 test + yeni 8 = `44 passed`. Kırılan varsa DUR ve raporla.

- [ ] **Step 6: Commit**

```bash
cd /opt/mitas
git add Allstar/shaq/src/coklu.py Allstar/shaq/tests/test_coklu.py
git commit -m "feat(shaq): N-kanal uzlastirma + guven etiketi (satir silinmez)"
```

---

### Task 4: Ölçüm — gerçek anlaşmazlık oranı

**Files:**
- Create: `Allstar/shaq/olcum/anlasmazlik.py`

**Interfaces:**
- Consumes: `coklu.uzlastir` (Task 3); girdi yatağı `Allstar/shaq/in/`.
- Produces: stdout raporu + `Allstar/shaq/olcum/anlasmazlik_YYYYMMDD.json`.

Bu, fazın **asıl çıktısıdır**: bir özellik değil, bir sayı.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
# Allstar/shaq/olcum/anlasmazlik.py
"""Faz B'nin ASIL CIKTISI: birim hizalandiktan sonraki gercek anlasmazlik orani.

Bu sayi mimari karari belirler (spec 2026-08-19-okuma-uzlastirma-design.md §6):
  dusuk (~%5-10) -> okuyucular birbirini dogruluyor, hakem sec (Faz C)
  yuksek (~%30+) -> uc okuyucu uc ayri gercek uretiyor, mimari gozden gecer

Kosum: Allstar/shaq/venv/bin/python Allstar/shaq/olcum/anlasmazlik.py
"""
from __future__ import annotations

import collections
import datetime
import glob
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "src"))

from coklu import uzlastir  # noqa: E402

KANALLAR = ("nash", "lebron", "jordan")


def paketleri_yukle(bolum_dizini: str) -> dict[str, dict]:
    paketler: dict[str, dict] = {}
    for yol in glob.glob(bolum_dizini + "/*.okuma.json"):
        for kanal in KANALLAR:
            if "/" + kanal + "-" in yol:
                try:
                    paketler[kanal] = json.load(open(yol, encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
    return paketler


def main() -> int:
    sayac = collections.Counter()
    bolum_sayisi = 0
    for bolum in sorted(glob.glob(str(KOK / "in" / "*" / "run-*" / "[gc]*"))):
        paketler = paketleri_yukle(bolum)
        if not paketler:
            continue
        bolum_sayisi += 1
        sayac["kanal_" + str(len(paketler))] += 1
        for karar in uzlastir(paketler):
            sayac[karar["durum"]] += 1
            sayac["guven_" + karar["guven"]] += 1

    toplam = sum(sayac[d] for d in
                 ("GECTI", "KONTROL_BEKLIYOR", "COZUMSUZ"))
    if not toplam:
        print("olculecek satir yok — in/ bos mu?")
        return 1

    oran = 100.0 * sayac["KONTROL_BEKLIYOR"] / toplam
    print(f"bolum            : {bolum_sayisi}")
    print(f"satir (benzersiz): {toplam}")
    print()
    print(f"GECTI            : {sayac['GECTI']:6d}")
    print(f"KONTROL_BEKLIYOR : {sayac['KONTROL_BEKLIYOR']:6d}")
    print(f"COZUMSUZ         : {sayac['COZUMSUZ']:6d}")
    print()
    print(f"guven yuksek     : {sayac['guven_yuksek']:6d}")
    print(f"guven orta       : {sayac['guven_orta']:6d}")
    print(f"guven dusuk      : {sayac['guven_dusuk']:6d}")
    print()
    print(f">>> ANLASMAZLIK ORANI: %{oran:.1f}  (kontrol kuyrugu yuku)")
    print(">>> spec §6: <=%10 ise Faz C (hakem sec) · >=%30 ise mimari gozden gecer")

    damga = datetime.date.today().strftime("%Y%m%d")
    hedef = KOK / "olcum" / f"anlasmazlik_{damga}.json"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(json.dumps(
        {"bolum": bolum_sayisi, "satir": toplam,
         "anlasmazlik_orani": round(oran, 2), "sayac": dict(sayac)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazildi: {hedef}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

Run: `cd /opt/mitas && Allstar/shaq/venv/bin/python Allstar/shaq/olcum/anlasmazlik.py`
Expected: bölüm sayısı ~76, satır sayısı binlerce, ve **`>>> ANLASMAZLIK ORANI: %XX.X`** satırı.

> **DUR VE RAPORLA.** Bu sayı Çağatay'a gösterilmeden Faz C'ye geçilmez.
> Ölçüm `in/` altındaki paketler **Task 2'den ÖNCE** üretildiği için Nash
> tarafı hâlâ kutu birimindedir. Gerçek sayıyı almak için Nash paketlerinin
> yeniden üretilmesi gerekir — bunu Çağatay'la konuş, kendi başına koşturma
> (GPU maliyeti var).

- [ ] **Step 3: Commit**

```bash
cd /opt/mitas
git add Allstar/shaq/olcum/anlasmazlik.py
git commit -m "measure(shaq): anlasmazlik orani olcum araci — Faz B'nin asil ciktisi"
```

---

### Task 5: Belge senkronu

**Files:**
- Modify: `Allstar/shaq/README.md`
- Modify: `Allstar/shaq/DURUM.md`

Spec §7.3'te tespit edilen belge–kod sapması kapatılır.

- [ ] **Step 1: README alan adlarını düzelt**

`Allstar/shaq/README.md` içindeki JSON örneğinde ve çevresindeki metinde:
- `"text"` → `"raw_text"` (ayrıca `"normalized_text"` alanı da var)
- `"bolum"` → `"section"`
- `"durum"` → `"status"` (değeri sözlük: `{"execution": ..., "content": ..., "proof": ...}`)
- bbox sözlük `{"x0":..,"y0":..,"x1":..,"y1":..}` → **liste** `[x0, y0, x1, y1]`

Girdi sözleşmesi başlığındaki *"bölüm başına **tam iki** `*.okuma.json`"*
cümlesini şununla değiştir:

```markdown
Film klasöründe bölüm başına **1–3** `*.okuma.json` bulunur. `nash` paketi
ZORUNLUDUR — bbox yalnız onda vardır (ölçüldü 2026-08-19: nash %100,
lebron %1, jordan %0) ve kör kontrol kuyruğu onun koordinatlarına bağlıdır.
Diğer kanallar varsa katılır, yoksa güven düşürülür.
```

- [ ] **Step 2: DURUM.md'deki yanlış sayıyı düzelt**

Şu cümleyi bul:

> `*.okuma.json` sayısı **0** olduğu için gerçek karşılaştırma henüz koşulamaz.

Şununla değiştir:

```markdown
`*.okuma.json` üretimi başladı: 2026-08-19 itibarıyla ağaçta **883** paket var
(sheriff: nash 347 · lebron 125 · jordan 72; ayrıca `shaq/in/` altında 30 film
× 76 bölüm üç kanallı). Gerçek karşılaştırmanın önündeki engel artık paket
yokluğu DEĞİL, **birim uyuşmazlığıdır**: Nash kutu parçası, LeBron/Jordan
birleştirilmiş satır üretiyordu. Faz B bunu Nash içinde kapatır.
```

- [ ] **Step 3: Commit**

```bash
cd /opt/mitas
git add Allstar/shaq/README.md Allstar/shaq/DURUM.md
git commit -m "docs(shaq): belge-kod sapmasi kapatildi — alan adlari, bbox bicimi, paket sayisi"
```

---

## Öz-denetim notu

Spec kapsamı ile plan eşleşmesi:

| spec bölümü | karşılayan task |
|---|---|
| §3.1 Nash satır toplama | Task 1 + 2 |
| §3.2 Shaq N-kanal + güven (karar tablosu 6 satır) | Task 3 |
| §3.3 kontrol kuyruğu | **Task 3'te `KONTROL_BEKLIYOR` üretilir; kuyruk DOSYASI yazımı Faz B'de kapsam dışı bırakıldı** — kuyruk uzunluğu Task 4'te sayılıyor, kırpım üretimi hakem seçilince (Faz C) anlamlı olur |
| §4 hata yönetimi | Task 3 (`COZUMSUZ` testi), Task 2 (regresyon kapısı) |
| §5 test | Task 1/2/3 adımları |
| §6 karar noktası | Task 4 |
| §7.3 belge sapması | Task 5 |

**Spec'ten sapma — bilinçli:** §3.2 normalleştirmeyi `harness/kunye_kiyas/isim_normalize.py`'den almayı söylüyordu; bu, Shaq'ın `harness/`'tan import etmesi demek ve **kule izolasyonunu deler**. Shaq'ın kendi `src/normalizasyon.py`'si aynı ilkeyi zaten uyguluyor (`near()` 6 karakterden kısa isimlerde fuzzy'yi kapatır = "kısa isimlerde tolerans sıfır"). Plan kendi modülünü kullanır.
