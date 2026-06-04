# -*- coding: utf-8 -*-
"""KLASİK TEST — credit_crosscheck (Idea 2) gold seti.
14 gold film TEYİT + 2 yanlış-yönetmen enjeksiyonu ÇELİŞKİ beklenir. Kimlik Türkçe başlıkla bulunmalı.
Çalıştır:  python scripts/credit_crosscheck_goldtest.py   (Wikidata X: + IMDb Y: erişimi gerekir)
"""
import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit_crosscheck as cc
sys.stdout.reconfigure(encoding="utf-8")

# (Türkçe başlık, orijinal, yıl, OKUNAN yönetmen, beklenen)
CASES = [
    ("PİNOKYO'NUN MACERALARI", "New Adventures of Pinocchio", 1999, "Michael Anderson", "TEYİT"),
    ("AHLAT AĞACI", "The Wild Pear Tree", 2018, "Nuri Bilge Ceylan", "TEYİT"),
    ("AHLAT AĞACI", "The Wild Pear Tree", 2018, "Murat Cemir", "ÇELİŞKİ"),       # VLM hatası — yakalanmalı
    ("X-MEN", "X-Men", 2000, "Bryan Singer", "TEYİT"),
    ("SON METRO", "Le Dernier Métro", 1980, "François Truffaut", "TEYİT"),
    ("SON METRO", "Le Dernier Métro", 1980, "Jean-Louis Godfroy", "ÇELİŞKİ"),    # VLM halüsinasyonu
    ("DRAKULA'NIN GELİNLERİ", "Brides of Dracula", 1960, "Terence Fisher", "TEYİT"),
    ("300 SPARTALI", "300", 2006, "Zack Snyder", "TEYİT"),
    ("ÇIPLAK AĞAÇLAR", "De nøgne træer", 1991, "Morten Henriksen", "TEYİT"),
    ("GÜZEL BİR ÖLÜM", "A Lovely Way to Die", 1968, "David Lowell Rich", "TEYİT"),
    ("ZENGİN OLSAYDIN", "I'd Rather Be Rich", 1964, "Jack Smight", "TEYİT"),
    ("ROBINSON CRUSOE", "Robinson Crusoe", 2016, "Vincent Kesteloot", "TEYİT"),
    ("YABANDAN GELEN ADAM", "Giù la testa", 1971, "Sergio Leone", "TEYİT"),
    ("DON KİŞOT'U ÖLDÜREN ADAM", "The Man Who Killed Don Quixote", 2018, "Terry Gilliam", "TEYİT"),
    ("BARBARLARI BEKLERKEN", "Waiting for the Barbarians", 2019, "Ciro Guerra", "TEYİT"),
    ("ATTİLA MARCEL", "Attila Marcel", 2013, "Sylvain Chomet", "TEYİT"),
]

def main():
    kb = cc.CreditKB()
    ok = 0
    print(f"{'BAŞLIK':26} {'okunan yön':20} {'bekle':8} {'SONUÇ':9} kaynak | eşleşen film")
    print("=" * 120)
    for tr, orig, yr, ydir, exp in CASES:
        r = kb.crosscheck(ydir, read_cast=[], title_tr=tr, original=orig, year=yr)
        v = r["verdict"]; hit = (v == exp); ok += hit
        print(f"{tr[:26]:26} {ydir[:20]:20} {exp:8} {('✓ '+v) if hit else ('✗ '+v):9} "
              f"{str(r.get('kaynak'))[:4]:4} | {str(r.get('eslesen_film'))[:30]}")
    print("=" * 120)
    print(f"DOĞRU: {ok}/{len(CASES)}")
    kb.close()
    return 0 if ok == len(CASES) else 1

if __name__ == "__main__":
    sys.exit(main())
