# Release Process (commercial)

## 1) Pre-release checks
1. Run `scripts/check_release.sh`.
2. Confirm tests, lint, and compile checks pass.
3. Update `release/latest.json` with next version and URL.

## 2) Build artifacts
1. Run `scripts/build_release.sh`.
2. Verify `dist/InventorySalesManager` binary exists.
3. Verify wheel/sdist exist in `dist/`.

## 3) Signing and installer
- Windows: sign executable with company certificate (`signtool`).
- Build installer (Inno Setup / MSI) and sign installer.
- Keep checksum (`sha256`) for support verification.

## 4) Publish
1. Upload installer and checksum to releases channel.
2. Update `release/latest.json` endpoint.
3. Announce release notes to customers.

## 5) Rollback
- Keep previous signed installer and `latest.json` pointer ready.
- If incident occurs, point `latest.json` back to previous stable version.