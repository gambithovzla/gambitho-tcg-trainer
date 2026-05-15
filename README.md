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
  - ingesta desde Lorcast (`POST /ingest/lorcana/lorcast`, usa https://api.lorcast.com/v0/cards/search),
  - ingesta desde URL (`POST /ingest/lorcana/source`).

## Simulacion: strict mode

La documentacion completa de strict mode (payloads, respuestas `200`/`422`, `error_code`, `strict_validation` y **version del contrato v1** de errores) esta en:

- `docs/api/simulation-strict-mode.md`

## Motor: prioridad de fidelidad de reglas

- `docs/engine/rule-fidelity-criteria.md` — criterios (impacto, frecuencia, sesgo), clasificacion P0/P1/P2 y mapeo a tests del FSM.

## Estado actual (checkpoint)

- Backend MVP funcional con API de `ingestion`, `decks` y `simulate`.
- Contrato estricto en simulacion (`strict` / `strict_intent_resolution`) con errores versionados (`contract_version: "1"`).
- FSM reforzado con validacion de legalidad de acciones (evita aplicar acciones invalidas).
- Golden tests agregados para transiciones de engine y snapshot de contrato en `/simulate/match`.
- Suite de pruebas actual: `90 passed` en `backend`.

## Roadmap de continuidad

El plan de trabajo para retomar en una nueva sesion esta en:

- `ROADMAP.md`

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

Benchmark offline (reproducible por `seed`):

```bash
python -m src.domain.simulation.benchmark --seeds 7,11,19 --matches-per-seed 20 --max-turns 12 --target-lore 8 --ismcts-iterations 64
```

Benchmark con rollout policy y modo espejo (sesgo de primer turno):

```bash
python -m src.domain.simulation.benchmark --seeds 7,11,19 --matches-per-seed 15 --max-turns 12 --target-lore 8 --ismcts-iterations 64 --rollout-policy random --mirror-start-player
```

`rollout_policy` soporta `random` (default, estable) y `guided_v1` (experimental).

Ejemplo de lectura base: `docs/benchmarks/baseline-fase2-v1.md`.

Sensibilidad por iteraciones de ISMCTS: `docs/benchmarks/sensitivity-ismcts-iterations-v1.md`.

A/B de rollout policy (`random` vs `guided_v1`): `docs/benchmarks/rollout-policy-ab-v1.md`.

Benchmark espejo de jugador inicial: `docs/benchmarks/mirror-start-player-v1.md`.

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
