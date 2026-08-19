# Sheriff durum kaydı

Tarih: 2026-08-17

## Tamamlanan

- Bağımsız `Allstar/sheriff` kontrol düzlemi ve CLI.
- SQLite/WAL film, run, DAG, task, dependency, attempt, artifact, reservation ve event modeli.
- Bölüm bazlı giriş/çıkış DAG'ı, idempotency, retry, lease/heartbeat ve instance kilidi.
- Shellsiz, atomik 4/8 dakika media prep; WAV ve frame JSONL kanıtı.
- Config-driven kule registry ve process-group runner.
- Canlı RAM/CPU/disk/NVIDIA telemetrili rezervasyon scheduler'ı.
- `mitas.okuma/v2`, frame ve Shaq bundle şemaları.
- LeBron RLE source-row provenance ve additive grounding proof.
- Nash selected-frame additive grounding proof.
- Jordan için dürüst `proof=NONE` v2 zarfı.
- Self-contained, hash doğrulamalı, atomik üç-kanal Shaq handoff.
- Birim/regresyon testleri ve eski pipeline import denylist'i.
- Aktif Kobe giriş motoru ve rol sözlüğünün Allstar içine alınması; aktif kodda
  `core/`, `scripts/` ve `mitas_pipeline` import'u kalmaması.
- Attempt-scoped kule çıktıları, sürekli lease recovery ve yetim rezervasyon temizliği.
- Kod/config hash'li pipeline kimliği ve çalışma anında sürüm sapması kapısı.
- Frame PTS tabanlı zaman haritası; pipe-buffer kilitlenmesine dayanıklı ffmpeg runner.
- Uygulanabilir 22.000 MB OOM-exclusive rezervasyonu ve dış GPU yükünde küçük
  işlerin gereksiz bekletilmemesi.
- `proof=COMPLETE` için bbox + kaynak frame + timecode zorunluluğu.
- Frame/manifest/klip girdilerinin upstream görev hash'ine başlamadan önce,
  tamamlandıktan sonra ve crash recovery sırasında yeniden bağlanması.
- `doctor` içinde bütün aktif kule venv pinlerinin kurulu paketlerle birebir
  karşılaştırılması; LeBron'un çalışan Torch 2.11 / Transformers 4.46.3
  ortamıyla çelişen eski pinlerin düzeltilmesi.
- CPU rezervasyonlarının ffmpeg ve yaygın BLAS/OMP runtime thread sınırlarına
  uygulanması; GPU-hazır iş önceliği ve hafif handoff kaynak profili.
- LeBron layout satırlarında taşınabilir `source_asset_id` bağı ve ilk handoff
  yayınının `_TAMAM` öncesi uçtan uca tekrar doğrulanması.

## Bilinçli açık işler / devreye alma kapıları

- Jordan'ın exact frame + bbox lokalizasyonu henüz yoktur.
- Shaq/Hakeem'in üç okuyuculu karar politikası henüz yoktur ve otomatik başlamaz.
- Gerçek modelle tek-film bbox overlay insan kontrolü yapılmadı.
- 5-film restart/force-stop/OOM tatbikatı yapılmadı.
- 25-film kayıp/OOM/tekrar/scheduler-utilization pilotu yapılmadı.
- Sheriff bugün her bölüm/görev için kuleyi yeni subprocess olarak açar; model
  cold-start maliyeti 25-film pilotunda ölçülmeden kalıcı worker servisine
  geçilip geçilmeyeceği kararlaştırılmayacaktır.
- Model config/index kimliği pipeline hash'ine girer; çok-gigabayt ağırlıkların
  tam içerik SHA-256 doğrulaması henüz başlangıç kapısına eklenmedi.
- Scheduler olayları ve peak metrikleri tutulur; 25-film kabul kapısındaki
  yüzde-10 GPU boşluk raporu henüz otomatik bir rapor komutuna dönüştürülmedi.
- Bu kapılar tamamlanmadan eski sistem durdurulmayacak veya arşive alınmayacaktır.
