# MCAF Adoption Plan for Adapt

This document tracks the concrete steps and gaps for aligning Adapt with the MCAF framework.

## 1. Context & Documentation Structure
- [x] Create `docs/Features/`, `docs/ADR/`, `docs/Testing/`, `docs/Development/` directories.
- [x] Add templates for each doc type.
- [ ] Audit and migrate existing docs from `docs/manual/` and `docs/spec/` to the new structure.
- [ ] Ensure all features, ADRs, and test strategies are documented and linked.

## 2. Feature Documentation
- [ ] For each non-trivial feature, create a doc in `docs/Features/` using the template.
- [ ] Link feature docs to code, tests, and ADRs.

## 3. Verification: Tests & Static Analysis
- [ ] Review `tests/` for integration/API/UI coverage; add missing tests.
- [ ] Ensure containerized test environments (e.g., Docker Compose) are documented.
- [ ] Audit static analyzer setup; document commands in `AGENTS.md` and `docs/Development/`.
- [ ] Restrict mocks/fakes to external systems only.

## 4. Instructions & AGENTS.md
- [x] Create root `AGENTS.md` with agent rules, commands, and coding/testing discipline.
- [ ] Update `.github/copilot-instructions.md` to reference and align with `AGENTS.md`.
- [ ] Add local `AGENTS.md` files for submodules if stricter rules are needed.

## 5. Coding and Testability
- [ ] Audit code for centralized constants/configuration and testable structure.
- [ ] Refactor hard-to-test code as needed.
- [ ] Document patterns in `AGENTS.md` and review checklists.

## 6. Development Cycle & Process
- [ ] Ensure workflow matches MCAF: docs/plan/tests/code/layered tests/static analysis/docs/review.
- [ ] Record plans/decisions in issues, docs, or merge requests.

## 7. AI Participation Modes
- [ ] Document preferred AI agent participation modes in `AGENTS.md` and/or `README.md`.

---

> Update this plan as progress is made or new gaps are discovered.
