-- Only needed if you run MySQL WITHOUT Docker (e.g. MySQL Workbench / XAMPP).
-- Run as root:   mysql -u root -p < database/create_user.sql
CREATE DATABASE IF NOT EXISTS movie_ticket_system
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'movie_app'@'localhost' IDENTIFIED BY 'movie_pass';
CREATE USER IF NOT EXISTS 'movie_app'@'%'         IDENTIFIED BY 'movie_pass';
GRANT ALL PRIVILEGES ON movie_ticket_system.* TO 'movie_app'@'localhost';
GRANT ALL PRIVILEGES ON movie_ticket_system.* TO 'movie_app'@'%';
FLUSH PRIVILEGES;
