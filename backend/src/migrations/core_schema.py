from __future__ import annotations

from contextlib import nullcontext
from typing import Dict, Iterable, List, Tuple

from ..config import load_env



CORE_TABLE_DDL: Dict[str, str] = {
    "app_config": """
CREATE TABLE IF NOT EXISTS `app_config` (
  `config_key` varchar(64) NOT NULL,
  `value_bool` tinyint(1) DEFAULT NULL,
  `value_decimal` decimal(18,6) DEFAULT NULL,
  `value_text` varchar(1024) DEFAULT NULL,
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    # Minimal users table
    "users": """
CREATE TABLE IF NOT EXISTS `users` (
  `user_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(64) NOT NULL,
  `email` varchar(255) DEFAULT NULL,
  `full_name` varchar(255) DEFAULT NULL,
  `phone` varchar(32) DEFAULT NULL,
  `password_hash` varchar(255) NOT NULL,
  `account_type` enum('standalone','parent','child') NOT NULL DEFAULT 'standalone',
  `account_plan` enum('free','student','starter','standard','advanced','professional','enterprise') NOT NULL DEFAULT 'free',
  `parent_user_id` bigint(20) unsigned DEFAULT NULL,
  `child_account_limit_override` int(10) unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_users_username` (`username`),
  UNIQUE KEY `uq_users_email` (`email`),
  KEY `idx_users_account_type` (`account_type`),
  KEY `idx_users_parent` (`parent_user_id`),
  CONSTRAINT `fk_users_parent_user` FOREIGN KEY (`parent_user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "chats": """
CREATE TABLE IF NOT EXISTS `chats` (
  `chat_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `title` varchar(512) DEFAULT NULL,
  `first_message` longtext DEFAULT NULL,
  `last_sum` longtext DEFAULT NULL,
  `archived` tinyint(1) NOT NULL DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`chat_id`),
  KEY `idx_chats_user` (`user_id`),
  KEY `idx_chats_updated` (`updated_at`),
  CONSTRAINT `fk_chats_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "chat_messages": """
CREATE TABLE IF NOT EXISTS `chat_messages` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `chat_id` bigint(20) unsigned NOT NULL,
  `role` enum('user','assistant','system','tool') NOT NULL,
  `message` longtext NOT NULL,
  `reasoning` longtext NOT NULL DEFAULT '',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_msgs_chat` (`chat_id`),
  KEY `idx_msgs_created` (`created_at`),
  CONSTRAINT `fk_msgs_chat` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`chat_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    # Message-scoped ictihat attachment (one JSON array per message id).
    # NOTE: Column is named `chat_id` for historical reasons; it stores chat_messages.id
    # (foreign-keyed) and acts as the primary identifier for the attached ictihat list.
    "chat_message_ictihat": """
CREATE TABLE IF NOT EXISTS `chat_message_ictihat` (
  `chat_id` bigint(20) unsigned NOT NULL,
  `ictihat_list_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`ictihat_list_json`)),
  UNIQUE KEY `uq_cmi_chat_id` (`chat_id`),
  KEY `idx_cmi_chat_id` (`chat_id`),
  CONSTRAINT `fk_cmi_chat_message` FOREIGN KEY (`chat_id`) REFERENCES `chat_messages` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "chat_context_items": """
CREATE TABLE IF NOT EXISTS `chat_context_items` (
  `context_item_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `chat_id` bigint(20) unsigned NOT NULL,
  `message_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `kind` varchar(32) NOT NULL,
  `source` varchar(16) NOT NULL DEFAULT 'ui',
  `sort_order` int(11) NOT NULL DEFAULT 0,
  `payload_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`payload_json`)),
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`context_item_id`),
  KEY `idx_cci_chat_created` (`chat_id`,`created_at`),
  KEY `idx_cci_message` (`message_id`),
  KEY `idx_cci_user_chat` (`user_id`,`chat_id`),
  KEY `idx_cci_kind` (`kind`),
  CONSTRAINT `fk_cci_chat` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`chat_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_cci_message` FOREIGN KEY (`message_id`) REFERENCES `chat_messages` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_cci_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "ictihat_search_history": """
