"""Write a CycloneDX document for a Helm chart directory.

Syft 1.54 does not catalog Helm charts. This chart also has no subchart
dependencies, so a Syft scan of the packaged chart has no components.
The document lists the chart and the container images it installs: the
default application image from values.yaml, plus literal images in templates.

Usage: python tools/chart_cyclonedx.py charts/adapt sbom/chart.cdx.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


_IMAGE_LINE = re.compile(r"^\s*image:\s*(\S+)\s*$")


def _unquote(value: str) -> str:
    value = value.split("#", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _top_scalars(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0] in " \t#" or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        values[key.strip()] = _unquote(raw)
    return values


def _nested_block(text: str, block: str) -> dict[str, str]:
    values: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        if not inside:
            if line.startswith(f"{block}:"):
                inside = True
            continue
        if line and not line[0].isspace():
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, raw = stripped.partition(":")
        values[key.strip()] = _unquote(raw)
    return values


def _image_ref(repository: str, tag: str, digest: str, app_version: str) -> str:
    if digest and tag:
        raise SystemExit("Set image.digest or image.tag, not both.")
    if not repository:
        raise SystemExit("image.repository is required.")
    if digest:
        return f"{repository}@{digest}"
    return f"{repository}:{tag or app_version}"


def _split_ref(ref: str) -> dict[str, str]:
    if "@" in ref:
        name, version = ref.split("@", 1)
    elif ":" in ref:
        name, version = ref.rsplit(":", 1)
    else:
        name, version = ref, ""
    component = {"type": "container", "name": name}
    if version:
        component["version"] = version
    return component


def _literal_images(chart_dir: Path) -> set[str]:
    refs: set[str] = set()
    templates = chart_dir / "templates"
    if not templates.is_dir():
        return refs
    for path in templates.rglob("*"):
        if path.suffix not in {".yaml", ".yml", ".tpl"}:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _IMAGE_LINE.match(line)
            if match is None or "{{" in match.group(1):
                continue
            refs.add(_unquote(match.group(1)))
    return refs


def document_for_chart(chart_dir: Path) -> dict:
    chart = _top_scalars((chart_dir / "Chart.yaml").read_text(encoding="utf-8"))
    image = _nested_block((chart_dir / "values.yaml").read_text(encoding="utf-8"), "image")
    missing = [key for key in ("name", "version", "appVersion") if not chart.get(key)]
    if missing:
        raise SystemExit(f"Chart.yaml is missing {', '.join(missing)}.")
    refs = {
        _image_ref(
            image.get("repository", ""),
            image.get("tag", ""),
            image.get("digest", ""),
            chart["appVersion"],
        )
    }
    refs.update(_literal_images(chart_dir))
    components = [_split_ref(ref) for ref in sorted(refs)]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": chart["name"],
                "version": chart["version"],
            }
        },
        "components": components,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "Usage: python tools/chart_cyclonedx.py CHART_DIR OUTPUT.json",
            file=sys.stderr,
        )
        return 1
    chart_dir = Path(argv[1])
    output = Path(argv[2])
    document = document_for_chart(chart_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"{output}: {len(document['components'])} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
