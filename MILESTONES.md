# Milestones — adapt

Each milestone after M0 is a tracer round: one thin, working, end-to-end
slice through all eight lanes (business logic, interface, data,
packaging, automation, tests, docs, security). Tracer code is kept, not
thrown away, once it lands. A milestone counts as reached only when every
lane reads `OK` for it in `PROJECT_STATUS.md`.

## M0 — Walking Skeleton (closed)

Goal: connect all eight lanes end to end. In practice this project has
run business logic, interface, tests, and docs far past a walking
skeleton already (v0.3.0, 319 tests, a real docs manual, at the time this
milestone closed — see `PROJECT_STATUS.md` for current numbers). M0's
security floor is now closed too (see M1 below and `PROJECT_STATUS.md`).

Definition of Done for M0:

- [x] The system installs and runs; `--version` and `--help` (or their
      equivalents) work.
- [x] CI builds the system and publishes releases (currently release-gated
      PyPI publish via OIDC trusted publishing, not `0.0.x` but a real
      0.3.0 — exceeds the bar).
- [x] One smoke test exists and runs in CI (there are 319).
- [x] A README exists.
- [x] The data storage location is decided and documented (SQLite at
      `<docroot>/.adapt/adapt.db`).
- [x] Security floor is in place:
  - [x] No secret is hardcoded; every secret loads from an environment
        variable or a secret store.
  - [x] Dependencies are pinned or constrained with upper bounds.
  - [x] CI runs one automated dependency-vulnerability scan.
  - [x] Transport and TLS assumptions are stated somewhere findable.
  - [x] `SECURITY.md` exists, with a reporting path and a first
        threat-model note.

## M1 — Close the security floor (done)

Goal: finish what M0 already promised — pin dependencies, add one CI
dependency-vulnerability scan, and add `SECURITY.md` with a reporting
path and a first threat-model note.
Why this slice: everything else in the project already outran M0; this is
the cheapest, highest-leverage slice because it closes an already-started
milestone rather than opening a new one, and it's a prerequisite for M2
(supply-chain hardening) to mean anything.

| Lane | Target state at this milestone |
|------|--------------------------------|
| Business logic | Unchanged (N/A for this round) |
| Interface | Unchanged (N/A for this round) |
| Data | Unchanged (N/A for this round) |
| Packaging | `pyproject.toml` dependencies pinned or constrained with upper bounds; lockfile if the team adopts one |
| Automation | `pip-audit` (or `safety`) added as a CI step in `test.yml` or a new workflow, gating on findings |
| Tests | Unchanged (N/A for this round) |
| Docs | `SECURITY.md` added at repo root: reporting path/contact, supported versions, and a short first threat-model note |
| Security | Threat-model note written; dependency scan wired in; pinned deps verified to still build and pass tests |

Exit criteria: all eight lanes read `OK` for M1 in `PROJECT_STATUS.md`
(most will simply read `N/A` or carry over their current `OK`, since this
round intentionally targets security/packaging/automation/docs only).

Result: done. `pyproject.toml` dependencies now carry lower + upper
version bounds; `.github/workflows/test.yml` gained a `dependency-audit`
job running `pip-audit` on every push/PR, gating on findings; `SECURITY.md`
added at the repo root with a reporting path and a threat-model note.

`pip-audit` initially found 18 known CVEs in `pillow==11.3.0`, all fixed
only in pillow>=12, which `moviepy==2.2.1` blocked by pinning
`pillow<12.0` — and no moviepy release back to 2.0.0 allows pillow>=11.
Rather than suppress the findings, `moviepy` was dropped: it was only used
in `adapt/plugins/media_plugin.py` to grab one video frame for a
thumbnail, which `imageio` + `imageio-ffmpeg` (moviepy's own frame-decode
dependencies) do directly without the conflicting pin. `pillow` is now
pinned to `>=12.3,<13`, and `pip-audit` runs with zero ignored findings.
All eight lanes read `OK`.

## Deployment tracer: Kubernetes/Helm packaging (done)

Not part of the numbered M0-M4 ladder — this is a deliberately-fired,
self-contained tracer round through a *new* surface (Kubernetes
deployment) rather than the next slice of hardening the existing PyPI
path. Named here explicitly, per the skill's own guidance, rather than
letting it hide as an unmarked gap against M2-M4.

