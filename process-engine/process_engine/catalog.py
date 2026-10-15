"""Versioned filesystem catalog for process definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from process_engine.schema import ProcessDefinition, validate_process_dict


class ProcessNotFound(KeyError):
    """Raised when id/version is missing from the catalog."""


def default_catalog_root() -> Path:
    """Bundled catalog shipped with the package."""
    return Path(__file__).resolve().parent / "catalog"


def load_process(path: Path | str) -> ProcessDefinition:
    """Load and validate a single process JSON file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"process file must be a JSON object: {path}")
    return validate_process_dict(raw)


class ProcessCatalog:
    """In-memory index over versioned process JSON files.

    Layout (filesystem stub)::

        catalog/
          standard_client_reply/
            1.json          # version "1"
            1.1.0.json      # optional newer version

    Filenames (without .json) are the version string. The JSON body's
    ``id`` / ``version`` must match the folder name / filename.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else default_catalog_root()
        self._by_key: Dict[str, ProcessDefinition] = {}
        self._latest: Dict[str, ProcessDefinition] = {}
        self.reload()

    def reload(self) -> None:
        by_key: Dict[str, ProcessDefinition] = {}
        by_id: Dict[str, List[ProcessDefinition]] = {}
        if not self.root.is_dir():
            self._by_key = {}
            self._latest = {}
            return

        for process_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for path in sorted(process_dir.glob("*.json")):
                definition = load_process(path)
                if definition.id != process_dir.name:
                    raise ValueError(
                        f"{path}: id {definition.id!r} does not match folder {process_dir.name!r}"
                    )
                if definition.version != path.stem:
                    raise ValueError(
                        f"{path}: version {definition.version!r} does not match filename stem"
                    )
                key = definition.catalog_key()
                if key in by_key:
                    raise ValueError(f"duplicate catalog key {key}")
                by_key[key] = definition
                by_id.setdefault(definition.id, []).append(definition)

        latest: Dict[str, ProcessDefinition] = {}
        for pid, versions in by_id.items():
            latest[pid] = _pick_latest(versions)

        self._by_key = by_key
        self._latest = latest

    def list_processes(
        self,
        *,
        tenant_id: Optional[str] = None,
        latest_only: bool = True,
    ) -> List[ProcessDefinition]:
        """Return catalog entries, optionally filtered by tenant.

        Shared templates (tenant_id=None) are always included. When
        ``tenant_id`` is set, tenant-specific definitions for that tenant
        are included as well.
        """
        source: Iterable[ProcessDefinition]
        if latest_only:
            source = self._latest.values()
        else:
            source = self._by_key.values()

        out: List[ProcessDefinition] = []
        for definition in source:
            if definition.tenant_id is None:
                out.append(definition)
            elif tenant_id is not None and definition.tenant_id == tenant_id:
                out.append(definition)
        return sorted(out, key=lambda d: (d.id, d.version))

    def get(
        self,
        process_id: str,
        version: Optional[str] = None,
    ) -> ProcessDefinition:
        if version is None:
            if process_id not in self._latest:
                raise ProcessNotFound(process_id)
            return self._latest[process_id]
        key = f"{process_id}@{version}"
        if key not in self._by_key:
            raise ProcessNotFound(key)
        return self._by_key[key]

    def keys(self) -> List[str]:
        return sorted(self._by_key.keys())


def _pick_latest(versions: List[ProcessDefinition]) -> ProcessDefinition:
    """Prefer higher semver-like tuples; fall back to string compare."""

    def sort_key(d: ProcessDefinition) -> Tuple:
        parts = d.version.split(".")
        nums: List[int] = []
        for part in parts:
            if part.isdigit():
                nums.append(int(part))
            else:
                return (0, d.version)
        return (1, *nums)

    return sorted(versions, key=sort_key)[-1]
