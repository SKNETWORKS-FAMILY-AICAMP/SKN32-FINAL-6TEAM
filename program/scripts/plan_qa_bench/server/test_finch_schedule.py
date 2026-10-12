"""학습률 식·경계·optimizer 적용을 CPU에서 확인한다. 모델 정확도 시험은 별도다."""
import math
import unittest
from finch_schedule import LossAdaptiveRate


class RateTests(unittest.TestCase):
    def test_loss_average_and_rate(self):
        schedule = LossAdaptiveRate(4)
        rate = schedule.update(1)
        self.assertAlmostEqual(schedule.ema, 3.7)
        self.assertAlmostEqual(rate, 2e-5 / math.sqrt(3.7 + 1e-12))
        self.assertEqual(schedule.updates, 1)

    def test_cap_when_loss_zero(self):
        self.assertEqual(LossAdaptiveRate(0).update(0), 5e-5)

    def test_invalid_settings(self):
        for kw in [{'initial_loss': -1}, {'initial_loss': float('nan')},
                   {'initial_loss': 1, 'cap': 0}, {'initial_loss': 1, 'alpha': 1}]:
            with self.assertRaises(ValueError):
                LossAdaptiveRate(**kw)

    def test_nonfinite_batch_preserves_state(self):
        schedule = LossAdaptiveRate(1)
        for value in [float('nan'), float('inf'), -1]:
            with self.assertRaises(ValueError):
                schedule.update(value)
        self.assertEqual(schedule.ema, 1)
        self.assertEqual(schedule.updates, 0)

    def test_all_optimizer_groups_are_updated(self):
        class Optimizer:
            param_groups = [{'lr': 0.1}, {'lr': 0.2}]
        optimizer = Optimizer()
        rate = LossAdaptiveRate(1).apply_before_step(optimizer, 1)
        self.assertEqual([g['lr'] for g in optimizer.param_groups], [rate, rate])


if __name__ == '__main__':
    unittest.main()
