# Allstar — kod adı ↔ görev sözlüğü

Kule = klasör + sözleşme. Her kule kendi girdisini alır, çıktısını YALNIZ kendi
`out/`'una yazar, gerisine karışmaz. Kuleler birbirini beklemez — Kobe kendi
hızında binlerce filmi işleyip klasörüne bırakır, tüketici hazır olanı alır.

Amaç, arızayı tek cümleye indirmek: *"sorun Kobe'de"* / *"sorun Nash'te."*
Düzeltme ayrı iş.

| Kod adı | Gerçek görev | Durum |
|---|---|---|
| **kobe** | Film sonu jeneriğinin başladığı kareyi bulur | **kuruldu** (2026-08-13) |
| lebron_james | Master PNG üretim hattı | planlandı |
| **nash** | Ham kare havuzundan jenerik okur (kare seçimi + DeepSeek-OCR) | **Faz 1 kuruldu** (2026-08-14) — okuyucu Faz 2'de |
| **jordan** | MP4'ten doğrudan okutma (Qwen3.5-9B) | **kuruldu** (2026-08-13) |
| shaq | Farkları kıyaslar + kutu kontrol | planlandı |
| phil_jackson | Shaq verisini fuzzy ile düzeltir (yazı→yazı) | planlandı |
| qc1_lakers | Kalite kapısı 1 | planlandı |
| qc2_sixers | Kalite kapısı 2 | planlandı |
| iverson | ASR tam transkript + API destekli özet | planlandı |

LeBron / Nash / Jordan aynı işe **üç ayrı besleme**dir: sırasıyla master PNG,
ham kare havuzu, doğrudan mp4. "Master PNG gerekli mi" sorusu ancak üçü de
karşılaştırılabilir **metin** ürettiğinde adil ölçülebilir.

> **Ortak okuyucu kulesi fikri terk edildi (2026-08-14, Çağatay).** Jordan
> okuyucusunu (Qwen3.5-9B) kendi içinde taşıyor; Nash de kendi okuyucusunu
> (DeepSeek-OCR) içine alıyor. Gerekçe: dışarıdaki bir servise bağlı kule
> kendi kendine yeten bir kule değildir — başkasının modeli değiştirmesi
> kuleyi sessizce değiştirir. Bedeli: besleme başına bir okuyucu kopyası.

Sonraki kule sırasını Çağatay söyler. Adım adım ilerlenir.

## Kule sınırı

Ayırt edici soru: **"bu şey değişirse kulenin CEVABI değişir mi?"**
Evet ise içeri, hayır ise dışarı.

**İçeri:** kulenin kodu, ürettiği veri, sözleşmesi ve **kendi çalışma zamanı —
venv'in içindeki her şey dahil: Paddle / torch / CUDA python paketleri.**

Bu kural pahalı bir dersle yazıldı: Kobe'ye kendi venv'i kurulunca skor
%94.5 → %92.7 düştü. Paddle sürümü, model ağırlıkları ve önbellek aynıydı;
sebep **76 eksik paketti**. Kulenin çıktısı, kodunun hiç `import` etmediği
paketlere bağlı — çalışma zamanını dondurmak skoru dondurmaktır. Ayrı venv'in
aldığı şey budur; paralellik DEĞİL (paralellik süreçten gelir, kurulumdan
değil).

**Dışarı (zemin):** sistem sürücüsü/CUDA sürücüsü, **model ağırlıkları**
(`~/.paddlex` gibi) ve `core/lexicon/` gibi paylaşılan salt-okunur sözlükler.

> Ağırlıklar bilinçli bir istisnadır: onlar da cevabı değiştirir, ama
> **kasten** paylaşılırlar — kopyalanırsa güncellenen bir model kuleye hiç
> ulaşmaz. Sözlüğü çatallamak da okuyucuya eklenen bir rolün Kobe'ye
> ulaşmaması demektir.

**Bedeli, ölçülmüş:** `kobe/venv` 11 GB · `jordan/venv` 5 GB · `nash/venv`
306 MB. Ağır kule ~5–11 GB çalışma zamanı taşır. Bilinen ve kabul edilen fiyat.

**Yasak:** başka bir kulenin **ÜRETTİĞİ** veriyi doğrudan okumak. İletişim
yalnız sözleşme üzerinden, ve yalnız `_TAMAM` işareti yazılmış dosyalardan.

## Klasör adı kuralı

Alt çizgi, tire değil (`phil_jackson`, `lebron-james` DEĞİL) — Python paketi
olarak import edilebilmeli.
