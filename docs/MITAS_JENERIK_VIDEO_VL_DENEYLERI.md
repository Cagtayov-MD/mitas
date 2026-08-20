# Jenerik → Video-VL Okuma Deneyleri (2026-07-30)

**Soru:** Tespit edilen jenerik segmentini VL modele **video olarak** verip
künye yazılarını okutmak — hangi parçalama/istem/ayar en iyi sonucu verir,
hangi model bu işte daha güçlü?

**Düzen:** v5 tespitinden gelen start_pos'tan içerik sonuna kadar sessiz mp4
parçaları kesildi (`_pipe_video_vl` mantığı, üretim koduna dokunulmadan
monkeypatch koşucuyla) → vLLM'e `video_url` ile verildi → "okuduğun her şeyi
yaz" sınıfı istem. Test malzemesi: ~2 dk'lık statik-kart jeneriği + ~50 sn
siyah kuyruk (384×288 PAL kaynak). Hakem cetveli: **karelerden gözle
doğrulanmış 11 zor isim** (SÜLÜN, ŞENYUVA, OTAĞ, EKŞİOĞLU, NİHAN TURHAN…).

Araçlar: `filmtest/dizi_cikis_vl/CICEK_TAKSI_b001/` altında
`vl_okuma_kosucu.py` (koşucu), `model_turu.sh` (model karşılaştırma),
`kiyas_gorsel.html` (kare + isim-isim görsel kıyas), `video_vl*/` (çıktılar).

---

## 1) İstem/parametre evrimi — üç koşu

| | r1 | r2 | r3 |
|---|---|---|---|
| Pencere / bindirme | 30 / 5 sn | 20 / 5 sn | 20 / 5 sn |
| max_tokens | 2500 (varsayılan) | 3500 | 3500 |
| repetition_penalty | 1.05 | 1.1 | 1.1 |
| Siyah parça | VL'e gitti | **ön-filtreyle atlandı** | atlandı |
| İstem şekli | kare-kare ("her kareyi ayrı yaz") | kare-kare | **kart-tekil** ("her FARKLI kartı bir kez") |
| Sonuç | 2 parça temiz; 1 parça **blok×7 tekrar** (68 sn); yoğun parça "CE" diye **kesildi** (2500 tavanı); 2.7 sn'lik siyah artığa **komple sahte künye** uydurdu | siyah sorunu bitti; ama kare-istem **yeni dejenerasyon**: tek karta kilitlenip 21 "kare" bastı (123 sn, 3500 tavanına dayandı) | **dejenerasyon SIFIR**, kesik yok, uydurma yok; 5 gerçek parça toplam ~35 sn |

**Ana bulgu — istem şekli kök sebep:** Statik kartlarda "her kareyi ayrı yaz"
istemi tekrarı GÖREV gereği zorluyor (kart 4-5 sn ekranda → model aynı metni
kare kare basmak zorunda, kare sayısını bilmediği için tavana kadar sayıyor).
r1'deki blok-tekrar ve r2'deki kart-kilidi aynı sınıfın iki yüzü. **Kart-tekil
istem doğru şekil** — hem temiz hem 3-4× hızlı.

**İkinci bulgu — siyah girdi stokastik uydurma üretiyor:** Aynı siyah içerik
bir parçada dürüst "[Ekran tamamen siyah.]", başka parçada **tam sahte künye**
("KARAKTER FILM STUDIO - 2024", "YÖNETMEN ALİ KARABULUT"…, istemdeki etiket
listesi şablon gibi doldurulmuş) üretti. Çare model tarafında değil:
**ffmpeg `blackdetect` ön-filtresi** (parçanın ≥%90'ı siyahsa VL'e hiç verme)
sınıfı kökten kesiyor + boş istek tasarrufu.

---

## 2) Model karşılaştırması (aynı 9 parça, kart-istem, aynı GT)

| Model | TAM isabet (11 isim) | Toplam okuma | Prompt tok/parça | Not |
|---|---|---|---|---|
| **MiniCPM-V-4.5** | **8/11** 🥇 | ~37 sn | ~2.1k | SÜLÜN/ŞENYUVA/NİHAN'ı tek doğru yazan; kalan 3 hata en hafif sınıf (Ğ/Ş/İ noktası) |
| Qwen3-VL-30B-A3B-AWQ | 5/11 | ~74 sn | ~2.5k | `video_url`'ü sorunsuz kabul etti ama 8B'nin hata sınıfını tekrarladı + 2× yavaş |
| InternVL3.5-8B | 4/11 | ~52 sn | ~8.3k (çok kare örnekliyor) | SÜLÜN'ü bildi ama ağır bozulmalar (ÖTAŞ, YAVID) + istem dışı markdown |
| Qwen3-VL-8B (mevcut motor) | 3/11 | ~35 sn | ~2.5k | En hızlılardan ama Türkçe özel-ad yazımında en zayıf |

İsim-isim dökümü ve gerçek kare görüntüleri: `kiyas_gorsel.html`.

