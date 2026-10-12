# Adapt Hardening Plan

Status: Active — Phase 3 producer steps are in the workflows. Review Gate 3
waits on the next public release. Phase 4 checks run on pull requests.
Created: 2026-09-03
Updated: 2026-10-12

This plan replaces the completed container and Helm cleanup plan. The full
record of that work is in
[`archive/CONTAINER_OCI_HELM_CLEANUP_PLAN_2026-09-02.md`](archive/CONTAINER_OCI_HELM_CLEANUP_PLAN_2026-09-02.md).

## Goal

Close the remaining deployment, supply-chain, quality, and data gaps in
priority order. Do not start a later phase until the current review gate
passes.

The phases are grouped into these milestones:

| Milestone | Phases | Outcome |
|---|---:|---|
| M2 — Coordinated 0.5.2 release | 1 | Application, image, and chart `0.5.2` publish with aligned metadata and a digest-pinnable image reference. |
| M3 — Dependency and supply-chain hardening | 2–3 | Automated updates, a pinned base image, artifact inventories, SBOMs, signatures, and verification instructions are in place. |
| M4 — Quality visibility | 4 | Python lint and test coverage run in CI with an agreed baseline. |
| M5 — Schema migrations and backup restore | 5 | Schema changes use versioned migrations. A backup and restore path has been exercised. |

## Working rules

- Complete phases in order.
- Keep each phase in one focused change set when practical.
- Update `PROJECT_STATUS.md`, `MILESTONES.md`, and user documentation in the
  same phase as the related implementation.
- Run the listed checks and record the evidence before requesting review.
- Stop at each review gate. Do not start the next phase until the gate passes.
- A later unscheduled item can close as `N/A` when its decision gate finds no
  real requirement. Record the reason instead of building speculative features.

## Phase 1 — Coordinated application and chart release

Milestone: M2

### Goal

Remove the known release-name failure. Publish application, image, and chart
version `0.5.2` with aligned metadata.

### Scope

- Set `enableServiceLinks: false` on the server Deployment and the bootstrap
  Job. This prevents the Service named `adapt` from injecting an `ADAPT_PORT`
  value that conflicts with Adapt configuration.
- Add Helm unit tests for both pod specifications.
- Run the kind smoke test with the exact Helm release name `adapt` and verify
  that the pod becomes ready and `/health` returns HTTP 200.
- Add `image.digest` to values, schema, templates, tests, and documentation.
  When set, render `repository@digest` without a tag.
- Set the application version to `0.5.2` in `pyproject.toml` and
  `adapt/__init__.py`.
- Set both `version` and `appVersion` to `0.5.2` in
  `charts/adapt/Chart.yaml` for the stable release.
- Keep the application and chart tag types separate. Use `v0.5.2` for the
  application release and `chart-v0.5.2` for the chart release.
- Publish the `0.5.2` Python package and container image before the chart. This
  order makes the chart default image available during chart verification.
- Add the upload threat surface to `docs/manual/security.md`: path traversal,
  content-type or MIME confusion, file-size limits, and authorization.
- Update `RELEASING.md` with the coordinated release order.
- Publish and test chart `0.5.2-rc.1` with `appVersion: "0.5.2"` before the
  stable chart.
- After stable verification, remove the temporary warning that tells users not
  to use `adapt` as the release name.

### Verification

- `helm lint charts/adapt`
- `helm unittest charts/adapt`
- `bash tools/test-helm-schema.sh`
- The supported kind matrix passes, including an install named `adapt`.
- `helm template` tests cover image tag and digest rendering.
- The application version command and package metadata report `0.5.2`.
- The published `0.5.2` container image supports both target architectures.
- `mkdocs build --strict`
- A clean environment can anonymously pull and install the release candidate.
- The clean-environment installation passes for stable chart `0.5.2`.

### Review Gate 1

Passed 2026-09-08.

- The bare `adapt` release name no longer causes a crash loop.
- Tag and digest image modes both render valid, exclusive image references.
- The package, image, chart `version`, and chart `appVersion` are `0.5.2`.
- Tags `v0.5.2` and `chart-v0.5.2` published the matching artifacts.
- The security manual covers uploads.
- Chart `0.5.2-rc.1` was skipped. Stable chart `0.5.2` passed an anonymous
  `helm show`/`helm install adapt` on the Vagrant VM (`kind` 1.37.0).
  `/health` returned HTTP 200 with `"version":"0.5.2"`.

## Phase 2 — Dependency automation and base-image pinning

Milestone: M3

### Goal

Keep dependencies current and make the Docker base image input reproducible.

### Scope

- Add `.github/dependabot.yml` for `pip`, `github-actions`, and `docker`.
- Use a weekly schedule, grouped updates where useful, and a conservative open
  pull-request limit.
- Pin the Python base image by tag and multi-platform manifest digest.
- Keep the human-readable Python version in the `FROM` line.
- Document how and when the digest is refreshed.
- Let dependency-update pull requests handle routine action runtime updates.
  Do not mix unrelated upgrades into the initial configuration change.

### Validation

- Dependabot accepts all three package ecosystems after the branch is pushed.
- The image builds for `linux/amd64` and `linux/arm64` in the existing publish
  workflow.
- The pinned base still reports Python 3.14 and passes the image smoke check.
- Documentation identifies both the tag and digest update process.

### Review Gate 2

Passed 2026-09-10.

