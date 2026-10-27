import json

import pytest

from modules import extractor


def fake_chat_returning(payload):
    def chat(**kwargs):
        return {"message": {"content": payload if isinstance(payload, str) else json.dumps(payload)}}

    return chat


def test_parse_number_handles_currency_and_commas():
    assert extractor.parse_number("₱1,250.50") == pytest.approx(1250.5)
    assert extractor.parse_number("3 days") == 3.0
    assert extractor.parse_number(7) == 7.0


def test_parse_number_rejects_text():
    with pytest.raises(ValueError):
        extractor.parse_number("soon")


def test_validate_offers_accepts_good_offer():
    raw = [{"supplier": "A", "product": "Cheese", "quantity": "10", "unit": "kg", "unit_price": "250", "delivery_days": "2 days"}]
    valid, errors = extractor.validate_offers(raw)
    assert errors == []
    assert valid[0]["quantity"] == 10.0
    assert valid[0]["delivery_days"] == 2


def test_validate_offers_reports_missing_fields():
    raw = [{"supplier": "A", "product": "Cheese", "quantity": 10, "unit_price": None, "delivery_days": 2}]
    valid, errors = extractor.validate_offers(raw)
    assert valid == []
    assert "unit_price" in errors[0]


def test_validate_offers_rejects_non_positive_values():
    raw = [{"supplier": "A", "product": "Cheese", "quantity": 0, "unit_price": 5, "delivery_days": 1}]
    valid, errors = extractor.validate_offers(raw)
    assert valid == []
    assert len(errors) == 1


def test_validate_offers_treats_nan_as_missing():
    raw = [{"supplier": "A", "product": "Cheese", "quantity": float("nan"), "unit_price": 5, "delivery_days": 1}]
    valid, errors = extractor.validate_offers(raw)
    assert valid == []
    assert "quantity" in errors[0]


def test_parse_response_recovers_json_from_wrapped_text():
    content = 'Here you go: {"offers": [{"supplier": "A"}]} thanks'
    assert extractor.parse_response(content) == [{"supplier": "A"}]


def test_parse_response_rejects_garbage():
    with pytest.raises(extractor.ExtractionError):
        extractor.parse_response("no json at all")


def test_extract_offers_end_to_end_with_fake_model():
    payload = {
        "offers": [
            {"supplier": "A", "product": "Cheese", "quantity": 10, "unit": "kg", "unit_price": 250, "delivery_days": 2},
            {"supplier": "B", "product": "Cheese", "quantity": 10, "unit": "kg", "unit_price": None, "delivery_days": 1},
        ]
    }
    result = extractor.extract_offers("some text", chat_fn=fake_chat_returning(payload))
    assert len(result["offers"]) == 1
    assert len(result["errors"]) == 1


def test_extract_offers_wraps_connection_errors():
    def broken_chat(**kwargs):
        raise ConnectionError("refused")

    with pytest.raises(extractor.ExtractionError):
        extractor.extract_offers("some text", chat_fn=broken_chat)


def test_extract_offers_rejects_empty_text():
    with pytest.raises(extractor.ExtractionError):
        extractor.extract_offers("   ", chat_fn=fake_chat_returning({}))
