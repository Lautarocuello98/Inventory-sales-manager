# 📦 Inventory & Sales Manager (ISM)

> Professional desktop inventory and sales management system built with Python, Tkinter, and SQLite.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)  
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)  
[![Tests: pytest](https://img.shields.io/badge/tests-pytest-green.svg)](#quality-checks)

---

# ✨ Overview

Inventory & Sales Manager (ISM) is a **desktop business management system** designed to handle inventory, sales, and restock operations with full financial traceability.

The application demonstrates a **clean layered architecture** with strict separation between domain logic, services, repositories, and the user interface.

The system focuses on:

- Accurate financial calculations
- Traceable inventory movements
- Clean modular architecture
- Maintainability and extensibility
- Automated business logic testing

---

# 🎬 Demo

A quick overview of how the system works.

https://youtu.be/fo5FR72vQPQ

---

# 🖼 Screenshot

![Start](media/screenshot.png)

---

# 🚀 Features

| Feature | Description |
|-------|-------------|
| Product Management | SKU-based product catalog with stock monitoring |
| Sales Workflow | Cart-based sales with automatic stock deduction |
| Restock Management | Purchase tracking with weighted cost recalculation |
| Currency Conversion | USD → ARS conversion using live FX rates |
| Excel Integration | Import products and export professional reports |
| KPI Monitoring | Revenue and profit metrics |
| Role-Based Security | Permission-based operations |
| Backup & Restore | Encrypted database backup system |

---

# 📦 Distribution

This repository is maintained as a **technical portfolio overview**.

Commercial binaries, installers, and support are distributed through private channels.

---

# 🏗 Architecture

The project follows a layered architecture designed for scalability and maintainability.

```
inventory-sales-manager/
│
├── .github/workflows/            # CI/CD pipelines
│   ├── build.yml
│   └── release.yml
│
├── docs/                         # Operational and QA documentation
│   ├── operations/
│   │   ├── COMMERCIAL_TERMS.md
│   │   └── SUPPORT_SLA_AND_INCIDENTS.md
│   │
│   ├── qa/
│   │   └── QA_FINAL_CHECKLIST.md
│   │
│   └── release/
│       └── RELEASE_PROCESS.md
│
├── media/                        # Screenshots and demo assets
│   └── screenshot.png
│
├── release/                      # Update metadata
│   └── latest.json
│
├── scripts/                      # Operational scripts
│   └── check_release.sh
│
├── src/ism/                      # Application source code
│
│   ├── main.py                   # Application entry point
│   ├── config.py                 # Configuration management
│   ├── logging_config.py         # Logging setup
│
│   ├── application/              # Dependency wiring / container
│   │   └── container.py
│
│   ├── domain/                   # Core business models and rules
│   │   ├── models.py
│   │   └── errors.py
│
│   ├── repositories/             # Data access layer
│   │   ├── contracts.py
│   │   ├── sqlite_repo.py
│   │   └── unit_of_work.py
│
│   ├── services/                 # Business logic services
│   │   ├── auth_service.py
│   │   ├── backup_service.py
│   │   ├── excel_service.py
│   │   ├── fx_service.py
│   │   ├── inventory_service.py
│   │   ├── operation_service.py
│   │   ├── purchase_service.py
│   │   ├── reporting_service.py
│   │   ├── sales_service.py
│   │   └── update_service.py
│
│   └── ui/                       # Tkinter presentation layer
│       ├── app.py
│       ├── config.py
│       ├── logging_config.py
│       │
│       └── views/
│           ├── products_view.py
│           ├── sales_view.py
│           ├── restock_view.py
│           └── reports_view.py
│
├── test/                         # Automated tests (pytest)
│   ├── conftest.py
│   ├── test_backup_and_auth_policy.py
│   ├── test_business_invariants.py
│   ├── test_fx_fallback.py
│   ├── test_migrations_and_roles.py
│   ├── test_operations_and_updates.py
│   ├── test_purchase_atomicity.py
│   ├── test_sales_fx_validation.py
│   ├── test_sales_validation.py
│   └── test_security_and_permissions.py
│
├── InventorySalesManager.spec
├── pyproject.toml
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

---

# Architecture Principles

### Domain Layer

Contains business entities and domain rules.

- No UI dependencies
- No database dependencies

---

### Repository Layer

Responsible for data persistence.

- SQLite access
- SQL encapsulation
- Unit of Work pattern for transaction safety

---

### Service Layer

Implements business logic such as:

- Stock validation
- Weighted average cost calculation
- Profit calculation
- FX handling
- Reporting aggregation
- Excel import/export coordination

---

### UI Layer

Tkinter-based presentation layer.

- Contains no business logic
- All operations are executed through services

---

### Dependency Injection

Services are wired in `main.py` and injected into the UI.

The UI never instantiates repositories directly.

---

# 💼 Business Logic

### Weighted Cost Formula

Used to recalculate inventory cost after restocking.

```
new_cost = (old_stock * old_cost + qty * unit_cost) / (old_stock + qty)
```

This guarantees accurate future profit margins.

---

# 📊 Excel Integration

### Import

Required headers:

```
sku | name | cost_usd | price_usd | stock | min_stock
```

Import behavior:

- Existing stock is never overwritten
- If Excel stock > current stock → restock recorded as purchase
- New products are created automatically
- Full audit trail is preserved

---

### Export

Generated Excel reports include:

**Summary Sheet**

- Sales count
- Revenue (USD / ARS)
- Gross profit
- Total restock spending
- Net profit

**Sales Detail Sheet**

- Sale ID
- Product
- Quantity
- Unit price
- Unit cost
- Line revenue
- Line profit
- Margin %

**Purchases Sheet**

- Purchase ID
- Vendor
- Product
- Quantity
- Unit cost
- Line total

---

# 🗄 Database

SQLite database with foreign keys enabled.

Tables include:

- `products`
- `sales`
- `sale_items`
- `purchases`
- `purchase_items`
- `fx_rates`

Transactional integrity is enforced for both **sales and purchases**.

---

# 🔒 Security and Operations

- Role-based permissions (admin / seller / viewer)
- Password hashing using **PBKDF2-SHA256**
- Login protection with lockout after repeated failures
- Encrypted SQLite backup (`AES-256`)
- Admin-only operational actions
- Optional update source override using `ISM_UPDATE_SOURCE`

---

# 🧪 Testing Strategy

The project includes a pytest suite focused on validating business correctness and operational safety.

Tests cover:

- Business invariants and financial calculations
- Sales validation and FX conversion
- Purchase atomicity and transaction safety
- Security rules and role permissions
- Backup and authentication policies
- Update operations and migrations

The UI layer is intentionally excluded from tests to keep validation focused on business logic.

---

# 🧰 Technical Stack

- Python 3.10+
- Tkinter
- SQLite
- requests
- openpyxl
- Structured logging
- pytest

---

# 👨‍💻 Author

**Lautaro Cuello**

Python Developer  

GitHub:  
https://github.com/Lautarocuello98

---

# 📄 License

This project is licensed under the MIT License.

See the **LICENSE** file for details.

---

⭐ If you found this project useful, consider giving this repository a star.
