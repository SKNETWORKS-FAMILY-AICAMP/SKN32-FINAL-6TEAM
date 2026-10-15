"""FINCH식 손실 EMA 학습률. 저자 코드를 복사하지 않고 공개 수식을 구현한다.

근거: https://arxiv.org/html/2605.20005v1 §3.3.
우리 판에서는 optimizer 갱신 하나를 accumulation batch 하나로 정의한다.
"""
import math


class LossAdaptiveRate:
    def __init__(self, initial_loss, base_rate=2e-5, cap=5e-5,
                 alpha=0.9, epsilon=1e-12):
        for name, value in [('initial_loss', initial_loss), ('base_rate', base_rate),
                            ('cap', cap), ('epsilon', epsilon)]:
            if not math.isfinite(value) or value < 0 or (name != 'initial_loss' and value == 0):
                raise ValueError(f'{name}: 유한한 양수 필요(초기 손실은 0 허용)')
        if not math.isfinite(alpha) or not 0 <= alpha < 1:
            raise ValueError('alpha: 0 이상 1 미만 필요')
        self.ema = float(initial_loss)
        self.base_rate, self.cap = base_rate, cap
        self.alpha, self.epsilon = alpha, epsilon
        self.updates = 0

    def update(self, batch_loss):
        if not math.isfinite(batch_loss) or batch_loss < 0:
            raise ValueError('batch_loss: 유한한 0 이상 필요')
        self.ema = self.alpha * self.ema + (1 - self.alpha) * batch_loss
        self.updates += 1
        return min(self.base_rate / math.sqrt(self.ema + self.epsilon), self.cap)

    def apply_before_step(self, optimizer, batch_loss):
        rate = self.update(batch_loss)
        for group in optimizer.param_groups:
            group['lr'] = rate
        return rate
