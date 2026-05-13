# Business Process Repository (BPR)

Phase 1 of **The Kendall Group Business Operating System (BOS)**.

A web application for cataloguing, governing, and reviewing every business process in the company — organised as a 4-level taxonomy (Domain → Function → Process Group → Terminal Process) with governance metadata on every node (owner, review cadence, KPIs, linked SOP, status).

## Stack

| Layer    | Technology                                            |
| -------- | ----------------------------------------------------- |
| Backend  | FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2        |
| Database | PostgreSQL 16 (adjacency list pattern)                |
| Frontend | Single-page vanilla HTML / CSS / JS (no build step)   |
| Runtime  | Docker Compose                                        |

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

## Quick start — Docker

```bash
cd bpr
docker compose up --build
```

Then open:

- **UI**:           <http://localhost:8000/>
- **OpenAPI docs**: <http://localhost:8000/docs>
- **Health**:       <http://localhost:8000/health>

On first boot the container runs `alembic upgrade head` and `python seed.py`, populating the DB with the 6 default L1 domains (Operations, Finance, HR, IT, Sales, Customer Service) and their L2 functions.

To wipe state:

```bash
docker compose down -v
```

## Local development (without Docker)

Requires Python 3.12+ and a running PostgreSQL.

```bash
cd bpr/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # then edit DATABASE_URL if needed
alembic upgrade head
python seed.py                      # optional — seeds 6 L1 domains
uvicorn main:app --reload
```

The frontend is served by the FastAPI app at `/` from `../frontend/`. To run it standalone (e.g. from a static server), pass an `?api=` query param to point at the API host.

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
bpr/
├── backend/
│   ├── main.py              FastAPI app + static frontend mount
│   ├── database.py          SQLAlchemy engine / session
│   ├── models.py            Node ORM model + enums
│   ├── schemas.py           Pydantic request/response schemas
│   ├── utils.py             next_review_date computation
│   ├── seed.py              Seed L1/L2 sample data
│   ├── routers/nodes.py     CRUD endpoints
│   ├── alembic/             Migrations
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html           Tree view + side detail panel
│   ├── styles.css
│   └── app.js
├── docker-compose.yml
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
