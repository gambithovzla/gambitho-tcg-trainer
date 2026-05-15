# Baseline Fase 2 - heuristic vs ismcts

Configuracion ejecutada con `backend/src/domain/simulation/benchmark.py`:

- `seeds`: `7,11,19,23,29`
- `matches_per_seed`: `30`
- `max_turns`: `12`
- `target_lore`: `8`
- `ismcts_iterations`: `64`
- total por estrategia: `150` partidas
- artefacto JSON: `backend/benchmark-results/baseline_fase2_v1.json`

## Resultados principales

- `heuristic`: `p1_winrate=1.00`, `p2_winrate=0.00`, `draw_rate=0.00`, `average_turns=11.00`
- `ismcts`: `p1_winrate=0.80`, `p2_winrate=0.1667`, `draw_rate=0.0333`, `average_turns=10.02`

## Lectura rapida

- Hay sesgo fuerte de primer jugador en este entorno simplificado; `heuristic` gana siempre como P1.
- `ismcts` reduce ese sesgo: baja `p1_winrate` en `-0.20` y habilita victorias de P2.
- `ismcts` termina partidas antes (`-0.98` turnos medios; `-12.72` entradas de historial), compatible con lineas mas directas.
- Distribucion de acciones con `ismcts` vs `heuristic`:
  - mas `quest` (`+0.0968`) y `sing_song` (`+0.0098`)
  - menos `challenge` (`-0.0908`)
  - ligeramente menos `develop_ink` y `play_character`

## Siguientes pasos sugeridos

1. Congelar este baseline como referencia de Fase 2.
2. Medir sensibilidad por `ismcts_iterations` (`32`, `64`, `128`) con mismo set de seeds.
3. Probar rollout policy con heuristica de lore-race/tempo para ver si mejora `p2_winrate` sin aumentar draws.
