DEFAULT_CRITERIA = {"unit_price": "cost", "delivery_days": "cost"}
DEFAULT_WEIGHTS = {"unit_price": 0.6, "delivery_days": 0.4}


def normalize_weights(weights):
    cleaned = {key: float(value) for key, value in weights.items()}
    if any(value < 0 for value in cleaned.values()):
        raise ValueError("Weights cannot be negative.")
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("At least one weight must be greater than zero.")
    return {key: value / total for key, value in cleaned.items()}


def min_max_normalize(values, kind):
    if kind not in ("cost", "benefit"):
        raise ValueError("Criterion kind must be 'cost' or 'benefit'.")
    low = min(values)
    high = max(values)
    if high == low:
        return [1.0] * len(values)
    if kind == "benefit":
        return [(value - low) / (high - low) for value in values]
    return [(high - value) / (high - low) for value in values]


def rank_offers(offers, weights=None, criteria=None):
    if not offers:
        return []
    criteria = criteria or DEFAULT_CRITERIA
    weights = weights or DEFAULT_WEIGHTS
    missing = [name for name in criteria if name not in weights]
    if missing:
        raise ValueError("Missing weights for: " + ", ".join(missing))
    weights = normalize_weights({name: weights[name] for name in criteria})

    normalized = {
        name: min_max_normalize([float(offer[name]) for offer in offers], kind)
        for name, kind in criteria.items()
    }

    ranked = []
    for index, offer in enumerate(offers):
        score = sum(weights[name] * normalized[name][index] for name in criteria)
        row = dict(offer)
        for name in criteria:
            row[f"norm_{name}"] = round(normalized[name][index], 4)
        row["utility_score"] = round(score, 4)
        ranked.append(row)

    ranked.sort(key=lambda row: row["utility_score"], reverse=True)
    for position, row in enumerate(ranked, start=1):
        row["rank"] = position
    return ranked
