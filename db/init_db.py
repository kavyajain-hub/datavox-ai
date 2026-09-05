import os
import sys

# Ensure project root is in sys.path when executed directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import text
from db.connection import get_engine
from config.settings import get_settings
import json

SAMPLE_SCHEMA_DEFINITIONS = [
    {
        "table": "customers",
        "description": "Customer profiles, demographic info, and sign-up dates. Referenced by: orders(customer_id)",
        "columns": "customer_id (INT, PK), name (VARCHAR), email (VARCHAR), region (VARCHAR), created_at (TIMESTAMP)"
    },
    {
        "table": "orders",
        "description": "Customer order records, order status, total amounts, and dates. Relationships: [customer_id references customers(customer_id)]",
        "columns": "order_id (INT, PK), customer_id (INT, FK -> customers.customer_id), order_date (DATE), total_amount (DECIMAL), status (VARCHAR)"
    },
    {
        "table": "order_items",
        "description": "Line items for each order. Relationships: [order_id references orders(order_id), product_id references products(product_id)]",
        "columns": "item_id (INT, PK), order_id (INT, FK -> orders.order_id), product_id (INT, FK -> products.product_id), quantity (INT), unit_price (DECIMAL)"
    },
    {
        "table": "products",
        "description": "Product catalog with categories, unit prices, and stock levels. Referenced by: order_items(product_id)",
        "columns": "product_id (INT, PK), product_name (VARCHAR), category (VARCHAR), unit_price (DECIMAL), stock_quantity (INT)"
    },
    {
        "table": "regional_sales",
        "description": "Aggregated daily sales numbers grouped by geographic region",
        "columns": "sales_id (INT, PK), region (VARCHAR), sales_date (DATE), total_revenue (DECIMAL), units_sold (INT)"
    }
]


