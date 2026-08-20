# 🎬 28 FİLMİN TÜM MODELLER İÇİN DETAYLI FİLM FİLM İSİM VE HATA KARŞILAŞTIRMA RAPORU

Bu rapor, `/home/cagatay/Belgeler/test` dizinindeki 28 videonun tamamı üzerinde 4 modelin (`Qwen2.5-VL-7B FP16 Native`, `Qwen3.6-27B Q5_K_M GGUF`, `Qwen3.6-27B Q4_K_M GGUF`, `Qwen3.5-9B Q8_0 GGUF`) birebir çıkardığı isimleri, harf farklarını, imla ve okuma hatalarını kıyaslamaktadır.

## 🎥 Film #01: `cag_output01.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 49 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 42 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 44 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Universal International` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `Universal` | ⚠️ 9B Harf Sapması yaptı (`Universal`) |
| Satır 2 | `Universal - International` | `<https://debuginfod.ubuntu.com>` | `International` | ⚠️ 9B Harf Sapması yaptı (`International`) |
| Satır 3 | `Presents` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `Universal - International` | ⚠️ 9B Harf Sapması yaptı (`Universal - International`) |
| Satır 4 | `Audie MURPHY` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `Presents` | ⚠️ 9B Harf Sapması yaptı (`Presents`) |
| Satır 5 | `Brian DONLEVY` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `Audie MURPHY` | ⚠️ 9B Harf Sapması yaptı (`Audie MURPHY`) |
| Satır 6 | `Marguerite CHAPMAN` | `Brian DONLEVY` | `Brian DONLEVY` | 🔍 FP16/27B Karakter İnce Ayarı (`Marguerite CHAPMAN` vs `Brian DONLEVY`) |
| Satır 7 | `Scott BRADY` | `Marguerite CHAPMAN` | `Marguerite CHAPMAN` | 🔍 FP16/27B Karakter İnce Ayarı (`Scott BRADY` vs `Marguerite CHAPMAN`) |
| Satır 8 | `in` | `Scott BRADY` | `Scott BRADY` | 🔍 FP16/27B Karakter İnce Ayarı (`in` vs `Scott BRADY`) |

---

## 🎥 Film #02: `cag_output02.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 327 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 45 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 37 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `20th` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `20th` | ⚠️ 9B Harf Sapması yaptı (`20th`) |
| Satır 2 | `CENTURY` | `<https://debuginfod.ubuntu.com>` | `CENTURY` | ⚠️ 9B Harf Sapması yaptı (`CENTURY`) |
| Satır 3 | `FOX` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `FOX` | ⚠️ 9B Harf Sapması yaptı (`FOX`) |
| Satır 4 | `Twentieth Century-Fox Presents` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `Twentieth Century-Fox Presents` | ⚠️ 9B Harf Sapması yaptı (`Twentieth Century-Fox Presents`) |
| Satır 5 | `Clifton Webb` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `Clifton Webb` | ⚠️ 9B Harf Sapması yaptı (`Clifton Webb`) |
| Satır 6 | `Jeanne Crain` | `Jeanne Crain` | `Jeanne Crain` | Kusursuz Eşleşme |
| Satır 7 | `Myrna Loy` | `Myrna Loy` | `Myrna Loy` | Kusursuz Eşleşme |
| Satır 8 | `in` | `in` | `Cheaper by the Dozen` | ⚠️ 9B Harf Sapması yaptı (`Cheaper by the Dozen`) |

---

## 🎥 Film #03: `cag_output03.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 154 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 28 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 46 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `COLUMBIA PICTURES CORPORATION` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `COLUMBIA` | ⚠️ 9B Harf Sapması yaptı (`COLUMBIA`) |
| Satır 2 | `PRESENTS` | `<https://debuginfod.ubuntu.com>` | `COLUMBIA PICTURES CORPORATION` | ⚠️ 9B Harf Sapması yaptı (`COLUMBIA PICTURES CORPORATION`) |
| Satır 3 | `GUN FURY` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `PRESENTS` | ⚠️ 9B Harf Sapması yaptı (`PRESENTS`) |
| Satır 4 | `STARRING` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `ROCKHEDDY` | ⚠️ 9B Harf Sapması yaptı (`ROCKHEDDY`) |
| Satır 5 | `ROCK HUDSON` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `DONNA REED` | ⚠️ 9B Harf Sapması yaptı (`DONNA REED`) |
| Satır 6 | `DONNA REED` | `ROBERTA HAYNES` | `ROBERTA HAYNES` | 🔍 FP16/27B Karakter İnce Ayarı (`DONNA REED` vs `ROBERTA HAYNES`) |
| Satır 7 | `PHIL CAREY` | `WITH` | `WITH` | 🔍 FP16/27B Karakter İnce Ayarı (`PHIL CAREY` vs `WITH`) |
| Satır 8 | `ROBERTA HAYNES` | `LEO GORDON` | `LEO GORDON` | 🔍 FP16/27B Karakter İnce Ayarı (`ROBERTA HAYNES` vs `LEO GORDON`) |

---

## 🎥 Film #04: `cag_output04.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 183 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 57 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 56 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Jeanne Moreau` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `Maurice Ronet` | ⚠️ 9B Harf Sapması yaptı (`Maurice Ronet`) |
| Satır 2 | `Maurice Ronet` | `<https://debuginfod.ubuntu.com>` | `Dans un film de` | ⚠️ 9B Harf Sapması yaptı (`Dans un film de`) |
| Satır 3 | `Dans un film de` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `Louis Malle` | ⚠️ 9B Harf Sapması yaptı (`Louis Malle`) |
| Satır 4 | `Louis Malle` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `Adaptation de` | ⚠️ 9B Harf Sapması yaptı (`Adaptation de`) |
| Satır 5 | `Ascenseur pour l'Echafaud` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `Roger Nimier` | ⚠️ 9B Harf Sapması yaptı (`Roger Nimier`) |
| Satır 6 | `Adaptation de` | `Adaptation de` | `et Louis Malle` | ⚠️ 9B Harf Sapması yaptı (`et Louis Malle`) |
| Satır 7 | `Roger Nimier et Louis Malle` | `Roger Nimier` | `d'après le roman de` | ⚠️ 9B Harf Sapması yaptı (`d'après le roman de`) |
| Satır 8 | `Dialogue de` | `et Louis Malle` | `Noël Cailly` | ⚠️ 9B Harf Sapması yaptı (`Noël Cailly`) |

