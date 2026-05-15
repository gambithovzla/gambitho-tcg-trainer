# Sensibilidad ISMCTS por iteraciones (v1)

Comparativa offline sobre el mismo entorno del baseline:

- `seeds`: `7,11,19,23,29`
- `matches_per_seed`: `30`
- `max_turns`: `12`
- `target_lore`: `8`
- total por corrida: `150` partidas
- estrategia evaluada: `ismcts`

Archivos:

- `backend/benchmark-results/sensitivity_ismcts_iter_32.json`
- `backend/benchmark-results/sensitivity_ismcts_iter_64.json`
- `backend/benchmark-results/sensitivity_ismcts_iter_128.json`

## Resultado resumido

- **32 iteraciones**
  - `p1_winrate=0.5733`, `p2_winrate=0.2000`, `draw_rate=0.2267`
  - `average_turns=10.9867`, `variance=0.2446`
- **64 iteraciones**
  - `p1_winrate=0.8000`, `p2_winrate=0.1667`, `draw_rate=0.0333`
  - `average_turns=10.0200`, `variance=0.1600`
- **128 iteraciones**
  - `p1_winrate=0.8733`, `p2_winrate=0.1133`, `draw_rate=0.0133`
  - `average_turns=9.5533`, `variance=0.1106`

## Lectura

- Subir iteraciones reduce draws y duración media, pero aumenta sesgo hacia P1 en este entorno.
- A `32` hay mejor equilibrio P1/P2, pero demasiados empates.
- A `128` casi no hay empates, pero P1 domina más.
- **`64` queda como punto intermedio razonable** para baseline operativo actual.

## Acción sugerida

Usar `64` como default de benchmark y enfocar la siguiente iteración en rollout policy para:

1. bajar sesgo de P1 sin volver a subir draws de forma marcada;
2. mantener duración media cerca de `10` turnos o menos.
