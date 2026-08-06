# Documentation contract

The running implementation on `main` is the source of truth for Adapt's
documented behavior.

- [`manual/`](manual/index.md) is the authoritative user documentation. It
  describes the behavior, commands, routes, configuration, and limitations
  that users can rely on in the current implementation.
- [`spec/`](spec/README.md) is an implementation specification. It explains
  the current design and must not be used as a roadmap or as a promise of
  intended behavior.
- Unimplemented ideas belong in a clearly labeled **Future work** section or
  in a project roadmap. They must not appear as current behavior.
- When the implementation and documentation differ, document the running
  implementation. Do not silently substitute intended behavior.
- Record implementation defects as limitations. Do not promise behavior that
  is known not to work.

This contract also covers documentation build and publish behavior:

- Hosted docs are built with MkDocs from this repository.
- Generated API reference content is produced from an app built against an
  empty document root so published docs represent the common Adapt surface.
- Runtime API docs on a live instance remain request-aware and
  permission-aware, and may include additional discovered-resource routes.
