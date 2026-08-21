# Kanarya bulguları — 2026-08-20, gerçek karelerle

> Kod yazılmadan önce çalışma zamanını doğrulamak için yapılan tek-grup koşusu.
> Beklenenden çok daha fazlasını verdi: tasarımın hedefi **canlı yakalandı**.

## Çalışma zamanı — DOĞRULANDI

| ölçüm | değer |
|---|---|
| model yükleme (kule içi kopya, `model/qwen3-vl-8b`) | 8,7 sn (soğuk) / 3,2 sn (sıcak) |
| üretim, 8 kare × 720 px | **2,2–2,4 sn** |
| VRAM tepe | **17,3 GB** / 24,5 GB |
| bütçe kestirimi | 90 sn klip ≈ 26 grup ≈ 60 sn/faz → **~2 dk/klip (2 faz)** |

8 klipli tam ölçüm turu ≈ **16 dk GPU**. Faz sayısını artırmak ucuz.

## BULGU 1 — mevcut 8B taban çizgisi PASTANE'de çökmüş (hata ⑤ + ①)

`gt_dizi/pastane/cikis_referans_8b.txt` sonu (gerçek dosya içeriği):

```
Yapım Koordinatörü: Yılmaz Erdoğan
Yapım Direktörü: Yılmaz Erdoğan
Yapım Müdürü: Yılmaz Erdoğan
Yapım Sorumlusu: Yılmaz Erdoğan
Yapım Ekibi: Yılmaz Erdoğan
Yapım Destek: Yılmaz Erdoğan
…
```

**Gerçek (insan GT):** `Yapım / TEOMAN TARHAN`, `Yönetmen / TEOMAN TARHAN`.
**`Yılmaz Erdoğan` ekranda HİÇ YOK** — ünlü bir Türk yönetmeninin adı, model
tarafından uydurulmuş ve kekeleme (⑤) ile 10 kez çoğaltılmış.

Bu, mimarinin var oluş sebebinin canlı kanıtı:
- **Faz-tutarlılığı** bunu yakalar mı? Kısmen — mutasyon zinciri koşudan koşuya
  değişir.
- **OCR kanıtı** yakalar mı? **Kesinlikle** — o piksellerde `Yılmaz Erdoğan`
  yazmıyor, Paddle onu üretemez.
- Tek başına hiçbiri yetmez, ikisi birlikte keser. Konsey kararı 8'in ta kendisi.

**Kabul ölçütü (kule için kırmızı çizgi):** Vince Carter'ın PASTANE çıktısında
`Yılmaz Erdoğan` **bulunmayacak**. Bulunursa kule başarısızdır.

## BULGU 2 — model reddi kredi satırı sayılmış

Aynı referans dosyasının son iki satırı:

```
There is no visible credit text in the provided images. The images are entirely black…
```

Modelin "burada yazı yok" **bildirimi**, kredi metni gibi çıktıya yazılmış.
Vince Carter'da bu `bos_bildirim` sınıfına ayrılır: ham cevapta durur, kredi
görünümüne girmez (Jordan'ın `[CREDITS]`/`[SUBTITLES]` ayrımının genişletilmişi).

## BULGU 3 — film içi sahne yazısı (neon tabela) kredi sanılıyor

`pastane_son_01m30s.mp4` ilk 4 saniyesi jenerik DEĞİL: karanlık bir sahnede
el yazısı neon tabela var. Model onu okumaya çalıştı → `Sevma`, `Yasamasi`
(ekranda gerçekte pastanenin adı yazıyor).

Bu, OCR kanıtının **savunmadığı** bir sınıf: tabela gerçekten piksellerde var,
OCR da görür, konum tutarlılığı da bozulmaz → sahte satır kanıtlanır.

**Karar:** ayrı bir `sahne_riski` işareti taşınacak (satır, kredi bloğunun
başlamasından ÖNCEki karelerde geçiyorsa). İşarettir, silme değildir; etkisi
GT yatağında ölçülecek. Jenerik SINIRI bulmak Vince Carter'ın işi değil —
o Kobe'nin işidir (MAP.md sorumluluk sınırı); kule kendisine verilen pencereyi
okur, ama şüphesini görünür kılar.

## BULGU 5 — havuz B homojen DEĞİL: Latin-dışı jenerik var

İki kare gözle incelendi (2026-08-21):

| film | kare | ne var |
|---|---|---|
| `TOPLU GÖSTERİLER-frame` c_0051 | 900×720 | **kolay uç**: mavi zemin, sarı büyük Türkçe metin, sabit kart (`Seslendirme Yönetmeni / NAİLE ATAŞAGUN`) |
| `GÜLLERİN SAVAŞI-frame` c_0062 | 600×480 | **zor uç**: Çince film — ÜÇ sütun (İngilizce rol │ Çince rol+isim │ Latin transliterasyon), küçük punto, kayan |

**Tasarım sonucu:** `latin_PP-OCRv5_mobile_rec` Çince'yi okuyamaz → o satırlarda
OCR kanıtı **sıfır** olacak. Naif bir OCR kapısı bu filmin TAMAMINI karantinaya
atardı. Konseyin (Kimi merceği) uyardığı "çok-alfabeli jenerik" edge-case'i
havuzda **gerçekten var**.

İki-olumsuz-sinyal kuralı bunu kurtarır: OCR kanıtı yok ama faz-tutarlılığı
var → **ZAYIF**, ana çıktıda kalır. Mimarinin bu kararı teorik değil, havuzun
gerçeğine denk düşüyor.

> Not: çok-alfabeli tanıyıcı devreye almak (Nash'in Arabic/ESlav devralma
> deseni) **bu kulenin işi değil** — burada OCR tanıktır, okuyucu değil.
> Latin transliterasyon sütunu zaten VLM tarafından okunuyor.

## BULGU 4 — diakritik kaybı gerçek ve sistematik

Sahne yazısında `Sevma`/`Yasamasi` (ş, ı yok), kredi karesinde `TARIHAN`
(GT: `TARHAN`). `## Turkish-Specific` uyarısı istemde olmasına rağmen kayıp
sürüyor → `diakritik_hakem` ayarının ölçülmesi (BIRLESTIRICI.md adım 6)
teorik bir merak değil, gerçek bir kazanç kalemi.
