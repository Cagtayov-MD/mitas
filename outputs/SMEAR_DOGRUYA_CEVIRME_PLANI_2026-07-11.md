# SMEAR SINIFLARINI DOĞRUYA ÇEVİRME — PLAN (İş-1)
2026-07-11 · Fable planı · Durum: TASLAK — kod öncesi konsey+qwen denetiminden geçecek (çerçeve-denetimi kanunu)
Hedef: reading_master_runaware.png kalitesini İLERİ taşımak — hiçbir filmde geri çekilme YOK (Çağatay şartı).

## 0. PROBLEM TANIMI (ölçülmüş üç sınıf; hepsi hibrit-dy'nin ÇÖZMEDİĞİ, önceden-var kusurlar)

| Sınıf | Canlı örnek | Mekanizma | İsim-kaybı? |
|---|---|---|---|
| S1: Kinetik/animasyonlu başlık | HAYALET BABAM ("GHOST DAD" büyüyen harfler), Mumya açılışı | Harfler üniform kaymıyor (büyüme/morph) → slit istifi bulaşıyor | Çoğunlukla başlık (isim az) — SIDNEY POITIER krediyi de yalıyor |
| S2: Sabit yazı + hareketli footage | pilkington (yürüyen figür), drakula kuyruğu, HAYALET BABAM kredileri | Parlak hareketli footage maskeye giriyor; yazı sabit, istif footage'ı buluyor | İsimler genelde okunur ama zedeli |
| S3: Kayan kredi + serpili footage-klip | senin_hikayen | Küçük klipler dikey çizgi sütunlarına bulanıyor + aralıklı satır-çakışması | Kısmi (birkaç satır çakışık) |

Ortak ilke: hibrit-dy şablonunun aynısı — **bayrak-kapılı, gölge-kanıtlı, ölçmeden değer yok.**

## FAZ 0 — SINIF ENVANTERİ (ölçüm; kod değişikliği YOK; ~yarım gün)
1. **Otomatik smear-şüphe taraması** (salt-okur script): tüm reading masterlarda (294 Database + 54 D-korpus)
   üç ucuz sinyal: (a) text-mask satır-profil otokorelasyon bozukluğu (çakışma imzası),
   (b) dikey-çizgi enerji oranı (S3 klip-smear imzası), (c) dilim_oneocr garble-oranı (varsa).
   + hibrit gölge sidecar'ları zaten elimizde (cov/skip/n_coin teşhisleri).
2. **Görsel-QC ajan filosu** şüphelileri S1/S2/S3/TEMİZ/KAYNAK-BOŞ diye sınıflar + isim-kaybı var/yok işaretler.
3. **Çıktı: boyut tablosu** — hangi sınıf kaç filmde, kaçında gerçek isim-kaybı. Önceliklendirme buradan
   (isim-kaybı olan sınıf önce; başlık-only kozmetik sona).
KABUL: envanter tablosu + sınıf-başına 3'er referans-vaka (altın set) seçilmiş.

## FAZ 1 — SINIF-BAŞINA FİX TASARIMI (önce şartname, konsey+qwen'e SALDIRT, sonra kod)
Ön-eskizler (denetimde değişebilir):
- **S1 (kinetik başlık):** tespit = text-mask bileşen ölçek-değişimi (büyüyen harf) VEYA yüksek dy-varyans +
  düşük satır-korelasyonu → o alt-aralık slit'e SOKULMAZ; başlığın tam-oturduğu en keskin kare statik-kart
  olarak alınır (mevcut split_static_cards/medoid makinesi YENİDEN KULLANILIR, yeni motor yazılmaz).
- **S2 (sabit yazı + hareketli footage):** iki bacak — (a) DEMOTE zaten bu sınıfın kapısı (skip↑, n_coin≈0,
  cov dürüst) → statik-sayfa; (b) statik-sayfa render'ına opsiyonel **temporal-median** katmanı: N karenin
  medyanı hareketli footage'ı siler, sabit yazıyı bırakır (SIDNEY POITIER'i gerçekten TEMİZLER —
  "eskiden de kötüydü"nün panzehiri). Median yalnız bu sınıfta, bayrak-kapılı.
- **S3 (serpili klip):** şerit-bazlı içerik kapısı — istif sırasında şeridin text-oranı (mevcut text_rows
  primitifi) eşik-altıysa şerit atlanır (klip istife girmez); satır-çakışması için şerit-sınırında
  mikro-hizalama (±2px arama). En riskli sınıf — belki v2'ye bölünür, denetim karar verir.
Hepsi TEK bayrak ailesi altında: MITAS_SLIT_SMEAR_FIX={0,golge,s1|s2|s3|hepsi}. Varsayılan 0.
KABUL: şartname konsey+qwen çapraz-ateşinden geçmiş, eşikler "kanıtsız-varsayılan" etiketli.

## FAZ 2 — TÜM FİLMLERDE KOŞ + KALİTE GERİ-Mİ-İLERİ-Mİ ÖLÇÜMÜ (Çağatay'ın açık isteği)
Hibrit-dy protokolünün birebir tekrarı, ek OCR-metriğiyle:
1. Baseline(bayrak-0) vs fix'li re-compose — D-korpus 54 + Database temsili örneklem (gölge modda tam 294).
2. **Film-başına kalite karşılaştırması:** (a) dilim-OneOCR satır sayısı Δ, (b) garble-oranı Δ,
   (c) **isim-seti farkı — KIRMIZI ÇİZGİ: hiçbir filmde mevcut okunan isim kaybolamaz**
   (yeni-isim kazanımı serbest), (d) master_saglik sınıfı, (e) travel_ratio, (f) görsel-QC örneklem
   (altın-set 9 vaka + rastgele 15).
3. Kabul kapısı: isim-kaybı=0 ∧ hedef-sınıf vakalarında ölçülür iyileşme (satır↑ veya garble↓ veya görsel-temiz)
   ∧ TEMİZ filmlerde SHA-birebir (fix sınıf-dışına sızmıyor). Geçemeyen bacak bayrakta KAPALI kalır.
4. Rapor: SMEAR_FIX_KALITE_RAPORU — sınıf-başına önce/sonra kanıt görselleri + sayılar.

## İLİŞKİLER / SINIRLAR
- reading_master_runaware.png ÜRETİCİSİ compose_reading_runaware→slitscan zinciri (kod-teyitli) — bu plan
  o zinciri İLERİ taşır; bayrak-0 bit-identik kuralı burada da geçerli (geri çekilme yapısal olarak imkânsız).
- Hibrit-dy'den bağımsız ama aynı dosyada — çakışmaması için hibrit commit'i (7d8cb6fb) üstüne inşa.
- Dizi tarafıyla bağ: S1/S2/S3 dizilerde de görülür (Yedi Numara statik-kart bölümündeki tekrarlar S2-komşusu);
  kazanımlar diziye otomatik yansır.

## TAHMİNİ BÜTÇE
Faz 0: ~yarım gün (script + ajan filosu). Faz 1: şartname+denetim 1 gün, kod sınıf-başına ~½-1 gün.
Faz 2: gölge koşuları gece + ölçüm ½ gün. Toplam: ~3-4 iş günü (S3 v2'ye kalırsa ~2.5).
