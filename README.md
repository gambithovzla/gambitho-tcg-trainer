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
  - validacion de mazos Lorcana,
  - motor FSM base con acciones y `The Bag`,
  - simulacion simplificada bot vs bot,
  - ingesta Lorcana (`POST /ingest/lorcana`) con escritura SQL y hooks de grafo/vectorial.

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
