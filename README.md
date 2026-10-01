# ☕ CafeAnalyst

**CafeAnalyst** is an AI-powered sales analytics, stock inventory, and forecasting platform tailored for cafes, bakeries, and coffee shops. It provides cafe owners and managers with deep operational visibility, demand forecasting, recipe-based stock tracking, and automated reporting.

---

## 🚀 Key Features

- **📊 Sales Dashboard & Visualization**: Real-time sales metrics, category distribution, top-performing items, and sales trends powered by Matplotlib.
- **📦 Inventory & Stock Management**: Real-time inventory tracking, automatic recipe ingredient deductions upon sale, minimum threshold stock alerts, and quick starter item seeding.
- **🤖 AI Insights & Demand Forecasting**: Machine learning models (Linear Regression via Scikit-Learn) to project future revenue and optimize inventory planning.
- **📄 Automated Export & Reporting**: One-click generation of professional sales summaries in PDF (ReportLab) and Excel `.xlsx` (OpenPyXL) formats.
- **📥 Batch Sales Import**: Upload daily or weekly sales transactions via CSV/Excel spreadsheets.
- **🔒 Authentication & Multi-User Isolation**: User registration and login secured with `werkzeug.security` password hashing.

---

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask, Werkzeug
- **Data & Machine Learning**: Pandas, NumPy, Scikit-Learn
- **Visualization**: Matplotlib
- **Document Generation**: ReportLab, OpenPyXL
- **Database**: SQLite3
- **Frontend**: HTML5, Vanilla CSS, Responsive Glassmorphism Design

---

## 📂 Project Structure

```text
CafeAnalyst/
├── app.py                  # Main Flask application and routing logic
├── create_db.py            # SQLite database initialization script
├── requirements.txt        # Python package dependencies
├── cafe.db                 # SQLite database file
├── analysis/               # Analysis scripts and utility modules
├── backend/                # Backend routes and configuration
├── database/               # Database schemas and DDL scripts
├── design/                 # Wireframes and UI design documents
├── docs/                   # Project documentation and specifications
├── reports/                # Report generation utilities
├── static/                 # Static assets (CSS, JS, images, generated charts)
│   ├── css/                # Custom stylesheets (dashboard, inventory, auth, etc.)
│   ├── images/             # Backgrounds and branding images
│   └── charts/             # Output chart visualisations
├── templates/              # Jinja2 HTML templates
├── tests/                  # Unit and integration tests
└── uploads/                # Directory for uploaded sales data files
```

---

## ⚙️ Getting Started

### 1. Prerequisites
- Python 3.10+ installed
- Git installed

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/<your-username>/CafeAnalyst.git
cd CafeAnalyst
pip install -r requirements.txt
```

### 3. Initialize the Database
Set up the SQLite database and create the default admin user:
```bash
python create_db.py
```
> **Default Admin Account:**
> - Username: `admin`
> - Password: `admin123`

### 4. Run the Application
Launch the Flask development server:
```bash
python app.py
```
Access the application in your browser at `http://127.0.0.1:5000`.

---

## 🧪 Running Tests
To run the automated test suite:
```bash
python -m unittest discover tests
```

---

## 📝 License
This project is open-source and available under the [MIT License](LICENSE).
