import sqlite3
from werkzeug.security import generate_password_hash

# Connect to the database (creates it if it doesn't exist)
connection = sqlite3.connect("cafe.db")

# Create a cursor
cursor = connection.cursor()

# Create Users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

# Create Sales table
cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    date TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    payment_method TEXT NOT NULL
)
""")

# Create Inventory table
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    current_stock REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL,
    min_threshold REAL NOT NULL DEFAULT 5,
    unit_cost REAL NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL
)
""")

# Create Recipes table (links products to inventory ingredients)
cursor.execute("""
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    product_name TEXT NOT NULL,
    inventory_id INTEGER NOT NULL,
    quantity_required REAL NOT NULL,
    FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE CASCADE
)
""")

# Create default admin user
cursor.execute("""
INSERT OR IGNORE INTO users
(username, password)
VALUES (?, ?)
""", (
    "admin",
    generate_password_hash("admin123")
))

# Save changes
connection.commit()

# Close database
connection.close()

print("[OK] Database and tables created successfully!")