- Dependabot ran `pip`, `github-actions`, and `docker` on `main`.
- GitHub Actions group PR #1 merged. All Test and Helm CI checks on that PR
  passed.
- The `pip` group PR #2 was closed. It raised `mcp` to 2.x and mixed docs
  majors. That is not required to close this gate.
- Docker opened no PR. The pinned `python:3.14-slim` index digest was current.
- Helm CI on `main` built the image and checked Python 3.14. Dual-arch
  remains the existing publish workflow.

## Phase 3 — Artifact SBOMs, provenance, and signing

Milestone: M3

### Goal

Give consumers verifiable evidence for every published artifact without
duplicating evidence that the registries already produce.

### Scope

- Inventory the evidence currently attached to the PyPI wheel and source
  archive, the GHCR image, and the OCI chart.
- Record the existing PyPI Trusted Publishing attestations before choosing any
  new signing step.
- Define the required SBOM format, signature or attestation type, identity, and
  verification command for each artifact type.
- Generate SBOMs for the Python distributions, container image, and chart.
- Add missing image and chart signatures or attestations with keyless CI
  identity where the registry and tooling support it.
- Avoid a second PyPI signing mechanism unless the inventory finds a real gap.
- Apply least-privilege workflow permissions and pin any new CI actions.
- Update `RELEASING.md` with producer checks and consumer verification commands.

### Validation

- Build one release candidate through each publish workflow.
- Download or pull every artifact from its public registry.
- Verify its identity, signature or provenance, and SBOM from a clean
  environment with the documented commands.
- Verify that failed verification returns a nonzero exit code.
- Verify that publish workflows still require their existing test gates.

### Review Gate 3

Not passed. The producer steps landed on 2026-10-12. `SUPPLY_CHAIN.md` records
the `0.5.2` inventory. `RELEASING.md` records the verification commands.
Image and chart signatures, and the new SBOMs, appear on the next publish.
Close this gate only after those public artifacts verify.

- The evidence inventory is accurate and checked into the repository.
- Every published artifact has a documented SBOM and verification path.
- Missing image and chart integrity evidence has been added and tested.
- PyPI work extends its existing attestations only where the inventory proved
  that more evidence was needed.

## Phase 4 — Python lint and coverage visibility

Milestone: M4

### Goal

Make static quality checks and test coverage visible in pull requests.

### Scope

- Add Ruff to the development dependency set and configure an initial rule set.
- Fix or explicitly exclude existing findings. Do not combine this phase with a
  repository-wide formatting rewrite.
- Add a lint job to the main test workflow.
- Add `pytest-cov` and measure the current test suite before choosing a failure
  threshold.
- Record the baseline, set a threshold that does not hide an existing deficit,
  and document how maintainers raise it.
- Publish a readable coverage summary in CI. Avoid duplicate reports from every
  dependency-matrix job.

### Validation

- Ruff passes locally and in CI.
- The complete Python test suite still passes.
- CI shows statement and missing-line coverage in one stable job.
- A deliberate lint error and a deliberate threshold failure are confirmed to
  fail the relevant jobs, then reverted.

### Review Gate 4

Local checks passed on 2026-10-12. CI confirmation is the next pull request.

- `lint` and `coverage` run on every pull request from `.github/workflows/test.yml`.
- The statement-coverage floor is `fail_under = 81` in `pyproject.toml`.
  The local measurement was 81.50% (356 passed, 1 skipped). Raising or
  lowering it is a one-line change, documented in `RELEASING.md`.
- A file with a syntax error failed `ruff check` with exit code 1. That file
  was not committed.
- `pytest --cov=adapt --cov-fail-under=100` failed with
  `FAIL Required test coverage of 100% not reached. Total coverage: 81.50%`.
  The committed floor is 81.

## Phase 5 — Schema migrations and backup restore

Milestone: M5

### Goal

Replace `create_all()` and one-off `ALTER` statements with versioned
migrations. Prove that a backup can restore a working database.

### Scope

- Choose one migration tool and record the choice.
- Add a baseline migration for the current SQLite schema, including the OIDC
  additive columns.
- Stop using `create_all()` as the production schema path.
- Provide operator commands or scripts for SQLite backup and restore. The
  restore script belongs to the automation lane.
- Treat backup files as sensitive. They contain credential material.
- Document how maintainers add a migration, and how operators run backup and
  restore.
- Add tests for migrate-up from the current schema and for restore.

### Validation

- A new empty database reaches the current schema through migrations only.
- An existing database that was created with `create_all()` plus OIDC `ALTER`
  statements migrates without data loss.
- A backup restore produces a usable database. The check includes a login or
  an equivalent health path.
- The Python test suite still passes.

### Review Gate 5

- Migrations are the only supported schema path.
- Backup and restore docs and a recorded restore drill exist.
- Tests cover migrate-up and restore.

## Retained backlog outside these five phases

These known gaps remain valid but are not in the ordered plan:

- Declarative docroot seeding. If a real user workflow needs chart-managed
  starter documents, schedule a milestone. Until then, keep mounted volumes,
  uploads, and custom images as the supported options.
- Multi-replica operation. If an availability requirement exists, schedule a
  milestone after M5. Until then, keep the documented single-replica limit.
- Automate version selection and changelog generation from the project's commit
  convention.
- Evaluate secret scanning, static security analysis, and container
  vulnerability scanning after the supply-chain milestone establishes the
  common evidence and workflow patterns.

Schedule each item as its own milestone before implementation. Multi-replica
work must wait for M5.
