"""How the app was made: shown under the heading of the home page.

``AI_WORK_HOURS`` is the AI's net working time, counted from the Claude Code session logs of
this project: every interval between log entries (model answers and tool runs), without the
waits for a human prompt and without pauses longer than 10 minutes; sub-agents running in
parallel counted once. Update it together with ``AS_OF`` when the app is extended.
"""

from __future__ import annotations

GUIDED_BY = "fgrander"
AI_MODEL = "Claude (Anthropic)"
AI_WORK_HOURS = 9.7
AS_OF = "2026-10-26"
