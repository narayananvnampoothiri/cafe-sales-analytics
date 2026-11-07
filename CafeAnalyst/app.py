from flask import Flask, render_template, request, redirect, url_for, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
print("Matplotlib Backend:", matplotlib.get_backend())
from sklearn.linear_model import LinearRegression
import numpy as np
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, timedelta
import matplotlib.dates as mdates

app = Flask(__name__)

app.secret_key = "CafeAnalystSecretKey2026"

def init_db():
    conn = sqlite3.connect("cafe.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        date TEXT NOT NULL,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        payment_method TEXT NOT NULL,
        inventory_deducted INTEGER DEFAULT 0
    )
    """)
    try:
        cur.execute("ALTER TABLE sales ADD COLUMN inventory_deducted INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    cur.execute("""
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        product_name TEXT NOT NULL,
        inventory_id INTEGER NOT NULL,
        quantity_required REAL NOT NULL,
        FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        connection = sqlite3.connect("cafe.db")
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        )

        user = cursor.fetchone()

        connection.close()

        if user and check_password_hash(user[2], password):

            session["username"] = username

            return redirect(url_for("dashboard"))

        else:

            return render_template(
                "login.html",
                error="Invalid username or password."
            )
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        connection = sqlite3.connect("cafe.db")
        cursor = connection.cursor()

        # Check if username already exists
        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "register.html",
                error="Username already exists."
            )

        # Insert new user
        cursor.execute(
            """
            INSERT INTO users (username, password)
            VALUES (?, ?)
            """,
            (username, hashed_password)
        )

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():

    if "username" not in session:
        return redirect(url_for("home"))

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    # Total Revenue
    cursor.execute("""
        SELECT SUM(quantity * price)
        FROM sales
        WHERE username = ?
    """, (session["username"],))

    total_revenue = cursor.fetchone()[0]

    if total_revenue is None:
        total_revenue = 0

    # Products Sold
    cursor.execute("""
        SELECT SUM(quantity)
        FROM sales
        WHERE username = ?
    """, (session["username"],))

    total_products = cursor.fetchone()[0]

    if total_products is None:
        total_products = 0

    # Total Sales Records
    cursor.execute("""
        SELECT COUNT(*)
        FROM sales
        WHERE username = ?
    """, (session["username"],))

    total_sales = cursor.fetchone()[0]

    # Best Selling Product
    cursor.execute("""
        SELECT product_name,
               SUM(quantity) AS qty
        FROM sales
        WHERE username = ?
        GROUP BY product_name
        ORDER BY qty DESC
        LIMIT 1
    """, (session["username"],))

    best_product = cursor.fetchone()

    if best_product:
        best_product = best_product[0]
    else:
        best_product = "No Data"
    # ==========================
    # Sales Trend - Last 30 Days
    # ==========================

    today_date = datetime.now().date()

    start_date = today_date - timedelta(days=29)

    sales_query = """
        SELECT
            date,
            SUM(quantity * price) AS total_sales
        FROM sales
        WHERE username = ?
            AND date >= ?
            AND date <= ?
        GROUP BY date
        ORDER BY date ASC
    """

    sales_df = pd.read_sql_query(
        sales_query,
        connection,
        params=(
            session["username"],
            start_date.strftime("%Y-%m-%d"),
            today_date.strftime("%Y-%m-%d")
        )
    )

    # Convert database dates to datetime
    sales_df["date"] = pd.to_datetime(sales_df["date"])

    # Create ALL 30 calendar days
    all_dates = pd.date_range(
        start=start_date,
        end=today_date,
        freq="D"
    )

    # Put sales data against all 30 dates
    sales_df = (
        sales_df
        .set_index("date")
        .reindex(all_dates, fill_value=0)
        .rename_axis("date")
        .reset_index()
    )

    # Make sure revenue is numeric
    sales_df["total_sales"] = pd.to_numeric(
        sales_df["total_sales"],
        errors="coerce"
    ).fillna(0)

    print("30-Day Sales Trend:")
    print(sales_df)

    # ==========================
    # Create Sales Trend Chart
    # ==========================

    plt.figure(figsize=(12, 5))

    plt.plot(
        sales_df["date"],
        sales_df["total_sales"],
        marker="o",
        linewidth=2
    )

    plt.title(
        "Sales Trend (Last 30 Days)",
        fontsize=16,
        fontweight="bold"
    )

    plt.xlabel("Date", fontsize=12)

    plt.ylabel("Sales (₹)", fontsize=12)

    # Show date every 2 days
    ax = plt.gca()

    ax.xaxis.set_major_locator(
        mdates.DayLocator(interval=2)
    )

    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%d-%b")
    )

    plt.xticks(rotation=45, ha="right")

    plt.grid(
        True,
        alpha=0.3
    )

    plt.tight_layout()

    plt.savefig(
        "static/charts/sales_trend.png",
        dpi=150,
        bbox_inches="tight"
    )

    plt.close()
        # Sales by Category Chart

    query = """
    SELECT category,
    SUM(quantity)
    FROM sales
    WHERE username = ?
    GROUP BY category
    """

    df = pd.read_sql_query(
    query,
    connection,
    params=(session["username"],)
    )

    if not df.empty:

        plt.figure(figsize=(5,5))

        plt.pie(
        df["SUM(quantity)"],
        labels=df["category"],
        autopct="%1.1f%%",
        startangle=90
        )

        plt.title("Sales by Category")

        plt.savefig("static/charts/category_chart.png")

        plt.close()
    cursor.execute("""
    SELECT *
    FROM sales
    WHERE username = ?
    ORDER BY id DESC
    LIMIT 5
    """, (session["username"],))

    recent_sales = []

    for row in cursor.fetchall():
        row = list(row)

        row.append(float(row[5]) * float(row[6]))

        recent_sales.append(row)
    # Product-wise Revenue Bar Chart
    selected_month = request.args.get("month")

    if not selected_month:
        selected_month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT product_name,
       SUM(quantity * price) AS revenue
    FROM sales
    WHERE username = ?
    AND strftime('%Y-%m', date) = ?
    GROUP BY product_name
    ORDER BY revenue DESC
    """, (session["username"], selected_month))

    product_data = cursor.fetchall()
    print("Selected Month:", selected_month)
    print("Product Data:", product_data)

    print(product_data)

    products = [row[0] for row in product_data]
    revenues = [row[1] for row in product_data]

    if product_data:
        print(products)
        print(revenues)

        plt.figure(figsize=(12,6))
      
        plt.bar(products, revenues)

        plt.title(f"Product-wise Revenue ({selected_month})")

        plt.xlabel("Products")

        plt.ylabel("Revenue (₹)")

        plt.xticks(rotation=45, ha="right")

        plt.tight_layout()

        import os

        chart_path = os.path.join("static", "charts", "product_bar.png")

        if os.path.exists(chart_path):
            os.remove(chart_path)

        plt.savefig(chart_path, dpi=200, bbox_inches="tight")

        plt.close("all")
    connection.close()
    today = datetime.now().strftime("%d %B %Y")

    return render_template(
        "dashboard.html",
        total_revenue=total_revenue,
        total_products=total_products,
        total_sales=total_sales,
        best_product=best_product,
        recent_sales=recent_sales,
        selected_month=selected_month,
          today=today
    )

@app.route("/logout")
def logout():

    session.pop("username", None)

    return redirect(url_for("home"))

def deduct_inventory_for_sale(cursor, username, product_name, quantity):
    """
    Deduct raw ingredients from inventory according to recipes configured for this product.
    Returns a list of dicts with ingredient name, deducted amount, unit, and remaining stock.
    """
    try:
        qty_sold = float(quantity)
    except (ValueError, TypeError):
        return []

    if qty_sold <= 0:
        return []

    cursor.execute("""
        SELECT r.inventory_id, r.quantity_required, i.item_name, i.unit, i.current_stock, i.min_threshold
        FROM recipes r
        JOIN inventory i ON r.inventory_id = i.id
        WHERE r.username = ? AND LOWER(TRIM(r.product_name)) = LOWER(TRIM(?))
    """, (username, product_name))
    recipe_items = cursor.fetchall()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    deductions = []

    for inv_id, qty_req, item_name, unit, curr_stock, min_th in recipe_items:
        deduct_amt = round(qty_sold * qty_req, 3)
        new_stock = max(0.0, round(curr_stock - deduct_amt, 3))
        cursor.execute("""
            UPDATE inventory
            SET current_stock = ?, last_updated = ?
            WHERE id = ? AND username = ?
        """, (new_stock, now_str, inv_id, username))
        deductions.append({
            "item_name": item_name,
            "deducted": deduct_amt,
            "unit": unit,
            "remaining": new_stock,
            "is_low": new_stock <= min_th,
            "is_out": new_stock <= 0
        })

    return deductions

def restore_inventory_for_sale(cursor, username, product_name, quantity):
    """
    Restore raw ingredients to inventory when a sale is deleted or updated.
    """
    try:
        qty_sold = float(quantity)
    except (ValueError, TypeError):
        return

    if qty_sold <= 0:
        return

    cursor.execute("""
        SELECT r.inventory_id, r.quantity_required, i.current_stock
        FROM recipes r
        JOIN inventory i ON r.inventory_id = i.id
        WHERE r.username = ? AND LOWER(TRIM(r.product_name)) = LOWER(TRIM(?))
    """, (username, product_name))
    recipe_items = cursor.fetchall()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    for inv_id, qty_req, curr_stock in recipe_items:
        restore_amt = round(qty_sold * qty_req, 3)
        new_stock = round(curr_stock + restore_amt, 3)
        cursor.execute("""
            UPDATE inventory
            SET current_stock = ?, last_updated = ?
            WHERE id = ? AND username = ?
        """, (new_stock, now_str, inv_id, username))

@app.route("/upload", methods=["GET", "POST"])
def upload():

    # Check if user is logged in
    if "username" not in session:
        return redirect(url_for("home"))

    success = request.args.get("success")

    # If form is submitted
    if request.method == "POST":

        record_id = request.form.get("id", "").strip()
        date = request.form["date"]
        product_name = request.form["product_name"].strip()
        category = request.form["category"]
        quantity = request.form["quantity"]
        price = request.form["price"]
        payment_method = request.form["payment_method"]
        username = session["username"]

        connection = sqlite3.connect("cafe.db")
        cursor = connection.cursor()

        deductions = []
        warnings = []

        # Insert new record
        if record_id == "":

            cursor.execute("""
                INSERT INTO sales
                (username, date, product_name, category, quantity, price, payment_method, inventory_deducted)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                username,
                date,
                product_name,
                category,
                quantity,
                price,
                payment_method
            ))

            deductions = deduct_inventory_for_sale(cursor, username, product_name, quantity)
            for d in deductions:
                if d["is_out"]:
                    warnings.append(f"{d['item_name']} is now OUT OF STOCK (0 {d['unit']})")
                elif d["is_low"]:
                    warnings.append(f"{d['item_name']} is running low ({d['remaining']} {d['unit']} left)")

            msg = f"Sale recorded for {quantity}x {product_name}!"

        # Update existing record
        else:
            # First restore previous sale's inventory if it was deducted
            cursor.execute("SELECT product_name, quantity, inventory_deducted FROM sales WHERE id = ? AND username = ?", (record_id, username))
            old_sale = cursor.fetchone()
            if old_sale and (old_sale[2] == 1 or old_sale[2] is None):
                restore_inventory_for_sale(cursor, username, old_sale[0], old_sale[1])

            cursor.execute("""
                UPDATE sales
                SET date=?,
                    product_name=?,
                    category=?,
                    quantity=?,
                    price=?,
                    payment_method=?,
                    inventory_deducted=1
                WHERE id=? AND username=?
            """, (
                date,
                product_name,
                category,
                quantity,
                price,
                payment_method,
                record_id,
                username
            ))

            deductions = deduct_inventory_for_sale(cursor, username, product_name, quantity)
            for d in deductions:
                if d["is_out"]:
                    warnings.append(f"{d['item_name']} is now OUT OF STOCK (0 {d['unit']})")
                elif d["is_low"]:
                    warnings.append(f"{d['item_name']} is running low ({d['remaining']} {d['unit']} left)")

            msg = f"Sale #{record_id} updated for {quantity}x {product_name}!"

        connection.commit()
        connection.close()

        session["upload_feedback"] = {
            "message": msg,
            "deductions": deductions,
            "warnings": warnings,
            "product_name": product_name,
            "no_recipe": len(deductions) == 0
        }

        return redirect(url_for("upload", success="1"))

    # Show all sales records
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM sales WHERE username = ? ORDER BY id DESC",
        (session["username"],)
    )
    sales = cursor.fetchall()

    connection.close()

    feedback = session.pop("upload_feedback", None)

    return render_template(
        "upload.html",
        success=success,
        sales=sales,
        feedback=feedback
    )

