# Jordan — değişiklik günlüğü

## 2026-08-20 — Sheriff doğrudan kare havuzu

- Sheriff `credits.mp4` yerine sınırlar içindeki kesintisiz, hash-doğrulanmış
  frame-v1 havuzunu `--kareler` ile Jordan'a bağladı.
- Jordan kaynak PNG'leri kendi güncel 720 px/Lanczos+unsharp/JPEG reçetesiyle
  hazırlayıp mevcut multi-image grup ve prompt config'ini aynen kullanır.
- Video girdisi bağımsız/geriye uyumlu kullanım için korunur; Sheriff varsayılanı
  aksi açıkça kararlaştırılana kadar frame havuzudur.

## 2026-08-19 — üretim varsayılanı Qwen3-VL-8B'ye sabitlendi

- 13-klip dizi GT yarışı: Qwen3-VL-8B 470/519 (%91) ile kazandı; Qwen3.6-27B
  %80 ile ikinci, MiniCPM-V-4.6 %35 ile sonuncu oldu. Sıralama 6 bölümün
  6'sında da aynı kaldı.
- MiniCPM'in kısa süreli üretim varsayılanlığı geri alındı. Config'teki
  "103 benzersiz satır / %100 İ" iddiası yarış-öncesi ham sayıdan geliyordu;
  içinde halüsinasyon satırları bulunduğu için kaldırıldı.
- Ölçülen reçete kuleye taşındı: 8'li öbek / 1 örtüşme (chunk 8, overlap 1),
  512 token, greedy (`do_sample: false`).
- İ-istemi cümlesinin ölçülmüş etkisi: 8B'de diakritik-tam satır sayısı
  27'den 29'a, 27B'de 33'ten 34'e çıktı; GT kapsama (43/43) her ikisinde de
  değişmeden kaldı.

## 2026-08-18 — üretim varsayılanı yeniden 2.5-VL olarak sabitlendi

- Ölçülmüş 28-klip kazananı Qwen2.5-VL-7B FP16 yeniden tek üretim
  varsayılanıdır: 2 fps, 720 px Lanczos, 8 kare, bindirme 0.
- Qwen3.6-27B silinmedi; yalnız açık `--backend llama_mtmd` deney koludur.
- Sheriff'in backend/model/grup seçmesi yasaklandı; kule kendi `config.yaml`
  reçetesinin tek sahibidir.

## 2026-08-17 — 27B büyük koşu reçetesi sabitlendi

- Qwen3.6-27B varsayılan büyük-koşu backend'i yapıldı.
- KSK özgün reçetesi birebir geri getirildi: 24 kare, tekrarlı `--image`, özgün
  etiketli prompt, `temp=0.01`, `top_p=0.10`, `repeat_penalty=1.05`, 1024 token.
- Prompta yeni yorum eklenmeden yalnız `credits[]` / `subtitles[]` JSON schema
  zorlanıyor. Rol/isim semantiği model okumasına yüklenmiyor.
- Tek geçici CUDA resource-allocation/OOM için 2 sn cooldown ile bir retry
  eklendi; tüm denemeler kanıta yazılıyor.
- Gerçek Jordan kabulü: 71 kare, 3 grup, 0 bozuk, bütün gruplar ilk denemede,
  tek final JSON, 50,4 sn. CPU testleri 80/80.

## 2026-08-17 — erken 27B adaptör deneyi (yerine yukarıdaki reçete geçti)

- Transformers kolundan bağımsız `src/model_27b.py` eklendi.
- Virgülle tek `--image` ve 6/8 kareli gruplar denendi; kalite/süre kazanmadığı
  için terk edildi. Sonraki runtime kanıtı (`total=25`) özgün tekrarlı
  `--image` çağrısının 24 görseli gerçekten işlediğini doğruladı.
- Ham JSON/schema kanıt yüzeyi bu deneyden korundu; besleme, prompt ve sampling
  daha sonra ölçülmüş özgün reçeteye geri döndürüldü.

## 2026-08-17 — multi-image hatta geçiş

- Native-video model yolu kaldırıldı. Dış video girdisi ffmpeg ile 2 fps,
  720 px, düz Lanczos JPEG karelere çevriliyor; model ayrı image listesi alıyor.
- Varsayılan model Qwen2.5-VL-7B FP16, varsayılan grup 8 kare oldu.
- KSK etiketli istemi ve greedy üretim reçetesi kuleye taşındı.
- Fuzzy tekrar eleme kaldırıldı. Yalnız kesin tekrarlar görünümden
  düşürülüyor; ham cevap ve eleme kaydı JSON'da kalıyor.
- Kare zamanı, boyutu ve SHA-256; grup ham cevabı ve SHA-256 tanıya eklendi.
- Rol/isim çiftleyici varsayılan kapatıldı, `--ciftle` ile isteğe bağlı kaldı.
- KSK gerçek koşusu: 71 kare, 9 grup, 0 bozuk, 54,9 sn.
- Jordan 64/64 ve Sheriff 67/67 CPU testi geçti.

