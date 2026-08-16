# Shared contracts

The FastAPI OpenAPI document is the source of truth. Generate client types from `http://localhost:8000/openapi.json` when the public API stabilizes. The MVP web client keeps its small matching interfaces in `apps/web/src/types.ts` to avoid committing generated code before the contract settles.

