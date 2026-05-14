from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from features.services.types import ApprovalResult, ApprovalStatus


class ApprovalAgent:
    """Human-in-the-loop approval bridge for n8n, with safe local fallback."""

    def __init__(self, webhook_url: str | None = None, webhook_secret: str | None = None) -> None:
        self.webhook_url = webhook_url or os.getenv("N8N_APPROVAL_WEBHOOK_URL")
        self.webhook_secret = webhook_secret or os.getenv("N8N_WEBHOOK_SECRET")

    def request_approval(self, payload: dict) -> ApprovalResult:
        if not self.webhook_url:
            return ApprovalResult(
                status=ApprovalStatus.PENDING,
                notified=False,
                comment="n8n webhook ayarlanmadi; mock insan onayi bekleniyor.",
            )

        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.webhook_secret:
            headers["X-KANIT-Webhook-Secret"] = self.webhook_secret
        request = urllib.request.Request(self.webhook_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                external_id = response.headers.get("X-Workflow-Execution-Id") or str(response.status)
        except (urllib.error.URLError, TimeoutError):
            return ApprovalResult(
                status=ApprovalStatus.PENDING,
                notified=False,
                comment="n8n webhook cagrisi basarisiz; rapor mock onayda bekliyor.",
            )
        return ApprovalResult(
            status=ApprovalStatus.PENDING,
            notified=True,
            external_workflow_id=external_id,
            comment="n8n insan onay workflow'una gonderildi.",
        )

