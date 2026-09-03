# AiSteth Dashboard FastAPI

## Authentication

All `/api/v1` endpoints require a verified AWS Cognito ID token. The API validates the RS256 signature against the User Pool JWKS, issuer, audience, expiry, and token use, then resolves the active role from the configured DynamoDB user-roles table. The current global dashboard permits only `superadmin` records whose `tenant_id` is `all`. `/health`, `/docs`, and `/openapi.json` remain public for local operations.

Copy `.env.example` to `.env` and replace the placeholders. `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, and `DASHBOARD_USER_ROLES_TABLE` must match the existing Cognito/role setup. Local AWS keys may be placed in `.env`; for deployed environments, use an IAM role instead of long-lived keys. `.env` is ignored by Git.

This is a standalone FastAPI service. Runtime configuration comes only from the
backend `.env` or deployment environment. It connects directly to Cognito,
DynamoDB, and Elasticsearch; no legacy backend or local configuration path is
used. Secrets are validated into masked values and are never included in Swagger,
API responses, or application logs.

## Run locally

From the repository root:

```powershell
python -m pip install -r backend_dashboard\requirements-dev.txt
python -m backend_dashboard.run
```

Configured mode first attempts the legacy Elasticsearch username/password and
automatically retries AWS Signature Version 4 authentication when the domain
returns 401 or 403. A blank `ES_PORT_DEFAULT` uses the URL scheme's standard port.

For isolated UI development without a connection:

```powershell
$env:DASHBOARD_DATA_MODE="synthetic"
python -m backend_dashboard.run
```

`DASHBOARD_ES_VERIFY_TLS` controls Elasticsearch certificate verification and
defaults to enabled.

The default local URLs are:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health: `http://127.0.0.1:8000/health`

Set `DASHBOARD_ALLOWED_HOSTS` and `DASHBOARD_CORS_ORIGINS` as comma-separated
allowlists when using different local hosts. Wildcard CORS is not enabled.

## API surface

- `GET /api/v1/dashboard/overview` - global metrics and operating health
- `GET /api/v1/dashboard/aih-buddy` - AiH Buddy and QRisk overview
- `GET /api/v1/organizations` - searchable, filtered, paginated organizations
- `GET /api/v1/organizations/{id}` - organization summary
- `GET /api/v1/organizations/{id}/dashboard` - organization-scoped metrics
- `GET /api/v1/organizations/{id}/providers` - organization providers
- `GET /api/v1/providers` - searchable, paginated medical professionals
- `GET /api/v1/providers/{id}` - provider summary
- `GET /api/v1/providers/{id}/dashboard` - provider-scoped metrics
- `GET /api/v1/locations` - organization map points
- `GET /api/v1/operations/overview` - pipeline, backup, subscription,
  onboarding, feedback, and data-quality health
- `POST /api/v1/onboarding/organizations` - validate an organization request
- `POST /api/v1/onboarding/providers` - validate a provider request

The onboarding endpoints currently validate and accept contracts but do not write
to DynamoDB. Dashboard organizations, providers, locations, and metric reads use
Elasticsearch in configured mode. Operational health fields that have not yet
been mapped to a configured index retain deterministic placeholders.

All reporting endpoints accept optional inclusive `date_from` and `date_to` query
parameters. The default reporting window is 180 days and the maximum is 730 days. Dashboard clients may explicitly request the full historical window with `all_time=true`.

## Legacy route consolidation

| Production route group | FastAPI replacement |
| --- | --- |
| Global tenant, provider, patient, recording, lab, and heart-sound totals | `/api/v1/dashboard/overview` |
| Tenant-specific statistics routes | `/api/v1/organizations/{id}/dashboard` |
| Provider-associated tenant statistics routes | `/api/v1/providers/{id}/dashboard` |
| AiH Buddy monthly/report statistics routes | `/api/v1/dashboard/aih-buddy` |
| Geopoints | `/api/v1/locations` |
| Tenant and provider onboarding | `/api/v1/onboarding/organizations` and `/api/v1/onboarding/providers` |

Authentication is implemented directly in FastAPI with signed Cognito JWT
verification and direct DynamoDB role authorization.

## Contracts and safety boundaries

- `schemas/dynamodb.py` contains strict persistence-boundary models transcribed
  from `DynamoDB Tables (1).pdf`.
- `schemas/dashboard.py` contains PII-minimized aggregate dashboard DTOs.
- `schemas/api.py` contains HTTP request and response models.
- `contracts/dashboard.ts` mirrors both persistence and API contracts without
  unsafe catch-all types.
- Undeclared request fields are rejected, timestamps are timezone-aware at the
  persistence boundary, and counts, percentages, coordinates, and date windows
  are range-validated.
- Not-found responses do not echo submitted identifiers.
- Responses include request IDs, restrictive cache behavior, clickjacking and MIME
  protections, a referrer policy, and a permissions policy.

Raw healthcare records are not exposed by these routes. Elasticsearch failures are
returned as sanitized 502 responses without endpoint or credential details.

## Audit commands

```powershell
python -m unittest discover -s backend_dashboard\tests -v
mypy backend_dashboard --config-file backend_dashboard\pyproject.toml
npm run audit:types
```

The tests cover Swagger/ReDoc/OpenAPI availability, response-model parsing, date
validation, pagination and filtering, scoped resources, sanitized errors,
onboarding validation, and security headers.

## Before deployment

Confirm representative redacted production items for provider contact maps,
flexible PHR and lab-report documents, subscription descriptions, and every status
value. Then add authentication, role and tenant authorization, secrets management,
rate limiting, audit logging, production-safe error monitoring, database query
limits, and integration tests before deployment.
