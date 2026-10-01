import unittest
import sqlite3
import io
from app import app

class InventoryTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Ensure admin user exists and simulate session
        with self.app.session_transaction() as sess:
            sess["username"] = "test_manager"

        # Clean up test data for test_manager
        conn = sqlite3.connect("cafe.db")
        c = conn.cursor()
        c.execute("DELETE FROM recipes WHERE username = 'test_manager'")
        c.execute("DELETE FROM inventory WHERE username = 'test_manager'")
        c.execute("DELETE FROM sales WHERE username = 'test_manager'")
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = sqlite3.connect("cafe.db")
        c = conn.cursor()
        c.execute("DELETE FROM recipes WHERE username = 'test_manager'")
        c.execute("DELETE FROM inventory WHERE username = 'test_manager'")
        c.execute("DELETE FROM sales WHERE username = 'test_manager'")
        conn.commit()
        conn.close()

    def test_inventory_flow(self):
        # 1. Access inventory page
        res = self.app.get("/inventory")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Inventory & Stock Management", res.data)

        # 2. Seed starter items
        res = self.app.post("/inventory/seed_starter", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Espresso Coffee Beans", res.data)
        self.assertIn(b"Full Cream Milk", res.data)

        # 3. Add custom inventory item
        res = self.app.post("/inventory/add", data={
            "item_name": "Matcha Powder",
            "category": "Tea & Infusions",
            "current_stock": "5",
            "unit": "kg",
            "min_threshold": "2",
            "unit_cost": "1200"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Matcha Powder", res.data)

        # 4. Restock custom item
        conn = sqlite3.connect("cafe.db")
        c = conn.cursor()
        c.execute("SELECT id FROM inventory WHERE username = 'test_manager' AND item_name = 'Matcha Powder'")
        matcha_id = c.fetchone()[0]
        conn.close()

        res = self.app.post(f"/inventory/restock/{matcha_id}", data={
            "add_quantity": "3",
            "new_unit_cost": ""
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify stock increased: 5 + 3 = 8
        conn = sqlite3.connect("cafe.db")
        c = conn.cursor()
        c.execute("SELECT current_stock FROM inventory WHERE id = ?", (matcha_id,))
        self.assertEqual(c.fetchone()[0], 8.0)
        conn.close()

        # 5. Add recipe mapping
        res = self.app.post("/inventory/recipe/add", data={
            "product_name": "Iced Matcha Latte",
            "inventory_id": str(matcha_id),
            "quantity_required": "0.015"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 6. Delete item
        res = self.app.post(f"/inventory/delete/{matcha_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"Matcha Powder", res.data)

    def test_sale_upload_reduces_inventory_realtime(self):
        # 1. Seed starter items which includes Burger recipe:
        # - Burger Buns (Pack of 4): 25.0 packs (0.25 per burger)
        # - Crispy Veg Patties: 45.0 units (1.0 per burger)
        # - Cheddar Cheese Slices: 60.0 slices (1.0 per burger)
        self.app.post("/inventory/seed_starter", follow_redirects=True)

        # 2. Upload sale of 2 Burgers
        res = self.app.post("/upload", data={
            "id": "",
            "date": "2026-09-16",
            "product_name": "Burger",
            "category": "Snack",
            "quantity": "2",
            "price": "120",
            "payment_method": "UPI"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Real-Time Inventory Deduction", res.data)
        self.assertIn(b"Crispy Veg Patties", res.data)

        # Verify stock decreased in DB:
        # Buns: 25.0 - (2 * 0.25) = 24.5
        # Patties: 45.0 - (2 * 1.0) = 43.0
        # Cheese: 60.0 - (2 * 1.0) = 58.0
        conn = sqlite3.connect("cafe.db")
        c = conn.cursor()
        c.execute("SELECT item_name, current_stock FROM inventory WHERE username = 'test_manager'")
        stock_map = dict(c.fetchall())
        self.assertEqual(stock_map["Burger Buns (Pack of 4)"], 24.5)
        self.assertEqual(stock_map["Crispy Veg Patties"], 43.0)
        self.assertEqual(stock_map["Cheddar Cheese Slices"], 58.0)

        # 3. Update the sale: change quantity to 1 Burger
        c.execute("SELECT id FROM sales WHERE username = 'test_manager' AND product_name = 'Burger'")
        sale_id = c.fetchone()[0]
        conn.close()

        res = self.app.post("/upload", data={
            "id": str(sale_id),
            "date": "2026-09-16",
            "product_name": "Burger",
            "category": "Snack",
            "quantity": "1",
            "price": "120",
            "payment_method": "UPI"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        conn = sqlite3.connect("cafe.db")
        c = conn.cursor()
        c.execute("SELECT item_name, current_stock FROM inventory WHERE username = 'test_manager'")
        stock_map = dict(c.fetchall())
        self.assertEqual(stock_map["Burger Buns (Pack of 4)"], 24.75)
        self.assertEqual(stock_map["Crispy Veg Patties"], 44.0)
        self.assertEqual(stock_map["Cheddar Cheese Slices"], 59.0)

        # 4. Delete the sale: stock should be fully restored to 25.0, 45.0, 60.0
        res = self.app.get(f"/delete/{sale_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        c.execute("SELECT item_name, current_stock FROM inventory WHERE username = 'test_manager'")
        stock_map = dict(c.fetchall())
        self.assertEqual(stock_map["Burger Buns (Pack of 4)"], 25.0)
        self.assertEqual(stock_map["Crispy Veg Patties"], 45.0)
        self.assertEqual(stock_map["Cheddar Cheese Slices"], 60.0)

        # 5. Test CSV upload: upload 1 Burger sale
        csv_content = "date,product_name,category,quantity,price,payment_method\n2026-09-16,Burger,Snack,1,120,Cash\n"
        data = {
            "csv_file": (io.BytesIO(csv_content.encode("utf-8")), "sales.csv")
        }
        res = self.app.post("/upload_csv", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        c.execute("SELECT item_name, current_stock FROM inventory WHERE username = 'test_manager'")
        stock_map = dict(c.fetchall())
        self.assertEqual(stock_map["Burger Buns (Pack of 4)"], 24.75)
        self.assertEqual(stock_map["Crispy Veg Patties"], 44.0)
        self.assertEqual(stock_map["Cheddar Cheese Slices"], 59.0)

        # 6. Test sync_sales when already synced: should not double deduct!
        res = self.app.post("/inventory/sync_sales", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"already synchronized", res.data)

        c.execute("SELECT item_name, current_stock FROM inventory WHERE username = 'test_manager'")
        stock_map = dict(c.fetchall())
        self.assertEqual(stock_map["Burger Buns (Pack of 4)"], 24.75)
        self.assertEqual(stock_map["Crispy Veg Patties"], 44.0)
        self.assertEqual(stock_map["Cheddar Cheese Slices"], 59.0)
        conn.close()

if __name__ == "__main__":
    unittest.main()
