# Lumina CRI

Bank customer data platform. Lumina reads customer data from several bank systems, cleans it, works out which records belong to the same person, builds one **golden record** per customer, and gives each customer a **trust score** from 0 to 1.

Team rules (branches, pull requests, migrations, secrets) are in [CONTRIBUTING.md](CONTRIBUTING.md). Read it before your first change.

## Stack

| Part | Tech | Folder |
|---|---|---|
| Frontend | React + TypeScript, built with Vite | `frontend/` |
| Backend | Django + Django REST Framework | `backend/` |
| Database | PostgreSQL 16 in Docker | `docker-compose.yml` |

## Folder layout

```
LUMINA CRI/
├── backend/
│   ├── config/        Settings and URLs
│   ├── sources/       The bank systems we read from, and how much we trust each one
│   ├── ingestion/     Connectors: read each system, keep the raw copy, save a cleaned copy
│   ├── mdm/           Matching, golden record and trust score
│   ├── stewardship/   Corrections with evidence and second-person approval
│   ├── accounts/      Roles and masking of personal data
│   ├── audit/         Append-only log of who did what
│   └── api/           REST endpoints the React app calls
├── frontend/src/
│   ├── api/           API client and TypeScript types
│   ├── auth/          Sign-in state and role checks
│   ├── components/    Reusable pieces (charts, badges, layout)
│   ├── pages/         One file per screen
│   └── styles/        Design tokens and CSS
├── fake_sources/      Fake Salesforce export and branch CSV files
├── docker/postgres/init/   Creates the fake FLEXCUBE database on first start
├── docs/design/       Design references and Stitch prompts
├── docker-compose.yml
└── .env.example       Template for your own .env
```

## First-time setup

You need Git, Docker Desktop, Python 3.10 or newer, and Node 20 or newer.

**1. Get the code**

```
git clone https://github.com/ibrahim-dev444/Lumina-CRI.git
cd Lumina-CRI
```

**2. Create your `.env`.** Copy `.env.example` to `.env`, then replace `change-me-locally` (both places) with a password of your choice, and `DJANGO_SECRET_KEY` with a random string. To make one:

```
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

`.env` stays on your machine. Never commit it and never paste it into chat.

`FIELD_ENCRYPTION_KEY` encrypts PAN and CKYC numbers. In development you can leave it empty (a key is derived from your secret key). Any shared or production server must set its own:

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If this key is lost, encrypted numbers cannot be read again. Changing it means re-syncing every source.

**3. Start the database.** Open Docker Desktop and wait until it is running, then:

```
docker compose up -d
```

Postgres runs on port **5433**, so it does not clash with a PostgreSQL installed directly on your computer.

**4. Set up the backend.**

Windows (PowerShell):
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

Mac or Linux: the same, but activate with `source .venv/bin/activate`.

**5. Load the fake bank data and build customers.**

```
python manage.py load_fake_flexcube
python manage.py sync flexcube
python manage.py sync salesforce
python manage.py sync branch_csv
python manage.py build_customers
```

**6. Create logins.**

```
python manage.py createsuperuser
python manage.py seed_demo_users
```

`seed_demo_users` creates one login per role (relationship manager, contact centre agent, data steward, compliance officer) and prints their passwords once. Run it again to reset them.

**7. Start the backend.** Keep this terminal open.

```
python manage.py runserver
```

**8. Start the frontend** in a second terminal.

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in.

## Every day

```
docker compose up -d                 # from the project folder, Docker Desktop running
cd backend && .venv\Scripts\activate && python manage.py runserver
cd frontend && npm run dev           # second terminal
```

After a pull that changed the fake data (files in `fake_sources/` or `docker/postgres/init/`), reload and re-sync:

```
python manage.py load_fake_flexcube
python manage.py sync flexcube
python manage.py sync salesforce
python manage.py sync branch_csv
python manage.py build_customers
```

After every `git pull`, also run:

```
cd backend
pip install -r requirements.txt
python manage.py migrate
cd ../frontend
npm install
```

## Useful commands

| Command (inside `backend/`) | What it does |
|---|---|
| `python manage.py load_fake_flexcube` | Re-create the fake FLEXCUBE table from `docker/postgres/init/01-flexcube.sql` |
| `python manage.py sync <source>` | Read one source: `flexcube`, `salesforce` or `branch_csv` |
| `python manage.py build_customers` | Re-run matching, golden records and trust scores |
| `python manage.py seed_demo_users` | Create or reset one demo login per role |
| `pytest` | Run all backend tests |

| Command (inside `frontend/`) | What it does |
|---|---|
| `npm run dev` | Start the app at http://localhost:5173 |
| `npm run build` | Type-check and build; must pass before a pull request |
| `npm run lint` | Check code style |

## Look at the database

Connect pgAdmin or DBeaver to host `localhost`, port `5433`, database `lumina`, user `lumina`, and the password from your `.env`. The fake FLEXCUBE system is the `src_flexcube` database on the same server. Use these tools to look, not to edit: changes made by hand skip score recalculation and the audit log.

## Reset your local data

```
docker compose down -v      # deletes your local database
docker compose up -d
```

Then repeat steps 4 (migrate) to 6. This only affects your own machine.
