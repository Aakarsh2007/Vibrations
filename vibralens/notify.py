"""Work-order notification, exactly-once per work order as far as possible (workflow.md §B7.2):
notify_state NONE -> SENDING (conditional) -> publish -> SENT.
Local/dev mode has no email: the approval link is written to the 'outbox' collection, which is only
readable through /api/dev/outbox when VL_DEV=1 (never shown to the technician in the main UI)."""
from __future__ import annotations

import logging
import time

from . import config

log = logging.getLogger("vibralens.notify")


def work_order_created(store, sess, token: str):
    wo_id = sess["work_order_id"]

    def to_sending(w):
        if w["notify_state"] in ("NONE",) or (w["notify_state"] == "SENDING" and time.time() - w.get("notify_ts", 0) > 300):
            return {**w, "notify_state": "SENDING", "notify_ts": time.time()}
        return None
    w = store.update("workorders", wo_id, to_sending)
    if w["notify_state"] != "SENDING":
        return
    link = f"{config.PUBLIC_BASE_URL}/approve.html#t={token}"
    body = ("VibraLens work order needs your decision.\n\n" + "\n".join(w["summary"]["evidence"]) +
            f"\n\nRecommended: {w['summary']['recommended_action']}\n\nOpen to approve or reject (expires in "
            f"{config.T['approval_hours']} h): {link}\nIf you received this twice, the link is the same.")
    if config.SNS_TOPIC_ARN:
        import boto3
        boto3.client("sns", region_name=config.AWS_REGION).publish(
            TopicArn=config.SNS_TOPIC_ARN, Subject="VibraLens: work order approval needed", Message=body)
    else:
        store.put("outbox", wo_id, {"wo_id": wo_id, "workspace_id": sess["workspace_id"], "body": body,
                                    "link": link, "ts": time.time()})
        log.info("approval link (dev outbox) for %s", wo_id)
    store.update("workorders", wo_id, lambda x: {**x, "notify_state": "SENT"})
