import pytest

from database import db


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    db.init_db(path)
    return path


def sample_offer(**overrides):
    offer = {
        "supplier": "Supplier A",
        "product": "Cheese",
        "unit": "kg",
        "quantity": 10,
        "unit_price": 250.0,
        "delivery_days": 2,
    }
    offer.update(overrides)
    return offer


def test_save_and_get_offers(db_path):
    saved = db.save_offers([sample_offer(), sample_offer(supplier="Supplier B", unit_price=240)], "raw", db_path)
    assert saved == 2
    rows = db.get_offers(db_path=db_path)
    assert len(rows) == 2
    assert {row["supplier"] for row in rows} == {"Supplier A", "Supplier B"}


def test_supplier_names_are_case_insensitive(db_path):
    db.save_offers([sample_offer(supplier="supplier a"), sample_offer(supplier="SUPPLIER A")], db_path=db_path)
    with db.connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
    assert count == 1


def test_filter_offers_by_product(db_path):
    db.save_offers([sample_offer(), sample_offer(product="Cooking Oil")], db_path=db_path)
    rows = db.get_offers(product="Cheese", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["product"] == "Cheese"


def test_save_purchase_order_computes_total(db_path):
    order_id = db.save_purchase_order(sample_offer(), "Email", "draft text", db_path)
    assert order_id == 1
    orders = db.get_purchase_orders(db_path)
    assert orders[0]["total_price"] == pytest.approx(2500.0)
    assert orders[0]["channel"] == "Email"
