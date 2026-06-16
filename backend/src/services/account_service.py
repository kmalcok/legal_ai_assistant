from __future__ import annotations

import asyncio
import secrets
import string
from decimal import Decimal
from typing import Any, Dict, Optional

from ..ai.memory.redis_memory import RedisMemory
from ..data.db_account_repository import (
    ACCOUNT_TYPE_CHILD,
    ACCOUNT_TYPE_PARENT,
    ACCOUNT_TYPE_STANDALONE,
    AccountRepository,
    DEFAULT_CHILD_LIMITS_BY_PLAN,
)
from ..data.db_auth_repository import AuthRepository
from ..data.db_user_repository import UserRepository
from ..security.passwords import hash_password
from ..db import core_db
from ..utils.credit_conversion import credit_to_usd, usd_to_credit
from ..utils.ephemeral_store import ephemeral_files
from ..api.errors import api_error, status_for_reason


def _generate_temp_password(length: int = 12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%?"
    size = max(8, int(length or 12))
    return "".join(secrets.choice(alphabet) for _ in range(size))


def _serialize_account_profile(account: Dict[str, Any]) -> Dict[str, Any]:
    credit_summary = account.get("credit_summary") or {}
    managed_children = account.get("managed_children") or {}
    items = managed_children.get("items") or []
    account_plan = account.get("account_plan")

    return {
        "user_id": int(account["user_id"]),
        "username": account.get("username"),
        "email": account.get("email"),
        "full_name": account.get("full_name"),
        "phone": account.get("phone"),
        "created_at": account.get("created_at"),
        "account_type": account.get("account_type"),
        "account_plan": account_plan,
        "parent_user_id": account.get("parent_user_id"),
        "parent_username": account.get("parent_username"),
        "child_account_limit_override": account.get("child_account_limit_override"),
        "credit": usd_to_credit(credit_summary.get("available_credit"), account_plan=account_plan),
        "credit_summary": {
            "available_credit": usd_to_credit(credit_summary.get("available_credit"), account_plan=account_plan),
            "reserved_credit": usd_to_credit(credit_summary.get("reserved_credit"), account_plan=account_plan),
            "total_credit": usd_to_credit(credit_summary.get("total_credit"), account_plan=account_plan),
        },
        "managed_children": {
            "count": int(managed_children.get("count") or 0),
            "limit": int(managed_children.get("limit") or 0),
            "items": [
                {
                    **item,
                    "credit": usd_to_credit(item.get("credit"), account_plan=item.get("account_plan")),
                    "allocated_credit": usd_to_credit(item.get("allocated_credit"), account_plan=item.get("account_plan")),
                }
                for item in items
                if isinstance(item, dict)
            ],
        },
        "permissions": {
            "can_manage_children": str(account.get("account_type")) == ACCOUNT_TYPE_PARENT,
            "can_delete_account": str(account.get("account_type")) != ACCOUNT_TYPE_CHILD,
            "can_wipe_data": True,
        },
    }


class AccountService:
    @staticmethod
    def build_user_profile(*, user_id: int) -> Dict[str, Any]:
        account = AccountRepository.get_user_account(int(user_id))
        if not account:
            raise ValueError("user_not_found")
        return _serialize_account_profile(account)

    @staticmethod
    def create_child_account(
        *,
        parent_user_id: int,
        username: str,
        email: str,
        full_name: str,
        password_hash: str,
        allocated_credit: float = 0.0,
    ) -> Dict[str, Any]:
        parent = AccountRepository.get_user_account(int(parent_user_id))
        if not parent:
            raise ValueError("user_not_found")
        child_plan = parent.get("account_plan")
        child_user_id = AccountRepository.create_child_account(
            parent_user_id=int(parent_user_id),
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            allocated_credit_usd=credit_to_usd(allocated_credit, account_plan=child_plan),
        )
        child = AccountRepository.get_child_account(parent_user_id=int(parent_user_id), child_user_id=int(child_user_id))
        if not child:
            raise ValueError("user_not_found")
        child_plan = child.get("account_plan")
        return {
            "user_id": int(child["user_id"]),
            "username": child.get("username"),
            "email": child.get("email"),
            "full_name": child.get("full_name"),
            "account_type": child.get("account_type"),
            "account_plan": child_plan,
            "parent_user_id": child.get("parent_user_id"),
            "credit": usd_to_credit(child.get("balance_usd"), account_plan=child_plan),
            "allocated_credit": usd_to_credit(child.get("allocated_balance_usd"), account_plan=child_plan),
            "created_at": child.get("created_at"),
        }

    @staticmethod
    def set_child_credit(*, parent_user_id: int, child_user_id: int, desired_credit: float) -> Dict[str, Any]:
        parent = AccountRepository.get_user_account(int(parent_user_id))
        child = AccountRepository.get_child_account(parent_user_id=int(parent_user_id), child_user_id=int(child_user_id))
        if not parent or not child:
            raise ValueError("child_not_found")
        parent_plan = parent.get("account_plan")
        child_plan = child.get("account_plan")
        result = AccountRepository.set_child_credit_balance(
            parent_user_id=int(parent_user_id),
            child_user_id=int(child_user_id),
            desired_balance_usd=credit_to_usd(desired_credit, account_plan=child_plan),
        )
        child = AccountRepository.get_child_account(parent_user_id=int(parent_user_id), child_user_id=int(child_user_id))
        if not child:
            raise ValueError("child_not_found")
        child_plan = child.get("account_plan")
        return {
            "parent_available_credit": usd_to_credit(result.get("parent_available_credit"), account_plan=parent_plan),
            "child_credit": usd_to_credit(result.get("child_credit"), account_plan=child_plan),
            "allocated_credit": usd_to_credit(result.get("allocated_credit"), account_plan=child_plan),
            "child": {
                "user_id": int(child["user_id"]),
                "username": child.get("username"),
                "email": child.get("email"),
                "full_name": child.get("full_name"),
                "account_plan": child_plan,
                "credit": usd_to_credit(child.get("balance_usd"), account_plan=child_plan),
                "allocated_credit": usd_to_credit(child.get("allocated_balance_usd"), account_plan=child_plan),
            },
        }


class UserDataWipeService:
    @staticmethod
    def _list_chat_ids(*, user_id: int) -> list[int]:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT chat_id FROM chats WHERE user_id=%s", (int(user_id),))
            rows = cur.fetchall() or []
            return [int(row[0]) for row in rows if row and row[0] is not None]

    @staticmethod
    async def wipe_user_data(*, user_id: int) -> Dict[str, Any]:
        chat_ids = UserDataWipeService._list_chat_ids(user_id=int(user_id))
        redis_memory = RedisMemory()
        cleared_chat_memory = 0
        cleared_ephemeral_files = 0

        for chat_id in chat_ids:
            try:
                await redis_memory.clear(int(chat_id))
                cleared_chat_memory += 1
            except Exception:
                pass
            try:
                cleared_ephemeral_files += int(
                    await ephemeral_files.purge_chat(chat_id=int(chat_id), user_id=int(user_id))
                )
            except Exception:
                pass

        def _wipe() -> Dict[str, Any]:
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM user_usages WHERE user_id=%s", (int(user_id),))
                deleted_user_usages = int(cur.rowcount or 0)
                cur.execute("DELETE FROM ictihat_search_history WHERE user_id=%s", (int(user_id),))
                deleted_history = int(cur.rowcount or 0)
                try:
                    cur.execute("DELETE FROM chat_context_items WHERE user_id=%s", (int(user_id),))
                    deleted_context_items = int(cur.rowcount or 0)
                except Exception:
                    deleted_context_items = 0
                cur.execute("DELETE FROM petitions WHERE user_id=%s", (int(user_id),))
                deleted_petitions = int(cur.rowcount or 0)
                cur.execute("DELETE FROM documents WHERE user_id=%s", (int(user_id),))
                deleted_documents = int(cur.rowcount or 0)
                cur.execute("DELETE FROM chats WHERE user_id=%s", (int(user_id),))
                deleted_chats = int(cur.rowcount or 0)
                conn.commit()
                return {
                    "deleted_chats": deleted_chats,
                    "deleted_documents": deleted_documents,
                    "deleted_petitions": deleted_petitions,
                    "deleted_history": deleted_history,
                    "deleted_user_usages": deleted_user_usages,
                    "deleted_chat_context_items": deleted_context_items,
                }

        deleted = await asyncio.to_thread(_wipe)
        deleted["cleared_chat_memory"] = int(cleared_chat_memory)
        deleted["cleared_ephemeral_files"] = int(cleared_ephemeral_files)
        return deleted


class AccountDeletionService:
    @staticmethod
    async def _delete_single_user(*, user_id: int, refund_parent_user_id: Optional[int]) -> None:
        if refund_parent_user_id is not None:
            try:
                AccountRepository.set_child_credit_balance(
                    parent_user_id=int(refund_parent_user_id),
                    child_user_id=int(user_id),
                    desired_balance_usd=Decimal("0.000000"),
                )
            except ValueError:
                pass

        await UserDataWipeService.wipe_user_data(user_id=int(user_id))
        await asyncio.to_thread(AccountRepository.delete_support_mail_rows, user_id=int(user_id))
        await asyncio.to_thread(AuthRepository.revoke_password_reset_tokens_for_user, user_id=int(user_id))
        await asyncio.to_thread(AuthRepository.revoke_all_refresh_tokens_for_user, user_id=int(user_id))
        await asyncio.to_thread(AuthRepository.bump_token_version, user_id=int(user_id))

        def _delete_user_row() -> None:
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM users WHERE user_id=%s", (int(user_id),))
                conn.commit()

        await asyncio.to_thread(_delete_user_row)

    @staticmethod
    async def delete_account(*, actor_user_id: int, target_user_id: int) -> Dict[str, Any]:
        actor = AccountRepository.get_user_account(int(actor_user_id))
        target = AccountRepository.get_user_account(int(target_user_id))
        if not actor or not target:
            raise ValueError("user_not_found")

        actor_id = int(actor["user_id"])
        target_id = int(target["user_id"])
        target_type = str(target.get("account_type") or "")

        if target_type == ACCOUNT_TYPE_CHILD:
            parent_user_id = int(target.get("parent_user_id") or 0)
            if actor_id == target_id:
                raise ValueError("child_account_delete_forbidden")
            if actor_id != parent_user_id:
                raise ValueError("forbidden")
            await AccountDeletionService._delete_single_user(
                user_id=target_id,
                refund_parent_user_id=parent_user_id,
            )
            return {"deleted_user_id": target_id, "deleted_account_type": target_type, "cascade_count": 0}

        if actor_id != target_id:
            raise ValueError("forbidden")

        if target_type == ACCOUNT_TYPE_PARENT:
            children = AccountRepository.list_children(parent_user_id=target_id)
            for child in children:
                child_user_id = int(child["user_id"])
                await AccountDeletionService._delete_single_user(
                    user_id=child_user_id,
                    refund_parent_user_id=None,
                )
            await AccountDeletionService._delete_single_user(user_id=target_id, refund_parent_user_id=None)
            return {
                "deleted_user_id": target_id,
                "deleted_account_type": target_type,
                "cascade_count": len(children),
            }

        await AccountDeletionService._delete_single_user(user_id=target_id, refund_parent_user_id=None)
        return {"deleted_user_id": target_id, "deleted_account_type": target_type or "standalone", "cascade_count": 0}

    @staticmethod
    async def delete_account_as_admin(*, target_user_id: int) -> Dict[str, Any]:
        target = AccountRepository.get_user_account(int(target_user_id))
        if not target:
            raise ValueError("user_not_found")

        target_id = int(target["user_id"])
        target_type = str(target.get("account_type") or ACCOUNT_TYPE_STANDALONE)

        if target_type == ACCOUNT_TYPE_CHILD:
            raise ValueError("child_account_delete_forbidden")

        if target_type == ACCOUNT_TYPE_PARENT:
            children = AccountRepository.list_children(parent_user_id=target_id)
            for child in children:
                child_user_id = int(child["user_id"])
                await AccountDeletionService._delete_single_user(
                    user_id=child_user_id,
                    refund_parent_user_id=None,
                )
            await AccountDeletionService._delete_single_user(user_id=target_id, refund_parent_user_id=None)
            return {
                "deleted_user_id": target_id,
                "deleted_account_type": target_type,
                "cascade_count": len(children),
            }

        await AccountDeletionService._delete_single_user(user_id=target_id, refund_parent_user_id=None)
        return {"deleted_user_id": target_id, "deleted_account_type": target_type or ACCOUNT_TYPE_STANDALONE, "cascade_count": 0}


class AdminAccountService:
    @staticmethod
    def list_accounts(*, account_types: Optional[list[str]] = None, query: str = "") -> list[Dict[str, Any]]:
        accounts = AccountRepository.list_admin_accounts(account_types=account_types, query=query, limit=200)
        return [_serialize_account_profile(account) for account in accounts if isinstance(account, dict)]

    @staticmethod
    def create_account(
        *,
        username: str,
        email: str,
        full_name: str,
        password_hash: str,
        account_type: str,
        account_plan: str,
        initial_credit: float = 0.0,
    ) -> Dict[str, Any]:
        user_id = AccountRepository.create_admin_account(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            account_type=account_type,
            account_plan=account_plan,
        )
        AccountRepository.set_available_credit_balance(
            user_id=int(user_id),
            desired_balance_usd=credit_to_usd(initial_credit, account_plan=account_plan),
            allowed_account_types=[str(account_type or "").strip().lower()],
        )
        account = AccountRepository.get_user_account(int(user_id))
        if not account:
            raise ValueError("user_not_found")
        return _serialize_account_profile(account)

    @staticmethod
    def set_account_credit(*, user_id: int, desired_credit: float) -> Dict[str, Any]:
        account = AccountRepository.get_user_account(int(user_id))
        if not account:
            raise ValueError("user_not_found")

        account_type = str(account.get("account_type") or ACCOUNT_TYPE_STANDALONE)
        account_plan = account.get("account_plan")
        previous_credit = float(account.get("credit_summary", {}).get("available_credit") or 0.0)

        if account_type == ACCOUNT_TYPE_CHILD:
            parent_user_id = int(account.get("parent_user_id") or 0)
            if parent_user_id <= 0:
                raise ValueError("parent_required")
            parent = AccountRepository.get_user_account(int(parent_user_id))
            if not parent:
                raise ValueError("user_not_found")
            result = AccountRepository.set_child_credit_balance(
                parent_user_id=parent_user_id,
                child_user_id=int(user_id),
                desired_balance_usd=credit_to_usd(desired_credit, account_plan=account_plan),
            )
            current_credit = float(result.get("child_credit") or 0.0)
        else:
            result = AccountRepository.set_available_credit_balance(
                user_id=int(user_id),
                desired_balance_usd=credit_to_usd(desired_credit, account_plan=account_plan),
                allowed_account_types=[ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT],
            )
            current_credit = float(result.get("balance_usd") or 0.0)

        account = AccountRepository.get_user_account(int(user_id))
        if not account:
            raise ValueError("user_not_found")
        return {
            "previous_credit": usd_to_credit(previous_credit, account_plan=account_plan),
            "current_credit": usd_to_credit(current_credit, account_plan=account_plan),
            "account": _serialize_account_profile(account),
        }

    @staticmethod
    def update_user_account_profile(
        *,
        user_id: int,
        account_type: Optional[str] = None,
        account_plan: Optional[str] = None,
    ) -> Dict[str, Any]:
        if account_type is None and account_plan is None:
            raise ValueError("no_patch_fields")

        account = AccountRepository.get_user_account(int(user_id))
        if not account:
            raise ValueError("user_not_found")

        cur_type = str(account.get("account_type") or ACCOUNT_TYPE_STANDALONE).strip().lower()
        cur_plan = str(account.get("account_plan") or "").strip().lower() or "free"
        parent_raw = account.get("parent_user_id")
        try:
            parent_user_id = int(parent_raw) if parent_raw is not None else 0
        except (TypeError, ValueError):
            parent_user_id = 0

        next_type = (
            str(account_type or "").strip().lower()
            if account_type is not None
            else cur_type
        )
        next_plan = (
            str(account_plan or "").strip().lower()
            if account_plan is not None
            else cur_plan
        )

        if next_type not in {ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT, ACCOUNT_TYPE_CHILD}:
            raise ValueError("invalid_account_type")
        if next_plan not in DEFAULT_CHILD_LIMITS_BY_PLAN:
            raise ValueError("invalid_account_plan")

        clear_parent = False
        if next_type != cur_type:
            if next_type == ACCOUNT_TYPE_CHILD:
                raise ValueError("invalid_account_type_transition")
            if cur_type == ACCOUNT_TYPE_CHILD and next_type != ACCOUNT_TYPE_CHILD:
                if parent_user_id > 0:
                    try:
                        AccountRepository.set_child_credit_balance(
                            parent_user_id=int(parent_user_id),
                            child_user_id=int(user_id),
                            desired_balance_usd=Decimal("0.000000"),
                        )
                    except ValueError as exc:
                        raise ValueError("child_credit_detach_failed") from exc
                clear_parent = True
            elif cur_type == ACCOUNT_TYPE_PARENT and next_type == ACCOUNT_TYPE_STANDALONE:
                if AccountRepository.admin_count_managed_children(parent_user_id=int(user_id)) > 0:
                    raise ValueError("parent_has_children")

        AccountRepository.admin_apply_user_account_update(
            user_id=int(user_id),
            account_type=next_type,
            account_plan=next_plan,
            clear_parent_user_id=clear_parent,
        )

        refreshed = AccountRepository.get_user_account(int(user_id))
        if not refreshed:
            raise ValueError("user_not_found")
        return _serialize_account_profile(refreshed)

    @staticmethod
    def reset_password(*, user_id: int) -> Dict[str, Any]:
        account = AccountRepository.get_user_account(int(user_id))
        if not account:
            raise ValueError("user_not_found")

        temp_password = _generate_temp_password(12)
        password_hash = hash_password(temp_password)
        UserRepository.update_password_hash(user_id=int(user_id), password_hash=password_hash)

        try:
            AuthRepository.revoke_all_refresh_tokens_for_user(user_id=int(user_id))
        except Exception:
            pass
        try:
            AuthRepository.bump_token_version(user_id=int(user_id))
        except Exception:
            pass

        refreshed = AccountRepository.get_user_account(int(user_id))
        if not refreshed:
            raise ValueError("user_not_found")

        return {
            "temp_password": temp_password,
            "account": _serialize_account_profile(refreshed),
        }

    @staticmethod
    async def delete_account(*, user_id: int) -> Dict[str, Any]:
        return await AccountDeletionService.delete_account_as_admin(target_user_id=int(user_id))


def raise_account_reason(reason: str) -> None:
    raise api_error(status_for_reason(reason), reason)
