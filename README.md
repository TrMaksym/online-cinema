# 🎬 Online Cinema API

A scalable RESTful API for online cinema management, built with **FastAPI**.

Supports:

- User registration & JWT authentication  
- Movie catalog browsing with ratings, comments, favorites  
- Shopping cart & order management  
- Secure payment workflow with Stripe  
- Role-based access (User, Moderator, Admin)  
- Asynchronous tasks with Celery & Celery Beat  
- Fully dockerized setup with PostgreSQL, Redis, MinIO  

---

## 🧪 Technology Stack

- Python 3.10+  
- FastAPI  
- PostgreSQL  
- Redis + Celery + Celery Beat  
- Docker & Docker Compose  
- MinIO (media storage)  
- Poetry (dependency management)  
- Stripe (payments)  
- GitHub Actions (CI/CD)  

---

## 🚀 Features

- 🔑 **Authentication**: Email-based registration, activation tokens, JWT (access & refresh), password reset  
- 🎥 **Movies**: Browse, search, filter, like/dislike, rate, comment, add to favorites  
- 🛒 **Shopping Cart**: Add/remove items, validate duplicates, checkout flow  
- 📦 **Orders**: Track status (*pending, paid, canceled*), order history, email confirmation  
- 💳 **Payments**: Stripe integration with refunds, cancellation, webhooks  
- 👥 **Roles**: User, Moderator (CRUD movies), Admin (manage users & groups)  
- 📖 **API Docs**: Swagger/OpenAPI 3.0 with access control  
- 🧪 **Testing**: Unit, integration & functional tests with pytest  

---

## 🧱 Models Overview

| Model       | Description |
|-------------|-------------|
| User        | Custom user with email login, profile, roles |
| UserProfile | Optional info (name, avatar, bio, gender, DOB) |
| Movie       | Title, year, duration, IMDb, description, price, certification |
| Genre       | Movie categories (many-to-many with Movie) |
| Director    | Linked to movies (many-to-many) |
| Star        | Actors linked to movies (many-to-many) |
| Cart        | One cart per user |
| CartItem    | Items in the cart (unique per movie) |
| Order       | Tracks movies purchased, status & total amount |
| OrderItem   | Snapshot of movies in an order with price at purchase |
| Payment     | Stripe transaction with status (successful, refunded, canceled) |
| PaymentItem | Snapshot of paid order items |

---

## ⚙️ Business Logic

- **Permissions**:  
  - Users: catalog, orders, favorites  
  - Moderators: CRUD movies, genres, actors  
  - Admins: user/group management, manual activations  

- **Tokens & Expiration**:  
  - Activation tokens expire after 24h  
  - Refresh tokens for JWT rotation  
  - Celery Beat cleans expired tokens  

- **Validation Rules**:  
  - Unique emails & accounts  
  - Strong password requirements  
  - No duplicate movies in cart  
  - Orders validated before payment (availability, pricing)  

- **Notifications**:  
  - Email confirmations for activation, password reset, orders, and payments  

---

## 🐳 Docker (recommended)

```bash
git clone https://github.com/TrMaksym/online-cinema.git
cd online-cinema
cp .env.sample .env
docker-compose up --build
```
## ⚡ Local Development (without Docker)
```bash
# Clone project
git clone https://github.com/TrMaksym/online-cinema.git
cd online-cinema

# Create virtual environment
python -m venv venv
source venv/bin/activate   # On Windows use: venv\Scripts\activate

# Install dependencies
poetry install

# Configure environment
cp .env.sample .env
# Edit `.env` and fill in secrets

# Apply migrations
alembic upgrade head

# Run development server
uvicorn app.main:app --reload