---

## 🎥 Film #05: `cag_output05.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 70 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 64 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 58 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Universal International` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `Universal` | ⚠️ 9B Harf Sapması yaptı (`Universal`) |
| Satır 2 | `A HAMMER FILM PRODUCTION` | `<https://debuginfod.ubuntu.com>` | `International` | ⚠️ 9B Harf Sapması yaptı (`International`) |
| Satır 3 | `PETER CUSHING IN` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `A` | ⚠️ 9B Harf Sapması yaptı (`A`) |
| Satır 4 | `THE BRIDES OF DRACULA` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `HAMMER FILM` | ⚠️ 9B Harf Sapması yaptı (`HAMMER FILM`) |
| Satır 5 | `COPYRIGHT © MCMXL BY HOTSPUR FILMS LTD. ALL RIGHTS RESERVED` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `PRODUCTION` | ⚠️ 9B Harf Sapması yaptı (`PRODUCTION`) |
| Satır 6 | `The characters and incidents portrayed and the names used herein are fictitious and any similarity to persons or events, living or dead, history of any person is entirely accidental and unintentional` | `PETER` | `PETER` | 🔍 FP16/27B Karakter İnce Ayarı (`The characters and incidents portrayed and the names used herein are fictitious and any similarity to persons or events, living or dead, history of any person is entirely accidental and unintentional` vs `PETER`) |
| Satır 7 | `ALSO STARRING` | `CUSHING` | `HAMMER FILM` | ⚠️ 9B Harf Sapması yaptı (`HAMMER FILM`) |
| Satır 8 | `FREDA JACKSON MARTITA HUNT AND YVONNE MONLAUR` | `IN` | `CUSHING` | ⚠️ 9B Harf Sapması yaptı (`CUSHING`) |

---

## 🎥 Film #06: `cag_output06.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 98 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 74 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 73 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `UNIVERSAL` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `A` | ⚠️ 9B Harf Sapması yaptı (`A`) |
| Satır 2 | `PICTURE` | `<https://debuginfod.ubuntu.com>` | `UNIVERSAL` | ⚠️ 9B Harf Sapması yaptı (`UNIVERSAL`) |
| Satır 3 | `ROSS HUNTER` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `PICTURE` | ⚠️ 9B Harf Sapması yaptı (`PICTURE`) |
| Satır 4 | `PRODUCTIONS, INC.` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `EDWARD MUEHL` | ⚠️ 9B Harf Sapması yaptı (`EDWARD MUEHL`) |
| Satır 5 | `PRESENTS` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `IN CHARGE OF PRODUCTION` | ⚠️ 9B Harf Sapması yaptı (`IN CHARGE OF PRODUCTION`) |
| Satır 6 | `SANDRA DEE` | `ROSS HUNTER` | `ROSS HUNTER` | 🔍 FP16/27B Karakter İnce Ayarı (`SANDRA DEE` vs `ROSS HUNTER`) |
| Satır 7 | `ROBERT` | `PRODUCTIONS, INC.` | `PRODUCTIONS, INC.` | 🔍 FP16/27B Karakter İnce Ayarı (`ROBERT` vs `PRODUCTIONS, INC.`) |
| Satır 8 | `GOULET` | `PRESENTS` | `PRESENTS` | 🔍 FP16/27B Karakter İnce Ayarı (`GOULET` vs `PRESENTS`) |

---

## 🎥 Film #07: `cag_output07.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 23 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 20 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 19 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `P.A.T.D.U.S` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `Après des aventures dramatiques et` | ⚠️ 9B Harf Sapması yaptı (`Après des aventures dramatiques et`) |
| Satır 2 | `pris en` | `<https://debuginfod.ubuntu.com>` | `cruelles, Angélique avait enfin retrouvé son` | ⚠️ 9B Harf Sapması yaptı (`cruelles, Angélique avait enfin retrouvé son`) |
| Satır 3 | `Après des aventures dramatiques et` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `mari devant Dieu: Joffrey de Peyrac devenu` | ⚠️ 9B Harf Sapması yaptı (`mari devant Dieu: Joffrey de Peyrac devenu`) |
| Satır 4 | `cruelles, Angélique avait enfin retrouvé son` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `"le Rescator", l'homme le plus redouté en` | ⚠️ 9B Harf Sapması yaptı (`"le Rescator", l'homme le plus redouté en`) |
| Satır 5 | `mari devant Dieu: Joffrey de Peyrac devenu` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `Méditerranée.` | ⚠️ 9B Harf Sapması yaptı (`Méditerranée.`) |
| Satır 6 | `"le Rescator", l'homme le plus redouté en` | `Un bonheur tant espéré semblait alors` | `Un bonheur tant espéré semblait alors` | 🔍 FP16/27B Karakter İnce Ayarı (`"le Rescator", l'homme le plus redouté en` vs `Un bonheur tant espéré semblait alors`) |
| Satır 7 | `Méditerranée.` | `possible, mais le corsaire renégat Escravinville` | `possible, mais le corsaire renégat Escrainville` | ⚠️ 9B Harf Sapması yaptı (`possible, mais le corsaire renégat Escrainville`) |
| Satır 8 | `Un bonheur tant espéré semblait alors` | `réussit à enlever Angélique et à mettre le feu` | `réussit à enlever Angélique et à mettre le feu` | 🔍 FP16/27B Karakter İnce Ayarı (`Un bonheur tant espéré semblait alors` vs `réussit à enlever Angélique et à mettre le feu`) |

---

## 🎥 Film #08: `cag_output08.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 18 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 16 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 14 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `CHARLES BRONSON` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `CHARLES BRONSON` | ⚠️ 9B Harf Sapması yaptı (`CHARLES BRONSON`) |
| Satır 2 | `THE WHITE BUFFALO` | `<https://debuginfod.ubuntu.com>` | `THE WHITE BUFFALO` | ⚠️ 9B Harf Sapması yaptı (`THE WHITE BUFFALO`) |
| Satır 3 | `COPYRIGHT ©INO DE LAURENTIS CORPORATION MCMLXXXVI. ALL RIGHTS RESERVED` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `COPYRIGHT ©DINO DE LAURENTIIS CORPORATION MCMLXXVIII. ALL RIGHTS RESERVED` | ⚠️ 9B Harf Sapması yaptı (`COPYRIGHT ©DINO DE LAURENTIIS CORPORATION MCMLXXVIII. ALL RIGHTS RESERVED`) |
| Satır 4 | `and` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `and` | ⚠️ 9B Harf Sapması yaptı (`and`) |
| Satır 5 | `KIM NOVAK` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `KIM NOVAK` | ⚠️ 9B Harf Sapması yaptı (`KIM NOVAK`) |
| Satır 6 | `as Poker Jenny` | `as Poker Jenny` | `as Poker Jenny` | Kusursuz Eşleşme |
| Satır 7 | `film editor` | `film editor` | `film editor` | Kusursuz Eşleşme |
| Satır 8 | `MICHAEL F ANDERSON` | `MICHAEL F ANDERSON` | `MICHAEL F ANDERSON` | Kusursuz Eşleşme |

