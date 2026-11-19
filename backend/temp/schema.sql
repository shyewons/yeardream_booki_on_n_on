-- 글쓰기 파트 ERD 초안 (MySQL 8 / DBeaver)
-- 구조: users 1:N books 1:N entries 1:N sentences 1:N corrections
-- 이름은 초안이라 바뀔 수 있음. 바꾸면 이 파일만 고쳐서 다시 실행.
-- 보상 쪽 표(clothes, user_clothes, user_equipped_clothes, reward_claims)는 팀원이 DB 에 직접 만들었고 여기에는 없다.
-- fairy_topics 는 sentences 가 참조해서 아래에 적어 두었다 (칸은 DB 와 같게. 정확한 정의는 SHOW CREATE TABLE fairy_topics 로 확인).
-- 시각 규칙: DB 서버는 UTC라서 *_at 값은 앱이 한국 시간(Asia/Seoul)으로 직접 만들어 넣는다.
--            (DBeaver에서 직접 넣을 땐 먼저 SET time_zone = '+09:00'; 를 실행)

USE app_db;

-- 다시 만들 때 편하게 (자식 → 부모 순서로 삭제). 데이터가 다 날아가니 개발 중에만 사용.
DROP TABLE IF EXISTS corrections;
DROP TABLE IF EXISTS sentences;
DROP TABLE IF EXISTS entries;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS fairy_topics;

