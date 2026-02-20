# QA Final Checklist

## Automated
- [x] Unit/integration suite passes (`pytest -q`).
- [x] Lint passes (`ruff check .`).
- [x] Compile check passes (`python -m py_compile ...`).
- [x] Migration tests pass.

## E2E desktop flows (manual)
- [x] Login as admin and force password change flow.
- [x] Create product, sell it, validate stock deduction.
- [x] Restock and verify weighted cost update.
- [x] Export Excel report and verify sheets.
- [x] Create encrypted backup and restore latest backup.
- [x] Run health check and export diagnostics zip.

## Regression
- [x] RBAC checks (admin/seller/viewer).
- [x] FX fallback works when API unavailable.
- [x] Low stock panel reflects changes.

## Release gate
- [ ] Installer signed.
- [x] `release/latest.json` updated.
- [x] Release notes and rollback plan documented.

## Notes
- Automated checks last validated in CI/local with: `pytest -q`, `ruff check .`, and `python -m py_compile`.
- Remaining gate is operational: generate installer and sign with organization certificate.