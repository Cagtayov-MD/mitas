# Deneme Arşivi — master_dup

2026-08-11'de `harness/master_dup/` kökünden buraya taşınan, izlenmeyen
(untracked) deneme dosyaları. **Hiçbiri silinmedi**, yalnız üretim
dizininden ayrıldı: `master_dup/` kökü `master_png_monitor.py` tarafından
`sys.path`'e ekleniyor, dolayısıyla oradaki her modül bir import riski.

| Dosya | Tarih | Not |
|---|---|---|
| `lebron_james.py.backup_step1` | 07 Ağu 14:29 | LeBron ara-adım yedeği |
| `lebron_james_step1.py` | 07 Ağu 14:46 | LeBron ara-adım |
| `lebron_james_v2.py` | 07 Ağu 22:33 | LeBron v2 denemesi (en büyük/en yeni) |
| `benchmark_iyilestirmeler.py` | 30 Tem 13:50 | **SÖZDİZİMİ HATALI**: `import ibrahimovic as adaptif_slit as _m` (satır 82) — çalıştırılamaz |

## Neden taşındı

07 Ağustos'ta `lebron_james.py`'nin ÜRETİM dosyası kazara eski bir sürümle
ezilmişti: Madde 2 (CLI), 6 (hibrit keskinlik-kontrast), 7 (metin-dışı
segment filtresi), 9 (OCR hata log'u), 10 (manifest genişletme) kaybolmuştu.
Kanıt: o hâlde `tests/test_lebron_grup1.py` 2 test kırıyordu (madde_2, madde_10);
HEAD sürümünde 5/5 geçiyor. Üretim dosyası HEAD'e geri alındı.

Bu ara-sürümlerin üretim dizininde durması aynı karışıklığı tekrar davet
ediyordu — bu yüzden ayrıldılar.

## Geri almak isterseniz

```bash
mv _deneme_arsivi/<dosya> .
```

`lebron_james_v2.py` üzerinde çalışmaya devam edilecekse, üretime alınmadan
önce `tests/test_lebron_grup1.py`'nin 5/5 geçmesi beklenir.
