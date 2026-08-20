"""RONALDO çekirdek testleri — konsey kırmızı-takım senaryoları vaka vaka."""
import ronaldo as rn


def test_fold_tr_i_duzeltmesi():
    # sihirli-flut acigi: 'Yapım' (ı) ile 'yapim' (i) ayni fold'a inmeli
    assert rn.fold_tr("Yapım") == rn.fold_tr("YAPIM") == "yapim"
    assert rn.fold_tr("DİLA") == rn.fold_tr("DILA") == "dila"
    assert rn.fold_tr("AYŞE  Yılmaz") == "ayse yilmaz"


def test_token_esle_kisa_isimde_fuzzy_kapali():
    # GLM/Nemotron: CAN/ÇAN edit-distance=1 ama <5 harf -> fuzzy KAPALI
    assert rn.token_esle("can", "can", set()) is True
    assert rn.token_esle("can", "cin", set()) is False


def test_token_esle_uzunluk_olcekli():
    # 5-9 harf -> 1 hata; 10+ -> 2 hata (max_edit = len//5)
    assert rn.token_esle("uganov", "ugarov", set()) is True     # 6 harf, 1 hata
    assert rn.token_esle("emre", "emrey", set()) is False        # 4 harf, fuzzy yok
    assert rn.token_esle("keenlyside", "keenlysida", set()) is True  # 10 harf


def test_token_esle_kb_cakisma_birlestirmez():
    # Nemotron #7: iki varyant da KB'de AYRI kayitliysa birlesme YOK
    kb_tok = {"emine", "emire"}
    assert rn.token_esle("emine", "emire", kb_tok) is False


def test_ic_dedup_ayni_kolda_tekrari_indirger():
    # Nemotron #1: kol içi tekrar diff'e girmeden teke inmeli (sıra korunur)
    s = ["AHMET YILMAZ", "Kamera", "ahmet yilmaz", "Kamera"]
    assert rn.ic_dedup(s) == ["AHMET YILMAZ", "Kamera"]


def test_garble_cift_basim_yakalanir():
    # slit çift-basımı: ardışık kelime-blok tekrarı
    assert rn.garble_mi("YONETMEN YARDIMCISI YONETMEN YARDIMCISI") is True
    assert rn.garble_mi("YONETMEN YARDIMCISI") is False


def test_garble_uzun_tekrarli_3gram():
    assert rn.garble_mi("ababababababababababababababababababababab") is True
    assert rn.garble_mi("With the Orchestra and Chorus of the Welsh National Opera") is False


def test_halusinasyon_parantez_ve_duzyazi():
    # Nemotron #6 + bugünkü 'dinozor paragrafı' sınıfı
    assert rn.halusinasyon_mu("[Müzik çalıyor]", set()) is True
    assert rn.halusinasyon_mu(
        "The image displays a stylized illustration with a central theme of a large dinosaur", set()) is True
    # 8+ kelime ama KB isabetli -> künye satırı olabilir, dokunma
    kb = {"archer", "mellor", "connell", "davies", "evans", "keenlyside", "clarke", "williams", "pope"}
    assert rn.halusinasyon_mu(
        "Neill Archer Alwyn Mellor John Connell Jennifer Davies Rebecca Evans", kb) is False
    assert rn.halusinasyon_mu("Tamino - Neill Archer", kb) is False


def test_satir_esle_varyant():
    kb = set()
    assert rn.satir_esle("AYŞE YILMAZ - KARAKTER", "AYSE YILMAZ — KARAKTER", kb) is True
    assert rn.satir_esle("Tamino - Neill Archer", "Papageno - Simon Keenlyside", kb) is False


def test_halusinasyon_kb_isabetli_duzyazi_yakalanir():
    # 2026-07-30 mutlu-gunler duman testi: 10M-isimlik KB'de sıradan İngilizce
    # kelimeler (man, green, brooks) soyadı olarak var -> KB-isabetsizlik
    # kuralı düzyazıda hiç ateşlemiyor. Düzyazı imzası (cümle fiili/zamiri)
    # ayrıca aranmalı.
    kb = {"douglas", "macarthur", "man", "green", "brooks"}
    assert rn.halusinasyon_mu(
        "A man in a suit and tie is walking towards the camera with a stern expression", kb) is True
    assert rn.halusinasyon_mu(
        "The man in the suit is General Douglas MacArthur who was the Supreme Commander", kb) is True
    assert rn.halusinasyon_mu(
        "It's not clear what caused the fire, but it looks like a cigarette butt", kb) is True


def test_halusinasyon_uzun_kunye_satiri_yakalanmaz():
    # Gerçek uzun künye satırları (sihirli-flut dökümünden) isim-öbeği yapısında,
    # cümle fiili içermez -> düzyazı imzası bunlara dokunmamalı.
    kb = {"seaman", "opus", "angle", "welsh"}
    assert rn.halusinasyon_mu(
        "With the Orchestra and Chorus of the Welsh National Opera", kb) is False
    assert rn.halusinasyon_mu(
        "Sound Recording by OPUS 30 Music Production by Right Angle", kb) is False


def test_halusinasyon_katalog_modu_yakalanir():
    # deepseek'in ikinci uydurma modu (mutlu-gunler): müze-kataloğu metadata'sı.
    # Markdown-bold (**) ekranda asla olmaz; katalog fiilleri isim-öbeği
    # imzasını deler.
    kb = {"evans", "walker", "hagemeyer"}
    assert rn.halusinasyon_mu("- **Dimensions:** 4 x 5 cm (1 9/16 x 2 in.)", kb) is True
    assert rn.halusinasyon_mu(
        '"Unidentified Individual, New York City" by Walker Evans, 1929-30. '
        "A poignant snapshot capturing a moment of urban life", kb) is True
    assert rn.halusinasyon_mu(
        "A black and white photograph of an urban scene, likely taken in the 1960s or 1970s.",
        kb) is True


