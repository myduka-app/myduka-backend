# MyDuka Backend

A robust RESTful API for the MyDuka inventory management system, built with Flask, SQLAlchemy, Flask-JWT-Extended, and Flask-Mail. Integrated with a React frontend, it supports user management, store operations, inventory tracking, transactions, supply requests, and reporting for merchants, admins, and clerks.

## 🚀 Features

- **User Management**: Registration and authentication for Merchants (superusers), Admins, and Clerks with JWT-based access and refresh tokens.
- **Store Management**: Create, update, and delete store locations (Merchants only).
- **Product Management**: Manage products with pricing and descriptions (Merchants and Admins).
- **Inventory Tracking**: Record and update inventory levels, including stock and spoilt items (Clerks, Admins, Merchants).
- **Transactions**: Record sales transactions and update inventory stock (Clerks).
- **Supply Requests**: Clerks can request product supplies, Admins can approve/decline, and Merchants can delete.
- **Reports**: Generate sales, stock, spoilt items, and payment status reports (Merchants and Admins).
- **Admin Invitations**: Merchants can invite Admins via email with tokenized registration links.
- **Secure Authentication**: Password hashing with bcrypt, token blacklisting for logout, and role-based access control.
- **CORS Support**: Configured for frontend integration (e.g., `http://localhost:5173`).
- **Rate Limiting**: Configured with Flask-Limiter to prevent abuse.
- **Error Handling**: Comprehensive handling for 400, 401, 403, 404, and 500 errors.

## 🛠 Technologies Used

- **Python 3.8+**
- **Flask 2.x**
- **Flask-SQLAlchemy** (ORM for database management)
- **Flask-Migrate** (Database migrations)
- **Flask-JWT-Extended** (JWT authentication)
- **Flask-Bcrypt** (Password hashing)
- **Flask-Mail** (Email invitations)
- **Flask-CORS** (Cross-Origin Resource Sharing)
- **Flask-Limiter** (Rate limiting)
- **PostgreSQL** (Development database, configurable for production)
- **Postman** (API testing)

## 📁 Project Structure
myduka-backend/
├── app/
│   ├── models/
│   │   ├── auth/
│   │   │   ├── invitations.py
│   │   │   ├── login.py
│   │   │   ├── permissions.py
│   │   ├── admin.py
│   │   ├── clerk.py
│   │   ├── inventory.py
│   │   ├── merchant.py
│   │   ├── products.py
│   │   ├── reports.py
│   │   ├── store.py
│   │   ├── supply_request.py
│   │   ├── transactions.py
│   │   ├── user_models.py
│   ├── database/
│   │   ├── connection.py
│   ├── init.py
│   ├── config.py
├── migrations/
├── main.py
├── .env
├── requirements.txt
├── README.md
text## ⚙️ Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/myduka-backend.git
   cd myduka-backend