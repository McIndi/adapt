"""Checks for the CycloneDX producers used by the package-sbom job."""

import json
import subprocess
import sys
from pathlib import Path


def test_chart_cyclonedx_lists_default_images(tmp_path):
    document = _chart_document(Path("charts/adapt"), tmp_path / "chart.cdx.json")
    assert document["metadata"]["component"]["name"] == "adapt"
    assert document["metadata"]["component"]["version"] == "0.5.2"
    refs = {(item["name"], item["version"]) for item in document["components"]}
    assert ("ghcr.io/mcindi/adapt-server", "0.5.2") in refs
    assert ("curlimages/curl", "8.9.1") in refs
    assert _check_accepts(document, tmp_path / "checked.cdx.json")


def test_chart_cyclonedx_prefers_digest_and_keeps_literal_images(tmp_path):
    chart = tmp_path / "demo"
    (chart / "templates").mkdir(parents=True)
    (chart / "Chart.yaml").write_text(
        'name: demo\nversion: 1.2.3\nappVersion: "9.9.9"\n',
        encoding="utf-8",
    )
    (chart / "values.yaml").write_text(
        'image:\n  repository: ghcr.io/example/demo\n  tag: ""\n  digest: sha256:abc\n',
        encoding="utf-8",
    )
    (chart / "templates" / "deploy.yaml").write_text(
        'image: example/sidecar:1\nimage: {{ include "adapt.image" . }}\n',
        encoding="utf-8",
    )
    document = _chart_document(chart, tmp_path / "demo.cdx.json")
    refs = {(item["name"], item["version"]) for item in document["components"]}
    assert ("ghcr.io/example/demo", "sha256:abc") in refs
    assert ("example/sidecar", "1") in refs
    assert all("include" not in item["name"] for item in document["components"])


def test_check_rejects_documents_with_only_file_components(tmp_path):
    path = tmp_path / "files.cdx.json"
    path.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "components": [{"type": "file", "name": "archive-member"}],
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "tools/check_cyclonedx.py", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "packages=0" in result.stderr


def _chart_document(chart_dir: Path, output: Path) -> dict:
    subprocess.check_call(
        [sys.executable, "tools/chart_cyclonedx.py", str(chart_dir), str(output)]
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _check_accepts(document: dict, output: Path) -> bool:
    output.write_text(json.dumps(document), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "tools/check_cyclonedx.py", str(output)],
        check=False,
    )
    return result.returncode == 0
