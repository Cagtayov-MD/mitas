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