@app.route("/upload_csv", methods=["POST"])
def upload_csv():

    if "username" not in session:
        return redirect(url_for("home"))

    file = request.files.get("csv_file")

    if not file or file.filename == "":
        return redirect(url_for("upload"))

    # Read CSV
    df = pd.read_csv(file)

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    username = session["username"]
    all_deductions = {}
    warnings = []

    for index, row in df.iterrows():

        p_name = str(row["product_name"]).strip()
        qty = row["quantity"]

        cursor.execute("""
            INSERT INTO sales
            (username, date, product_name, category, quantity, price, payment_method, inventory_deducted)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            username,
            row["date"],
            p_name,
            row["category"],
            qty,
            row["price"],
            row["payment_method"]
        ))

        row_deductions = deduct_inventory_for_sale(cursor, username, p_name, qty)
        for d in row_deductions:
            item_key = (d["item_name"], d["unit"])
            all_deductions[item_key] = all_deductions.get(item_key, 0.0) + d["deducted"]
            if d["is_out"]:
                w_msg = f"{d['item_name']} is OUT OF STOCK"
                if w_msg not in warnings:
                    warnings.append(w_msg)
            elif d["is_low"]:
                w_msg = f"{d['item_name']} is running low ({d['remaining']} {d['unit']})"
                if w_msg not in warnings:
                    warnings.append(w_msg)

    connection.commit()
    connection.close()

    deduction_summary = [
        {"item_name": k[0], "unit": k[1], "deducted": round(v, 3)}
        for k, v in all_deductions.items()
    ]

    session["upload_feedback"] = {
        "message": f"CSV uploaded! {len(df)} sales recorded and inventory updated.",
        "deductions": deduction_summary,
        "warnings": warnings,
        "no_recipe": len(deduction_summary) == 0
    }

    return redirect(url_for("upload", success="1"))

@app.route("/ai-insights")
def ai_insights():

    if "username" not in session:
        return redirect(url_for("home"))

    connection = sqlite3.connect("cafe.db")

    query = """
        SELECT date,
        SUM(quantity * price) AS total_sales
        FROM sales
        WHERE username = ?
        GROUP BY date
        ORDER BY date
        """

    df = pd.read_sql_query(
        query,
        connection,
        params=(session["username"],)
    )

    connection.close()
            # Find Best Selling Product
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT product_name, SUM(quantity) AS total_quantity
        FROM sales
        WHERE username = ?
        GROUP BY product_name
        ORDER BY total_quantity DESC
        LIMIT 1
        """, (session["username"],))

    best_product = cursor.fetchone()

    connection.close()
    # Find Total Revenue
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    cursor.execute("""
    SELECT SUM(quantity * price)
    FROM sales
    WHERE username = ?
    """, (session["username"],))

    total_revenue = cursor.fetchone()[0]

    connection.close()

    if total_revenue is None:
        total_revenue = 0
        # Find Most Used Payment Method
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT payment_method, COUNT(*) AS total_transactions
        FROM sales
        WHERE username = ?
        GROUP BY payment_method
        ORDER BY total_transactions DESC
        LIMIT 1
        """, (session["username"],))

    payment_method = cursor.fetchone()
    # AI Recommendation
    if best_product:
        recommendation = (
        f"Focus on promoting {best_product[0]}. "
        f"It is your best-selling product and can help increase revenue."
    )
    else:
        recommendation = "No recommendation available."

    connection.close()
    print(df)
    print("Rows:", len(df))
    # Sales by Category
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT category,
        SUM(quantity * price) AS revenue
        FROM sales
        WHERE username = ?
        GROUP BY category
        ORDER BY revenue DESC
        """, (session["username"],))

    category_sales = cursor.fetchall()

    connection.close()
    print(df)
    print("Rows:", len(df))

    plt.figure(figsize=(8,5))

    plt.plot(
        df["date"],
        df["total_sales"],
        marker="o"
    )

    plt.title("Sales Trend")
    plt.xlabel("Date")
    plt.ylabel("Sales (₹)")
    plt.grid(True)

    plt.xticks(rotation=45)

    plt.tight_layout()

    plt.savefig("static/charts/sales_trend.png")

    plt.close()
    # ===============================
    # Sales Prediction using Linear Regression
    # ===============================

    prediction = None

    # Only train the model if we have at least 2 days of sales data
    if len(df) >= 2:

        # X = Day numbers (0,1,2,3...)
        X = np.arange(len(df)).reshape(-1, 1)

        # Y = Sales values
        y = df["total_sales"].values

        # Create and train model
        model = LinearRegression()
        model.fit(X, y)

        # Predict tomorrow's sales
        tomorrow = np.array([[len(df)]])
        prediction = model.predict(tomorrow)[0]
        # ===============================
        # Sales Trend Analysis
        # ===============================

    trend_message = "Not enough data to analyze sales trend."

    if len(df) >= 2:

            yesterday = df["total_sales"].iloc[-2]
            today = df["total_sales"].iloc[-1]

            if yesterday != 0:

                percentage = ((today - yesterday) / yesterday) * 100

                if percentage > 0:
                    trend_message = f"📈 Sales increased by {percentage:.2f}% compared to yesterday."

                elif percentage < 0:
                    trend_message = f"📉 Sales decreased by {abs(percentage):.2f}% compared to yesterday."

                else:
                    trend_message = "Sales remained the same compared to yesterday."
    print("Reached render_template")
    return render_template(
        "ai_insights.html",
        best_product=best_product,
        total_revenue=total_revenue,
        payment_method=payment_method,
        category_sales=category_sales,
        recommendation=recommendation,
        prediction=prediction,
        trend_message=trend_message
        )

