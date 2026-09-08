# Adapt Hardening Plan

Status: Active — Phase 1 is in the repository. Review Gate 1 waits on
publish (`v0.5.2`, chart `0.5.2-rc.1`, then `chart-v0.5.2`).
Created: 2026-09-03
Updated: 2026-09-08

This plan replaces the completed container and Helm cleanup plan. The full
record of that work is in
[`archive/CONTAINER_OCI_HELM_CLEANUP_PLAN_2026-09-02.md`](archive/CONTAINER_OCI_HELM_CLEANUP_PLAN_2026-09-02.md).

## Goal

Close the remaining deployment, supply-chain, and quality gaps in priority
order. Do not start a later phase until the current review gate passes.

The phases are grouped into these milestones:

| Milestone | Phases | Outcome |
|---|---:|---|
| M2 — Coordinated 0.5.2 release | 1 | Application, image, and chart `0.5.2` publish with aligned metadata and a digest-pinnable image reference. |
| M3 — Dependency and supply-chain hardening | 2–3 | Automated updates, a pinned base image, artifact inventories, SBOMs, signatures, and verification instructions are in place. |
| M4 — Quality visibility | 4 | Python lint and test coverage run in CI with an agreed baseline. |
| M5 — Declarative docroot seeding | 5 | If users need it, the chart can seed a docroot safely and repeatably. Otherwise, the decision to omit it is recorded. |
| M6 — Multi-replica operation | 6 | If high availability is required, Adapt has an approved architecture and tested implementation. Otherwise, the single-replica limit stays explicit. |

## Working rules

- Complete phases in order.
- Keep each phase in one focused change set when practical.
- Update `PROJECT_STATUS.md`, `MILESTONES.md`, and user documentation in the
  same phase as the related implementation.
- Run the listed checks and record the evidence before requesting review.
- Stop at each review gate. Do not start the next phase until the gate passes.
- A conditional phase can close as `N/A` when its decision gate finds no real
  requirement. Record the reason instead of building speculative features.

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

- The bare `adapt` release name no longer causes a crash loop.
- Tag and digest image modes both render valid, exclusive image references.
- The package, image, chart `version`, and chart `appVersion` are `0.5.2`.
- The `v0.5.2` and `chart-v0.5.2` tags publish the correct artifact types.
- The security manual covers uploads.
- Chart `0.5.2-rc.1` and chart `0.5.2` both pass the remote round trip.

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

- Dependabot has opened or queued valid update checks for all three ecosystems.
- The pinned base image builds for both supported architectures.
- No unrelated dependency upgrade is required to pass the gate.

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

- Lint and coverage are required pull-request checks.
- The recorded coverage baseline matches CI.
- The threshold policy is documented and can increase without redesigning the
  workflow.

## Phase 5 — Declarative docroot seeding (conditional)

Milestone: M5

### Decision gate

Identify a real user workflow that needs chart-managed starter documents. If
no current workflow needs it, record Phase 5 as `N/A` and keep mounted volumes,
uploads, and custom images as the supported options.

### Implementation scope if approved

- Choose one minimal, declarative source for seed content. Do not design several
  source mechanisms in the first release.
- Add values and schema for the source, destination, overwrite policy, and file
  ownership.
- Use an init container that is idempotent and safe with persistent volumes.
- Define whether seeding occurs only for an empty destination or also supports
  an explicit update mode.
- Preserve the runtime UID/GID and read-only-root-filesystem security posture.
- Define interactions with `persistence`, `existingClaim`, and external volume
  mounts.
- Add Helm unit tests, kind tests for first install and upgrade, and operator
  documentation.
- Use a chart minor version for the new capability unless review finds a
  breaking values change.

### Review Gate 5

- The need and chosen source are documented, or the phase is closed as `N/A`.
- If implemented, first install, repeated upgrade, and pre-populated-volume
  behavior are deterministic and preserve existing user files.

## Phase 6 — Multi-replica operation (conditional)

Milestone: M6

### Decision gate

Define the availability objective, expected write concurrency, failure model,
and target Kubernetes storage classes. If no current requirement needs more
than one replica, record Phase 6 as `N/A` and retain the documented
single-replica limit.

### Architecture scope if approved

- Resolve SQLite write locking and schema-migration coordination. This can
  require a supported external database instead of shared SQLite storage.
- Resolve shared document storage, session state, caches, search indexes, and
  bootstrap-job coordination.
- Define ReadWriteMany requirements and behavior on clusters that do not offer
  it.
- Design probes, disruption budgets, rolling upgrades, and safe scale-down.
- Produce a migration and rollback plan for existing single-replica installs.
- Complete an architecture review before changing `replicaCount` behavior.

### Implementation and verification if approved

- Implement the approved storage and coordination design across the
  application and chart.
- Test concurrent reads and writes, pod loss, rolling upgrades, bootstrap
  races, and database migration races.
- Run multi-node kind or an equivalent integration environment where storage
  behavior is representative.
- Document capacity limits, required infrastructure, migration, rollback, and
  recovery.

### Review Gate 6

- The requirement and architecture decision are recorded, or the phase is
  closed as `N/A`.
- If implemented, failure and upgrade tests demonstrate the stated availability
  objective without data loss or permission regressions.

## Retained backlog outside these six phases

These known gaps remain valid but were not part of the deferred-item ordering
that produced this plan:

- Add database schema migrations and a tested backup-and-restore drill.
- Automate version selection and changelog generation from the project's commit
  convention.
- Evaluate secret scanning, static security analysis, and container
  vulnerability scanning after the supply-chain milestone establishes the
  common evidence and workflow patterns.

Schedule each item as its own milestone before implementation. If Phase 6 is
approved, schema migration and restore work becomes a prerequisite and must be
scheduled before its implementation begins.
