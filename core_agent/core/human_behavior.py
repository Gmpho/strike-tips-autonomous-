import random
import asyncio
import math
import logging
from typing import Tuple, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("HumanBehavior")


@dataclass
class MousePosition:
    """Represents a point on the screen."""

    x: int
    y: int


class HumanBehaviorSimulator:
    """
    Tier-2 Invisibility: Human behavior simulation.
    Ported from User's Gold Standard Project.
    """

    VIEWPORTS = [(1920, 1080), (1366, 768), (1440, 900), (1280, 720), (2560, 1440)]
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    ]

    def __init__(self):
        self.current_pos = MousePosition(0, 0)
        self.actions = 0

    async def random_delay(self, min_ms: int = 1000, max_ms: int = 3000):
        """Thinking time: simulating a human reading the screen."""
        delay = (
            random.triangular(min_ms, max_ms, min_ms + (max_ms - min_ms) * 0.3) / 1000
        )
        await asyncio.sleep(delay)
        self.actions += 1

    def _generate_bezier_path(
        self, start: MousePosition, end: MousePosition, steps: int = 20
    ) -> List[MousePosition]:
        """Generate human-like wobbly curve between two points."""
        mid_x = (start.x + end.x) / 2 + random.randint(-100, 100)
        mid_y = (start.y + end.y) / 2 + random.randint(-100, 100)
        path = []
        for i in range(steps + 1):
            t = i / steps
            x = (1 - t) ** 2 * start.x + 2 * (1 - t) * t * mid_x + t**2 * end.x
            y = (1 - t) ** 2 * start.y + 2 * (1 - t) * t * mid_y + t**2 * end.y
            path.append(
                MousePosition(
                    int(x + random.randint(-2, 2)), int(y + random.randint(-2, 2))
                )
            )
        return path

    async def move_mouse_naturally(self, page, x: int, y: int):
        """Move mouse in a curved path like a real hand."""
        target = MousePosition(x, y)
        path = self._generate_bezier_path(
            self.current_pos, target, steps=random.randint(15, 30)
        )
        for point in path:
            await page.mouse.move(point.x, point.y)
            await asyncio.sleep(random.uniform(0.005, 0.02))  # Fast but jittered
        self.current_pos = target
        self.actions += 1

    async def scroll_naturally(self, page, direction: str = "down", amount: int = None):
        """Simulation of reading: scrolling in chunks with pauses."""
        if amount is None:
            amount = random.randint(200, 600)
        delta = amount if direction == "down" else -amount

        steps = random.randint(4, 9)
        for _ in range(steps):
            await page.mouse.wheel(0, delta / steps)
            await asyncio.sleep(random.uniform(0.05, 0.2))

        await self.random_delay(500, 1500)
        self.actions += 1

    async def type_naturally(self, page, selector: str, text: str):
        """Imperfect typing simulation with pauses."""
        await page.click(selector)
        for char in text:
            await page.keyboard.type(char)
            delay = random.uniform(0.05, 0.2)
            if char == " ":
                delay *= 2
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.4, 0.9))
            else:
                await asyncio.sleep(delay)
        self.actions += 1

    def get_random_viewport(self):
        return random.choice(self.VIEWPORTS)

    def get_random_user_agent(self):
        return random.choice(self.USER_AGENTS)
