CREATE TABLE IF NOT EXISTS dim_card_core (
  uuid TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  subtitle TEXT,
  set_id TEXT,
  collector_number TEXT,
  rarity TEXT,
  image_url TEXT,
  image_thumbnail_url TEXT
);

ALTER TABLE dim_card_core ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE dim_card_core ADD COLUMN IF NOT EXISTS image_thumbnail_url TEXT;

CREATE TABLE IF NOT EXISTS fact_card_stats (
  card_uuid TEXT PRIMARY KEY REFERENCES dim_card_core (uuid),
  cost INTEGER,
  inkwell_inkable BOOLEAN,
  strength INTEGER,
  willpower INTEGER,
  lore INTEGER,
  move_cost INTEGER
);

CREATE TABLE IF NOT EXISTS dim_card_tags (
  card_uuid TEXT PRIMARY KEY REFERENCES dim_card_core (uuid),
  color_aspect TEXT[],
  card_type TEXT,
  subtypes TEXT[]
);

CREATE TABLE IF NOT EXISTS fact_card_rules (
  card_uuid TEXT PRIMARY KEY REFERENCES dim_card_core (uuid),
  rules_text TEXT NOT NULL DEFAULT '',
  source_provider TEXT NOT NULL DEFAULT 'generic',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