Goal: make Adapt deployable on Kubernetes with a real Helm chart, durable
storage, and a way to reach it and log in without hand-editing manifests
or shelling into a pod.
Why this slice: local/VM installs already worked; Kubernetes was
unaddressed entirely. Firing it as one slice (not spread across several
milestones) kept persistence, bootstrapping, and connectivity coherent
with each other instead of landing as three uncoordinated changes.

| Lane | Result |
|------|--------|
| Business logic | N/A — no application-level change |
| Interface | `service.type: NodePort` (with a pinnable `nodePort`) added for clusters without an Ingress controller, alongside the existing `ClusterIP`/Ingress path |
| Data | `persistence.enabled` + PVC support added to the chart (dynamic provisioning or a pre-created `existingClaim`), replacing the previous always-ephemeral `emptyDir` mount |
| Packaging | `charts/adapt/` is versioned independently of the app via `Chart.yaml`; Phase 5 published it to `oci://ghcr.io/mcindi/charts/adapt` from a matching `chart-v<version>` tag. The release-candidate `chart-v0.5.1-rc.1` round trip passed; stable `0.5.1` is still to be tagged. `appVersion` remains tied to the app release. |
| Automation | `helm-ci.yml` runs for chart-affecting `main` pushes, pull requests, manual dispatches, and reusable workflow callers, including `tools/test-helm-schema.sh` changes. It runs lint, the chart unit tests, schema checks, and `kind` install smoke tests across 3 Kubernetes versions. `publish-chart.yml` calls it and the Python test workflow before a chart can be pushed to GHCR; its first run published `chart-v0.5.1-rc.1` and a clean-machine `helm install` into a fresh kind cluster confirmed the package installs anonymously and serves `/health`. |
| Tests | 52 `helm-unittest` cases cover persistence, pod selectors, security contexts, health probes, admin-bootstrap Job/Secret rendering, NodePort wiring, operator notes, ingress URL rendering, external volume mounts, schema rejection, unsafe storage combinations, and namespace-qualified commands. The bootstrap guard still stops rendering when persistence is disabled. |
| Docs | README and `docs/manual/installation.md` gained a full Helm section: all three persistence modes, admin bootstrapping, NodePort, and a `values-dev.yaml` overlay for local cluster development. `RELEASING.md` documents chart tags and OCI installation; Phase 6 will consolidate deployment documentation. |
| Security | Admin-bootstrap credentials are generated into a Kubernetes Secret (24-char random password, generated once and preserved across upgrades) rather than requiring a hand-typed password or shipping a default one |

Result: done. Also surfaced two bugs, both fixed in the same slice rather
than deferred: `charts/adapt/Chart.yaml`'s `appVersion` had silently
drifted one release behind `pyproject.toml` (now guarded by the version-
match check described in M2 below), and two web UI routes leaked dataset
*names* (not data) to authenticated users without read permission on them
via an unfiltered navigation-link builder — fixed with regression tests
that were confirmed to fail against the pre-fix code.

Phase 4 usability work is implemented in the chart: `NOTES.txt` explains
service access, login, document transfer, and ephemeral state; `extraVolumes`
and `extraVolumeMounts` support mounted document sources; `values.schema.json`
rejects unknown root values and misspellings in required sections; and chart
metadata is complete. Helm lint, schema checks, unit tests, and live kind
checks have been run for Phase 4, with the caveat that kind leaves
LoadBalancer external IPs pending.

## M2 — Supply-chain hardening at publish time

Goal: every artifact published — to PyPI **and** now to GHCR as a
container image (see the deployment tracer above, which added that
publish path) — is signed and ships with a generated SBOM, and Dependabot
keeps dependencies current automatically.
Why this slice: the publish pipeline already works (OIDC trusted
publishing to PyPI, and now GHCR too) — this round makes what it publishes
verifiable and keeps the M1 dependency floor from rotting, rather than
opening a new capability.

