# Documentation contract

The running implementation on `main` is the source of truth for Adapt's
documented behavior.

- [`manual/`](manual/index.md) is the authoritative user documentation. It
  describes the behavior, commands, routes, configuration, and limitations
  that users can rely on in the current implementation.
- [`spec/`](spec/README.md) is an implementation specification. It explains
  the current design. Do not use it as a roadmap or as a promise of
  intended behavior.
- Put unimplemented ideas in a clearly labeled **Future work** section, or
  in a project roadmap. They must not appear as current behavior.
- When the implementation and the documentation differ, document the
  running implementation. Do not silently substitute intended behavior.
- Record implementation defects as limitations. Do not promise behavior
  that is known not to work.

This contract also covers documentation build and publish behavior:

- MkDocs builds the hosted documentation from this repository.
- The generated API reference comes from an app built against an empty
  document root. This keeps the published documentation limited to the
  common Adapt surface.
- Runtime API documentation on a live instance stays request-aware and
  permission-aware. It can include more discovered-resource routes.
