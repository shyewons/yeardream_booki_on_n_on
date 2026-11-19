-- 임시 의상 데이터 (2026-11-19, 팀 확인 받은 임시안. 진짜 의상이 정해지면 이 파일을 고친다)
-- 요구사항: FR-039 일기 주간 보상, FR-040 동화 단계별 구성품, FR-041 옷장
--
-- 들어가는 것 (모두 43개, 이미지는 아직 없어서 image_url = NULL)
--   일기 10개: 주간 목표(5일)를 달성한 순서(reward_order 1~10)대로 받는다. 모든 사용자에게 같은 순서
--   동화 33개: 켜진 동화 주제 10개 + 자유 주제('내가 정할래요') 1개 × 3구간. 1번째 = 모자, 2번째 = 상의, 3번째 = 신발
--   자유 주제도 주제 하나로 센다 (2026-11-19 결정). 자유 주제 줄은 is_active = 0 이라 아래에서 따로 넣는다
--
-- 보상 기준 숫자는 backend/reward_rules.py 가 기준이다 (WEEK_MIN_DAYS, STORY_REWARD_CHAPTERS).
--   required_count 는 NOT NULL 이라 같은 숫자(5 / 3·6·10)로 채우지만, 보상 코드는 이 칸을 읽지 않는다.
--   옷은 reward_order 로 찾는다 (일기: 달성 차수, 동화: 주제 안에서 몇 번째 구간인지)
--
-- 동화 옷은 주제 '이름'으로 fairy_topics 번호를 찾는다 (번호가 바뀌어도 맞게 들어가도록).
--   주제 이름이 없으면 그 줄은 들어가지 않으니, 실행 뒤 맨 아래 확인 쿼리에서 40개인지 본다.
--
-- 다시 실행하면 의상을 모두 지우고 새로 넣는다.
--   아이가 이미 받은 옷이 있으면(user_clothes · reward_claims) DELETE 가 외래키로 막힌다. 그때는 지우지 말고
--   UPDATE 로 이름 · 이미지만 바꾼다.

USE app_db;
SET time_zone = '+09:00';

START TRANSACTION;

DELETE FROM clothes;

-- ── 일기 주간 보상 (reward_order = 몇 번째로 주간 목표를 달성했는지) ──
INSERT INTO clothes (name, slot, reward_kind, reward_order, required_count, fairy_topic_id) VALUES
('빨간 티셔츠',   'top',    'diary', 1,  5, NULL),
('노란 바지',     'bottom', 'diary', 2,  5, NULL),
('파란 모자',     'hat',    'diary', 3,  5, NULL),
('초록 운동화',   'shoes',  'diary', 4,  5, NULL),
('하얀 장갑',     'gloves', 'diary', 5,  5, NULL),
('줄무늬 티셔츠', 'top',    'diary', 6,  5, NULL),
('청바지',        'bottom', 'diary', 7,  5, NULL),
('밀짚모자',      'hat',    'diary', 8,  5, NULL),
('장화',          'shoes',  'diary', 9,  5, NULL),
('털장갑',        'gloves', 'diary', 10, 5, NULL);

-- ── 동화 주제별 세트 (reward_order 1·2·3 = 3장·6장·10장 구간) ──
INSERT INTO clothes (name, slot, reward_kind, reward_order, required_count, fairy_topic_id)
SELECT s.name, s.slot, 'fairy', s.reward_order, s.required_count, t.id
FROM (
              SELECT '토끼' AS topic, '토끼 귀 머리띠' AS name, 'hat' AS slot, 1 AS reward_order, 3 AS required_count
    UNION ALL SELECT '토끼',             '토끼 조끼',       'top',   2, 6
    UNION ALL SELECT '토끼',             '토끼 발 신발',    'shoes', 3, 10
    UNION ALL SELECT '작은 용',          '용 뿔 모자',      'hat',   1, 3
    UNION ALL SELECT '작은 용',          '용 비늘 옷',      'top',   2, 6
    UNION ALL SELECT '작은 용',          '용 발톱 신발',    'shoes', 3, 10
    UNION ALL SELECT '바닷속 학교',      '물고기 모자',     'hat',   1, 3
    UNION ALL SELECT '바닷속 학교',      '해초 셔츠',       'top',   2, 6
    UNION ALL SELECT '바닷속 학교',      '오리발',          'shoes', 3, 10
    UNION ALL SELECT '장난감 로봇',      '로봇 안테나',     'hat',   1, 3
    UNION ALL SELECT '장난감 로봇',      '로봇 갑옷',       'top',   2, 6
    UNION ALL SELECT '장난감 로봇',      '로봇 부츠',       'shoes', 3, 10
    UNION ALL SELECT '마법 가방',        '마법사 모자',     'hat',   1, 3
    UNION ALL SELECT '마법 가방',        '마법사 망토',     'top',   2, 6
    UNION ALL SELECT '마법 가방',        '마법 구두',       'shoes', 3, 10
    UNION ALL SELECT '비밀 문',          '열쇠 모자',       'hat',   1, 3
    UNION ALL SELECT '비밀 문',          '탐험가 조끼',     'top',   2, 6
    UNION ALL SELECT '비밀 문',          '탐험가 신발',     'shoes', 3, 10
    UNION ALL SELECT '말하는 나무',      '나뭇잎 화관',     'hat',   1, 3
    UNION ALL SELECT '말하는 나무',      '나무껍질 옷',     'top',   2, 6
    UNION ALL SELECT '말하는 나무',      '뿌리 신발',       'shoes', 3, 10
    UNION ALL SELECT '구름 마을',        '구름 모자',       'hat',   1, 3
    UNION ALL SELECT '구름 마을',        '구름 솜옷',       'top',   2, 6
    UNION ALL SELECT '구름 마을',        '구름 신발',       'shoes', 3, 10
    UNION ALL SELECT '길 잃은 별',       '별 머리띠',       'hat',   1, 3
    UNION ALL SELECT '길 잃은 별',       '별빛 망토',       'top',   2, 6
    UNION ALL SELECT '길 잃은 별',       '반짝 신발',       'shoes', 3, 10
    UNION ALL SELECT '하늘을 나는 신발', '비행 고글',       'hat',   1, 3
    UNION ALL SELECT '하늘을 나는 신발', '비행사 점퍼',     'top',   2, 6
    UNION ALL SELECT '하늘을 나는 신발', '날개 신발',       'shoes', 3, 10
) AS s
JOIN fairy_topics t ON t.title = s.topic AND t.is_active = 1;

-- ── 자유 주제 세트 ('내가 정할래요'로 만든 책. 추천에는 안 나오는 줄이라 is_active 를 보지 않는다) ──
-- 제목 비교는 books_repo.FREE_TOPIC_TITLE 과 같이 띄어쓰기를 뺀다
INSERT INTO clothes (name, slot, reward_kind, reward_order, required_count, fairy_topic_id)
SELECT s.name, s.slot, 'fairy', s.reward_order, s.required_count, t.id
FROM (
              SELECT '꽃 모자' AS name, 'hat' AS slot, 1 AS reward_order, 3 AS required_count
    UNION ALL SELECT '꽃무늬 셔츠', 'top',   2, 6
    UNION ALL SELECT '꽃 신발',     'shoes', 3, 10
) AS s
JOIN (SELECT MIN(id) AS id FROM fairy_topics WHERE REPLACE(title, ' ', '') = '자유주제') AS t ON t.id IS NOT NULL;

COMMIT;

-- 확인: diary 10, fairy 33 이어야 한다
SELECT reward_kind, COUNT(*) AS n FROM clothes GROUP BY reward_kind;
