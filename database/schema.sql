-- =====================================================================
-- MovieTicketSystem - MySQL schema
-- Owner: Mizt
-- 5 related tables: users, movies, showtimes, bookings, tickets
-- =====================================================================

CREATE DATABASE IF NOT EXISTS movie_ticket_system
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE movie_ticket_system;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS showtimes;
DROP TABLE IF EXISTS movies;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- users: customer and admin accounts
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100)  NOT NULL,
    email          VARCHAR(150)  NOT NULL,
    password_hash  VARCHAR(255)  NOT NULL,
    phone          VARCHAR(20)   NULL,
    role           ENUM('customer','admin') NOT NULL DEFAULT 'customer',
    avatar_path    VARCHAR(255)  NULL,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- movies: catalog managed by admins
-- ---------------------------------------------------------------------
CREATE TABLE movies (
    movie_id      INT AUTO_INCREMENT PRIMARY KEY,
    title         VARCHAR(200) NOT NULL,
    genre         VARCHAR(100) NOT NULL,
    duration_min  INT          NOT NULL,
    rating        VARCHAR(10)  NOT NULL DEFAULT 'G',     -- age rating: G, PG, PG-13, R ...
    description   TEXT         NULL,
    poster_path   VARCHAR(255) NULL,                      -- file stored locally in static/uploads/posters
    status        ENUM('now_showing','coming_soon','ended') NOT NULL DEFAULT 'now_showing',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_movies_duration CHECK (duration_min > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- showtimes: a movie playing in a hall at a time  (movie 1 -- N showtimes)
-- ---------------------------------------------------------------------
CREATE TABLE showtimes (
    showtime_id  INT AUTO_INCREMENT PRIMARY KEY,
    movie_id     INT           NOT NULL,
    hall         VARCHAR(20)   NOT NULL,
    start_time   DATETIME      NOT NULL,
    price        DECIMAL(8,2)  NOT NULL,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_showtimes_movie FOREIGN KEY (movie_id)
        REFERENCES movies(movie_id) ON DELETE CASCADE,
    CONSTRAINT uq_showtimes_hall_time UNIQUE (hall, start_time),
    CONSTRAINT chk_showtimes_price CHECK (price >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- bookings: booking header  (user 1 -- N bookings, showtime 1 -- N bookings)
-- ---------------------------------------------------------------------
CREATE TABLE bookings (
    booking_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT           NOT NULL,
    showtime_id     INT           NOT NULL,
    total_amount    DECIMAL(10,2) NOT NULL DEFAULT 0,
    payment_method  ENUM('cash','credit_card','promptpay') NOT NULL DEFAULT 'cash',
    status          ENUM('confirmed','cancelled') NOT NULL DEFAULT 'confirmed',
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at    DATETIME      NULL,
    cancelled_seats VARCHAR(255)  NULL,   -- seat list kept for history; tickets are deleted to free the seats
    CONSTRAINT fk_bookings_user FOREIGN KEY (user_id)
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_bookings_showtime FOREIGN KEY (showtime_id)
        REFERENCES showtimes(showtime_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- tickets: one row per seat  (booking 1 -- N tickets)
-- UNIQUE (showtime_id, seat_label) = the same seat can never be sold twice
-- ---------------------------------------------------------------------
CREATE TABLE tickets (
    ticket_id    INT AUTO_INCREMENT PRIMARY KEY,
    booking_id   INT          NOT NULL,
    showtime_id  INT          NOT NULL,
    seat_label   VARCHAR(5)   NOT NULL,
    price        DECIMAL(8,2) NOT NULL,
    CONSTRAINT fk_tickets_booking FOREIGN KEY (booking_id)
        REFERENCES bookings(booking_id) ON DELETE CASCADE,
    CONSTRAINT fk_tickets_showtime FOREIGN KEY (showtime_id)
        REFERENCES showtimes(showtime_id) ON DELETE RESTRICT,
    CONSTRAINT uq_tickets_showtime_seat UNIQUE (showtime_id, seat_label)
) ENGINE=InnoDB;

CREATE INDEX idx_showtimes_start ON showtimes(start_time);
CREATE INDEX idx_bookings_user   ON bookings(user_id);
