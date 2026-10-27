from modules import po_generator

OFFER = {
    "supplier": "Supplier A",
    "product": "Cheese",
    "unit": "kg",
    "quantity": 10,
    "unit_price": 250.0,
    "delivery_days": 2,
}


def test_email_draft_has_subject_and_total():
    draft = po_generator.generate_po_draft(OFFER, "Email", "Sample Bakery", "Juan")
    assert draft["subject"] == "Purchase Order Request - Cheese"
    assert "PHP 2,500.00" in draft["body"]
    assert "Dear Supplier A" in draft["body"]
    assert "Sample Bakery" in draft["body"]


def test_messenger_draft_has_no_subject():
    draft = po_generator.generate_po_draft(OFFER, "Viber / Messenger")
    assert draft["subject"] == ""
    assert "10 kg of Cheese" in draft["body"]


def test_single_day_delivery_wording():
    draft = po_generator.generate_po_draft({**OFFER, "delivery_days": 1}, "Email")
    assert "within 1 day" in draft["body"]