---

## 🎥 Film #09: `cag_output09.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 46 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 38 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 31 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `GÉRARD DEPARDIEU` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `GÉRARD DEPARDIEU` | ⚠️ 9B Harf Sapması yaptı (`GÉRARD DEPARDIEU`) |
| Satır 2 | `SCÉNARIO DE` | `<https://debuginfod.ubuntu.com>` | `SCÉNARIO DE` | ⚠️ 9B Harf Sapması yaptı (`SCÉNARIO DE`) |
| Satır 3 | `FRANÇOIS TRUFFAUT ET SUZANNE SCHIFFMAN` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `FRANÇOIS TRUFFAUT ET SUZANNE SCHIFFMAN` | ⚠️ 9B Harf Sapması yaptı (`FRANÇOIS TRUFFAUT ET SUZANNE SCHIFFMAN`) |
| Satır 4 | `DIALOGUE DE` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `DIALOGUE DE` | ⚠️ 9B Harf Sapması yaptı (`DIALOGUE DE`) |
| Satır 5 | `FRANÇOIS TRUFFAUT, SUZANNE SCHIFFMAN` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `FRANÇOIS TRUFFAUT, SUZANNE SCHIFFMAN` | ⚠️ 9B Harf Sapması yaptı (`FRANÇOIS TRUFFAUT, SUZANNE SCHIFFMAN`) |
| Satır 6 | `JEAN-CLAUDE GRUMBERG` | `JEAN-CLAUDE GRUMBERG` | `JEAN-CLAUDE GRUMBERG` | Kusursuz Eşleşme |
| Satır 7 | `SABINE HAUDEPIN` | `DÉCORS` | `DÉCORS` | 🔍 FP16/27B Karakter İnce Ayarı (`SABINE HAUDEPIN` vs `DÉCORS`) |
| Satır 8 | `MAURICE RISCH` | `JEAN-PIERRE KOHUT-SVELKO` | `JEAN-PIERRE KOHUT-SVELKO` | 🔍 FP16/27B Karakter İnce Ayarı (`MAURICE RISCH` vs `JEAN-PIERRE KOHUT-SVELKO`) |

---

## 🎥 Film #10: `cag_output10.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 27 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 5 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 30 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 29 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `RUGGERO RAIMONDI` | `This GDB supports auto-downloading debuginfo from the following URLs:` | `RUGGERO RAIMONDI` | ⚠️ 9B Harf Sapması yaptı (`RUGGERO RAIMONDI`) |
| Satır 2 | `FANNY ARDANT` | `<https://debuginfod.ubuntu.com>` | `LA VIE EST UN ROMAN` | ⚠️ 9B Harf Sapması yaptı (`LA VIE EST UN ROMAN`) |
| Satır 3 | `LA VIE EST` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | `FANNY ARDANT` | ⚠️ 9B Harf Sapması yaptı (`FANNY ARDANT`) |
| Satır 4 | `UN ROMAN` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | `ROBERT MANUEL` | ⚠️ 9B Harf Sapması yaptı (`ROBERT MANUEL`) |
| Satır 5 | `ROBERT MANUEL` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | `SAMSON RAMANDER` | ⚠️ 9B Harf Sapması yaptı (`SAMSON RAMANDER`) |
| Satır 6 | `SAMSON FAINSILBER` | `SANDRA MAUER` | `HELENE PATAROT` | ⚠️ 9B Harf Sapması yaptı (`HELENE PATAROT`) |
| Satır 7 | `avec par ordre d'apparition` | `HELENE PATAROT` | `FLAVIE DUCORPS` | ⚠️ 9B Harf Sapması yaptı (`FLAVIE DUCORPS`) |
| Satır 8 | `sur l'écran` | `FLAVIE DUCORPS` | `JEAN-CLAUDE CORBEL` | ⚠️ 9B Harf Sapması yaptı (`JEAN-CLAUDE CORBEL`) |

---

## 🎥 Film #11: `cag_output11.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 14 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 11 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 11 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 11 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `A BARWOOD/ROBBINS PRODUCTION` | `A BARWOOD/ROBBINS PRODUCTION` | `A BARWOOD/ROBBINS PRODUCTION` | Kusursuz Eşleşme |
| Satır 2 | `WARNING SIGN` | `WARNING SIGN` | `WARNING SIGN` | Kusursuz Eşleşme |
| Satır 3 | `SAM WATERSTON` | `SAM WATERSTON` | `SAM WATERSTON` | Kusursuz Eşleşme |
| Satır 4 | `KATHLEEN QUINLAN` | `KATHLEEN QUINLAN` | `KAYEEN QUINLAN` | ⚠️ 9B Harf Sapması yaptı (`KAYEEN QUINLAN`) |
| Satır 5 | `YAPHET KOTTO` | `JEFFREY DE MUNN` | `JEFFREY DE MUNN` | 🔍 FP16/27B Karakter İnce Ayarı (`YAPHET KOTTO` vs `JEFFREY DE MUNN`) |
| Satır 6 | `JEFFREY DE MUNN` | `RICHARD DYSART` | `RICHARD DYSART` | 🔍 FP16/27B Karakter İnce Ayarı (`JEFFREY DE MUNN` vs `RICHARD DYSART`) |
| Satır 7 | `RICHARD DYSART` | `G.W. BAILEY` | `G.W. BAILEY` | 🔍 FP16/27B Karakter İnce Ayarı (`RICHARD DYSART` vs `G.W. BAILEY`) |
| Satır 8 | `G.W. BAILEY` | `EXECUTIVE PRODUCER` | `EXECUTIVE PRODUCER` | 🔍 FP16/27B Karakter İnce Ayarı (`G.W. BAILEY` vs `EXECUTIVE PRODUCER`) |

