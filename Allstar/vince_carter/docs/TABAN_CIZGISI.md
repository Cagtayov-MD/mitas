# Taban çizgisi — yenilmesi gereken sayı

> Ölçüm: **2026-08-21** · eşik (YAKIN) = `0.9` · alet: `olcum/puan.py`

`gt_dizi/<film>/<bölüm>_referans_<motor>.txt` dosyaları MEVCUT
okuyucuların çıktılarıdır. Bunlar kule içindeki GT anlık görüntüsüne
(`olcum/gt/`) karşı puanlandı — **hiç GPU koşusu yapılmadan**.
Vince Carter'ın Faz 2 kapısı: **GT yatağında F1 ≥ taban_8b**
(docs/PLAN.md §5).

## Motor özeti (yalnız doğrulanmış GT yüzeyleri)

| motor | yüzey | F1 ortalama | havuz F1 | BİREBİR | YAKIN | KAYIP | FAZLA |
|---|---:|---:|---:|---:|---:|---:|---:|
| **8b** | 7 | 0.761 | 0.685 | 586 | 26 | 37 | 527 |
| **27b** | 7 | 0.628 | 0.470 | 411 | 63 | 175 | 892 |
| **7b** | 6 | 0.614 | 0.533 | 333 | 81 | 192 | 534 |
| **mini** | 7 | 0.555 | 0.397 | 185 | 192 | 272 | 872 |

`F1 ortalama` = yüzey başına F1'lerin ortalaması (her film eşit ağırlık).
`havuz F1` = tüm satırlar tek havuzda (büyük filmler ağır basar).
İkisi birlikte verilir: tek sayı yanıltır — küçük filmde iyi, büyük
filmde kötü bir motor yalnız `F1 ortalama`ya bakınca iyi görünür.

## Film × motor

| film | bölüm | motor | BİREBİR | YAKIN | KAYIP | FAZLA | kesinlik | duyarlılık | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| cennetin_cocuklari | cikis | 8b | 233 | 0 | 16 | 34 | 0.873 | 0.936 | **0.903** |
| cennetin_cocuklari | cikis | 27b | 160 | 20 | 69 | 111 | 0.619 | 0.723 | **0.667** |
| cennetin_cocuklari | cikis | 7b | 138 | 19 | 92 | 55 | 0.741 | 0.630 | **0.681** |
| cennetin_cocuklari | cikis | mini | 60 | 59 | 130 | 72 | 0.623 | 0.478 | **0.541** |
| cicek_taksi | giris | 8b | 35 | 8 | 0 | 8 | 0.843 | 1.000 | **0.915** |
| cicek_taksi | giris | 27b | 38 | 4 | 1 | 12 | 0.778 | 0.977 | **0.866** |
| cicek_taksi | giris | mini | 16 | 22 | 5 | 20 | 0.655 | 0.884 | **0.752** |
| dost_eller | cikis | 8b | 56 | 2 | 4 | 16 | 0.784 | 0.935 | **0.853** |
| dost_eller | cikis | 27b | 50 | 6 | 6 | 18 | 0.757 | 0.903 | **0.824** |
| dost_eller | cikis | 7b | 40 | 19 | 3 | 15 | 0.797 | 0.952 | **0.868** |
| dost_eller | cikis | mini | 21 | 28 | 13 | 34 | 0.590 | 0.790 | **0.676** |
| gunes | cikis | 8b | 23 | 3 | 1 | 9 | 0.743 | 0.963 | **0.839** |
| gunes | cikis | 27b | 19 | 3 | 5 | 14 | 0.611 | 0.815 | **0.698** |
| gunes | cikis | 7b | 16 | 4 | 7 | 12 | 0.625 | 0.741 | **0.678** |
| gunes | cikis | mini | 12 | 11 | 4 | 15 | 0.605 | 0.852 | **0.708** |
| marnali | cikis | 8b | 123 | 3 | 2 | 350 | 0.265 | 0.984 | **0.417** |
| marnali | cikis | 27b | 46 | 13 | 69 | 566 | 0.094 | 0.461 | **0.157** |
| marnali | cikis | 7b | 58 | 23 | 47 | 355 | 0.186 | 0.633 | **0.287** |
| marnali | cikis | mini | 19 | 30 | 79 | 596 | 0.076 | 0.383 | **0.127** |
| pastane | cikis | 8b | 37 | 8 | 14 | 105 | 0.300 | 0.763 | **0.431** |
| pastane | cikis | 27b | 23 | 13 | 23 | 155 | 0.189 | 0.610 | **0.288** |
| pastane | cikis | 7b | 19 | 12 | 28 | 79 | 0.282 | 0.525 | **0.367** |
| pastane | cikis | mini | 14 | 18 | 27 | 105 | 0.234 | 0.542 | **0.327** |
| suc_dosyasi | cikis | 8b | 79 | 2 | 0 | 5 | 0.942 | 1.000 | **0.970** |
| suc_dosyasi | cikis | 27b | 75 | 4 | 2 | 16 | 0.832 | 0.975 | **0.898** |
| suc_dosyasi | cikis | 7b | 62 | 4 | 15 | 18 | 0.786 | 0.815 | **0.800** |
| suc_dosyasi | cikis | mini | 43 | 24 | 14 | 30 | 0.691 | 0.827 | **0.753** |
| iz_pesinde ⚠ | cikis | 8b | 84 | 1 | 1 | 3 | 0.966 | 0.988 | **0.977** |
| iz_pesinde ⚠ | cikis | 27b | 72 | 5 | 9 | 24 | 0.762 | 0.895 | **0.824** |
| iz_pesinde ⚠ | cikis | 7b | 57 | 11 | 18 | 15 | 0.819 | 0.791 | **0.805** |
| iz_pesinde ⚠ | cikis | mini | 27 | 23 | 36 | 22 | 0.694 | 0.581 | **0.633** |

