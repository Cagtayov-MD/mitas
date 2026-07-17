# MITAS → Linux Geçiş Planı

> **Bu klasör nedir?** MITAS boru hattını Windows'tan tam bare-metal Linux'a taşımanın
> baştan sona tasarımı. Yeni PC'ye geçtiğinde **buradaki sıraya göre** hareket edersin.
> Her belge kendi başına okunabilir; hiçbir adım "detay sonra" bırakılmadı.

**Tasarım tarihi:** 2026-07-10 · **Kaynak makine:** Windows 10 Pro, `E:\MITAS` · **Hedef:** Ubuntu 24.04 LTS bare-metal

---

## Nasıl kullanılır

1. Önce **01 (Kararlar)** ve **04 (Faz Planı)** oku — neden ve hangi sırayla.
2. Yeni PC'de **10 (Kontrol Listesi)** açık dursun; fiziksel adımları oradan işaretle.
3. Her teknik iş için ilgili belgeye in (kod, venv, servis, OneOCR).
4. Her fazın sonunda **09 (Doğrulama)** kapısını geç; geçemezsen **geri-dönüş** koşulu aynı belgede.

## Temel ilke (tek cümle)

**Windows kurulumu, Linux tarafı bir üretim dalgasını temiz koşana kadar SİLİNMEZ.**
Geçiş "büyük patlama" değil; kanıt biriktikçe kayan, her adımı geri-alınabilir bir süreç.

---

## Belgeler

| # | Belge | İçerik |
|---|---|---|
| 00 | [INDEX](00_INDEX.md) | Bu dosya — harita + durum |
| 01 | [KARARLAR_VE_KISITLAR](01_KARARLAR_VE_KISITLAR.md) | Neyin neden böyle olduğu — bağlayıcı kararlar + global kısıtlar |
| 02 | [ENVANTER](02_ENVANTER.md) | Windows'a bağlı her nokta (dosya:satır) — "ne değişecek" defteri |
| 03 | [DONANIM_DISK_KURULUM](03_DONANIM_DISK_KURULUM.md) | Diskler, dağıtım seçimi, bölümleme, GPU/CUDA, NTFS mount, dizin düzeni |
| 04 | [FAZ_PLANI](04_FAZ_PLANI.md) | Aşamalı göç — doğrulama kapıları + geri-dönüş koşulları (omurga) |
| 05 | [KOD_DEGISIKLIKLERI](05_KOD_DEGISIKLIKLERI.md) | Dosya-dosya kod değişiklikleri, gerçek ikame koduyla |
| 06 | [VENV_KURULUM](06_VENV_KURULUM.md) | 18 venv'in Linux'ta yeniden kurulumu + duman testleri |
| 07 | [SERVISLER_SYSTEMD](07_SERVISLER_SYSTEMD.md) | start_mitas.ps1 + autostart + ollama + watchdog → systemd birimleri |
| 08 | [ONEOCR_IKAME](08_ONEOCR_IKAME.md) | OneOCR'ı Paddle/GLM ile değiştirme + golden-regresyon kapısı |
| 09 | [DOGRULAMA_GERI_DONUS](09_DOGRULAMA_GERI_DONUS.md) | Golden-regresyon protokolü, faz kapıları, geri-dönüş runbook'u |
| 10 | [KONTROL_LISTESI](10_KONTROL_LISTESI.md) | Yeni PC'de sırayla işaretlenecek ana liste |
| 11 | [DUAL_BOOT_KURULUM_RUNBOOK](11_DUAL_BOOT_KURULUM_RUNBOOK.md) | F diskine Ubuntu kurulumu, tıkla-tıkla (disk seri ...1976; Windows'a dokunmadan) |
| 12 | [WSL_F_SIFIRDAN_KURULUM](12_WSL_F_SIFIRDAN_KURULUM.md) | **AKTİF PLAN:** F'de WSL/Ubuntu + sıfırdan izole MITAS (kod+venv+model hepsi F'de, C/D/E'siz) + vLLM |

---

## Üretilmiş artefaktlar (F wipe'ından bağımsız, git'te durur)

- `reqs/*.txt` — 18 venv'in dondurulmuş paket reçetesi (Windows'ta çıkarıldı) ✓
- `mitas.env` — Linux ortam dosyası (yollar + üretim default'ları; sırlar placeholder) ✓
- `setup/install_mitas_linux.sh` — kurulum-sonrası otomatik MITAS hazırlığı (apt+pyenv+venv+env) ✓

---

## Durum takibi

Her faz bittiğinde buraya tarih yaz (yeni PC'de canlı tutulur):

- [ ] **Faz 0** — WSL porting laboratuvarı (yollar/API/venv/OneOCR köprüsü, golden WSL'de yeşil) · _tarih:_
- [ ] **Faz 1** — OneOCR ikamesi golden'da kanıtlandı (Paddle/GLM otorite) · _tarih:_
- [ ] **Faz 2** — Bare-metal Linux kuruldu (D diski, GPU/CUDA, mount'lar) · _tarih:_
- [ ] **Faz 3** — Cutover: bir üretim dalgası Linux'ta temiz koştu · _tarih:_
- [ ] **Faz 4** — Windows emekli + E/F diskleri ext4'e çevrildi · _tarih:_

---

## Özet karar

- **OneOCR bırakılıyor** (Paddle/GLM ikame) → uç durum: **tam bare-metal Linux, Windows gider.**
- **Dual-boot YOK** — mimariye uymuyor (bkz. 01). Ayrı-disk kurulum: her OS kendi diskinde, BIOS boot-menüsü seçer.
- **Diskler:** D → Linux OS+programlar · C → Windows (rollback, dokunulmaz) · E/F → geçişte NTFS mount, en son ext4.
- **Prova sahnesi hazır:** `Ubuntu-MITAS` WSL2 (Ubuntu 24.04, GPU geçişi çalışıyor, F:\wsl). Faz 0 orada, üretime sıfır dokunuş.
