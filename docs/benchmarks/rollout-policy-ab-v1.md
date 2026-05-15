# A/B rollout policy en ISMCTS (v1)

Comparativa rápida con misma configuración para `rollout_policy`:

- `seeds`: `7,11,19`
- `matches_per_seed`: `15`
- `max_turns`: `12`
- `target_lore`: `8`
- `ismcts_iterations`: `64`
- total por corrida: `45` partidas

Archivos:

- `backend/benchmark-results/ab_rollout_random_smoke.json`
- `backend/benchmark-results/ab_rollout_guided_v1_smoke.json`

## Resultado (`ismcts`)

- `random`:
  - `p1_winrate=0.7778`
  - `p2_winrate=0.1778`
  - `draw_rate=0.0444`
  - `average_turns=10.2889`
- `guided_v1`:
  - `p1_winrate=0.9333`
  - `p2_winrate=0.0667`
  - `draw_rate=0.0000`
  - `average_turns=9.4667`

## Lectura

- `guided_v1` acelera partidas y reduce empates, pero **incrementa de forma fuerte el sesgo a P1**.
- Para el objetivo actual de Fase 2 (mejorar calidad sin amplificar sesgo), **se mantiene `random` como default**.
- El flag `rollout_policy` queda disponible para seguir iterando nuevas políticas sin tocar baseline estable.
