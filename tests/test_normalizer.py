from normalizer.kana import normalize_name, to_fullwidth_kana, to_hiragana, to_katakana


def test_to_fullwidth_kana_halfwidth():
    assert to_fullwidth_kana("ﾛｷｿﾆﾝ") == "ロキソニン"


def test_to_fullwidth_kana_trims_whitespace():
    assert to_fullwidth_kana("  ロキソニン  ") == "ロキソニン"


def test_to_hiragana():
    assert to_hiragana("ロキソニン") == "ろきそにん"


def test_to_katakana():
    assert to_katakana("ろきそにん") == "ロキソニン"


def test_normalize_name_nfkc_and_space_removal():
    assert normalize_name("Ａ ＢＣ") == "ABC"


def test_to_fullwidth_kana_normalizes_long_sound_mark():
    assert to_fullwidth_kana("ロキソ-ニン") == "ロキソーニン"
