# Observability

The repository includes lightweight in-process tracing and metrics collectors.
They can record spans, counters, and duration summaries for local inspection;
they are not an OpenTelemetry deployment or a production monitoring system.

Workflow integration can emit optional run/completion/duration measurements.
The health server's `/metrics` route currently returns a static
`ai_agent_up 1` gauge and does not export the in-process collector snapshots.
No exporter, alerting rules, SLO dashboards, or centralized telemetry pipeline
is established.

See [Deployment and Operations](./DEPLOYMENT_AND_OPERATIONS.md) for current
operational gaps and [Product Roadmap](./PRODUCT_ROADMAP.md) for proposed
production observability work.