@app.route("/reports")
def reports():

    if "username" not in session:
        return redirect(url_for("home"))

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    # Today's Revenue
    cursor.execute("""
        SELECT SUM(quantity * price)
        FROM sales
        WHERE username = ?
        AND date = DATE('now')
    """, (session["username"],))

    today_revenue = cursor.fetchone()[0]

    if today_revenue is None:
        today_revenue = 0

    # Weekly Revenue
    cursor.execute("""
        SELECT SUM(quantity * price)
        FROM sales
        WHERE username = ?
        AND date >= DATE('now','-6 days')
    """, (session["username"],))

    weekly_revenue = cursor.fetchone()[0]

    if weekly_revenue is None:
        weekly_revenue = 0

    # Monthly Revenue
    cursor.execute("""
        SELECT SUM(quantity * price)
        FROM sales
        WHERE username = ?
        AND strftime('%Y-%m', date) = strftime('%Y-%m','now')
    """, (session["username"],))

    monthly_revenue = cursor.fetchone()[0]

    if monthly_revenue is None:
        monthly_revenue = 0

    # Total Orders
    cursor.execute("""
        SELECT COUNT(*)
        FROM sales
        WHERE username = ?
        """, (session["username"],))

    total_orders = cursor.fetchone()[0]

    cursor.execute("""
        SELECT product_name, SUM(quantity) AS qty
        FROM sales
        WHERE username = ?
        GROUP BY product_name
        ORDER BY qty DESC
        LIMIT 1
        """, (session["username"],))

    result = cursor.fetchone()

    if result:
        best_seller = result[0]
    else:
        best_seller = "No Data"
        # Recent Sales Report

    cursor.execute("""
    SELECT date,
           product_name,
           category,
           quantity,
           price
    FROM sales
    WHERE username = ?
    ORDER BY date DESC
    """, (session["username"],))

    sales_report = cursor.fetchall()    

    connection.close()

    return render_template(
        "reports.html",
        today_revenue=today_revenue,
        weekly_revenue=weekly_revenue,
        monthly_revenue=monthly_revenue,
        total_orders=total_orders,
        best_seller=best_seller,
        sales_report=sales_report
    )
