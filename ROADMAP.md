# Roadmap

Plan de continuidad para llevar `gambitho-tcg-trainer` desde MVP tecnico a v1 util de entrenamiento.

## Estado de partida

- Base de infraestructura local lista (PostgreSQL, Neo4j, Qdrant).
- Ingesta Lorcana funcionando (fuentes directas, Lorcast y LorcanaJSON).
- Linter/reparacion de mazos operativo.
- Simulacion con `heuristic` e `ismcts` base disponible via API.
- Strict mode de intents implementado y documentado (incluye `contract_version: "1"` en errores).
- Test suite backend estable: `90 passed`.

## Fase 1 - Simulator confiable (prioridad alta)

Objetivo: asegurar consistencia de reglas e invariantes para evitar sesgos fuertes en entrenamiento.

1. Completar reglas de engine de mayor impacto:
   - seleccionar objetivo explicito en challenge (no solo primer exerted).
   - separar costos/condiciones de song vs cantar gratis cuando aplique el caso.
   - revisar reglas de finalizacion y conteo de turnos (`turns_played`).
2. Ampliar golden tests de engine:
   - secuencias con doble challenge y acumulacion de dano.
   - escenarios de borde (mano vacia, deck vacio, sin acciones salvo `end_turn`).
3. Ampliar golden tests de API:
   - snapshot de contrato para `/simulate/decision`.
   - snapshot para respuesta de `/simulate/intent-profile` en modo `strict`.

Definition of Done Fase 1:
- sin regresiones en golden tests.
- contratos API de simulacion cubiertos por tests snapshot.
- suite verde en CI local.

## Fase 2 - ISMCTS mas fuerte

Objetivo: mejorar calidad de decisiones de manera medible.

1. Mejorar rollout policy:
   - heuristicas de tempo/lore-race en rollouts.
   - penalizacion de lineas dominadas.
2. Determinization mas informada:
   - reforzar uso de senales de mano/rangos.
   - calibrar pesos por perfil de mazo.
3. Benchmarks offline:
   - script reproducible por seed.
   - metricas: winrate, varianza, duracion media, distribucion de acciones.

Definition of Done Fase 2:
- mejora medible vs baseline heuristico.
- reporte de benchmark reproducible guardado en repo.

## Fase 3 - Training loop y operacion

Objetivo: ciclo de iteracion rapido para experimentar.

1. Pipeline de experimentos:
   - configuraciones versionadas.
   - ejecucion batch de simulaciones.
   - export de resultados.
2. Observabilidad:
   - tiempos por endpoint/estrategia.
   - errores por `error_code`.
3. UX tecnica minima:
   - presets y perfiles listos para pruebas comparativas.
   - guia de "runbook" para ejecutar evaluacion completa.

Definition of Done Fase 3:
- un flujo unico de experimento end-to-end reproducible.
- comparativa entre configuraciones en una sola corrida.

## Backlog inmediato (siguiente sesion)

1. Diseñar `guided_v2` (rollout policy) con foco explicito en reducir sesgo P1 sin aumentar draws.
2. Correr A/B (`random` vs `guided_v2`) en modo espejo como criterio de aceptacion.
3. Ampliar corrida espejo (mismo protocolo) a escala baseline para confirmar que la mejora no es solo ruido de muestra.

## Issue list (lista operativa)

### ISSUE-001: Golden snapshot de `/simulate/decision`

Objetivo:
- Congelar contrato base de salida para detectar cambios no intencionales.

Tareas:
- Crear test snapshot para claves obligatorias y tipos.
- Verificar invariantes de `options`, `resolved_weights_source` y `strict_validation`.
- Cubrir caso `strict_intent_resolution=true` y caso normal.

Criterio de cierre:
- Test nuevo estable en `test_simulation_api.py` y suite verde.

### ISSUE-002: Definir contrato de `turns_played`

Objetivo:
- Eliminar ambiguedad de conteo de turnos en `/simulate/match`.

Tareas:
- Decidir semantica final (`<= max_turns` vs `max_turns + 1` posible).
- Ajustar implementacion o documentacion para reflejar contrato real.
- Añadir test de regresion de limite de turnos.

Criterio de cierre:
- Contrato documentado + test estable + sin inconsistencias en API docs.

### ISSUE-003: Cobertura de `STRICT_INTENT_INPUT_REQUIRED`

Objetivo:
- Asegurar consistencia de errores strict en todos los endpoints de simulacion.

Tareas:
- Añadir tests de rechazo por input faltante en `/simulate/match`.
- Añadir tests de rechazo por input faltante en `/simulate/decision`.
- Verificar presencia de `contract_version`, `error_code` y `context`.

Criterio de cierre:
- Tests de error strict completos para `intent-profile`, `match`, `decision`.

### ISSUE-004: Criterios de fidelidad de reglas (engine)

Objetivo:
- Priorizar reglas del FSM por impacto real en calidad de entrenamiento.

Tareas:
- Crear documento corto de criterios (impacto, frecuencia, riesgo de sesgo).
- Clasificar reglas en P0/P1/P2.
- Vincular cada regla priorizada a test/golden esperado.

**Documento:** [`docs/engine/rule-fidelity-criteria.md`](docs/engine/rule-fidelity-criteria.md)

Criterio de cierre:
- Documento de criterios disponible y usado para ordenar el backlog de Fase 1.

### ISSUE-005: Target selection explicito en challenge

Objetivo:
- Evitar simplificacion excesiva de combate (hoy toma primer exerted).

Tareas:
- Extender `ChallengeAction` para seleccionar objetivo.
- Ajustar legalidad y aplicacion de dano/banish.
- Agregar tests de seleccion de objetivo y regresion.

**Estado:** `ChallengeAction(defender_index)` y una acción legal por defensor exerted; ver tests en `test_engine_transitions.py`.

Criterio de cierre:
- API interna del engine soporta target explicito y tests de combate cubren el flujo.

### ISSUE-006: Reglas de song (costos/condiciones)

Objetivo:
- Acercar modelo de canciones a comportamiento de juego esperado.

Tareas:
- Separar condicion de "cantar gratis" vs pago por tinta.
- Actualizar acciones legales y resolucion de `SingSongAction`.
- Añadir tests de casos permitidos/no permitidos.

**Estado:** `SingSongAction` soporta `uses_singer` con dos rutas legales (`cost=0` gratis con singer listo, `cost=1` pagada sin singer), con cobertura dedicada en `test_engine_transitions.py`.

Criterio de cierre:
- Reglas de song coherentes, testeadas y sin regresiones.

## Prompt sugerido para retomar

"Continuemos con Fase 2 del `ROADMAP.md`: implementar `guided_v2` y compararlo en benchmark espejo contra `random`."
