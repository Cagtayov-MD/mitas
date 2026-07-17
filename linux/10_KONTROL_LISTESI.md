# 10 · Ana Kontrol Listesi

> Yeni PC'de **sırayla** işaretle. Her kutu bir eylem. Fiziksel/geri-alınamaz adımlar ⚠ ile
> işaretli — onlarda dur, iki kez düşün, yedeği doğrula. Detay için ilgili belgeye in.

---

## HAZIRLIK (ŞİMDİ, Windows'tayken yapılabilir — geçiş başlamadan)

- [ ] **Golden taban çizgisi al** (Windows referansı): `regresyon_golden.py --out golden_baseline_windows.json` → [09](09_DOGRULAMA_GERI_DONUS.md)
- [x] **18 venv reçetesini dondur**: her venv `pip freeze` → `linux/reqs/<profil>.txt` ✓ 2026-07-10 (Windows-özgü: oneocr/pywin32/win32_setctime işaretli) → [06·Adım1](06_VENV_KURULUM.md)
- [ ] **Üretim model listesini çıkar** (ollama etiketleri, HF model'leri) → [06·Adım5](06_VENV_KURULUM.md)
- [ ] **`mitas.env` taslağını yaz** (start_mitas.ps1 default'ları + yol tohumları + anahtarlar) → [05·Görev1](05_KOD_DEGISIKLIKLERI.md)
- [ ] Bu `linux/` klasörünü + reqs + golden baseline'ı git'e commit et (yeni PC'ye taşınacak)

---

## FAZ 0 — WSL laboratuvarı (üretime sıfır dokunuş)

- [ ] Kodu WSL ext4'e al (`~/mitas`, `/mnt/e` değil) → [04·Faz0](04_FAZ_PLANI.md)
- [ ] `mitas.env` (WSL yolları) yerleştir, `source` et
- [ ] Kod fix: yol-tohumları (Görev 2,3,10), Win-API (Görev 4,5,6), font (Görev 7), win32-bayrak (Görev 11) → [05](05_KOD_DEGISIKLIKLERI.md)
- [ ] `linux-port` dalını aç, fix'leri orada topla
- [ ] Venv kur: önce `core`, `ocr`, `asr` → [06](06_VENV_KURULUM.md)
- [ ] OneOCR **köprüsü** kur (Windows host servis + Linux istemci) → [08·YolA](08_ONEOCR_IKAME.md)
- [ ] Kalan 15 venv (kullanım sırasına göre)
- [ ] **KAPI 0:** `pytest tests/` + golden (köprü ile) yeşil → [09](09_DOGRULAMA_GERI_DONUS.md)
- [ ] Kapı geçince `linux-port` → `master` (KAPI 0 kanıtıyla)

---

## FAZ 1 — OneOCR ikamesi (hâlâ WSL)

- [ ] GLM-OCR ikamesini `raw_ocr_lines` yoluna tak (flag: `MITAS_OCR_ENGINE=glm`) → [08·YolB](08_ONEOCR_IKAME.md)
- [ ] PaddleOCR yedek dalını tak
- [ ] Golden ×3 motor koştur (oneocr-köprü / glm / paddle), ham-OCR + künye kararı karşılaştır
- [ ] Çok-script alt-kümesini ayrı ölç (FR-küçük / Arapça / Kiril)
- [ ] **KAPI 1 (K1-GATE):** ikame ≥ OneOCR, kayıp yok, OCR-otorite korundu → [08·K1-GATE](08_ONEOCR_IKAME.md)
- [ ] Geçerse: `MITAS_OCR_ENGINE` üretim default'ını ikameye çevir. Geçmezse: Branch A (köprü kalıcı) → [04·Faz1](04_FAZ_PLANI.md)

---

## FAZ 2 — Bare-metal kurulum (D diski)

- [ ] ⚠ **D diskini yedekle** (387 GB → F boşu veya harici, **E'ye ASLA**), yedeği DOĞRULA → [03](03_DONANIM_DISK_KURULUM.md)
- [ ] ⚠ D'yi formatla + Ubuntu 24.04 kur (ayrı-disk, GRUB Windows'a DOKUNMASIN) → [03·Boot](03_DONANIM_DISK_KURULUM.md)
- [ ] GPU sürücü (`ubuntu-drivers autoinstall`) + `nvidia-smi` doğrula (RTX 3090, 24 GB)
- [ ] Sistem paketleri: ffmpeg, tesseract, mscorefonts, ntfs-3g, pyenv+3.10.11 → [03](03_DONANIM_DISK_KURULUM.md)
- [ ] E/F NTFS mount (`/data/mitas`, `/data/mitas2`), `/etc/fstab`, UUID'ler → [03·Mount](03_DONANIM_DISK_KURULUM.md)
- [ ] Kodu `/opt/mitas`'a al, `mitas.env` (Linux yolları), HF/ollama model symlink'leri
- [ ] 18 venv'i kur (Faz 0 reçeteleriyle) → [06](06_VENV_KURULUM.md)
- [ ] Üretim model'lerini çek (`ollama pull ...`)
- [ ] systemd birimleri kur + enable (asr, tedial, ollama, webui, nöbetçi) → [07](07_SERVISLER_SYSTEMD.md)
- [ ] **KAPI 2:** `pytest`+golden yeşil; `reboot` sonrası servisler autostart; hız ölç (NTFS) → [09](09_DOGRULAMA_GERI_DONUS.md)

---

## FAZ 3 — Cutover

- [ ] Dalga takviminde pencere seç (iki koşu arası)
- [ ] Bir tam üretim dalgasını Linux'ta koştur (systemd servisleriyle)
- [ ] Çıktıyı Windows'un aynı-film geçmişiyle karşılaştır (karar/cast/PDF)
- [ ] **KAPI 3:** dalga hatasız + çıktı tutarlı + operatör rahat → [04·Faz3](04_FAZ_PLANI.md)
- [ ] Sorun çıkarsa: dalgayı Windows'ta yeniden koştur (C hazır), kök-neden gider → [09·Geri-Dönüş](09_DOGRULAMA_GERI_DONUS.md)

---

## FAZ 4 — Windows emekli + ext4

- [ ] Birkaç dalga Linux'ta temiz koştuğunu teyit et (acele etme)
- [ ] ⚠ E/F verisini sıralı taşı → bir disk ext4, veri ötekine, diğerini ext4 (**her adım doğrulanmış yedekle**) → [04·Faz4](04_FAZ_PLANI.md)
- [ ] `/etc/fstab` ext4'e güncelle
- [ ] **KAPI 4:** golden yeşil + ext4 hız kazancı ölçüldü (NTFS/Windows tabanına göre)
- [ ] C diskini cold-spare bırak (birkaç hafta), sonra istersen boşalt (onaylı)
- [ ] WSL'i kaldır (opsiyonel)
- [ ] `00_INDEX.md` durum takibini güncelle → tam-Linux ✓

---

## Altın kurallar (her fazda geçerli)

1. **C diski Faz 3 geçene kadar DOKUNULMAZ** — nihai emniyet ağı.
2. **Golden yeşil olmadan sonraki faza geçme** — "çalışıyor görünmek" kanıt değil.
3. **Hiçbir şey onaysız silinmez** — özellikle Faz 2 (D) ve Faz 4 (E/F) veri adımları.
4. **Göç davranış-nötr** — künye/cast/PDF çıktısı değişirse DUR, kök-neden bul.
5. **OneOCR kararı ölçüye bağlı** — K1-GATE geçmezse Branch A meşru sonuç, zorlama yok.
