# 11 · Dual-Boot Kurulum Runbook'u (F diski)

> Ubuntu 24.04'ü F diskine (ayrı disk, Windows'a dokunmadan) kurmanın tıkla-tıkla rehberi.
> Fiziksel adımlar SENDE; her adım tam yazıldı. En kritik risk kalın: **YANLIŞ DİSKE KURMA.**

---

## ⚠ ÖN-GÜVENLİK — En kritik nokta

Makinede **iki adet 1.8 TB Samsung 970 EVO Plus** var. Kurulumda ikisi de aynı görünür.
Seri numarasıyla ayırt et:

| Disk | Rol | Seri no (son 4) | Linux'ta kontrol |
|---|---|---|---|
| **F (disk 3)** | **LINUX BURAYA** | **...1976** | `lsblk -o NAME,SIZE,SERIAL` → 1976 olan |
| **E (disk 2)** | **MITAS VERİSİ — ELLEME** | ...19BF | 19BF olan → ASLA seçme |
| C (disk 0) | Windows | ...D34E | 500 GB, elleme |
| D (disk 1) | veri | ...D352 | 500 GB, elleme |

**Çifte emniyet:** F'yi tamamen boşalttıysan, kurulumda F **tamamen boş (unallocated)** görünür;
E ise **dolu NTFS bölümü** gösterir. Hem seri **1976** hem **boş olan** → doğru disk. İkisi
uymuyorsa DUR.

---

## Adım 0 — Windows tarafı hazırlık (kurulumdan ÖNCE)

1. **F'yi tamamen boşalt + doğrula** (yapıyorsun). Boşaldığında Windows'ta F sürücüsü boş olmalı.
2. **Fast Startup'ı KAPAT** (dual-boot için şart — açık kalırsa Windows diskleri kilitli-hibernate
   bırakır, Linux NTFS'i güvenli mount edemez, boot sorunları çıkar):
   `Denetim Masası → Güç Seçenekleri → Güç düğmelerinin yapacaklarını seçin → "Şu anda kullanılamayan
   ayarları değiştir" → "Hızlı başlatmayı aç" işaretini KALDIR → Kaydet.`
3. **BitLocker kontrolü:** C: BitLocker ile şifreliyse, dual-boot recovery-key isteyebilir.
   `manage-bde -status C:` → şifreliyse kurtarma anahtarını yanına al (veya geçici askıya al).
4. **BIOS/UEFI notu:** Secure Boot açık kalabilir (Ubuntu 24.04 destekler). Sorun çıkarsa geçici kapat.

---

## Adım 1 — Ubuntu 24.04 USB'si yap

