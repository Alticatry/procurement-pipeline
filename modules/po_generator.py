from datetime import date

CHANNELS = ("Email", "Viber / Messenger")


def _amount(value):
    return f"{value:,.2f}"


def _quantity_text(offer):
    quantity = float(offer["quantity"])
    unit = str(offer.get("unit") or "").strip()
    return f"{quantity:g} {unit}".strip()


def generate_po_draft(offer, channel="Email", business_name="", buyer_name=""):
    quantity = float(offer["quantity"])
    unit_price = float(offer["unit_price"])
    total = quantity * unit_price
    delivery_days = int(offer["delivery_days"])
    supplier = offer["supplier"]
    product = offer["product"]
    quantity_text = _quantity_text(offer)
    today = date.today().strftime("%B %d, %Y")
    delivery_text = "within 1 day" if delivery_days == 1 else f"within {delivery_days} days"

    signature_lines = [line for line in (buyer_name.strip(), business_name.strip()) if line]
    signature = "\n".join(signature_lines) if signature_lines else "Purchasing Department"

    if channel == "Email":
        body = (
            f"Dear {supplier},\n\n"
            f"We would like to place the following order based on your quotation.\n\n"
            f"Date: {today}\n"
            f"Product: {product}\n"
            f"Quantity: {quantity_text}\n"
            f"Unit price: PHP {_amount(unit_price)}\n"
            f"Total: PHP {_amount(total)}\n"
            f"Requested delivery: {delivery_text}\n\n"
            f"Please confirm this order and the delivery schedule at your earliest convenience.\n\n"
            f"Thank you.\n\n"
            f"Regards,\n{signature}"
        )
        return {"subject": f"Purchase Order Request - {product}", "body": body}

    body = (
        f"Hello {supplier}, we would like to order {quantity_text} of {product} "
        f"at PHP {_amount(unit_price)} per unit (total PHP {_amount(total)}), "
        f"to be delivered {delivery_text}. "
        f"Please confirm. Thank you!\n- {signature.replace(chr(10), ', ')}"
    )
    return {"subject": "", "body": body}