-- 사용자 (별명 + 유저구분번호; 로그인 없음)
CREATE TABLE users (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nickname    VARCHAR(30)  NOT NULL COMMENT '별명 (유일, 중복 불가)',
  token_hash  VARCHAR(255) NOT NULL COMMENT '토큰 (해시로 저장, 원문 저장 금지)',
  user_code   VARCHAR(255) NULL COMMENT '유저구분번호: 아이가 입력하는 비밀코드 (디자인에 화면 없음, 저장 방식 협의)',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '만든시각',
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_nickname (nickname)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='사용자';

-- 동화 주제 (새 책 만들기에서 고른다. 주제 추천 /api/topics 는 켜진 것만 읽는다. 책과 문장에 고른 주제 번호가 남는다)
-- 주제는 요구사항정의서 '동화주제' 시트 10개 (2026-11-19). 이름 · 쓰기 안내(prompt) · 시작 상황(opening).
-- '자유 주제' 줄은 '내가 정할래요'로 만든 책 · 문장이 가리키는 줄이다 (is_active = 0 이라 추천에는 안 나온다. books_repo.FREE_TOPIC_TITLE)
CREATE TABLE fairy_topics (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title       VARCHAR(100) NOT NULL COMMENT '주제 이름 (예: 토끼). 자유 주제 줄은 ''자유 주제''',
  prompt      VARCHAR(200) NULL COMMENT '쓰기 안내: 주제 카드에 보인다 (예: 토끼가 주인공인 동화를 만들어 봐!)',
  opening     VARCHAR(200) NULL COMMENT '시작 상황: 글쓰기 첫 장에 보인다 (예: 토끼가 숲에서 … 누구의 발자국일까?)',
  is_active   TINYINT NOT NULL DEFAULT 1 COMMENT '추천에 쓰는지 (0 이면 추천에서 빠진다. 이미 쓴 책 · 문장의 번호는 그대로)',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='동화 주제 목록';

INSERT INTO fairy_topics (title, prompt, opening, is_active, created_at) VALUES
('토끼','토끼가 주인공인 동화를 만들어 봐!','토끼가 숲에서 자기 발보다 훨씬 큰 발자국을 발견했어. 누구의 발자국일까?',1,NOW()),
('마법 가방','신기한 마법 가방이 나오는 동화를 만들어 봐!','가방에서 필요한 물건이 나오는데, 꼭 하나씩 엉뚱한 물건도 따라 나와. 오늘은 무엇이 나왔을까?',1,NOW()),
('구름 마을','구름 위에 있는 마을을 상상하며 동화를 만들어 봐!','구름 마을에 도착했는데, 마을이 바람을 따라 움직이기 시작했어. 어디로 가는 걸까?',1,NOW()),
('말하는 나무','말을 할 수 있는 나무가 나오는 동화를 만들어 봐!','매일 지나치던 나무가 오늘 처음으로 말을 걸었어. 나무는 무슨 이야기를 하고 싶었을까?',1,NOW()),
('작은 용','작은 용이 주인공인 동화를 만들어 봐!','작은 용은 불 대신 비눗방울을 뿜어. 이 능력으로 어떤 일이 벌어질까?',1,NOW()),
('비밀 문','새로운 곳으로 이어지는 비밀 문에 관한 동화를 만들어 봐!','방 안에 처음 보는 작은 문이 생겼어. 문 너머에서 누군가 똑똑 두드려. 누가 찾아온 걸까?',1,NOW()),
('바닷속 학교','바닷속 학교에서 벌어지는 동화를 만들어 봐!','바닷속 학교에 새 친구가 왔는데, 수영을 할 줄 모른대. 이 친구는 어떻게 학교에 오게 됐을까?',1,NOW()),
('길 잃은 별','집으로 돌아가고 싶은 별에 관한 동화를 만들어 봐!','창문 밖에 작은 별이 앉아 있어. 하늘로 돌아가는 길을 잊어버렸대. 어떤 여행이 시작될까?',1,NOW()),
('장난감 로봇','장난감 로봇이 주인공인 동화를 만들어 봐!','잠에서 깨어 보니 장난감 로봇이 여행 가방을 싸고 있어. 로봇은 어디로 떠나려는 걸까?',1,NOW()),
('하늘을 나는 신발','하늘을 나는 신발이 나오는 동화를 만들어 봐!','신발을 신었더니 발이 둥실 떠올랐어. 그런데 신발이 가고 싶은 곳이 따로 있대. 어디로 데려갈까?',1,NOW()),
('자유 주제',NULL,NULL,0,NOW());

-- 책 (일기 동물 / 동화책 한 권)
CREATE TABLE books (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  kind        ENUM('diary','fairy') NOT NULL COMMENT '종류: 일기/동화',
  fairy_topic_id BIGINT UNSIGNED NULL COMMENT '동화: 책 만들 때 고른 주제. 내가 정할래요 = 자유 주제 줄 (일기는 늘 NULL)',
  finished_at  DATETIME NULL COMMENT '동화: 이야기 끝내기를 누른 시각 (NULL = 아직 쓰는 중)',
  finish_asked INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '동화: 끝낼지 물어보고 아이가 이어 쓰기를 고른 마지막 장 구간 (reward_rules.STORY_FINISH_ASK_AT, 지금은 묻지 않아 0)',
  title       VARCHAR(60)  NOT NULL COMMENT '제목 (일기는 동물 이름)',
  cover       VARCHAR(20)  NULL COMMENT '표지/동물 모양 (양, 알파카 등)',
  visibility  ENUM('full','stats') NOT NULL DEFAULT 'stats' COMMENT '공개여부: 원문 공개/통계만 (협의 필요)',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_books_user (user_id),
  KEY idx_books_topic (fairy_topic_id),
  CONSTRAINT fk_books_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_books_topic FOREIGN KEY (fairy_topic_id) REFERENCES fairy_topics (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='책';

-- 글 (일기 하루 / 동화 한 편)
CREATE TABLE entries (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  book_id      BIGINT UNSIGNED NOT NULL,
  diary_date   DATE NULL COMMENT '일기 날짜: 한 책 안에서 하루 = 글 하나 (동화는 NULL)',
  chapter_no   INT UNSIGNED NULL COMMENT '동화: 몇 장인지 (1~100, reward_rules.STORY_MAX_CHAPTERS). 일기는 NULL',
  status       ENUM('writing','done') NOT NULL DEFAULT 'writing' COMMENT '작성상태: 문장을 고치면 writing, 이야기 저장하기를 누르면 done',
  draft_text   TEXT NULL COMMENT '임시입력: 검사 전 입력 중인 문장 (덮어쓰기)',
  draft_saved_at DATETIME NULL COMMENT '임시저장시각',
  draft_mode   VARCHAR(10) NULL COMMENT '임시입력 종류: new 새 문장 / edit 다시쓰기 / insert 위에 넣기',
  draft_seq    INT NULL COMMENT '임시입력 자리: edit·insert 일 때 몇 번째 문장인지',
  saved_at     DATETIME NULL COMMENT '저장시각: 이야기 저장하기를 누른 때',
  edited_at    DATETIME NULL COMMENT '수정시각: 문장 내용이 바뀔 때만 갱신',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '만든시각',
  checked      TINYINT NOT NULL DEFAULT 0 COMMENT '확인여부 (선생님/부모님 확인)',
  check_log    JSON NULL COMMENT '확인내역 (list)',
  checked_at   DATETIME NULL COMMENT '확인날짜 (< edited_at 이면 확인 후 수정됨)',
  day_done_at  DATETIME NULL COMMENT '일기 하루치(기준 문장 수) 처음 달성 시각. 지난 날짜는 기준 일수 안에 채웠을 때만 (reward_rules.py)',
  PRIMARY KEY (id),
  UNIQUE KEY uq_entries_book_date (book_id, diary_date),  -- 같은 책, 같은 날짜의 글은 하나만 (NULL은 여러 개 가능)
  UNIQUE KEY uq_entries_chapter (book_id, chapter_no),     -- 동화: 같은 책, 같은 장의 글은 하나만 (일기의 NULL은 여러 개 가능)
  CONSTRAINT fk_entries_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='글';

-- 문장 (유효성 검사 + 최종 결과)
CREATE TABLE sentences (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entry_id         BIGINT UNSIGNED NOT NULL,
  seq              INT NULL COMMENT '순서 (다시쓰기 · 지우기 · 표현 선택으로 화면에서 빠진 줄은 NULL)',
  original         TEXT NOT NULL COMMENT '원문 (original_sentence)',
  revised          TEXT NOT NULL COMMENT '최종문장 (revised_sentence)',
  attempt_count    INT NOT NULL DEFAULT 1 COMMENT '입력횟수: 통과까지 시도한 횟수 (유효성 검사)',
  invalid_reasons  JSON NULL COMMENT '틀린이유: 유효성 검사에서 틀린 이유들 (list)',
  has_correction   TINYINT NOT NULL DEFAULT 0 COMMENT '교정여부 (has_correction)',
  correction_mode  VARCHAR(20) NULL COMMENT '교정방식 (mode)',
  expression_choice JSON NULL COMMENT '표현선택 (동화에서 고른 표현)',
  written_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '작성날짜',
  ended_at         DATETIME NULL COMMENT '화면에서 빠진 시각 (다시쓰기 · 지우기 · 표현 선택으로 바뀐 때). 보이는 줄은 NULL',
  end_reason       VARCHAR(10) NULL COMMENT '빠진 이유: edit 다시쓰기 / delete 지우기 / expr 동화 표현 선택',
  fairy_topic_id   BIGINT UNSIGNED NULL COMMENT '이 문장을 쓸 때 고른 동화 주제 (자유 주제는 자유 주제 줄). 일기는 NULL',
  PRIMARY KEY (id),
  UNIQUE KEY uq_sentences_order (entry_id, seq),   -- 보이는 줄의 순서는 겹치지 않는다 (빠진 줄의 NULL 은 여러 개 가능)
  KEY idx_sentences_topic (fairy_topic_id),
  CONSTRAINT fk_sentences_entry FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE,
  CONSTRAINT fk_sentences_topic FOREIGN KEY (fairy_topic_id) REFERENCES fairy_topics (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='문장';

-- 교정 항목 (corrections[] 한 줄이 한 행)
CREATE TABLE corrections (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sentence_id      BIGINT UNSIGNED NOT NULL,
  idx              INT NOT NULL COMMENT 'index',
  start_pos        INT NULL COMMENT 'start',
  end_pos          INT NULL COMMENT 'end',
  before_text      VARCHAR(200) NOT NULL COMMENT 'before',
  after_text       VARCHAR(200) NOT NULL COMMENT 'after',
  explanation      TEXT NULL,
  evidence_doc_id  VARCHAR(100) NULL,
  evidence_part    VARCHAR(40) NULL COMMENT '근거 문서 이름 (한글 맞춤법 / 표준어 사정 원칙). 두 문서에 같은 조항 번호가 있어 조항과 함께 봐야 한다',
  evidence_article VARCHAR(100) NULL,
  evidence_page    INT NULL,
  evidence_score   FLOAT NULL,
  evidences        JSON NULL COMMENT '근거 조항 전체 (최대 3개) [{doc_id, part, article, page, score, source}]. 위 evidence_* 는 그중 대표 1개',
  query_text       VARCHAR(500) NULL COMMENT 'query',
  error_type       VARCHAR(40) NULL COMMENT '판정 유형 (파이프라인의 type: ①표기만 / ②띄어쓰기+구체 / ③띄어쓰기+표기 / ④일반 띄어쓰기)',
  PRIMARY KEY (id),
  KEY idx_corrections_sentence (sentence_id),
  KEY idx_corrections_type (error_type),
  CONSTRAINT fk_corrections_sentence FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='교정 항목';
