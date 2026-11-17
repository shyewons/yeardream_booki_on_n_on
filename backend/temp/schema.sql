-- 글쓰기 파트 ERD 초안 (MySQL 8 / DBeaver)
-- 구조: users 1:N books 1:N entries 1:N sentences 1:N corrections
-- 이름은 초안이라 바뀔 수 있음. 바꾸면 이 파일만 고쳐서 다시 실행.
-- 시각 규칙: DB 서버는 UTC라서 *_at 값은 앱이 한국 시간(Asia/Seoul)으로 직접 만들어 넣는다.
--            (DBeaver에서 직접 넣을 땐 먼저 SET time_zone = '+09:00'; 를 실행)

USE app_db;

-- 다시 만들 때 편하게 (자식 → 부모 순서로 삭제). 데이터가 다 날아가니 개발 중에만 사용.
DROP TABLE IF EXISTS corrections;
DROP TABLE IF EXISTS sentences;
DROP TABLE IF EXISTS entries;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS users;

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

-- 책 (일기 동물 / 동화책 한 권)
CREATE TABLE books (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  kind        ENUM('diary','fairy') NOT NULL COMMENT '종류: 일기/동화',
  title       VARCHAR(60)  NOT NULL COMMENT '제목 (일기는 동물 이름)',
  cover       VARCHAR(20)  NULL COMMENT '표지/동물 모양 (양, 알파카 등)',
  visibility  ENUM('full','stats') NOT NULL DEFAULT 'stats' COMMENT '공개여부: 원문 공개/통계만 (협의 필요)',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_books_user (user_id),
  CONSTRAINT fk_books_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='책';

-- 글 (일기 하루 / 동화 한 편)
CREATE TABLE entries (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  book_id      BIGINT UNSIGNED NOT NULL,
  diary_date   DATE NULL COMMENT '일기 날짜: 한 책 안에서 하루 = 글 하나 (동화는 NULL)',
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
  PRIMARY KEY (id),
  UNIQUE KEY uq_entries_book_date (book_id, diary_date),  -- 같은 책, 같은 날짜의 글은 하나만 (NULL은 여러 개 가능)
  CONSTRAINT fk_entries_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='글';

-- 문장 (유효성 검사 + 최종 결과)
CREATE TABLE sentences (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entry_id         BIGINT UNSIGNED NOT NULL,
  seq              INT NOT NULL COMMENT '순서',
  original         TEXT NOT NULL COMMENT '원문 (original_sentence)',
  revised          TEXT NOT NULL COMMENT '최종문장 (revised_sentence)',
  attempt_count    INT NOT NULL DEFAULT 1 COMMENT '입력횟수: 통과까지 시도한 횟수 (유효성 검사)',
  invalid_reasons  JSON NULL COMMENT '틀린이유: 유효성 검사에서 틀린 이유들 (list)',
  has_correction   TINYINT NOT NULL DEFAULT 0 COMMENT '교정여부 (has_correction)',
  correction_mode  VARCHAR(20) NULL COMMENT '교정방식 (mode)',
  expression_choice JSON NULL COMMENT '표현선택 (동화에서 고른 표현)',
  written_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '작성날짜',
  PRIMARY KEY (id),
  UNIQUE KEY uq_sentences_order (entry_id, seq),
  CONSTRAINT fk_sentences_entry FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
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
