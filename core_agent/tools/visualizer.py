import logging
import io
from typing import List, Dict, Optional

logger = logging.getLogger("visualizer")

try:
    import cairosvg
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False
    logger.warning("cairosvg not installed — chart PNG conversion unavailable")


class PerformanceVisualizer:
    """Generates performance charts as PNG bytes using SVG + cairosvg"""

    WIDTH = 800
    HEIGHT = 450
    MARGIN = {"top": 60, "right": 30, "bottom": 70, "left": 70}

    @staticmethod
    def _chart_area() -> tuple[int, int, int, int]:
        m = PerformanceVisualizer.MARGIN
        w = PerformanceVisualizer.WIDTH
        h = PerformanceVisualizer.HEIGHT
        return m["left"], m["top"], w - m["left"] - m["right"], h - m["top"] - m["bottom"]

    @staticmethod
    def _build_svg(dates: List[str], pnl: List[float], gains: List[float]) -> str:
        x0, y0, cw, ch = PerformanceVisualizer._chart_area()

        if not dates:
            return "<svg/>"

        min_val = min(min(pnl), min(gains), 0)
        max_val = max(max(pnl), max(gains), 0.01)
        val_range = max_val - min_val or 1

        def x_pos(i: int) -> float:
            return x0 + (i / max(len(dates) - 1, 1)) * cw

        def y_pos(v: float) -> float:
            return y0 + ch - ((v - min_val) / val_range) * ch

        lines = []
        lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{PerformanceVisualizer.WIDTH}" height="{PerformanceVisualizer.HEIGHT}" viewBox="0 0 {PerformanceVisualizer.WIDTH} {PerformanceVisualizer.HEIGHT}">')
        lines.append(f'<rect width="{PerformanceVisualizer.WIDTH}" height="{PerformanceVisualizer.HEIGHT}" fill="#121212"/>')

        lines.append(f'<text x="{PerformanceVisualizer.WIDTH / 2}" y="30" text-anchor="middle" fill="#FFFFFF" font-family="sans-serif" font-size="18" font-weight="bold">Strike Tips — Performance ROI</text>')

        for i in range(5):
            frac = i / 4
            y = y0 + ch * frac
            lines.append(f'<line x1="{x0}" y1="{y}" x2="{x0 + cw}" y2="{y}" stroke="#222222" stroke-width="1"/>')
            val = max_val - frac * val_range
            lines.append(f'<text x="{x0 - 8}" y="{y + 4}" text-anchor="end" fill="#AAAAAA" font-family="sans-serif" font-size="11">R{val:+.0f}</text>')

        n = len(dates)
        step = max(1, n // 7)
        for i in range(0, n, step):
            x = x_pos(i)
            lines.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y0 + ch}" stroke="#222222" stroke-width="1"/>')
            label = dates[i][-5:] if len(dates[i]) > 5 else dates[i]
            lines.append(f'<text x="{x}" y="{y0 + ch + 18}" text-anchor="end" fill="#AAAAAA" font-family="sans-serif" font-size="11" transform="rotate(-30, {x}, {y0 + ch + 18})">{label}</text>')

        points = " ".join(f"{x_pos(i)},{y_pos(v)}" for i, v in enumerate(pnl))
        lines.append(f'<polygon points="{x0},{y0 + ch} {points} {x_pos(len(pnl) - 1)},{y0 + ch}" fill="rgba(59,130,246,0.2)"/>')
        lines.append(f'<polyline points="{points}" fill="none" stroke="#3B82F6" stroke-width="2.5"/>')

        bw = max(6, cw // len(gains) * 0.5)
        for i, v in enumerate(gains):
            x = x_pos(i)
            bar_h = (v / val_range) * ch
            if v >= 0:
                lines.append(f'<rect x="{x - bw / 2}" y="{y0 + ch - bar_h}" width="{bw}" height="{bar_h}" fill="#10B981" rx="2"/>')
            else:
                lines.append(f'<rect x="{x - bw / 2}" y="{y0 + ch}" width="{bw}" height="{-bar_h}" fill="#EF4444" rx="2"/>')

        ly = PerformanceVisualizer.HEIGHT - 25
        lines.append(f'<line x1="{x0}" y1="{ly}" x2="{x0 + 20}" y2="{ly}" stroke="#3B82F6" stroke-width="2.5"/>')
        lines.append(f'<text x="{x0 + 28}" y="{ly + 4}" fill="#CCCCCC" font-family="sans-serif" font-size="12">Cumulative P&amp;L</text>')
        lines.append(f'<rect x="{x0 + 170}" y="{ly - 6}" width="12" height="12" fill="#10B981" rx="2"/>')
        lines.append(f'<text x="{x0 + 190}" y="{ly + 4}" fill="#CCCCCC" font-family="sans-serif" font-size="12">Daily Gain</text>')

        lines.append("</svg>")
        return "\n".join(lines)

    @staticmethod
    async def generate_bankroll_chart(history: List[Dict]) -> Optional[bytes]:
        if not history:
            return None

        if not HAS_CAIRO:
            logger.error("cairosvg not installed — cannot render chart")
            return None

        dates = [h.get("date", "?") for h in history]
        pnl = [h.get("pnl", 0) for h in history]
        gains = [h.get("daily_gain", 0) for h in history]

        try:
            svg = PerformanceVisualizer._build_svg(dates, pnl, gains)
            png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"), scale=2)
            return png_bytes
        except Exception as e:
            logger.error(f"Chart rendering failed: {e}")
            return None
