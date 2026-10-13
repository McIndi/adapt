# Supply-chain evidence

Checked against the published `0.5.2` artifacts on 2026-10-12. Producer steps
and consumer commands for later releases are in `RELEASING.md`.

## Inventory of 0.5.2

| Artifact | What is already attached | What is missing |
|---|---|---|
| PyPI wheel `adapt_server-0.5.2-py3-none-any.whl` | PEP 740 publish attestation. Sigstore certificate, GitHub OIDC, workflow `publish-pypi.yml` at `refs/tags/v0.5.2`. Predicate `https://docs.pypi.org/attestations/publish/v1`. Wheel sha256 `9c4177c438d7f0cbd5c8c8ecdde3826943511baf6ef5a59143ef53ab66975061`. `has_sig` is false (no detached GPG signature). | A dependency SBOM. No second signature. |
| PyPI sdist `adapt_server-0.5.2.tar.gz` | The same PEP 740 publish attestation from `publish-pypi.yml`. | A dependency SBOM. No second signature. |
| Image index `ghcr.io/mcindi/adapt-server:0.5.2` (`sha256:39accc4e605febb0c5ce801ef79a137bd51cdc3a4032d07e7a680fae6a34eab8`) | SLSA provenance v1 attestations from BuildKit for `linux/amd64` and `linux/arm64`. The amd64 statement records base image `python:3.14-slim` digest `sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6`. | An SBOM attestation. A keyless Cosign signature (the `sha256-….sig` tag is absent). |
| Chart `oci://ghcr.io/mcindi/charts/adapt:0.5.2` (`sha256:ee973207dbea9ef8618f045c2ff33896c35f257f1b5912eec4e10a9324053e17`) | Helm OCI manifest and chart layer only. | SBOM, signature, and provenance. |

PyPI Trusted Publishing already signs the distributions. This repository does
not add a second PyPI signing mechanism. The gap on PyPI is the SBOM, which
the GitHub Release carries from the next application release onward.

## Evidence each publish workflow adds

| Artifact | SBOM | Signature or attestation | Identity |
|---|---|---|---|
| PyPI wheel and sdist | CycloneDX JSON on the GitHub Release (`adapt_server-<version>.whl.cdx.json` and `adapt_server-<version>.tar.gz.cdx.json`), attested with `actions/attest` | Existing PEP 740 attestation only | `publish-pypi.yml` via GitHub OIDC |
| Container image | SPDX attestation attached by Buildx (`sbom: true`) plus the existing SLSA provenance (`provenance: mode=max`) | Keyless Cosign signature of the image index | `publish-image.yml` via GitHub OIDC |
| Helm chart | CycloneDX JSON attested with `cosign attest --type cyclonedx` | Keyless Cosign signature of the chart OCI tag | `publish-chart.yml` via GitHub OIDC |

`publish-image.yml` and `publish-chart.yml` still wait for the Test workflow.
The chart workflow also waits for Helm CI. New actions are pinned to commit
SHAs: `anchore/sbom-action` v0.24.3, `sigstore/cosign-installer` v4.1.2
(Cosign v3.1.3), and `actions/attest` v4.1.0. Syft is pinned to v1.54.1.

Syft 1.54.1 does not open a `.whl`, and it does not catalog a Helm chart.
The wheel and sdist jobs unpack the archive and add the locked runtime
requirements. Syft then lists those packages. The chart job writes its own
CycloneDX document with `tools/chart_cyclonedx.py`. That document lists the
chart and the container images it installs.

Pull requests run these same producers in the `package-sbom` job. They do not
sign or publish.

## Review Gate 3

The inventory above is the checked-in record for `0.5.2`. The new producer
steps run on the next `v*` release and the next `chart-v*` tag. Gate 3 stays
open until those public artifacts verify with the commands in `RELEASING.md`.
