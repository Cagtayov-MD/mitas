# 04 · Faz Planı (Omurga)

> Beş faz. Her fazın **çıktısı**, **doğrulama kapısı** ve **geri-dönüş koşulu** var. Kapıyı
> geçmeden sonraki faza geçme. Windows, Faz 3 geçene kadar silinmez (Global Kısıt K4).

```
Faz 0 ─ WSL porting laboratuvarı        (üretime SIFIR dokunuş, hiçbir disk boşaltılmaz)
  │       └─ KAPI 0: golden WSL'de yeşil (OneOCR köprüsü ile)
Faz 1 ─ OneOCR ikamesi (Paddle/GLM)     (hâlâ WSL'de)
  │       └─ KAPI 1 (K1-GATE): ikame golden'da otorite olarak kanıtlı
Faz 2 ─ Bare-metal Linux kurulumu       (D diski; C/E/F dokunulmaz)
  │       └─ KAPI 2: golden bare-metal'de yeşil + hız ölçümü
Faz 3 ─ Cutover                          (bir üretim dalgası Linux'ta)
  │       └─ KAPI 3: dalga temiz koştu, çıktı Windows-üretimiyle tutarlı
Faz 4 ─ Windows emekli + ext4            (E/F yeniden formatlanır)
          └─ KAPI 4: tam-Linux, ext4 hız kazancı ölçüldü
```

Bu sürede paralel çalışan iki iş var: **sen** diski hazırlarsın (Faz 2 fiziksel), **kod tarafı**
(Faz 0–1) WSL'de üretime dokunmadan ilerler.

---

## FAZ 0 — WSL Porting Laboratuvarı

**Amaç:** "Pipeline Linux'ta doğru çalışıyor mu?" sorusunu üretime hiç dokunmadan yanıtla.

**Nerede:** Mevcut `Ubuntu-MITAS` WSL2 (F:\wsl, GPU geçişi çalışıyor).

