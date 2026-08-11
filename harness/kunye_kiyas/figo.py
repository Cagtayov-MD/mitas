"""FIGO — Geriye Dönük Uyumluluk Shimi.
Bu modül yeni KOBE BRYANT (kobe.py) jenerik başlangıç tespit motoruna yönlendirir.

NEDEN MODÜL TAKMASI (alias), `from kobe import *` DEĞİL:
`import *` alt çizgiyle başlayan isimleri (private-by-convention) ATLAR. Üretimde
`scripts/_jenerik_pool.py` `import figo as _co` yapıp `_co._kare_no(...)` çağırıyordu →
her çağrıda `AttributeError: module 'figo' has no attribute '_kare_no'` (2026-08-11
denetiminde 106 kayıtlı hata). Bu hata `_v5_detect`in geniş `except`ine düşüp jenerik
tespitini sessizce iptal ediyor, `script` alanı varsayılan "en"de kalıp PDF'te
"hep Latin Alfabesi" yazılmasına yol açıyordu.

`sys.modules` takması figo'yu kobe'nin TA KENDİSİ yapar: public/private tüm isimler
(bugünküler ve ileride eklenecekler) otomatik çözülür — aynı bug bir daha doğmaz.
"""
import sys

import kobe

sys.modules[__name__] = kobe
