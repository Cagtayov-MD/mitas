# olcum — Jordan config optimizasyonu

## Amaç
3 model (`w8a8`, `bf16`, `qwen2.5-vl-7b`, `qwen3-vl-8b`) için en iyi config'i
bulmak. Ölçüt: **isim atlamama · doğru okuma · Türkçe harf (ü ğ ı ş ç ö İ)**.

## Çalışma alanı — ÖLÇÜLMÜŞ GERÇEK
Klipler `/home/cagatay/Belgeler/test/` (28 adet, cag_output01–28).
Çözünürlük **düzensiz**: 600×480 (17 klip), 854×480 (9), 900×720 (1).
Çağatay: *"1080p içerik gelmez, 480 altı da gelmez — çalışma alanımız bu."*

→ `config.yaml`'daki `scale=720:-2` bu popülasyonda **600'ü BÜYÜTÜYOR**.
Büyütme bilgi eklemez, token yakar. Aday düzeltme: `scale='min(iw,720)':-2`
(asla büyütme) — ölçülecek.

## Klip triyajı (28/28, tek temas sayfasından)
| Sınıf | Klipler |
|---|---|
| Türkçe | 06, 14, 17, 18, 25, **26** |
| İngilizce kayan | 01, 21, 22, 27, 28 |
| Latin dışı | 19, 23 (Arapça/Farsça), 20 (Kiril) |
| Karanlık/düşük kontrast | 08, 10, 11, 15, 16, 24 |
| Fransızca/eski baskı | 02, 03, 04, 05, 07 |

Seçilen 10: **26 25 14 17 18** (TR) + **28 22 27 21 01** (EN).

## GT yöntemi (token-verimli)
Izgara (`tile=3x3`) siyah boşluk yüzünden israflı. Doğrusu **metin bandını
kesip yığmak**:
```bash
ffmpeg -i KLIP.mp4 -vf "fps=1,crop=iw:ih*0.30:0:ih*0.68,\
scale=iw*2.2:ih*2.2:flags=lanczos,tile=1x7" s_%02d.png
```
Klip 26 için 17 yığın dosyası → `gt/26/s_*.png`.

## Durum
- [x] 28 klip triyajı
- [x] 10 klip seçimi + GT kareleri (`gt/<nn>/`)
- [ ] Klip 26 GT metni (17 yığından 1'i okundu — s_06)
- [ ] Config süpürmesi