1. **ISO indir:** https://ubuntu.com/download/desktop → Ubuntu 24.04 LTS (WSL'deki ile aynı sürüm).
2. **USB'ye yaz** (≥8 GB USB):
   - **Rufus** (https://rufus.ie) veya **balenaEtcher** (https://etcher.balena.io)
   - ISO seç → USB seç → Yaz. (Rufus'ta "GPT / UEFI" modu.)
3. USB'yi tak, makineyi yeniden başlat.

---

## Adım 2 — USB'den boot et

1. Açılışta **boot-menü tuşuna** bas (marka-göre: F8/F11/F12/Esc — açılış ekranında yazar).
2. Boot listesinden **USB'yi (UEFI: <USB adı>)** seç.
3. Ubuntu ekranında **"Try or Install Ubuntu"** → **Install**.
4. İlk ekranlar: Dil, Klavye (Türkçe), Ağ (Wi-Fi/Ethernet bağla — sürücü/paket için lazım).
5. "Kurulum türü" ekranına gelene kadar normal ilerle (Normal kurulum + "üçüncü taraf sürücüler"
   işaretle → NVIDIA sürücüsü otomatik gelsin).

---

## Adım 3 — ⚠ Bölümleme (EN DİKKATLİ ADIM)

1. "Kurulum türü" ekranında **"Başka bir şey" / "Manuel" / "Something else"** seç. ("Diski sil ve
   Ubuntu kur"u SEÇME — o hangi diski sileceğini sormaz, riskli.)
2. Disk listesinde **seri/boyuttan F diskini bul** (boş, ~1.8 TB, seri ...1976). E'yi (dolu NTFS,
   ...19BF) **görmezden gel.**
3. F diskinde (tamamen boş alan üzerinde) şu bölümleri oluştur (`+` ile):

   | Bölüm | Boyut | Tip | Bağlama / kullanım |
   |---|---|---|---|
   | EFI | **1024 MB** | EFI Sistem Bölümü | (boot) |
   | swap | **32768 MB** | takas alanı (swap) | — |
   | kök | **kalan (~1.8 TB)** | Ext4 | bağlama noktası **`/`** |

   > İstersen kökü ~500 GB tutup gerisini ayrı bir ext4 `/data`'ya ayırabilirsin; ama F tümüyle
   > Linux olduğundan tek büyük `/` en basiti (MITAS + modeller + test hepsi içeri sığar).

4. **⚠ EN KRİTİK SATIR — "Önyükleyici kurulacak aygıt" (Device for boot loader installation):**
   Bunu **F diskinin kendisine** ayarla (seri ...1976 olan `/dev/nvme?n?`) — **Windows diskine
   (C) ASLA.** Böylece GRUB Windows açılışına dokunmaz; C bağımsız kalır.

5. "Şimdi Kur" → değişiklikleri onayla (yalnız F diskinde yazma olduğunu ekrandan teyit et).

---

## Adım 4 — Kurulumu bitir + ilk boot

1. Saat dilimi (İstanbul), kullanıcı adı/parola → kur.
2. Bitince USB'yi çıkar, yeniden başlat.
3. **Boot seçimi:** UEFI boot-menüsünden (F-tuşu) hangi diske gideceğini seç: **F=Linux**, **C=Windows**.
   (GRUB de her ikisini listeleyebilir; ama boot-menü yöntemi bootloader'ları ayrı tutar = en güvenli.)
4. Windows'a dönüşü test et: yeniden başlat → boot-menü → Windows disk → Windows sorunsuz açılmalı.
   (Bu, "Windows bozulmadı" kanıtı.)

---

## Adım 5 — İlk Linux açılışı: sürücü + temel

```bash
sudo ubuntu-drivers autoinstall     # NVIDIA 560+ sürücü
sudo reboot
nvidia-smi                          # doğrula: RTX 3090, 24576 MiB
sudo apt update && sudo apt install -y \
    ffmpeg tesseract-ocr tesseract-ocr-tur build-essential git curl \
    ttf-mscorefonts-installer fonts-liberation ntfs-3g
```

- **E/F NTFS erişimi (gerekirse):** MITAS verisi/modelleri E veya D'de NTFS'te; Linux `ntfs3` ile
  okur. `/etc/fstab` mount'ları için → [03·Mount](03_DONANIM_DISK_KURULUM.md). (F artık Linux
  diski olduğundan veri E/D'den okunur; ya da modeller ext4'e kopyalanır.)

---

## Adım 6 — MITAS kurulumu (buradan sonrası yazılım)

Sistem hazır. MITAS'ı kurmak için sırayla:
- pyenv + Python 3.10.11 → [03](03_DONANIM_DISK_KURULUM.md)
- Kodu `/opt/mitas`'a al + `mitas.env` → [05·Görev1](05_KOD_DEGISIKLIKLERI.md)
- 18 venv (Faz 0 reçeteleriyle) → [06](06_VENV_KURULUM.md)
- Kod fix'leri (yol/API/font) → [05](05_KOD_DEGISIKLIKLERI.md)
- OneOCR ikamesi → [08](08_ONEOCR_IKAME.md)
- systemd servisleri → [07](07_SERVISLER_SYSTEMD.md)
- Golden-regresyon (KAPI 2) → [09](09_DOGRULAMA_GERI_DONUS.md)

> **Not:** Bu yazılım adımlarının çoğu Faz 0'da WSL'de önceden hazırlanıp kanıtlanır; buraya
> taşındığında "kur + doğrula" işine iner. Linux içindeki bir Claude oturumu bunları scriptle
> uçtan uca yürütebilir.

---

## Geri-dönüş

- Kurulum bozulursa / boot sorunları: **boot-menüden C diskine (Windows) boot et** — dokunulmadı,
  aynen çalışır. F'yi silip baştan kur. C sağlam = risk yok.
- GRUB yanlışlıkla Windows açılışını ezmişse (Adım 3.4'e uyulmadıysa): Windows kurtarma USB'si ile
  `bootrec /fixboot` — ama Adım 3.4'e uyduysan bu olmaz.
