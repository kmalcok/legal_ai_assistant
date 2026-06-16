from .repository import CalendarRepository
from .service import register_from_petition, add_event_for_user
from .parser import extract_deadlines_from_header_blocks
# NOTE: `reminder` is intentionally NOT re-exported here.
# Importing it pulls in MailService -> services/__init__.py -> agent_service ->
# law_agent -> tool_wrappers.petitions, which itself imports from this package
# during the petition wrapper's module-load phase => circular import.
# Consumers (e.g. app.py startup) should import the loop directly:
#   from ..calendar_events.reminder import run_reminder_loop

__all__ = [
    "CalendarRepository",
    "register_from_petition",
    "add_event_for_user",
    "extract_deadlines_from_header_blocks",
]
