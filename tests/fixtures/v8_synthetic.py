from copy import deepcopy
import time
from black_swan.engine import TrustedContext, WindowUpdate
from black_swan_v7_latency_edge_audit import scenario

def trusted_fixtures():
    """Trusted only for the synthetic benchmark; not real change approvals."""
    now = time.time()
    records = []
    for name in ['approved_backup', 'software_release', 'campaign_traffic', 'planned_cloud_drift']:
        e = scenario(name).context_events[0]
        records.append(TrustedContext(e.event_key, e.evidence_ref, e.covered_metrics,
                                      e.confidence, now - 60, now + 3600))
    return tuple(records)


def update_for(model, name, item):
    token = model.register_baseline(name, item)
    return WindowUpdate(token, item.scenario_id, deepcopy(item.recent),
                        deepcopy(item.recent_status), dict(item.lifecycle), list(item.context_events))


