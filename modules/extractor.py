import json
import math
import re

import ollama

MODEL_NAME = "llama3:8b-instruct-q4_0"
REQUIRED_FIELDS = ("supplier", "product", "quantity", "unit_price", "delivery_days")

SYSTEM_PROMPT = """You extract supplier quotation details from messy business text such as chat messages, quotations, invoices and spreadsheet rows.

Return ONLY a JSON object in exactly this shape:
{"offers": [{"supplier": string, "product": string, "quantity": number, "unit": string, "unit_price": number, "delivery_days": number}]}

Rules:
- One entry per supplier and product combination.
- "supplier" is the name of the seller or sender of the offer.
- "quantity" is the amount offered or requested, as a plain number.
- "unit" is the unit of measure such as kg, box, pack, liter, piece. Use an empty string if not stated.
- "unit_price" is the price for ONE unit as a plain number. Remove currency symbols and thousands separators. If only a total price and quantity are given, divide to get the unit price.
- "delivery_days" is the number of days until delivery as a whole number. Convert "next day" to 1 and "a week" to 7.
- If a value is not stated in the text, use null. Never invent values.
- Do not add explanations or any text outside the JSON object."""


class ExtractionError(Exception):
    pass


def build_messages(text):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Extract the offers from this text:\n\n" + text.strip()},
    ]


def _is_missing(value):
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() == ""


def parse_number(value):
    if isinstance(value, bool):
        raise ValueError(f"'{value}' is not a number")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            raise ValueError("value is not a number")
        return float(value)
    cleaned = str(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        raise ValueError(f"'{value}' is not a number")
    return float(match.group())


def validate_offers(raw_offers):
    valid = []
    errors = []
    for index, item in enumerate(raw_offers, start=1):
        if not isinstance(item, dict):
            errors.append(f"Offer {index}: expected an object.")
            continue

        missing = [field for field in REQUIRED_FIELDS if _is_missing(item.get(field))]
        if missing:
            errors.append(f"Offer {index}: missing {', '.join(missing)}.")
            continue

        try:
            quantity = parse_number(item["quantity"])
            unit_price = parse_number(item["unit_price"])
            delivery_days = parse_number(item["delivery_days"])
        except ValueError as exc:
            errors.append(f"Offer {index}: {exc}.")
            continue

        if quantity <= 0 or unit_price <= 0 or delivery_days < 0:
            errors.append(f"Offer {index}: quantity and price must be positive and delivery days cannot be negative.")
            continue

        unit = "" if _is_missing(item.get("unit")) else str(item["unit"]).strip()
        valid.append(
            {
                "supplier": str(item["supplier"]).strip(),
                "product": str(item["product"]).strip(),
                "quantity": quantity,
                "unit": unit,
                "unit_price": unit_price,
                "delivery_days": int(round(delivery_days)),
            }
        )
    return valid, errors


def parse_response(content):
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ExtractionError("The model did not return valid JSON.")
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise ExtractionError("The model returned malformed JSON.") from exc

    if isinstance(data, dict):
        data = data.get("offers", [])
    if not isinstance(data, list):
        raise ExtractionError("The model JSON did not contain a list of offers.")
    return data


def extract_offers(text, model=MODEL_NAME, chat_fn=None):
    if not text or not text.strip():
        raise ExtractionError("There is no text to extract from.")

    chat = chat_fn or ollama.chat
    try:
        response = chat(
            model=model,
            messages=build_messages(text),
            format="json",
            options={"temperature": 0},
        )
    except Exception as exc:
        raise ExtractionError(
            f"Could not reach Ollama or the model '{model}'. "
            f"Make sure Ollama is running and the model is pulled. Details: {exc}"
        ) from exc

    content = response["message"]["content"]
    valid, errors = validate_offers(parse_response(content))
    return {"offers": valid, "errors": errors, "raw": content}
