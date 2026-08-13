# golden — karar demiri

`tek_film.json`, `Allstar/kobe/havuz/` içindeki ilk filmin Kobe
kararıdır. Kule kurulduğu gün (2026-08-13), **gerçek Paddle** ile, kulenin
kendi `venv/`'i üzerinden, `kobe` CLI'ı ile üretildi. Zamana ve git SHA'sına
bağlı alanlar (`uretim_zamani`, `motor_surumu`, `sure_sn`) bilerek dışarıda —
yalnız **karar** demirlenmiştir.

Yeniden doğrulamak için:

```bash
cd /opt/mitas
FILM=$(realpath "$(ls -d Allstar/kobe/havuz/*/ | head -1)")
./Allstar/kobe/kobe tek --kareler "$FILM" --film-id "$(basename "$FILM")"
```

Çıkan `durum` / `baslangic_kare` / `script` bu dosyayla aynı olmalıdır.

**Farklıysa kule davranışı değişmiştir.** 110 filmlik tam ölçümü koş ve
nedenini bul — tek film hızlı bir kanarya, ölçüm gerçek karardır:

```bash
systemctl is-active ollama          # 'inactive' OLMALI
cd /opt/mitas/Allstar/kobe/olcum && ../venv/bin/python olc_pool.py --paralel 8
```

Beklenen: kapsam 110, genel 104/110 = %94.5, üretim %97.3, kredi-yok 29/29.
