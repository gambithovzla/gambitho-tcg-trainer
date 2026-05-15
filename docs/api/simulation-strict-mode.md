# Simulation Strict Mode

Esta guia documenta el modo estricto de resolucion de intents para simulacion.

## Endpoints con strict mode

- `POST /simulate/intent-profile` con `strict: true`
- `POST /simulate/match` con `strict_intent_resolution: true`
- `POST /simulate/decision` con `strict_intent_resolution: true`

## Contrato de error estable (`422`)

Cuando falla en modo estricto, la API responde `422` con `detail` estructurado:

```json
{
  "detail": {
    "contract_version": "1",
    "error_code": "STRICT_INTENT_HINTS_INSUFFICIENT",
    "message": "Strict intent resolution for active_player failed: 1/2 deck cards have usable hints and catalog matched 0/2. Provide card hints (type/stats) or ingest catalog.",
    "context": {
      "actor": "active_player",
      "hinted_cards": 1,
      "matched_catalog_cards": 0,
      "total_cards": 2,
      "source": "input_only"
    }
  }
}
```

Codigos actuales:

- `STRICT_INTENT_PRESET_MISSING`: falta uno o mas presets referenciados.
- `STRICT_INTENT_HINTS_INSUFFICIENT`: la inferencia por deck no tiene señales suficientes (ni catalogo suficiente ni hints completos).
- `STRICT_INTENT_INPUT_REQUIRED`: en strict mode faltan deck/pesos/preset para el actor evaluado.

Sugerencia para frontend: usa `detail.error_code` para flujo de UI y `detail.context` para mensajes de diagnostico sin parsear `message`.

## Version del contrato (v1)

El objeto `detail` de los `422` de strict intent se trata como **contrato v1**:

- **Estable**: `contract_version`, `error_code` y las claves presentes en `context` (no dependas de parsear `message` para logica).
- **Inestable a proposito**: el texto de `message` puede cambiar en redaccion sin considerarse cambio incompatible.
- **Evolucion**: si mas adelante hay un v2 con campos nuevos o semantica distinta, se documentara aqui.

## Ejemplos rapidos

### `POST /simulate/intent-profile` (pasa)

```json
{
  "strict": true,
  "deck": [
    { "card_id": "song_hint", "copies": 4, "card_type": "Song", "subtypes": ["Song"] },
    { "card_id": "char_hint", "copies": 4, "card_type": "Character", "cost": 3, "strength": 2, "willpower": 3, "lore": 1 }
  ]
}
```

Respuesta `200` esperada (resumen):

```json
{
  "weights": {
    "tempo": 0.2,
    "aggressive": 0.1,
    "quester": 0.2,
    "defender": 0.1,
    "song": 0.4
  },
  "cards_seen": 2,
  "cards_matched_catalog": 0,
  "source": "input_only",
  "strict_validation": [
    {
      "actor": "intent_profile",
      "hinted_cards": 2,
      "matched_catalog_cards": 0,
      "total_cards": 2,
      "source": "input_only"
    }
  ]
}
```

### `POST /simulate/intent-profile` (falla: hints insuficientes)

```json
{
  "strict": true,
  "deck": [
    { "card_id": "no_hint_a", "copies": 4 },
    { "card_id": "no_hint_b", "copies": 4 }
  ]
}
```

Respuesta `422` esperada (resumen):

```json
{
  "detail": {
    "contract_version": "1",
    "error_code": "STRICT_INTENT_HINTS_INSUFFICIENT",
    "message": "Strict intent resolution for intent_profile failed: 0/2 deck cards have usable hints and catalog matched 0/2. Provide card hints (type/stats) or ingest catalog.",
    "context": {
      "actor": "intent_profile",
      "hinted_cards": 0,
      "matched_catalog_cards": 0,
      "total_cards": 2,
      "source": "input_only"
    }
  }
}
```

### `POST /simulate/match` (pasa)

