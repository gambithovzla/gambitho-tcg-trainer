# Roadmap

Plan de continuidad para llevar `gambitho-tcg-trainer` desde MVP tecnico a v1 util de entrenamiento.

## Estado de partida (actualizado)

### Completado recientemente

| Area | Entregable |
|------|------------|
| **Catálogo real** | ~2960 cartas EN en PostgreSQL (stats, reglas, tags). Soporte Railway via `POSTGRES_DSN`. |
| **Imagenes oficiales** | `image_url` / `image_thumbnail_url` (Ravensburger). CLI `image_backfill` y ingesta híbrida. |
| **Ingesta híbrida** | `POST /ingest/lorcana/hybrid`, `hybrid_bootstrap`, precedencia Lorcast/LorcanaJSON. |
| **API catálogo** | `GET /catalog/cards`, `GET /catalog/cards/{id}`. |
| **Frontend** | UI Next.js: simulacion, decks, ingesta + **catálogo visual** de cartas físicas. |
| **Protocolo de turnos** | `turn_protocol_version`, `starting_player_id` en respuestas de match. |
| **Engine P0** | Challenge con defensor explicito; song con rutas gratis/pagada. |
| **Calidad** | Suite backend **94 passed**; benchmarks en `docs/benchmarks/`. |

### Base ya existente

- Infra local opcional (PostgreSQL, Neo4j, Qdrant).
- Linter/reparacion de mazos.
- Simulacion `heuristic` / `ismcts` con strict mode documentado.
- Contrato de errores `contract_version: "1"`.

---

## Fase 0 — Catálogo y datos (cerrada)

Objetivo: cartas reales, persistidas y visibles como las físicas.

- [x] Ingesta LorcanaJSON completa (EN).
- [x] Esquema SQL con `fact_card_rules` y URLs de imagen.
- [x] Backfill / re-sync de imagenes.
- [x] UI de catálogo con arte oficial.

**Siguiente mejora opcional:** re-ingesta periódica o job en Railway para sets nuevos; Lorcast como enriquecimiento.

---

## Fase 1 — Simulator confiable (prioridad alta)

Objetivo: consistencia de reglas e invariantes para evitar sesgos en entrenamiento.

1. Completar reglas de engine de mayor impacto (P1):
   - efectos de texto / habilidades mas alla del scaffold actual.
   - revisar reglas de finalizacion y conteo de turnos (`turns_played`) — ver ISSUE-002.
2. Ampliar golden tests de engine:
   - secuencias con doble challenge y acumulacion de dano.
   - escenarios de borde (mano vacia, deck vacio, solo `end_turn`).
3. Ampliar golden tests de API:
   - snapshot de `/simulate/decision`.
   - snapshot de `/simulate/intent-profile` en modo `strict`.

**Hecho en P0:** target explicito en challenge (ISSUE-005); song costos/condiciones (ISSUE-006).

Definition of Done Fase 1:
- sin regresiones en golden tests.
- contratos API de simulacion cubiertos por tests snapshot.
- suite verde en CI local.

---

## Fase 2 — ISMCTS mas fuerte

Objetivo: mejorar calidad de decisiones de manera medible.

1. Rollout policy `guided_v2` y A/B vs `random` en modo espejo.
2. Determinizacion mas informada (mano/rangos, pesos por perfil de mazo).
3. Benchmarks reproducibles por seed (ya hay CLI; ampliar reportes).

Definition of Done Fase 2:
- mejora medible vs baseline heuristico.
- reporte de benchmark versionado en `docs/benchmarks/`.

---

## Fase 3 — Training loop y operacion

Objetivo: ciclo de iteracion rapido para experimentar.

1. Pipeline de experimentos (configs versionadas, batch, export).
2. Observabilidad (latencia por endpoint, errores por `error_code`).
3. UX: constructor de mazos visual desde catálogo (arrastrar cartas, no solo JSON).

Definition of Done Fase 3:
- flujo end-to-end reproducible en un comando.
- comparativa entre configuraciones en una sola corrida.

---

## Backlog inmediato (siguiente sesion)

1. **Mazos visuales:** armar deck desde catálogo (clic → JSON / validacion).
2. **ISSUE-001 / ISSUE-002 / ISSUE-003:** snapshots y contrato `turns_played` + cobertura strict en match/decision.
3. **guided_v2** + benchmark espejo como criterio de aceptacion (Fase 2).
4. **Despliegue:** backend + frontend en Railway/Vercel con misma `POSTGRES_DSN`.

---

## Issue list (lista operativa)

### ISSUE-001: Golden snapshot de `/simulate/decision`

- Estado: **pendiente**
- Criterio: test estable en `test_simulation_api.py`.

### ISSUE-002: Contrato de `turns_played`

- Estado: **pendiente**
- Criterio: semantica documentada + test de limite.

### ISSUE-003: Cobertura de `STRICT_INTENT_INPUT_REQUIRED`

- Estado: **pendiente**
- Criterio: tests en `/simulate/match` y `/simulate/decision`.

### ISSUE-004: Criterios de fidelidad de reglas

- Estado: **hecho** — [`docs/engine/rule-fidelity-criteria.md`](docs/engine/rule-fidelity-criteria.md)

### ISSUE-005: Target selection explicito en challenge

- Estado: **hecho** — `ChallengeAction(defender_index)` + tests en `test_engine_transitions.py`.

### ISSUE-006: Reglas de song (costos/condiciones)

- Estado: **hecho** — `SingSongAction` con rutas gratis/pagada + tests.

### ISSUE-007: Catálogo visual e imagenes oficiales

- Estado: **hecho**
- Entregables: columnas de imagen, `image_backfill`, `/catalog/*`, UI en `frontend/`.

---

## Prompt sugerido para retomar

"Continuemos con Fase 1 del `ROADMAP.md`: golden snapshots de `/simulate/decision` y constructor de mazos visual desde el catálogo."
