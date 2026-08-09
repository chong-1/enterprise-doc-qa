"""LLM 调用令牌桶限速器（asyncio 版，无外部依赖）。

令牌桶 vs 信号量的区别：
- Semaphore：限制"同时在途"数量（管拥挤度）
- TokenBucket：限制"每秒发送"速率（管发射速率）
两者语义不同，叠加使用——请求先等令牌（限速率），再过信号量（限在途）。
"""

import asyncio
import time


class TokenBucket:
    """令牌桶：限制平均速率 + 允许突发。

    每个请求 acquire() 拿走一个令牌；桶里没令牌则计算还需等待多久并 sleep。
    令牌按 rate 每秒补充，最多积累 capacity 个（突发上限）。
    长期平均速率 ≤ rate，瞬时突发 ≤ capacity。
    """

    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate          # 每秒补充令牌数（请求/秒）
        self.capacity = capacity  # 桶容量（最大突发请求数）
        self._tokens = capacity
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """获取一个令牌（没有就等待）。"""
        while True:
            async with self._lock:
                now = time.monotonic()
                # 按流逝时间补充令牌（补满为止）
                self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # 还需等待 (1 - tokens) 个令牌的补充时间
                wait = (1.0 - self._tokens) / self.rate
            await asyncio.sleep(wait)
