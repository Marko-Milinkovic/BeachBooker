-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema mydb
-- -----------------------------------------------------
-- -----------------------------------------------------
-- Schema beachbooker
-- -----------------------------------------------------

-- -----------------------------------------------------
-- Schema beachbooker
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `beachbooker` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci ;
USE `beachbooker` ;

-- -----------------------------------------------------
-- Table `beachbooker`.`amenity`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`amenity` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(80) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uk_amenity_name` (`name` ASC) VISIBLE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`user`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`user` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `first_name` VARCHAR(80) NOT NULL,
  `last_name` VARCHAR(80) NOT NULL,
  `role` ENUM('registered', 'owner', 'admin') NOT NULL DEFAULT 'registered',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uk_user_email` (`email` ASC) VISIBLE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`beach_bar`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`beach_bar` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `owner_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  `address` VARCHAR(255) NOT NULL,
  `city` VARCHAR(80) NOT NULL,
  `description` TEXT NULL DEFAULT NULL,
  `opening_time` TIME NOT NULL,
  `closing_time` TIME NOT NULL,
  `map_url` VARCHAR(512) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_beach_bar_owner` (`owner_id` ASC) VISIBLE,
  CONSTRAINT `fk_beach_bar_owner`
    FOREIGN KEY (`owner_id`)
    REFERENCES `beachbooker`.`user` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`beach_bar_amenity`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`beach_bar_amenity` (
  `beach_bar_id` BIGINT UNSIGNED NOT NULL,
  `amenity_id` BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (`beach_bar_id`, `amenity_id`),
  INDEX `fk_bba_amenity` (`amenity_id` ASC) VISIBLE,
  CONSTRAINT `fk_bba_amenity`
    FOREIGN KEY (`amenity_id`)
    REFERENCES `beachbooker`.`amenity` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_bba_beach_bar`
    FOREIGN KEY (`beach_bar_id`)
    REFERENCES `beachbooker`.`beach_bar` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`bundle`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`bundle` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `beach_bar_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  `description` VARCHAR(255) NULL DEFAULT NULL,
  `price` DECIMAL(10,2) NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  INDEX `idx_bundle_beach_bar` (`beach_bar_id` ASC) VISIBLE,
  CONSTRAINT `fk_bundle_beach_bar`
    FOREIGN KEY (`beach_bar_id`)
    REFERENCES `beachbooker`.`beach_bar` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`sunbed_category`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`sunbed_category` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `beach_bar_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(80) NOT NULL,
  `price` DECIMAL(10,2) NOT NULL,
  `description` VARCHAR(255) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_category_beach_bar` (`beach_bar_id` ASC) VISIBLE,
  CONSTRAINT `fk_category_beach_bar`
    FOREIGN KEY (`beach_bar_id`)
    REFERENCES `beachbooker`.`beach_bar` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`sunbed`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`sunbed` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `beach_bar_id` BIGINT UNSIGNED NOT NULL,
  `category_id` BIGINT UNSIGNED NOT NULL,
  `label` VARCHAR(20) NOT NULL,
  `grid_row` SMALLINT UNSIGNED NOT NULL,
  `grid_col` SMALLINT UNSIGNED NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uk_sunbed_bar_label` (`beach_bar_id` ASC, `label` ASC) VISIBLE,
  INDEX `idx_sunbed_category` (`category_id` ASC) VISIBLE,
  CONSTRAINT `fk_sunbed_beach_bar`
    FOREIGN KEY (`beach_bar_id`)
    REFERENCES `beachbooker`.`beach_bar` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_sunbed_category`
    FOREIGN KEY (`category_id`)
    REFERENCES `beachbooker`.`sunbed_category` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`reservation`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`reservation` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `sunbed_id` BIGINT UNSIGNED NOT NULL,
  `reservation_date` DATE NOT NULL,
  `status` ENUM('active', 'completed', 'cancelled') NOT NULL DEFAULT 'active',
  `price_at_booking` DECIMAL(10,2) NOT NULL,
  `payment_status` VARCHAR(20) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uk_reservation_sunbed_date` (`sunbed_id` ASC, `reservation_date` ASC) VISIBLE,
  INDEX `idx_reservation_user` (`user_id` ASC) VISIBLE,
  INDEX `idx_reservation_date` (`reservation_date` ASC) VISIBLE,
  CONSTRAINT `fk_reservation_sunbed`
    FOREIGN KEY (`sunbed_id`)
    REFERENCES `beachbooker`.`sunbed` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT `fk_reservation_user`
    FOREIGN KEY (`user_id`)
    REFERENCES `beachbooker`.`user` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`reservation_bundle`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`reservation_bundle` (
  `reservation_id` BIGINT UNSIGNED NOT NULL,
  `bundle_id` BIGINT UNSIGNED NOT NULL,
  `price_at_booking` DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (`reservation_id`, `bundle_id`),
  INDEX `fk_rb_bundle` (`bundle_id` ASC) VISIBLE,
  CONSTRAINT `fk_rb_bundle`
    FOREIGN KEY (`bundle_id`)
    REFERENCES `beachbooker`.`bundle` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT `fk_rb_reservation`
    FOREIGN KEY (`reservation_id`)
    REFERENCES `beachbooker`.`reservation` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `beachbooker`.`review`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `beachbooker`.`review` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `beach_bar_id` BIGINT UNSIGNED NOT NULL,
  `rating` TINYINT UNSIGNED NOT NULL,
  `review_text` TEXT NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_review_beach_bar` (`beach_bar_id` ASC) VISIBLE,
  INDEX `idx_review_user` (`user_id` ASC) VISIBLE,
  CONSTRAINT `fk_review_beach_bar`
    FOREIGN KEY (`beach_bar_id`)
    REFERENCES `beachbooker`.`beach_bar` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_review_user`
    FOREIGN KEY (`user_id`)
    REFERENCES `beachbooker`.`user` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
