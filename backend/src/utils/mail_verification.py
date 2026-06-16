from __future__ import annotations

import requests

from ..config import load_env, mail_config


class MailVerification:
    def __init__(self, *, enabled: bool | None = None) -> None:
        load_env()
        cfg = mail_config()
        self.api_key = cfg.verification_api_key
        self.enabled = bool(cfg.verification_enabled) if enabled is None else bool(enabled)

    def verify_deliverable(self, email: str) -> bool:
        """
        EmailListVerify deliverability check.
        When MAIL_VERIFICATION=0 -> always True.
        """
        email = (email or "").strip()
        if not email:
            return False

        if not self.enabled:
            return True

        if not self.api_key:
            raise RuntimeError("MAIL_VERIF_API_KEY is not configured")

        try:
            resp = requests.get(
                "https://api.emaillistverify.com/api/verifyEmail",
                headers={"x-api-key": self.api_key, "accept": "text/html"},
                params={"email": email},
                timeout=10,
            )
        except requests.RequestException:
            # Fail closed when verification is enabled
            return False

        if int(resp.status_code) != 200:
            return False

        status = (resp.text or "").strip()
        return status in ("ok", "ok_for_all")

