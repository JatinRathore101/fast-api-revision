# User Management Service

A production-ready FastAPI microservice for user management backed by PostgreSQL.

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application entry point
│   ├── config.py        # Environment-based configuration
│   ├── database.py      # SQLAlchemy engine, session factory, Base, get_db dependency
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py      # SQLAlchemy ORM model for user_table
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── user.py      # Pydantic request/response schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   └── user.py      # Route handlers for /users/*
│   └── utils/
│       ├── __init__.py
│       └── security.py  # Password hashing helpers (bcrypt)
├── setup.py             # One-time DB table creation script
├── requirements.txt
├── .env                 # Environment variables (not committed)
└── README.md
```

## Prerequisites

- Python 3.10+
- PostgreSQL running on `localhost:5432` (Docker container named `postgres`)

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Edit `.env` to match your PostgreSQL credentials:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=postgres
SERVER_PORT=52243
```

### 4. Create the database table

```bash
python setup.py
```

### 5. Start the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 52243 --reload
```

The API will be available at `http://localhost:52243`.
Interactive docs: `http://localhost:52243/docs`

---

## API Reference

### POST `/users/create-user`

Create a new user.

**Request body:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "username": "janedoe",
  "password": "secret123"
}
```

**Success response (201):**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "username": "janedoe",
  "message": "User created successfully"
}
```

| Status | Meaning |
|--------|---------|
| 201    | User created |
| 400    | Validation error |
| 409    | Username or email already exists |

---

### GET `/users/get-user/{username}`

Fetch a user by username.

**Success response (200):**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "username": "janedoe",
  "message": "User fetched successfully"
}
```

| Status | Meaning |
|--------|---------|
| 200    | User found |
| 404    | User not found |

---

## curl Examples

### Create a user

```bash
curl -s -X POST http://localhost:52243/users/create-user \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "email": "jane@example.com",
    "username": "janedoe",
    "password": "secret123"
  }' | python3 -m json.tool
```

### Get a user

```bash
curl -s http://localhost:52243/users/get-user/janedoe | python3 -m json.tool
```

### Health check

```bash
curl -s http://localhost:52243/health
```