---

## 🎥 Film #12: `cag_output12.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 21 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 21 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 21 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 20 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `MARIE.HELENE` | `MARIE. HELENE` | `MARIE HELENE` | ⚠️ 9B Harf Sapması yaptı (`MARIE HELENE`) |
| Satır 2 | `BREILLAT` | `BREILLAT` | `BREILLAT` | Kusursuz Eşleşme |
| Satır 3 | `LE CHASSEUR` | `LE CHASSEUR` | `LE CHASSEUR` | Kusursuz Eşleşme |
| Satır 4 | `DE CHEZ` | `DE CHEZ` | `DE CHEZ` | Kusursuz Eşleşme |
| Satır 5 | `MAXIM'S` | `MAXIM'S` | `MAXIM'S` | Kusursuz Eşleşme |
| Satır 6 | `VISA DE CONTROLE CINEMATOGRAPHIQUE N°46087` | `D'APRES LA PIECE DE` | `D'APRES LA PIECE DE` | 🔍 FP16/27B Karakter İnce Ayarı (`VISA DE CONTROLE CINEMATOGRAPHIQUE N°46087` vs `D'APRES LA PIECE DE`) |
| Satır 7 | `© COPYRIGHT PRODUCTION 2000 1976. ALL RIGHTS RESERVED` | `YVES MIRANDE ET` | `YVES MIRANDE ET` | 🔍 FP16/27B Karakter İnce Ayarı (`© COPYRIGHT PRODUCTION 2000 1976. ALL RIGHTS RESERVED` vs `YVES MIRANDE ET`) |
| Satır 8 | `D'APRES LA PIECE DE` | `GUSTAVE QUINSON` | `GUSTAVE QUINSON` | 🔍 FP16/27B Karakter İnce Ayarı (`D'APRES LA PIECE DE` vs `GUSTAVE QUINSON`) |

---

## 🎥 Film #13: `cag_output13.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 1 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 15 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 15 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 15 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `منصور خدا` | `فیلم‌ساز` | `نمکخار` | ⚠️ 9B Harf Sapması yaptı (`نمکخار`) |
| Satır 2 | `—` | `سالمه فیضی` | `سلمه فیضی` | ⚠️ 9B Harf Sapması yaptı (`سلمه فیضی`) |
| Satır 3 | `—` | `حلیله شریفی‌زاده` | `حلبیان شجیع‌غوب` | ⚠️ 9B Harf Sapması yaptı (`حلبیان شجیع‌غوب`) |
| Satır 4 | `—` | `فرحناز صفری` | `فرحناز صفری` | 🔍 FP16/27B Karakter İnce Ayarı (`—` vs `فرحناز صفری`) |
| Satır 5 | `—` | `طراحی صحنه` | `تدوین: سحنه` | ⚠️ 9B Harf Sapması yaptı (`تدوین: سحنه`) |
| Satır 6 | `—` | `ناصیر غفاریان` | `ناظم غطالان` | ⚠️ 9B Harf Sapması yaptı (`ناظم غطالان`) |
| Satır 7 | `—` | `مدیر تدارکات` | `مدیر تداریکات` | ⚠️ 9B Harf Sapması yaptı (`مدیر تداریکات`) |
| Satır 8 | `—` | `سعید عراقی` | `سعيد عراقی` | ⚠️ 9B Harf Sapması yaptı (`سعيد عراقی`) |

---

## 🎥 Film #14: `cag_output14.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 16 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 37 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 37 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 14 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `mes` | `mes` | `mes` | Kusursuz Eşleşme |
| Satır 2 | `AKADEMİ` | `AKADEMİ` | `AKADEMİ` | Kusursuz Eşleşme |
| Satır 3 | `ÜMİT KANTARCILAR` | `mes` | `ÜMİT KANTARCILAR` | ⚠️ 9B Harf Sapması yaptı (`ÜMİT KANTARCILAR`) |
| Satır 4 | `SEVCAN YAŞAR` | `AKADEMİ` | `SEVCAN YAŞAR` | ⚠️ 9B Harf Sapması yaptı (`SEVCAN YAŞAR`) |
| Satır 5 | `TOPRAK KIVİLCİM` | `mes` | `TOPRAK KIVILCIM` | ⚠️ 9B Harf Sapması yaptı (`TOPRAK KIVILCIM`) |
| Satır 6 | `MÜZİK` | `AKADEMİ` | `MÜZİK` | ⚠️ 9B Harf Sapması yaptı (`MÜZİK`) |
| Satır 7 | `İRSEL ÇİVİT` | `mes` | `İRSEL ÇİVİT` | ⚠️ 9B Harf Sapması yaptı (`İRSEL ÇİVİT`) |
| Satır 8 | `TOPRAK KIVİLCİM` | `AKADEMİ` | `TOPRAK KIVILCIM` | ⚠️ 9B Harf Sapması yaptı (`TOPRAK KIVILCIM`) |

---

## 🎥 Film #15: `cag_output15.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 8 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 7 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 7 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 7 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `C.Cabbarh adına “Azərbaycanfilm” kinostudiyası` | `C.Cabbarlı adına "Azərbaycanfilm" kinostudiyası` | `C.Cabbarlı adına "Azərbaycanfilm" kinostudiyası` | 🔍 FP16/27B Karakter İnce Ayarı (`C.Cabbarh adına “Azərbaycanfilm” kinostudiyası` vs `C.Cabbarlı adına "Azərbaycanfilm" kinostudiyası`) |
| Satır 2 | `Ssenari müəllifi` | `Qənaət müəllif` | `Qəhrəmanları:` | ⚠️ 9B Harf Sapması yaptı (`Qəhrəmanları:`) |
| Satır 3 | `Təhmİno Rafaella` | `Laləhova R. (ƏLLC)` | `Leyla Kərimova (A.L.C.)` | ⚠️ 9B Harf Sapması yaptı (`Leyla Kərimova (A.L.C.)`) |
| Satır 4 | `İlqar Safat` | `İlqar Səfət` | `İlqar Safat` | ⚠️ 9B Harf Sapması yaptı (`İlqar Safat`) |
| Satır 5 | `Quruluşçu operator` | `Prodüser` | `Prodüser` | 🔍 FP16/27B Karakter İnce Ayarı (`Quruluşçu operator` vs `Prodüser`) |
| Satır 6 | `Luka KoassIn (A.I.C.)` | `Müşfiq Hətəmov` | `Müşfiq Hətəmov` | 🔍 FP16/27B Karakter İnce Ayarı (`Luka KoassIn (A.I.C.)` vs `Müşfiq Hətəmov`) |
| Satır 7 | `Prodüser` | `içəri şəhər` | `İÇƏRİ ŞƏHƏR` | ⚠️ 9B Harf Sapması yaptı (`İÇƏRİ ŞƏHƏR`) |
| Satır 8 | `Müşfiq Hatamov` | `—` | `—` | 🔍 FP16/27B Karakter İnce Ayarı (`Müşfiq Hatamov` vs `—`) |

