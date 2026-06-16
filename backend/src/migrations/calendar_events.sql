-- Yargucu - Calendar / Deadline tracking table
-- Apply with: mysql -u root -p <db_name> < calendar_events.sql
-- Idempotent (CREATE TABLE IF NOT EXISTS).

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

-- Idempotent migration: add `notified_24h_at` column for existing installs.
-- Safe to run multiple times.
ALTER TABLE `calendar_events`
  ADD COLUMN IF NOT EXISTS `notified_24h_at` datetime DEFAULT NULL AFTER `color`;

ALTER TABLE `calendar_events`
  ADD KEY IF NOT EXISTS `idx_calevt_due_notif` (`due_date`,`notified_24h_at`);

-- 4-hour follow-up alarm: tracked independently from the 24-hour reminder so
-- both can be sent for the same event without one suppressing the other.
ALTER TABLE `calendar_events`
  ADD COLUMN IF NOT EXISTS `notified_4h_at` datetime DEFAULT NULL AFTER `notified_24h_at`;

ALTER TABLE `calendar_events`
  ADD KEY IF NOT EXISTS `idx_calevt_due_notif4h` (`due_date`,`notified_4h_at`);
