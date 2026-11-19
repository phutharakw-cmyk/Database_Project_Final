-- =====================================================================
-- MovieTicketSystem - MySQL seed data
-- Owner: Mizt
-- Logins (password in brackets):
--   admin@cinema.local  (admin123)  - admin
--   alice@example.com   (alice123)  - customer
--   bob@example.com     (bob123)    - customer
-- Showtimes are relative to the day you load the seed, so they are
-- always in the future.
-- =====================================================================
USE movie_ticket_system;

INSERT INTO users (user_id, name, email, password_hash, phone, role) VALUES
(1, 'Cinema Admin', 'admin@cinema.local',
 'pbkdf2:sha256:600000$5vuudGEXQulxAqJ0$6adc48180b5d90a57dbb920c890ed68f4a23a12c457438baafc58de270696953',
 '020000000', 'admin'),
(2, 'Alice Customer', 'alice@example.com',
 'pbkdf2:sha256:600000$IpPSDxNnEp17by7b$d3432cce6017d16dfdb3880844cd419fa54a1cab212ec694337dc87a9765f467',
 '0811111111', 'customer'),
(3, 'Bob Customer', 'bob@example.com',
 'pbkdf2:sha256:600000$DN55CJOlCR6t9RZU$60f00392842d0451622a4ca06d2b401ffee3ef48a309c0bcd4df1275448af16a',
 '0822222222', 'customer');

INSERT INTO movies (movie_id, title, genre, duration_min, rating, description, poster_path, status) VALUES
(1, 'Starfall Protocol', 'Sci-Fi', 128, 'PG-13',
 'A rescue crew races to stop a falling space station before it hits the Gulf of Thailand.',
 'uploads/posters/seed_1.png', 'now_showing'),
(2, 'The Last Monsoon', 'Drama', 112, 'PG',
 'Three generations of a rice-farming family face one final rainy season together.',
 'uploads/posters/seed_2.png', 'now_showing'),
(3, 'Bangkok Midnight Run', 'Action', 105, 'R',
 'A tuk-tuk driver gets one night to deliver a mysterious package across the city.',
 'uploads/posters/seed_3.png', 'now_showing'),
(4, 'Paper Lanterns', 'Animation', 95, 'G',
 'A paper lantern comes to life during Loy Krathong and searches for its maker.',
 'uploads/posters/seed_4.png', 'now_showing'),
(5, 'Echoes in the Hall', 'Horror', 99, 'R',
 'Students locked in an old lecture hall overnight start hearing their own voices.',
 'uploads/posters/seed_5.png', 'now_showing'),
(6, 'Coffee & Code', 'Comedy', 101, 'PG',
 'Two rival developers are forced to share one desk, one deadline and one coffee machine.',
 'uploads/posters/seed_6.png', 'coming_soon');

INSERT INTO showtimes (showtime_id, movie_id, hall, start_time, price) VALUES
(1,  1, 'Hall 1', TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '13:00:00'), 220.00),
(2,  1, 'Hall 1', TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '19:30:00'), 260.00),
(3,  1, 'Hall 2', TIMESTAMP(CURDATE() + INTERVAL 2 DAY, '16:00:00'), 220.00),
(4,  2, 'Hall 3', TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '14:15:00'), 180.00),
(5,  2, 'Hall 3', TIMESTAMP(CURDATE() + INTERVAL 2 DAY, '20:00:00'), 200.00),
(6,  3, 'Hall 2', TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '21:00:00'), 240.00),
(7,  3, 'Hall 4', TIMESTAMP(CURDATE() + INTERVAL 3 DAY, '18:00:00'), 240.00),
(8,  4, 'Hall 4', TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '10:30:00'), 150.00),
(9,  4, 'Hall 4', TIMESTAMP(CURDATE() + INTERVAL 2 DAY, '11:00:00'), 150.00),
(10, 5, 'Hall 5', TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '22:30:00'), 200.00),
(11, 5, 'Hall 5', TIMESTAMP(CURDATE() + INTERVAL 3 DAY, '23:00:00'), 200.00);

-- Existing bookings so the seat map / My Bookings are not empty.
-- Showtime 1 is left EMPTY on purpose for the A1 + A2 rollback demo.
INSERT INTO bookings (booking_id, user_id, showtime_id, total_amount, payment_method, status) VALUES
(1, 3, 2, 520.00, 'promptpay',   'confirmed'),
(2, 2, 4, 360.00, 'credit_card', 'confirmed'),
(3, 3, 6, 240.00, 'cash',        'confirmed');

INSERT INTO tickets (booking_id, showtime_id, seat_label, price) VALUES
(1, 2, 'E5', 260.00),
(1, 2, 'E6', 260.00),
(2, 4, 'D4', 180.00),
(2, 4, 'D5', 180.00),
(3, 6, 'C7', 240.00);

-- keep AUTO_INCREMENT after the explicit ids
ALTER TABLE users     AUTO_INCREMENT = 4;
ALTER TABLE movies    AUTO_INCREMENT = 7;
ALTER TABLE showtimes AUTO_INCREMENT = 12;
ALTER TABLE bookings  AUTO_INCREMENT = 4;