---

## 🎥 Film #16: `cag_output16.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 2 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 16 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 16 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 17 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `ALEX SHAFFER` | `FOX SEARCHLIGHT PICTURES Presents` | `FOX SEARCHLIGHT PICTURES Presents` | 🔍 FP16/27B Karakter İnce Ayarı (`ALEX SHAFFER` vs `FOX SEARCHLIGHT PICTURES Presents`) |
| Satır 2 | `Kahretsın.` | `In Association with EVEREST ENTERTAINMENT` | `In Association with EVEREST ENTERTAINMENT` | 🔍 FP16/27B Karakter İnce Ayarı (`Kahretsın.` vs `In Association with EVEREST ENTERTAINMENT`) |
| Satır 3 | `—` | `WIN WIN` | `A GROUNDWALKER PRODUCTION` | ⚠️ 9B Harf Sapması yaptı (`A GROUNDWALKER PRODUCTION`) |
| Satır 4 | `—` | `KAZANANLAR KULÜBÜ` | `WINWIN` | ⚠️ 9B Harf Sapması yaptı (`WINWIN`) |
| Satır 5 | `—` | `AMY RYAN` | `KAZANANLAR KULÜBÜ` | ⚠️ 9B Harf Sapması yaptı (`KAZANANLAR KULÜBÜ`) |
| Satır 6 | `—` | `BOBBY CANNAVALE` | `AMY RYAN` | ⚠️ 9B Harf Sapması yaptı (`AMY RYAN`) |
| Satır 7 | `—` | `BURT YOUNG` | `BOBBY CANNAVALE` | ⚠️ 9B Harf Sapması yaptı (`BOBBY CANNAVALE`) |
| Satır 8 | `—` | `ALEX SHAFFER` | `BURT YOUNG` | ⚠️ 9B Harf Sapması yaptı (`BURT YOUNG`) |

---

## 🎥 Film #17: `cag_output17.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 43 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 11 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 11 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 11 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `CAN RÜFE` | `CEM GELİNOĞLU` | `CEM GELİNOĞLU` | 🔍 FP16/27B Karakter İnce Ayarı (`CAN RÜFE` vs `CEM GELİNOĞLU`) |
| Satır 2 | `CEM GELİNOĞLU` | `GÖKHAN KIRAÇ` | `GÖKHAN KIRAÇ` | 🔍 FP16/27B Karakter İnce Ayarı (`CEM GELİNOĞLU` vs `GÖKHAN KIRAÇ`) |
| Satır 3 | `GÖKHAN KIRAÇ` | `YAYAT ZEYNEP TUĞÇE BAYAT` | `ZEYNEP TUĞÇE BAYAT` | ⚠️ 9B Harf Sapması yaptı (`ZEYNEP TUĞÇE BAYAT`) |
| Satır 4 | `ZEYNEP TUĞÇE BAYAT` | `KÜSAPMA ALKANTEP ÜMİT YESİN BURAK TUNÇ YILMAZ` | `MUSTAFA ALKAN - ÜMİT YEŞİL - BURAK YILDIRIM` | ⚠️ 9B Harf Sapması yaptı (`MUSTAFA ALKAN - ÜMİT YEŞİL - BURAK YILDIRIM`) |
| Satır 5 | `GÜLSÜM ALKAN` | `SİNAN BENGİER` | `SİNAN BENGİER` | 🔍 FP16/27B Karakter İnce Ayarı (`GÜLSÜM ALKAN` vs `SİNAN BENGİER`) |
| Satır 6 | `ÜMIT YESIN` | `METİN COŞKUN` | `METİN COŞKUN` | 🔍 FP16/27B Karakter İnce Ayarı (`ÜMIT YESIN` vs `METİN COŞKUN`) |
| Satır 7 | `METİN YILDIZ` | `ZERRİN SÜMER` | `ZERRİN SÜMER` | 🔍 FP16/27B Karakter İnce Ayarı (`METİN YILDIZ` vs `ZERRİN SÜMER`) |
| Satır 8 | `MUSTAFA KIRANTEPE` | `SELİN KILIÇ` | `SPİRO PANTAZIS` | ⚠️ 9B Harf Sapması yaptı (`SPİRO PANTAZIS`) |

---

## 🎥 Film #18: `cag_output18.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 2 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 41 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 41 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 40 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Proje Süpervizörü` | `Senin` | `Senin` | 🔍 FP16/27B Karakter İnce Ayarı (`Proje Süpervizörü` vs `Senin`) |
| Satır 2 | `Leyla GÜVER-BECK` | `HİKAYEN` | `HİKAYEN` | 🔍 FP16/27B Karakter İnce Ayarı (`Leyla GÜVER-BECK` vs `HİKAYEN`) |
| Satır 3 | `—` | `Timuçin ESEN` | `Timuçin ESEN` | 🔍 FP16/27B Karakter İnce Ayarı (`—` vs `Timuçin ESEN`) |
| Satır 4 | `—` | `Selma ERGEÇ` | `Selma ERGEÇ` | 🔍 FP16/27B Karakter İnce Ayarı (`—` vs `Selma ERGEÇ`) |
| Satır 5 | `—` | `Sait GENAY` | `Sait GENAY` | 🔍 FP16/27B Karakter İnce Ayarı (`—` vs `Sait GENAY`) |
| Satır 6 | `—` | `Nevra SEREZLİ` | `Nevra SEREZLİ` | 🔍 FP16/27B Karakter İnce Ayarı (`—` vs `Nevra SEREZLİ`) |
| Satır 7 | `—` | `Nevra SEREZLİ` | `Murat SEREZLİ` | ⚠️ 9B Harf Sapması yaptı (`Murat SEREZLİ`) |
| Satır 8 | `—` | `Murat SEREZLİ` | `Levent CAN` | ⚠️ 9B Harf Sapması yaptı (`Levent CAN`) |

