import model


class _Torch:
    long = "long"

    @staticmethod
    def ones_like(value, dtype=None):
        return ("ones", value, dtype)


class _Tokenizer:
    # Adaptör uzak/tokenizer ayarını değil Nash sözleşmesini zorlamalı.
    eos_token_id = 99
    pad_token_id = 98


class _FakeModel:
    def __init__(self):
        self.gelen = None

    def generate(self, *args, **kwargs):
        self.gelen = (args, kwargs)
        return "ok"


def test_uzak_kod_8192_istese_de_generate_sinirlari_zorlanir():
    sahte = _FakeModel()
    sinirlar = model._generate_sinirla(
        sahte, _Tokenizer(),
        {"max_new_tokens": 2048, "max_generation_seconds": 30}, _Torch)
    assert sahte.generate("tokenler", max_new_tokens=8192, max_time=999,
                          temperature=0.7, do_sample=True) == "ok"
    _, kwargs = sahte.gelen
    assert kwargs["max_new_tokens"] == 2048
    assert kwargs["max_time"] == 30
    assert kwargs["temperature"] == 0.0 and kwargs["do_sample"] is False
    assert kwargs["eos_token_id"] == 1 and kwargs["pad_token_id"] == 2
    assert kwargs["attention_mask"] == ("ones", "tokenler", "long")
    assert sinirlar["max_new_tokens"] == 2048


def test_uretim_varsayilani_1024_ve_ust_tavan_2048():
    a = _FakeModel()
    assert model._generate_sinirla(a, _Tokenizer(), {}, _Torch)["max_new_tokens"] == 1024
    b = _FakeModel()
    sinir = model._generate_sinirla(
        b, _Tokenizer(), {"max_new_tokens": 99999,
                          "max_generation_seconds": 999}, _Torch)
    assert sinir["max_new_tokens"] == 2048
    assert sinir["max_generation_seconds"] == 30