Head start already in place: both `publish-pypi.yml` and the newer
`publish-image.yml` now hard-depend on the full test suite passing
(`test.yml` called as a reusable workflow, not just trusted to have run)
before either can publish, and both refuse to run if the release tag
doesn't match `pyproject.toml`'s version. That's supply-chain integrity
work that landed as part of the deployment tracer above, ahead of this
milestone — it doesn't close M2 by itself (no SBOM, no signing yet), but
it's real progress toward it and shouldn't be re-done here.

| Lane | Target state at this milestone |
|------|--------------------------------|
| Business logic | Unchanged (N/A for this round) |
| Interface | Unchanged (N/A for this round) |
| Data | Unchanged (N/A for this round) |
| Packaging | SBOM (e.g. CycloneDX via `cyclonedx-py`) generated and attached to each release, for **both** the PyPI wheel and the GHCR container image; both builds remain reproducible |
| Automation | `.github/dependabot.yml` added for the `pip`, `github-actions`, and (new) `docker` ecosystems; `publish-pypi.yml` **and** `publish-image.yml` each gain a `cosign`/sigstore signing step |
| Tests | Unchanged (N/A for this round) |
| Docs | README/RELEASING.md updated to describe how a consumer verifies a signed release (wheel and image) and reads the SBOM; `charts/adapt` values documented for pinning to a signed/digest-verified image if the cluster enforces that |
| Security | Signing key/identity setup documented; SBOM and signature verified end-to-end on one real release, for both artifact types |

Exit criteria: all eight lanes read `OK` for M2 in `PROJECT_STATUS.md`.

## M3 — Schema evolution and tested backup/restore

Goal: introduce a real migration tool for the SQLite schema and prove a
backup can actually be restored.
Why this slice: `SQLModel.metadata.create_all()` works today because the
schema has never needed to change under existing data; the first real
migration is the moment this breaks, so it's worth retiring that risk
deliberately rather than discovering it during an incident. It also pairs
naturally with a tested restore path, since both touch the same SQLite
file.

| Lane | Target state at this milestone |
|------|--------------------------------|
| Business logic | Unchanged (N/A for this round) |
| Interface | Unchanged (N/A for this round) |
| Data | Alembic (or equivalent) introduced; one real migration written and applied |
| Packaging | Unchanged (N/A for this round) |
| Automation | Backup script plus a restore script added, and the restore path exercised in CI or a documented manual drill |
| Tests | A test that runs a migration against a populated database and asserts data survives |
| Docs | `docs/manual` gains a migration/backup-restore section |
| Security | Confirm restored data does not bypass access-control invariants (e.g. hashed passwords/API keys survive intact) |

Exit criteria: all eight lanes read `OK` for M3 in `PROJECT_STATUS.md`.

## M4 — Release automation and coverage visibility

Goal: version bumps and the changelog fall out of Conventional Commits
automatically, and test coverage is visible in CI rather than implied by
test count alone.
Why this slice: the project already has a real (if manual) release
process; this closes the gap between "hundreds of tests exist" (see
`PROJECT_STATUS.md` for the current count) and "we know what they cover,"
and removes the last hand-maintained artifact (the version number and a
changelog that doesn't exist yet).

| Lane | Target state at this milestone |
|------|--------------------------------|
| Business logic | Version number now derived from commit history, not hand-edited in `pyproject.toml` |
| Interface | Unchanged (N/A for this round) |
| Data | Unchanged (N/A for this round) |
| Packaging | `python-semantic-release` (single registry, pure Python — see `RELEASING.md`) wired into the release workflow |
| Automation | Release workflow computes version + changelog from commits; coverage tool added to `test.yml` |
| Tests | Coverage report generated in CI (visible in PR checks, not just local) |
| Docs | `CHANGELOG.md` added and auto-populated going forward |
| Security | Unchanged (N/A for this round) |

Exit criteria: all eight lanes read `OK` for M4 in `PROJECT_STATUS.md`.

<!--
Add further milestones the same way. Milestones after M0 don't come from
a fixed list — define each one for what this specific project needs
next. Keep every milestone a genuine end-to-end slice: touching only one
or two lanes deeply while leaving the rest untouched is not a tracer
round, it's the kind of gap the ripple rule exists to catch. A team may
choose to push one lane ahead on purpose as a targeted tracer bullet —
that's fine, but name the resulting gap in PROJECT_STATUS.md rather than
letting it hide as an unmarked LAG.
-->