def ensure_sample_schema_file():
    """Ensure schema.json contains the default sample tables if missing."""
    schema_file = os.path.join(os.path.dirname(__file__), "..", "schema.json")
    try:
        existing = []
        if os.path.exists(schema_file):
            try:
                with open(schema_file, "r") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        existing_names = {t.get("table") for t in existing if isinstance(t, dict)}
        needs_update = False
        for sample_tbl in SAMPLE_SCHEMA_DEFINITIONS:
            if sample_tbl["table"] not in existing_names:
                existing.append(sample_tbl)
                needs_update = True

        if needs_update or not existing:
            with open(schema_file, "w") as f:
                json.dump(existing or SAMPLE_SCHEMA_DEFINITIONS, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not update sample schema: {e}")


def create_and_seed_database():
    """Initialize sample tables and seed realistic sample data."""
    ensure_sample_schema_file()
    engine = get_engine()

    with engine.connect() as conn:
        # Create customers table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) NOT NULL UNIQUE,
                region VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Create products table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name VARCHAR(100) NOT NULL,
                category VARCHAR(50) NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                stock_quantity INTEGER NOT NULL
            );
        """))

        # Create orders table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                order_date DATE NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );
        """))

        # Create order_items table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );
        """))

        # Create regional_sales table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS regional_sales (
                sales_id INTEGER PRIMARY KEY AUTOINCREMENT,
                region VARCHAR(50) NOT NULL,
                sales_date DATE NOT NULL,
                total_revenue DECIMAL(12, 2) NOT NULL,
                units_sold INTEGER NOT NULL
            );
        """))

        # Check if already seeded
        ensure_sample_schema_file()
        res = conn.execute(text("SELECT COUNT(*) FROM customers;"))
        count = res.scalar()
        if count and count > 0:
            print(f"Database already populated ({count} customers found).")
            conn.commit()
            return

        # Seed Customers
        conn.execute(text("""
            INSERT INTO customers (name, email, region) VALUES
            ('Alice Smith', 'alice@example.com', 'North'),
            ('Bob Jones', 'bob@example.com', 'South'),
            ('Charlie Brown', 'charlie@example.com', 'East'),
            ('Diana Prince', 'diana@example.com', 'West'),
            ('Evan Wright', 'evan@example.com', 'North'),
            ('Fiona Gallagher', 'fiona@example.com', 'Central'),
            ('George Clark', 'george@example.com', 'South'),
            ('Hannah Abbott', 'hannah@example.com', 'East'),
            ('Ian Malcolm', 'ian@example.com', 'West'),
            ('Julia Roberts', 'julia@example.com', 'Central');
        """))

        # Seed Products
        conn.execute(text("""
            INSERT INTO products (product_name, category, unit_price, stock_quantity) VALUES
            ('Wireless Headphones', 'Electronics', 99.99, 150),
            ('Smart Watch', 'Electronics', 199.50, 80),
            ('Ergonomic Chair', 'Furniture', 249.00, 45),
            ('Standing Desk', 'Furniture', 499.00, 25),
            ('Cotton T-Shirt', 'Apparel', 24.99, 300),
            ('Denim Jeans', 'Apparel', 59.99, 200),
            ('Coffee Maker', 'Appliances', 79.99, 60),
            ('Blender', 'Appliances', 49.99, 90),
            ('Yoga Mat', 'Fitness', 29.99, 120),
            ('Dumbbell Set', 'Fitness', 89.99, 70);
        """))

        # Seed Orders
        conn.execute(text("""
            INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES
            (1, '2024-01-15', 299.49, 'completed'),
            (2, '2024-01-18', 99.99, 'completed'),
            (3, '2024-01-20', 748.00, 'completed'),
            (4, '2024-02-01', 84.98, 'completed'),
            (5, '2024-02-05', 499.00, 'shipped'),
            (1, '2024-02-10', 129.98, 'completed'),
            (6, '2024-02-14', 199.50, 'pending'),
            (7, '2024-02-20', 24.99, 'completed'),
            (8, '2024-03-01', 249.00, 'completed'),
            (9, '2024-03-05', 119.98, 'cancelled');
        """))

        # Seed Order Items
        conn.execute(text("""
            INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
            (1, 1, 1, 99.99),
            (1, 2, 1, 199.50),
            (2, 1, 1, 99.99),
            (3, 3, 1, 249.00),
            (3, 4, 1, 499.00),
            (4, 5, 1, 24.99),
            (4, 6, 1, 59.99),
            (5, 4, 1, 499.00),
            (6, 9, 1, 29.99),
            (6, 10, 1, 89.99);
        """))

        # Seed Regional Sales
        conn.execute(text("""
            INSERT INTO regional_sales (region, sales_date, total_revenue, units_sold) VALUES
            ('North', '2024-01-31', 45200.00, 310),
            ('South', '2024-01-31', 38400.00, 260),
            ('East', '2024-01-31', 52100.00, 420),
            ('West', '2024-01-31', 61500.00, 490),
            ('Central', '2024-01-31', 29800.00, 195),
            ('North', '2024-02-29', 48900.00, 340),
            ('South', '2024-02-29', 41200.00, 285),
            ('East', '2024-02-29', 54700.00, 440),
            ('West', '2024-02-29', 63800.00, 510),
            ('Central', '2024-02-29', 31500.00, 210);
        """))

        conn.commit()
        print("Database tables created and sample data successfully seeded.")

    # Populate schema.json with default sample schema if empty
    schema_file = os.path.join(os.path.dirname(__file__), "..", "schema.json")
    try:
        sample_schema = [
            {
                "table": "customers",
                "description": "Customer profiles, demographic info, and sign-up dates. Referenced by: orders(customer_id)",
                "columns": "customer_id (INT, PK), name (VARCHAR), email (VARCHAR), region (VARCHAR), created_at (TIMESTAMP)"
            },
            {
                "table": "orders",
                "description": "Customer order records, order status, total amounts, and dates. Relationships: [customer_id references customers(customer_id)]",
                "columns": "order_id (INT, PK), customer_id (INT, FK -> customers.customer_id), order_date (DATE), total_amount (DECIMAL), status (VARCHAR)"
            },
            {
                "table": "order_items",
                "description": "Line items for each order. Relationships: [order_id references orders(order_id), product_id references products(product_id)]",
                "columns": "item_id (INT, PK), order_id (INT, FK -> orders.order_id), product_id (INT, FK -> products.product_id), quantity (INT), unit_price (DECIMAL)"
            },
            {
                "table": "products",
                "description": "Product catalog with categories, unit prices, and stock levels. Referenced by: order_items(product_id)",
                "columns": "product_id (INT, PK), product_name (VARCHAR), category (VARCHAR), unit_price (DECIMAL), stock_quantity (INT)"
            },
            {
                "table": "regional_sales",
                "description": "Aggregated daily sales numbers grouped by geographic region",
                "columns": "sales_id (INT, PK), region (VARCHAR), sales_date (DATE), total_revenue (DECIMAL), units_sold (INT)"
            }
        ]
        with open(schema_file, "w") as f:
            import json
            json.dump(sample_schema, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not write sample schema.json: {e}")


if __name__ == "__main__":
    create_and_seed_database()
