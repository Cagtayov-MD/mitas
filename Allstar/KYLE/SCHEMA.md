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

## result — `kyle.result/v1`

`durum`: `DEGISIKLIK_VAR | DEGISIKLIK_YOK | ARIZA`.

## public delta — `kyle.delta/v1`

Yalnız yeni/değişen kayıtları taşır. Bilinen kişiler burada tekrar edilmez.

## memory patch — `kyle.memory-patch/v1`

KYLE'ın profile eklemeyi önerdiği kişileri taşır. Üretim koşusu profile'ı kendiliğinden değiştirmez.
