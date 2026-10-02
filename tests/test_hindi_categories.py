from agents_hindi.categories import (
    CATEGORIES, pick_category, classify_topic, normalize_category, looks_hindi,
)


def test_pick_category_avoids_last_one():
    for _ in range(50):
        assert pick_category(last_category="science") != "science"


def test_pick_category_only_allowed():
    for _ in range(50):
        assert pick_category() in CATEGORIES


def test_normalize_category_fixes_bad_llm_value():
    assert normalize_category("history", "iPhone water test") == "gadgets"
    assert normalize_category("", "nothing matches here") == "science"
    assert normalize_category("AI") == "ai"


def test_looks_hindi():
    assert looks_hindi("Yeh liquid aag ki tarah dikhta hai par jalta nahi")
    assert looks_hindi("क्या आपने कभी यह प्रयोग देखा है?")
    assert not looks_hindi("Mix these two liquids and watch the foam rise in seconds")
    assert not looks_hindi("")


def test_spy_filters_by_category(monkeypatch, tmp_path):
    import agents_hindi.spy_agent as spy
    topics = [
        {"category": "ai", "topic": "a", "views": 1},
        {"category": "gadgets", "topic": "b", "views": 1},
    ]
    monkeypatch.setattr(spy, "get_hindi_trending_topics", lambda: topics)
    assert spy.get_best_hindi_topic(category="gadgets")["topic"] == "b"
    assert spy.get_best_hindi_topic(category="tech")["topic"] in ("a", "b")  # falls back
