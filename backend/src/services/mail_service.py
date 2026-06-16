from __future__ import annotations

import asyncio
from typing import Optional

import mailtrap as mt

from ..config import load_env, mail_config


class MailService:
    @staticmethod
    def _sender_email() -> str:
        return mail_config().sender_email

    @staticmethod
    def _sender_name() -> str:
        return mail_config().sender_name

    @staticmethod
    def _api_key() -> str:
        key = mail_config().mailtrap_api_key
        if not key:
            raise RuntimeError("MAILTRAP_API_KEY is not set")
        return key

    @staticmethod
    def _support_receiver_email() -> str:
        receiver = (mail_config().support_receiver_email or "").strip()
        if not receiver:
            raise RuntimeError("SUPPORT_MAIL_RECEIVER is not set")
        return receiver

    @staticmethod
    def _support_sender_name() -> str:
        return mail_config().support_sender_name

    @staticmethod
    async def send_new_password_email(
        *,
        to_email: str,
        to_name: Optional[str],
        new_password: str,
    ) -> None:
        """
        Sends a plaintext email containing the newly generated password.
        (Per project requirement for the first iteration.)
        """
        load_env()
        to_email = (to_email or "").strip()
        if not to_email:
            raise ValueError("to_email_empty")

        sender_email = MailService._sender_email()
        sender_name = MailService._sender_name()
        api_key = MailService._api_key()

        name = (to_name or "").strip() or to_email
        subject = "Şifreniz yenilendi"
        body = (
            "Şifreniz yenilenmiştir.\n\n"
            f"Yeni şifreniz: {new_password}\n\n"
            "Giriş yaptıktan sonra lütfen şifrenizi değiştirin."
        )

        mail = mt.Mail(
            sender=mt.Address(email=sender_email, name=sender_name),
            to=[mt.Address(email=to_email, name=name)],
            subject=subject,
            text=body,
        )

        def _send() -> None:
            client = mt.MailtrapClient(token=api_key)
            client.send(mail)

        await asyncio.to_thread(_send)

    @staticmethod
    async def send_password_reset_email(
        *,
        to_email: str,
        to_name: Optional[str],
        reset_url: str,
    ) -> None:
        load_env()
        to_email = (to_email or "").strip()
        reset_url = (reset_url or "").strip()
        if not to_email:
            raise ValueError("to_email_empty")
        if not reset_url:
            raise ValueError("reset_url_empty")

        sender_email = MailService._sender_email()
        sender_name = MailService._sender_name()
        api_key = MailService._api_key()

        name = (to_name or "").strip() or to_email
        subject = "Şifre sıfırlama bağlantınız"
        body = (
            "Şifrenizi sıfırlamak için aşağıdaki bağlantıyı kullanın.\n\n"
            f"{reset_url}\n\n"
            "Bu bağlantı tek kullanımlıktır ve süresi sınırlıdır."
        )

        mail = mt.Mail(
            sender=mt.Address(email=sender_email, name=sender_name),
            to=[mt.Address(email=to_email, name=name)],
            subject=subject,
            text=body,
        )

        def _send() -> None:
            client = mt.MailtrapClient(token=api_key)
            client.send(mail)

        await asyncio.to_thread(_send)

    @staticmethod
    async def send_child_account_created_email(
        *,
        to_email: str,
        to_name: Optional[str],
        parent_name: str,
        username: str,
        password: str,
        credit: float,
    ) -> None:
        load_env()
        to_email = (to_email or "").strip()
        username = (username or "").strip()
        password = str(password or "").strip()
        parent_name = (parent_name or "").strip() or "Üst hesap"
        if not to_email:
            raise ValueError("to_email_empty")
        if not username:
            raise ValueError("username_empty")
        if not password:
            raise ValueError("password_empty")

        sender_email = MailService._sender_email()
        sender_name = MailService._sender_name()
        api_key = MailService._api_key()

        name = (to_name or "").strip() or to_email
        credit_text = f"{float(credit):.2f}".replace(".", ",")
        subject = f"{parent_name} tarafından Yargucu hesabınız oluşturuldu"
        body = (
            f"Merhaba {name},\n\n"
            f"{parent_name} tarafından sizin için bir Yargucu hesabı oluşturuldu.\n\n"
            "Giriş bilgileriniz:\n"
            f"Kullanıcı adı: {username}\n"
            f"Şifre: {password}\n"
            f"Kredi: {credit_text}\n\n"
            "İlk girişten sonra şifrenizi değiştirmenizi öneririz."
        )

        mail = mt.Mail(
            sender=mt.Address(email=sender_email, name=sender_name),
            to=[mt.Address(email=to_email, name=name)],
            subject=subject,
            text=body,
        )

        def _send() -> None:
            client = mt.MailtrapClient(token=api_key)
            client.send(mail)

        await asyncio.to_thread(_send)

    @staticmethod
    async def send_calendar_reminder_email(
        *,
        to_email: str,
        to_name: Optional[str],
        title: str,
        due_date: str,
        due_time: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """
        Sends a reminder email ~1 day before a calendar event is due.
        Plain text body, Turkish content (matches the app's primary locale).
        """
        load_env()
        to_email = (to_email or "").strip()
        title = (title or "Etkinlik").strip()
        due_date = (due_date or "").strip()
        if not to_email:
            raise ValueError("to_email_empty")
        if not due_date:
            raise ValueError("due_date_empty")

        sender_email = MailService._sender_email()
        sender_name = MailService._sender_name()
        api_key = MailService._api_key()

        name = (to_name or "").strip() or to_email
        due_time = (due_time or "").strip()
        note = (note or "").strip()

        when_str = due_date if not due_time else f"{due_date} {due_time}"
        subject = f"Hatırlatma: yarın {title}"

        lines = [
            f"Merhaba {name},",
            "",
            "Yargucu takviminize göre yarın için planlanmış bir etkinliğiniz var.",
            "",
            f"Başlık : {title}",
            f"Tarih  : {when_str}",
        ]
        if note:
            lines.extend([f"Not    : {note}"])
        lines.extend([
            "",
            "Etkinlik tamamlandıysa Yargucu üzerinden 'Tamamlandı' olarak işaretleyebilirsiniz.",
            "",
            "Saygılarımızla,",
            "Yargucu",
        ])
        body = "\n".join(lines)

        mail = mt.Mail(
            sender=mt.Address(email=sender_email, name=sender_name),
            to=[mt.Address(email=to_email, name=name)],
            subject=subject,
            text=body,
        )

        def _send() -> None:
            client = mt.MailtrapClient(token=api_key)
            client.send(mail)

        await asyncio.to_thread(_send)

    @staticmethod
    async def send_calendar_alarm_email(
        *,
        to_email: str,
        to_name: Optional[str],
        title: str,
        due_date: str,
        due_time: Optional[str] = None,
        note: Optional[str] = None,
        hours_remaining: int = 4,
    ) -> None:
        """
        Sends a follow-up "alarm" reminder a few hours (default ~4) before a
        calendar event is due. Designed as a stronger nudge than the 24h
        reminder — Turkish copy, plain text body, alarm clock glyph in the
        subject so it's easy to spot in an inbox.
        """
        load_env()
        to_email = (to_email or "").strip()
        title = (title or "Etkinlik").strip()
        due_date = (due_date or "").strip()
        if not to_email:
            raise ValueError("to_email_empty")
        if not due_date:
            raise ValueError("due_date_empty")

        sender_email = MailService._sender_email()
        sender_name = MailService._sender_name()
        api_key = MailService._api_key()

        name = (to_name or "").strip() or to_email
        due_time = (due_time or "").strip()
        note = (note or "").strip()
        try:
            hours = max(1, int(hours_remaining))
        except Exception:
            hours = 4

        when_str = due_date if not due_time else f"{due_date} {due_time}"
        # ⏰ glyph keeps the visual cue without HTML — works in any mail client.
        subject = f"\u23F0 Uyarı: {hours} saat içinde {title}"

        lines = [
            f"Merhaba {name},",
            "",
            f"Yargucu takviminize göre yaklaşık {hours} saat içinde planlanmış bir etkinliğiniz var.",
            "Bu, daha önce iletilen hatırlatmanın takip uyarısıdır.",
            "",
            f"Başlık : {title}",
            f"Tarih  : {when_str}",
        ]
        if note:
            lines.append(f"Not    : {note}")
        lines.extend([
            "",
            "Etkinlik tamamlandıysa Yargucu üzerinden 'Tamamlandı' olarak işaretleyebilirsiniz.",
            "",
            "Saygılarımızla,",
            "Yargucu",
        ])
        body = "\n".join(lines)

        mail = mt.Mail(
            sender=mt.Address(email=sender_email, name=sender_name),
            to=[mt.Address(email=to_email, name=name)],
            subject=subject,
            text=body,
        )

        def _send() -> None:
            client = mt.MailtrapClient(token=api_key)
            client.send(mail)

        await asyncio.to_thread(_send)

    @staticmethod
    async def send_support_email(
        *,
        subject: str,
        body: str,
    ) -> None:
        load_env()
        subject = (subject or "").strip()
        body = (body or "").strip()
        if not subject:
            raise ValueError("subject_empty")
        if not body:
            raise ValueError("body_empty")

        sender_email = MailService._sender_email()
        sender_name = MailService._support_sender_name()
        receiver_email = MailService._support_receiver_email()
        api_key = MailService._api_key()

        mail = mt.Mail(
            sender=mt.Address(email=sender_email, name=sender_name),
            to=[mt.Address(email=receiver_email, name=sender_name)],
            subject=subject,
            text=body,
        )

        def _send() -> None:
            client = mt.MailtrapClient(token=api_key)
            client.send(mail)

        await asyncio.to_thread(_send)

