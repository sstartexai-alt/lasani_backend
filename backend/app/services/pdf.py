from datetime import date
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

SHOP_NAME = "Inam Ur Rehman Commission Shop"


def _money(value) -> str:
    return f"{Decimal(value):,.2f}"


def _build(title: str, meta: list[tuple[str, str]], columns: list[str],
           rows: list[list], totals: list[tuple[str, str]]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(SHOP_NAME, styles["Title"]))
    elements.append(Paragraph(title, styles["Heading2"]))
    elements.append(Spacer(1, 6 * mm))

    meta_table = Table([[Paragraph(f"<b>{k}:</b> {v}", styles["Normal"])] for k, v in meta])
    meta_table.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    elements.append(meta_table)
    elements.append(Spacer(1, 6 * mm))

    data = [columns] + rows
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    totals_table = Table([[k, v] for k, v in totals], colWidths=[120 * mm, 40 * mm])
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(totals_table)
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph("Thank you for your business.", styles["Italic"]))

    doc.build(elements)
    return buffer.getvalue()


def sales_invoice_pdf(invoice, customer, product_names: dict[int, str]) -> bytes:
    meta = [
        ("Invoice #", invoice.invoice_number),
        ("Date", str(invoice.invoice_date)),
        ("Customer", customer.customer_name),
        ("Area", customer.area or "-"),
        ("Sale Type", invoice.sale_type),
    ]
    columns = ["Product", "Unit", "Qty", "Rate", "Discount", "Amount"]
    rows = [
        [
            product_names.get(it.product_id, str(it.product_id)),
            it.unit_type,
            _money(it.quantity),
            _money(it.rate),
            _money(it.discount_amount),
            _money(it.total_amount),
        ]
        for it in invoice.items
    ]
    totals = [
        ("Subtotal", _money(invoice.subtotal_amount)),
        ("Discount", _money(invoice.discount_amount)),
        ("Total", _money(invoice.total_amount)),
        ("Paid", _money(invoice.paid_amount)),
        ("Outstanding", _money(invoice.outstanding_amount)),
    ]
    return _build("Sales Invoice", meta, columns, rows, totals)


def purchase_invoice_pdf(invoice, supplier, product_names: dict[int, str]) -> bytes:
    meta = [
        ("Invoice #", invoice.invoice_number),
        ("Date", str(invoice.purchase_date)),
        ("Supplier", supplier.supplier_name),
        ("Contact", supplier.contact_number or "-"),
        ("Status", invoice.payment_status),
    ]
    columns = ["Product", "Unit", "Qty", "Pieces", "Rate", "Amount"]
    rows = [
        [
            product_names.get(it.product_id, str(it.product_id)),
            it.unit_type,
            _money(it.quantity),
            _money(it.quantity_in_pieces),
            _money(it.purchase_rate),
            _money(it.total_amount),
        ]
        for it in invoice.items
    ]
    totals = [
        ("Total", _money(invoice.total_amount)),
        ("Paid", _money(invoice.paid_amount)),
        ("Outstanding", _money(invoice.outstanding_amount)),
    ]
    return _build("Purchase Invoice", meta, columns, rows, totals)