CREATE TABLE IF NOT EXISTS `ictihat_search_history` (
  `history_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `search_type` varchar(16) NOT NULL,
  `query_text` text DEFAULT NULL,
  `filters_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (`filters_json` is null or json_valid(`filters_json`)),
  `top_k` int(11) NOT NULL DEFAULT 5,
  `result_count` int(11) NOT NULL DEFAULT 0,
  `return_items_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (`return_items_json` is null or json_valid(`return_items_json`)),
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`history_id`),
  KEY `idx_ish_user_created` (`user_id`,`created_at`),
  KEY `idx_ish_user_type` (`user_id`,`search_type`,`created_at`),
  CONSTRAINT `fk_ish_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "user_usages": """
CREATE TABLE IF NOT EXISTS `user_usages` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `chat_id` bigint(20) unsigned DEFAULT NULL,
  `chat_message_id` bigint(20) unsigned DEFAULT NULL,
  `type` enum('input_tokens','output_tokens','reasoning_tokens') NOT NULL,
  `model` varchar(64) DEFAULT NULL,
  `amount` int(11) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_usage_user` (`user_id`),
  KEY `idx_usage_chat` (`chat_id`),
  KEY `idx_usage_created` (`created_at`),
  KEY `idx_usage_chat_message` (`chat_message_id`),
  CONSTRAINT `fk_usage_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_usage_chat` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`chat_id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_usage_chat_message` FOREIGN KEY (`chat_message_id`) REFERENCES `chat_messages` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    # user_tool_usages kaldirildi - tum kullanim token bazinda user_usages tablosuna kaydedilir.
    # Tablo DB'de hala mevcut olabilir; yeni kurulumlar icin olusturulmaz.
    "auth_refresh_tokens": """
CREATE TABLE IF NOT EXISTS `auth_refresh_tokens` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `jti` char(36) NOT NULL,
  `issued_at` datetime NOT NULL DEFAULT current_timestamp(),
  `expires_at` datetime NOT NULL,
  `revoked` tinyint(1) NOT NULL DEFAULT 0,
  `revoked_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_refresh_jti` (`jti`),
  KEY `idx_refresh_user` (`user_id`),
  KEY `idx_refresh_exp` (`expires_at`),
  CONSTRAINT `fk_refresh_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "auth_user_state": """
CREATE TABLE IF NOT EXISTS `auth_user_state` (
  `user_id` bigint(20) unsigned NOT NULL,
  `token_version` bigint(20) unsigned NOT NULL DEFAULT 1,
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_auth_user_state_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "auth_password_reset_tokens": """
CREATE TABLE IF NOT EXISTS `auth_password_reset_tokens` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `token_hash` char(64) NOT NULL,
  `request_ip` varchar(64) DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  `used_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_password_reset_token_hash` (`token_hash`),
  KEY `idx_auth_password_reset_user` (`user_id`),
  KEY `idx_auth_password_reset_expires` (`expires_at`),
  CONSTRAINT `fk_auth_password_reset_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "user_app_config": """
CREATE TABLE IF NOT EXISTS `user_app_config` (
  `user_id` bigint(20) unsigned NOT NULL,
  `main_agent_verbosity` varchar(16) DEFAULT NULL,
  `main_agent_reasoning_effort` varchar(16) DEFAULT NULL,
  `ictihat_agent_reasoning_effort` varchar(16) DEFAULT NULL,
  `extra_instructions` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_user_app_config_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "documents": """
CREATE TABLE IF NOT EXISTS `documents` (
  `document_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `filename` varchar(512) NOT NULL,
  `file_type` enum('pdf','docx','udf','unknown') NOT NULL DEFAULT 'unknown',
  `mime_type` varchar(128) DEFAULT NULL,
  `size_bytes` int(11) NOT NULL,
  `sha256` char(64) NOT NULL,
  `storage_path` varchar(1024) NOT NULL,
  `status` enum('uploaded','processing','ready','failed') NOT NULL DEFAULT 'uploaded',
  `error_message` longtext DEFAULT NULL,
  `page_count` int(11) NOT NULL DEFAULT 0,
  `short_summary` longtext DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`document_id`),
  KEY `idx_docs_user` (`user_id`),
  KEY `idx_docs_status` (`status`),
  KEY `idx_docs_created` (`created_at`),
  UNIQUE KEY `uq_docs_user_sha256` (`user_id`,`sha256`),
  CONSTRAINT `fk_docs_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "document_pages": """
CREATE TABLE IF NOT EXISTS `document_pages` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `document_id` bigint(20) unsigned NOT NULL,
  `page_no` int(11) NOT NULL,
  `text` longtext NOT NULL,
  `page_summary` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_doc_page` (`document_id`,`page_no`),
  KEY `idx_pages_doc` (`document_id`),
  CONSTRAINT `fk_pages_doc` FOREIGN KEY (`document_id`) REFERENCES `documents` (`document_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "chat_documents": """
CREATE TABLE IF NOT EXISTS `chat_documents` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `chat_id` bigint(20) unsigned NOT NULL,
  `document_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_chat_doc` (`chat_id`,`document_id`),
  KEY `idx_chat_docs_chat` (`chat_id`),
  KEY `idx_chat_docs_doc` (`document_id`),
  CONSTRAINT `fk_chat_docs_chat` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`chat_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_chat_docs_doc` FOREIGN KEY (`document_id`) REFERENCES `documents` (`document_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "petitions": """
CREATE TABLE IF NOT EXISTS `petitions` (
  `petition_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `chat_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `status` enum('processing','ready','failed') NOT NULL DEFAULT 'processing',
  `title` varchar(512) DEFAULT NULL,
  `document_type` varchar(255) DEFAULT NULL,
  `court` varchar(512) DEFAULT NULL,
  `error_message` longtext DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`petition_id`),
  KEY `idx_petitions_chat` (`chat_id`),
  KEY `idx_petitions_user` (`user_id`),
  KEY `idx_petitions_status` (`status`),
  CONSTRAINT `fk_petitions_chat` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`chat_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_petitions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "petition_versions": """
CREATE TABLE IF NOT EXISTS `petition_versions` (
  `version_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `petition_id` bigint(20) unsigned NOT NULL,
  `version_no` int(11) NOT NULL,
  `intake_json` longtext NOT NULL,
  `output_json` longtext NOT NULL,
  `summary_text` longtext NOT NULL,
  `docx_filename` varchar(512) NOT NULL,
  `docx_mime` varchar(128) NOT NULL DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  `docx_blob` longblob NOT NULL,
  `udf_filename` varchar(512) DEFAULT NULL,
  `udf_mime` varchar(128) DEFAULT NULL,
  `udf_blob` longblob DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`version_id`),
  UNIQUE KEY `uq_petition_version_no` (`petition_id`,`version_no`),
  KEY `idx_petition_versions_petition` (`petition_id`),
  KEY `idx_petition_versions_created` (`created_at`),
  CONSTRAINT `fk_petition_versions_petition` FOREIGN KEY (`petition_id`) REFERENCES `petitions` (`petition_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "calendar_events": """
CREATE TABLE IF NOT EXISTS `calendar_events` (
  `event_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `chat_id` bigint(20) unsigned DEFAULT NULL,
  `petition_id` bigint(20) unsigned DEFAULT NULL,
  `title` varchar(512) NOT NULL,
  `note` text DEFAULT NULL,
  `due_date` date NOT NULL,
  `due_time` time DEFAULT NULL,
  `source` enum('petition_tool','petition_auto','manual') NOT NULL DEFAULT 'manual',
  `status` enum('pending','done','dismissed') NOT NULL DEFAULT 'pending',
  `color` varchar(16) DEFAULT NULL,
  `notified_24h_at` datetime DEFAULT NULL,
  `notified_4h_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`event_id`),
  KEY `idx_calevt_user` (`user_id`),
  KEY `idx_calevt_user_due` (`user_id`,`due_date`),
  KEY `idx_calevt_petition` (`petition_id`),
  KEY `idx_calevt_chat` (`chat_id`),
  KEY `idx_calevt_due_notif` (`due_date`,`notified_24h_at`),
  KEY `idx_calevt_due_notif4h` (`due_date`,`notified_4h_at`),
  CONSTRAINT `fk_calevt_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_calevt_chat` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`chat_id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_calevt_petition` FOREIGN KEY (`petition_id`) REFERENCES `petitions` (`petition_id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "generated_documents": """
CREATE TABLE IF NOT EXISTS `generated_documents` (
  `generated_document_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `chat_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `source_tool` varchar(64) NOT NULL DEFAULT 'word_render_docx',
  `filename` varchar(512) NOT NULL,
  `mime` varchar(128) NOT NULL DEFAULT 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  `size_bytes` bigint(20) unsigned NOT NULL DEFAULT 0,
  `source_payload_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (`source_payload_json` is null or json_valid(`source_payload_json`)),
  `docx_blob` longblob NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`generated_document_id`),
  KEY `idx_generated_documents_chat` (`chat_id`,`created_at`),
  KEY `idx_generated_documents_user` (`user_id`,`created_at`),
  CONSTRAINT `fk_generated_documents_chat` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`chat_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_generated_documents_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    # Credits (USD-based ledger + balance)
    "credit_transaction_types": """
CREATE TABLE IF NOT EXISTS `credit_transaction_types` (
  `type_id` smallint(5) unsigned NOT NULL,
  `code` varchar(32) NOT NULL,
  `name` varchar(128) NOT NULL,
  PRIMARY KEY (`type_id`),
  UNIQUE KEY `uq_ctt_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "user_credits": """
CREATE TABLE IF NOT EXISTS `user_credits` (
  `user_id` bigint(20) unsigned NOT NULL,
  `balance_usd` decimal(18,6) NOT NULL DEFAULT 0.000000,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_user_credits_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `chk_user_credits_nonneg` CHECK (`balance_usd` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "user_credits_transactions": """
CREATE TABLE IF NOT EXISTS `user_credits_transactions` (
  `tx_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `type_id` smallint(5) unsigned NOT NULL,
  `amount_usd` decimal(18,6) NOT NULL,
  `balance_after_usd` decimal(18,6) DEFAULT NULL,
  `reference_type` varchar(32) NOT NULL,
  `reference_id` bigint(20) unsigned NOT NULL,
  `meta` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`meta`)),
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`tx_id`),
  UNIQUE KEY `uq_ref_once` (`reference_type`,`reference_id`),
  KEY `idx_uctx_user_time` (`user_id`,`created_at`),
  KEY `idx_uctx_type` (`type_id`),
  CONSTRAINT `fk_uctx_type` FOREIGN KEY (`type_id`) REFERENCES `credit_transaction_types` (`type_id`)
    ON UPDATE CASCADE,
  CONSTRAINT `fk_uctx_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "child_credit_allocations": """
CREATE TABLE IF NOT EXISTS `child_credit_allocations` (
  `allocation_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `parent_user_id` bigint(20) unsigned NOT NULL,
  `child_user_id` bigint(20) unsigned NOT NULL,
  `allocated_balance_usd` decimal(18,6) NOT NULL DEFAULT 0.000000,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`allocation_id`),
  UNIQUE KEY `uq_child_credit_allocations_child` (`child_user_id`),
  KEY `idx_child_credit_allocations_parent` (`parent_user_id`),
  CONSTRAINT `fk_child_credit_allocations_parent` FOREIGN KEY (`parent_user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_child_credit_allocations_child` FOREIGN KEY (`child_user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `chk_child_credit_allocations_nonneg` CHECK (`allocated_balance_usd` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "coupons": """
CREATE TABLE IF NOT EXISTS `coupons` (
  `coupon_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `code` varchar(64) NOT NULL,
  `campaign_name` varchar(255) NOT NULL,
  `credit_amount` decimal(18,6) NOT NULL DEFAULT 0.000000,
  `max_redemptions` int(10) unsigned NOT NULL DEFAULT 1,
  `redemption_count` int(10) unsigned NOT NULL DEFAULT 0,
  `target_account_plan` enum('free','student','starter','standard','advanced','professional','enterprise') DEFAULT NULL,
  `created_by_label` varchar(255) DEFAULT NULL,
  `used_by_id` bigint(20) unsigned DEFAULT NULL,
  `used_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`coupon_id`),
  UNIQUE KEY `uq_coupons_code` (`code`),
  KEY `idx_coupons_campaign_name` (`campaign_name`),
  KEY `idx_coupons_used_by` (`used_by_id`),
  KEY `idx_coupons_created_at` (`created_at`),
  KEY `idx_coupons_used_at` (`used_at`),
  CONSTRAINT `fk_coupons_used_by` FOREIGN KEY (`used_by_id`) REFERENCES `users` (`user_id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `chk_coupons_credit_amount_nonneg` CHECK (`credit_amount` >= 0),
  CONSTRAINT `chk_coupons_max_redemptions_positive` CHECK (`max_redemptions` >= 1),
  CONSTRAINT `chk_coupons_redemption_count_nonneg` CHECK (`redemption_count` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
    "coupon_redemptions": """
CREATE TABLE IF NOT EXISTS `coupon_redemptions` (
  `redemption_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `coupon_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `redeemed_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`redemption_id`),
  UNIQUE KEY `uq_coupon_redemptions_coupon_user` (`coupon_id`,`user_id`),
  KEY `idx_coupon_redemptions_user` (`user_id`),
  KEY `idx_coupon_redemptions_redeemed_at` (`redeemed_at`),
  CONSTRAINT `fk_coupon_redemptions_coupon` FOREIGN KEY (`coupon_id`) REFERENCES `coupons` (`coupon_id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_coupon_redemptions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
""",
}


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def _column_data_type(conn, table_name: str, column_name: str) -> str | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    row = cur.fetchone()
    if not row:
        return None
    # mysql-connector returns a tuple
    return str(row[0] or "")


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s
        LIMIT 1
        """,
        (table_name, index_name),
    )
    return cur.fetchone() is not None


def _table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = %s
        LIMIT 1
        """,
        (table_name,),
    )
    return cur.fetchone() is not None


def _trigger_exists(conn, trigger_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.triggers
        WHERE trigger_schema = DATABASE() AND trigger_name = %s
        LIMIT 1
        """,
        (trigger_name,),
    )
    return cur.fetchone() is not None

def core_db():
    """
    placeholder for import db.core_db
    :return:
    """
    return None


def ensure_core_schema(*, create_missing: bool = True) -> List[str]:
    """
    Ensure core application tables exist (tables + basic constraints).

    Returns a list of tables that were created.
    """
    load_env()
    created: List[str] = []
    with core_db() as conn:
        for table, ddl in CORE_TABLE_DDL.items():
            exists = _table_exists(conn, table)
            if exists:
                continue
            if not create_missing:
                continue
            cur = conn.cursor()
            cur.execute(ddl)
            conn.commit()
            created.append(table)

        # Lightweight migrations for existing installs: ensure new auth columns exist.
        # This is intentionally minimal and idempotent.
        if _table_exists(conn, "users"):
            # Add username/full_name/password_hash if missing
            alterations: List[str] = []
            if not _column_exists(conn, "users", "username"):
                alterations.append("ADD COLUMN `username` varchar(64) NOT NULL")
            if not _column_exists(conn, "users", "full_name"):
                alterations.append("ADD COLUMN `full_name` varchar(255) DEFAULT NULL")
            if not _column_exists(conn, "users", "phone"):
                alterations.append("ADD COLUMN `phone` varchar(32) DEFAULT NULL")
            if not _column_exists(conn, "users", "password_hash"):
                alterations.append("ADD COLUMN `password_hash` varchar(255) NOT NULL DEFAULT ''")
            if not _column_exists(conn, "users", "account_type"):
                alterations.append(
                    "ADD COLUMN `account_type` enum('standalone','parent','child') NOT NULL DEFAULT 'standalone'"
                )
            if not _column_exists(conn, "users", "account_plan"):
                alterations.append(
                    "ADD COLUMN `account_plan` enum('free','student','starter','standard','advanced','professional','enterprise') NOT NULL DEFAULT 'free'"
                )
            if not _column_exists(conn, "users", "parent_user_id"):
                alterations.append("ADD COLUMN `parent_user_id` bigint(20) unsigned DEFAULT NULL")
            if not _column_exists(conn, "users", "child_account_limit_override"):
                alterations.append("ADD COLUMN `child_account_limit_override` int(10) unsigned DEFAULT NULL")

            if alterations:
                cur = conn.cursor()
                cur.execute(f"ALTER TABLE `users` {', '.join(alterations)}")
                conn.commit()

            if not _index_exists(conn, "users", "uq_users_username"):
                cur = conn.cursor()
                cur.execute("ALTER TABLE `users` ADD UNIQUE KEY `uq_users_username` (`username`)")
                conn.commit()
            if not _index_exists(conn, "users", "idx_users_account_type"):
                cur = conn.cursor()
                cur.execute("ALTER TABLE `users` ADD KEY `idx_users_account_type` (`account_type`)")
                conn.commit()
            if not _index_exists(conn, "users", "idx_users_parent"):
                cur = conn.cursor()
                cur.execute("ALTER TABLE `users` ADD KEY `idx_users_parent` (`parent_user_id`)")
                conn.commit()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    ALTER TABLE `users`
                    ADD CONSTRAINT `fk_users_parent_user`
                    FOREIGN KEY (`parent_user_id`) REFERENCES `users` (`user_id`)
                    ON DELETE CASCADE ON UPDATE CASCADE
                    """
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

        if _table_exists(conn, "auth_refresh_tokens") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["auth_refresh_tokens"])
            conn.commit()
            created.append("auth_refresh_tokens")

        if _table_exists(conn, "auth_user_state") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["auth_user_state"])
            conn.commit()
            created.append("auth_user_state")

        if _table_exists(conn, "auth_password_reset_tokens") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["auth_password_reset_tokens"])
            conn.commit()
            created.append("auth_password_reset_tokens")

        if _table_exists(conn, "user_app_config") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["user_app_config"])
            conn.commit()
            created.append("user_app_config")

        if _table_exists(conn, "app_config") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["app_config"])
            conn.commit()
            created.append("app_config")

        if _table_exists(conn, "child_credit_allocations") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["child_credit_allocations"])
            conn.commit()
            created.append("child_credit_allocations")

        if _table_exists(conn, "coupons") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["coupons"])
            conn.commit()
            created.append("coupons")

        if _table_exists(conn, "coupon_redemptions") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["coupon_redemptions"])
            conn.commit()
            created.append("coupon_redemptions")

        if _table_exists(conn, "coupons"):
            alterations: List[str] = []
            if not _column_exists(conn, "coupons", "campaign_name"):
                alterations.append("ADD COLUMN `campaign_name` varchar(255) NOT NULL DEFAULT 'default'")
            if not _column_exists(conn, "coupons", "max_redemptions"):
                alterations.append("ADD COLUMN `max_redemptions` int(10) unsigned NOT NULL DEFAULT 1")
            if not _column_exists(conn, "coupons", "redemption_count"):
                alterations.append("ADD COLUMN `redemption_count` int(10) unsigned NOT NULL DEFAULT 0")
            if alterations:
                cur = conn.cursor()
                cur.execute(f"ALTER TABLE `coupons` {', '.join(alterations)}")
                conn.commit()
            if not _index_exists(conn, "coupons", "idx_coupons_campaign_name"):
                cur = conn.cursor()
                cur.execute("ALTER TABLE `coupons` ADD KEY `idx_coupons_campaign_name` (`campaign_name`)")
                conn.commit()
            try:
                if _column_exists(conn, "coupons", "redemption_count") and _column_exists(conn, "coupons", "used_at"):
                    cur = conn.cursor()
                    cur.execute(
                        """
                        UPDATE `coupons`
                        SET `redemption_count` = CASE
                          WHEN `redemption_count` > 0 THEN `redemption_count`
                          WHEN `used_at` IS NOT NULL OR `used_by_id` IS NOT NULL THEN 1
                          ELSE 0
                        END
                        """
                    )
                    conn.commit()
            except Exception:
                pass

        if _table_exists(conn, "chat_context_items") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["chat_context_items"])
            conn.commit()
            created.append("chat_context_items")

        if _table_exists(conn, "ictihat_search_history") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["ictihat_search_history"])
            conn.commit()
            created.append("ictihat_search_history")

        if _table_exists(conn, "calendar_events") is False and create_missing:
            cur = conn.cursor()
            cur.execute(CORE_TABLE_DDL["calendar_events"])
            conn.commit()
            created.append("calendar_events")

        # user_tool_usages migration'lari artik gereksiz (tablo devre disi).

        # Usage: optionally link usage rows to a specific chat message (idempotent).
        if _table_exists(conn, "user_usages"):
            try:
                if not _column_exists(conn, "user_usages", "chat_message_id"):
                    cur = conn.cursor()
                    cur.execute("ALTER TABLE `user_usages` ADD COLUMN `chat_message_id` bigint(20) unsigned DEFAULT NULL")
                    conn.commit()
                if not _index_exists(conn, "user_usages", "idx_usage_chat_message"):
                    cur = conn.cursor()
                    cur.execute("ALTER TABLE `user_usages` ADD KEY `idx_usage_chat_message` (`chat_message_id`)")
                    conn.commit()
            except Exception:
                # Best-effort; never fail startup due to migrations.
                pass

        # Documents: add DB storage columns for raw uploads (idempotent).
        if _table_exists(conn, "documents"):
            alterations: List[str] = []
            if not _column_exists(conn, "documents", "raw_blob"):
                alterations.append("ADD COLUMN `raw_blob` longblob DEFAULT NULL")
            if alterations:
                cur = conn.cursor()
                cur.execute(f"ALTER TABLE `documents` {', '.join(alterations)}")
                conn.commit()

        # Petitions: store pre-rendered UDF blobs in petition_versions (idempotent).
        if _table_exists(conn, "petition_versions"):
            alterations: List[str] = []
            if not _column_exists(conn, "petition_versions", "udf_filename"):
                alterations.append("ADD COLUMN `udf_filename` varchar(512) DEFAULT NULL")
            if not _column_exists(conn, "petition_versions", "udf_mime"):
                alterations.append("ADD COLUMN `udf_mime` varchar(128) DEFAULT NULL")
            if not _column_exists(conn, "petition_versions", "udf_blob"):
                alterations.append("ADD COLUMN `udf_blob` longblob DEFAULT NULL")
            if alterations:
                cur = conn.cursor()
                cur.execute(f"ALTER TABLE `petition_versions` {', '.join(alterations)}")
                conn.commit()

        # Credits: ensure WELCOME is type_id=6 (user request).
        # If 6 is already used (historical 'adjust'), migrate it to a new id.
        try:
            if _table_exists(conn, "credit_transaction_types") and _table_exists(conn, "user_credits_transactions"):
                cur = conn.cursor()
                cur.execute("SELECT code, name FROM credit_transaction_types WHERE type_id=6 LIMIT 1")
                row6 = cur.fetchone()
                if row6:
                    code6 = str(row6[0] or "")
                    name6 = str(row6[1] or "")
                    if code6 != "WELCOME":
                        # If this code exists under another id, just repoint tx rows.
                        cur.execute("SELECT type_id FROM credit_transaction_types WHERE code=%s LIMIT 1", (code6,))
                        existing = cur.fetchone()
                        if existing and int(existing[0]) != 6:
                            new_id = int(existing[0])
                        else:
                            cur.execute("SELECT COALESCE(MAX(type_id), 0) FROM credit_transaction_types")
                            mx = cur.fetchone()
                            new_id = int((mx[0] or 0)) + 1
                            if new_id == 6:
                                new_id += 1
                            cur.execute(
                                "INSERT IGNORE INTO credit_transaction_types(type_id, code, name) VALUES (%s, %s, %s)",
                                (new_id, code6, name6),
                            )
                        # Move existing tx rows from 6 -> new_id (before repurposing 6).
                        cur.execute("UPDATE user_credits_transactions SET type_id=%s WHERE type_id=6", (new_id,))
                        # Repurpose 6 to WELCOME.
                        cur.execute(
                            "UPDATE credit_transaction_types SET code='WELCOME', name='Welcome credit' WHERE type_id=6"
                        )
                        conn.commit()
                else:
                    # No row at type_id=6: create WELCOME directly.
                    cur.execute(
                        "INSERT IGNORE INTO credit_transaction_types(type_id, code, name) VALUES (6, 'WELCOME', 'Welcome credit')"
                    )
                    conn.commit()

                # Keep historical/manual adjustment type available (best-effort).
                cur.execute("SELECT 1 FROM credit_transaction_types WHERE code='adjust' LIMIT 1")
                if cur.fetchone() is None:
                    cur.execute("SELECT COALESCE(MAX(type_id), 0) FROM credit_transaction_types")
                    mx2 = cur.fetchone()
                    new_id2 = int((mx2[0] or 0)) + 1
                    if new_id2 == 6:
                        new_id2 += 1
                    cur.execute(
                        "INSERT IGNORE INTO credit_transaction_types(type_id, code, name) VALUES (%s, 'adjust', 'Manuel Düzeltme')",
                        (new_id2,),
                    )
                    conn.commit()
        except Exception:
            # Best-effort; never fail startup due to data migrations.
            try:
                conn.rollback()
            except Exception:
                pass

        # Credits: welcome credit (optional) is implemented as a DB trigger on user creation.
        # Trigger logic is idempotent via user_credits_transactions.uq_ref_once.
        try:
            if (
                _table_exists(conn, "users")
                and _table_exists(conn, "app_config")
                and _table_exists(conn, "user_credits")
                and _table_exists(conn, "user_credits_transactions")
                and _table_exists(conn, "credit_transaction_types")
            ):
                cur = conn.cursor()
                cur.execute("DROP TRIGGER IF EXISTS `trg_welcome_credit_on_user_create`")
                cur.execute(
                    """
                    CREATE TRIGGER `trg_welcome_credit_on_user_create`
                    AFTER INSERT ON `users`
                    FOR EACH ROW
                    welcome: BEGIN
                      DECLARE v_amt decimal(18,6);
                      DECLARE v_tx_id bigint unsigned;
                      DECLARE v_new_balance decimal(18,6);
                      DECLARE v_type_id smallint unsigned DEFAULT NULL;
                      DECLARE v_welcome_enforce tinyint(1) DEFAULT 0;
                      DECLARE v_default_amt decimal(18,6) DEFAULT 0.000000;
                      DECLARE v_student_amt decimal(18,6) DEFAULT 0.000000;

                      -- Ensure a balance row exists even if welcome credit is disabled.
                      INSERT IGNORE INTO user_credits(user_id, balance_usd)
                      VALUES (NEW.user_id, 0.000000);

                      SELECT
                        COALESCE(MAX(CASE WHEN config_key = 'welcome_credit_enforce' THEN value_bool END), 0),
                        COALESCE(MAX(CASE WHEN config_key = 'welcome_credit_usd' THEN value_decimal END), 0.000000),
                        COALESCE(MAX(CASE WHEN config_key = 'student_welcome_credit_usd' THEN value_decimal END), 0.000000)
                      INTO
                        v_welcome_enforce,
                        v_default_amt,
                        v_student_amt
                      FROM app_config
                      WHERE config_key IN ('welcome_credit_enforce', 'welcome_credit_usd', 'student_welcome_credit_usd');

                      IF v_welcome_enforce = 0 THEN
                        LEAVE welcome;
                      END IF;

                      IF NEW.account_plan = 'student' THEN
                        SET v_amt = COALESCE(v_student_amt, 0.000000);
                      ELSE
                        SET v_amt = COALESCE(v_default_amt, 0.000000);
                      END IF;

                      IF v_amt IS NULL OR v_amt <= 0 THEN
                        LEAVE welcome;
                      END IF;

                      -- WELCOME type_id is fixed to 6 (ensured by ensure_core_schema migration).
                      SET v_type_id = 6;

                      IF v_type_id IS NULL THEN
                        LEAVE welcome;
                      END IF;

                      -- Ledger gate: only once per user_id
                      INSERT IGNORE INTO user_credits_transactions
                        (user_id, type_id, amount_usd, reference_type, reference_id, meta)
                      VALUES
                        (NEW.user_id, v_type_id, v_amt, 'welcome_credit', NEW.user_id,
                         JSON_OBJECT('source', 'trigger'));

                      IF ROW_COUNT() = 0 THEN
                        LEAVE welcome;
                      END IF;

                      SET v_tx_id = LAST_INSERT_ID();

                      UPDATE user_credits
                      SET balance_usd = balance_usd + v_amt
                      WHERE user_id = NEW.user_id;

                      SELECT balance_usd INTO v_new_balance
                      FROM user_credits
                      WHERE user_id = NEW.user_id
                      LIMIT 1;

                      UPDATE user_credits_transactions
                      SET balance_after_usd = v_new_balance
                      WHERE tx_id = v_tx_id;
                    END
                    """
                )
                conn.commit()
        except Exception:
            # Best-effort; never fail startup due to optional credit trigger.
            pass
    return created


"""def main() -> None:
    created = ensure_core_schema(create_missing=True)
    if created:
        print("Created tables:", ", ".join(created))
    else:
        print("Core schema OK (no changes).")


if __name__ == "__main__":
    main()"""


