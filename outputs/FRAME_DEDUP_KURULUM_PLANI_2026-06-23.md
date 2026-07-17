# Frame Dedup — Kurulum Planı (2026-06-23)

## Bağlam — neden

CLIP bekçisi kredi karelerini seçtikten sonra, seçilen **her kare** tek tek OneOCR'a
gidiyor (`_pipe_ocr.py:499-500`). OneOCR per-frame okuma pipeline'ın **darboğazı**.
Sabit bir isim kartı 8 kare (4 sn @ 2fps) boyunca ekranda durduğunda 8 kare de OCR
ediliyor; 7'si saf israf. Üstelik bu fazlalık, stitch frekans-oylamasını besleyen
gürültüyü artırıyor (JAMES×7 / DAMES×1 bug'ının zemini).

**Çözüm:** CLIP ile OneOCR arasına, dHash parmak-izine dayalı, **kendi-kendine
yönlenen** bir frame-dedup adımı. Sabit kartlar agresif elenecek; scroll kareleri
(yazı kaydığı için parmak izleri farklı) **doğal olarak hiç elenmeyecek** — tip
sinyaline ihtiyaç yok.

**Araçlar zaten var:** `db_compose_master.py` içinde `dhash()` (satır 233),
`hamming()` (243), kalibre eşikler (`DUP_HAM=8`, `card_same_thr=6`). O modül
`_pipe_ocr.py`'de zaten `DB_COMPOSE` olarak import edilmiş (satır 460). Yeni
kütüphane yok; mevcut parçayı bağlıyoruz.

## Beklenen kazanç / kapsam

- **Kazanç:** sabit-kart ağırlıklı filmlerde OneOCR çağrı sayısı belirgin düşer
  (hız + daha az oy-gürültüsü). Recall **değişmemeli** (asıl invariant).
- **Kapsam dışı:** scroll-mozaik motorlarını bağlamak YOK (ölü kod + 16 dk/film).
  Tip sinyalini OCR'a taşımak YOK (gerek yok).

---

## Tasarım

### Flag'ler (hepsi env, kod-default)

| Flag | Default | Anlam |
|---|---|---|
| `MITAS_FRAME_DEDUP` | **0 (OFF)** | Ana aç/kapa. Kanıtlanana dek OFF. |
| `MITAS_FRAME_DEDUP_HAM` | `4` | "Aynı kart" Hamming eşiği (≤ ise aynı). Konservatif: sabit kart ~0-2 verir, scroll'a marj. |
| `MITAS_FRAME_DEDUP_KEEP` | `3` | Küme başına tutulacak temsilci kare sayısı (oylama güvenliği). |

> `MITAS_FRAME_DEDUP` **`_PROD_DEFAULTS`'a EKLENMEZ** (mitas_pipeline.py) — default
> OFF kalır, yalnız A/B testinde elle açılır. A/B geçerse ayrı kararla ON yapılır.

### Yeni yardımcı: `_dedup_idx(...)` (yerel, `_pipe_ocr.py` içinde)

`db_compose_master`'ın `dhash` + `hamming`'ini çağıran küçük bir yerel fonksiyon
(modülü kirletmemek için helper `_pipe_ocr.py`'de durur):

```
def _dedup_idx(idx, frame_paths, rd, dhash, hamming, ham_thr, keep_k):
    """Ardışık near-identical kareleri kümeleyip küme başına keep_k temsilci tutar.
    Karşılaştırma kümenin İLK karesine (anchor) göre — yavaş-scroll çabuk kopar
    (güvenli yön: fazla kare tut, recall'u koru). Dönüş: (kısaltılmış_idx, stats)."""
    # 1) idx<=keep_k ise no-op
    # 2) idx'i sırayla gez; her kareyi rd ile decode + dhash
    # 3) anchor'a hamming<=ham_thr ise aynı kümeye ekle; değilse kümeyi 'flush' et
    # 4) flush: küme<=keep_k ise tümü; değilse eşit-aralıklı keep_k kare seç
    # 5) None/okunamayan kare -> kendi başına TUT (asla atma)
```

**Anchor (ilk-kare) karşılaştırması, previous değil:** `split_static_cards`
previous'a bakıp kademeli-drift'i tek kart sayar (panning harita); biz DEDUP
güvenliği için anchor'a bakıyoruz → herhangi bir sürüklenme kümeyi hızla koparır →
şüphede **daha çok kare tutarız** (recall lehine).

### Bağlanma noktası: `_pipe_ocr.py`, satır ~496

idx kesinleştikten **sonra** (hibrit-kapı satır 475 + `if not idx` erken-dönüş 484-495),
decode+read_pos'tan (497-500) **önce**:

```
# ── FRAME DEDUP (MITAS_FRAME_DEDUP, default OFF) ── 20 satır yukarıdaki
#    hibrit-kapı ile AYNI fail-safe desen: hata -> idx AYNEN (regresyon yok).
if _FRAME_DEDUP_ON and len(idx) > _KEEP:
    try:
        import db_compose_master üzerinden _dcm = _load("dcm_compose", DB_COMPOSE)  # 460 ile aynı
        _idx2, _st = _dedup_idx(idx, frame_paths, fp.rd, _dcm.dhash, _dcm.hamming, _HAM, _KEEP)
        if _idx2 and len(_idx2) < len(idx):
            print(f"[pipeline100] frame-dedup: {len(idx)} -> {len(_idx2)} kare", file=sys.stderr)
            _dedup_stats = {"in": len(idx), "out": len(_idx2), "dropped": len(idx)-len(_idx2)}
            idx = _idx2
    except Exception as _dx:   # FAIL-SAFE: idx korunur
        print(f"[pipeline100] frame-dedup atlandi (idx AYNEN): {type(_dx).__name__}: {_dx}", file=sys.stderr)
```

`_dcm` text_or bloğundan bağımsız yüklenir (dedup açık + text_or kapalı olabilir).

### Telemetri

Dönüş dict'ine `dedup_in / dedup_out / dedup_dropped` eklenir → A/B ölçer.
`ocr_summary.json`'a yansır.

### Dokunulmayanlar (invariant)

- `read_pos`, `stitch_kunye`, `pick_best`, `dedup_static`, `runs_of` — **hiç
  değişmez**. Dedup yalnız `idx` listesini kısaltır; aşağı akış aynı veri yapısını
  alır, sadece daha az kareden.
- KEEP-ALL semantiği korunur (stitch zaten satır DROP etmiyor).
- Flag OFF → kod yolu hiç çalışmaz → **birebir eski davranış**.

---

## Dosyalar

| Dosya | Değişiklik |
|---|---|
| `scripts/_pipe_ocr.py` | `_dedup_idx` helper + bağlanma bloğu (~496) + flag okuma + telemetri |
| `scripts/start_mitas.ps1` | `MITAS_FRAME_DEDUP` opt-in olarak **yorumlu** eklenir (görünürlük; default OFF) |
| `tests/test_frame_dedup_20260623.py` | YENİ — helper birim testi |

> `db_compose_master.py` ve `mitas_pipeline.py` **dokunulmaz** (sadece import edilir).

---

## Uygulama — adım adım (ajan dağıtımı)

### Adım 1 — Helper + bağlama  → **Sonnet ajan A**
`_dedup_idx`'i yaz, `_pipe_ocr.py`'ye bağla, flag'leri oku, fail-safe + telemetri.
Anchor-karşılaştırma, None-kare-tut, keep_k eşit-aralıklı seçim. `db_compose`'u
mevcut `_load("dcm_compose", DB_COMPOSE)` ile çağır.

### Adım 2 — Birim testi  → **Sonnet ajan B**
`tests/test_frame_dedup_20260623.py`:
- 8 **birebir-aynı** sentetik kare → `out == keep_k`, sıralı, anchor+son dahil.
- 6 **birbirinden farklı** (kaydırılmış) kare → `out == in` (hiç atılmaz).
- Flag OFF → idx **aynen** (no-op).
- `idx <= keep_k` → no-op.
- Okunamayan (None) kare → tutulur, çökme yok.
Saf fonksiyon testi (OneOCR/CLIP gerektirmez; dhash/hamming gerçek modülden).

### Adım 3 — Kontrolör denetimi  → **kontrolör ajan (adversarial)**
Diff'i + bu tasarımı oku, şunları **kanıtla**:
1. Flag default **OFF**; OFF iken `idx` değişmiyor.
2. Fail-safe blok var; hata → `idx` aynen.
3. `read_pos`/`stitch`/`pick_best` **dokunulmamış**.
4. Anchor karşılaştırması (previous değil); keep_k ≥ 2.
5. None-kare asla atılmıyor.
6. Telemetri eklenmiş.
**Adversarial:** scroll'un yanlışlıkla kümeye çökebileceği bir senaryo bul (yavaş
scroll, ham_thr çok gevşek). Bulursa eşik/anchor mantığını sorgula. PASS/FAIL + kanıt.

### Adım 4 — Regresyon + A/B koşusu  → **ben + Sonnet**
1. **pytest:** `python -m pytest tests/ -k "credit or ocr or dedup" -v` → mevcut
   testler + yeni test yeşil (mevcut credit_qc_block 55/55, OCR testleri bozulmamalı).
2. **A/B (tek-film, döngüsüz — yetim-süreç YOK):** 4-6 film, her biri OFF sonra ON:
   ```
   MITAS_FRAME_DEDUP=0 python scripts/mitas_pipeline.py --video <F> --no-asr ...
   MITAS_FRAME_DEDUP=1 python scripts/mitas_pipeline.py --video <F> --no-asr ...
   ```
   Test seti: 2-3 sabit-kart (eski TR), 2 scroll (yeni), 1 yabancı.
   Ölç: `kunye.txt` satırları (recall), `bucket`, OCR süresi, `dedup_in/out`.

### Adım 5 — A/B denetimi  → **kontrolör ajan**
Sonuçları incele:
- **Recall invariant:** OFF vs ON `kunye.txt` satırları **birebir eşleşmeli**
  (eşleşmiyorsa eşik agresif → ham_thr düşür / keep_k artır).
- **Hız:** sabit-kart filmlerinde OCR süresi düşmeli; scroll'da ≈ aynı (dedup=0).
- **bucket** degrade YOK. **karar** (ONAYLI/KONTROL) regresyon YOK.
Tek tablo: film × {satır OFF/ON, süre OFF/ON, dropped} + PASS/FAIL.

---

## Güvenlik / durdurma (yetim-süreç tuzağı)

Tek-film CLI koşusu döngüsüz → yetim-döngü riski **yok**. Batch script (batch_watch.sh)
**kullanılmaz**. Alt-süreç timeout/kill `mitas_pipeline.py` içinde zaten var
(communicate+kill → zombie yok).

## Açıkça yapılmayacaklar (izin bekler)

- Flag'i **default ON** yapmak → yalnız A/B PASS + Çağatay'ın açık onayıyla.
- **Commit** → yalnız Çağatay "commit et" deyince.
- `db_compose_master.py` / `mitas_pipeline.py` çekirdeğini değiştirmek.

## Başarı kriteri

Flag ON iken: sabit-kart filmlerinde belirgin kare azalması + **OFF ile birebir aynı
isim çıktısı** + süre düşüşü; scroll'da sıfır değişiklik. Flag OFF iken: hiçbir fark.