```json
{
  "max_turns": 4,
  "target_lore": 6,
  "strategy": "heuristic",
  "strict_intent_resolution": true,
  "player_one_deck": [
    { "card_id": "non_catalog_song", "copies": 4, "card_type": "Song", "subtypes": ["Song"] },
    { "card_id": "non_catalog_char", "copies": 4, "card_type": "Character", "cost": 3, "strength": 2, "willpower": 3, "lore": 1 }
  ],
  "player_two_intent_weights": {
    "tempo": 0.2,
    "aggressive": 0.2,
    "quester": 0.2,
    "defender": 0.2,
    "song": 0.2
  }
}
```

Respuesta `200` esperada (resumen):

```json
{
  "winner_player_id": 1,
  "turns_played": 4,
  "history": ["..."],
  "resolved_player_one_intent_weights": {
    "tempo": 0.2,
    "aggressive": 0.2,
    "quester": 0.2,
    "defender": 0.1,
    "song": 0.3
  },
  "resolved_player_two_intent_weights": {
    "tempo": 0.2,
    "aggressive": 0.2,
    "quester": 0.2,
    "defender": 0.2,
    "song": 0.2
  },
  "resolved_weights_source": "p1:deck;p2:manual;opp:manual",
  "strict_validation": [
    {
      "actor": "p1",
      "hinted_cards": 2,
      "matched_catalog_cards": 0,
      "total_cards": 2,
      "source": "input_only"
    }
  ]
}
```

### `POST /simulate/match` (falla: preset faltante)

```json
{
  "max_turns": 6,
  "target_lore": 6,
  "strategy": "heuristic",
  "strict_intent_resolution": true,
  "player_one_intent_preset": "missing_1"
}
```

Respuesta `422` esperada (resumen):

```json
{
  "detail": {
    "contract_version": "1",
    "error_code": "STRICT_INTENT_PRESET_MISSING",
    "message": "Missing intent preset(s): missing_1",
    "context": {
      "missing_presets": ["missing_1"]
    }
  }
}
```

### `POST /simulate/decision` (pasa)

```json
{
  "target_lore": 8,
  "active_player_id": 1,
  "player_one_lore": 2,
  "player_two_lore": 3,
  "ismcts_iterations": 10,
  "strict_intent_resolution": true,
  "active_player_deck": [
    { "card_id": "active_song", "copies": 4, "card_type": "Song", "subtypes": ["Song"] },
    { "card_id": "active_char", "copies": 4, "card_type": "Character", "cost": 2, "strength": 2, "willpower": 2, "lore": 1 }
  ],
  "opponent_intent_weights": {
    "tempo": 0.2,
    "aggressive": 0.2,
    "quester": 0.2,
    "defender": 0.2,
    "song": 0.2
  }
}
```

Respuesta `200` esperada (resumen):

```json
{
  "chosen_action_type": "develop_ink",
  "chosen_player_id": 1,
  "chosen_amount": null,
  "chosen_cost": null,
  "chosen_archetype": null,
  "total_iterations": 10,
  "options": ["..."],
  "resolved_active_player_intent_weights": {
    "tempo": 0.2,
    "aggressive": 0.2,
    "quester": 0.2,
    "defender": 0.1,
    "song": 0.3
  },
  "resolved_opponent_intent_weights": {
    "tempo": 0.2,
    "aggressive": 0.2,
    "quester": 0.2,
    "defender": 0.2,
    "song": 0.2
  },
  "resolved_weights_source": "active:deck;opponent:manual",
  "strict_validation": [
    {
      "actor": "active_player",
      "hinted_cards": 2,
      "matched_catalog_cards": 0,
      "total_cards": 2,
      "source": "input_only"
    }
  ]
}
```

### `POST /simulate/decision` (falla: preset faltante)

```json
{
  "target_lore": 8,
  "active_player_id": 1,
  "player_one_lore": 2,
  "player_two_lore": 3,
  "ismcts_iterations": 10,
  "strict_intent_resolution": true,
  "opponent_intent_preset": "missing_preset"
}
```

Respuesta `422` esperada (resumen):

```json
{
  "detail": {
    "contract_version": "1",
    "error_code": "STRICT_INTENT_PRESET_MISSING",
    "message": "Missing intent preset(s): missing_preset",
    "context": {
      "missing_presets": ["missing_preset"]
    }
  }
}
```
