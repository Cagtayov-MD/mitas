"""KB-SUFFIX-SPLIT — 'KARAKTER ADI + OYUNCU ADI' birlesik kredi satirindan oyuncuyu kurtar.

Turk jeneriginde oyuncu cogu zaman karakter adina yapisik tek satirda okunur
(orn "Muzaffer Tayyip Uslu Kivanc Tatlitug"). Oyuncunun standalone karti okunmamissa
final kunyeye yapisik girer; clean.consensus.near() token-sayi farki>1 oldugu icin ayirmaz.

Bu fonksiyon: her satirin SONDAN token-penceresini (2..max_win) KB (mitas_people_index)
ile eslestirir; en UZUN KB-eslesmesi = tam oyuncu adi (sagda) -> AYRI kayit olarak EKLE.

PRENSIPLER:
- ADDITIVE: girdi satirlarini DEGISTIRMEZ/SILMEZ; sadece eklenecek isimleri dondurur (OCR-otorite).
- KB-GATED: yalniz KB'de tam-fold eslesen pencere eklenir -> garble/karakter-token sizmaz (~0 yanlis).
- PREFIX-NON-EMPTY (n>w): standalone isim (karakter-prefix'i olmayan) BOLUNMEZ -> zaten consensus halleder.
- SONDAN: 'KARAKTER OYUNCU' formatinda oyuncu SAGDA; karakter (solda) ASLA eklenmez.
"""
import re
from difflib import SequenceMatcher

def _atok(t):
    return [w for w in re.split(r"\s+", (t or "").strip()) if any(c.isalpha() for c in w)]


def _dedup_variants(items, cr, thr=0.90):
    """(isim, frekans) listesinden YAZIM-VARYANTLARINI birlestir ('Maria Landi'~'Marla Landi').
    Frekansa gore azalan sirala; ayni-token-sayili + fold-benzerligi>=thr olanlari EN SIK olana katar.
    Iki gercek-farkli kisi nadiren birlesir (ayni token-sayisi + cok-yuksek benzerlik sarti = muhafazakar)."""
    out = []
    for name, cnt in sorted(items, key=lambda x: -x[1]):   # en sik ONCE (temsilci o olur)
        f = cr.fold(name); nt = len(f.split())
        hit = None
        for kept in out:
            kf = cr.fold(kept[0])
            if len(kf.split()) == nt and SequenceMatcher(None, f, kf).ratio() >= thr:
                hit = kept; break
        if hit:
            hit[1] += cnt                                  # varyant frekansini temsilciye kat
        else:
            out.append([name, cnt])
    return [(n, c) for n, c in out]


def kb_suffix_split(lines, con, cr, max_win=4, exclude_folds=None, role_kw=None):
    """lines: list[str] kredi satirlari. con: duckdb baglantisi. cr: credit_read modulu (fold, kb_exact_batch).
    exclude_folds: zaten ciktida olan fold seti (tekrar eklenmesin).
    role_kw: ROL kelime seti (clean.ROLE_KW). Verilirse PREFIX'inde rol-kelimesi olan satir BOLUNMEZ
             ('Muzik Rahman Altin' -> ekip, rol baglami korunsun; sadece KARAKTER+OYUNCU bolunur).
    Donduren: list[(isim, frekans)] kurtarilan KB-kisileri (KB-kanonik yazim), fold-benzersiz, satir-sirali.
              frekans = isim kac satirda suffix oldu (NOT: cast/crew ayirmaz; lider-oyuncu 1x de olabilir).
              NOT-KAPSAM: cast+crew+yabanci TUM kredi-kisileri doner (hepsi KB-gercek=0 garble); rol atamasi
              downstream extractor'in isi. Cast/crew otomatik ayrilamaz (frekans ayirmiyor)."""
    exclude = set(exclude_folds or set())
    rkw = set(role_kw or set())
    cand = {}            # fold -> True (benzersiz aday pencereler)
    per_line = []        # (line_idx, [(fold, w)...]) uzun-once
    for li, line in enumerate(lines):
        toks = _atok(line)
        n = len(toks)
        wins = []
        for w in range(2, max_win + 1):
            if n > w:                                  # prefix BOS olmamali (karakter+oyuncu)
                # ROL-PREFIX KAPISI: prefix'te rol-kelimesi varsa bu EKIP satiri -> bolme
                if rkw:
                    prefix_low = {t.lower() for t in toks[:n - w]}
                    if prefix_low & rkw:
                        continue
                f = cr.fold(" ".join(toks[n - w:]))
                if f:
                    wins.append((f, w)); cand[f] = True
        if wins:
            per_line.append((li, sorted(wins, key=lambda x: -x[1])))   # en uzun pencere once
    if not cand:
        return []
    kb = cr.kb_exact_batch(con, list(cand.keys()))     # {fold: kanonik_isim}
    # her isim KAC satirda (suffix olarak) gecti -> frekans (cast karti uzun durur=cok; scroll-crew az)
    counts = {}
    order = []
    for li, wins in per_line:
        for f, w in wins:                              # uzun-once: ilk KB-eslesme = en uzun (tam oyuncu)
            if f in kb:
                name = kb[f]; bf = cr.fold(name)
                if bf in exclude:
                    break
                if bf not in counts:
                    counts[bf] = [name, 0]; order.append(bf)
                counts[bf][1] += 1
                break                                  # bu satir icin tek (en uzun) eslesme
    # (isim, frekans); YAZIM-VARYANTLARINI birlestir (cift-yazim engeli) -> frekans-azalan
    return _dedup_variants([(counts[bf][0], counts[bf][1]) for bf in order], cr)
