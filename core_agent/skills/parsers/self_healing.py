"""
Self-Healing Parser
Adaptive HTML parser that tracks selector success rates and falls back
gracefully when the racing site changes its structure.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("self-healing-parser")


class SelfHealingParser:
    """
    Adaptive selector engine that tracks which CSS selectors work
    and automatically promotes or demotes them based on success rate.

    Usage:
        parser = SelfHealingParser()
        element = parser.find_element(soup, "horse_name")
    """

    DEFAULT_SELECTORS: Dict[str, List[str]] = {
        "horse_name": [
            ".horse-name",
            "[class*='horse'] [class*='name']",
            ".runner-name",
            "td.name",
            "[data-horse-name]",
            "td:first-child a",
        ],
        "odds": [
            ".odds-value",
            "[class*='odds'] span",
            "[class*='price']",
            ".decimal-odds",
            "td.odds",
        ],
        "race_time": [
            ".race-time",
            "[class*='race-time']",
            ".start-time",
            "[data-start-time]",
        ],
        "jockey": [
            ".jockey-name",
            "[class*='jockey']",
            "td.jockey",
        ],
        "trainer": [
            ".trainer-name",
            "[class*='trainer']",
            "td.trainer",
        ],
        "form": [
            ".form-string",
            "[class*='form']",
            "td.form",
        ],
    }

    def __init__(self, config_file: Optional[str] = None):
        self._config_file = config_file or os.path.join("data", "parser_config.json")
        self._selector_stats: Dict[str, Dict[str, Dict]] = {}  # field → selector → {hits, misses}
        self._load_config()

    def _load_config(self):
        """Load persisted selector stats"""
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file) as f:
                    self._selector_stats = json.load(f)
            except Exception:
                self._selector_stats = {}

    def _save_config(self):
        """Persist selector stats"""
        try:
            os.makedirs(os.path.dirname(self._config_file) or ".", exist_ok=True)
            with open(self._config_file, "w") as f:
                json.dump(self._selector_stats, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not save parser config: {e}")

    def _get_success_rate(self, field: str, selector: str) -> float:
        stats = self._selector_stats.get(field, {}).get(selector, {"hits": 0, "misses": 0})
        total = stats["hits"] + stats["misses"]
        return stats["hits"] / total if total > 0 else 0.5  # default 50% for new selectors

    def _record_result(self, field: str, selector: str, success: bool):
        if field not in self._selector_stats:
            self._selector_stats[field] = {}
        if selector not in self._selector_stats[field]:
            self._selector_stats[field][selector] = {"hits": 0, "misses": 0}
        if success:
            self._selector_stats[field][selector]["hits"] += 1
        else:
            self._selector_stats[field][selector]["misses"] += 1

    def _ranked_selectors(self, field: str) -> List[str]:
        """Return selectors sorted by success rate (best first)"""
        selectors = self.DEFAULT_SELECTORS.get(field, [])
        return sorted(
            selectors,
            key=lambda s: self._get_success_rate(field, s),
            reverse=True,
        )

    def find_element(self, soup: Any, field: str) -> Optional[Any]:
        """
        Find an HTML element using ranked selectors.
        Records success/failure for each selector tried.
        """
        for selector in self._ranked_selectors(field):
            try:
                el = soup.select_one(selector)
                if el:
                    self._record_result(field, selector, True)
                    return el
                else:
                    self._record_result(field, selector, False)
            except Exception:
                self._record_result(field, selector, False)

        # All selectors failed
        logger.warning(f"[HEALING] All selectors failed for field '{field}'")
        self._save_config()
        return None

    def find_all_elements(self, soup: Any, field: str) -> List[Any]:
        """Find all matching elements using ranked selectors"""
        for selector in self._ranked_selectors(field):
            try:
                elements = soup.select(selector)
                if elements:
                    self._record_result(field, selector, True)
                    return elements
                else:
                    self._record_result(field, selector, False)
            except Exception:
                self._record_result(field, selector, False)

        self._save_config()
        return []

    def get_selector_report(self) -> Dict:
        """Return a report of selector success rates"""
        report = {}
        for field, selectors in self._selector_stats.items():
            report[field] = {}
            for selector, stats in selectors.items():
                total = stats["hits"] + stats["misses"]
                report[field][selector] = {
                    "success_rate": f"{(stats['hits'] / total * 100):.1f}%" if total > 0 else "N/A",
                    "hits": stats["hits"],
                    "misses": stats["misses"],
                }
        return report
