"""Stage the local corpus in Bedrock's S3 sidecar metadata format."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "corpus"
DESTINATION = ROOT / ".cloud" / "corpus"


def _attribute(value):
    if isinstance(value, bool):
        typed = {"type": "BOOLEAN", "booleanValue": value}
    elif isinstance(value, (int, float)):
        typed = {"type": "NUMBER", "numberValue": value}
    elif isinstance(value, list):
        typed = {"type": "STRING_LIST", "stringListValue": [str(item) for item in value]}
    else:
        typed = {"type": "STRING", "stringValue": str(value)}
    return {"value": typed, "includeForEmbedding": True}


def main() -> None:
    """Copy Markdown and convert every sibling ``.meta.json`` sidecar."""
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    for document in SOURCE.rglob("*.md"):
        relative = document.relative_to(SOURCE)
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(document, target)
        local_meta = document.with_suffix(".meta.json")
        if local_meta.exists():
            raw = json.loads(local_meta.read_text())
            sidecar = {"metadataAttributes": {key: _attribute(value) for key, value in raw.items()}}
            target.with_name(target.name + ".metadata.json").write_text(
                json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n"
            )
    print(f"staged {len(list(DESTINATION.rglob('*.md')))} documents in {DESTINATION}")


if __name__ == "__main__":
    main()
