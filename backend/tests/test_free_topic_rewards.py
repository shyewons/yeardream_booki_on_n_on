"""자유 주제 보상 제외를 메모리 DB에서 검사한다. 실제 사용자 데이터는 건드리지 않는다."""
import sqlite3
import unittest
from unittest.mock import patch

import rewards_repo as rewards


class FreeTopicRewardTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.addCleanup(self.connection.close)
        self.connection.executescript("""
            CREATE TABLE books (id INTEGER, user_id INTEGER, kind TEXT, fairy_topic_id INTEGER);
            CREATE TABLE fairy_topics (id INTEGER, title TEXT, prompt TEXT, opening TEXT);
            CREATE TABLE clothes (id INTEGER, name TEXT, slot TEXT, image_url TEXT,
                reward_kind TEXT, fairy_topic_id INTEGER, reward_order INTEGER);
            CREATE TABLE reward_claims (book_id INTEGER, reward_kind TEXT, reward_order INTEGER,
                claimed_at TEXT, clothes_id INTEGER);
            INSERT INTO fairy_topics (id, title) VALUES (1, '고양이'), (21, '자유 주제'), (22, '자유주제');
            INSERT INTO books VALUES (10, 99, 'fairy', 1), (20, 99, 'fairy', 21),
                (30, 99, 'fairy', NULL), (40, 99, 'fairy', 22), (50, 100, 'fairy', 1),
                (60, 99, 'diary', NULL);
            INSERT INTO clothes VALUES (1, '고양이 모자', 'hat', '/cat.png', 'fairy', 1, 1),
                (2, '고양이 옷', 'top', '/cat-top.png', 'fairy', 1, 2),
                (3, '고양이 신발', 'shoes', '/cat-shoes.png', 'fairy', 1, 3),
                (4, '자유 주제 선물', 'hat', '/free.png', 'fairy', 21, 1);
        """)

        def query(sql, parameters=None):
            return [dict(row) for row in self.connection.execute(sql, parameters or {})]

        self.query = patch.object(rewards.db, "query", side_effect=query).start()
        self.progress = patch.object(rewards.progress_repo, "story_progress", return_value={"qualified": 10}).start()
        self.write = patch.object(rewards.db, "run_in_transaction").start()
        self.addCleanup(patch.stopall)

    def test_free_topics_have_no_reward_stages_even_if_clothes_exist(self):
        for book_id in (20, 30, 40):
            with self.subTest(book_id=book_id):
                info = rewards.fairy_reward(99, book_id)
                self.assertFalse(info["enabled"])
                self.assertEqual(info["stages"], [])
                self.assertIsNone(info["next"])
        self.write.assert_not_called()

    def test_free_topic_direct_claim_cannot_grant_a_reward(self):
        for book_id in (20, 30, 40):
            for order in (1, 2, 3):
                with self.subTest(book_id=book_id, order=order):
                    with self.assertRaisesRegex(rewards.BadRequest, "자유 주제"):
                        rewards.claim_fairy(99, book_id, order)
        self.write.assert_not_called()

    def test_chosen_topic_keeps_its_reward_thresholds(self):
        for count, statuses, next_count in (
            (2, ["locked", "locked", "locked"], 3),
            (3, ["claimable", "locked", "locked"], 6),
            (6, ["claimable", "claimable", "locked"], 10),
            (10, ["claimable", "claimable", "claimable"], None),
        ):
            with self.subTest(count=count):
                self.progress.return_value = {"qualified": count}
                info = rewards.fairy_reward(99, 10)
                self.assertTrue(info["enabled"])
                self.assertEqual([stage["status"] for stage in info["stages"]], statuses)
                self.assertEqual([stage["clothes"]["id"] for stage in info["stages"]], [1, 2, 3])
                self.assertEqual(info["next"]["chapters"] if info["next"] else None, next_count)

    def test_only_owned_fairy_books_are_accessible(self):
        for book_id in (50, 60, 999):
            with self.subTest(book_id=book_id):
                self.assertIsNone(rewards.fairy_reward(99, book_id))
                self.assertIsNone(rewards.claim_fairy(99, book_id, 1))
        self.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
