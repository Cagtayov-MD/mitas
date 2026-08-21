# KYLE — Dizi jeneriği değişiklik kulesi

KYLE, bir dizinin **manuel/doğrulanmış ilk cast+crew profilini** referans alır; Jordan, Nash ve LeBron gibi bağımsız okuyucuların **saf metin çıktılarında bilinen kişileri susturur** ve yalnız yeni/değişen kayıtları raporlar.

## Tek cümlelik görev

> **Bilinenleri eşleştir ve sustur; yeni kişi, rol sahibi değişimi, kişi sayısı artışı ve konuk/bölüm oyuncusunu kanıtla.**

KYLE başka kuleleri değiştirmez, onların klasörlerine yazmaz ve onların model/algoritmalarını bilmez. Girdiler çağıran tarafından KYLE'a dosya yolu olarak verilir. KYLE yalnız kendi `out/` ve `data/series/` alanına yazar.

## Neden

100–200 bölümlük bir dizide kadronun çoğu sabittir. Her bölümü sıfırdan tam jenerik olarak yeniden çözmek yerine doğrulanmış dizi hafızasına bağlamak, zor problemi yalnız değişen birkaç satıra indirir.

## Temel kurallar

1. Diğer kuleler KYLE açısından **salt-okunurdur**.
2. Aynı kaynağın tekrarları birden fazla oy sayılmaz.
3. Bilinen kişi eşleşmesi profile karşı fuzzy olabilir; canonical isim profile'dan gelir.
4. Database/profile yeni kişiyi bastırmaz. En az 2 bağımsız kaynak yeni kişide birleşirse değişiklik adayıdır.
5. Yeni isim profile otomatik eklenmez. `memory_patch.json` üretilir; açık `kyle uygula` komutuyla işlenir.
6. Rol adları closed-world canonicalize edilir; ham gözlemler kanıtta korunur.
7. Yeni isim metni gerçek bir source observation'dan seçilir; KYLE isim string'i sentezlemez.
8. `_TAMAM` en son yazılır.
9. `ARIZA`, `DEGISIKLIK_YOK` değildir.

## Akış

```text
Jordan ─┐
Nash   ─┼─> raw observations
LeBron ─┘
          -> rol başlığı canonicalization
          -> bilinen kişi / dizi profile fuzzy match
          -> bilinenleri sustur
          -> kalan bilinmeyenleri rol içinde cross-source cluster
          -> 2+ bağımsız kaynak kapısı
          -> NEW / COUNT_INCREASE / ROLE_HOLDER_CHANGED / GUEST / EPISODE
          -> değişiklik-only JSON + PDF + kanıt + memory_patch
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

## Değişiklik tipleri

- `COUNT_INCREASE`: örn. Işık Şefi beklenen 1, yeni bölümde doğrulanan 2.
- `ROLE_HOLDER_CHANGED`: beklenen tek rol sahibi görünmedi, 2+ kaynak başka kişiyi destekliyor.
- `NEW_MEMBER`: sabit crew veya ana kadro birimine yeni kişi.
- `NEW_GUEST`: yeni konuk oyuncu.
- `NEW_EPISODE_MEMBER`: yeni bölüm oyuncusu.

`KIRMIZI`: ana kadro/crew/yönetmen/kişi sayısı değişimi. `MAVI`: konuk/bölüm oyuncusu.

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

Bilinen kişiler `degisiklikler.json` ve PDF'de tekrar edilmez; audit için `kanit.json` içinde kalır.

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

Yerel kurulumda 6 temel davranış testi geçmiştir: bilinen kişilerin susturulması, kişi sayısı artışı, rol sahibi değişimi, yeni konuk, tek-kaynak kapısı ve explicit memory patch.
