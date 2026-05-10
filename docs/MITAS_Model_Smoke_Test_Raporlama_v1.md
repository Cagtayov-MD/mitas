# MITAS Model Smoke Test Raporlama v1

## Amaç

Bu doküman Sprint 4.1 kapsamında model manifest adayları için smoke test runner raporlama davranışını tanımlar.

Bu görev benchmark değildir.
Model seçimi değildir.
Production ana motor seçimi değildir.
Video analizi değildir.

## Kapsam Dışı

- Model indirme
- Model kurma
- Benchmark çalıştırma
- OCR/ASR/Face/VisualTag pipeline yazma
- UI yazma
- Ana motor seçme

## Runner Davranışı

Runner dosyası:

```text
E:\MITAS\scripts\run_model_smoke_tests.py
```

Runner varsayılan olarak `dry_run` modunda çalışır.

Dry-run modunda:

- `model_manifest.yaml` okunur.
- Hiçbir `smoke_test_command` çalıştırılmaz.
- Her aday `planned` olarak raporlanır.
- `selected_as_engine` alanı değiştirilmez.

Real-run modunda:

- `--real-run` parametresi gerekir.
- `--timeout` parametresi desteklenir.
- Komut `python` ile başlıyorsa ilgili venv altındaki `python.exe` dikkate alınır.
- Aday bazında hata yakalanır.
- Hata bir adayı `failed` yapar ama runner’ın tamamını beklenmedik şekilde çökertmez.

## Rapor Alanları

Rapor dosyası:

```text
E:\MITAS\outputs\model_smoke_report.json
```

Alanlar:

- `run_mode`
- `candidate_count`
- `planned_count`
- `executed_count`
- `passed_count`
- `failed_count`
- `skipped_count`
- `timeout_count`
- `results`
- `status`

## Temel Güvenlik Kuralı

Runner hiçbir durumda manifest içindeki `selected_as_engine` alanını değiştirmez.

Benchmark öncesi tüm adaylar:

```yaml
selected_as_engine: false
```

olarak kalır.

## Son Karar

Sprint 4.1 smoke runner altyapısı dry-run güvenli varsayılanla hazırlanır.
Gerçek smoke komutları ancak açık `--real-run` parametresiyle çalıştırılır.
