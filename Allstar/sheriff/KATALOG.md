# Sheriff dosya kataloğu

- `sheriff`, `main.py`: kamu CLI yüzeyi.
- `config.yaml`: fiziksel kule registry'si, DAG rolleri ve kaynak profilleri.
- `src/store.py`: SQLite/WAL durum makinesi.
- `src/engine.py`: DAG reconcile, scheduler, retry ve recovery.
- `src/media.py`: ffprobe, ses ve 2 fps bölüm havuzları.
- `src/resources.py`: canlı telemetri + deklaratif rezervasyon.
- `src/runner.py`: process-group yürütme, timeout, heartbeat ve peak ölçümleri.
- `src/adapters.py`: kamu CLI adaptörü ve sözleşme doğrulaması.
- `src/materialize.py`: Kobe'nin frame'leriyle birlikte `_sinif.json`
  zaman-serisi sözleşmesini LeBron input'una byte-aynı taşır; Jordan için
  kesintisiz/doğrulanmış frame havuzu üretir (sessiz klip geriye uyumludur).
- `src/contracts.py`: `mitas.okuma/v2` doğrulayıcı ve yardımcıları.
- `src/handoff.py`: Shaq inbox paketleyicisi.
- `schemas/`: okuma, frame, boundary, Jordan ve bundle sözleşmeleri.
- `tests/`: kontrol düzlemi, media, proof, handoff ve izolasyon kapıları.
- `state/`, `runs/`, `logs/`: çalışma zamanı verisi; git dışında tutulur.
