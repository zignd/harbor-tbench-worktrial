# Attributed funnel service
Run `./run.sh` to listen on port 8080. The service accepts JSON POST requests at `/v1/reset`, `/v1/append`, and `/v1/report`, and reports health at `/health`. Report rows use `campaign_name`, `session_count`, `purchase_count`, and `net_revenue_cents`.
