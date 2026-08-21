# Vince Carter — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Kurulum sırası, kararlar ve açık borçlar burada.

**Son güncelleme:** 2026-08-20 · **Durum:** kuruluyor (Faz 0–3a paralel)

## Kule ne yapar

Film **giriş** ve **çıkış** jeneriğini okur; her satırı **piksel kanıtına**
bağlar; kanıtsız satırı silmez, işaretler. Jenerik SINIRINI bulmaz (o Kobe'nin
işi), isim düzeltmez, dünya bilgisi kullanmaz.

## Karar zinciri (neden böyle)

| karar | gerekçe | kaynak |
|---|---|---|
| Kare beslemesi, native video YASAK | video beslemede oyuncu eşleşmesi 0/16 (ölçülmüş) | `jenerik-okuma-frame-catisi` |
| Okuyucu: Qwen3-VL-8B, Jordan'ın istemi birebir | 13-klip GT yarışı %91 (27B %80, MiniCPM %35) | `jordan/KATALOG.md` |
| İkinci VLM YOK → aynı modelin **faz-kaydırmalı** 2. koşusu | 7B ölçülmüş olarak zayıf; aynı aile bağımsızlık kanıtsız; faz-kaydırma 0 ek VRAM | `docs/KONSEY_2026-08-20.md` karar 2 |
| OCR **hakem değil tanık**; karantina **iki** olumsuz sinyal ister | tek sinyalle eleme, kayan/stilize jenerikte gerçek satırları yiyordu | konsey kararı 1 |
| Kanıt = metin + kare aralığı + **Y bandı** | uydurulan isim ekranın başka yerinde varsa salt metin eşleşmesi yanlış satırı KESİN yapar | konsey kararı 4 (GLM) |
| Zayıf kutu birleşimden dışlanmaz, **etiketlenir** | dışlama pastane'de 5 gerçek satırı kanıtsız bırakıyordu | `docs/OLCUM_OCR_RECALL.md` |
| OCR tanıyıcı: `latin_PP-OCRv5_mobile_rec` | genel v6 Türkçe'de `UČUR/MÜZiK`, Latin `UĞUR/MÜZİK` | `nash/config.yaml` |
| `E1` ızgarası 0.62–0.82 (0.90 DEĞİL) | ≥0.90'da OCR recall %61'e düşüyor → gerçek satır elenir | `docs/OLCUM_OCR_RECALL.md` |

## Ölçülenler (uydurma yok, hepsi koşuldu)

| ölçüm | sonuç | tarih |
|---|---|---|
| Qwen3-VL-8B kule içi, 8 kare × 720px | 2,2 sn üretim · **17,3 GB** VRAM tepe | 08-20 |
| Paddle satır-recall, marnali (262 kare) | **%96,1** (≥0.90) · **%100** (≥0.70) | 08-20 |
| Paddle satır-recall, pastane (180 kare) | **%61,0** (≥0.90) · **%91,5** (≥0.70) | 08-20 |

## TABAN ÇİZGİSİ — yenilecek sayı (Qwen3-VL-8B tek kanal, 2026-08-21 ölçüldü)

| film | F1 | kesinlik | duyarlılık | birebir | kayıp | **fazla** |
|---|---|---|---|---|---|---|
| suc_dosyasi | 0,970 | 0,942 | 1,000 | 79 | 0 | 5 |
| cennetin_cocuklari | 0,903 | 0,873 | 0,936 | 233 | 16 | 34 |
| dost_eller | 0,853 | 0,784 | 0,935 | 56 | 4 | 16 |
| gunes | 0,839 | 0,743 | 0,963 | 23 | 1 | 9 |
| pastane | **0,431** | 0,300 | 0,763 | 37 | 14 | 105 |
| marnali | **0,417** | 0,265 | 0,984 | 123 | 2 | **350** |
| **ortalama** | **0,735** | | | | | |