## 2026-08-13 — kule kuruldu

Allstar'ın ikinci kulesi. **mp4 girer, yazı çıkar.** Native video okuma,
Qwen3.5-9B ile. Düzeltme, yorum, router yok.

**Sözleşme.** `OKUNDU` / `METIN_YOK` / `ARIZA` — Kobe'nin üçlü ayrımı devralındı
ve en önemli değişmez korundu: **`ARIZA` asla `METIN_YOK`'a dönüşmez.**
`METIN_YOK` ve `ARIZA` blok/çift taşıyamaz, `OKUNDU` bloksuz olamaz — hepsi
`ValueError` ile zorlanır. Atomik yazım (`os.replace`), `_TAMAM` en son.
Çıktı: `out/<film_id>/<bolum>/` içinde `jordan.json` + `jordan.txt` + `_TAMAM`.

**İki geçiş.** Geçiş 1 videodan ham metin bloklarını okur; geçiş 2 **yalnız o
metni** görerek rol→isim çiftler — görüntüyü görmez. Tek istekte model rolü
tutturmak için metni düzeltmeye başlıyor ve okuma hatasıyla eşleme hatası
ayrılamaz hale geliyordu. **Sızdırmazlık kapısı:** çıkan her rol/isim geçiş 1'in
satırlarında geçmek zorunda; geçmiyorsa atılır ve `kanit.cift_eleme`'ye yazılır.
Geçiş 2 çökerse geçiş 1'in metni korunur (`kanit.cift_ariza`).

**Parçalama — ölçülmüş zorunluluk.** Sandbox ölçümü (2026-08-12): 36 kare/çağrı
→ **39 filmin 39'unda CUDA OOM**; 30 kare → çalıştı. Klip 15 sn'lik, 2 sn
bindirmeli parçalara kesilip her parça ayrı çağrıda okunuyor. Bindirme, parça
sınırında kesilen ismi kurtarıyor; ardışık parçadaki birebir aynı blok düşüyor,
uzak tekrarlar korunuyor. Emniyet freni: `parca.kare_tavani`.

**Düşünme kapatıldı.** Qwen3.5 varsayılan akıl yürütüyor ve muhakemesi
transkripte sızıyordu — sandbox çıktısında modelin *"Wait, looking closely at
the first frame…"* diye yorum yaptığı ve cevabı kaçak bir `</think>` ile iki kez
bastığı gözlendi. `enable_thinking=False` + sızıntı ayıklayıcı: son `</think>`
sonrası alınır ve `kanit.dusunme_sizinti` sayılır; blok kapanmamışsa
`ARIZA(CIKTI_BOZUK)`. Sessizce temizleyip "okundu" denmiyor.

**İki checkpoint kuruldu.**
`model/w8a8` = INT8 W8A8 (`RedHatAI/Qwen3.5-9B-quantized.w8a8`, 14 GB) —
VARSAYILAN. `model/bf16` = orijinal (`Qwen/Qwen3.5-9B`, 19.3 GB) — kıyasın
kontrol kolu. w8a8'de **görüntü kulesi kuantize değil** (`model.visual.*`
`ignore` listesinde, bf16 kalıyor); yalnız dil tarafı 8-bit.

> **FP8 bu kartta yok.** RTX 3090 = Ampere `sm_86`, FP8 çekirdeği `sm_89`+
> ister. "8-bit" istendiğinde bu donanımda doğru cevap INT8'dir.
>
> **Hangisinin daha iyi okuduğu ÖLÇÜLMEDİ.** INT8 varsayılan çünkü bellek
> kısıtı ölçülmüş, kuantizasyon kaybı henüz varsayım. bf16 silinmez.

**Kurulum sırasında çıkan iki gerçek kusur:**
① `Allstar/.gitignore`'a `*/model/` eklendi — 33 GB ağırlık git'e girecekti.
② `torchvision` 0.26 `read_video`'yu kaldırmış; transformers ona düşüp
`AttributeError` veriyordu. `torchcodec` kuruldu. Kule bunu **sessizce
yutmadı** — ilk gerçek koşu `ARIZA(MODEL)` yazdı, hata görünür oldu.

**Uçtan uca gerçek koşu.** KUKLA ADAM açılışı (30 sn): 3 parça, 0 bozuk,
düşünme sızıntısı 0, 3 blok / 7 satır, **23.3 sn** →
`CORI FILMS` · `Quantum Films / in association with / Capital Productions
Limited / presents` · `HUMPTY DUMPTY MAN`. Uydurma yok.

Testler **52/52** (sözleşme 17 · okuyucu 14 · çiftleyici 8 · akış 13), hiçbiri
GPU istemiyor.
