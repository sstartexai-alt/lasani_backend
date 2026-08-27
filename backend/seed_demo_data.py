"""Seed a small, realistic demo dataset so the API is testable immediately.

Run AFTER migrations:  python seed_demo_data.py

Inserts categories, products (mix of carton/piece), customers, suppliers, a few
purchase invoices and a few sales invoices. Rows are inserted in the correct
order so the database triggers populate stock and ledgers automatically.
"""
import asyncio
import secrets
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.customer import Customer
from app.models.product import Product, ProductCategory
from app.models.purchase import PurchaseInvoice, PurchaseInvoiceItem
from app.models.sales import SalesInvoice, SalesInvoiceItem
from app.models.supplier import Supplier
from app.models.user import User
from app.services.invoicing import to_pieces

TODAY = date.today()


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if admin is None:
            admin_password = secrets.token_urlsafe(16)
            admin = User(
                username="admin",
                password_hash=hash_password(admin_password),
                full_name="System Administrator",
                role="admin",
            )
            db.add(admin)
            await db.flush()
            print(f"Created admin user. Temporary password: {admin_password}")

        # A sales_entry demo user.
        if not (await db.execute(select(User).where(User.username == "sales1"))).scalar_one_or_none():
            db.add(
                User(
                    username="sales1",
                    password_hash=hash_password("sales12345"),
                    full_name="Sales Entry Demo",
                    role="sales_entry",
                )
            )

        existing = (await db.execute(select(ProductCategory))).scalars().first()
        if existing:
            await db.commit()
            print("Demo data already present. User accounts verified.")
            return

        # Categories
        beverages = ProductCategory(category_name="Beverages")
        snacks = ProductCategory(category_name="Snacks")
        household = ProductCategory(category_name="Household")
        db.add_all([beverages, snacks, household])
        await db.flush()

        # Products (mix of carton/piece)
        products = [
            Product(sku="BEV-001", product_name="Cola 500ml", category_id=beverages.category_id,
                    unit_type="both", pieces_per_carton=24, opening_stock=Decimal("240"),
                    current_stock=Decimal("240"), purchase_price=Decimal("40"), sale_price=Decimal("55"),
                    low_stock_threshold=Decimal("48")),
            Product(sku="BEV-002", product_name="Mineral Water 1.5L", category_id=beverages.category_id,
                    unit_type="carton", pieces_per_carton=12, opening_stock=Decimal("120"),
                    current_stock=Decimal("120"), purchase_price=Decimal("30"), sale_price=Decimal("45"),
                    low_stock_threshold=Decimal("24")),
            Product(sku="SNK-001", product_name="Potato Chips 50g", category_id=snacks.category_id,
                    unit_type="piece", pieces_per_carton=1, opening_stock=Decimal("300"),
                    current_stock=Decimal("300"), purchase_price=Decimal("20"), sale_price=Decimal("30"),
                    low_stock_threshold=Decimal("50")),
            Product(sku="HH-001", product_name="Dish Soap 500ml", category_id=household.category_id,
                    unit_type="both", pieces_per_carton=6, opening_stock=Decimal("60"),
                    current_stock=Decimal("60"), purchase_price=Decimal("120"), sale_price=Decimal("160"),
                    low_stock_threshold=Decimal("12")),
        ]
        db.add_all(products)

        # Customers
        customers = [
            Customer(customer_name="Ali General Store", area="Model Town",
                     contact_number="0300-1112223", opening_balance=Decimal("0"),
                     credit_limit=Decimal("50000")),
            Customer(customer_name="Hassan Mart", area="Gulberg",
                     contact_number="0301-4445556", opening_balance=Decimal("5000"),
                     credit_limit=Decimal("30000")),
        ]
        db.add_all(customers)

        # Suppliers
        suppliers = [
            Supplier(supplier_name="PepsiCo Distributor", contact_number="042-111000",
                     address="Industrial Estate", opening_balance=Decimal("0")),
            Supplier(supplier_name="Unilever Distributor", contact_number="042-222000",
                     address="Ferozepur Road", opening_balance=Decimal("10000")),
        ]
        db.add_all(suppliers)
        await db.flush()

        # Purchase invoice: buy more cola + water from supplier 1, partially paid.
        pinv = PurchaseInvoice(
            invoice_number=f"PUR-{TODAY.year}-000001",
            supplier_id=suppliers[0].supplier_id,
            purchase_date=TODAY - timedelta(days=3),
            total_amount=Decimal("10") * Decimal("24") * Decimal("40") + Decimal("5") * Decimal("12") * Decimal("30"),
            paid_amount=Decimal("5000"),
            created_by=admin.user_id,
        )
        db.add(pinv)
        await db.flush()
        db.add_all([
            PurchaseInvoiceItem(purchase_invoice_id=pinv.purchase_invoice_id, product_id=products[0].product_id,
                                unit_type="carton", quantity=Decimal("10"),
                                quantity_in_pieces=to_pieces("carton", Decimal("10"), 24),
                                purchase_rate=Decimal("40")),
            PurchaseInvoiceItem(purchase_invoice_id=pinv.purchase_invoice_id, product_id=products[1].product_id,
                                unit_type="carton", quantity=Decimal("5"),
                                quantity_in_pieces=to_pieces("carton", Decimal("5"), 12),
                                purchase_rate=Decimal("30")),
        ])

        # Sales invoice 1: cash sale (fully paid) to customer 1.
        sub1 = Decimal("24") * Decimal("55") + Decimal("10") * Decimal("30")
        sinv1 = SalesInvoice(
            invoice_number=f"INV-{TODAY.year}-000001",
            customer_id=customers[0].customer_id,
            invoice_date=TODAY,
            sale_type="cash",
            subtotal_amount=sub1,
            discount_amount=Decimal("0"),
            paid_amount=sub1,
            created_by=admin.user_id,
        )
        db.add(sinv1)
        await db.flush()
        db.add_all([
            SalesInvoiceItem(invoice_id=sinv1.invoice_id, product_id=products[0].product_id,
                             unit_type="piece", quantity=Decimal("24"),
                             quantity_in_pieces=Decimal("24"), rate=Decimal("55"),
                             discount_amount=Decimal("0")),
            SalesInvoiceItem(invoice_id=sinv1.invoice_id, product_id=products[2].product_id,
                             unit_type="piece", quantity=Decimal("10"),
                             quantity_in_pieces=Decimal("10"), rate=Decimal("30"),
                             discount_amount=Decimal("0")),
        ])

        # Sales invoice 2: credit sale (unpaid) to customer 2.
        sub2 = Decimal("2") * Decimal("160")
        sinv2 = SalesInvoice(
            invoice_number=f"INV-{TODAY.year}-000002",
            customer_id=customers[1].customer_id,
            invoice_date=TODAY,
            sale_type="credit",
            subtotal_amount=sub2,
            discount_amount=Decimal("0"),
            paid_amount=Decimal("0"),
            created_by=admin.user_id,
        )
        db.add(sinv2)
        await db.flush()
        db.add(
            SalesInvoiceItem(invoice_id=sinv2.invoice_id, product_id=products[3].product_id,
                             unit_type="piece", quantity=Decimal("2"),
                             quantity_in_pieces=Decimal("2"), rate=Decimal("160"),
                             discount_amount=Decimal("0"))
        )

        await db.commit()
        print("Demo data seeded successfully.")
        print("  - 3 categories, 4 products, 2 customers, 2 suppliers")
        print("  - 1 purchase invoice, 2 sales invoices")
        print("  - demo sales_entry user: sales1 / sales12345")


if __name__ == "__main__":
    async def main() -> None:
        try:
            await seed()
        finally:
            await engine.dispose()

    asyncio.run(main())