---

## 🎥 Film #19: `cag_output19.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 24 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 192 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 192 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 65 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `م. مصود` | `إخراج` | `إخراج` | 🔍 FP16/27B Karakter İnce Ayarı (`م. مصود` vs `إخراج`) |
| Satır 2 | `فيتوفلاما` | `فادي كمال الدين` | `فهد الدشتي` | ⚠️ 9B Harf Sapması yaptı (`فهد الدشتي`) |
| Satır 3 | `مساعد أول منتج` | `مساعد الاخراج` | `مساعدة الاخراج` | ⚠️ 9B Harf Sapması yaptı (`مساعدة الاخراج`) |
| Satır 4 | `احمد داود` | `أمالي يماني` | `أمال يمني` | ⚠️ 9B Harf Sapması yaptı (`أمال يمني`) |
| Satır 5 | `تركيب الفيلم ايناس نصار` | `إيناس بكر` | `ايناس بكر` | ⚠️ 9B Harf Sapması yaptı (`ايناس بكر`) |
| Satır 6 | `نيجاتيف` | `مصطفى اليونسي` | `مصطفى ابو ريشي` | ⚠️ 9B Harf Sapması yaptı (`مصطفى ابو ريشي`) |
| Satır 7 | `ليل فهمي` | `كفاح الدين محمد` | `كمال الدين محمد` | ⚠️ 9B Harf Sapması yaptı (`كمال الدين محمد`) |
| Satır 8 | `تسجيل الحوار` | `عمر الدروبي` | `عمر الدروبي` | 🔍 FP16/27B Karakter İnce Ayarı (`تسجيل الحوار` vs `عمر الدروبي`) |

---

## 🎥 Film #20: `cag_output20.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 45 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 40 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 40 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 6 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `киностудия` | `КИНОСТУДИЯ` | `This GDB supports auto-downloading debuginfo from the following URLs:` | ⚠️ 9B Harf Sapması yaptı (`This GDB supports auto-downloading debuginfo from the following URLs:`) |
| Satır 2 | `имени АЛЕКСАНДРА ДОВЖЕНКО` | `имени АЛЕКСАНДРА ДОВЖЕНКО` | `<https://debuginfod.ubuntu.com>` | ⚠️ 9B Harf Sapması yaptı (`<https://debuginfod.ubuntu.com>`) |
| Satır 3 | `При участии фирм:` | `При участии фирм:` | `Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]` | ⚠️ 9B Harf Sapması yaptı (`Enable debuginfod for this session? (y or [n]) [answered N; input not from terminal]`) |
| Satır 4 | `«АЛЬЯНС ФИЛЬМОПРОДУКЦИОН»` | `«АЛЬЯНС ФИЛЬМОПРОДУКЦИОН»` | `To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.` | ⚠️ 9B Harf Sapması yaptı (`To make this setting permanent, add 'set debuginfod enabled off' to .gdbinit.`) |
| Satır 5 | `«РЕГИНА ЦИГЛЕР ФИЛЬМОПРОДУКЦИОН»` | `«РЕГИНА ЦИГЛЕР ФИЛЬМОПРОДУКЦИОН»` | `56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S` | ⚠️ 9B Harf Sapması yaptı (`56	in ../sysdeps/unix/sysv/linux/x86_64/syscall_cancel.S`) |
| Satır 6 | `(Западный Берлин)` | `(Западный Берлин)` | `75	in ./nptl/cancellation.c` | ⚠️ 9B Harf Sapması yaptı (`75	in ./nptl/cancellation.c`) |
| Satır 7 | `«ЦДФ» (ФРГ)` | `«ЦДФ» (ФРГ)` | `—` | ⚠️ 9B Harf Sapması yaptı (`—`) |
| Satır 8 | `БАЯРТО ДАМБАЕВ` | `БАЯРТӨ ДАМБАЕВ` | `—` | ⚠️ 9B Harf Sapması yaptı (`—`) |

---

## 🎥 Film #21: `cag_output21.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 10 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 95 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 95 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 107 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `LONDON TRANSPORT` | `THE END` | `THE END` | 🔍 FP16/27B Karakter İnce Ayarı (`LONDON TRANSPORT` vs `THE END`) |
| Satır 2 | `SONGS AND MUSICAL NUMBERS` | `MADE AT` | `MADE AT` | 🔍 FP16/27B Karakter İnce Ayarı (`SONGS AND MUSICAL NUMBERS` vs `MADE AT`) |
| Satır 3 | `'Seven Days To A Holiday' 'Let Us Take You For A Ride'` | `THE ELSTREE STUDIOS` | `THE ELSTREE STUDIOS` | 🔍 FP16/27B Karakter İnce Ayarı (`'Seven Days To A Holiday' 'Let Us Take You For A Ride'` vs `THE ELSTREE STUDIOS`) |
| Satır 4 | `'Stranger in Town' 'Swinging Affair' 'Really Waltzing'` | `OF` | `OF` | 🔍 FP16/27B Karakter İnce Ayarı (`'Stranger in Town' 'Swinging Affair' 'Really Waltzing'` vs `OF`) |
| Satır 5 | `'Yugoslavian Wedding' 'All At Once'` | `ASSOCIATED BRITISH PICTURE CORPORATION LTD.` | `ASSOCIATED BRITISH PICTURE CORPORATION LTD.` | 🔍 FP16/27B Karakter İnce Ayarı (`'Yugoslavian Wedding' 'All At Once'` vs `ASSOCIATED BRITISH PICTURE CORPORATION LTD.`) |
| Satır 6 | `'Dancing Shoes' 'Foot-tapper'` | `HERTS. ENGLAND` | `HERTS. ENGLAND` | 🔍 FP16/27B Karakter İnce Ayarı (`'Dancing Shoes' 'Foot-tapper'` vs `HERTS. ENGLAND`) |
| Satır 7 | `'Bachelor Boy'` | `All characters and events in this film are fictitious and any similarity to persons either living or dead` | `All characters and events in this film are fictitious and any similarity to persons either living or dead is purely coincidental.` | ⚠️ 9B Harf Sapması yaptı (`All characters and events in this film are fictitious and any similarity to persons either living or dead is purely coincidental.`) |
| Satır 8 | `'Bruce Welch'` | `is purely coincidental` | `LAURA HAYES` | ⚠️ 9B Harf Sapması yaptı (`LAURA HAYES`) |

