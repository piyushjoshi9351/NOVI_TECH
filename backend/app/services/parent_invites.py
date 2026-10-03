"""Parent invitation delivery.

Deliberately a stub: NOVI has no transactional email provider wired up yet, and
building one here would put credentials and retry/queue semantics in the middle
of the consent flow. The interface exists so the linking code stays honest about
the one thing it must never do -- persist a usable invite token.

Contract for a real implementation:

* Receive the RAW token and hash it yourself (or use ``hash_invite_token``).
* Never log, echo, or persist the raw token beyond the duration of the send.
* Never reveal, in any user-facing error, whether an address has an account.
"""

import logging

from app.models.user import hash_invite_token

logger = logging.getLogger("novi.parent_invites")


class InviteSender:
    """Interface for delivering a parent invitation to a student."""

    def send_parent_invite(
        self,
        *,
        to_email: str,
        parent_name: str,
        raw_token: str,
        expires_at: object,
    ) -> bool:
        raise NotImplementedError


class LoggingInviteSender(InviteSender):
    """Default sender: logs a redacted notice and reports success.

    Treats "logged" as delivered so the linking flow is testable end to end
    without an email provider. Swap this out via dependency injection once a real
    provider exists.
    """

    def send_parent_invite(
        self,
        *,
        to_email: str,
        parent_name: str,
        raw_token: str,
        expires_at: object,
    ) -> bool:
        logger.info(
            "parent invite queued to=%s parent=%s expires_at=%s token=%s",
            to_email,
            parent_name,
            expires_at,
            hash_invite_token(raw_token)[:8],
        )
        return True


_default_sender = LoggingInviteSender()


def get_invite_sender() -> InviteSender:
    return _default_sender


def set_invite_sender(sender: InviteSender) -> None:
    """Inject a real sender (used by tests and future wiring)."""
    global _default_sender
    _default_sender = sender