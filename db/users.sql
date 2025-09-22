CREATE USER 'gbuser_legacy'@'%' IDENTIFIED BY 'gbuser_legacy';
SET PASSWORD FOR 'gbuser_legacy'@'%' = OLD_PASSWORD('gbuser_legacy');
GRANT ALL PRIVILEGES ON gbwc.* TO 'gbuser_legacy'@'%';

CREATE USER 'gbuser_legacy'@'localhost' IDENTIFIED BY 'gbuser_legacy';
SET PASSWORD FOR 'gbuser_legacy'@'localhost' = OLD_PASSWORD('gbuser_legacy');
GRANT ALL PRIVILEGES ON gbwc.* TO 'gbuser_legacy'@'localhost';

CREATE USER 'gbuser'@'%' IDENTIFIED BY 'gbpass';
GRANT ALL PRIVILEGES ON gbwc.* TO 'gbuser'@'%';

FLUSH PRIVILEGES;