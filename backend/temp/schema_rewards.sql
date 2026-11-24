-- 보상 · 옷장 표 (MySQL 8 / DBeaver). temp/schema.sql 다음에 실행한다 (users · books · fairy_topics 를 가리킨다).
-- 실행 순서: ① schema.sql → ② 이 파일 → ③ seed_clothes.sql (옷 43벌)
--
-- 이 표들은 팀원(택근)이 팀 DB 에 직접 만든 것이고, 이 파일은 그 표를 쓰는 코드(rewards_repo.py)에 맞춰 다시 적은 것이다 (2026-11-23 낙준).
--   칸 이름 · 순서는 팀 DB(DBeaver)와 같다. 길이 · 기본값 · 키 이름 같은 세부 조건은 팀 DB 와 조금 다를 수 있다.
--   정확한 원본 정의는 팀 DB 에서 SHOW CREATE TABLE clothes; 처럼 확인한다.
--
-- 코드가 기대하는 것
--   clothes.slot          rewards_repo.SLOTS 와 같은 5가지 (top · bottom · hat · shoes · gloves)
--   reward_claims         두 번 받기 막기: 같은 사용자의 같은 주(일기) · 같은 책 같은 구간(동화)은 한 줄만 (UNIQUE → 409)
--   user_clothes          INSERT IGNORE 로 넣으므로 (user_id, clothes_id) 가 기본 키
--   user_equipped_clothes INSERT ... ON DUPLICATE KEY UPDATE 로 넣으므로 user_id 가 기본 키
--   clothes.required_count · diary_reward_order, reward_claims.diary_reward_order 는 코드가 읽지 않는다 (팀 DB 와 칸을 맞추려고 둠)
--
-- 시각 규칙은 schema.sql 과 같다: *_at 값은 앱이 한국 시간으로 직접 넣는다.

USE app_db;

-- 다시 만들 때 (자식 → 부모 순서로 삭제). 받은 보상 기록이 다 날아가니 개발 중에만 사용.
-- schema.sql 을 다시 실행하려면 이 네 줄을 먼저 실행해야 한다 (이 표들이 users · books 를 가리켜서 그쪽 DROP 이 막힌다).
DROP TABLE IF EXISTS user_equipped_clothes;
DROP TABLE IF EXISTS user_clothes;
DROP TABLE IF EXISTS reward_claims;
DROP TABLE IF EXISTS clothes;

