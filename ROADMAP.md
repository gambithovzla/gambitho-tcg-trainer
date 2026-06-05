# Roadmap

Plan para llevar `gambitho-tcg-trainer` de **MVP técnico** a **entrenador élite de Lorcana**: mazos por restricciones, guías por turno, matchup vs meta y simulación con cartas reales.

---

## Visión de producto (north star)

El usuario debería poder pedir, por ejemplo:

> *"Quiero un mazo de toys, amarillo y verde, competitivo, que le gane al meta actual"*

y obtener: **mazo construido** → **guía de líneas por turno** → **winrate estimado vs arquetipos** → feedback tras simular.

### Cuatro pilares

| # | Capacidad | Descripción |
|---|-----------|-------------|
| 1 | **Motor de reglas fiel** | Partidas con 60 cartas del catálogo, keywords y efectos resueltos (no proxies abstractos). |
| 2 | **Deck builder inteligente** | Generación por color, subtipo (`toys`, `princess`, …), curva, rol y restricción "competitivo". |
| 3 | **Analizador estratégico** | Secuencias por turno, fortalezas/debilidades, matchup vs meta importado. |
| 4 | **Simulación fuerte** | ISMCTS (o equivalente) sobre estado real, muchas iteraciones, rollout/value network cuando aplique. |

---

## Visión vs estado actual (honesto)

| Pilar | Estado | Notas |
|-------|--------|--------|
| Catálogo y datos | **Hecho** | ~2960 cartas EN, stats, `rules_text`, subtypes, imágenes Ravensburger, API `/catalog/*`. |
| Motor de reglas fiel | **Muy incompleto** | FSM con *intents* (`tempo`, `aggressive`, `quester`…), no instancias de carta del catálogo. |
| Deck builder inteligente | **No iniciado** | Linter 60/2 colores; sin generador, sin sinergias Neo4j operativas, sin meta. |
| Analizador estratégico | **No iniciado** | Sin guías, sin matchup, sin secuencias óptimas por turno. |
| Simulación fuerte | **Scaffold** | ISMCTS root-only, pocas iteraciones, sin red neuronal; entrena sobre proxy, no sobre Lorcana real. |

**Cuello de botella:** el catálogo existe, pero **`/simulate/match` no juega UUIDs reales**. Hasta cerrar eso, optimizar `guided_v2` o benchmarks de intents tiene **ROI bajo**.

### Qué sí aporta el MVP actual

- Base de ingeniería sólida (capas dominio/infra/API, tipos, tests).
- Ingesta híbrida y persistencia multi-DB preparada.
- Strict mode, presets, linter y catálogo visual útiles como **infra**, no como producto final.

---

## Estado de partida (técnico)

| Área | Entregable |
|------|------------|
| Catálogo | PostgreSQL + Railway, imágenes oficiales, `GET /catalog/cards` |
| Ingesta | `hybrid_bootstrap`, `POST /ingest/lorcana/hybrid` |
| FSM (proxy) | Turnos, challenge con defensor, song, The Bag placeholder |
| API / UI | Simulación, decks, ingesta, catálogo en Next.js |
| Calidad | **94 passed**, `docs/benchmarks/`, `rule-fidelity-criteria.md` |

---

## Fase 0 — Catálogo y datos ✅ (cerrada)

- [x] LorcanaJSON EN completo, esquema SQL, imágenes, UI catálogo.

---

## Fase A — Motor con cartas reales 🔴 CRÍTICA

**Prioridad única** hasta alcanzar DoD. Sin esta fase no hay deck builder creíble ni ISMCTS útil.

### A.1 Modelo de estado

- [ ] Mazo de 60 `card_uuid` por jugador (shuffle, draw, mulligan).
- [ ] Mano, board, inkwell y descarte como **instancias** (id de instancia + `card_uuid` + daño/exerted/ubicación).
- [x] Soporte Item y Location en board (P0: jugar, quest en Location; Item sin efectos de texto).

### A.2 Acciones desde catálogo

- [ ] Resolver carta vía Postgres al jugar (cost, type, subtypes, `rules_text`).
- [ ] Keywords P0 ejecutables: Evasive, Rush, Ward, Resist, Support, Bodyguard, Challenger, Reckless (según [`rule-fidelity-criteria.md`](docs/engine/rule-fidelity-criteria.md)).
- [ ] Canciones / cantar con coste real de tinta y singers (extender lo ya hecho en proxy).

### A.3 Reglas y The Bag

- [ ] Parser o capa híbrida *keyword-first* + fragmentos de `rules_text` para efectos frecuentes.
- [x] The Bag base: cola de triggers con orden LIFO (gain lore/draw/location set step).

### A.4 API y tests

- [ ] `POST /simulate/match` acepta decks como lista de `card_uuid` (+ copias); modo legacy de intents deprecado o paralelo.
- [ ] Golden: partida mínima con 2 mazos del catálogo y al menos 5 keywords verificados en log/estado.

**Definition of Done Fase A**

- Una partida bot vs bot usa **solo cartas del catálogo** de principio a fin.
- Tests de regresión en keywords P0 y mulligan/draw.
- Documentado en README qué reglas están **in** vs **out**.

**Estimación orientativa:** 3–4 meses (1 dev FT) para P0 jugable; 6+ meses para fidelidad alta.

---

## Fase B — Deck builder inteligente

*Bloqueada por Fase A para simulación de validación; puede empezar en paralelo la parte de datos.*

