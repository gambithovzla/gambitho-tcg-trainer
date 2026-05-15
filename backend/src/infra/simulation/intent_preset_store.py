from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.engine.fsm import GameEngineFSM


@dataclass(frozen=True)
class IntentPreset:
    name: str
    weights: dict[str, float]
    tags: list[str] | None = None
    updated_at: str | None = None
    created_at: str | None = None
    version: int | None = None
    history: list[dict] | None = None


class IntentPresetStore:
    """
    Small JSON-file-backed store for reusable intent-weight presets.
    """

    def __init__(self, file_path: str | None = None) -> None:
        default_path = Path(__file__).resolve().parents[3] / "data" / "intent_presets.json"
        configured = file_path or os.getenv("INTENT_PRESETS_PATH")
        self._path = Path(configured) if configured else default_path

    def list_presets(self) -> dict[str, IntentPreset]:
        payload = self._read_all()
        presets_raw = payload.get("presets", {})
        out: dict[str, IntentPreset] = {}
        for name, raw in presets_raw.items():
            if not isinstance(name, str):
                continue
            weights, tags, updated_at, created_at, version, history = self._coerce_preset_value(raw)
            out[name] = IntentPreset(
                name=name,
                weights=GameEngineFSM._normalize_intent_weights(weights),
                tags=tags,
                updated_at=updated_at,
                created_at=created_at,
                version=version,
                history=history,
            )
        return out

    def get_preset(self, name: str) -> IntentPreset | None:
        presets = self.list_presets()
        return presets.get(name)

    def upsert_preset(
        self,
        name: str,
        weights: dict[str, float],
        tags: list[str] | None = None,
    ) -> IntentPreset:
        normalized = GameEngineFSM._normalize_intent_weights(weights)
        payload = self._read_all()
        presets = payload.setdefault("presets", {})
        if not isinstance(presets, dict):
            presets = {}
            payload["presets"] = presets

        existing = presets.get(name)
        _, existing_tags, existing_updated_at, existing_created_at, existing_version, existing_history = self._coerce_preset_value(
            existing
        )
        _ = existing_updated_at
        updated_at = datetime.now(timezone.utc).isoformat()
        created_at = existing_created_at or updated_at
        version = max(1, (existing_version or 0) + 1)
        normalized_tags = self._normalize_tags(tags if tags is not None else existing_tags)
        history = list(existing_history or [])
        history.append(
            {
                "version": version,
                "updated_at": updated_at,
                "weights": normalized,
                "tags": normalized_tags,
            }
        )
        presets[name] = {
            "weights": normalized,
            "tags": normalized_tags,
            "updated_at": updated_at,
            "created_at": created_at,
            "version": version,
            "history": history,
        }
        self._write_all(payload)
        return IntentPreset(
            name=name,
            weights=normalized,
            tags=normalized_tags,
            updated_at=updated_at,
            created_at=created_at,
            version=version,
            history=history,
        )

    def patch_preset(
        self,
        name: str,
        partial_weights: dict[str, float] | None = None,
        tags: list[str] | None = None,
    ) -> IntentPreset | None:
        existing = self.get_preset(name)
        if existing is None:
            return None
        merged = dict(existing.weights)
        if partial_weights:
            for key, value in partial_weights.items():
                if key in GameEngineFSM.INTENT_KEYS:
                    try:
                        merged[key] = float(value)
                    except (TypeError, ValueError):
                        continue
        merged_tags = tags if tags is not None else existing.tags
        return self.upsert_preset(name, merged, tags=merged_tags)

    def delete_preset(self, name: str) -> bool:
        payload = self._read_all()
        presets = payload.get("presets")
        if not isinstance(presets, dict):
            return False
        if name not in presets:
            return False
        del presets[name]
        payload["presets"] = presets
        self._write_all(payload)
        return True

    def get_preset_history(self, name: str) -> list[dict]:
        preset = self.get_preset(name)
        if preset is None or not preset.history:
            return []
        return list(preset.history)

    def _read_all(self) -> dict:
        if not self._path.exists():
            return {"presets": {}}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"presets": {}}

    def _write_all(self, payload: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _coerce_preset_value(
        raw: object,
    ) -> tuple[dict[str, float], list[str] | None, str | None, str | None, int | None, list[dict] | None]:
        # Backwards compatible with old format: value is directly a weights dict.
        if isinstance(raw, dict):
            if "weights" in raw and isinstance(raw.get("weights"), dict):
                version_raw = raw.get("version")
                version = int(version_raw) if isinstance(version_raw, int) else None
                history_raw = raw.get("history")
                history: list[dict] | None = None
                if isinstance(history_raw, list):
                    history = [entry for entry in history_raw if isinstance(entry, dict)]
                tags = IntentPresetStore._normalize_tags(raw.get("tags"))
                return (
                    raw["weights"],
                    tags,
                    str(raw.get("updated_at")) if raw.get("updated_at") else None,
                    str(raw.get("created_at")) if raw.get("created_at") else None,
                    version,
                    history,
                )
            return raw, None, None, None, None, None
        return {}, None, None, None, None, None

    @staticmethod
    def _normalize_tags(raw: object) -> list[str]:
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            cleaned = item.strip().lower()
            if not cleaned:
                continue
            if cleaned not in out:
                out.append(cleaned)
        return out
