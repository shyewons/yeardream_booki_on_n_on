"""실제 DB에 쓰지 않고 보상 지급 및 착용 변경의 경계를 검사한다."""
import unittest
from unittest.mock import Mock, patch

import rewards_repo as rewards


class WardrobeTests(unittest.TestCase):
    def setUp(self):
        self.tx = Mock()
        self.query = patch.object(rewards.db, "query", return_value=[{"slot": "bottom"}]).start()
        self.transaction = patch.object(rewards.db, "run_in_transaction", side_effect=lambda work: work(self.tx)).start()
        self.result = patch.object(rewards, "character", return_value={"top": None, "bottom": {"id": 3}}).start()
        self.addCleanup(patch.stopall)

    def test_bottom_replaces_one_piece_in_same_transaction(self):
        self.tx.query.return_value = [{"image_url": "/images/wardrobe/story/01-cat/outfit-cat-pinafore.png"}]
        result = rewards.equip(99, "bottom", 3)
        self.transaction.assert_called_once()
        sql, parameters = self.tx.execute.call_args.args
        self.assertIn("top_clothes_id = NULL", sql)
        self.assertIn("bottom_clothes_id = :cid", sql)
        self.assertEqual(parameters, {"uid": 99, "cid": 3})
        self.assertIn("FOR UPDATE", self.tx.query.call_args.args[0])
        self.assertEqual(result["character"]["bottom"]["id"], 3)

    def test_regular_top_is_not_removed(self):
        self.tx.query.return_value = [{"image_url": "/images/wardrobe/diary/top-coral-tshirt.png"}]
        rewards.equip(99, "bottom", 3)
        self.assertNotIn("top_clothes_id = NULL", self.tx.execute.call_args.args[0])

    def test_removing_bottom_keeps_one_piece(self):
        rewards.equip(99, "bottom", None)
        self.assertNotIn("top_clothes_id", self.tx.execute.call_args.args[0])

    def test_donning_one_piece_preserves_previous_bottom(self):
        self.query.return_value = [{"slot": "top"}]
        rewards.equip(99, "top", 2)
        self.assertNotIn("bottom_clothes_id", self.tx.execute.call_args.args[0])

    def test_unowned_or_wrong_slot_never_writes(self):
        for rows in ([], [{"slot": "hat"}]):
            with self.subTest(rows=rows):
                self.query.return_value = rows
                with self.assertRaises(rewards.BadRequest):
                    rewards.equip(99, "bottom", 3)
        self.transaction.assert_not_called()

    def test_failed_transaction_does_not_return_success(self):
        self.transaction.side_effect = RuntimeError("storage unavailable")
        with self.assertRaises(RuntimeError):
            rewards.equip(99, "bottom", 3)
        self.result.assert_not_called()


class RewardTests(unittest.TestCase):
    def test_fairy_claim_rejects_locked_claimed_or_missing_asset(self):
        for status, clothes, exception in (
            ("locked", {"id": 5}, rewards.BadRequest),
            ("claimed", {"id": 5}, rewards.AlreadyClaimed),
            ("claimable", None, rewards.BadRequest),
        ):
            with self.subTest(status=status, clothes=clothes):
                with patch.object(rewards, "fairy_reward", return_value={"enabled": True, "stages": [{"status": status, "chapters": 3, "clothes": clothes}]}), patch.object(rewards.db, "run_in_transaction") as write:
                    with self.assertRaises(exception):
                        rewards.claim_fairy(99, 10, 1)
                    write.assert_not_called()

    def test_fairy_grant_and_owned_item_are_written_together(self):
        tx = Mock()
        clothes = {"id": 5, "image_url": "/images/wardrobe/story/01-cat/hat-cat-earband-pigtails.png"}
        info = {"enabled": True, "stages": [{"status": "claimable", "chapters": 3, "clothes": clothes}]}
        with patch.object(rewards, "fairy_reward", return_value=info), patch.object(rewards.db, "run_in_transaction", side_effect=lambda work: work(tx)) as transaction:
            self.assertEqual(rewards.claim_fairy(99, 10, 1)["clothes"], clothes)
            transaction.assert_called_once()
            self.assertIn("reward_claims", tx.insert.call_args.args[0])
            self.assertIn("INSERT IGNORE INTO user_clothes", tx.execute.call_args.args[0])
            self.assertEqual(tx.insert.call_args.args[1]["cid"], tx.execute.call_args.args[1]["cid"])

    def test_duplicate_diary_claim_does_not_grant_again(self):
        tx = Mock()
        tx.query.return_value = [{"claimed_at": "2026-11-23 10:00:00"}]
        with patch.object(rewards, "sync_diary_claims"), patch.object(rewards.db, "run_in_transaction", side_effect=lambda work: work(tx)):
            with self.assertRaises(rewards.AlreadyClaimed):
                rewards.claim_diary(99, "2026-11-23")
            tx.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
