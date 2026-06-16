from __future__ import annotations

from typing import Final

from ..util.instruction_loader import load_instruction_text

INSTRUCTIONS_TR: Final[str] = load_instruction_text("law_agentv2.md")
STUDENT_INSTRUCTIONS_TR: Final[str] = load_instruction_text("law_agent_student.md")
PETITION_ADDENDUM_TR: Final[str] = load_instruction_text("petition_agent.md")

# Handoff guidance injected into the main (supervisor) agent so it delegates
# dilekçe work to the petition agent instead of drafting it inline.
MAIN_AGENT_HANDOFF_NOTE_TR: Final[str] = (
    "# ÇOK-AJANLI ÇALIŞMA – DEVİR (HANDOFF)\n\n"
    "Bu sistem çok-ajanlıdır ve paylaşılan bir durum (shared state) üzerinde çalışır.\n"
    "Sen ANA HUKUK ASİSTANI (supervisor) rolündesin. Bir DİLEKÇE AJANI ile birlikte çalışıyorsun.\n\n"
    "- Kullanıcı bir dilekçenin OLUŞTURULMASINI, REVİZE EDİLMESİNİ, ÖZETLENMESİNİ ya da bir "
    "dilekçeye bağlı süre/zamanaşımı takviminin işlenmesini istediğinde, bu işi kendin yapma; "
    "`transfer_to_petition_agent` aracıyla kontrolü DİLEKÇE AJANINA devret.\n"
    "- Devirden önce, somut olayı/talebi ve varsa seçili içtihatları sohbet içinde netleştir; "
    "bunlar paylaşılan durum üzerinden dilekçe ajanına aktarılır.\n"
    "- Dilekçe dışı tüm hukuki analiz, mevzuat/içtihat araştırması ve genel sorular sende kalır.\n"
)


def build_instructions() -> str:
    return INSTRUCTIONS_TR.strip()


def build_student_instructions() -> str:
    return STUDENT_INSTRUCTIONS_TR.strip()


def build_main_agent_instructions() -> str:
    """Main (supervisor) agent prompt = base law instructions + handoff guidance."""
    return (INSTRUCTIONS_TR.strip() + "\n\n---\n\n" + MAIN_AGENT_HANDOFF_NOTE_TR.strip()).strip()


def build_petition_instructions() -> str:
    """
    Petition agent prompt. Per the migration plan we copy the full base law
    instructions verbatim and append the petition-role addendum, so the petition
    agent keeps all of Yargucu's legal-reasoning rules.
    """
    return (INSTRUCTIONS_TR.strip() + "\n\n---\n\n" + PETITION_ADDENDUM_TR.strip()).strip()


