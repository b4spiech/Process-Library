# Business Process Repository (BPR)

Phase 1 of **The Kendall Group Business Operating System (BOS)**.

A web application for cataloguing, governing, and reviewing every business process in the company — organised as a 4-level taxonomy (Domain → Function → Process Group → Terminal Process) with governance metadata on every node (owner, review cadence, KPIs, linked SOP, status).

## Stack

| Layer    | Technology                                            |
| -------- | ----------------------------------------------------- |
| Backend  | FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2        |
| Database | PostgreSQL 16 (adjacency list pattern)                |
| Frontend | Single-page vanilla HTML / CSS / JS (no build step)   |
| Runtime  | Railway (Nixpacks builder)                            |

## Data Model

A single `nodes` table stores the entire taxonomy via a self-referencing `parent_id`. Every row carries the same governance metadata regardless of level:

```
L1 — Business Domain        (e.g. OPS — Operations)
└── L2 — Function           (e.g. OPS-WH — Warehousing)
    └── L3 — Process Group  (e.g. OPS-WH-RCV — Receiving)
        └── L4 — Terminal Process (e.g. OPS-WH-RCV-IFV — Inbound Freight Verification)
```

Governance fields on every node:
`owner`, `review_frequency` (monthly | quarterly | annually), `last_review_date`,
`next_review_date` (auto-computed), `status` (active | under_review | deprecated),
`linked_procedure_url`, `kpi_name`, `kpi_target`, `kpi_current`,
`camunda_process_key` (placeholder for future BPMN integration).

## Deployment — Railway

The repo is configured for Railway with Nixpacks. Required pieces are committed:

- [`Procfile`](Procfile) — `web: alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
- [`railway.json`](railway.json) — pins the builder to `NIXPACKS` and sets `/health` as the healthcheck path
- [`requirements.txt`](requirements.txt) — pulled by Nixpacks to install Python deps

To deploy:

1. In Railway, create the service from this repo and set the **Deploy Branch** to `dev` (or whichever you publish).
2. Add a **Postgres** plugin in the same project; Railway will inject `DATABASE_URL` as a service variable — reference it on the API service.
3. Deploy. Migrations run automatically via the `Procfile` `release`-style chain.

The seed script ([`seed.py`](seed.py)) is **not** run automatically on deploy — invoke it once via the Railway shell if you want the sample L1/L2 domains.

## Local development

Requires Python 3.12+ and a running PostgreSQL.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # then edit DATABASE_URL if needed
alembic upgrade head
python seed.py                      # optional — seeds 6 L1 domains
uvicorn main:app --reload           # serves http://localhost:8000
```

The frontend (`index.html`, `styles.css`, `app.js`) is served by the FastAPI app at `/`. To run it from a separate static server, pass an `?api=` query param to point at the API host.

## API

| Method | Path                       | Description                       |
| ------ | -------------------------- | --------------------------------- |
| GET    | `/health`                  | Health check                      |
| GET    | `/nodes`                   | Full tree (nested children)       |
| GET    | `/nodes/{id}`              | Single node detail                |
| POST   | `/nodes`                   | Create node                       |
| PUT    | `/nodes/{id}`              | Update node (partial)             |
| DELETE | `/nodes/{id}`              | Delete node (cascades to children)|
| GET    | `/nodes/level/{level}`     | Filter by level (1–4)             |

Validation enforced by the backend:
- Root nodes must be `level=1` with `parent_id=null`.
- A child's `level` must be exactly `parent.level + 1`.
- `code` is globally unique.
- `next_review_date` is recomputed on every create/update from `last_review_date + review_frequency`.

## Project layout

```
.
├── main.py              FastAPI app + explicit static routes for the 3 frontend files
├── database.py          SQLAlchemy engine / session
├── models.py            Node ORM model + enums
├── schemas.py           Pydantic request/response schemas
├── utils.py             next_review_date computation
├── seed.py              Seed L1/L2 sample data
├── routers/nodes.py     CRUD endpoints
├── alembic/             Migrations
├── alembic.ini
├── requirements.txt
├── .env.example
├── index.html           Tree view + side detail panel
├── styles.css
├── app.js
├── Procfile             Railway start command
├── railway.json         Railway build config (Nixpacks)
└── README.md
```

## Status colour key (UI)

- 🟢 **green** — active
- 🟡 **yellow** — under review
- ⚪ **gray** — deprecated

## Future (out of scope for Phase 1)

- BPMN process execution via Camunda (the `camunda_process_key` column is a placeholder).
- AuthN/AuthZ — currently no auth; intended for internal-network deployment.
- Audit history of metadata changes.
- Bulk import / export (CSV, JSON).
