# 01 · Kararlar ve Global Kısıtlar

> Bağlayıcı kararlar ve nedenleri. Bir faz sırasında "acaba şöyle mi yapsak" dediğinde
> önce buraya bak — çoğu alternatif burada zaten elenmiş. Yeni bir kanıt bir kararı
> çürütürse, kararı **burada güncelle** (tarihini yaz), koda dokunmadan önce.

---

## K1 — OneOCR bırakılıyor (Paddle/GLM ikame)

**Karar:** OneOCR (Windows-only Microsoft OCR) üretimden çıkarılacak; yerini PaddleOCR veya
GLM-OCR alacak.

**Neden:** OneOCR tek gerçek Windows bağıydı. In-process import ediliyor ve şu an **ham-OCR
otoritesi** (künyenin LLM'e giden asıl kaynağı). Bırakılırsa Windows'a hiçbir zorunlu bağ
kalmaz → temiz tam-Linux mümkün olur.

**Kapı (K1-GATE):** İkame, OneOCR'ın yerine geçmeden önce **golden-regresyon setinde otorite
olarak birebir kanıtlanmalı.** OneOCR çok-script native okuması (Latin/Fransızca-küçük-harf/
Arapça/Kiril) yüzünden seçilmişti; ikamenin bu kapsamı düşürmediği ÖLÇÜLECEK. Detay: [08](08_ONEOCR_IKAME.md).

**Aday:** GLM-OCR (VLM-credit-OCR bench'ini kazanmıştı: hızlı/temiz). PaddleOCR ikinci aday
(zaten kurulu, deterministik). Nihai seçim K1-GATE ölçümüyle.

---

## K2 — Uç durum: tam bare-metal Linux (Windows gider)

**Karar:** K1 sonrası pipeline'ın Windows'a zorunlu bağı kalmadığından, hedef mimari **tam
bare-metal Ubuntu 24.04 LTS**. WSL veya kalıcı Windows host DEĞİL.

**Neden:** Asıl verim kazançları (küçük-dosya I/O = frame havuzları, süreç yönetimi
stabilitesi, systemd/cgroup ile llama-server kilit sınıfının yok olması) bare-metal'de gerçekleşir.
WSL yalnızca **prova** için (doğruluk testi), nihai üretim için değil.

---

## K3 — Dual-boot ELENDİ

**Karar:** Klasik (paylaşımlı-disk, GRUB) dual-boot KULLANILMAYACAK.

**Neden:** Dual-boot aynı anda tek OS çalıştırır. Geçiş fazında iki OS'a **aynı anda** ihtiyaç
olabilir (Windows rollback + Linux prova), ve GRUB'un Windows bootloader'ını yeniden yazması
gereksiz risk. Bunun yerine **ayrı-disk kurulum**: her OS kendi fiziksel diskinde, boot'ta
UEFI/BIOS boot-menüsünden (F-tuşu) disk seçilir. Bootloader'lar birbirine dokunmaz →
geri-dönüş = öbür diske boot et.

**Not:** K1 tamamlanınca OneOCR bağı bittiğinden zaten "neden dual-boot, direkt tam Linux"
noktasına gelinir; dual-boot bu mimaride hiçbir aşamada kazanç getirmiyor.

---

## K4 — Aşamalı geçiş, geri-alınabilir

**Karar:** Beş faz (Faz 0–4, bkz. [04](04_FAZ_PLANI.md)). Her fazın bir **doğrulama kapısı**
ve bir **geri-dönüş koşulu** var. Windows, Faz 3 (bir üretim dalgası Linux'ta temiz) geçene
kadar silinmez.

**Neden:** MITAS canlı üretimde (dalga koşuları sürüyor, TRT makinesi). Kanıtlanmamış bir OS'a
tek hamlede üretim teslim etmek kabul edilemez. "Dolu≠doğru" ilkesi: Linux'ta "çalışıyor
görünmek" yetmez, golden'da kanıtlanmalı.

---

## K5 — WSL prova sahnesi olarak kullanılıyor (Faz 0)

**Karar:** Mevcut `Ubuntu-MITAS` WSL2 dağıtımı porting laboratuvarı. Yol/API düzeltmeleri,
venv kurulumları, OneOCR ikamesi ve golden-regresyon önce burada koşulur.

**Neden:** Zaten kurulu (Ubuntu 24.04, GPU geçişi çalışıyor, `F:\wsl\Ubuntu-MITAS`, vllm-venv
mevcut). Faz 0 işinin ~%90'ı bare-metal'e birebir taşınır (yol/env/API fix, venv reçeteleri,
golden). Üretim Windows'a sıfır dokunuş. Diskler dolu (C %96, E %97) — WSL hiçbir diski
boşaltmayı gerektirmiyor, F'de 528 GB boş var.

**Uyarı:** WSL'den `/mnt/e` (Windows NTFS) I/O YAVAŞ. Faz 0'da doğruluk test edilir; **hız
ölçümü** WSL'de yapılmaz (yanıltıcı olur) — hız kanıtı Faz 2 bare-metal'de alınır.

---

## Global Kısıtlar

Her fazın ve her görevin gereklilikleri bunları **kapsar** (tekrar yazılmaz):

| Kısıt | Değer | Kaynak |
|---|---|---|
| Dağıtım | Ubuntu 24.04 LTS (WSL ile aynı) | K2/K5 |
| Python | **3.10.11** (tüm 18 venv bu sürümde) | `venvs/*/pyvenv.cfg` |
| GPU | NVIDIA RTX 3090 24 GB, sürücü ≥ 560.x | donanım |
| CUDA | 12.x (torch ile uyumlu wheel) | 06 |
| Windows disk (C) | Faz 3 geçene kadar DOKUNULMAZ | K4 |
| Veri diskleri (E/F) | Faz 4'e kadar NTFS mount; veri TAŞINMAZ | K3/03 |
| OCR-otorite kanunu | OCR ne okursa o; gelen veri OCR'i EZMEZ | proje kuralı |
| Golden-regresyon | Her faz kapısında ZORUNLU; byte-fark açıklanmalı | K4/09 |
| Değişiklik disiplini | Pipeline davranışı yalnız talimatla değişir; göç **davranış-nötr** olmalı | proje kuralı |
| Silme yasağı | Hiçbir veri/dizin otonom silinmez; her silme onaylı | proje kuralı |

**Kritik değişmez:** Bu göç bir **davranış-nötr taşıma**. Linux çıktısı Windows üretim
çıktısıyla golden sette birebir eşleşmeli (tek meşru fark: OneOCR→ikame, o da K1-GATE'te
ayrıca ölçülür). Yol/OS değişikliği künye kararını, cast'i, PDF'i DEĞİŞTİRMEMELİ.
