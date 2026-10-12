"""Fail unless each path is a CycloneDX JSON document with components.

Usage: python tools/check_cyclonedx.py sbom/one.cdx.json sbom/two.cdx.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(paths: list[str]) -> int:
    if not paths:
        print("No SBOM paths given.", file=sys.stderr)
        return 1
    failed = False
    for raw in paths:
        path = Path(raw)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            failed = True
            continue
        components = document.get("components") or []
        if document.get("bomFormat") != "CycloneDX" or not components:
            print(
                f"{path}: bomFormat={document.get('bomFormat')!r} "
                f"components={len(components)}",
                file=sys.stderr,
            )
            failed = True
            continue
        print(f"{path}: {len(components)} components")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
