# gambitho-tcg-trainer

Repositorio para construir un motor neuro-simbolico de entrenamiento en TCGs, comenzando por Disney Lorcana.

## Objetivo inicial

- Ingesta de cartas a PostgreSQL, Neo4j y Qdrant.
- Linter determinista de mazos.
- Motor de reglas FSM con soporte inicial de The Bag.
- Simulacion base bot vs bot para preparar ISMCTS.
- Catálogo visual con arte oficial de carta física (Ravensburger / LorcanaJSON).

## Que incluye el repo

- `docker-compose.yml` con PostgreSQL, Neo4j y Qdrant (desarrollo local opcional).
- **Backend** Python + FastAPI (`backend/`):
  - validacion y reparacion de mazos Lorcana (`POST /decks/validate`, `POST /decks/repair`),
  - motor FSM con acciones, `The Bag` y reglas P0 (challenge con defensor explicito, song),
  - simulacion bot vs bot (`heuristic` / `ismcts`),
  - determinizacion y explicacion de decision (`POST /simulate/decision`),
  - ingesta Lorcana (payload, Lorcast, LorcanaJSON, URL y **híbrida**),
  - **catálogo** con busqueda y URLs de imagen oficial (`GET /catalog/cards`).
- **Frontend** Next.js (`frontend/`):
  - panel de simulacion, presets, decks e ingesta,
  - **catálogo de cartas** con proporcion 5:7 y imagenes Ravensburger.

## Simulacion: strict mode

Documentacion de strict mode (payloads, `422`, `error_code`, `contract_version: "1"`):

- `docs/api/simulation-strict-mode.md`

## Motor: prioridad de fidelidad de reglas

- `docs/engine/rule-fidelity-criteria.md` — criterios P0/P1/P2 y mapeo a tests del FSM.

## Estado actual (checkpoint)

- Catálogo real en PostgreSQL (~2960 cartas EN) con stats, `rules_text`, subtypes e **imagenes oficiales**.
- Ingesta híbrida, API `/catalog/*`, frontend con catálogo visual.
- Simulacion **MVP con intents abstractos** (`tempo`, `aggressive`, …): util para infra y ISMCTS experimental, **no** sustituye partidas con cartas reales del catálogo.
- Suite backend: **94 passed**.

**Prioridad del proyecto:** Fase A en `ROADMAP.md` — motor FSM con decks de 60 `card_uuid` (ISSUE-008). Hasta entonces, deck builder "competitivo" y meta son roadmap, no capacidad actual.

Plan completo (visión élite, gaps, estimaciones): `ROADMAP.md`

## Arranque rapido (local)

### 1. Base de datos

**Opcion A — Railway (recomendado si ya tienes Postgres ahi)**

1. Crea o usa un servicio PostgreSQL en Railway.
2. Copia `DATABASE_PUBLIC_URL` (desde tu PC) o `DATABASE_URL` (desde otro servicio en el mismo proyecto).
3. En `backend/`, copia `.env.railway.example` → `.env` y pega la URL en `POSTGRES_DSN`.

**Opcion B — Docker local**

```bash
docker compose up -d
```

Usa por defecto `postgresql://tcg:tcg@localhost:5432/tcg` o define `POSTGRES_DSN` en `backend/.env`.

### 2. Backend

Desde `backend/`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn src.api.main:app --reload --port 8000
```

El servidor carga `backend/.env` al arrancar (`POSTGRES_DSN`, timeouts, etc.).

### 3. Cargar cartas (primera vez)

Todas las cartas EN (~2966) desde LorcanaJSON:

```bash
python -m src.infra.ingestion.hybrid_bootstrap --language en --include-lorcanajson
```

Si el catálogo ya existe pero **sin imagenes**, solo actualiza URLs:

```bash
python -m src.infra.ingestion.image_backfill --language en
```

Híbrido con Lorcast (mas lento, respeta rate limits):

```bash
python -m src.infra.ingestion.hybrid_bootstrap --language en --include-lorcanajson --include-lorcast --lorcast-queries "set:1,set:2"
```

Endpoint canónico equivalente: `POST /ingest/lorcana/hybrid`

### 4. Frontend

Desde `frontend/`:

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

| Servicio | URL |
|----------|-----|
| UI | http://localhost:3000 |
| API + Swagger | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/health |
| Catálogo (ejemplo) | http://127.0.0.1:8000/catalog/cards?search=ariel&limit=12 |

## Benchmark offline

```bash
cd backend
python -m src.domain.simulation.benchmark --seeds 7,11,19 --matches-per-seed 20 --max-turns 12 --target-lore 8 --ismcts-iterations 64
```

Modo espejo y rollout policy:

```bash
python -m src.domain.simulation.benchmark --seeds 7,11,19 --matches-per-seed 15 --max-turns 12 --target-lore 8 --ismcts-iterations 64 --rollout-policy random --mirror-start-player
```

Reportes en `docs/benchmarks/`.

## Variables de entorno

| Variable | Proposito |
|----------|------------|
| `POSTGRES_DSN` | PostgreSQL (local o Railway). En Railway desde PC usa `DATABASE_PUBLIC_URL`. |
| `POSTGRES_CONNECT_TIMEOUT` | Timeout de conexion en segundos (ej. `30` para Railway). |
| `CATALOG_FALLBACK_MODE` | `degraded` (default) o `strict` en simulacion/decks |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | Grafo de sinergias (opcional) |
| `QDRANT_URL`, `QDRANT_COLLECTION` | Vectores de texto de cartas (opcional) |
| `NEXT_PUBLIC_API_BASE_URL` | URL del backend para el frontend (default `http://127.0.0.1:8000`) |

Sin Neo4j/Qdrant la ingesta **sigue guardando el catálogo en SQL**; grafo y vector son opcionales.

## API de catálogo

```http
GET /catalog/cards?search=ariel&limit=24&offset=0
GET /catalog/cards/{card_id}
```

Las imagenes provienen de `images.full` / `images.thumbnail` en LorcanaJSON (CDN oficial Ravensburger). El frontend las muestra con proporcion de carta física (5:7).
