# Kobe kulesi — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Her iş biriminden sonra güncellenir ve commit'lenir.
> Plan: `docs/superpowers/plans/2026-08-12-allstar-kobe-kulesi.md`
> Spec: `docs/superpowers/specs/2026-08-12-allstar-kobe-kulesi-design.md`

**Son güncelleme:** 2026-08-13 00:05

---

## Değişmez kurallar (her oturumda geçerli)

- **`ollama.service` DURDURULMUŞ kalır.** Ölçüm kapıları buna bağlı; açılırsa
  skor ~%93.6'ya iner ve kapı sahte alarm verir. Her ölçümden önce
  `systemctl is-active ollama` → `inactive` doğrula.
- **`git add -A`, `git add .`, `git reset --hard`, `git stash` YASAK.** Ağaçta
  bu işe ait olmayan 9 değişik + 68 silinmiş (`mutfak/`) dosya var. Yalnız adı
  geçen yolları sahnele.
- **Üretim durmuş.** Hiçbir toplu koşu başlatma.
- Ölçüm referansı: **kapsam 110, doğru 104, genel %94.5, üretim %97.3,
  kredi-var 75/81, kredi-yok 29/29, eksik 5**.
- Ölçüm komutu (~140 sn):
  `cd /opt/mitas/Allstar/kobe/olcum && <python> olc_pool.py --paralel 8`

---

## Tamamlanan

| # | İş | Kanıt |
|---|---|---|
| 1 | Ölçüm ÖNCE + geri-dönüş noktası | `raporlar/olcum_ONCE.json`, commit `d497bdb0` |
| 2 | Kendi çalışma zamanı (`venv/`, 7 GB, paddle 3.3.1+CUDA) | `venv_kur.sh`, commit `9f24a769` |
| 4 | Dosya taşıma + import yolları + `figo` adının silinmesi | commit `3577c8b9` |
| 5 | Testler kule içine taşındı | 19/19 geçiyor |
| 6 | **TAŞIMA KAPISI GEÇTİ** — yeni yol + eski venv = %94.5, sapma sıfır | `raporlar/olcum_SONRA_tasima.json`, commit `a875b43d` |

## Açık kusur — ÖNCELİK 1

**Kobe kendi `venv/`'iyle %92.7 veriyor (%94.5 değil).** İki film doğru →
`KREDI_YOK` oluyor: `MELEKLERİ_GÖRMEK_İSTEDİM` (Kiril), `ARKADAŞIMIN_EVİ_NEREDE`
(Farsça). Üçüncü film 2 kare kayıyor (İNİŞLİ_ÇIKIŞLI 951→949).

Elenen şüpheliler (tekrar deneme):
- ❌ Farklı Paddle/CUDA yapısı — ikisi de 3.3.1 / CUDA 12.6 / cuDNN 9.5.1 / commit `7688495538f4`
- ❌ Det önbelleği — 118 dosya, 23 Temmuz'dan beri değişmemiş
- ❌ Model ağırlıkları — bugün hiç dokunulmamış
- ❌ Ölçüm gürültüsü — `venvs/ocr` iki ayrı koşuda birebir aynı sonucu verdi
- ❌ Kobe'nin kodu eksik pakete dokunuyor — `motor/kutu/icerik` hiçbirine dokunmuyor

Bilinen ayrılma noktası (tek film, `ARKADAŞIMIN`):

| | venvs/ocr | Kobe venv |
|---|---|---|
| `start_frame` | 933 | -1 |
| `yontem` | `kutu+scroll+kurtarma` | `kredi_yok` |
| `aday_sayisi` | 1 | 0 |
| `scroll_orani` | 1.0 | 0.0 |

Kalan şüpheli: `venvs/ocr`'da olup Kobe'de olmayan **79 paket** — en güçlüsü
torch + `nvidia-cudnn-cu13`/`cublas` (Paddle çalışma anında bunları yükleyebilir).

## Kalan işler

| # | İş | Plan bölümü |
|---|---|---|
| 7 | `sozlesme.py` — `Girdi`/`Cikti`/`ariza`, atomik yazım + `_TAMAM` | Görev 7 (tam kod planda) |
| 8 | `main.py` + `kobe` sarmalayıcı + `config.yaml` — CLI ve toplu kuyruk | Görev 8 (tam kod planda) |
| 9 | `README.md`, `CHANGELOG.md`, `Allstar/MAP.md`, `golden/`, `Players/` silme | Görev 9 |

## Geri dönüş

Ağaç kirli — `git reset --hard` YASAK. Geri dönmek için:

```
git checkout <SHA> -- harness/kunye_kiyas tests scripts/_jenerik_pool.py
rm -rf Allstar
```

SHA: `raporlar/geri_donus.txt` içinde.
