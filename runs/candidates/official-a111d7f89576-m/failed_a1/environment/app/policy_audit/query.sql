SELECT r.ingestion_sequence request_sequence,r.tenant_id tenant,
 CASE WHEN p.effect='allow' THEN 'allow' ELSE 'deny' END decision,
 pr.revision_id matched_policy_revision,p.effect||' policy '||p.policy_id reason
FROM access_requests r LEFT JOIN policy_bindings b ON b.valid_from<=r.requested_at
LEFT JOIN policy_revisions pr ON pr.revision_id=b.revision_id LEFT JOIN policies p ON p.policy_id=pr.policy_id
WHERE r.ingestion_sequence BETWEEN ? AND ? AND p.tenant_id=r.tenant_id AND p.action=r.action
AND r.resource LIKE p.resource_prefix||'%' AND (b.valid_until IS NULL OR r.requested_at<b.valid_until)
ORDER BY r.request_id
