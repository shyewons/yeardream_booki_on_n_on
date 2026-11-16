-- 더미데이터 (목록 불러오기 · 페이징 시험용)
-- 사용자 dummy_user 한 명만 만들고, 지우려면 아래 한 줄이면 됨 (책·글·문장·교정이 같이 지워짐):
--     DELETE FROM users WHERE nickname = 'dummy_user';
-- 이 파일은 여러 번 실행해도 됨 (맨 처음에 dummy_user를 지우고 다시 만듦).
--
-- 들어가는 것
--   책 11권 (일기 7 + 동화 4)  → 5권씩이면 5 / 5 / 1 권으로 3쪽
--   몽실(일기): 글 23개 (2026-10-21 ~ 11-12)       → 10개씩이면 10 / 10 / 3 으로 3쪽, 가장 최근 글은 '쓰는 중'
--   구름·보리·콩이·별이(일기): 글 3개씩, 두부(일기): 1개, 하양(일기): 0개 (빈 책)
--   동화 4권: 글(이야기) 1개씩, 날짜 없음
--   모든 글에 문장 3개 (2번 문장은 교정 있음, 3번 문장은 2번 만에 통과)

USE app_db;
SET time_zone = '+09:00';   -- DBeaver에서 시각 자동값이 UTC로 들어가지 않게

DELETE FROM users WHERE nickname = 'dummy_user';

INSERT INTO users (nickname, token_hash, created_at)
VALUES ('dummy_user', 'dummy-token-hash', '2026-11-01 08:00:00');
SET @uid = LAST_INSERT_ID();

-- 책 11권 (만든 시각을 하루씩 다르게 해서 정렬이 흔들리지 않게)
INSERT INTO books (user_id, kind, title, cover, visibility, created_at) VALUES
  (@uid, 'diary', '몽실', 'sheep',   'stats', '2026-10-20 09:00:00'),
  (@uid, 'diary', '구름', 'alpaca',  'stats', '2026-10-21 09:00:00'),
  (@uid, 'diary', '보리', 'sheep',   'stats', '2026-10-22 09:00:00'),
  (@uid, 'diary', '콩이', 'alpaca',  'stats', '2026-10-23 09:00:00'),
  (@uid, 'diary', '하양', 'sheep',   'stats', '2026-10-24 09:00:00'),
  (@uid, 'diary', '별이', 'alpaca',  'stats', '2026-10-25 09:00:00'),
  (@uid, 'diary', '두부', 'sheep',   'stats', '2026-10-26 09:00:00'),
  (@uid, 'fairy', '솜이', 'alpaca',  'stats', '2026-10-27 09:00:00'),
  (@uid, 'fairy', '달이', 'sheep',   'stats', '2026-10-28 09:00:00'),
  (@uid, 'fairy', '미르', 'alpaca',  'stats', '2026-10-29 09:00:00'),
  (@uid, 'fairy', '나무', 'sheep',   'stats', '2026-10-30 09:00:00');

-- 일기 글: 하루 = 글 하나. 날짜는 2026-11-12부터 하루씩 거슬러 올라감
INSERT INTO entries (book_id, diary_date, status, draft_text, draft_saved_at, saved_at, edited_at, created_at)
SELECT b.id,
       x.d,
       IF(x.n = 0 AND b.title = '몽실', 'writing', 'done'),
       IF(x.n = 0 AND b.title = '몽실', '오늘은 날씨가', NULL),
       IF(x.n = 0 AND b.title = '몽실', TIMESTAMP(x.d, '19:12:00'), NULL),
       IF(x.n = 0 AND b.title = '몽실', NULL, TIMESTAMP(x.d, '20:30:00')),
       IF(x.n = 0 AND b.title = '몽실', TIMESTAMP(x.d, '19:10:00'), TIMESTAMP(x.d, '20:30:00')),
       TIMESTAMP(x.d, '19:00:00')