---

## 🎥 Film #22: `cag_output22.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 36 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 53 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 53 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 53 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `THE CAST:` | `THE CAST:` | `THE CAST:` | Kusursuz Eşleşme |
| Satır 2 | `Young Edison:` | `Young Edison:` | `Young Edison:` | Kusursuz Eşleşme |
| Satır 3 | `Marty Schaljo` | `Marty Schaljo` | `Marty Schaljo` | Kusursuz Eşleşme |
| Satır 4 | `Old Edison:` | `Old Edison:` | `Old Edison:` | Kusursuz Eşleşme |
| Satır 5 | `George Brengel` | `George Brengel` | `George Brengel` | Kusursuz Eşleşme |
| Satır 6 | `OTHERS IN ORDER OF` | `OTHERS IN ORDER OF APPEARANCE:` | `OTHERS IN ORDER OF` | ⚠️ 9B Harf Sapması yaptı (`OTHERS IN ORDER OF`) |
| Satır 7 | `APPEARANCE:` | `Brad Adrien` | `APPEARANCE:` | ⚠️ 9B Harf Sapması yaptı (`APPEARANCE:`) |
| Satır 8 | `Brad Adrien` | `Robert Palmer` | `Brad Adrien` | ⚠️ 9B Harf Sapması yaptı (`Brad Adrien`) |

---

## 🎥 Film #23: `cag_output23.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 123 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 102 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 102 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 239 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `داستان حسین ایلخان آذر` | `داستان` | `دانشگاه` | ⚠️ 9B Harf Sapması yaptı (`دانشگاه`) |
| Satır 2 | `کارگردان کلیبرز` | `هادی خالوجی` | `کانون سینماگران` | ⚠️ 9B Harf Sapması yaptı (`کانون سینماگران`) |
| Satır 3 | `تولین سیمیع عبدالرضا` | `فیلمنامه` | `آذربایجان شرقی` | ⚠️ 9B Harf Sapması yaptı (`آذربایجان شرقی`) |
| Satır 4 | `طرح صحت و دلبان مسکین عطایان` | `مهدی آذری جرمیری` | `تدوین` | ⚠️ 9B Harf Sapması yaptı (`تدوین`) |
| Satır 5 | `چسبندگی کارگران و بهنام شیری` | `تهیه‌کننده` | `سیدمحمدعلی` | ⚠️ 9B Harf Sapması yaptı (`سیدمحمدعلی`) |
| Satır 6 | `متاود اجرای حبیب رضایی` | `سید محمد حسینی` | `با هنرمندی` | ⚠️ 9B Harf Sapması yaptı (`با هنرمندی`) |
| Satır 7 | `تولین سیمیع عبدالرضا` | `کارگردان` | `محمدرضا طاهری` | ⚠️ 9B Harf Sapması yaptı (`محمدرضا طاهری`) |
| Satır 8 | `طرح صحت و دلبان مسکین عطایان` | `مهدی آذری جرمیری` | `بازیگران` | ⚠️ 9B Harf Sapması yaptı (`بازیگران`) |

---

## 🎥 Film #24: `cag_output24.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 13 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 26 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 26 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 26 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Bölümün` | `askeri danışmanlar` | `askeri damsmalar` | ⚠️ 9B Harf Sapması yaptı (`askeri damsmalar`) |
| Satır 2 | `askeri damismanlar` | `Bölümün GÜNŞEV` | `Dz. 2. Ön Yzb. BÖLÜM GÜNŞEV` | ⚠️ 9B Harf Sapması yaptı (`Dz. 2. Ön Yzb. BÖLÜM GÜNŞEV`) |
| Satır 3 | `Dz P Ön Yb. MESUT GUNSEV` | `Dz. 2. Ön Yb. MUSTAFA COŞAR` | `Dz. 2. Ön Yzb. MUSTAFA ÇOŞAR` | ⚠️ 9B Harf Sapması yaptı (`Dz. 2. Ön Yzb. MUSTAFA ÇOŞAR`) |
| Satır 4 | `Dz P Ön Yb. MUSTAFA COSAR` | `prodüksiyon amiri` | `prodüksiyon amiri` | 🔍 FP16/27B Karakter İnce Ayarı (`Dz P Ön Yb. MUSTAFA COSAR` vs `prodüksiyon amiri`) |
| Satır 5 | `prodüksiyon amiri` | `RAGIP TARANÇ` | `RAGIP TARANÇ` | 🔍 FP16/27B Karakter İnce Ayarı (`prodüksiyon amiri` vs `RAGIP TARANÇ`) |
| Satır 6 | `RAGIP TARANC` | `yönetim yardımcısı` | `yönetim yardımcısı` | 🔍 FP16/27B Karakter İnce Ayarı (`RAGIP TARANC` vs `yönetim yardımcısı`) |
| Satır 7 | `yönetim yardımcısı` | `YÜCEL ÖZGÜR` | `YÜCEL ÖZGÜR` | 🔍 FP16/27B Karakter İnce Ayarı (`yönetim yardımcısı` vs `YÜCEL ÖZGÜR`) |
| Satır 8 | `YÜCEL ÖZGÜR` | `devamlılık yazmanları` | `devamlılık yazmanlar` | ⚠️ 9B Harf Sapması yaptı (`devamlılık yazmanlar`) |

---

## 🎥 Film #25: `cag_output25.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 81 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 144 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 144 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 142 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Dünyanın, çocukluğu habersizce çalınan bütün çocuklarına,` | `Dünyanın, çocukluğu habersizce çalınan bütün çocuklarına,` | `Dünyanın, çocukluğunu habersizce çalınan bütün çocuklarma,` | ⚠️ 9B Harf Sapması yaptı (`Dünyanın, çocukluğunu habersizce çalınan bütün çocuklarma,`) |
| Satır 2 | `Cennetin çocuklarına...` | `Cennetin çocuklarına...` | `Cennetin çocuklarma...` | ⚠️ 9B Harf Sapması yaptı (`Cennetin çocuklarma...`) |
| Satır 3 | `YÖNETMEN` | `YÖNETMEN` | `YÖNETMEN` | Kusursuz Eşleşme |
| Satır 4 | `SONER CANER` | `SONER CANER` | `SONER CANER` | Kusursuz Eşleşme |
| Satır 5 | `YAPIMCI` | `YAPIMCI` | `YAPIMCI` | Kusursuz Eşleşme |
| Satır 6 | `HASAN KARUL` | `HASAN KAYAL` | `SONER CANER` | ⚠️ 9B Harf Sapması yaptı (`SONER CANER`) |
| Satır 7 | `iqs` | `tiyo` | `GUSTO` | ⚠️ 9B Harf Sapması yaptı (`GUSTO`) |
| Satır 8 | `Kiğili` | `KIĞILI` | `KİGİLİ` | ⚠️ 9B Harf Sapması yaptı (`KİGİLİ`) |

