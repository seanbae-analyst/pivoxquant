"""registry/ 디렉터리 읽기."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import Control, Document, SchemaError

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "registry"
SNAPSHOT_DIR = ROOT / "snapshots"
OUT_DIR = ROOT / "out"


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_controls(registry_dir: Path = REGISTRY_DIR) -> list[Control]:
    data = _load_yaml(registry_dir / "controls.yaml")
    controls = [Control.from_dict(c) for c in data["controls"]]
    nums = [c.num for c in controls]
    if nums != sorted(nums) or len(set(nums)) != len(nums):
        raise SchemaError("controls.yaml: num 은 중복 없이 오름차순")
    return controls


def load_documents(registry_dir: Path = REGISTRY_DIR) -> dict[str, Document]:
    docs: dict[str, Document] = {}
    for path in sorted((registry_dir / "documents").glob("*.yaml")):
        d = _load_yaml(path)
        if not isinstance(d, dict):
            raise SchemaError(f"{path.name}: 최상위는 매핑이어야 함")
        doc = Document.from_dict(d)
        if doc.id != path.stem:
            raise SchemaError(f"{path.name}: id {doc.id!r} 가 파일 이름과 다름")
        if doc.id in docs:
            raise SchemaError(f"중복 id {doc.id}")
        docs[doc.id] = doc
    for doc in docs.values():
        for r in doc.related:
            if r not in docs:
                raise SchemaError(f"{doc.id}: related 에 없는 문서 {r}")
    return docs


def load_codings(registry_dir: Path = REGISTRY_DIR) -> dict[str, dict[str, Any]]:
    """코더 이름 → 코딩 파일. TEMPLATE 은 건너뛴다."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((registry_dir / "codings").glob("*.yaml")):
        if path.stem.upper() == "TEMPLATE":
            continue
        data = _load_yaml(path)
        out[path.stem] = data
    return out


def load_sources(registry_dir: Path = REGISTRY_DIR) -> list[dict[str, Any]]:
    data = _load_yaml(registry_dir / "sources.yaml")
    return list(data["sources"])
