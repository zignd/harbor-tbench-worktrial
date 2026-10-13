# Attributed Funnel Service

Run `./run.sh`; the service listens on port 8080. Events use UTC ISO-8601 timestamps. Kinds are `touch`, `purchase`, and `refund`. Campaign names are returned as supplied, with `(direct)` used when a purchase has no preceding touch. Reports use half-open `[since, until)` ranges and JSON rows with `campaign`, `campaign_name`, `sessions`, `purchases`, and `revenue_cents`.
