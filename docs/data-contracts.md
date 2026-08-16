# Data contracts

## Inference events

Every event has an increasing string ID and one of these names:

- `run.started`
- `content.delta`
- `progress`
- `result.completed`
- `run.cancelled`
- `error`
- `done`

Clients can reconnect with `Last-Event-ID` while the API process is alive. Completed run and result state is always persisted and remains available through the run endpoint after restart.

## Trust boundary

The model may supply only:

- clash/no-clash;
- clash type;
- orientation;
- cross-sectional shape;
- cross-sectional size;
- a short explanation.

Clash names, element IDs, layers, report references, and source metadata are copied from parsed report records. Severity and recommended action are deterministic backend rules.

