# Benchmark espejo de jugador inicial (v1)

Corrida en modo espejo (`--mirror-start-player`) para cuantificar sesgo de primer turno:

- `seeds`: `7,11,19`
- `matches_per_seed`: `15`
- `max_turns`: `12`
- `target_lore`: `8`
- `ismcts_iterations`: `64`
- total por estrategia: `90` partidas (cada semilla/indice corre iniciando con P1 y con P2)

Archivos:

- `backend/benchmark-results/mirror_random_smoke.json`
- `backend/benchmark-results/mirror_guided_v1_smoke.json`

## Resultado clave

### ISMCTS + `rollout_policy=random`

- `first_player_winrate = 0.8111`
- `second_player_winrate = 0.1333`
- `draw_rate = 0.0556`

### ISMCTS + `rollout_policy=guided_v1`

- `first_player_winrate = 0.9556`
- `second_player_winrate = 0.0444`
- `draw_rate = 0.0000`

## Lectura

- El sesgo de primer turno es muy fuerte incluso con `random`.
- `guided_v1` empeora claramente ese sesgo (aunque reduce draws y duración).
- Se mantiene `rollout_policy=random` como default y queda pendiente diseñar `guided_v2` con objetivo explícito de reducir `first_player_winrate`.