@app.route("/download_excel")
def download_excel():

    if "username" not in session:
        return redirect(url_for("home"))

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT date,
               product_name,
               category,
               quantity,
               price,
               payment_method
        FROM sales
        WHERE username = ?
    """, (session["username"],))

    sales = cursor.fetchall()

    connection.close()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sales Report"

    # Headings
    sheet.append([
        "Date",
        "Product",
        "Category",
        "Quantity",
        "Price",
        "Revenue",
        "Payment Method"
    ])

    # Data
    for sale in sales:
        sheet.append([
            sale[0],
            sale[1],
            sale[2],
            sale[3],
            sale[4],
            sale[3] * sale[4],
            sale[5]
        ])

    workbook.save("Sales_Report.xlsx")

    return send_file(
        "Sales_Report.xlsx",
        as_attachment=True
    )
@app.route("/download_pdf")
def download_pdf():

    if "username" not in session:
        return redirect(url_for("home"))

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    cursor.execute("""
    SELECT date,
           product_name,
           category,
           quantity,
           price,
           payment_method
    FROM sales
    WHERE username = ?
    """, (session["username"],))

    sales = cursor.fetchall()

    connection.close()

    pdf = SimpleDocTemplate("Sales_Report.pdf")

    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("<b>CafeAnalyst Sales Report</b>", styles["Title"]))

    data = [["Date", "Product", "Category", "Qty", "Revenue"]]

    for sale in sales:
        data.append([
            sale[0],
            sale[1],
            sale[2],
            sale[3],
            f"₹{sale[3] * sale[4]}"
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.green),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,1), (-1,-1), colors.beige),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("BOTTOMPADDING", (0,0), (-1,0), 12),
    ]))

    elements.append(table)

    pdf.build(elements)

    return send_file(
        "Sales_Report.pdf",
        as_attachment=True
    )
@app.route("/delete/<int:id>")
def delete(id):
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    # Check if sale exists and whether inventory was deducted
    cursor.execute("SELECT product_name, quantity, inventory_deducted FROM sales WHERE id = ? AND username = ?", (id, username))
    sale = cursor.fetchone()
    if sale and (sale[2] == 1 or sale[2] is None):
        restore_inventory_for_sale(cursor, username, sale[0], sale[1])

    cursor.execute("DELETE FROM sales WHERE id = ? AND username = ?", (id, username))
    connection.commit()
    connection.close()

    if sale:
        session["upload_feedback"] = {
            "message": f"Sale record #{id} for {sale[0]} deleted and ingredients restored to inventory.",
            "deductions": [],
            "warnings": [],
            "no_recipe": False
        }

    return redirect(url_for("upload"))

@app.route("/edit/<int:id>")
def edit(id):

    if "username" not in session:
        return redirect(url_for("home"))

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    # Get selected sale
    cursor.execute(
        "SELECT * FROM sales WHERE id = ? AND username = ?",
    (id, session["username"])
    )
    
    sale = cursor.fetchone()

    # Get all sales of logged-in user
    cursor.execute(
        "SELECT * FROM sales WHERE username = ?",
        (session["username"],)
    )
    sales = cursor.fetchall()

    connection.close()

    return render_template(
        "upload.html",
        sale=sale,
        sales=sales,
        success=None
    )

# ==========================================
# INVENTORY & RECIPE MANAGEMENT ROUTES
# ==========================================

@app.route("/inventory")
def inventory():
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    # Get all inventory items
    cursor.execute("""
        SELECT id, item_name, category, current_stock, unit, min_threshold, unit_cost, last_updated
        FROM inventory
        WHERE username = ?
        ORDER BY category ASC, item_name ASC
    """, (username,))
    raw_inventory = cursor.fetchall()

    inventory_items = []
    total_stock_value = 0.0
    low_stock_count = 0
    out_of_stock_count = 0

    for row in raw_inventory:
        item_id, item_name, category, current_stock, unit, min_threshold, unit_cost, last_updated = row
        item_value = round(current_stock * unit_cost, 2)
        total_stock_value += item_value

        if current_stock <= 0:
            status = "Out of Stock"
            status_class = "danger"
            out_of_stock_count += 1
        elif current_stock <= min_threshold:
            status = "Low Stock"
            status_class = "warning"
            low_stock_count += 1
        else:
            status = "In Stock"
            status_class = "success"

        max_target = max(min_threshold * 2.5, 1.0)
        stock_percent = min(round((current_stock / max_target) * 100), 100) if current_stock > 0 else 0

        inventory_items.append({
            "id": item_id,
            "item_name": item_name,
            "category": category,
            "current_stock": current_stock,
            "unit": unit,
            "min_threshold": min_threshold,
            "unit_cost": unit_cost,
            "total_value": item_value,
            "last_updated": last_updated,
            "status": status,
            "status_class": status_class,
            "stock_percent": stock_percent
        })

    total_items = len(inventory_items)
    categories = sorted(list(set([item["category"] for item in inventory_items])))

    # Fetch distinct product names from sales to suggest in recipe creation
    cursor.execute("""
        SELECT DISTINCT product_name, AVG(price) as avg_price
        FROM sales
        WHERE username = ?
        GROUP BY product_name
        ORDER BY product_name ASC
    """, (username,))
    sales_products = cursor.fetchall()
    product_price_map = {row[0]: round(row[1], 2) for row in sales_products}

    # Fetch all recipes with ingredient details
    cursor.execute("""
        SELECT r.id, r.product_name, r.inventory_id, r.quantity_required,
               i.item_name, i.unit, i.unit_cost, i.current_stock
        FROM recipes r
        JOIN inventory i ON r.inventory_id = i.id
        WHERE r.username = ?
        ORDER BY r.product_name ASC, i.item_name ASC
    """, (username,))
    recipe_rows = cursor.fetchall()

    recipes_by_product = {}
    for r_id, p_name, inv_id, qty_req, i_name, i_unit, i_cost, i_stock in recipe_rows:
        if p_name not in recipes_by_product:
            selling_price = product_price_map.get(p_name, 0.0)
            recipes_by_product[p_name] = {
                "product_name": p_name,
                "selling_price": selling_price,
                "ingredients": [],
                "total_cogs": 0.0,
                "portions_available": float("inf")
            }
        
        ingredient_cost = round(qty_req * i_cost, 2)
        recipes_by_product[p_name]["total_cogs"] += ingredient_cost
        
        portion_for_this = int(i_stock // qty_req) if qty_req > 0 else 0
        if portion_for_this < recipes_by_product[p_name]["portions_available"]:
            recipes_by_product[p_name]["portions_available"] = portion_for_this

        recipes_by_product[p_name]["ingredients"].append({
            "recipe_id": r_id,
            "inventory_id": inv_id,
            "item_name": i_name,
            "quantity_required": qty_req,
            "unit": i_unit,
            "unit_cost": i_cost,
            "current_stock": i_stock,
            "ingredient_cost": ingredient_cost,
            "portion_capacity": portion_for_this
        })

    recipe_cards = []
    for p_name, data in recipes_by_product.items():
        data["total_cogs"] = round(data["total_cogs"], 2)
        if data["portions_available"] == float("inf"):
            data["portions_available"] = 0
            
        profit = round(data["selling_price"] - data["total_cogs"], 2)
        margin_pct = round((profit / data["selling_price"]) * 100, 1) if data["selling_price"] > 0 else 0.0
        
        if margin_pct >= 60:
            margin_badge = "success"
            margin_status = "High Margin"
        elif margin_pct >= 35:
            margin_badge = "warning"
            margin_status = "Moderate"
        else:
            margin_badge = "danger"
            margin_status = "Low Margin"

        data["profit"] = profit
        data["margin_pct"] = margin_pct
        data["margin_badge"] = margin_badge
        data["margin_status"] = margin_status
        recipe_cards.append(data)

    connection.close()

    message = request.args.get("msg")
    active_tab = request.args.get("tab", "stock")

    return render_template(
        "inventory.html",
        inventory_items=inventory_items,
        total_items=total_items,
        total_stock_value=round(total_stock_value, 2),
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        categories=categories,
        sales_products=sales_products,
        recipe_cards=recipe_cards,
        message=message,
        active_tab=active_tab
    )

@app.route("/inventory/add", methods=["POST"])
def inventory_add():
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    item_name = request.form.get("item_name", "").strip()
    category = request.form.get("category", "General").strip()
    try:
        current_stock = float(request.form.get("current_stock", 0) or 0)
    except ValueError:
        current_stock = 0.0
    unit = request.form.get("unit", "units").strip()
    try:
        min_threshold = float(request.form.get("min_threshold", 5) or 5)
    except ValueError:
        min_threshold = 5.0
    try:
        unit_cost = float(request.form.get("unit_cost", 0) or 0)
    except ValueError:
        unit_cost = 0.0
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    if item_name:
        connection = sqlite3.connect("cafe.db")
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO inventory (username, item_name, category, current_stock, unit, min_threshold, unit_cost, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, item_name, category, current_stock, unit, min_threshold, unit_cost, last_updated))
        connection.commit()
        connection.close()

    return redirect(url_for("inventory", msg=f"Added {item_name} successfully"))

@app.route("/inventory/edit/<int:id>", methods=["POST"])
def inventory_edit(id):
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    item_name = request.form.get("item_name", "").strip()
    category = request.form.get("category", "").strip()
    try:
        current_stock = float(request.form.get("current_stock", 0) or 0)
    except ValueError:
        current_stock = 0.0
    unit = request.form.get("unit", "").strip()
    try:
        min_threshold = float(request.form.get("min_threshold", 5) or 5)
    except ValueError:
        min_threshold = 5.0
    try:
        unit_cost = float(request.form.get("unit_cost", 0) or 0)
    except ValueError:
        unit_cost = 0.0
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()
    cursor.execute("""
        UPDATE inventory
        SET item_name=?, category=?, current_stock=?, unit=?, min_threshold=?, unit_cost=?, last_updated=?
        WHERE id=? AND username=?
    """, (item_name, category, current_stock, unit, min_threshold, unit_cost, last_updated, id, username))
    connection.commit()
    connection.close()

    return redirect(url_for("inventory", msg="Item updated successfully"))

@app.route("/inventory/restock/<int:id>", methods=["POST"])
def inventory_restock(id):
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    try:
        add_qty = float(request.form.get("add_quantity", 0) or 0)
    except ValueError:
        add_qty = 0.0
        
    new_cost_str = request.form.get("new_unit_cost", "").strip()
    new_cost = -1.0
    if new_cost_str:
        try:
            new_cost = float(new_cost_str)
        except ValueError:
            new_cost = -1.0

    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    if add_qty > 0:
        connection = sqlite3.connect("cafe.db")
        cursor = connection.cursor()
        if new_cost >= 0:
            cursor.execute("""
                UPDATE inventory
                SET current_stock = current_stock + ?, unit_cost = ?, last_updated = ?
                WHERE id = ? AND username = ?
            """, (add_qty, new_cost, last_updated, id, username))
        else:
            cursor.execute("""
                UPDATE inventory
                SET current_stock = current_stock + ?, last_updated = ?
                WHERE id = ? AND username = ?
            """, (add_qty, last_updated, id, username))
        connection.commit()
        connection.close()

    return redirect(url_for("inventory", msg="Restock completed"))

@app.route("/inventory/delete/<int:id>", methods=["POST"])
def inventory_delete(id):
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()
    cursor.execute("DELETE FROM recipes WHERE inventory_id = ? AND username = ?", (id, username))
    cursor.execute("DELETE FROM inventory WHERE id = ? AND username = ?", (id, username))
    connection.commit()
    connection.close()

    return redirect(url_for("inventory", msg="Inventory item deleted"))

@app.route("/inventory/recipe/add", methods=["POST"])
def recipe_add():
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    product_name = request.form.get("product_name", "").strip()
    try:
        inventory_id = int(request.form.get("inventory_id", 0))
    except ValueError:
        inventory_id = 0
    try:
        qty_req = float(request.form.get("quantity_required", 0) or 0)
    except ValueError:
        qty_req = 0.0

    if product_name and inventory_id and qty_req > 0:
        connection = sqlite3.connect("cafe.db")
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id FROM recipes
            WHERE username = ? AND product_name = ? AND inventory_id = ?
        """, (username, product_name, inventory_id))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE recipes SET quantity_required = ? WHERE id = ?
            """, (qty_req, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO recipes (username, product_name, inventory_id, quantity_required)
                VALUES (?, ?, ?, ?)
            """, (username, product_name, inventory_id, qty_req))
            
        connection.commit()
        connection.close()

    return redirect(url_for("inventory", tab="recipes", msg=f"Recipe updated for {product_name}"))

