# Keyword handlers (plan Fase A)

Mapa previsto de keywords Lorcana → módulo del motor. Estado: **planificación**; el FSM proxy actual no implementa la mayoría.

Referencia de prioridad: [`rule-fidelity-criteria.md`](rule-fidelity-criteria.md).

| Keyword | Impacto | Handler previsto | Estado |
|---------|---------|------------------|--------|
| Evasive | P0 | Solo atacantes con Evasive o **Alert** retan defensor Evasive (CR 9.4) | Hecho |
| Alert | P0 | Retar «como si tuviera Evasive»; no es Evasive al defender | Hecho |
| Rush | P0 | `PlayRestrictions` — puede challenge turn played | Hecho (real FSM) |
| Ward | P0 | Efectos rivales: no elegible; **sí** puede ser retado (CR 9.12) | Parcial (challenge OK; targeting pendiente) |
| Resist | P0 | `DamageModification` — restar N al recibir daño | Hecho (real FSM) |
| Support | P0 | `QuestBonus` — +S a aliado al quest | Hecho (real FSM) |
| Bodyguard | P0 | `TargetSelection` si hay Bodyguard exerted retable; **opcional** entrar exerted al jugar | Hecho (real FSM) |
| Challenger | P1 | `ChallengeLegality` — +N strength al challenge | Hecho (real FSM) |
| Reckless | P1 | `MustChallenge` si able; no quest | Hecho (real FSM) |
| Shift | P1 | `PlayReplacement` — jugar sobre personaje mismo nombre | Pendiente |

## Reglas de texto (`rules_text`)

Estrategia híbrida (Fase A.3):

1. **Keywords** en tabla o flags en ingestión → handlers deterministas.
2. **Patrones frecuentes** en `rules_text` (regex / plantillas) para P0.
3. **Resto** — no ejecutar en simulación hasta parser completo; log `unsupported_effect`.

## DoD por keyword

Cada fila P0 requiere al menos un test en `test_real_card_engine.py` (por crear) con carta real del catálogo o fixture mínimo con `rules_text` oficial.
