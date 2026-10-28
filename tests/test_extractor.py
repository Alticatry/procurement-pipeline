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


def chat_by_message(responses):
    def chat(**kwargs):
        user_text = kwargs["messages"][-1]["content"]
        for key, payload in responses.items():
            if key in user_text:
                return {"message": {"content": payload if isinstance(payload, str) else json.dumps(payload)}}
        return {"message": {"content": json.dumps({"offers": []})}}

    return chat


def offer(supplier, price, days=2):
    return {"supplier": supplier, "product": "Oil", "quantity": 20, "unit": "tin", "unit_price": price, "delivery_days": days}


def test_supplier_override_replaces_model_value():
    payload = {"offers": [offer(None, 1800)]}
    result = extractor.extract_offers("msg", chat_fn=fake_chat_returning(payload), supplier="  Supplier Z  ")
    assert result["errors"] == []
    assert result["offers"][0]["supplier"] == "Supplier Z"


def test_blank_supplier_override_is_ignored():
    payload = {"offers": [offer("Supplier A", 1800)]}
    result = extractor.extract_offers("msg", chat_fn=fake_chat_returning(payload), supplier="   ")
    assert result["offers"][0]["supplier"] == "Supplier A"


def test_connection_failure_raises_model_unavailable():
    def broken_chat(**kwargs):
        raise ConnectionError("refused")

    with pytest.raises(extractor.ModelUnavailableError):
        extractor.extract_offers("msg", chat_fn=broken_chat)


def test_extract_messages_merges_offers_in_order():
    chat = chat_by_message(
        {
            "alpha": {"offers": [offer("A", 1850, 3)]},
            "beta": {"offers": [offer("B", 1720, 5)]},
        }
    )
    result = extractor.extract_messages(["alpha text", "beta text"], chat_fn=chat)
    assert [row["supplier"] for row in result["offers"]] == ["A", "B"]
    assert result["errors"] == []
    assert result["message_count"] == 2


def test_extract_messages_names_the_failing_message():
    chat = chat_by_message(
        {
            "alpha": {"offers": [offer("A", 1850)]},
            "beta": {"offers": [{"supplier": "B", "product": "Oil", "quantity": 20, "unit": "tin", "unit_price": 1720, "delivery_days": None}]},
            "gamma": "not json at all",
        }
    )
    result = extractor.extract_messages(["alpha", "beta", "gamma"], chat_fn=chat)
    assert len(result["offers"]) == 1
    assert any(error.startswith("Message 2:") and "delivery_days" in error for error in result["errors"])
    assert any(error.startswith("Message 3:") for error in result["errors"])


def test_extract_messages_reports_messages_without_offers():
    chat = chat_by_message({"alpha": {"offers": [offer("A", 1850)]}})
    result = extractor.extract_messages(["alpha", "just a greeting"], chat_fn=chat)
    assert len(result["offers"]) == 1
    assert result["errors"] == ["Message 2: no offers were found."]


def test_extract_messages_stops_when_model_is_unavailable():
    calls = []

    def broken_chat(**kwargs):
        calls.append(1)
        raise ConnectionError("refused")

    with pytest.raises(extractor.ModelUnavailableError):
        extractor.extract_messages(["one", "two", "three"], chat_fn=broken_chat)
    assert len(calls) == 1


def test_extract_messages_applies_supplier_override_to_every_message():
    chat = chat_by_message(
        {"alpha": {"offers": [offer(None, 1850)]}, "beta": {"offers": [offer("Other", 1720)]}}
    )
    result = extractor.extract_messages(["alpha", "beta"], supplier="Supplier Z", chat_fn=chat)
    assert [row["supplier"] for row in result["offers"]] == ["Supplier Z", "Supplier Z"]
