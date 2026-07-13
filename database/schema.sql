-- BeachBooker — logical schema (MySQL 8+)
-- Aligns with database/conceptual_model.md
-- Import into Workbench: File → Run SQL Script, then Database → Reverse Engineer

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS admin_action_log;
DROP TABLE IF EXISTS reservation_bundle;
DROP TABLE IF EXISTS reservation;
DROP TABLE IF EXISTS review;
DROP TABLE IF EXISTS bundle;
DROP TABLE IF EXISTS sunbed;
DROP TABLE IF EXISTS sunbed_category;
DROP TABLE IF EXISTS beach_bar_amenity;
DROP TABLE IF EXISTS beach_bar;
DROP TABLE IF EXISTS amenity;
DROP TABLE IF EXISTS user;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------------
-- user — registered customers, owners, admins (guests are not stored)
-- ---------------------------------------------------------------------------
CREATE TABLE user (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    last_login DATETIME NULL,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    role ENUM('registered', 'owner', 'admin') NOT NULL DEFAULT 'registered',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- beach_bar — one owner (user) may have many bars
-- ---------------------------------------------------------------------------
CREATE TABLE beach_bar (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(80) NOT NULL,
    description TEXT NULL,
    opening_time TIME NOT NULL,
    closing_time TIME NOT NULL,
    map_url VARCHAR(512) NULL,
    image_url VARCHAR(512) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_beach_bar_owner (owner_id),
    CONSTRAINT fk_beach_bar_owner
        FOREIGN KEY (owner_id) REFERENCES user (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- amenity + beach_bar_amenity — explore filters (n:m)
-- ---------------------------------------------------------------------------
CREATE TABLE amenity (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_amenity_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE beach_bar_amenity (
    beach_bar_id BIGINT UNSIGNED NOT NULL,
    amenity_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (beach_bar_id, amenity_id),
    CONSTRAINT fk_bba_beach_bar
        FOREIGN KEY (beach_bar_id) REFERENCES beach_bar (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_bba_amenity
        FOREIGN KEY (amenity_id) REFERENCES amenity (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- sunbed_category — pricing zone per bar
-- ---------------------------------------------------------------------------
CREATE TABLE sunbed_category (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    beach_bar_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(80) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    description VARCHAR(255) NULL,
    PRIMARY KEY (id),
    KEY idx_category_beach_bar (beach_bar_id),
    CONSTRAINT fk_category_beach_bar
        FOREIGN KEY (beach_bar_id) REFERENCES beach_bar (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- sunbed — one spot on the map; unique label per bar
-- ---------------------------------------------------------------------------
CREATE TABLE sunbed (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    beach_bar_id BIGINT UNSIGNED NOT NULL,
    category_id BIGINT UNSIGNED NOT NULL,
    label VARCHAR(20) NOT NULL,
    grid_row SMALLINT UNSIGNED NOT NULL,
    grid_col SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sunbed_bar_label (beach_bar_id, label),
    KEY idx_sunbed_category (category_id),
    CONSTRAINT fk_sunbed_beach_bar
        FOREIGN KEY (beach_bar_id) REFERENCES beach_bar (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_sunbed_category
        FOREIGN KEY (category_id) REFERENCES sunbed_category (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- reservation — one sunbed, one date; price snapshot
-- One row per (sunbed, date): cancel = update status; avoids double booking
-- ---------------------------------------------------------------------------
CREATE TABLE reservation (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    sunbed_id BIGINT UNSIGNED NOT NULL,
    reservation_date DATE NOT NULL,
    status ENUM('active', 'completed', 'cancelled') NOT NULL DEFAULT 'active',
    price_at_booking DECIMAL(10, 2) NOT NULL,
    payment_status VARCHAR(20) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_reservation_sunbed_date (sunbed_id, reservation_date),
    KEY idx_reservation_user (user_id),
    KEY idx_reservation_date (reservation_date),
    CONSTRAINT fk_reservation_user
        FOREIGN KEY (user_id) REFERENCES user (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_reservation_sunbed
        FOREIGN KEY (sunbed_id) REFERENCES sunbed (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- bundle + reservation_bundle — schema now, MVP UI later
-- ---------------------------------------------------------------------------
CREATE TABLE bundle (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    beach_bar_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(255) NULL,
    price DECIMAL(10, 2) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    KEY idx_bundle_beach_bar (beach_bar_id),
    CONSTRAINT fk_bundle_beach_bar
        FOREIGN KEY (beach_bar_id) REFERENCES beach_bar (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE reservation_bundle (
    reservation_id BIGINT UNSIGNED NOT NULL,
    bundle_id BIGINT UNSIGNED NOT NULL,
    price_at_booking DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (reservation_id, bundle_id),
    CONSTRAINT fk_rb_reservation
        FOREIGN KEY (reservation_id) REFERENCES reservation (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_rb_bundle
        FOREIGN KEY (bundle_id) REFERENCES bundle (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- review — schema now, UI later
-- ---------------------------------------------------------------------------
CREATE TABLE review (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    beach_bar_id BIGINT UNSIGNED NOT NULL,
    rating TINYINT UNSIGNED NOT NULL,
    review_text TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_review_beach_bar (beach_bar_id),
    KEY idx_review_user (user_id),
    CONSTRAINT fk_review_user
        FOREIGN KEY (user_id) REFERENCES user (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_review_beach_bar
        FOREIGN KEY (beach_bar_id) REFERENCES beach_bar (id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_review_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- admin_action_log — BeachBooker admin panel audit trail (SSU 5.4)
-- ---------------------------------------------------------------------------
CREATE TABLE admin_action_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    admin_id BIGINT UNSIGNED NOT NULL,
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(40) NOT NULL DEFAULT '',
    target_id BIGINT NULL,
    detail VARCHAR(512) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_admin_action_log_admin (admin_id),
    KEY idx_admin_action_log_action (action),
    KEY idx_admin_action_log_created (created_at),
    CONSTRAINT fk_admin_action_log_admin
        FOREIGN KEY (admin_id) REFERENCES user (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
