from datetime import date

import pytest

from tests.conftest import auth

pytestmark = pytest.mark.asyncio


async def test_purchase_increases_stock_and_supplier_balance(client, admin_token, unique):
    h = auth(admin_token)

    product = await client.post(
        "/products",
        headers=h,
        json={
            "sku": f"SKU-{unique}",
            "product_name": f"Test Product {unique}",
            "unit_type": "both",
            "pieces_per_carton": 10,
            "opening_stock": "0",
            "purchase_price": "50",
            "sale_price": "70",
            "low_stock_threshold": "5",
        },
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["product_id"]

    supplier = await client.post(
        "/suppliers",
        headers=h,
        json={"supplier_name": f"Supplier {unique}", "opening_balance": "0"},
    )
    assert supplier.status_code == 201, supplier.text
    supplier_id = supplier.json()["supplier_id"]

    # Buy 3 cartons (= 30 pieces) at rate 50 -> total 150; pay 100.
    resp = await client.post(
        "/purchase-invoices",
        headers=h,
        json={
            "supplier_id": supplier_id,
            "purchase_date": str(date.today()),
            "paid_amount": "100",
            "payment_mode": "cash",
            "items": [
                {"product_id": product_id, "unit_type": "carton", "quantity": "3", "purchase_rate": "50"}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    inv = resp.json()
    assert inv["total_amount"] == "150.00"
    assert inv["outstanding_amount"] == "50.00"
    assert inv["payment_status"] == "partial"
    assert inv["items"][0]["quantity_in_pieces"] == "30.00"

    # Stock should now be 30 pieces (trigger applied).
    prod = (await client.get(f"/products/{product_id}", headers=h)).json()
    assert prod["current_stock"] == "30.00"

    # Supplier payable = 150 - 100 = 50.
    sup = (await client.get(f"/suppliers/{supplier_id}", headers=h)).json()
    assert sup["current_balance"] == "50.00"

    # Stock ledger has a purchase movement.
    ledger = (await client.get(f"/stock-ledger/{product_id}", headers=h)).json()
    assert any(row["transaction_type"] == "purchase" for row in ledger["items"])

    # PDF generation works.
    pdf = await client.get(f"/purchase-invoices/{inv['purchase_invoice_id']}/pdf", headers=h)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
