# Kobe kulesi — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Her iş biriminden sonra güncellenir ve commit'lenir.
> Plan: `docs/superpowers/plans/2026-08-12-allstar-kobe-kulesi.md`
> Spec: `docs/superpowers/specs/2026-08-12-allstar-kobe-kulesi-design.md`

**Son güncelleme:** 2026-08-13 00:10 — **kule ayakta, üç ölçüm kapısı da geçti**

---

## Değişmez kurallar (her oturumda geçerli)

- **`ollama.service` DURDURULMUŞ kalır.** Ölçüm kapıları buna bağlı; açılırsa
  skor ~%93.6'ya iner ve kapı sahte alarm verir. Her ölçümden önce
  `systemctl is-active ollama` → `inactive` doğrula.
- **`git add -A`, `git add .`, `git reset --hard`, `git stash` YASAK.** Ağaçta
  bu işe ait olmayan 9 değişik + 68 silinmiş (`mutfak/`) dosya var. Yalnız adı
  geçen yolları sahnele.
- **Üretim durmuş.** Hiçbir toplu koşu başlatma.
- **`gereksinimler.txt`'ten paket çıkarma.** Kobe'nin çıktısı, kodunun hiç
  import etmediği paketlere bağlı (aşağıdaki ders). Çıkarmadan önce 110 filmlik
  ölçümü koş ve sapma sıfır olduğunu gör.
- Ölçüm referansı: **kapsam 110, doğru 104, genel %94.5, üretim %97.3,
  kredi-var 75/81, kredi-yok 29/29, eksik 5**.
- Ölçüm komutu (~140 sn):
  `cd /opt/mitas/Allstar/kobe/olcum && ../venv/bin/python olc_pool.py --paralel 8`

---

## Tamamlanan

| # | İş | Kanıt |
|---|---|---|
| 1 | Ölçüm ÖNCE + geri-dönüş noktası | `raporlar/olcum_ONCE.json`, `d497bdb0` |
| 2 | Kendi çalışma zamanı (`venv/`, paddle 3.3.1+CUDA, 167 pin) | `venv_kur.sh`, `9f24a769` |
| 4 | Dosya taşıma + import yolları + `figo` adının silinmesi | `3577c8b9` |
| 5 | Testler kule içine taşındı | 19/19 |
| 6 | **TAŞIMA KAPISI** — yeni yol + eski venv = %94.5 | `raporlar/olcum_SONRA_tasima.json`, `a875b43d` |
| 7 | `sozlesme.py` — `Girdi`/`Cikti`/`ariza`, atomik yazım + `_TAMAM` | 12/12, `31f9abe7` |
| 8 | `main.py` + `kobe` + `config.yaml` — CLI, toplu kuyruk | 8/8 (toplam 39/39), `b733e85a` |
| 3 | **KULE KAPISI** — kendi venv'iyle %94.5, sapma sıfır | `raporlar/olcum_SONRA.json`, `8bd5b4ad` |
| 8b | Uçtan uca gerçek koşu + `golden/tek_film.json` demiri | POTEMKİN → kare 1133, 21.4 sn |

**Kule çalışıyor.** Uçtan uca doğrulandı:

```bash
./Allstar/kobe/kobe tek --kareler <kare-dizini> --film-id <id>
# → out/<id>/kobe.json + _TAMAM, geçici dosya yok, dış dizine dokunulmaz
```

## Çözülen kusur — pahalı ders (kaydedildi)

Kobe kendi venv'iyle önce **%92.7** verdi (%94.5 değil): iki film doğru →
`KREDI_YOK` (`MELEKLERİ`/Kiril, `ARKADAŞIMIN`/Farsça), bir film 2 kare kaydı.

**Kök sebep: eksik paketler.** İlk denemede `venvs/ocr`'dan elle seçilmiş
16 paketlik bir pin listesi kullanılmıştı. Altı kilit paket (paddle 3.3.1,
paddleocr 3.7.0, paddlex 3.7.2, numpy 2.3.5, pillow 12.1.0, opencv 5.0.0.93)
**ikisinde de birebir aynı** olduğu halde sonuç sapıyordu. Eksik 76 paket
kurulunca skor **tam olarak** geri geldi.

> **Ders:** Kobe'nin çıktısı, kodunun **hiç import etmediği** paketlere bağlı.
> `motor.py`/`kutu.py`/`icerik.py` hiçbiri torch, sklearn, easyocr, timm veya
> transformers'a dokunmuyor. "Hangi paket önemli" TAHMİN EDİLMEZ — ortam bütün
> olarak dondurulur.

Elenen şüpheliler (tekrar deneme): Paddle/CUDA yapısı (ikisi de 3.3.1 / CUDA
12.6 / cuDNN 9.5.1 / commit `7688495538f4`), det önbelleği (118 dosya,
değişmemiş), model ağırlıkları (dokunulmamış), ölçüm gürültüsü (`venvs/ocr`
iki koşuda birebir aynı).

## Kalan işler

| # | İş | Durum |
|---|---|---|
| 9 | `README.md`, `CHANGELOG.md`, `Allstar/MAP.md`, `Players/` silme | Sonnet yürütüyor |
| — | `docs/GUNLUK.md` kaydı | son adım |

## Sonraki kule (Çağatay söyleyecek)

Bilinen borç: `src/kutu.py` ve `src/icerik.py`, `harness/kunye_kiyas/`
altındaki asıllarının **kopyası**. Aslını üretim okuyucusu
`scripts/_pipe_hibrit_okuma.py:111` kullanıyor. Okuma kulesi kurulunca o kule
kendi kopyasını alacak ve `harness/kunye_kiyas/` tamamen silinecek.

Ayrıca ertelenen: CPU/GPU kaynak bölüşümü ölçümü (spec §4.7) — Kobe'yi CPU'da
geniş paralel, okuma kulesini GPU'da koşturma hedefi. 110 filmlik yatakta
ölçülmeden kabul edilmez.

## Geri dönüş

Ağaç kirli — `git reset --hard` YASAK. Geri dönmek için:

```
git checkout <SHA> -- harness/kunye_kiyas tests scripts/_jenerik_pool.py
rm -rf Allstar
```

SHA: `raporlar/geri_donus.txt` içinde.
