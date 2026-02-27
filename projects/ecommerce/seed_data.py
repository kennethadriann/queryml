"""Generate seed CSV data and load into DuckDB for the e-commerce example project."""

import csv
import random
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "ecommerce.db"

random.seed(42)

REGIONS = ["West", "East", "Central", "South"]
SEGMENTS = ["Consumer", "Corporate", "Home Office"]
STATUSES = ["completed", "completed", "completed", "completed", "completed",
            "completed", "completed", "returned", "cancelled"]  # ~11% return, ~11% cancel

CATEGORIES = {
    "Electronics": {
        "sub_categories": ["Phones", "Laptops", "Accessories", "Audio"],
        "price_range": (50, 1200),
    },
    "Clothing": {
        "sub_categories": ["Men", "Women", "Kids", "Activewear"],
        "price_range": (20, 300),
    },
    "Home": {
        "sub_categories": ["Furniture", "Decor", "Kitchen", "Bedding"],
        "price_range": (30, 800),
    },
    "Office Supplies": {
        "sub_categories": ["Paper", "Pens", "Storage", "Tech Accessories"],
        "price_range": (5, 150),
    },
}


def generate_products():
    products = []
    pid = 1
    for cat, info in CATEGORIES.items():
        for sub in info["sub_categories"]:
            for i in range(5):  # 5 products per sub-category
                products.append({
                    "product_id": f"P{pid:04d}",
                    "product_name": f"{sub} Item {i+1}",
                    "category": cat,
                    "sub_category": sub,
                    "base_price": random.randint(*info["price_range"]),
                })
                pid += 1
    return products


def generate_customers():
    first_names = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace",
                   "Hank", "Iris", "Jack", "Karen", "Leo", "Mia", "Nick",
                   "Olivia", "Paul", "Quinn", "Rita", "Sam", "Tina"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                  "Miller", "Davis", "Rodriguez", "Martinez"]
    customers = []
    for i in range(100):
        customers.append({
            "customer_id": f"C{i+1:04d}",
            "customer_name": f"{random.choice(first_names)} {random.choice(last_names)}",
            "customer_segment": random.choice(SEGMENTS),
            "region": random.choice(REGIONS),
        })
    return customers


def generate_orders(products, customers):
    orders = []
    # Generate 12 months of data
    for month in range(1, 13):
        # Vary order volume by month (seasonality — Q4 is higher)
        base_count = 80 if month >= 10 else 50
        num_orders = random.randint(base_count, base_count + 40)

        for i in range(num_orders):
            customer = random.choice(customers)
            product = random.choice(products)
            status = random.choice(STATUSES)

            # Corporate orders tend to be larger
            multiplier = 1.5 if customer["customer_segment"] == "Corporate" else 1.0
            revenue = round(product["base_price"] * multiplier * random.uniform(0.8, 1.3), 2)

            # Deliberately make South region have higher return rates
            if customer["region"] == "South" and random.random() < 0.15:
                status = "returned"

            # Deliberately make Electronics have higher return rates
            if product["category"] == "Electronics" and random.random() < 0.10:
                status = "returned"

            day = random.randint(1, 28)
            orders.append({
                "order_id": f"O{len(orders)+1:05d}",
                "order_date": f"2025-{month:02d}-{day:02d}",
                "customer_id": customer["customer_id"],
                "product_id": product["product_id"],
                "region": customer["region"],
                "customer_segment": customer["customer_segment"],
                "status": status,
                "revenue": revenue,
                "is_returned": 1 if status == "returned" else 0,
                "order_count_raw": 1,
            })
    return orders


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    products = generate_products()
    customers = generate_customers()
    orders = generate_orders(products, customers)

    # Write CSVs
    write_csv(DATA_DIR / "products.csv", products,
              ["product_id", "product_name", "category", "sub_category", "base_price"])
    write_csv(DATA_DIR / "customers.csv", customers,
              ["customer_id", "customer_name", "customer_segment", "region"])
    write_csv(DATA_DIR / "orders.csv", orders,
              ["order_id", "order_date", "customer_id", "product_id", "region",
               "customer_segment", "status", "revenue", "is_returned", "order_count_raw"])

    # Load into DuckDB
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = duckdb.connect(str(DB_PATH))

    conn.execute("""
        CREATE TABLE products AS
        SELECT * FROM read_csv_auto(?)
    """, [str(DATA_DIR / "products.csv")])

    conn.execute("""
        CREATE TABLE customers AS
        SELECT * FROM read_csv_auto(?)
    """, [str(DATA_DIR / "customers.csv")])

    conn.execute("""
        CREATE TABLE orders AS
        SELECT * FROM read_csv_auto(?)
    """, [str(DATA_DIR / "orders.csv")])

    # Verify
    for table in ["products", "customers", "orders"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")

    conn.close()
    print(f"\nDatabase created at {DB_PATH}")


if __name__ == "__main__":
    main()
