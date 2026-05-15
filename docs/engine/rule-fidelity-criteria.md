# Criterios de fidelidad de reglas (engine)

Documento operativo para **ordenar el backlog del FSM** según impacto en simulación y entrenamiento (ISMCTS / heurísticas). No sustituye reglas oficiales del juego: describe el **modelo actual** en código y dónde conviene invertir primero.

## Dimensiones de priorización

| Dimensión | Pregunta guía |
|-----------|----------------|
| **Impacto** | Si la regla está mal o simplificada, ¿cambia de forma relevante el espacio de acciones legales o el resultado terminal (lore / tablero)? |
| **Frecuencia** | ¿Aparece en casi todas las partidas (economía de tinta, búsqueda, fin de turno) o solo en líneas raras? |
| **Riesgo de sesgo** | ¿Empuja al bot o al rollout a decisiones sistemáticamente distintas al juego real (por ejemplo, combate que siempre elige el mismo objetivo)? |

**Prioridad**

- **P0**: alto impacto y/o alto riesgo de sesgo; corregir antes de confiar en métricas de entrenamiento.
- **P1**: impacto medio o alta frecuencia; importante para coherencia de partidas largas.
- **P2**: refinamiento, bordes raros o placeholders que no distorsionan tanto el aprendizaje.

## Reglas del modelo actual (clasificación)

Referencias de tests: `backend/tests/test_engine_transitions.py` salvo que se indique otro.

| Área | Regla / comportamiento (MVP en código) | P | Impacto / sesgo | Cobertura test esperada |
|------|------------------------------------------|---|------------------|-------------------------|
| Victoria | Lore ≥ `target_lore` asigna ganador y corta acciones | **P0** | Define objetivo de simulación | `test_quest_updates_state_and_resolves_bag`, flujos golden |
| Economía | `develop_ink` una vez por turno; tinta disponible al inicio de main | **P0** | Ritmo de juego y jugabilidad de personajes | `test_end_turn_refreshes_next_player_ink_and_turn_flags`, golden opening |
| Personajes | `play_character` desde plantillas; coste en tinta; consume `hand_intents` alineado al arquetipo | **P0** | Define ramas legales y costes | `test_play_character_consumes_matching_hand_intent`, `test_legal_actions_include_multiple_play_templates_with_enough_ink`, `test_illegal_play_character_does_not_spend_ink_or_change_state` |
| Tablero | `quest` requiere personaje listo; exert tras quest; lore por cantidad legal | **P0** | Principal fuente de lore en MVP | `test_quest_requires_ready_character_and_removes_quest_action_after_use`, `test_illegal_quest_amount_is_rejected` |
| Combate | `challenge` simplificado: atacante listo vs **primer** personaje exerted rival; intercambio de daño y banish | **P0** | **Alto sesgo** si el juego real exige elegir objetivo | `test_challenge_banishes_opponent_exerted_character`, `test_challenge_resolves_damage_exchange_and_can_banish_both`, `test_golden_challenge_flow_damage_persists_across_turns` → ampliar cuando exista selección explícita (ISSUE-005) |
| Canciones | `sing_song`: requiere intent `song`, personaje listo, tinta ≥ coste fijo del modelo | **P0** | Separar coste 0 vs pago es crítico en Lorcana real | `test_sing_song_requires_song_intent_and_consumes_it` → añadir casos gratis vs pago (ISSUE-006) |
| Turno / fases | `end_turn` cambia jugador activo; `turn_number` y `total_turns_taken`; fases ready → draw → main | **P1** | Orden temporal y robo | `test_end_turn_switches_active_player`, `test_first_player_skips_first_draw_step`, `test_golden_opening_flow_develop_play_quest` |
| Estado bordo | Daño persiste; ready phase quita exert/summoning sick | **P1** | Combate multi-turno | `test_golden_challenge_flow_damage_persists_across_turns` |
| Información oculta | Bonus de lore si `hidden_combo_potential` alto (modelo de creencia) | **P1** | Sesga valoraciones ISMCTS si mal calibrado | `test_hidden_combo_potential_can_grant_bonus_lore` |
| Intents | Mano inicial sesgada por pesos de intent | **P2** | Afecta aperturas, no invariantes duros | `test_intent_profile_biases_initial_hand_generation` |
| The Bag | Resolución de triggers placeholder en cadena | **P2** | Extensible; hoy impacto bajo si solo log | `test_quest_updates_state_and_resolves_bag` (`Resolve trigger`) |

## Orden sugerido de implementación (Fase 1 engine)

1. **P0 – Combate**: objetivo explícito en `ChallengeAction` y legalidad (ISSUE-005); goldens de doble challenge y daño acumulado (ROADMAP Fase 1.2).
2. **P0 – Canciones**: coste 0 vs pago y condiciones de cantar gratis (ISSUE-006).
3. **P1 – Turnos**: alinear documentación/API de `turns_played` con `max_turns` (ya documentado en esquema OpenAPI y `simulate_simple_match`).
4. **P1 – Bordes**: mano vacía, deck vacío, solo `end_turn` legal (ROADMAP Fase 1.2).

## Uso del documento

- Antes de añadir reglas nuevas al FSM, clasificarlas con la tabla (P0/P1/P2) y añadir una fila con el test mínimo que las congela.
- Al discutir “fidelidad”, separar **intención de juego real** vs **contrato del MVP** ya testeado en `test_engine_transitions.py`.
