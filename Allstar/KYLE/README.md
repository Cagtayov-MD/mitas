# KYLE — Dizi jeneriği değişiklik kulesi

KYLE, bir dizinin **manuel/doğrulanmış ilk cast+crew profilini** referans alır; Jordan, Nash ve LeBron gibi bağımsız okuyucuların saf metin çıktılarında bilinen kişileri profile bağlar ve yeni/değişen kayıtları kanıtlar.

## Tek cümlelik görev

> **Bilinenleri tanı; yeni kişi, rol sahibi değişimi, kişi sayısı artışı ve konuk/bölüm oyuncusunu 2+ bağımsız kaynakla kanıtla.**

KYLE başka kuleleri değiştirmez, onların klasörlerine yazmaz ve onların model/algoritmalarını bilmez. Girdiler çağıran tarafından KYLE'a dosya yolu olarak verilir. KYLE yalnız kendi `out/` ve `data/series/` alanına yazar.

## Neden

100–200 bölümlük bir dizide kadronun çoğu sabittir. Her bölümü sıfırdan tam jenerik olarak yeniden çözmek yerine doğrulanmış dizi hafızasına bağlamak, zor problemi değişen birkaç satıra indirir.

## Temel kurallar

1. Diğer kuleler KYLE açısından **salt-okunurdur**.
2. Aynı kaynağın tekrarları birden fazla oy sayılmaz.
3. Bilinen kişi eşleşmesi profile karşı fuzzy olabilir; canonical isim profile'dan gelir.
4. Profile yeni kişiyi bastırmaz. En az 2 bağımsız kaynak yeni kişide birleşirse değişiklik adayıdır.
5. Yeni isim profile otomatik eklenmez. `memory_patch.json` üretilir; açık `kyle uygula` komutuyla işlenir.
6. Rol adları closed-world canonicalize edilir; ham gözlemler kanıtta korunur.
7. Yeni isim metni gerçek bir source observation'dan seçilir; KYLE isim string'i sentezlemez.
8. Dizi adı ilk satırlarda profile başlığına fuzzy eşleşirse metadata sayılır; oyuncu yapılmaz.
9. `_TAMAM` en son yazılır.
10. `ARIZA`, `DEGISIKLIK_YOK` değildir.

## Akış

```text
Jordan ─┐
Nash   ─┼─> raw observations
LeBron ─┘
          -> dizi başlığı / metadata kapısı
          -> rol başlığı canonicalization
          -> bilinen kişi / dizi profile fuzzy match
          -> kalan bilinmeyenleri rol içinde cross-source cluster
          -> 2+ bağımsız kaynak kapısı
          -> NEW_MEMBER / COUNT_INCREASE / ROLE_HOLDER_CHANGED / GUEST / EPISODE
          -> tek oyuncu görünümü + rol bazlı değişiklik blokları
          -> JSON + PDF + kanıt + memory_patch
```

## Kurulum

```bash
cd Allstar/KYLE
./venv_kur.sh
```

## İlk dizi profili

Senin çıkardığın ilk güvenilir cast/crew bir seed JSON olarak verilir:

```bash
Allstar/KYLE/kyle profil-olustur \
  --series-id iz-pesinde \
  --title "İz Peşinde" \
  --seed /yol/ilk_cast_crew.json
```

Varsayılan profil:

```text
Allstar/KYLE/data/series/<series_id>/profile.json
```

Örnek rol:

```json
{
  "YONETMEN": {
    "expected_count": 1,
    "mode": "stable",
    "members": [
      {"person_id": "d1", "canonical_name": "CENGİZ KURT", "active": true}
    ]
  }
}
```

## Bölüm çalıştırma

KYLE diğer kulelerin `out/` klasörünü kendisi keşfetmez. Çağıran hazır saf metinleri verir:

```bash
Allstar/KYLE/kyle tek \
  --series-id iz-pesinde \
  --episode-id 037 \
  --jordan /hazir/jordan.txt \
  --nash /hazir/nash.txt \
  --lebron /hazir/lebron.txt
```

En az iki bağımsız kaynak zorunludur; üçü tercih edilir.

## Oyuncu raporu

Oyuncular PDF'de kişi başına ayrı alarm başlığı oluşturmaz. Bu bölümde gerçekten gözlenen ana/konuk/bölüm oyuncuları tek `OYUNCULAR` tablosunda gösterilir:

```text
OYUNCULAR

KENAN IŞIK      ANA     MEVCUT   3 (jordan,nash,lebron)
AYŞE DEMİR      ANA     MEVCUT   2 (jordan,nash)
SELİM KAYA      KONUK   YENİ     3 (jordan,nash,lebron)
MEHMET CAN      ANA     YENİ     2 (jordan,nash)
```

Profile'da kayıtlı olup bu bölümde gözlenmeyen kişi tabloya zorla eklenmez. OCR eksikliği, "bu bölümde vardı" gerçeğine çevrilmez.

## Değişiklik tipleri

- `COUNT_INCREASE`: sabit birimde, örn. Işık Şefi beklenen 1 iken bu bölümde doğrulanan 2.
- `ROLE_HOLDER_CHANGED`: beklenen tek rol sahibi görünmedi, 2+ kaynak başka kişiyi destekliyor.
- `NEW_MEMBER`: ana oyuncu veya roster birimine yeni kişi.
- `NEW_GUEST`: yeni konuk oyuncu.
- `NEW_EPISODE_MEMBER`: yeni bölüm oyuncusu.

Ana oyuncular `COUNT_INCREASE` diye kişi başına alarm üretmez; `NEW_MEMBER` olur ve tek oyuncu tablosunda `YENİ` etiketiyle görünür. Sabit crew rollerinde kişi sayısı değişikliği kırmızı alarm olmaya devam eder.

## Çıktı

```text
Allstar/KYLE/out/<series_id>/<episode_id>/
├─ kyle.json
├─ degisiklikler.json
├─ kanit.json
├─ memory_patch.json
├─ rapor.pdf
└─ _TAMAM
```

- `degisiklikler.json`: makine çıktısı + `actors` tek görünümü.
- `kanit.json`: ham eşleşme kanıtı, rol başlıkları, yok sayılan metadata ve çözülemeyenler.
- `memory_patch.json`: onay sonrası profile uygulanabilecek değişiklikler.
- `rapor.pdf`: oyuncular tek tabloda; diğer birimler rol başına tek alarm bloğunda.

## Profile güncelleme

Değişiklik insan veya üst süreç tarafından onaylandıktan sonra:

```bash
Allstar/KYLE/kyle uygula \
  --series-id iz-pesinde \
  --patch Allstar/KYLE/out/iz-pesinde/037/memory_patch.json
```

Tek bozuk bölüm dizi hafızasını otomatik zehirleyemez.

## Test

```bash
Allstar/KYLE/venv/bin/python -m pytest -q Allstar/KYLE/tests
```

Test paketi; bilinen kişi fuzzy eşleştirmesi, sabit rol kişi sayısı artışı, rol sahibi değişimi, konuk oyuncu, tek-kaynak kapısı, explicit memory patch, dizi başlığının metadata olarak elenmesi ve oyuncuların `MEVCUT/YENİ` tek görünümünü kapsar.
