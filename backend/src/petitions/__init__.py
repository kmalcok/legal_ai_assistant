"""
Petition generation pipeline:
- Main agent prepares an intake JSON (from conversation).
- Petition LLM (gpt-5.2) produces a strict output JSON (schema constrained).
- Server renders DOCX (python-docx) and stores blob in MariaDB.
- Frontend is notified over websocket per chat channel: chat:{chat_id}.
"""


