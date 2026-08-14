# Nash kulesi — değişiklik günlüğü

## 2026-08-14 — Faz 1: kule kuruldu, havuz yarısı çalışıyor

**Kule ayakta.** Ham kare dizini girer; havuz derlenir, temsilci kareler seçilir,
karar `out/<film_id>/<bolum>/nash.json` + `_TAMAM` olarak yazılır. Okuyucu
(Faz 2) kurulmadığı için gerçek koşu `ARIZA(MODEL)` döner — **bilerek görünür
bir eksik**, kule tahmin etmez.

### Eklendi
- `sozlesme.py` — `OKUNDU` / `METIN_YOK` / `ARIZA`, 5 arıza sınıfı, atomik
  yazım + `_TAMAM` en son.
- `src/havuz.py` — `harness/track_kunye/steve_nash.py` **birebir** taşındı
  (yalnız docstring başlığı değişti).
- `src/secim.py` — dizin→seçim; üretimde üç ayrı yere dağılmış örnekleme ve
  iki sigorta (son-kare, ham-kuyruk) tek yerde toplandı.
- `src/okuyucu.py` — fold-dedup, gevezelik süzgeci, sağlık dedektörü. Modeli
  bilmez (`sor` geri-çağrısı) → tamamı GPU'suz test edilebilir.
- `main.py` + `nash` + `config.yaml` — CLI (`tek` / `start`), toplu kuyruk.
- `olcum/referans_uret.py` + `olcum/kapi1.py` — taşıma kapısı.
- 99 test (havuz 25 taşındı + 74 yeni), GPU gerektirmez.

### Ölçüldü
- **KAPI 1: 29/29 birebir aynı, sapma sıfır** (15 film × çıkış+giriş yüzeyi).
  Kule, bugünkü üretim koduyla aynı havuz istatistiğini üretiyor.

### Düzeltildi (üretimden devralınan kusurlar)
- **"Havuz boş" ikiye ayrıldı.** Üretimde (`_pipe_track_kunye.py:178`) iki
  farklı gerçek tek kutuda: kareler okundu-ama-içeriksiz mi, hiçbiri
  açılamadı mı? Kule ayırır: `METIN_YOK` / `ARIZA(KARE_OKUNAMADI)`.
- **`sayfa_hata_n` sayılır.** Üretimde patlayan sayfa `continue` ile sessizce
  atlanıyor; 12 sayfadan 9'u okunmuş çıktı "tam" görünüyordu.
- **`dusurulen_n` doğru hesaplanıyor.** Referans
  (`olcum_yatagi_faz2.py:147`) atamadan sonra çıkarma yapıyor → daima 0.

### Uygulama sırasında düzeltilen iki kendi kusurum
- **Sağlık bayraktır, hüküm değil.** İlk halde her olumsuz sağlık sonucu
  `ARIZA(CIKTI_BOZUK)` üretiyordu; testler yakaladı — 150 karakterlik gerçek
  bir kısa jenerik ARIZA olup içeriği çöpe gidiyordu. Artık yalnız
  `garble_yuksek` arıza üretir, `cok_kisa` kanıta yazılır.
- **`nash.txt` yalnız `OKUNDU`'da yazılır.** Gerçek koşuda görüldü: boş bir
  `nash.txt` + `_TAMAM`, metni okuyan tüketiciye "yazı yok" gibi görünüyor ve
  ARIZA/METIN_YOK ayrımını yutuyordu.

### Kayda geçen bulgu (Nash'in dışı)
- `e1a201d5` (2026-08-05) `film_esigi`'nin Otsu aramasını yeniden yazdı —
  *"O(n) optimizasyonu"* diye, ama **cevabı değiştiriyor**. MOBY DICK 1'de
  eşik 28→13, sayfa 15→165 (11×). Hangisinin doğru olduğu **ölçülmedi**.
  Ayrıntı: `DURUM.md`.

### Bekleyen
- **Faz 0′** — sadakat sondajı (Ollama vs transformers, aynı kareler).
  Çağatay onayı gerekiyor: ~6.7 GB model indirme.
- **Faz 2** — okuyucu kule içine (`src/model.py`, `model_kur.sh`).
- **Faz 3** — üretim geçişi + `harness/track_kunye` sökümü.