**Adımlar:**
1. Kodu WSL ext4'e klonla (`/mnt/e`'de DEĞİL — I/O yavaş): `git clone` veya `cp` → `~/mitas`.
2. `mitas.env` dosyasını yaz (tüm `MITAS_*` yolları Linux'a) — [02·A1](02_ENVANTER.md).
3. Yol-tohumu olmayan sabit yolları düzelt — [05](05_KOD_DEGISIKLIKLERI.md) Görev 1-3.
4. Windows-API 3 noktasını düzelt (meminfo, pkill, ollama) — [05](05_KOD_DEGISIKLIKLERI.md) Görev 4-6.
5. Fontları ayarla — [05](05_KOD_DEGISIKLIKLERI.md) Görev 7.
6. 18 venv'i kur (öncelik: `core`, `ocr`, `asr`) — [06](06_VENV_KURULUM.md).
7. **OneOCR köprüsü** kur (Windows host'ta OneOCR HTTP servisi, WSL çağırır) — [08·Köprü](08_ONEOCR_IKAME.md).
   Bu, Faz 0'da OneOCR'ı olduğu gibi bırakıp pipeline'ın geri kalanını Linux'ta koşturmayı sağlar.
8. `tests/` + `scripts/regresyon_golden.py` + `scripts/run_model_smoke_tests.py` çalıştır.

**KAPI 0 (geç/kal):**
- [ ] `pytest tests/` — Windows'taki ile aynı geçen/kalan sayısı (OS-özgü test'ler hariç, işaretle).
- [ ] `regresyon_golden.py` — golden set çıktısı Windows üretimiyle **byte-eşleşme** veya **açıklanmış fark**.
- [ ] Smoke: en az 3 tam film (TR + yabancı-dil) uçtan uca koşar, künye/cast/PDF üretir.

**Geri-dönüş:** Faz 0 yıkıcı değil (WSL izole). Kapı geçilemezse Windows üretim etkilenmez;
kök-nedeni WSL'de teşhis et, düzelt, tekrar dene. Windows'a geçiş BAŞLAMADIĞI için risk sıfır.

**Süre tahmini:** En büyük kalem 18 venv + duman test (günler). Yol/API fix mekanik (saatler).

---

## FAZ 1 — OneOCR İkamesi

**Amaç:** OneOCR bağını kopar — Paddle/GLM'i ham-OCR otoritesi yap, golden'da kanıtla.

**Nerede:** Hâlâ WSL (köprü yerine yerel ikame denenir).

**Adımlar:** [08](08_ONEOCR_IKAME.md)'in tamamı. Özet:
1. İkame OCR motorunu (GLM-OCR öncelik, Paddle yedek) `_pipe_ocr.py` ham-OCR yoluna tak (flag arkası).
2. Golden setin her filminde eski (OneOCR-köprü) vs yeni (ikame) ham-OCR satırlarını karşılaştır.
3. Çok-script kapsama ölç (Latin/FR-küçük/Arapça/Kiril) — regresyon var mı?

**KAPI 1 (K1-GATE — bağlayıcı):**
- [ ] İkame, golden künye kararında OneOCR-köprü ile **eşdeğer veya daha iyi** (kayıp yok).
- [ ] Çok-script kapsama düşmedi (ölçülü, örnek-bazlı — tek film "tamam" demez).
- [ ] "OCR-otorite kanunu" korundu: ikame ne okursa o; gelen veri ezmiyor.

**Geri-dönüş:** İkame golden'ı düşürüyorsa → OneOCR köprüsüyle devam (Faz 0 durumu), Windows
host'u OneOCR servisi olarak kalıcı tut. Bu durumda K2 "tam-Linux" yerine "Linux ana + Windows
OneOCR servisi"ne düşer (bkz. 01·K1 Branch A). Karar tamamen ölçüye bağlı.

---

## FAZ 2 — Bare-metal Linux Kurulumu

**Amaç:** Gerçek üretim ortamını kur — D diskine Ubuntu, GPU/CUDA, mount'lar, servisler.

**Ön-koşul:** KAPI 0 ve KAPI 1 geçmiş (kod Linux'ta kanıtlı). D diski yedeklenmiş ([03](03_DONANIM_DISK_KURULUM.md)).

**Adımlar:**
1. D'yi yedekle + doğrula (fiziksel onay kapısı, [10](10_KONTROL_LISTESI.md)).
2. Ubuntu 24.04 D diskine kur (ayrı-disk, GRUB Windows'a dokunmaz — [03](03_DONANIM_DISK_KURULUM.md)).
3. GPU sürücü + CUDA + sistem paketleri.
4. E/F NTFS mount (`/data/mitas`, `/data/mitas2`).
5. Kodu `/opt/mitas`'a al, `mitas.env` yerleştir.
6. 18 venv'i kur (Faz 0 reçeteleriyle — artık kanıtlı) — [06](06_VENV_KURULUM.md).
7. systemd birimleri kur (asr, tedial, ollama, watchdog, autostart) — [07](07_SERVISLER_SYSTEMD.md).

**KAPI 2 (geç/kal):**
- [ ] `pytest tests/` + `regresyon_golden.py` bare-metal'de yeşil (Faz 0 ile aynı sonuç).
- [ ] Servisler systemd ile ayağa kalkıyor, reboot sonrası autostart çalışıyor.
- [ ] **Hız ölçümü:** frame-havuzu I/O ve film/saat, Windows üretim taban değeriyle karşılaştır
      (NTFS mount'ta — Faz 4'te ext4 ile tekrar ölçülecek).

**Geri-dönüş:** Sorun çıkarsa boot menüsünden Windows'a dön (C dokunulmamış). Linux D'de izole;
Windows üretimi hiç durmadı. Teşhis et, düzelt, KAPI 2'yi tekrar dene.

---

## FAZ 3 — Cutover

**Amaç:** Gerçek bir üretim dalgasını Linux'ta koştur; Windows'u yalnız rollback olarak beklet.

**Ön-koşul:** KAPI 2 geçmiş.

**Adımlar:**
1. Dalga takvimine göre uygun bir pencere seç (iki koşu arası).
2. Bir tam dalgayı Linux'ta koştur (üretim ayarlarıyla, `start_mitas` systemd karşılığı).
3. Çıktıyı (künye, cast, PDF, ONAYLI/KONTROL kararları) Windows'un aynı-film geçmişiyle karşılaştır.

**KAPI 3 (geç/kal):**
- [ ] Dalga uçtan uca hatasız koştu (servis çökme yok, LLM/ollama stabil).
- [ ] Çıktı Windows-üretimiyle tutarlı (kararlar, cast sayıları, PDF format — açıklanmamış fark yok).
- [ ] Operatör (sen) Linux ortamında rahat: log'lar, izleme, karar-günlüğü, WebUI çalışıyor.

**Geri-dönüş:** Dalga Linux'ta sorun çıkarırsa → o dalgayı Windows'ta yeniden koştur (C hazır),
Linux'ta kök-nedeni gider. Windows en az bir başarılı Linux dalgasına kadar **birincil** kalır.

---

## FAZ 4 — Windows Emekli + ext4

**Amaç:** Windows'u kaldır, veri disklerini ext4'e çevir, asıl I/O hız kazancını al.

**Ön-koşul:** KAPI 3 geçmiş — **en az bir (tercihen birkaç) dalga Linux'ta temiz koşmuş.**

**Adımlar:**
1. E/F NTFS verisini geçici olarak boşalt (Linux OS diskine sığmaz → dikkatli sıralı taşıma:
   bir diski ext4'e çevir, veriyi ötekine, sonra diğerini çevir). **Silme yasağı: her adım onaylı.**
2. E → ext4, F → ext4. `/etc/fstab` güncelle.
3. Windows disk'i (C): önce cold-spare olarak bırak (birkaç hafta), sonra istersen boşalt.
4. WSL artık gereksiz (isteğe bağlı kaldır).

**KAPI 4 (bitiş):**
- [ ] Tüm veri ext4'te, mount'lar sağlam, golden hâlâ yeşil.
- [ ] **Hız kazancı ölçüldü:** frame-havuzu I/O ve film/saat, Faz 2 (NTFS) ve Windows tabanına göre.
- [ ] Sistem tam-Linux, systemd-yönetimli, stabil.

**Geri-dönüş:** Bu faz veri-taşıma içerdiğinden en riskli. Her disk çevriminden önce **doğrulanmış
yedek** şart. C diski hâlâ cold-spare olduğu için nihai emniyet ağı orada.