def test_halusinasyon_cjk_betimleme_yakalanir():
    # deepseek'in Çince betimleme modu (mutlu-gunler master dökümünde görüldü);
    # boşluksuz yazıldığı için kelime-sayısı kuralına hiç girmiyor.
    assert rn.halusinasyon_mu("图片顶部是一片茂密的竹林，竹子排列整齐，叶片细长而密集。", set()) is True


def test_satir_esle_kisa_satir_paragrafa_yutulmaz():
    # Duman testi: 'CHARACTERS' (1 token) 40 kelimelik paragrafın içindeki tek
    # kelimeyle %100 örtüşme sayılıp birleşti; paragraf birincil oldu, gerçek
    # künye satırı variants'a düştü.
    kb = {"smith"}
    prosa = ("The image is in black and white, showing a close-up view of some "
             "tangled wires or cables. There are no discernible texts or characters in the image.")
    assert rn.satir_esle("CHARACTERS", prosa, kb) is False
    filigran = "The image contains a watermark with the text 2012 J. M. Smith and a URL"
    assert rn.satir_esle("SMITH", filigran, kb) is False
    # Regresyon korkuluğu: kısa satırın KISA genişlemesi hâlâ eşleşir.
    assert rn.satir_esle("KID", "KID HANK WOOD", kb) is True


def test_birlestir_messi_omurga_sira_korunur():
    # GLM #3 + Nemotron #3: sıra = Messi kronolojisi; İbra sadece boşluk doldurur
    messi = ["SUNG BY", "Tamino - Neill Archer", "Pamina - Alwyn Mellor"]
    ibra = ["Tamino - Neill Archer", "Sarastro - John Connell"]
    kb_tok = {"neill", "archer", "alwyn", "mellor", "john", "connell", "tamino", "pamina", "sarastro"}
    r = rn.birlestir(messi, ibra, set(), kb_tok)
    assert r["birlesik"][:3] == messi            # omurga aynen
    assert "Sarastro - John Connell" in r["birlesik"]   # boşluk dolduruldu
    assert r["ibra_eklenen"] == ["Sarastro - John Connell"]


def test_birlestir_kb_gecmeyen_ibra_satiri_reddedilir():
    # garble sızma kilidi: İbra-only satır KB'siz ve çapraz-doğrulamasızsa girmez
    messi = ["Tamino - Neill Archer"]
    ibra = ["Tamino - Neill Archer", "xq zvw qqp"]
    kb_tok = {"neill", "archer", "tamino"}
    r = rn.birlestir(messi, ibra, set(), kb_tok)
    assert "xq zvw qqp" not in r["birlesik"]
    assert r["ibra_reddedilen"] == ["xq zvw qqp"]


def test_birlestir_varyant_kaydi():
    messi = ["AYSE YILMAZ"]
    ibra = ["AYŞE YILMAZ"]
    r = rn.birlestir(messi, ibra, set(), {"ayse", "yilmaz"})
    assert r["birlesik"] == ["AYSE YILMAZ"]      # yazım bazı Messi
    assert r["varyantlar"]["AYSE YILMAZ"] == ["AYŞE YILMAZ"]


def test_guven_bandi_normal_tamamlayicilik_green():
    assert rn.guven_bandi(115, 120, 100) == "green"


def test_guven_bandi_cift_dil_yellow():
    # Nemotron #5 senaryo C: iki dolu küme, az kesişim -> YELLOW (çöküş DEĞİL)
    assert rn.guven_bandi(85, 80, 10) == "red" or rn.guven_bandi(85, 80, 30) == "yellow"


def test_guven_bandi_motor_cokusu_red():
    assert rn.guven_bandi(110, 5, 3) == "red"


def test_guven_bandi_ikisi_bos_none():
    # Nemotron #2: 0/0 -> NaN değil None (asla 'mükemmel' değil)
    assert rn.guven_bandi(0, 0, 0) is None


def test_bayraklar_ortak_korluk_ve_yapisal_capa():
    b = rn.bayraklar(["Tamino - Neill Archer"], kare_toplam=600, messi_kare=4, ibra_kare=5)
    assert b["common_blind"] is True                 # 600 karede 9 seçim
    assert b["structural_anchor_missing"] is True    # 'Directed by/©/Yönetmen' yok
    b2 = rn.bayraklar(["Directed by Valeri Ugarov"], kare_toplam=200, messi_kare=53, ibra_kare=60)
    assert b2["common_blind"] is False
    assert b2["structural_anchor_missing"] is False


def test_capraz_uctan_uca():
    messi = ["SUNG BY", "Tamino - Neill Archer",
             "The image displays a large dinosaur in a stylized scene with people around a table",
             "Directed by"]
    ibra = ["Tamino - Neill Archer", "Sarastro - John Connell",
            "YONETMEN YARDIMCISI YONETMEN YARDIMCISI"]
    kb_tok = {"neill", "archer", "john", "connell", "tamino", "sarastro"}
    r = rn.capraz(messi, ibra, set(), kb_tok, kare_toplam=200, messi_kare=50, ibra_kare=60)
    assert "Sarastro - John Connell" in r.birlesik
    assert all("dinosaur" not in s for s in r.birlesik)          # halüsinasyon dışarıda
    assert r.fark["hallucinations"]                               # ama raporda
    assert "YONETMEN YARDIMCISI YONETMEN YARDIMCISI" in r.fark["ibra_only_reddedilen"]
    assert r.band in ("green", "yellow", "red")
    assert r.bayraklar["structural_anchor_missing"] is False