---

## 🎥 Film #26: `cag_output26.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 142 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 78 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 78 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 133 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `YÖNETMEN` | `YAPIMCI` | `YÖNETMEN` | ⚠️ 9B Harf Sapması yaptı (`YÖNETMEN`) |
| Satır 2 | `DOĞAN ÜMİT KARACA` | `YÖNETMEN` | `DOĞAN ÜMİT KARACA` | ⚠️ 9B Harf Sapması yaptı (`DOĞAN ÜMİT KARACA`) |
| Satır 3 | `YAPIMCI` | `MEHMET CANPOLAT` | `YAPIMCI` | ⚠️ 9B Harf Sapması yaptı (`YAPIMCI`) |
| Satır 4 | `MEHMET CANPOLAT` | `DOĞAN ÜMIT KARACA` | `MEHMET CANPOLAT` | ⚠️ 9B Harf Sapması yaptı (`MEHMET CANPOLAT`) |
| Satır 5 | `SADI CANPOLAT` | `SADI CANPOLAT` | `SADİ CANPOLAT` | ⚠️ 9B Harf Sapması yaptı (`SADİ CANPOLAT`) |
| Satır 6 | `Yönetmen` | `Yönetmen DOĞAN ÜMIT KARACA` | `Yönetmen` | ⚠️ 9B Harf Sapması yaptı (`Yönetmen`) |
| Satır 7 | `DOĞAN ÜMİT KARACA` | `Yapımcı MEHMET CANPOLAT` | `DOĞAN ÜMİT KARACA` | ⚠️ 9B Harf Sapması yaptı (`DOĞAN ÜMİT KARACA`) |
| Satır 8 | `Yapımcı` | `SADI CANPOLAT` | `Yapımcı` | ⚠️ 9B Harf Sapması yaptı (`Yapımcı`) |

---

## 🎥 Film #27: `cag_output27.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 34 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 59 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 59 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 58 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Written and Directed by` | `Written and Directed by` | `Written and Directed by` | Kusursuz Eşleşme |
| Satır 2 | `SERGE RODNUNSKY` | `SERGE RODNUNSKY` | `SERGE RODNUNSKY` | Kusursuz Eşleşme |
| Satır 3 | `Executive Producers` | `Executive Producers` | `Executive Producers` | Kusursuz Eşleşme |
| Satır 4 | `DAVID FORREST` | `DAVID FORREST` | `DAVID FORREST` | Kusursuz Eşleşme |
| Satır 5 | `BEAU ROGERS` | `BEAU ROGERS` | `BEAU ROGERS` | Kusursuz Eşleşme |
| Satır 6 | `Produced by` | `Produced by` | `Produced by` | Kusursuz Eşleşme |
| Satır 7 | `SERGE RODNUNSKY` | `SERGE RODNUNSKY` | `SERGE RODNUNSKY` | Kusursuz Eşleşme |
| Satır 8 | `GERALD I. WOLFE` | `GERALD I. WOLFE` | `GERALD I. WOLFE` | Kusursuz Eşleşme |

---

## 🎥 Film #28: `cag_output28.mp4`
* **Qwen2.5-VL-7B (FP16 Native):** 62 Satır
* **Qwen3.6-27B (Q5_K_M GGUF):** 112 Satır (Yüksek Hassasiyet)
* **Qwen3.6-27B (Q4_K_M GGUF):** 112 Satır (Denge Modeli)
* **Qwen3.5-9B (Q8_0 GGUF):** 113 Satır (Seri Üretim Modeli)

| Satır / İsim | Qwen2.5-VL-7B (FP16) | Qwen3.6-27B (Q5_K_M / Q4_K_M) | Qwen3.5-9B (Q8_0) | İnceleme / Hata Analizi |
| :--- | :--- | :--- | :--- | :--- |
| Satır 1 | `Nigel Costelow` | `Elizabeth SOPHIE MARCEAU` | `Elizabeth SOPHIE MARCOTU` | ⚠️ 9B Harf Sapması yaptı (`Elizabeth SOPHIE MARCOTU`) |
| Satır 2 | `Piers Dunn` | `Charles STEPHEN DILLANE` | `Charles STEPHEN DILLANE` | 🔍 FP16/27B Karakter İnce Ayarı (`Piers Dunn` vs `Charles STEPHEN DILLANE`) |
| Satır 3 | `Unit Manager (France)` | `John Taylor KEVIN ANDERSON` | `John Taylor KEVIN ANDERSON` | 🔍 FP16/27B Karakter İnce Ayarı (`Unit Manager (France)` vs `John Taylor KEVIN ANDERSON`) |
| Satır 4 | `Jean-Philippe Blim` | `Constance LIA WILLIAMS` | `Constance LIA WILLIAMS` | 🔍 FP16/27B Karakter İnce Ayarı (`Jean-Philippe Blim` vs `Constance LIA WILLIAMS`) |
| Satır 5 | `Location Manager (France)` | `Lord Clare JOSS ACKLAND` | `Lord Clare JOSS ACKLAND` | 🔍 FP16/27B Karakter İnce Ayarı (`Location Manager (France)` vs `Lord Clare JOSS ACKLAND`) |
| Satır 6 | `Cyril Prentout` | `Molly Holland SALLY DEXTER` | `Molly Holland SALLY DEXTER` | 🔍 FP16/27B Karakter İnce Ayarı (`Cyril Prentout` vs `Molly Holland SALLY DEXTER`) |
| Satır 7 | `Production Co-ordinator` | `Ellen EMMA AMOS` | `Ellen EMMA AMOS` | 🔍 FP16/27B Karakter İnce Ayarı (`Production Co-ordinator` vs `Ellen EMMA AMOS`) |
| Satır 8 | `Marilyn Clarke` | `Elizabeth SOPHIE MARCEAU` | `Elizabeth SOPHIE MARCOTU` | ⚠️ 9B Harf Sapması yaptı (`Elizabeth SOPHIE MARCOTU`) |

---
