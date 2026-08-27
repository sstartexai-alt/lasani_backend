"""initial schema: tables, triggers, views, seed admin

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-25

Reproduces the finalized MySQL schema exactly (tables + generated columns +
indexes + views) and adds the database-level triggers that keep stock and
ledgers in sync, plus a seeded admin user.
"""
import secrets
from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = [
    """
    CREATE TABLE `users` (
      `user_id` int unsigned NOT NULL AUTO_INCREMENT,
      `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
      `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
      `full_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
      `role` enum('admin','sales_entry') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'sales_entry',
      `is_active` tinyint(1) NOT NULL DEFAULT '1',
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`user_id`),
      UNIQUE KEY `username` (`username`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `product_categories` (
      `category_id` int unsigned NOT NULL AUTO_INCREMENT,
      `category_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`category_id`),
      UNIQUE KEY `category_name` (`category_name`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `products` (
      `product_id` int unsigned NOT NULL AUTO_INCREMENT,
      `sku` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
      `product_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
      `category_id` int unsigned DEFAULT NULL,
      `unit_type` enum('carton','piece','both') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'piece',
      `pieces_per_carton` int unsigned NOT NULL DEFAULT '1',
      `opening_stock` decimal(10,2) NOT NULL DEFAULT '0.00',
      `current_stock` decimal(10,2) NOT NULL DEFAULT '0.00',
      `purchase_price` decimal(12,2) NOT NULL DEFAULT '0.00',
      `stock_value` decimal(14,2) GENERATED ALWAYS AS ((`current_stock` * `purchase_price`)) STORED,
      `sale_price` decimal(12,2) NOT NULL DEFAULT '0.00',
      `low_stock_threshold` decimal(10,2) NOT NULL DEFAULT '0.00',
      `is_active` tinyint(1) NOT NULL DEFAULT '1',
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`product_id`),
      UNIQUE KEY `sku` (`sku`),
      KEY `fk_products_category` (`category_id`),
      KEY `idx_products_name` (`product_name`),
      KEY `idx_products_low_stock` (`current_stock`,`low_stock_threshold`),
      CONSTRAINT `fk_products_category` FOREIGN KEY (`category_id`) REFERENCES `product_categories` (`category_id`) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `customers` (
      `customer_id` int unsigned NOT NULL AUTO_INCREMENT,
      `customer_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
      `area` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `contact_number` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `opening_balance` decimal(12,2) NOT NULL DEFAULT '0.00',
      `credit_limit` decimal(12,2) NOT NULL DEFAULT '0.00',
      `current_balance` decimal(12,2) NOT NULL DEFAULT '0.00',
      `is_active` tinyint(1) NOT NULL DEFAULT '1',
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`customer_id`),
      KEY `idx_customers_name` (`customer_name`),
      KEY `idx_customers_area` (`area`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `suppliers` (
      `supplier_id` int unsigned NOT NULL AUTO_INCREMENT,
      `supplier_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
      `contact_number` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `address` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `opening_balance` decimal(12,2) NOT NULL DEFAULT '0.00',
      `current_balance` decimal(12,2) NOT NULL DEFAULT '0.00',
      `is_active` tinyint(1) NOT NULL DEFAULT '1',
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`supplier_id`),
      KEY `idx_suppliers_name` (`supplier_name`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `stock_ledger` (
      `stock_ledger_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `product_id` int unsigned NOT NULL,
      `transaction_type` enum('opening','purchase','sale','adjustment') COLLATE utf8mb4_unicode_ci NOT NULL,
      `reference_table` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `reference_id` bigint unsigned DEFAULT NULL,
      `quantity_change` decimal(10,2) NOT NULL,
      `balance_after` decimal(10,2) NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`stock_ledger_id`),
      KEY `idx_stockledger_product_date` (`product_id`,`created_at`),
      CONSTRAINT `fk_stockledger_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `customer_ledger` (
      `ledger_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `customer_id` int unsigned NOT NULL,
      `transaction_date` date NOT NULL,
      `transaction_type` enum('opening_balance','invoice','payment','adjustment') COLLATE utf8mb4_unicode_ci NOT NULL,
      `reference_table` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `reference_id` bigint unsigned DEFAULT NULL,
      `debit` decimal(12,2) NOT NULL DEFAULT '0.00',
      `credit` decimal(12,2) NOT NULL DEFAULT '0.00',
      `balance_after` decimal(12,2) NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`ledger_id`),
      KEY `idx_custledger_customer_date` (`customer_id`,`transaction_date`),
      CONSTRAINT `fk_custledger_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `customer_payments` (
      `payment_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `customer_id` int unsigned NOT NULL,
      `payment_date` date NOT NULL,
      `amount` decimal(12,2) NOT NULL,
      `payment_mode` enum('cash','bank') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'cash',
      `reference_note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `received_by` int unsigned NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`payment_id`),
      KEY `fk_custpay_user` (`received_by`),
      KEY `idx_custpay_customer_date` (`customer_id`,`payment_date`),
      CONSTRAINT `fk_custpay_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
      CONSTRAINT `fk_custpay_user` FOREIGN KEY (`received_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `supplier_ledger` (
      `ledger_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `supplier_id` int unsigned NOT NULL,
      `transaction_date` date NOT NULL,
      `transaction_type` enum('opening_balance','purchase','payment','adjustment') COLLATE utf8mb4_unicode_ci NOT NULL,
      `reference_table` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `reference_id` bigint unsigned DEFAULT NULL,
      `debit` decimal(12,2) NOT NULL DEFAULT '0.00',
      `credit` decimal(12,2) NOT NULL DEFAULT '0.00',
      `balance_after` decimal(12,2) NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`ledger_id`),
      KEY `idx_supledger_supplier_date` (`supplier_id`,`transaction_date`),
      CONSTRAINT `fk_supledger_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers` (`supplier_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `supplier_payments` (
      `payment_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `supplier_id` int unsigned NOT NULL,
      `payment_date` date NOT NULL,
      `amount` decimal(12,2) NOT NULL,
      `payment_mode` enum('cash','bank') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'cash',
      `reference_note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `paid_by` int unsigned NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`payment_id`),
      KEY `fk_suppay_user` (`paid_by`),
      KEY `idx_suppay_supplier_date` (`supplier_id`,`payment_date`),
      CONSTRAINT `fk_suppay_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers` (`supplier_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
      CONSTRAINT `fk_suppay_user` FOREIGN KEY (`paid_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `purchase_invoices` (
      `purchase_invoice_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `invoice_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
      `supplier_id` int unsigned NOT NULL,
      `purchase_date` date NOT NULL,
      `total_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
      `paid_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
      `outstanding_amount` decimal(12,2) GENERATED ALWAYS AS ((`total_amount` - `paid_amount`)) STORED,
      `payment_status` enum('unpaid','partial','paid') COLLATE utf8mb4_unicode_ci GENERATED ALWAYS AS ((case when (`paid_amount` <= 0) then _utf8mb4'unpaid' when (`paid_amount` >= `total_amount`) then _utf8mb4'paid' else _utf8mb4'partial' end)) STORED,
      `created_by` int unsigned NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`purchase_invoice_id`),
      UNIQUE KEY `invoice_number` (`invoice_number`),
      KEY `fk_purchinv_user` (`created_by`),
      KEY `idx_purchinv_date` (`purchase_date`),
      KEY `idx_purchinv_supplier` (`supplier_id`),
      CONSTRAINT `fk_purchinv_supplier` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers` (`supplier_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
      CONSTRAINT `fk_purchinv_user` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `purchase_invoice_items` (
      `purchase_item_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `purchase_invoice_id` bigint unsigned NOT NULL,
      `product_id` int unsigned NOT NULL,
      `unit_type` enum('carton','piece') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'piece',
      `quantity` decimal(10,2) NOT NULL,
      `quantity_in_pieces` decimal(10,2) NOT NULL,
      `purchase_rate` decimal(12,2) NOT NULL,
      `total_amount` decimal(12,2) GENERATED ALWAYS AS ((`quantity` * `purchase_rate`)) STORED,
      PRIMARY KEY (`purchase_item_id`),
      KEY `idx_purchitem_invoice` (`purchase_invoice_id`),
      KEY `idx_purchitem_product` (`product_id`),
      CONSTRAINT `fk_purchitem_invoice` FOREIGN KEY (`purchase_invoice_id`) REFERENCES `purchase_invoices` (`purchase_invoice_id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_purchitem_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `sales_invoices` (
      `invoice_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `invoice_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
      `customer_id` int unsigned NOT NULL,
      `invoice_date` date NOT NULL,
      `sale_type` enum('cash','credit') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'cash',
      `subtotal_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
      `discount_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
      `total_amount` decimal(12,2) GENERATED ALWAYS AS ((`subtotal_amount` - `discount_amount`)) STORED,
      `paid_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
      `outstanding_amount` decimal(12,2) GENERATED ALWAYS AS (((`subtotal_amount` - `discount_amount`) - `paid_amount`)) STORED,
      `created_by` int unsigned NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`invoice_id`),
      UNIQUE KEY `invoice_number` (`invoice_number`),
      KEY `fk_salesinv_user` (`created_by`),
      KEY `idx_salesinv_date` (`invoice_date`),
      KEY `idx_salesinv_customer` (`customer_id`),
      CONSTRAINT `fk_salesinv_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`customer_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
      CONSTRAINT `fk_salesinv_user` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `sales_invoice_items` (
      `sales_item_id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `invoice_id` bigint unsigned NOT NULL,
      `product_id` int unsigned NOT NULL,
      `unit_type` enum('carton','piece') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'piece',
      `quantity` decimal(10,2) NOT NULL,
      `quantity_in_pieces` decimal(10,2) NOT NULL,
      `rate` decimal(12,2) NOT NULL,
      `discount_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
      `total_amount` decimal(12,2) GENERATED ALWAYS AS (((`quantity` * `rate`) - `discount_amount`)) STORED,
      PRIMARY KEY (`sales_item_id`),
      KEY `idx_salesitem_invoice` (`invoice_id`),
      KEY `idx_salesitem_product` (`product_id`),
      CONSTRAINT `fk_salesitem_invoice` FOREIGN KEY (`invoice_id`) REFERENCES `sales_invoices` (`invoice_id`) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT `fk_salesitem_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE `backup_logs` (
      `backup_id` int unsigned NOT NULL AUTO_INCREMENT,
      `file_path` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
      `backup_type` enum('manual','automatic') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'manual',
      `performed_by` int unsigned NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`backup_id`),
      KEY `fk_backup_user` (`performed_by`),
      CONSTRAINT `fk_backup_user` FOREIGN KEY (`performed_by`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


TRIGGERS = [
    # Opening stock ledger seed for new products (current_stock is set by the API to opening_stock).
    """
    CREATE TRIGGER trg_products_after_insert AFTER INSERT ON products
    FOR EACH ROW
    BEGIN
      IF NEW.opening_stock <> 0 THEN
        INSERT INTO stock_ledger (product_id, transaction_type, reference_table, reference_id, quantity_change, balance_after)
        VALUES (NEW.product_id, 'opening', 'products', NEW.product_id, NEW.opening_stock, NEW.opening_stock);
      END IF;
    END
    """,
    # Seed current_balance from opening_balance for customers/suppliers.
    """
    CREATE TRIGGER trg_customers_before_insert BEFORE INSERT ON customers
    FOR EACH ROW
    BEGIN
      SET NEW.current_balance = NEW.opening_balance;
    END
    """,
    """
    CREATE TRIGGER trg_customers_after_insert AFTER INSERT ON customers
    FOR EACH ROW
    BEGIN
      IF NEW.opening_balance <> 0 THEN
        INSERT INTO customer_ledger (customer_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
        VALUES (NEW.customer_id, CURDATE(), 'opening_balance', 'customers', NEW.customer_id, NEW.opening_balance, 0, NEW.opening_balance);
      END IF;
    END
    """,
    """
    CREATE TRIGGER trg_suppliers_before_insert BEFORE INSERT ON suppliers
    FOR EACH ROW
    BEGIN
      SET NEW.current_balance = NEW.opening_balance;
    END
    """,
    """
    CREATE TRIGGER trg_suppliers_after_insert AFTER INSERT ON suppliers
    FOR EACH ROW
    BEGIN
      IF NEW.opening_balance <> 0 THEN
        INSERT INTO supplier_ledger (supplier_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
        VALUES (NEW.supplier_id, CURDATE(), 'opening_balance', 'suppliers', NEW.supplier_id, 0, NEW.opening_balance, NEW.opening_balance);
      END IF;
    END
    """,
    # Purchase item -> increase stock + stock ledger.
    """
    CREATE TRIGGER trg_purchitem_after_insert AFTER INSERT ON purchase_invoice_items
    FOR EACH ROW
    BEGIN
      UPDATE products SET current_stock = current_stock + NEW.quantity_in_pieces WHERE product_id = NEW.product_id;
      INSERT INTO stock_ledger (product_id, transaction_type, reference_table, reference_id, quantity_change, balance_after)
      SELECT NEW.product_id, 'purchase', 'purchase_invoice_items', NEW.purchase_item_id, NEW.quantity_in_pieces, current_stock
      FROM products WHERE product_id = NEW.product_id;
    END
    """,
    # Sales item -> decrease stock + stock ledger.
    """
    CREATE TRIGGER trg_salesitem_after_insert AFTER INSERT ON sales_invoice_items
    FOR EACH ROW
    BEGIN
      UPDATE products SET current_stock = current_stock - NEW.quantity_in_pieces WHERE product_id = NEW.product_id;
      INSERT INTO stock_ledger (product_id, transaction_type, reference_table, reference_id, quantity_change, balance_after)
      SELECT NEW.product_id, 'sale', 'sales_invoice_items', NEW.sales_item_id, -NEW.quantity_in_pieces, current_stock
      FROM products WHERE product_id = NEW.product_id;
    END
    """,
    # Purchase invoice -> increase payable + supplier ledger (and record immediate payment).
    """
    CREATE TRIGGER trg_purchinv_after_insert AFTER INSERT ON purchase_invoices
    FOR EACH ROW
    BEGIN
      UPDATE suppliers SET current_balance = current_balance + NEW.total_amount WHERE supplier_id = NEW.supplier_id;
      INSERT INTO supplier_ledger (supplier_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
      SELECT NEW.supplier_id, NEW.purchase_date, 'purchase', 'purchase_invoices', NEW.purchase_invoice_id, 0, NEW.total_amount, current_balance
      FROM suppliers WHERE supplier_id = NEW.supplier_id;
      IF NEW.paid_amount > 0 THEN
        UPDATE suppliers SET current_balance = current_balance - NEW.paid_amount WHERE supplier_id = NEW.supplier_id;
        INSERT INTO supplier_ledger (supplier_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
        SELECT NEW.supplier_id, NEW.purchase_date, 'payment', 'purchase_invoices', NEW.purchase_invoice_id, NEW.paid_amount, 0, current_balance
        FROM suppliers WHERE supplier_id = NEW.supplier_id;
      END IF;
    END
    """,
    # Sales invoice -> increase receivable + customer ledger (and record immediate payment).
    """
    CREATE TRIGGER trg_salesinv_after_insert AFTER INSERT ON sales_invoices
    FOR EACH ROW
    BEGIN
      UPDATE customers SET current_balance = current_balance + NEW.total_amount WHERE customer_id = NEW.customer_id;
      INSERT INTO customer_ledger (customer_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
      SELECT NEW.customer_id, NEW.invoice_date, 'invoice', 'sales_invoices', NEW.invoice_id, NEW.total_amount, 0, current_balance
      FROM customers WHERE customer_id = NEW.customer_id;
      IF NEW.paid_amount > 0 THEN
        UPDATE customers SET current_balance = current_balance - NEW.paid_amount WHERE customer_id = NEW.customer_id;
        INSERT INTO customer_ledger (customer_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
        SELECT NEW.customer_id, NEW.invoice_date, 'payment', 'sales_invoices', NEW.invoice_id, 0, NEW.paid_amount, current_balance
        FROM customers WHERE customer_id = NEW.customer_id;
      END IF;
    END
    """,
    # Standalone customer payment -> reduce receivable + ledger.
    """
    CREATE TRIGGER trg_custpay_after_insert AFTER INSERT ON customer_payments
    FOR EACH ROW
    BEGIN
      UPDATE customers SET current_balance = current_balance - NEW.amount WHERE customer_id = NEW.customer_id;
      INSERT INTO customer_ledger (customer_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
      SELECT NEW.customer_id, NEW.payment_date, 'payment', 'customer_payments', NEW.payment_id, 0, NEW.amount, current_balance
      FROM customers WHERE customer_id = NEW.customer_id;
    END
    """,
    # Standalone supplier payment -> reduce payable + ledger.
    """
    CREATE TRIGGER trg_suppay_after_insert AFTER INSERT ON supplier_payments
    FOR EACH ROW
    BEGIN
      UPDATE suppliers SET current_balance = current_balance - NEW.amount WHERE supplier_id = NEW.supplier_id;
      INSERT INTO supplier_ledger (supplier_id, transaction_date, transaction_type, reference_table, reference_id, debit, credit, balance_after)
      SELECT NEW.supplier_id, NEW.payment_date, 'payment', 'supplier_payments', NEW.payment_id, NEW.amount, 0, current_balance
      FROM suppliers WHERE supplier_id = NEW.supplier_id;
    END
    """,
]


VIEWS = [
    """
    CREATE VIEW `vw_cash_summary` AS
    SELECT CURDATE() AS `report_date`,
      (SELECT COALESCE(SUM(`customer_payments`.`amount`),0) FROM `customer_payments`
        WHERE ((`customer_payments`.`payment_mode` = 'cash') AND (`customer_payments`.`payment_date` = CURDATE()))) AS `cash_in_from_customers`,
      (SELECT COALESCE(SUM(`supplier_payments`.`amount`),0) FROM `supplier_payments`
        WHERE ((`supplier_payments`.`payment_mode` = 'cash') AND (`supplier_payments`.`payment_date` = CURDATE()))) AS `cash_out_to_suppliers`
    """,
    """
    CREATE VIEW `vw_customer_wise_sales` AS
    SELECT `c`.`customer_id` AS `customer_id`, `c`.`customer_name` AS `customer_name`,
      COUNT(DISTINCT `si`.`invoice_id`) AS `invoice_count`,
      COALESCE(SUM(`si`.`total_amount`),0) AS `total_sales`,
      `c`.`current_balance` AS `outstanding_balance`
    FROM (`customers` `c` LEFT JOIN `sales_invoices` `si` ON ((`si`.`customer_id` = `c`.`customer_id`)))
    GROUP BY `c`.`customer_id`, `c`.`customer_name`, `c`.`current_balance`
    """,
    """
    CREATE VIEW `vw_dashboard_summary` AS
    SELECT
      (SELECT COALESCE(SUM(`products`.`current_stock`),0) FROM `products` WHERE (`products`.`is_active` = 1)) AS `total_stock_pieces`,
      (SELECT COALESCE(SUM(`products`.`stock_value`),0) FROM `products` WHERE (`products`.`is_active` = 1)) AS `total_stock_value`,
      (SELECT COALESCE(SUM(`sales_invoices`.`total_amount`),0) FROM `sales_invoices` WHERE (`sales_invoices`.`invoice_date` = CURDATE())) AS `today_sales`,
      (SELECT COALESCE(SUM(`customers`.`current_balance`),0) FROM `customers` WHERE (`customers`.`current_balance` > 0)) AS `total_receivable`,
      (SELECT COALESCE(SUM(`suppliers`.`current_balance`),0) FROM `suppliers` WHERE (`suppliers`.`current_balance` > 0)) AS `total_payable`
    """,
    """
    CREATE VIEW `vw_monthly_sales` AS
    SELECT DATE_FORMAT(`si`.`invoice_date`,'%Y-%m') AS `sales_month`,
      COUNT(DISTINCT `si`.`invoice_id`) AS `invoice_count`,
      SUM(`si`.`total_amount`) AS `total_sales`
    FROM `sales_invoices` `si` GROUP BY DATE_FORMAT(`si`.`invoice_date`,'%Y-%m')
    """,
    """
    CREATE VIEW `vw_outstanding_customers` AS
    SELECT `customers`.`customer_id` AS `customer_id`, `customers`.`customer_name` AS `customer_name`,
      `customers`.`area` AS `area`, `customers`.`contact_number` AS `contact_number`,
      `customers`.`current_balance` AS `current_balance`
    FROM `customers` WHERE (`customers`.`current_balance` > 0)
    """,
    """
    CREATE VIEW `vw_product_wise_sales` AS
    SELECT `p`.`product_id` AS `product_id`, `p`.`product_name` AS `product_name`,
      SUM(`sii`.`quantity_in_pieces`) AS `total_qty_sold_pieces`,
      SUM(`sii`.`total_amount`) AS `total_sales_amount`
    FROM (`products` `p` JOIN `sales_invoice_items` `sii` ON ((`sii`.`product_id` = `p`.`product_id`)))
    GROUP BY `p`.`product_id`, `p`.`product_name`
    """,
    """
    CREATE VIEW `vw_profit_report` AS
    SELECT `sii`.`invoice_id` AS `invoice_id`, `si`.`invoice_date` AS `invoice_date`,
      `p`.`product_id` AS `product_id`, `p`.`product_name` AS `product_name`,
      `sii`.`quantity_in_pieces` AS `quantity_in_pieces`, `sii`.`rate` AS `sale_rate`,
      `p`.`purchase_price` AS `cost_rate`, `sii`.`total_amount` AS `sale_amount`,
      (`p`.`purchase_price` * `sii`.`quantity_in_pieces`) AS `cost_amount`,
      (`sii`.`total_amount` - (`p`.`purchase_price` * `sii`.`quantity_in_pieces`)) AS `profit`
    FROM ((`sales_invoice_items` `sii` JOIN `sales_invoices` `si` ON ((`si`.`invoice_id` = `sii`.`invoice_id`)))
      JOIN `products` `p` ON ((`p`.`product_id` = `sii`.`product_id`)))
    """,
    """
    CREATE VIEW `vw_purchase_report` AS
    SELECT `pi`.`purchase_invoice_id` AS `purchase_invoice_id`, `pi`.`invoice_number` AS `invoice_number`,
      `pi`.`purchase_date` AS `purchase_date`, `s`.`supplier_name` AS `supplier_name`,
      `pi`.`total_amount` AS `total_amount`, `pi`.`paid_amount` AS `paid_amount`,
      `pi`.`outstanding_amount` AS `outstanding_amount`
    FROM (`purchase_invoices` `pi` JOIN `suppliers` `s` ON ((`s`.`supplier_id` = `pi`.`supplier_id`)))
    """,
    """
    CREATE VIEW `vw_stock_report` AS
    SELECT `products`.`product_id` AS `product_id`, `products`.`sku` AS `sku`,
      `products`.`product_name` AS `product_name`, `products`.`unit_type` AS `unit_type`,
      `products`.`current_stock` AS `current_stock`, `products`.`purchase_price` AS `purchase_price`,
      `products`.`stock_value` AS `stock_value`, `products`.`low_stock_threshold` AS `low_stock_threshold`,
      (`products`.`current_stock` <= `products`.`low_stock_threshold`) AS `is_low_stock`
    FROM `products` WHERE (`products`.`is_active` = 1)
    """,
    """
    CREATE VIEW `vw_today_sales` AS
    SELECT `si`.`invoice_date` AS `invoice_date`, COUNT(DISTINCT `si`.`invoice_id`) AS `invoice_count`,
      SUM(`si`.`total_amount`) AS `total_sales`, SUM(`si`.`paid_amount`) AS `total_received`,
      SUM(`si`.`outstanding_amount`) AS `total_outstanding`
    FROM `sales_invoices` `si` WHERE (`si`.`invoice_date` = CURDATE()) GROUP BY `si`.`invoice_date`
    """,
]

VIEW_NAMES = [
    "vw_cash_summary",
    "vw_customer_wise_sales",
    "vw_dashboard_summary",
    "vw_monthly_sales",
    "vw_outstanding_customers",
    "vw_product_wise_sales",
    "vw_profit_report",
    "vw_purchase_report",
    "vw_stock_report",
    "vw_today_sales",
]

TRIGGER_NAMES = [
    "trg_products_after_insert",
    "trg_customers_before_insert",
    "trg_customers_after_insert",
    "trg_suppliers_before_insert",
    "trg_suppliers_after_insert",
    "trg_purchitem_after_insert",
    "trg_salesitem_after_insert",
    "trg_purchinv_after_insert",
    "trg_salesinv_after_insert",
    "trg_custpay_after_insert",
    "trg_suppay_after_insert",
]

TABLE_NAMES = [
    "backup_logs",
    "sales_invoice_items",
    "sales_invoices",
    "purchase_invoice_items",
    "purchase_invoices",
    "supplier_payments",
    "supplier_ledger",
    "customer_payments",
    "customer_ledger",
    "stock_ledger",
    "suppliers",
    "customers",
    "products",
    "product_categories",
    "users",
]


def upgrade() -> None:
    for stmt in TABLES:
        op.execute(stmt)
    for stmt in TRIGGERS:
        op.execute(stmt)
    for stmt in VIEWS:
        op.execute(stmt)

    # Seed a default admin with a strong random password printed to the console.
    from app.core.security import hash_password

    password = secrets.token_urlsafe(16)
    pw_hash = hash_password(password).replace("'", "''")
    op.execute(
        "INSERT INTO users (username, password_hash, full_name, role, is_active) "
        f"VALUES ('admin', '{pw_hash}', 'System Administrator', 'admin', 1)"
    )
    print("\n" + "=" * 70)
    print("  DEFAULT ADMIN CREATED")
    print("  username: admin")
    print(f"  password: {password}")
    print("  >>> Log in and change this password immediately via")
    print("  >>> POST /api/v1/auth/change-password")
    print("=" * 70 + "\n")


def downgrade() -> None:
    for name in VIEW_NAMES:
        op.execute(f"DROP VIEW IF EXISTS `{name}`")
    for name in TRIGGER_NAMES:
        op.execute(f"DROP TRIGGER IF EXISTS `{name}`")
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    for name in TABLE_NAMES:
        op.execute(f"DROP TABLE IF EXISTS `{name}`")
    op.execute("SET FOREIGN_KEY_CHECKS=1")
