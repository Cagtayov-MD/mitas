# McGrady CHANGELOG

## 2026-08-18 (öğleden sonra) — Tamamlama: 3 çekirdek dosya yerleşti

- Çağatay onayıyla Mimosa PreToolUse geçici kaldırıldı → credit_crosscheck.py,
  credit_qc_gates.py, poster_fetch.py Write ile yerleştirildi → hooks.json
  birebir geri yüklendi. Kule farkları listesi DURUM.md'de.
- Gerçek-zemin kanarya: **DOGRULANDI** (AHLAT AĞACI: TEYİT, ov=4, tt6628102);
  internetten afiş çekildi, poster_ok portre kapısından geçti (184KB).
- Garble kapısı gerçek DB'de doğrulandı: "GEORCE STOAD" suspect, gerçek
  oyuncular temiz.
- 36/36 test; kule gölge modda çağrıya hazır.

## 2026-08-18 — Kurulum (gölge)

- Kobe kalıbıyla kule kuruldu: `sozlesme.py` (mcgrady.girdi/v1 paket doğrulama,
  Cikti değişmezleri, atomik yazım + _TAMAM, sheriff kimlik bloğu), `main.py`
  (tek/start CLI), `mcgrady` wrapper, `config.yaml` (zemin yolları + motor
  bayrakları), `venv/` (duckdb 1.5.4 / pillow 12.1.0 / PyYAML 6.0.2 — venvs/ocr
  pin'leri), `gereksinimler.txt`, `venv_kur.sh`.
- QC2 taşıma: `src/garble.py` (credit_text_read sökümü — _looks_garble +
  _only_persons zincirleri), `src/web_cache.py` (kule kopyası; sha256 dosya adı
  + realpath sınırlama + kule-içi öntanımlı dizin), `src/sql/sorgular.sql`
  (CreditKB sabit sorguları), `src/motor.py` (orkestrasyon: crosscheck → çapa →
  öneri → garble → afiş; her katman kendi fail-safe'i).
- Dizi politikası: profile=dizi'de web katmanı atlanır (2026-08-18 kararı).
- OCR-otorite + deferans kulede de geçerli: kule YALNIZ ÖNERİ üretir, künye
  verisini EZMEZ; TMDB cast'i yalnız öneri; garble SİLME YOK.
- Testler: 36 passed (sözleşme, garble, motor-fake, izolasyon, poster_ok).
- KULUÇKA: credit_crosscheck.py / credit_qc_gates.py / poster_fetch.py
  içerikleri hazır ama Mimosa tarayıcı bloğu nedeniyle yazılamadı — yeniden
  üretim talimatı DURUM.md'de. Motor MOTOR_EKSIK ARIZA'sıyla düzgün düşer.
- MAP.md: `qc2_sixers | planlandı` → `mcgrady | kuruldu`.
