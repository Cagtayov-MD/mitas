# 09 · Doğrulama Protokolü + Geri-Dönüş Runbook'u

> Her fazın kapısı burada tanımlı test'lerle geçilir. "Çalışıyor görünmek" yetmez; kanıt
> golden'da. Geri-dönüş runbook'u: her faz için "sorun çıkarsa ne yapılır".

---

## Golden-regresyon protokolü

**Araç:** `scripts/regresyon_golden.py` (mevcut) + `tests/` + `scripts/run_model_smoke_tests.py`.

**Taban çizgisi (ŞİMDİ, Windows'ta al):** Göç başlamadan Windows üretiminde golden seti koştur,
çıktıyı dondur. Bu **referans** — Linux çıktısı buna karşı karşılaştırılır.

```powershell
# Windows'ta, göç öncesi referans:
& E:\MITAS\venvs\core\Scripts\python.exe E:\MITAS\scripts\regresyon_golden.py `
    --out E:\MITAS\linux\golden_baseline_windows.json
```

**Golden setin kapsamı** (örnek-bazlı, tek film yetmez):
- En az bir TR film, bir yabancı-dil (Fransızca/İtalyanca küçük-harf), bir Arapça/Kiril script.
- Bilinen zor vakalar: çok-satırlı yönetmen-kartı, nokta-dizili karakter-adı, footage-veto,
  cast sessiz-kayıp senaryoları (memory'deki aktif işlerden örnekler).
- Giriş + çıkış jeneriği ikisi de.

> **Uyarı (kunye.txt≠ham OCR tuzağı):** Karşılaştırmada LLM'e giden asıl kaynak `ocr_ham.txt`/
> `ocr_raw_all.txt`. Golden karşılaştırması ham-OCR seviyesinde DE yapılmalı, yalnız kunye.txt değil.

---

## Faz kapıları (özet — detay [04](04_FAZ_PLANI.md))

| Kapı | Test | Geçme ölçütü |
|---|---|---|
| **KAPI 0** | `pytest tests/` + golden (OneOCR köprü) | Windows ile aynı geçen/kalan; golden byte-eşleşme/açıklanmış fark |
| **KAPI 1** | golden ×3 motor (oneocr/glm/paddle) | ikame ≥ OneOCR; çok-script kayıp yok; OCR-otorite korundu |
| **KAPI 2** | bare-metal `pytest`+golden; reboot; hız | Faz 0 ile aynı sonuç; servisler autostart; hız tabana göre ölçüldü |
| **KAPI 3** | bir üretim dalgası | hatasız koştu; çıktı Windows-üretimiyle tutarlı; operatör rahat |
| **KAPI 4** | ext4 sonrası golden + hız | golden yeşil; ext4 hız kazancı ölçüldü |

**OS-özgü test'ler:** Bazı test'ler Windows-özgü olabilir (`test_prod_defaults_ps1_mirror.py`,
path-format test'leri). Bunları Linux'ta **işaretle ve beklenen-fark listesine yaz** — "kaldı"
sayma, "OS-özgü, Linux muadili X" diye açıkla.

---

## Byte-fark nasıl açıklanır

Golden'da fark çıkarsa, "kabul edilebilir mi" kararı:

| Fark türü | Kabul? | Aksiyon |
|---|---|---|
| Yol string'i (E:\ vs /opt) çıktıda | Evet | env doğru; çıktı-içi yol varsa göreli-yola çevir |
| Satır-sonu (CRLF vs LF) | Evet | metin çıktıları LF'e normalize et |
| Font-metrik (PNG/PDF piksel) | Dikkat | mscorefonts ile Arial birebir olmalı; değilse Görev 7 |
| Künye kararı / cast / isim farkı | **HAYIR** | kök-neden bul; göç davranış-nötr olmalı |
| Float/model determinizmi (LLM) | Ölç | seed/keep-alive aynı mı; OS kaynaklı değilse ayrı mesele |

---

## Geri-Dönüş Runbook'u (faz-faz)

### Faz 0 (WSL)
- **Risk:** sıfır (WSL izole, Windows üretimi hiç durmaz).
- **Sorun çıkarsa:** WSL'de teşhis et, düzelt, tekrar dene. Geçiş henüz başlamadı.

### Faz 1 (OneOCR ikame)
- **Sorun:** ikame golden'ı düşürüyor.
- **Geri-dönüş:** `MITAS_OCR_ENGINE=oneocr` (köprü) → Branch A. Windows host OneOCR servisi kalır.
  Karar ölçüye bağlı; zorlanan geçiş yok.

### Faz 2 (bare-metal kurulum)
- **Sorun:** kurulum/venv/servis Linux'ta yeşile gelmiyor.
- **Geri-dönüş:** Boot menüsünden **Windows disk'ine (C) boot et** — dokunulmadı, üretim aynen çalışır.
  Linux D'de izole; sınırsız deneme hakkı. C sağlam kaldıkça risk yok.

### Faz 3 (cutover)
- **Sorun:** dalga Linux'ta çöküyor / çıktı tutarsız.
- **Geri-dönüş:** O dalgayı **Windows'ta yeniden koştur** (C hazır). Linux'ta kök-nedeni gider.
  Windows en az bir başarılı Linux dalgasına kadar birincil.

### Faz 4 (ext4)
- **Risk:** en yüksek (veri-taşıma, geri-alınamaz).
- **Ön-koşul:** her disk çevriminden önce **doğrulanmış yedek** (silme yasağı: her adım onaylı).
- **Geri-dönüş:** C diski hâlâ cold-spare (birkaç hafta bekletilir) = nihai emniyet ağı.
  Veri kaybı riski varsa çevrimi durdur, yedekten dön.

---

## Öz-denetim

- Taban çizgisi Windows'ta ÖNCE alınıyor (referans olmadan karşılaştırma olmaz).
- Ham-OCR seviyesi karşılaştırması dahil (kunye.txt tuzağı).
- Her fazın geri-dönüşü somut ve C-diski emniyet ağı Faz 4'e kadar korunuyor (K4 ile tutarlı).
- Byte-fark tablosu davranış-nötr ilkesini uyguluyor (künye/cast farkı kabul EDİLMEZ).
