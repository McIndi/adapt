"""Fail unless each path is a CycloneDX JSON document with package components.

A component of type "file" does not count. Syft records archive members as
files, and that list can be non-empty when no package was cataloged.

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
        packages = [item for item in components if item.get("type") != "file"]
        if document.get("bomFormat") != "CycloneDX" or not packages:
            print(
                f"{path}: bomFormat={document.get('bomFormat')!r} "
                f"packages={len(packages)} components={len(components)}",
                file=sys.stderr,
            )
            failed = True
            continue
        print(f"{path}: {len(packages)} packages")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