-- 의상 (보상으로 주는 옷. 데이터는 seed_clothes.sql)
CREATE TABLE clothes (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name               VARCHAR(50)  NOT NULL COMMENT '옷 이름 (예: 빨간 티셔츠)',
  slot               ENUM('top','bottom','hat','shoes','gloves') NOT NULL COMMENT '부위: 상의 · 하의 · 모자 · 신발 · 장갑',
  image_url          VARCHAR(255) NULL COMMENT '그림 (아직 없으면 NULL)',
  reward_kind        ENUM('diary','fairy') NOT NULL COMMENT '어떤 보상인지: 일기 주간 / 동화 구간',
  reward_order       INT UNSIGNED NOT NULL COMMENT '일기: 몇 번째로 주간 목표를 달성했을 때 / 동화: 그 주제의 몇 번째 구간(1 · 2 · 3)',
  required_count     INT UNSIGNED NOT NULL COMMENT '필요한 횟수 (일기 5일 / 동화 3 · 6 · 10장). 코드는 reward_rules.py 를 보고 이 칸은 읽지 않는다',
  fairy_topic_id     BIGINT UNSIGNED NULL COMMENT '동화: 이 옷 세트의 주제 (일기는 NULL)',
  diary_reward_order INT UNSIGNED NULL COMMENT '팀 DB 와 칸을 맞추려고 둠 (코드는 쓰지 않는다)',
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_clothes_reward (reward_kind, reward_order),
  KEY idx_clothes_topic (fairy_topic_id),
  CONSTRAINT fk_clothes_topic FOREIGN KEY (fairy_topic_id) REFERENCES fairy_topics (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='보상 의상';

-- 보상 기록 (달성 · 받기)
--   일기: 주간 목표를 달성하면 그 주(week_start = 월요일)를 다음 차수로 적어 두고(claimed_at = NULL), 받을 때 claimed_at 을 채운다
--   동화: 받는 순간 책(book_id) · 구간(reward_order)과 함께 적는다 (achieved_at = claimed_at)
CREATE TABLE reward_claims (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id            BIGINT UNSIGNED NOT NULL,
  clothes_id         BIGINT UNSIGNED NOT NULL COMMENT '받을(받은) 옷',
  reward_kind        ENUM('diary','fairy') NOT NULL COMMENT '일기 주간 / 동화 구간',
  reward_order       INT UNSIGNED NOT NULL COMMENT '일기: 몇 번째 달성 / 동화: 몇 번째 구간(1 · 2 · 3)',
  book_id            BIGINT UNSIGNED NULL COMMENT '동화: 어느 책의 보상인지 (일기는 NULL)',
  week_start         DATE NULL COMMENT '일기: 달성한 주의 월요일 (동화는 NULL)',
  diary_reward_order INT UNSIGNED NULL COMMENT '팀 DB 와 칸을 맞추려고 둠 (코드는 쓰지 않는다)',
  achieved_at        DATETIME NOT NULL COMMENT '달성을 확인한 시각',
  claimed_at         DATETIME NULL COMMENT '받은 시각 (NULL = 아직 안 받음)',
  PRIMARY KEY (id),
  UNIQUE KEY uq_claims_week (user_id, reward_kind, week_start),     -- 일기: 한 주에 한 번 (동화는 week_start 가 NULL 이라 걸리지 않는다)
  UNIQUE KEY uq_claims_book (user_id, book_id, reward_order),       -- 동화: 한 책의 같은 구간은 한 번 (일기는 book_id 가 NULL 이라 걸리지 않는다)
  KEY idx_claims_clothes (clothes_id),
  KEY idx_claims_book (book_id),
  CONSTRAINT fk_claims_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_claims_clothes FOREIGN KEY (clothes_id) REFERENCES clothes (id),
  CONSTRAINT fk_claims_book FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='보상 기록';

-- 가진 옷 (받기와 같은 트랜잭션에서 INSERT IGNORE)
CREATE TABLE user_clothes (
  user_id     BIGINT UNSIGNED NOT NULL,
  clothes_id  BIGINT UNSIGNED NOT NULL,
  acquired_at DATETIME NOT NULL COMMENT '얻은 시각',
  PRIMARY KEY (user_id, clothes_id),
  KEY idx_user_clothes_clothes (clothes_id),
  CONSTRAINT fk_user_clothes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT fk_user_clothes_clothes FOREIGN KEY (clothes_id) REFERENCES clothes (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='가진 의상';

-- 입은 옷 (사용자당 한 줄, 부위 5칸. 비어 있으면 그 부위는 안 입음)
CREATE TABLE user_equipped_clothes (
  user_id           BIGINT UNSIGNED NOT NULL,
  top_clothes_id    BIGINT UNSIGNED NULL COMMENT '상의',
  bottom_clothes_id BIGINT UNSIGNED NULL COMMENT '하의',
  hat_clothes_id    BIGINT UNSIGNED NULL COMMENT '모자',
  shoes_clothes_id  BIGINT UNSIGNED NULL COMMENT '신발',
  gloves_clothes_id BIGINT UNSIGNED NULL COMMENT '장갑',
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '바꾼 시각',
  PRIMARY KEY (user_id),
  CONSTRAINT fk_equipped_user   FOREIGN KEY (user_id)           REFERENCES users (id)   ON DELETE CASCADE,
  CONSTRAINT fk_equipped_top    FOREIGN KEY (top_clothes_id)    REFERENCES clothes (id) ON DELETE SET NULL,
  CONSTRAINT fk_equipped_bottom FOREIGN KEY (bottom_clothes_id) REFERENCES clothes (id) ON DELETE SET NULL,
  CONSTRAINT fk_equipped_hat    FOREIGN KEY (hat_clothes_id)    REFERENCES clothes (id) ON DELETE SET NULL,
  CONSTRAINT fk_equipped_shoes  FOREIGN KEY (shoes_clothes_id)  REFERENCES clothes (id) ON DELETE SET NULL,
  CONSTRAINT fk_equipped_gloves FOREIGN KEY (gloves_clothes_id) REFERENCES clothes (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='입은 의상';

-- 확인: 네 표가 보이면 성공
SHOW TABLES LIKE '%clothes%';
SHOW TABLES LIKE 'reward_claims';