FROM books b
JOIN (
  SELECT t.n, DATE_SUB('2026-11-12', INTERVAL t.n DAY) AS d
  FROM (SELECT a.n + c.n AS n
        FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
              UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
        CROSS JOIN (SELECT 0 n UNION ALL SELECT 10 UNION ALL SELECT 20) c
        WHERE a.n + c.n < 23) t
) x
WHERE b.user_id = @uid
  AND b.kind = 'diary'
  AND ( b.title = '몽실'                                    -- 23개
        OR (b.title IN ('구름', '보리', '콩이', '별이') AND x.n < 3)   -- 3개
        OR (b.title = '두부' AND x.n < 1) );                 -- 1개  (하양은 0개)

-- 동화 글: 책 한 권에 이야기 한 편, 날짜 없음
INSERT INTO entries (book_id, diary_date, status, saved_at, edited_at, created_at)
SELECT b.id, NULL, 'done', '2026-11-05 20:30:00', '2026-11-05 20:30:00', '2026-11-05 19:00:00'
FROM books b
WHERE b.user_id = @uid AND b.kind = 'fairy';

-- 문장: 글마다 3개
INSERT INTO sentences
  (entry_id, seq, original, revised, attempt_count, invalid_reasons, has_correction, correction_mode, written_at)
SELECT e.id,
       s.n,
       IF(s.n = 2, '오날은 학교에 갔다.',
          CONCAT(IFNULL(DATE_FORMAT(e.diary_date, '%m월 %d일'), '옛날 옛적에'), ' 더미 문장 ', s.n, '번째예요.')),
       IF(s.n = 2, '오늘은 학교에 갔다.',
          CONCAT(IFNULL(DATE_FORMAT(e.diary_date, '%m월 %d일'), '옛날 옛적에'), ' 더미 문장 ', s.n, '번째예요.')),
       IF(s.n = 3, 2, 1),
       IF(s.n = 3, JSON_ARRAY('too_short'), JSON_ARRAY()),
       IF(s.n = 2, 1, 0),
       IF(s.n = 2, 'correction', 'none'),
       TIMESTAMP(IFNULL(e.diary_date, '2026-11-05'), MAKETIME(19, 30 + s.n, 0))
FROM entries e
JOIN books b ON b.id = e.book_id
JOIN (SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3) s
WHERE b.user_id = @uid;

-- 교정 항목: 교정이 있는 문장마다 한 줄
INSERT INTO corrections
  (sentence_id, idx, start_pos, end_pos, before_text, after_text, explanation,
   evidence_doc_id, evidence_article, evidence_page, evidence_score, query_text, error_type)
SELECT s.id, 0, 0, 2, '오날', '오늘', '(더미) 오늘이 맞는 표기예요.',
       'dummy-doc', '제43항', 100, 0.82, '오날 오늘', 'spelling'
FROM sentences s
JOIN entries e ON e.id = s.entry_id
JOIN books b ON b.id = e.book_id
WHERE b.user_id = @uid AND s.has_correction = 1;

-- ───────── 확인용 (아래 두 개를 실행해서 숫자가 맞는지 보기) ─────────
-- 책별 글 개수: 몽실 23, 구름·보리·콩이·별이 3, 두부 1, 하양 0, 동화 4권은 1씩
SELECT b.id, b.kind, b.title, COUNT(e.id) AS entries
FROM books b
LEFT JOIN entries e ON e.book_id = b.id
WHERE b.user_id = @uid
GROUP BY b.id, b.kind, b.title
ORDER BY b.created_at, b.id;

-- 전체 개수: 책 11, 글 40 (23 + 12 + 1 + 4), 문장 120, 교정 40
SELECT (SELECT COUNT(*) FROM books WHERE user_id = @uid) AS books,
       (SELECT COUNT(*) FROM entries e JOIN books b ON b.id = e.book_id WHERE b.user_id = @uid) AS entries,
       (SELECT COUNT(*) FROM sentences s JOIN entries e ON e.id = s.entry_id JOIN books b ON b.id = e.book_id WHERE b.user_id = @uid) AS sentences,
       (SELECT COUNT(*) FROM corrections c JOIN sentences s ON s.id = c.sentence_id JOIN entries e ON e.id = s.entry_id JOIN books b ON b.id = e.book_id WHERE b.user_id = @uid) AS corrections;
