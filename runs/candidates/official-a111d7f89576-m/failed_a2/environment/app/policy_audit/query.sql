SELECT r.ingestion_sequence AS request_sequence, r.tenant_id AS tenant,
       COALESCE((SELECT p.effect FROM policies p JOIN policy_revisions pr ON pr.policy_id=p.policy_id JOIN policy_bindings b ON b.revision_id=pr.revision_id WHERE p.tenant_id=r.tenant_id AND p.action=r.action AND r.resource LIKE p.resource_prefix || '%' AND b.valid_from<=r.requested_at AND (b.valid_until IS NULL OR r.requested_at<b.valid_until) ORDER BY length(p.resource_prefix) DESC, p.priority DESC, pr.revision_timestamp DESC LIMIT 1), 'deny') AS decision,
       NULL AS matched_policy_revision,
       'no applicable policy' AS reason
FROM access_requests r WHERE r.ingestion_sequence BETWEEN ? AND ? ORDER BY r.ingestion_sequence, r.request_row_id;
