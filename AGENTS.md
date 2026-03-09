# AGENTS.md

This file defines how AI coding agents work in this repository, following the MCAF framework.

## Agent Behaviour
- Agents read this file and all relevant docs before editing code.
- Agents follow the documented development flow and testing discipline.
- Agents help draft feature docs, ADRs, and test specifications.
- Agents run only the documented commands for build, test, format, and analyze.

## Canonical Commands
- **build:** (define build command here)
- **test:** (define test command here)
- **format:** (define formatting command here)
- **analyze:** (define static analysis command here)

## Coding Rules
- Centralize meaningful constants/configuration.
- Structure code for integration/API/UI testability.
- Avoid global state and hidden side effects.
- Refactor hard-to-test code as a design issue.

## Testing Discipline
- Integration/API/UI tests for all significant features.
- Mocks/fakes only for external systems, with realistic behaviour.
- Static analyzers run as part of Definition of Done.

## Self-Learning
- Agents extract rules from feedback and code history.
- Stable patterns are written into this file or docs.

## Maintainer Preferences
- (Add naming, formatting, tone, and explanation style preferences here)

> Update this file as new rules, commands, or patterns emerge.
