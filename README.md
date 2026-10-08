# Lumina CRI

Bank customer data platform. Lumina reads customer data from many bank systems, cleans it, matches records that belong to the same person, builds one **golden record** per customer, and gives each customer a **trust score**.

The two HTML files in this folder are clickable prototypes of the UI:
- `Lumina Trust Console.html`: connectors, golden record, trust score
- `Lumina Bank CRM.html`: role-based CRM screens

## Stack

| Part | Tech |
|---|---|
| Frontend | React + TypeScript (Vite), in `frontend/` |
| Backend | Django + Django REST Framework, in `backend/` |
| Database | PostgreSQL 16, running in Docker |

## Folder layout

```
LUMINA CRI/
├── backend/                 Django project
│   ├── config/              settings, urls
│   └── sources/             Source model (each bank system + its trust level)
├── frontend/                React + TypeScript app
├── docker/postgres/init/    SQL that creates and fills the fake source systems
├── docker-compose.yml       Local Postgres
└── .env.example             Template for your local .env
```

## First-time setup

You need: Docker Desktop, Python 3.10+, Node 20+, Git.

1. **Create your `.env`.** Copy `.env.example` to `.env`. Put your own password and secret key in it. `.env` is never committed.
2. **Start Postgres.** Start Docker Desktop, then run:
   ```
   docker compose up -d
   ```
   On first start, this creates two databases: `lumina` (ours) and `src_flexcube` (fake FLEXCUBE with 10 messy customers).
3. **Set up the backend:**
   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate          (Windows)   |   source .venv/bin/activate   (Mac/Linux)
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```
   Open http://localhost:8000/admin and check that 3 sources are listed.
4. **Set up the frontend** in a second terminal:
   ```
   cd frontend
   npm install
   npm run dev
   ```
   Open http://localhost:5173.

## How the team shares the database

Every developer runs **their own** Postgres in Docker. Nobody connects to anyone else's laptop.

What is shared through git:
- **Table structure:** Django migrations in `backend/*/migrations/`. After `git pull`, run `python manage.py migrate`.
- **Starting data:** seed migrations and the SQL in `docker/postgres/init/`.
- **Settings template:** `.env.example`. Real values stay in each person's own `.env`.

Rules:
- Changed a model? Run `python manage.py makemigrations` and commit the new migration file with your code.
- Never edit a migration that is already on `main`. Add a new one instead.
- Two people created migrations at the same time? Run `python manage.py makemigrations --merge`.
- Need fresh data? Run `docker compose down -v` (this **deletes** your local DB), then `docker compose up -d` and `python manage.py migrate`.

A shared **dev server** database for testing everything together comes later.

## Run tests

```
cd backend
pytest
```
