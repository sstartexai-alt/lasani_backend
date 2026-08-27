from datetime import date

import pytest

from tests.conftest import auth

pytestmark = pytest.mark.asyncio


async def _setup_product_with_stock(client, h, unique, opening_stock="100"):
    product = await client.post(
        "/products",
        headers=h,
        json={
            "sku": f"SALE-{unique}",
            "product_name": f"Sale Product {unique}",
            "unit_type": "piece",
            "pieces_per_carton": 1,
            "opening_stock": opening_stock,
            "purchase_price": "50",
            "sale_price": "70",
            "low_stock_threshold": "5",
        },
    )
    assert product.status_code == 201, product.text
    return product.json()["product_id"]


async def test_cash_sale_decrements_stock_and_autopays(client, admin_token, unique):
    h = auth(admin_token)
    product_id = await _setup_product_with_stock(client, h, unique)

    customer = await client.post(
        "/customers",
        headers=h,
        json={"customer_name": f"Cust {unique}", "opening_balance": "0", "credit_limit": "0"},
    )
    customer_id = customer.json()["customer_id"]

    resp = await client.post(
        "/sales-invoices",
        headers=h,
        json={
            "customer_id": customer_id,
            "invoice_date": str(date.today()),
            "sale_type": "cash",
            "items": [{"product_id": product_id, "unit_type": "piece", "quantity": "10", "rate": "70"}],
        },
    )
    assert resp.status_code == 201, resp.text
    inv = resp.json()
    assert inv["total_amount"] == "700.00"
    # Cash sale is auto fully paid.
    assert inv["paid_amount"] == "700.00"
    assert inv["outstanding_amount"] == "0.00"
    assert inv["invoice_number"].startswith("INV-")

    prod = (await client.get(f"/products/{product_id}", headers=h)).json()
    assert prod["current_stock"] == "90.00"


async def test_insufficient_stock_rejected(client, admin_token, unique):
    h = auth(admin_token)
    product_id = await _setup_product_with_stock(client, h, unique, opening_stock="5")
    customer = await client.post(
        "/customers", headers=h, json={"customer_name": f"Cust2 {unique}", "credit_limit": "0"}
    )
    customer_id = customer.json()["customer_id"]

    resp = await client.post(
        "/sales-invoices",
        headers=h,
        json={
            "customer_id": customer_id,
            "invoice_date": str(date.today()),
            "sale_type": "cash",
            "items": [{"product_id": product_id, "unit_type": "piece", "quantity": "50", "rate": "70"}],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INSUFFICIENT_STOCK"


async def test_credit_limit_enforced(client, admin_token, unique):
    h = auth(admin_token)
    product_id = await _setup_product_with_stock(client, h, unique, opening_stock="100")
    customer = await client.post(
        "/customers",
        headers=h,
        json={"customer_name": f"Cust3 {unique}", "opening_balance": "0", "credit_limit": "100"},
    )
    customer_id = customer.json()["customer_id"]

    resp = await client.post(
        "/sales-invoices",
        headers=h,
        json={
            "customer_id": customer_id,
            "invoice_date": str(date.today()),
            "sale_type": "credit",
            "items": [{"product_id": product_id, "unit_type": "piece", "quantity": "10", "rate": "70"}],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "CREDIT_LIMIT_EXCEEDED"

    # Admin override succeeds.
    resp2 = await client.post(
        "/sales-invoices",
        headers=h,
        json={
            "customer_id": customer_id,
            "invoice_date": str(date.today()),
            "sale_type": "credit",
            "override_credit_limit": True,
            "items": [{"product_id": product_id, "unit_type": "piece", "quantity": "10", "rate": "70"}],
        },
    )
    assert resp2.status_code == 201, resp2.text


async def test_customer_payment_reduces_balance(client, admin_token, unique):
    h = auth(admin_token)
    product_id = await _setup_product_with_stock(client, h, unique, opening_stock="100")
    customer = await client.post(
        "/customers",
        headers=h,
        json={"customer_name": f"Cust4 {unique}", "credit_limit": "100000"},
    )
    customer_id = customer.json()["customer_id"]

    await client.post(
        "/sales-invoices",
        headers=h,
        json={
            "customer_id": customer_id,
            "invoice_date": str(date.today()),
            "sale_type": "credit",
            "items": [{"product_id": product_id, "unit_type": "piece", "quantity": "10", "rate": "70"}],
        },
    )
    before = (await client.get(f"/customers/{customer_id}", headers=h)).json()["current_balance"]
    assert before == "700.00"

    pay = await client.post(
        "/customer-payments",
        headers=h,
        json={
            "customer_id": customer_id,
            "payment_date": str(date.today()),
            "amount": "200",
            "payment_mode": "cash",
        },
    )
    assert pay.status_code == 201, pay.text
    after = (await client.get(f"/customers/{customer_id}", headers=h)).json()["current_balance"]
    assert after == "500.00"
