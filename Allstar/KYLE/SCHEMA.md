# KYLE sözleşmeleri

## series profile — `kyle.series/v1`

Her rol kendi üyelerini ve beklenen kişi sayısını tutar. `expected_count` bilinmiyorsa `null` olabilir.

```json
{
  "schema_version": "kyle.series/v1",
  "series_id": "dizi-x",
  "title": "Dizi X",
  "roles": {
    "YONETMEN": {
      "expected_count": 1,
      "mode": "stable",
      "members": [
        {"person_id": "d1", "canonical_name": "CENGİZ KURT", "active": true}
      ]
    }
  },
  "history": []
}
```

`title` aynı zamanda kredi dışı dizi başlığını tanımak için kullanılır. İlk satırlarda başlığa yeterince yakın OCR varyantları (`İZ PEŞİNDE`, `IZ PESINDE`, `12 PEŞİNDE` gibi) `DIZI_BASLIGI` metadata kanıtı olur; kişi sayılmaz.

## result — `kyle.result/v1`

`durum`: `DEGISIKLIK_VAR | DEGISIKLIK_YOK | ARIZA`.

`changes` yalnız karar verilmiş yeni/değişen kayıtları taşır. Ham ve susturulan gözlemler `evidence`/`kanit.json` içinde korunur.

## public delta — `kyle.delta/v1`

İki görünüm taşır:

- `actors`: bu bölümde gerçekten gözlenen ana/konuk/bölüm oyuncularının tek listesi. Her satır `MEVCUT` veya `YENİ` durumundadır.
- `changes`: makine kararları (`NEW_MEMBER`, `NEW_GUEST`, `COUNT_INCREASE`, `ROLE_HOLDER_CHANGED` vb.).

Örnek:

```json
{
  "schema_version": "kyle.delta/v1",
  "actors": [
    {"name": "KENAN IŞIK", "type": "ANA", "status": "MEVCUT", "support_count": 3},
    {"name": "SELİM KAYA", "type": "KONUK", "status": "YENİ", "support_count": 2}
  ],
  "changes": []
}
```

PDF, `actors` listesini **tek OYUNCULAR tablosu** olarak gösterir. Sabit crew değişiklikleri kişi başına tekrarlanan başlıklar yerine rol başına tek alarm bloğunda gruplanır.

## memory patch — `kyle.memory-patch/v1`

KYLE'ın profile eklemeyi önerdiği kişileri taşır. Üretim koşusu profile'ı kendiliğinden değiştirmez; yalnız açık `kyle uygula` işlemi profile yazar.