⚠ = GT doğrulanmamış (bkz. `olcum/gt/KAYNAK.md`) — tabloda
gösterilir ama **motor özetine katılmaz**.

## Hata sebepleri (fark dökümü toplamı)

`olcum/puan.py --fark-dokumu` sayaçlarının motor başına toplamı.
Ham F1 'ne kadar kötü' der; bu tablo **NEDEN kötü** der.

| motor | FAZLA uydurma adayı | FAZLA tekrar | FAZLA motor notu | FAZLA GT-dışı eşleşme | KAYIP hiç yok | KAYIP eşik altı |
|---|---:|---:|---:|---:|---:|---:|
| **8b** | 440 | 15 | 7 | 65 | 14 | 23 |
| **27b** | 750 | 14 | 4 | 124 | 57 | 118 |
| **7b** | 400 | 17 | 0 | 117 | 102 | 90 |
| **mini** | 697 | 25 | 0 | 150 | 113 | 159 |

## Ek referanslar (standart dörtlü dışı)

Bu dosyalar `gt_dizi`'de mevcut ama `{8b,27b,7b,mini}` adlandırma
kalıbına girmiyor. Ölçüldüler ama motor özetine katılmadılar —
gizlenmesinler diye buradalar.

| film | bölüm | motor | BİREBİR | YAKIN | KAYIP | FAZLA | F1 |
|---|---|---|---:|---:|---:|---:|---:|
| cicek_taksi | giris | `JORDANKULE8b` | 32 | 11 | 0 | 7 | 0.925 |
| cicek_taksi | giris | `YARISKODUJORDANKARE` | 32 | 11 | 0 | 1 | 0.989 |

## Bulunamayan referans dosyaları

5 kombinasyonda referans dosyası yok (o motor o film için hiç koşulmamış):

- `cicek_taksi/cikis` · **8b** — referans dosyasi yok: /opt/mitas/Allstar/gt_dizi/cicek_taksi_2001_9011_0_001_00_1/cikis_referans_8b.txt
- `cicek_taksi/cikis` · **27b** — referans dosyasi yok: /opt/mitas/Allstar/gt_dizi/cicek_taksi_2001_9011_0_001_00_1/cikis_referans_27b.txt
- `cicek_taksi/cikis` · **7b** — referans dosyasi yok: /opt/mitas/Allstar/gt_dizi/cicek_taksi_2001_9011_0_001_00_1/cikis_referans_7b.txt
- `cicek_taksi/cikis` · **mini** — referans dosyasi yok: /opt/mitas/Allstar/gt_dizi/cicek_taksi_2001_9011_0_001_00_1/cikis_referans_mini.txt
- `cicek_taksi/giris` · **7b** — referans dosyasi yok: /opt/mitas/Allstar/gt_dizi/cicek_taksi_2001_9011_0_001_00_1/giris_referans_7b.txt
