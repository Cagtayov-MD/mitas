"""20260531_2030 — KB crew-çek + isim-eşleştirme demo (a, 2. yarı). READ-ONLY.
1) çözülen film -> IMDB principals (beklenen kadro) + category.
2) principal -> mitas_people_index (imdb_id köprüsü) -> Wikidata zenginleştirme (meslek/qid).
3) OCR-ismi -> fuzzy eşleştir (film kadrosuna karşı) -> düzelt.
"""
import sys, difflib
from pathlib import Path
import duckdb
sys.stdout.reconfigure(encoding="utf-8")
con=duckdb.connect(r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb", read_only=True)

def norm(s):
    s=(s or "").lower()
    for a,b in [("ı","i"),("İ","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("’","'"),("İ","i")]:
        s=s.replace(a,b)
    return " ".join(s.replace("İ","i").split())

FILMS=[("tt0120903","X-Men"),("tt4320258","Diriliş: Ertuğrul"),("tt0448277","Bizim Evin Halleri")]

print("="*64,"\n1) FİLM -> KADRO (IMDB principals) + KB zenginleştirme\n"+"="*64)
crew_cache={}
for tc,nm in FILMS:
    rows=con.execute("""
        SELECT n.primaryName, p.category, p.job, n.nconst, n.primaryProfession
        FROM imdb.principals p JOIN imdb.names n ON p.nconst=n.nconst
        WHERE p.tconst=? ORDER BY p.ordering LIMIT 15""",[tc]).fetchall()
    crew_cache[tc]=[r[0] for r in rows]
    print(f"\n[{nm} {tc}] kadro ({len(rows)} principal):")
    for pn,cat,job,nc,prof in rows:
        # KB kopru: imdb_id ile Wikidata zenginlestirme
        kb=con.execute("SELECT name,occupations,countries,qid FROM main.mitas_people_index WHERE imdb_id=? LIMIT 1",[nc]).fetchone()
        enr=""
        if kb:
            occ=(kb[1] or "")[:40]; enr=f"  ↔KB: {kb[0]} | {occ} | {kb[3]}"
        print(f"   {pn:26} [{cat}]{enr}")

print("\n"+"="*64,"\n2) OCR-İSMİ -> FUZZY EŞLEŞTİR (film kadrosuna karşı)\n"+"="*64)
# gercek OCR-hatasi simulasyonu (Paddle tipik hatalar)
tests=[("tt0120903","HALLE BERY"),("tt0120903","PatricK STEWARD"),("tt0120903","HUGH JACKMAN"),
       ("tt4320258","ENGİN ALTAN DÜZYATAN"),("tt4320258","ESRA BİLGİÇ")]
for tc,ocr in tests:
    crew=crew_cache.get(tc,[])
    cand=difflib.get_close_matches(norm(ocr),[norm(c) for c in crew],n=1,cutoff=0.6)
    if cand:
        # geri esle
        best=next(c for c in crew if norm(c)==cand[0])
        ratio=difflib.SequenceMatcher(None,norm(ocr),cand[0]).ratio()
        tag="EXACT" if norm(ocr)==cand[0] else f"DÜZELTİLDİ ({ratio:.2f})"
        print(f"   OCR '{ocr}'  ->  '{best}'   [{tag}]")
    else:
        print(f"   OCR '{ocr}'  ->  kadroda eşleşme YOK (global KB / Türkçe-DB'ye düşer)")
con.close()
