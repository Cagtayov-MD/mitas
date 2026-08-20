"""Otomatik Düzeltme Sistemi — alt-çalışan ekipleri.

Her ekip kendi alanından sorumlu:
  - afis_ekibi:    TMDB poster fetch
  - yonetmen_ekibi: IMDb/Wikidata yönetmen bul
  - yapimci_ekibi: IMDb/Wikidata yapımcı bul
  - ozet_ekibi:    ASR transkript → kurallı özet
  - latin_ekibi:   Non-Latin karakter transliterasyonu

Orkestra: QC bulgularını oku → doğru ekibi çağır → doğrula → uygula.
Prensip: %100 güvenli olmayan düzeltme YAPILMAZ.
"""
