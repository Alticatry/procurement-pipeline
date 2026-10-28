import pytest

from modules import saw_engine


def test_normalize_weights_sum_to_one():
    result = saw_engine.normalize_weights({"unit_price": 3, "delivery_days": 1})
    assert result["unit_price"] == pytest.approx(0.75)
    assert result["delivery_days"] == pytest.approx(0.25)
    assert sum(result.values()) == pytest.approx(1.0)


def test_normalize_weights_rejects_zero_total():
    with pytest.raises(ValueError):
        saw_engine.normalize_weights({"unit_price": 0, "delivery_days": 0})


def test_normalize_weights_rejects_negative():
    with pytest.raises(ValueError):
        saw_engine.normalize_weights({"unit_price": -1, "delivery_days": 2})


def test_cost_normalization():
    assert saw_engine.min_max_normalize([10, 20, 30], "cost") == pytest.approx([1.0, 0.5, 0.0])


def test_benefit_normalization():
    assert saw_engine.min_max_normalize([10, 20, 30], "benefit") == pytest.approx([0.0, 0.5, 1.0])


def test_equal_values_normalize_to_one():
    assert saw_engine.min_max_normalize([5, 5, 5], "cost") == [1.0, 1.0, 1.0]


def test_invalid_kind_rejected():
    with pytest.raises(ValueError):
        saw_engine.min_max_normalize([1, 2], "other")


def test_rank_empty_returns_empty_list():
    assert saw_engine.rank_offers([]) == []


def test_rank_worked_example():
    offers = [
        {"supplier": "A", "unit_price": 10, "delivery_days": 5},
        {"supplier": "B", "unit_price": 20, "delivery_days": 1},
        {"supplier": "C", "unit_price": 15, "delivery_days": 3},
    ]
    ranked = saw_engine.rank_offers(offers, {"unit_price": 0.6, "delivery_days": 0.4})
    assert [row["supplier"] for row in ranked] == ["A", "C", "B"]
    assert ranked[0]["utility_score"] == pytest.approx(0.6)
    assert ranked[1]["utility_score"] == pytest.approx(0.5)
    assert ranked[2]["utility_score"] == pytest.approx(0.4)
    assert [row["rank"] for row in ranked] == [1, 2, 3]


def test_weights_change_the_winner():
    offers = [
        {"supplier": "Cheap", "unit_price": 10, "delivery_days": 7},
        {"supplier": "Fast", "unit_price": 20, "delivery_days": 1},
    ]
    price_first = saw_engine.rank_offers(offers, {"unit_price": 0.9, "delivery_days": 0.1})
    speed_first = saw_engine.rank_offers(offers, {"unit_price": 0.1, "delivery_days": 0.9})
    assert price_first[0]["supplier"] == "Cheap"
    assert speed_first[0]["supplier"] == "Fast"


def test_missing_weight_rejected():
    offers = [{"supplier": "A", "unit_price": 1, "delivery_days": 1}]
    with pytest.raises(ValueError):
        saw_engine.rank_offers(offers, {"unit_price": 1})


def test_input_offers_not_mutated():
    offers = [
        {"supplier": "A", "unit_price": 10, "delivery_days": 5},
        {"supplier": "B", "unit_price": 20, "delivery_days": 1},
    ]
    saw_engine.rank_offers(offers)
    assert "utility_score" not in offers[0]


def test_chapter_two_worked_example():
    offers = [
        {"supplier": "A", "unit_price": 1850, "delivery_days": 3},
        {"supplier": "B", "unit_price": 1720, "delivery_days": 5},
        {"supplier": "C", "unit_price": 1790, "delivery_days": 2},
    ]
    ranked = saw_engine.rank_offers(offers, {"unit_price": 0.6, "delivery_days": 0.4})
    scores = {row["supplier"]: row["utility_score"] for row in ranked}
    assert [row["supplier"] for row in ranked] == ["C", "B", "A"]
    assert scores["C"] == pytest.approx(0.6769, abs=0.0001)
    assert scores["B"] == pytest.approx(0.6000, abs=0.0001)
    assert scores["A"] == pytest.approx(0.2667, abs=0.0001)


def test_chapter_two_example_with_price_weight_ninety():
    offers = [
        {"supplier": "A", "unit_price": 1850, "delivery_days": 3},
        {"supplier": "B", "unit_price": 1720, "delivery_days": 5},
        {"supplier": "C", "unit_price": 1790, "delivery_days": 2},
    ]
    ranked = saw_engine.rank_offers(offers, {"unit_price": 0.9, "delivery_days": 0.1})
    assert ranked[0]["supplier"] == "B"
