# gambitho-tcg-trainer

Repositorio para construir un motor neuro-simbolico de entrenamiento en TCGs, comenzando por Disney Lorcana.

## Objetivo inicial

- Ingesta de cartas a PostgreSQL, Neo4j y Qdrant.
- Linter determinista de mazos.
- Motor de reglas FSM con soporte inicial de The Bag.
- Simulacion base bot vs bot para preparar ISMCTS.

## Primer scaffold (en progreso)

Este repo ya incluye:
- `docker-compose.yml` con PostgreSQL, Neo4j y Qdrant.
- backend Python con FastAPI y modulos iniciales para:
  - validacion de mazos Lorcana con codigos de issue estructurados,
  - reparacion determinista de mazos (`POST /decks/repair`),
  - motor FSM base con acciones y `The Bag`,
  - simulacion simplificada bot vs bot,
  - estrategia de simulacion `heuristic` o `ismcts` (base),
  - interfaz de determinizacion con sampler de creencias guiado por señales observadas,
  - reporte estructurado de decision ISMCTS (`POST /simulate/decision`),
  - ingesta Lorcana (`POST /ingest/lorcana`) con escritura SQL y grafo/vectorial (Neo4j y Qdrant activos si hay variables de entorno),
  - ingesta desde URL (`POST /ingest/lorcana/source`).

## Comandos rapidos

Infra local:

```bash
docker compose up -d
```

Backend (desde `backend`):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn src.api.main:app --reload
```

## Variables de entorno (ingesta opcional)

Si no defines estas variables, la ingesta sigue escribiendo en **PostgreSQL** y los contadores de grafo/vectorial mantienen el comportamiento de compatibilidad (sin conexion externa).

| Variable | Proposito |
|----------|------------|
| `POSTGRES_DSN` | Cadena PostgreSQL (por defecto `postgresql://tcg:tcg@localhost:5432/tcg`) |
| `NEO4J_URI` | Ej. `bolt://localhost:7687` — si esta vacio, no se escribe en Neo4j |
| `NEO4J_USER` | Usuario Neo4j (por defecto `neo4j`) |
| `NEO4J_PASSWORD` | Contrasena (en `docker-compose`: `tcgpassword`) |
| `NEO4J_DATABASE` | Base logica (por defecto `neo4j`) |
| `QDRANT_URL` | Ej. `http://localhost:6333` — si esta vacio, no se indexa en Qdrant |
| `QDRANT_COLLECTION` | Nombre de coleccion (por defecto `lorcana_cards`) |
