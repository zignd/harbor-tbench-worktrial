"""Legacy correlated resolver used by the initial service."""
def export_rows(con, since, until):
    sql = """
    SELECT r.request_sequence, t.name AS tenant,
      (SELECT p.effect FROM policy_definitions p JOIN policy_revisions v ON v.policy_id=p.policy_id
       WHERE p.tenant_id=r.tenant_id AND p.action=r.action
         AND r.resource LIKE p.resource_prefix || '%' AND v.revision_ts <= r.event_ts
       ORDER BY p.priority DESC LIMIT 1) AS decision,
      (SELECT v.revision_id FROM policy_definitions p JOIN policy_revisions v ON v.policy_id=p.policy_id
       WHERE p.tenant_id=r.tenant_id AND p.action=r.action
         AND r.resource LIKE p.resource_prefix || '%' AND v.revision_ts <= r.event_ts
       ORDER BY p.priority DESC LIMIT 1) AS matched_policy_revision,
      (SELECT p.reason FROM policy_definitions p JOIN policy_revisions v ON v.policy_id=p.policy_id
       WHERE p.tenant_id=r.tenant_id AND p.action=r.action
         AND r.resource LIKE p.resource_prefix || '%' AND v.revision_ts <= r.event_ts
       ORDER BY p.priority DESC LIMIT 1) AS reason
    FROM access_requests r JOIN tenants t ON t.tenant_id=r.tenant_id
    WHERE r.event_ts >= ? AND r.event_ts < ? ORDER BY r.request_id
    """
    return con.execute(sql, (since, until))
