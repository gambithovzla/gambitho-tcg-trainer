# Keyword handlers (plan Fase A)

Mapa previsto de keywords Lorcana → módulo del motor. Estado: **planificación**; el FSM proxy actual no implementa la mayoría.

Referencia de prioridad: [`rule-fidelity-criteria.md`](rule-fidelity-criteria.md).

| Keyword | Impacto | Handler previsto | Estado |
|---------|---------|------------------|--------|
| Evasive | P0 | `ChallengeLegality` — solo challengers con Evasive | Pendiente (real) |
| Rush | P0 | `PlayRestrictions` — puede challenge turn played | Pendiente |
| Ward | P0 | `TargetSelection` — no targeteable por rivales | Pendiente |
| Resist | P0 | `DamageModification` — restar N al recibir daño | Pendiente |
| Support | P0 | `QuestBonus` / static | Pendiente |
| Bodyguard | P0 | `TargetSelection` — obligatorio si exerted | Pendiente |
| Challenger | P1 | `ChallengeLegality` — +N strength al challenge | Pendiente |
| Reckless | P1 | `MustChallenge` si able | Pendiente |
| Shift | P1 | `PlayReplacement` — jugar sobre personaje mismo nombre | Pendiente |

## Reglas de texto (`rules_text`)

Estrategia híbrida (Fase A.3):

1. **Keywords** en tabla o flags en ingestión → handlers deterministas.
2. **Patrones frecuentes** en `rules_text` (regex / plantillas) para P0.
3. **Resto** — no ejecutar en simulación hasta parser completo; log `unsupported_effect`.

## DoD por keyword

Cada fila P0 requiere al menos un test en `test_real_card_engine.py` (por crear) con carta real del catálogo o fixture mínimo con `rules_text` oficial.
