"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { CardCatalog } from "@/components/card-catalog";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Status = "idle" | "loading" | "ok" | "error";

function pretty(data: unknown): string {
  return JSON.stringify(data, null, 2);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  const text = await response.text();
  let payload: unknown = text;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    // keep raw text
  }

  if (!response.ok) {
    const normalized =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    throw new Error(
      typeof normalized === "string" ? normalized : JSON.stringify(normalized, null, 2),
    );
  }
  return payload as T;
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="surface p-5">
      <div className="mb-4">
        <h2 className="panel-title text-xl">{title}</h2>
        <p className="subtle mt-1 text-sm">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

export default function Home() {
  const [health, setHealth] = useState<Status>("idle");
  const [healthDetail, setHealthDetail] = useState<string>("Not checked");

  const [simResult, setSimResult] = useState<string>("{}");
  const [simStatus, setSimStatus] = useState<Status>("idle");
  const [simError, setSimError] = useState<string>("");

  const [decisionResult, setDecisionResult] = useState<string>("{}");
  const [decisionStatus, setDecisionStatus] = useState<Status>("idle");
  const [decisionError, setDecisionError] = useState<string>("");

  const [intentResult, setIntentResult] = useState<string>("{}");
  const [intentStatus, setIntentStatus] = useState<Status>("idle");
  const [intentError, setIntentError] = useState<string>("");

  const [presetsResult, setPresetsResult] = useState<string>("{}");
  const [presetsStatus, setPresetsStatus] = useState<Status>("idle");
  const [presetsError, setPresetsError] = useState<string>("");

  const [decksResult, setDecksResult] = useState<string>("{}");
  const [decksStatus, setDecksStatus] = useState<Status>("idle");
  const [decksError, setDecksError] = useState<string>("");

  const [ingestResult, setIngestResult] = useState<string>("{}");
  const [ingestStatus, setIngestStatus] = useState<Status>("idle");
  const [ingestError, setIngestError] = useState<string>("");

  const [matchStrategy, setMatchStrategy] = useState<"heuristic" | "ismcts">("ismcts");
  const [matchTurns, setMatchTurns] = useState(12);
  const [matchTargetLore, setMatchTargetLore] = useState(8);
  const [matchIterations, setMatchIterations] = useState(64);

  const [decisionIterations, setDecisionIterations] = useState(96);
  const [decisionTargetLore, setDecisionTargetLore] = useState(8);
  const [decisionActivePlayer, setDecisionActivePlayer] = useState(1);
  const [decisionP1Lore, setDecisionP1Lore] = useState(2);
  const [decisionP2Lore, setDecisionP2Lore] = useState(3);

  const [intentStrict, setIntentStrict] = useState(true);
  const [intentDeckJson, setIntentDeckJson] = useState(
    pretty([
      { card_id: "song_hint", copies: 4, card_type: "Song", subtypes: ["Song"] },
      { card_id: "char_hint", copies: 4, card_type: "Character", cost: 3, strength: 2, willpower: 3, lore: 1 },
    ]),
  );

  const [presetName, setPresetName] = useState("aggro_song_ui");
  const [presetWeightsJson, setPresetWeightsJson] = useState(
    pretty({ tempo: 0.1, aggressive: 0.5, quester: 0.15, defender: 0.1, song: 0.15 }),
  );
  const [presetTags, setPresetTags] = useState("ladder,ui");

  const [deckCardsJson, setDeckCardsJson] = useState(
    pretty([
      { card_id: "card_1", copies: 4, colors: ["amber"] },
      { card_id: "card_2", copies: 4, colors: ["amber"] },
      { card_id: "card_3", copies: 4, colors: ["steel"] },
    ]),
  );

  const [ingestMode, setIngestMode] = useState<"source" | "lorcast" | "lorcanajson">("lorcanajson");
  const [ingestSourceUrl, setIngestSourceUrl] = useState("https://lorcanajson.org/files/current/en/allCards.json");
  const [lorcastQuery, setLorcastQuery] = useState("set:1");
  const [lorcanajsonLanguage, setLorcanajsonLanguage] = useState("en");
  const [lorcanajsonResource, setLorcanajsonResource] = useState<"all_cards" | "set">("all_cards");
  const [lorcanajsonSetCode, setLorcanajsonSetCode] = useState("1");

  const [simDeckP1Json, setSimDeckP1Json] = useState(
    pretty([{ card_id: "song_1", copies: 4, card_type: "Song", subtypes: ["Song"] }]),
  );
  const [simDeckP2Json, setSimDeckP2Json] = useState(
    pretty([{ card_id: "char_1", copies: 4, card_type: "Character", cost: 3, strength: 2, willpower: 3, lore: 1 }]),
  );

  const statusPill = useMemo(() => {
    if (health === "ok") return "border-[#3f7f63] bg-[#173726] text-[#9bf3c8]";
    if (health === "error") return "border-[#7a324a] bg-[#31141f] text-[#ffadbe]";
    if (health === "loading") return "border-[#6a5a2b] bg-[#2f2712] text-[#ffd88c]";
    return "border-[#38446e] bg-[#17203f] text-[#c8d3ff]";
  }, [health]);

  useEffect(() => {
    void checkHealth();
  }, []);

  async function checkHealth() {
    setHealth("loading");
    try {
      const data = await apiFetch<{ status: string }>("/health");
      setHealth("ok");
      setHealthDetail(`Backend online (${data.status})`);
    } catch (error) {
      setHealth("error");
      setHealthDetail((error as Error).message);
    }
  }

  function parseJsonOrThrow<T>(value: string, label: string): T {
    try {
      return JSON.parse(value) as T;
    } catch {
      throw new Error(`Invalid JSON in ${label}.`);
    }
  }

  async function submitMatch(e: FormEvent) {
    e.preventDefault();
    setSimStatus("loading");
    setSimError("");
    try {
      const player_one_deck = parseJsonOrThrow<object[]>(simDeckP1Json, "P1 deck");
      const player_two_deck = parseJsonOrThrow<object[]>(simDeckP2Json, "P2 deck");
      const data = await apiFetch("/simulate/match", {
        method: "POST",
        body: JSON.stringify({
          max_turns: matchTurns,
          target_lore: matchTargetLore,
          strategy: matchStrategy,
          ismcts_iterations: matchIterations,
          player_one_deck,
          player_two_deck,
        }),
      });
      setSimResult(pretty(data));
      setSimStatus("ok");
    } catch (error) {
      setSimStatus("error");
      setSimError((error as Error).message);
    }
  }

  async function submitDecision(e: FormEvent) {
    e.preventDefault();
    setDecisionStatus("loading");
    setDecisionError("");
    try {
      const data = await apiFetch("/simulate/decision", {
        method: "POST",
        body: JSON.stringify({
          target_lore: decisionTargetLore,
          active_player_id: decisionActivePlayer,
          player_one_lore: decisionP1Lore,
          player_two_lore: decisionP2Lore,
          ismcts_iterations: decisionIterations,
          observed_opponent_profile: "balanced",
          observed_turns: 4,
        }),
      });
      setDecisionResult(pretty(data));
      setDecisionStatus("ok");
    } catch (error) {
      setDecisionStatus("error");
      setDecisionError((error as Error).message);
    }
  }

  async function submitIntentProfile(e: FormEvent) {
    e.preventDefault();
    setIntentStatus("loading");
    setIntentError("");
    try {
      const deck = parseJsonOrThrow<object[]>(intentDeckJson, "Intent profile deck");
      const data = await apiFetch("/simulate/intent-profile", {
        method: "POST",
        body: JSON.stringify({ strict: intentStrict, deck }),
      });
      setIntentResult(pretty(data));
      setIntentStatus("ok");
    } catch (error) {
      setIntentStatus("error");
      setIntentError((error as Error).message);
    }
  }

  async function listPresets() {
    setPresetsStatus("loading");
    setPresetsError("");
    try {
      const data = await apiFetch("/simulate/intent-presets");
      setPresetsResult(pretty(data));
      setPresetsStatus("ok");
    } catch (error) {
      setPresetsStatus("error");
      setPresetsError((error as Error).message);
    }
  }

  async function upsertPreset(e: FormEvent) {
    e.preventDefault();
    setPresetsStatus("loading");
    setPresetsError("");
    try {
      const weights = parseJsonOrThrow<Record<string, number>>(presetWeightsJson, "Preset weights");
      const tags = presetTags
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);
      const data = await apiFetch("/simulate/intent-presets", {
        method: "POST",
        body: JSON.stringify({ name: presetName, weights, tags }),
      });
      setPresetsResult(pretty(data));
      setPresetsStatus("ok");
    } catch (error) {
      setPresetsStatus("error");
      setPresetsError((error as Error).message);
    }
  }

  async function runDeckValidation(mode: "validate" | "repair") {
    setDecksStatus("loading");
    setDecksError("");
    try {
      const cards = parseJsonOrThrow<object[]>(deckCardsJson, "Deck cards");
      const data = await apiFetch(`/decks/${mode}`, {
        method: "POST",
        body: JSON.stringify({ cards, strict_catalog: true }),
      });
      setDecksResult(pretty(data));
      setDecksStatus("ok");
    } catch (error) {
      setDecksStatus("error");
      setDecksError((error as Error).message);
    }
  }

  async function runIngestion(e: FormEvent) {
    e.preventDefault();
    setIngestStatus("loading");
    setIngestError("");
    try {
      let path = "/ingest/lorcana/lorcanajson";
      let payload: Record<string, unknown> = {};
      if (ingestMode === "source") {
        path = "/ingest/lorcana/source";
        payload = { url: ingestSourceUrl };
      } else if (ingestMode === "lorcast") {
        path = "/ingest/lorcana/lorcast";
        payload = { q: lorcastQuery, unique: "prints" };
      } else {
        payload = {
          language: lorcanajsonLanguage,
          resource: lorcanajsonResource,
          set_code: lorcanajsonResource === "set" ? lorcanajsonSetCode : undefined,
        };
      }
      const data = await apiFetch(path, { method: "POST", body: JSON.stringify(payload) });
      setIngestResult(pretty(data));
      setIngestStatus("ok");
    } catch (error) {
      setIngestStatus("error");
      setIngestError((error as Error).message);
    }
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,#1b2a57_0%,#0b0e1d_45%,#070810_100%)]">
      <div className="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
        <header className="surface mb-6 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="chip inline-flex px-3 py-1 text-xs font-semibold">Lorcana Control Center</p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight">Gambitho TCG Trainer UI</h1>
              <p className="subtle mt-1 max-w-3xl text-sm">
                Interfaz profesional para simulación, presets de intent, validación/reparación de mazos e ingesta de
                datos.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button className="btn btn-secondary" type="button" onClick={checkHealth}>
                Check Backend
              </button>
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusPill}`}>
                {healthDetail}
              </span>
            </div>
          </div>
        </header>

        <section className="surface mb-6 p-5">
          <div className="mb-4">
            <h2 className="panel-title text-xl">Catálogo de cartas</h2>
            <p className="subtle mt-1 text-sm">
              Arte oficial de Ravensburger — misma apariencia que las cartas físicas de Lorcana.
            </p>
          </div>
          <CardCatalog />
        </section>

        <main className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Panel title="Simulación de Match" subtitle="Corre una partida completa bot vs bot con estrategia configurable.">
            <form onSubmit={submitMatch} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <label className="text-sm">
                  Strategy
                  <select className="field mt-1" value={matchStrategy} onChange={(e) => setMatchStrategy(e.target.value as "heuristic" | "ismcts")}>
                    <option value="heuristic">heuristic</option>
                    <option value="ismcts">ismcts</option>
                  </select>
                </label>
                <label className="text-sm">
                  Iteraciones ISMCTS
                  <input className="field mt-1" type="number" value={matchIterations} onChange={(e) => setMatchIterations(Number(e.target.value))} />
                </label>
                <label className="text-sm">
                  Max Turns
                  <input className="field mt-1" type="number" value={matchTurns} onChange={(e) => setMatchTurns(Number(e.target.value))} />
                </label>
                <label className="text-sm">
                  Target Lore
                  <input className="field mt-1" type="number" value={matchTargetLore} onChange={(e) => setMatchTargetLore(Number(e.target.value))} />
                </label>
              </div>
              <label className="text-sm block">
                Deck P1 (JSON)
                <textarea className="field mt-1 h-24 font-mono text-xs" value={simDeckP1Json} onChange={(e) => setSimDeckP1Json(e.target.value)} />
              </label>
              <label className="text-sm block">
                Deck P2 (JSON)
                <textarea className="field mt-1 h-24 font-mono text-xs" value={simDeckP2Json} onChange={(e) => setSimDeckP2Json(e.target.value)} />
              </label>
              <div className="flex items-center gap-3">
                <button className="btn" type="submit" disabled={simStatus === "loading"}>
                  {simStatus === "loading" ? "Ejecutando..." : "Run Match"}
                </button>
                {simError ? <span className="text-sm text-[var(--error)]">{simError}</span> : null}
              </div>
              <pre className="json-block">{simResult}</pre>
            </form>
          </Panel>

          <Panel title="Explicación de Decisión" subtitle="Inspecciona la mejor acción raíz que elige ISMCTS en un estado dado.">
            <form onSubmit={submitDecision} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <label className="text-sm">
                  Active Player
                  <select className="field mt-1" value={decisionActivePlayer} onChange={(e) => setDecisionActivePlayer(Number(e.target.value))}>
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                  </select>
                </label>
                <label className="text-sm">
                  Iteraciones
                  <input className="field mt-1" type="number" value={decisionIterations} onChange={(e) => setDecisionIterations(Number(e.target.value))} />
                </label>
                <label className="text-sm">
                  P1 Lore
                  <input className="field mt-1" type="number" value={decisionP1Lore} onChange={(e) => setDecisionP1Lore(Number(e.target.value))} />
                </label>
                <label className="text-sm">
                  P2 Lore
                  <input className="field mt-1" type="number" value={decisionP2Lore} onChange={(e) => setDecisionP2Lore(Number(e.target.value))} />
                </label>
              </div>
              <button className="btn" type="submit" disabled={decisionStatus === "loading"}>
                {decisionStatus === "loading" ? "Calculando..." : "Explain Decision"}
              </button>
              {decisionError ? <p className="text-sm text-[var(--error)]">{decisionError}</p> : null}
              <pre className="json-block">{decisionResult}</pre>
            </form>
          </Panel>

          <Panel title="Intent Profile (Strict)" subtitle="Inferencia de pesos por deck y validación strict de hints estructurales.">
            <form onSubmit={submitIntentProfile} className="space-y-3">
              <label className="inline-flex items-center gap-2 text-sm">
                <input type="checkbox" checked={intentStrict} onChange={(e) => setIntentStrict(e.target.checked)} />
                strict
              </label>
              <textarea className="field h-32 font-mono text-xs" value={intentDeckJson} onChange={(e) => setIntentDeckJson(e.target.value)} />
              <button className="btn" type="submit" disabled={intentStatus === "loading"}>
                {intentStatus === "loading" ? "Infiriendo..." : "Infer Intent Profile"}
              </button>
              {intentError ? <p className="text-sm text-[var(--error)]">{intentError}</p> : null}
              <pre className="json-block">{intentResult}</pre>
            </form>
          </Panel>

          <Panel title="Intent Presets" subtitle="Crea, actualiza y consulta presets para experimentos comparativos.">
            <form onSubmit={upsertPreset} className="space-y-3">
              <label className="text-sm block">
                Preset Name
                <input className="field mt-1" value={presetName} onChange={(e) => setPresetName(e.target.value)} />
              </label>
              <label className="text-sm block">
                Weights JSON
                <textarea className="field mt-1 h-28 font-mono text-xs" value={presetWeightsJson} onChange={(e) => setPresetWeightsJson(e.target.value)} />
              </label>
              <label className="text-sm block">
                Tags (comma-separated)
                <input className="field mt-1" value={presetTags} onChange={(e) => setPresetTags(e.target.value)} />
              </label>
              <div className="flex gap-3">
                <button className="btn" type="submit" disabled={presetsStatus === "loading"}>
                  Upsert Preset
                </button>
                <button className="btn btn-secondary" type="button" onClick={listPresets} disabled={presetsStatus === "loading"}>
                  List Presets
                </button>
              </div>
              {presetsError ? <p className="text-sm text-[var(--error)]">{presetsError}</p> : null}
              <pre className="json-block">{presetsResult}</pre>
            </form>
          </Panel>

          <Panel title="Deck Tools" subtitle="Valida y repara mazos usando reglas del linter Lorcana.">
            <div className="space-y-3">
              <textarea className="field h-32 font-mono text-xs" value={deckCardsJson} onChange={(e) => setDeckCardsJson(e.target.value)} />
              <div className="flex gap-3">
                <button className="btn" type="button" onClick={() => void runDeckValidation("validate")} disabled={decksStatus === "loading"}>
                  Validate
                </button>
                <button className="btn btn-secondary" type="button" onClick={() => void runDeckValidation("repair")} disabled={decksStatus === "loading"}>
                  Repair
                </button>
              </div>
              {decksError ? <p className="text-sm text-[var(--error)]">{decksError}</p> : null}
              <pre className="json-block">{decksResult}</pre>
            </div>
          </Panel>

          <Panel title="Ingestion Hub" subtitle="Carga cartas desde LorcanaJSON, Lorcast o una URL de fuente externa.">
            <form onSubmit={runIngestion} className="space-y-3">
              <label className="text-sm block">
                Ingest Mode
                <select className="field mt-1" value={ingestMode} onChange={(e) => setIngestMode(e.target.value as "source" | "lorcast" | "lorcanajson")}>
                  <option value="lorcanajson">lorcanajson</option>
                  <option value="lorcast">lorcast</option>
                  <option value="source">source url</option>
                </select>
              </label>

              {ingestMode === "source" ? (
                <label className="text-sm block">
                  Source URL
                  <input className="field mt-1" value={ingestSourceUrl} onChange={(e) => setIngestSourceUrl(e.target.value)} />
                </label>
              ) : null}

              {ingestMode === "lorcast" ? (
                <label className="text-sm block">
                  Lorcast Query
                  <input className="field mt-1" value={lorcastQuery} onChange={(e) => setLorcastQuery(e.target.value)} />
                </label>
              ) : null}

              {ingestMode === "lorcanajson" ? (
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm">
                    Language
                    <select className="field mt-1" value={lorcanajsonLanguage} onChange={(e) => setLorcanajsonLanguage(e.target.value)}>
                      <option value="en">en</option>
                      <option value="fr">fr</option>
                      <option value="de">de</option>
                      <option value="it">it</option>
                    </select>
                  </label>
                  <label className="text-sm">
                    Resource
                    <select className="field mt-1" value={lorcanajsonResource} onChange={(e) => setLorcanajsonResource(e.target.value as "all_cards" | "set")}>
                      <option value="all_cards">all_cards</option>
                      <option value="set">set</option>
                    </select>
                  </label>
                  {lorcanajsonResource === "set" ? (
                    <label className="text-sm col-span-2">
                      Set code
                      <input className="field mt-1" value={lorcanajsonSetCode} onChange={(e) => setLorcanajsonSetCode(e.target.value)} />
                    </label>
                  ) : null}
                </div>
              ) : null}

              <button className="btn" type="submit" disabled={ingestStatus === "loading"}>
                {ingestStatus === "loading" ? "Ingesting..." : "Run Ingestion"}
              </button>
              {ingestError ? <p className="text-sm text-[var(--error)]">{ingestError}</p> : null}
              <pre className="json-block">{ingestResult}</pre>
            </form>
          </Panel>
        </main>
      </div>
    </div>
  );
}