**Yorum:** "Boyut = kalite" varsayımı burada TUTMADI (30B < MiniCPM-8B).
Türkçe diakritikli özel-ad okuma, aile/eğitim farkına boyuttan daha duyarlı.
İki bağımsız modelin aynı yazımda buluşması (SÜLÜN) tek-tanık şüphesini
kırmada işe yaradı — çapraz-tanık deseni burada da geçerli.

**⚠️ Kapsam uyarısı:** Tek segment, tek içerik türü (statik kart), tek kaynak
çözünürlük. **Motor kararı İÇİN YETERLİ DEĞİL** — eval-harness-first: film
yatağından örneklem + scroll-jenerik vakalarıyla benchmark + konsey turu şart.

---

## 3) Donanım elemeleri (RTX 3090 / 24 GB — kesin, tekrar denenmesin)

| Model | Sebep |
|---|---|
| Nemotron-Nano-12B-v2-VL-**FP8** | modelopt nicemleme **SM89+** ister (Ada/Hopper); 3090 = **SM86** → hiç açılmıyor. bf16 çeşidi ~24 GB → o da sığmaz |
| Kimi-VL-A3B | bf16 **31 GB** → sığmaz (AWQ çeşidi diskte yok) |
| Qwen3-VL-**32B**-AWQ | Ağırlık (20 GB) sığıyor ama KV-cache'e **0.16 GB** kalıyor; video token'ları ~2 GB ister (tahmini max_len 656) → video işinde kullanılamaz |

Diskte hazır olup koşanlar: 30B-A3B-AWQ (17G), InternVL3.5-8B (16G),
MiniCPM-V-4.5 (17G) — üçü de vLLM'de `video_url` kabul etti (`--trust-remote-code`
InternVL/MiniCPM için gerekli).

---

## 4) Ayar kaldıraçları — ne işe yaradı, ne yaramadı

| Kaldıraç | Hüküm |
|---|---|
| `MITAS_VIDEO_VL_MAX_TOKENS` 2500→3500 | ✅ Gerekli — 2500 yoğun parçada isim ortasında kesiyor ("CE") |
| Kart-tekil istem (`VL_SORU_MOD=kart`) | ✅ En büyük kazanç — dejenerasyonu bitirdi + 3-4× hız |
| Siyah ön-filtre (blackdetect ≥%90) | ✅ Halüsinasyon sınıfını kökten kesti |
| Pencere 30→20 sn | ✅ Parça başına kart yükünü düşürdü (15 yeni + 5 geçiş) |
| `repetition_penalty` 1.05→1.1 | ~ Tek başına dejenerasyonu ÇÖZMEDİ (r2 kanıtı); istem düzelince yardımcı |
| `MITAS_VLLM_MAX_PIXELS` (125440) | ⛔ 384×288 kaynakta ETKİSİZ (110.592 px zaten tavanın altında). 720×576 kaynakta (414.720 px, 3.3× küçültülüyor) denenmeye DEĞER — açık iş |
| Parçaları eşzamanlı gönderme / `--enforce-eager` kaldırma | Denenmedi — hız gerekirse ilk adaylar |

---

## 5) Ops dersleri (GPU paylaşımı / vLLM turları)

- **vLLM stop sonrası VRAM salımı BEKLENMELİ.** `pkill` sonrası hemen yeni
  model yüklemek ardışık OOM üretti (tur v1). Çare: süreç + boş-VRAM kontrolü.
- **Anlık boş VRAM görmek yeterli DEĞİL.** Paralel oturumun ollama işi
  (istekler arası model düşürüp geri yükleyen ping-pong) tam yükleme anında
  geri gelip motoru 2 GB'a düşürdü (tur v2). Çare: rakip sürecin **120 sn
  kesintisiz yokluğu** + boşluk şartı birlikte (debounce'lu kapı, tur v3).
- `vlm_sunucu.sh start` ollama'daki TÜM modelleri boşaltır — paralel oturumda
  canlı ollama işi varken çağırmak onun işini keser; önce koordinasyon.
- v5 tespiti **CPU'da koşamaz** (paddle oneDNN/PIR `NotImplementedError`,
  PP-OCRv5_server_det) — GPU şart; OneOCR yedeği Linux'ta yok.

---

## 6) Açık işler / sırada

1. **MiniCPM-V-4.5 gerçek benchmark'a** — film yatağı örneklemi + scroll
   jenerikler + birkaç farklı kaynak; sonra konsey kırmızı-takımı
   (`no_engine_selection_before_benchmark`).
2. Kart-tekil istem + siyah ön-filtrenin **üretim `_pipe_video_vl`'ye
   alınması kararı** (şimdilik deney koşucusunda yaşıyor).
3. Blok-düzeyi dejenerasyon filtresi (mevcut `_dejenerasyon_filtresi`
   satır-düzeyi; blok tekrarını yakalamıyor) — kart-istem varken aciliyeti
   düştü, yine de emniyet kemeri olarak değerlendirilebilir.
4. `MITAS_VLLM_MAX_PIXELS` denemesi 720×576 kaynaklı bir vakada.
5. Çift-model çapraz-tanık (ör. MiniCPM + Qwen) — `kunye_cikar` doktrinindeki
   çift-kaynak teyidinin model boyutuna genişletilmesi.