@app.route("/inventory/recipe/delete/<int:id>", methods=["POST"])
def recipe_delete(id):
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()
    cursor.execute("DELETE FROM recipes WHERE id = ? AND username = ?", (id, username))
    connection.commit()
    connection.close()

    return redirect(url_for("inventory", tab="recipes", msg="Recipe ingredient removed"))

@app.route("/inventory/seed_starter", methods=["POST"])
def inventory_seed_starter():
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    starter_items = [
        ("Espresso Coffee Beans", "Coffee Beans", 15.0, "kg", 4.0, 650.0),
        ("Full Cream Milk", "Dairy & Milks", 40.0, "liters", 10.0, 60.0),
        ("Oat Milk", "Dairy & Milks", 12.0, "liters", 4.0, 180.0),
        ("Vanilla Syrup", "Syrups & Flavors", 5.0, "bottles", 2.0, 320.0),
        ("Caramel Syrup", "Syrups & Flavors", 4.0, "bottles", 2.0, 340.0),
        ("Refined Sugar", "Pantry", 20.0, "kg", 5.0, 45.0),
        ("Takeaway Paper Cups 250ml", "Packaging", 300.0, "units", 50.0, 6.0),
        ("Takeaway Cup Lids", "Packaging", 300.0, "units", 50.0, 2.5),
        ("Burger Buns (Pack of 4)", "Bakery", 25.0, "packs", 8.0, 40.0),
        ("Crispy Veg Patties", "Pantry", 45.0, "units", 10.0, 35.0),
        ("Cheddar Cheese Slices", "Dairy & Milks", 60.0, "slices", 15.0, 12.0),
        ("Croissant Dough", "Bakery", 25.0, "units", 6.0, 45.0),
        ("Chocolate Sauce", "Syrups & Flavors", 6.0, "bottles", 2.0, 220.0),
        ("French Fries (Frozen)", "Pantry", 20.0, "kg", 5.0, 95.0),
        ("Tea Leaves (Assam CTC)", "Tea & Infusions", 8.0, "kg", 2.0, 280.0),
    ]

    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    item_id_map = {}
    for name, cat, stock, unit, min_th, cost in starter_items:
        cursor.execute("""
            SELECT id FROM inventory WHERE username = ? AND item_name = ?
        """, (username, name))
        row = cursor.fetchone()
        if row:
            item_id_map[name] = row[0]
        else:
            cursor.execute("""
                INSERT INTO inventory (username, item_name, category, current_stock, unit, min_threshold, unit_cost, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, name, cat, stock, unit, min_th, cost, now_str))
            item_id_map[name] = cursor.lastrowid

    # Seed starter recipes matching common sales products
    starter_recipes = [
        ("Coffee", [("Espresso Coffee Beans", 0.018), ("Full Cream Milk", 0.15), ("Takeaway Paper Cups 250ml", 1.0), ("Takeaway Cup Lids", 1.0)]),
        ("Latte", [("Espresso Coffee Beans", 0.020), ("Full Cream Milk", 0.22), ("Takeaway Paper Cups 250ml", 1.0), ("Takeaway Cup Lids", 1.0)]),
        ("Tea", [("Tea Leaves (Assam CTC)", 0.010), ("Full Cream Milk", 0.12), ("Refined Sugar", 0.015), ("Takeaway Paper Cups 250ml", 1.0)]),
        ("Burger", [("Burger Buns (Pack of 4)", 0.25), ("Crispy Veg Patties", 1.0), ("Cheddar Cheese Slices", 1.0)]),
        ("Fries", [("French Fries (Frozen)", 0.20)]),
    ]

    for prod, ingredients in starter_recipes:
        for ing_name, qty in ingredients:
            if ing_name in item_id_map:
                inv_id = item_id_map[ing_name]
                cursor.execute("""
                    SELECT id FROM recipes WHERE username = ? AND product_name = ? AND inventory_id = ?
                """, (username, prod, inv_id))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO recipes (username, product_name, inventory_id, quantity_required)
                        VALUES (?, ?, ?, ?)
                    """, (username, prod, inv_id, qty))

    connection.commit()
    connection.close()

    return redirect(url_for("inventory", msg="Starter cafe inventory & recipes loaded successfully!"))

