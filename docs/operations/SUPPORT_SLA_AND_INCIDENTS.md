# Support, SLA and Incident Policy

## Support channels
- Primary: support email (business hours).
- Secondary: ticket form with attached diagnostics zip.

## SLA targets
- P1 (system unusable): first response <= 4 business hours.
- P2 (critical workflow degraded): <= 8 business hours.
- P3 (minor bug / UX): <= 2 business days.

## Incident handling
1. Register incident ID and customer context.
2. Request diagnostics package from app (`Export diagnostics`).
3. Classify severity (P1/P2/P3).
4. Mitigate: hotfix, rollback, or guided restore backup.
5. Publish postmortem with root cause and preventive action.

## Data recovery policy
- Encourage daily encrypted backups.
- Use in-app restore only from trusted backup source.
- Confirm integrity check result (`ok`) after restoration.