**Ölçümün söylediği — stratejiyi değiştiren bulgu:** duyarlılık zaten yüksek
(6 filmin 4'ünde ≥%93). Katil **kesinlik**: model GT'nin 2–4 katı satır
üretiyor. marnali'de 476 satırın hepsi **benzersiz** — tekrar değil mutasyon
(`ŞÜKRÜ TİRKİŞ`/`TIRKİŞ`/`TIRKIŞ`). Bu yüzden birincil kaldıraç bulanık
eleme değil, **kanıt çapasıyla kümeleme** (`docs/BIRLESTIRICI.md` adım 4b).

## Kırmızı çizgiler (kule bunları geçemezse başarısızdır)

1. **PASTANE çıktısında `Yılmaz Erdoğan` BULUNMAYACAK.** Mevcut 8B taban
   çizgisi bu ismi uydurup 10 kez tekrarlamış; ekranda hiç yok (gerçek:
   `TEOMAN TARHAN`). `docs/KANARYA_BULGULARI.md` bulgu 1.
2. Model reddi (`"There is no visible credit text…"`) kredi satırı sayılmayacak.
3. `ARIZA` asla `METIN_YOK`'a dönüşmeyecek; `_TAMAM` + bayat dosya bırakılmayacak.
4. Ölçüm yapılmadan hiçbir eşik/kanal "iyileştirme" sayılmayacak.

## Yerleşim

| ne | yol |
|---|---|
| sözleşme | `sozlesme.py` |
| CLI + bölüm yönlendirmesi (izolasyon burada) | `main.py`, `vince` |
| kare hazırlığı (tek görsel reçete) | `src/hazirlik.py` |
| VLM kanalı (faz 0 + faz K) | `src/kanal_vlm.py` |
| OCR tanık kanalı | `src/kanal_ocr.py` |
| kanıt tartısı | `src/birlestirici.py` *(Faz 3b — bekliyor)* |
| ölçüm yatağı + puanlayıcı | `olcum/` |
| çalışma zamanı | `venv/` (torch+transformers) · `venv_ocr/` (paddle) |
| modeller (kule içi kopya) | `model/qwen3-vl-8b` (17 GB) · `model/paddle/` (~150 MB) |

## Kurulum günlüğü

- **2026-08-20 gece:** plan + konsey turu + çalışma zamanı + iki ölçüm. Dört
  Sonnet ajanı paralel başlatıldı (Faz 0/1/2/3a).
- **2026-08-21 ~03:00:** dört ajan da **oturum limiti** yüzünden düştü. O anda
  hazır olan: sözleşme, `main.py`, `vince`, `src/hazirlik.py`, GT yatağı,
  78 test yeşil. Eksik: puanlayıcı, üç kanal modülü, birleştirici.
- **2026-08-21 05:26:** limit sıfırlandı, üç ajan **bağlamlarıyla** devam
  ettirildi (sıfırdan başlatmak yerine — bağlam yeniden türetilmesin).

## Açık borçlar

1. **`src/birlestirici.py` yazılmadı** — Faz 3b. Şartname: `docs/BIRLESTIRICI.md`.
2. **`E1`/`E2` kalibre edilmedi** — `config.yaml`'da `null`. Faz 4.
3. **Diakritik hakemi ölçülmedi** — üç ayar (`kapali`/`paddle_kirpim`/
   `vlm_kirpim`) GT yatağında koşulacak. **En büyük tekil skor kaldıracı.**
4. **Giriş bölümünün nicel GT'si yok.** Havuzdaki giriş kliplerinin
   `giris.txt`'leri boş; tek dolu GT (`cicek_taksi/giris`, 45 satır) için klip
   havuzda yok. Giriş, havuz B'nin 16 filminde **öz-tutarlılık + OCR destek
   oranı** ile doğrulanacak (GT'siz ölçüm) + gözle nokta denetimi.
5. **`gt_dizi/iz_pesinde/İZ PEŞİNDE ÇIKTI.txt` insan GT'si mi belirsiz** —
   8B/27B çıktılarıyla 86 satırın ~51'i ortak. Birincil yatağa ALINMADI;
   Çağatay'ın onayı bekliyor.
6. **`main.py toplu()` yalnız video tarar** — havuz B'nin 16 kare dizini için
   `start --kareler <dizin>` (alt dizinleri gez) yolu yok. Faz 3b'de eklenecek.
7. **Sahne yazısı (film içi metin) savunması yok** — pastane klibinin ilk
   4 sn'si jenerik değil, neon tabela; OCR de VLM de onu okuyor, kanıt
   birbirini doğruluyor. `sahne_riski` işareti tasarlandı, ölçülmedi.