@app.route("/inventory/sync_sales", methods=["POST"])
def inventory_sync_sales():
    if "username" not in session:
        return redirect(url_for("home"))

    username = session["username"]
    connection = sqlite3.connect("cafe.db")
    cursor = connection.cursor()

    # Find unsynced sales (inventory_deducted is 0 or NULL)
    cursor.execute("""
        SELECT product_name, SUM(quantity)
        FROM sales
        WHERE username = ? AND (inventory_deducted IS NULL OR inventory_deducted = 0)
        GROUP BY product_name
    """, (username,))
    sales_summary = cursor.fetchall()

    if not sales_summary:
        connection.close()
        return redirect(url_for("inventory", msg="All sales are already synchronized in real time with inventory!"))

    deductions = {}
    for product_name, total_qty in sales_summary:
        cursor.execute("""
            SELECT inventory_id, quantity_required
            FROM recipes
            WHERE username = ? AND LOWER(TRIM(product_name)) = LOWER(TRIM(?))
        """, (username, product_name))
        recipe_items = cursor.fetchall()
        for inv_id, qty_req in recipe_items:
            deductions[inv_id] = deductions.get(inv_id, 0.0) + (total_qty * qty_req)

    updated_count = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    for inv_id, used_qty in deductions.items():
        cursor.execute("""
            UPDATE inventory
            SET current_stock = MAX(0.0, ROUND(current_stock - ?, 3)), last_updated = ?
            WHERE id = ? AND username = ?
        """, (used_qty, now_str, inv_id, username))
        updated_count += 1

    # Mark unsynced sales as synced
    cursor.execute("""
        UPDATE sales
        SET inventory_deducted = 1
        WHERE username = ? AND (inventory_deducted IS NULL OR inventory_deducted = 0)
    """, (username,))

    connection.commit()
    connection.close()

    return redirect(url_for("inventory", msg=f"Stock synchronized based on recorded sales across {updated_count} ingredients!"))

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
    