- [ ] Generador por restricciones: colores + subtypes + tamaño de curva.
- [ ] Grafo Neo4j: queries de sinergia (`HAS_SUBTYPE`, combos frecuentes).
- [ ] Import de listas meta (torneos / comunidad) y etiquetado de arquetipos.
- [ ] Optimizador: roles (quest, removal, flood) y balance de coste.

**DoD:** API `POST /decks/generate` con payload tipo `{ colors, subtypes, competitive: true }` → 60 cartas válidas + informe.

**Estimación:** 2–3 meses tras A.1–A.2.

---

## Fase C — Analizador estratégico y guías

- [ ] Líneas recomendadas por turno (heurística + simulación corta).
- [ ] Matchup: winrate vs arquetipos del meta importado.
- [ ] Informe fortalezas/debilidades del mazo.
- [ ] Guía en lenguaje natural (plantillas; LLM opcional).

**DoD:** Para un mazo dado, respuesta estructurada + texto guía en UI.

**Estimación:** 2–3 meses tras Fase A estable.

---

## Fase D — Simulación fuerte (ISMCTS + ML)

**Explícitamente después de Fase A.** No priorizar `guided_v2` sobre cartas reales.

- [ ] ISMCTS con tree reuse y 1000+ iteraciones configurables.
- [ ] Rollout policy entrenable; value network para evaluar posiciones.
- [ ] Simulación paralela / batch para benchmarks.

**DoD:** Mejora medible vs heurística **en partidas con cartas reales**, reporte en `docs/benchmarks/`.

**Estimación:** 4–6 meses tras Fase A.

---

## Fase E — Producto end-to-end

- [ ] Flujo: catálogo → construir mazo → guía → simular → feedback.
- [ ] Frontend: deck builder visual, guía interactiva, no solo JSON.
- [ ] Despliegue coherente (API + UI + Postgres Railway).

**Estimación:** 2–3 meses con A–C avanzados.

### Horizonte total (orientativo)

| Equipo | Calendario aproximado |
|--------|------------------------|
| 1 dev FT | 13–19 meses hasta producto élite completo |
| 2–3 devs | 6–10 meses con alcance acotado (sets core + P0 keywords) |

---

## Mantenimiento técnico (paralelo, no bloquea A)

Tareas de calidad del MVP proxy; hacer cuando no roben foco de Fase A:

| Issue | Tema | Prioridad |
|-------|------|-----------|
| ISSUE-001 | Snapshot `/simulate/decision` | Media |
| ISSUE-002 | Contrato `turns_played` | Media |
| ISSUE-003 | Strict en match/decision | Media |
| ISSUE-004 | Criterios fidelidad | ✅ Hecho |
| ISSUE-005 | Challenge defensor explícito | ✅ Hecho (proxy) |
| ISSUE-006 | Song costes/condiciones | ✅ Hecho (proxy) |
| ISSUE-007 | Catálogo visual | ✅ Hecho |

---

## ISSUE-008: Simulación con instancias de carta reales 🔴

**Estado:** en progreso (spike) — **epic de Fase A**

### Objetivo

Que el motor deje de depender de *intent profiles* abstractos y consuma el catálogo PostgreSQL como fuente de verdad del juego.

### Tareas

1. [x] `CardInstance` + `RealGameState` (mazo 60, mano, board, ink).
2. [x] Cargar definiciones desde catálogo (`PostgresCatalogProvider`).
3. [x] Acciones: ink, jugar Character, quest, challenge, end turn (`POST /simulate/match/real`).
4. [x] Bot heurístico mínimo + tests en `test_real_card_engine.py`.
5. [x] Song, Action (básico); mulligan sin tinta; Item/Location P0; The Bag base LIFO.
6. [x] Keywords P0: **Evasive**, **Ward**, **Resist**, **Rush**, **Challenger**, **Bodyguard**, **Reckless**, **Support** + tests.

### Entregado en spike (rama actual)

- Motor `RealCardGameEngine` (`engine_mode: real_cards`, `turn_protocol_version: real-5`).
- Endpoint `POST /simulate/match/real` con decks `{ card_id, copies }` × 60.
- Keyword **Evasive** en legalidad de challenge.

### Criterio de cierre (epic completo)

- [ ] Match API con dos listas de 60 UUIDs del catálogo termina sin error en producción.
- [x] Log referencia **nombres** de cartas jugadas (`cards_referenced`).
- [x] ≥ 5 keywords P0 con tests dedicados (5/5 básicos).
- [ ] README tabla "in/out" de reglas ampliada.

### Anti-objetivos (no hacer antes de cerrar 008)

- Subir iteraciones ISMCTS sin estado real.
- Deck builder "competitivo" sin simulación fiel.
- Entrenar redes sobre intents proxy.

---

## Backlog inmediato (orden recomendado)

1. **ISSUE-008** — Rush/Ward/Resist + jugar Action/Song; mulligan; partida con IDs del catálogo Railway.
2. Unificar o deprecar `/simulate/match` (proxy) cuando `real-1` cubra el flujo demo.
3. Deck builder visual que exporte a `card_id` + `copies` para `/simulate/match/real`.
4. Mantenimiento: ISSUE-002 + ISSUE-001.
5. ~~guided_v2~~ → pospuesto hasta Fase D.

---

## Prompt sugerido para retomar

"Implementemos ISSUE-008 / Fase A.1: estado con 60 UUIDs, mulligan y primera acción de jugar carta desde catálogo. Mantén tests verdes."
