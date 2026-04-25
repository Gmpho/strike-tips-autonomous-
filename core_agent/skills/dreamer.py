import random
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Dream:
    id: str
    timestamp: str
    scenario: str
    probability_shift: float
    insight: str
    vividness: float # 0.0 to 1.0

class DreamEngine:
    SCENARIOS = [
        "What if Kenilworth was Heavy ground today?",
        "Simulating Turffontein with a 20km/h headwind on the straight.",
        "Refactoring probability edge for low-liquidity Maiden Plates.",
        "Synthesizing 1000 races at Greyville under night lights.",
        "Evaluating the 'Jockey Factor' if Richard Fourie switched mounts.",
        "Calculating the ripple effect of a late scratch in Race 7.",
        "Dreaming of a perfect ROI sequence at Scottsville.",
        "Neural re-training on historical 'Rank Outsider' wins.",
    ]
    
    INSIGHTS = [
        "Detected 3.2% edge variance in soft conditions.",
        "Wind factor outweighs distance in 400m sprint simulations.",
        "Market sentiment is lagging behind trainer strike rate.",
        "Potential value lock identified in early morning odds drift.",
        "Systemic bias toward favorites discovered in night races.",
        "Half-Kelly fraction shows stability in extreme volatility tests.",
    ]

    def __init__(self):
        self.history: List[Dream] = []

    def generate_dream(self) -> Dream:
        dream = Dream(
            id=f"dream-{random.randint(1000, 9999)}",
            timestamp=datetime.now().strftime("%H:%M:%S"),
            scenario=random.choice(self.SCENARIOS),
            probability_shift=round(random.uniform(-0.15, 0.15), 3),
            insight=random.choice(self.INSIGHTS),
            vividness=round(random.uniform(0.4, 0.95), 2)
        )
        self.history.insert(0, dream)
        if len(self.history) > 20:
            self.history.pop()
        return dream

    def get_recent_dreams(self) -> List[Dream]:
        if not self.history:
            # Seed with some initial dreams
            for _ in range(5):
                self.generate_dream()
        return self.history

dream_engine = DreamEngine()
