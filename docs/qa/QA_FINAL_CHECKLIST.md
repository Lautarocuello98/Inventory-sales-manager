# QA Final Checklist

## Automated
- [ ] Unit/integration suite passes (`pytest -q`).
- [ ] Lint passes (`ruff check .`).
- [ ] Compile check passes (`python -m py_compile ...`).
- [ ] Migration tests pass.

## E2E desktop flows (manual)
- [ ] Login as admin and force password change flow.
- [ ] Create product, sell it, validate stock deduction.
- [ ] Restock and verify weighted cost update.
- [ ] Export Excel report and verify sheets.
- [ ] Create encrypted backup and restore latest backup.
- [ ] Run health check and export diagnostics zip.

## Regression
- [ ] RBAC checks (admin/seller/viewer).
- [ ] FX fallback works when API unavailable.
- [ ] Low stock panel reflects changes.

## Release gate
- [ ] Installer signed.
- [ ] `release/latest.json` updated.
- [ ] Release notes and rollback plan documented.