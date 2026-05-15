"use client";

import { useCallback, useEffect, useState } from "react";

import { LorcanaCard, type LorcanaCardData } from "@/components/lorcana-card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type CatalogListResponse = {
  total: number;
  limit: number;
  offset: number;
  cards: LorcanaCardData[];
};

type CardCatalogProps = {
  onSelectCard?: (card: LorcanaCardData) => void;
};

export function CardCatalog({ onSelectCard }: CardCatalogProps) {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [cards, setCards] = useState<LorcanaCardData[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<LorcanaCardData | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState("");

  const limit = 24;

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const loadCards = useCallback(async (nextOffset: number, term: string) => {
    setStatus("loading");
    setError("");
    try {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(nextOffset),
      });
      if (term) {
        params.set("search", term);
      }
      const response = await fetch(`${API_BASE_URL}/catalog/cards?${params.toString()}`);
      const payload = (await response.json()) as CatalogListResponse | { detail?: string };
      if (!response.ok) {
        const detail = typeof payload === "object" && payload && "detail" in payload ? payload.detail : "Error";
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      const data = payload as CatalogListResponse;
      setCards(data.cards);
      setTotal(data.total);
      setOffset(data.offset);
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    void loadCards(0, debouncedSearch);
  }, [debouncedSearch, loadCards]);

  function handleSelect(card: LorcanaCardData) {
    setSelected(card);
    onSelectCard?.(card);
  }

  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[240px] flex-1 text-sm">
          Buscar carta
          <input
            className="field mt-1"
            placeholder="Nombre o ID (ej. Ariel, 1)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <p className="subtle text-sm">
          {total.toLocaleString()} cartas · vista oficial Ravensburger
        </p>
      </div>

      {error ? <p className="text-sm text-[var(--error)]">{error}</p> : null}

      <div className="flex flex-wrap gap-4">
        {cards.map((card, index) => (
          <button
            key={card.id}
            type="button"
            className={`text-left transition ${selected?.id === card.id ? "ring-2 ring-[#9e7bff] rounded-xl" : ""}`}
            onClick={() => handleSelect(card)}
          >
            <LorcanaCard card={card} size="md" priority={index < 8} />
          </button>
        ))}
        {status === "loading" && cards.length === 0 ? (
          <p className="subtle text-sm">Cargando cartas...</p>
        ) : null}
        {status !== "loading" && cards.length === 0 ? (
          <p className="subtle text-sm">No hay resultados. Prueba otro nombre.</p>
        ) : null}
      </div>

      <div className="flex items-center gap-3">
        <button
          className="btn btn-secondary"
          type="button"
          disabled={!canPrev || status === "loading"}
          onClick={() => void loadCards(Math.max(0, offset - limit), debouncedSearch)}
        >
          Anterior
        </button>
        <span className="subtle text-sm">
          {Math.min(offset + 1, total)}–{Math.min(offset + limit, total)} de {total}
        </span>
        <button
          className="btn btn-secondary"
          type="button"
          disabled={!canNext || status === "loading"}
          onClick={() => void loadCards(offset + limit, debouncedSearch)}
        >
          Siguiente
        </button>
      </div>

      {selected && (selected.image_url || selected.image_thumbnail_url) ? (
        <div className="catalog-preview surface p-4">
          <p className="subtle mb-3 text-sm">Vista ampliada (arte oficial de carta física)</p>
          <div className="flex flex-wrap items-start gap-6">
            <LorcanaCard card={selected} size="lg" showMeta={false} priority />
            <div className="min-w-[200px] flex-1 space-y-1 text-sm">
              <p className="text-lg font-semibold">{selected.name}</p>
              {selected.subtitle ? <p className="subtle">{selected.subtitle}</p> : null}
              <p className="subtle">
                ID {selected.id} · Set {selected.set_id} · #{selected.collector_number}
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
