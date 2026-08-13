# raporlar — kule içinde yaşayan koşu kayıtları

Jordan'a ait her sonuç bu klasörde durur. Kulenin dışında Jordan verisi yoktur.

## `uctan_uca_KUKLA_ADAM_w8a8.*` — kurulum günü karar demiri

Kule kurulduğu gün (2026-08-13) **gerçek model** ile, kulenin kendi `venv/`'i
ve `jordan` CLI'ı üzerinden üretildi. Girdi:
`/home/cagatay/Belgeler/test/240/1989-0352_KUKLA_ADAM.mp4` (245 sn).

```
model/w8a8 · 19 parça · 0 bozuk · düşünme sızıntısı 0
15 blok / 28 satır · 8 çift · 0 eleme · 120.0 sn
```

Yeniden doğrulamak için:

```bash
cd /opt/mitas/Allstar/jordan
./jordan tek --video /home/cagatay/Belgeler/test/240/1989-0352_KUKLA_ADAM.mp4 \
             --film-id KANARYA
```

Çıkan `bloklar` ve `ciftler` bu dosyayla aynı olmalıdır. Zamana ve git SHA'sına
bağlı alanlar (`uretim_zamani`, `motor_surumu`, `sure_sn`) bilerek dışarıda.

**Farklıysa kule davranışı değişmiştir.** Nedenini bul — bu tek film hızlı bir
kanaryadır, gerçek karar ölçüm yatağıdır (henüz kurulmadı, bkz. `DURUM.md` §③).

> Bu klip 4 dakikalık bir film AÇILIŞI; jenerik 91. saniyede biter, sonrası
> filmdir. 91 sn sonrası satırlar (`The manor of the sea`, `H.N.`, `30`)
> sahne metnidir — doğru okuma, ama künye değil. Üretimde Jordan'a Kobe'nin
> klibi girer ve o bölge zaten yoktur. Ayrıntı: `KATALOG.md` §7.
