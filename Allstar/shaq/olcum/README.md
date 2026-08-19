# Shaq ↔ HAKEEM ölçüm yatağı

Henüz insan etiketli gerçek veri ve `mitas.okuma/v1` paketi yoktur; ölçüm yokken
oran veya kazanan iddia edilmez.

`gt_ornek.json`, 100-film insan doğrusu için sözleşme örneğidir. Gerçek dosya
`gt_100.json` adıyla hazırlanabilir; motor çıktısından otomatik GT türetilmez.

```bash
Allstar/shaq/karsilastir on-kontrol --input /paketler
Allstar/shaq/karsilastir calistir --input /paketler --limit 100 --gt Allstar/shaq/olcum/gt_100.json
```

Raporlar varsayılan olarak `olcum/raporlar/` altına atomik yazılır. GT yoksa
yalnız operasyonel anlaşmazlık raporlanır. GT varsa seçim önceliği yanlış geçiş,
tam doğru bölüm ve gereksiz blok sırasıdır.
