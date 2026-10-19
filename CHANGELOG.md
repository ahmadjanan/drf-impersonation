# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-20

### Added

- `ImpersonationMixin` for header-based impersonation on top of any DRF authentication class.
- `ImpersonationTokenAuthentication`, DRF's `TokenAuthentication` with impersonation.
- Hooks: `impersonation_header`, `impersonation_lookup_fields`, `can_impersonate`,
  `can_impersonate_target`, `on_impersonate`.
- `DRF_IMPERSONATION` settings: `READ_ONLY`, `SIGNALS` and `OPENAPI`, all on by default.
- Read-only impersonation. Write methods get `403` while impersonating.
- `user_impersonated` signal.
- drf-spectacular extension that documents the header as an optional security scheme. Install it
  with the `openapi` extra.
- Type hints and a `py.typed` marker.

[Unreleased]: https://github.com/ahmadjanan/drf-impersonation/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ahmadjanan/drf-impersonation/releases/tag/v0.1.0
