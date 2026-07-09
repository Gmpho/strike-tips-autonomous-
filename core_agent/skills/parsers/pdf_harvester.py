import logging
import os
import re
import json
import httpx
import io
import fitz
from datetime import date
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from core_agent.skills.parsers.pdf_discovery import PDFDiscoveryService

logger = logging.getLogger("pdf-harvester")


class PDFHarvester:
    CDN_BASE = "https://aztabstorage.blob.core.windows.net/tabonline-blob/FieldsPDF"

    INTELLIGENCE_URLS = {
        "Computaform SA": f"{CDN_BASE}/ComputaformSA/{{track}}@{{date}}.pdf",
        "Daily Tips": f"{CDN_BASE}/Tips/TIPPINGSHEET@{{date}}.pdf",
    }

    SPONSORED_TRACKS = {
        "greyville": "HOLLYWOODBETS GREYVILLE",
    }

    def __init__(self, cache_dir: Optional[str] = None, memory=None):
        self.cache_dir = cache_dir or os.path.join("data", "pdf_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.memory = memory

    def _get_track_code(self, track: str) -> str:
        lowered = track.lower()
        if lowered in self.SPONSORED_TRACKS:
            return self.SPONSORED_TRACKS[lowered]
        return track.upper()

    async def get_latest_racing_intelligence(
        self,
        track: str,
        intelligence_type: str = "Computaform SA",
        specific_date: Optional[str] = None,
        precomputed_url: Optional[str] = None,
    ) -> Dict:
        today = specific_date or date.today().isoformat()
        cache_key = f"{track}_{intelligence_type}_{today}".replace(" ", "_").lower()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            with open(cache_file) as f:
                return {**json.load(f), "cached": True}

        # Check ChromaDB before hitting Azure
        memory_result = await self._check_memory_cache(track, today, intelligence_type)
        if memory_result:
            with open(cache_file, "w") as f:
                json.dump(memory_result, f, indent=2)
            memory_result["cached"] = True
            return memory_result

        url = precomputed_url
        if not url:
            url_template = self.INTELLIGENCE_URLS.get(intelligence_type, "")
            formatted_date = today.replace("-", ".")
            url = url_template.format(
                track=self._get_track_code(track), date=formatted_date
            )

        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=15)
        try:
            response = await client.get(url, allow_redirects=True)

            if response.status_code == 404:
                logger.info(
                    f"[PDF] 404 for {url}. Discovering dynamic URL for {track}..."
                )
                discovered_url = await PDFDiscoveryService.get_live_pdf_url(track, today)
                if discovered_url:
                    logger.info(f"[PDF] Discovery successful: {discovered_url}")
                    response = await client.get(
                        discovered_url, allow_redirects=True
                    )

            if response.status_code == 200:
                return await self._parse_pdf_bytes(
                    response.content, track, today, intelligence_type, cache_file
                )
        except Exception as e:
            logger.error(f"Download failed for {track}: {e}")

        return self._stub_intelligence(track, today)

    async def _parse_pdf_bytes(
        self,
        pdf_bytes: bytes,
        track: str,
        today: str,
        intelligence_type: str,
        cache_file: str,
    ) -> Dict:
        if pdf_bytes.strip().lower().startswith(b"<!"):
            return self._stub_intelligence(track, today)

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            num_pages = len(doc)
            raw_text = "\n".join(page.get_text() or "" for page in doc)
            doc.close()
        except Exception as e:
            logger.error(f"Failed to parse PDF for {track}: {e}")
            return self._stub_intelligence(track, today)

        runners = []
        current_race = None
        in_horse_table = False
        race_header_count = 0
        table_count = 0
        races = {}

        current_horse = None
        awaiting = "IDLE"

        lines = raw_text.split("\n")
        for i, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line and awaiting != "COMMENT":
                continue

            race_match = re.search(r"RACE\s+(\d+)\s*@", line, re.IGNORECASE)
            if race_match:
                current_race = int(race_match.group(1))
                race_header_count += 1
                in_horse_table = False
                continue

            if line.startswith("HORSE") and "NET WGT" in line:
                in_horse_table = True
                table_count += 1
                continue

            if "COMPUTAFORM RATINGS" in line or "SPEED RATINGS" in line:
                in_horse_table = False
                if current_horse and current_horse.get("name"):
                    runners.append(current_horse)
                current_horse = None
                awaiting = "IDLE"
                continue

            inline_race = re.match(r"^(\d+)$", line)
            if inline_race and not in_horse_table:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.match(r"\d+:\d+\s*-\s*R\d", next_line):
                        rn = int(inline_race.group(1))
                        current_race = rn
                        race_header_count += 1
                        if rn not in races:
                            races[rn] = {}
                        detail_line = next_line
                        j = i + 2
                        while j < len(lines):
                            nxt = lines[j].strip()
                            if not nxt:
                                j += 1
                                continue
                            if re.match(r"\d+:\d+\s*-\s*R\d", nxt):
                                break
                            if "NO-" in nxt or "COMPUTAFORM" in nxt or "SPEED" in nxt:
                                break
                            if re.search(r"\d+m\s+\w+$", nxt):
                                detail_line += " " + nxt
                                break
                            detail_line += " " + nxt
                            j += 1
                        det = re.match(
                            r"(\d+:\d+)\s*-\s*(R[\d ,]+)\s+(.+?)\s+(\d+m)\s+(\w+)",
                            detail_line,
                        )
                        if det:
                            clean_name = re.sub(
                                r"\s*FOR HOSPITALITY BOOKINGS?\s+CALL\s+[\d\s]+\s*",
                                " ",
                                det.group(3).strip(),
                            ).strip()
                            races[rn].update(
                                {
                                    "time": det.group(1),
                                    "prize": det.group(2),
                                    "race_name": clean_name,
                                    "distance_m": int(
                                        re.sub(r"[^\d]", "", det.group(4))
                                    ),
                                    "surface": det.group(5),
                                }
                            )
                        st = lines[i + 2].strip() if i + 2 < len(lines) else ""
                        if "Same Trainer" in st:
                            races[rn]["same_trainer"] = st
                        elif re.search(
                            r"(BIPOT|PICK6|JACKPOT|PA|SWINGER)\s+LEG", st
                        ):
                            races[rn]["leg_info"] = st
                        continue

            if not in_horse_table:
                continue

            horse_start = re.match(r"^(\d+)\s*-\s*(\d+)\s*(.*)", line)
            if horse_start:
                if current_horse and current_horse.get("name"):
                    runners.append(current_horse)

                current_horse = {
                    "race_number": current_race,
                    "horse_number": int(horse_start.group(1)),
                    "draw": int(horse_start.group(2)),
                }
                rest = horse_start.group(3).strip()
                if rest:
                    nm = re.match(
                        r"([A-Z][A-Z\s\'’\-\.\(\)/]+)\s+(\d+\.?\d*)\s*$", rest
                    )
                    if nm and len(nm.group(1).strip()) > 2:
                        current_horse["name"] = nm.group(1).strip()
                        current_horse["weight_kg"] = float(nm.group(2))
                        awaiting = "FORM"
                    else:
                        awaiting = "NAME"
                else:
                    awaiting = "NAME"
                continue

            if awaiting == "NAME" and current_horse and "name" not in current_horse:
                nm = re.match(r"([A-Z][A-Z\s\'’\-\.\(\)/]+)\s+(\d+\.?\d*)\s*$", line)
                if nm and len(nm.group(1).strip()) > 2:
                    current_horse["name"] = nm.group(1).strip()
                    current_horse["weight_kg"] = float(nm.group(2))
                    awaiting = "FORM"
                else:
                    awaiting = "IDLE"
                continue

            if awaiting == "FORM":
                current_horse["form_flag"] = ""
                if line.startswith("XX"):
                    current_horse["form_flag"] = "XX"
                elif line.startswith("X") and (len(line) == 1 or line[1] in ' \t'):
                    current_horse["form_flag"] = "X"
                rest = re.sub(r"^X{0,2}\s*", "", line).strip()
                if rest:
                    current_horse["comment"] = rest
                    current_horse["has_won"] = current_horse["form_flag"] in ("X", "XX")
                    awaiting = "ODDS"
                else:
                    awaiting = "COMMENT"
                continue

            if awaiting == "COMMENT":
                current_horse["comment"] = line if line else ""
                current_horse["has_won"] = current_horse.get("form_flag", "") in ("X", "XX")
                awaiting = "ODDS"
                continue

            if awaiting == "ODDS":
                om = re.match(r"^(\d+)/(\d+)", line)
                if om:
                    num, den = int(om.group(1)), int(om.group(2))
                    current_horse["odds"] = om.group(0)
                    current_horse["odds_decimal"] = round((num / den) + 1, 2) if den > 0 else None
                runners.append(current_horse)
                current_horse = None
                awaiting = "IDLE"
                continue

        # Parse expanded "No L3 Name R-1-2-3" section for trainer/jockey/ratings
        self._parse_expanded_section(raw_text, runners)

        self_check = {
            "pages": num_pages,
            "races_found": race_header_count,
            "tables_detected": table_count,
            "runners_parsed": len(runners),
            "parser_ok": (len(runners) > 0 or table_count == 0),
        }

        if table_count > 0 and len(runners) == 0:
            logger.warning(
                f"SELF-CHECK FAILED: {table_count} tables but 0 runners "
                f"({num_pages} pages, {race_header_count} races)"
            )
        elif race_header_count > 0 and table_count == 0:
            logger.warning(
                f"SELF-CHECK: {race_header_count} races but no horse tables "
                f"({num_pages} pages)"
            )
        elif len(runners) > 0:
            logger.info(
                f"PDF OK: {num_pages}pgs, {race_header_count}R, "
                f"{table_count}T, {len(runners)} runners"
            )
        else:
            logger.info(
                f"PDF: {num_pages}pgs, no race data (off-day or non-standard PDF)"
            )

        result = {
            "source": intelligence_type,
            "track": track,
            "date": today,
            "runners": runners,
            "races": races,
            "parsed_tips": [
                {"race_number": r["race_number"], "selections": r["name"]}
                for r in runners
            ],
            "raw_text": raw_text,
            "cached": False,
            "self_check": self_check,
        }
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)

        if self.memory and hasattr(self.memory, "store_pdf_racecard"):
            self.memory.store_pdf_racecard(result)

        return result

    async def _check_memory_cache(
        self, track: str, today: str, intelligence_type: str
    ) -> Optional[Dict]:
        """Reconstruct PDF result from ChromaDB if previously stored."""
        if not self.memory or not hasattr(self.memory, "get_pdf_racecards"):
            return None
        try:
            rows = self.memory.get_pdf_racecards(track=track, date=today)
            if not rows:
                return None

            runners, races, parsed_by_race = [], {}, {}

            for row in rows:
                m = row["metadata"]
                runner = {
                    "race_number": m["race_number"],
                    "horse_number": m["horse_number"],
                    "draw": m["draw"],
                    "name": m["horse_name"],
                    "form_flag": m["form_flag"],
                    "has_won": m["has_won"],
                    "weight_kg": m["weight_kg"],
                    "odds_decimal": m["odds_decimal"],
                    "comment": m["comment"],
                    "trainer": m.get("trainer", ""),
                    "jockey": m.get("jockey", ""),
                    "trainer_win_pct": m.get("trainer_win_pct", 0),
                    "jockey_win_pct": m.get("jockey_win_pct", 0),
                    "hmr": m.get("hmr", 0),
                    "cmr": m.get("cmr", 0),
                    "forecast_odds_decimal": m.get("forecast_odds_decimal", 0),
                    "career_runs": m.get("career_runs", 0),
                    "career_wins": m.get("career_wins", 0),
                    "career_places": m.get("career_places", 0),
                }
                rn = m["race_number"]
                runners.append(runner)
                if rn not in parsed_by_race:
                    parsed_by_race[rn] = []
                parsed_by_race[rn].append(runner["name"])
                if rn not in races:
                    races[rn] = {
                        "distance_m": m.get("distance_m", 0),
                        "surface": m.get("surface", ""),
                    }

            logger.info(
                f"[PDF] Memory cache hit: {track} {today} ({len(runners)} runners)"
            )
            return {
                "source": intelligence_type,
                "track": track,
                "date": today,
                "runners": runners,
                "races": races,
                "parsed_tips": [
                    {"race_number": rn, "selections": names[0] if len(names) == 1 else ", ".join(names)}
                    for rn, names in parsed_by_race.items()
                ],
                "raw_text": "",
                "cached": True,
            }
        except Exception as e:
            logger.warning(f"[PDF] Memory cache check failed: {e}")
            return None

    # ─── Expanded Section Parser ────────────────────────────────────────────

    _EXPANDED_HEADER = re.compile(r'No\s+L3\s+Name\s+R-1-2-3')

    @staticmethod
    def _clean_pct(val: str) -> float:
        """Clean a percentage value with PDF encoding artifacts (e.g. 14→3% -> 14.3)."""
        val = val.rstrip('%')
        if not val:
            return 0.0
        val = val.replace('\uFFFD', '.').replace('\ufffd', '.')
        try:
            return float(val)
        except ValueError:
            return 0.0

    def _parse_expanded_section(self, raw_text: str, runners: List[Dict]) -> int:
        """Parse the expanded 'No L3 Name R-1-2-3' sections from Computaform PDF.

        These appear after each race's horse table and contain trainer/jockey
        names with win%, HMR/CMR ratings, career stats, and forecast odds.

        Cross-references by horse name to attach fields to the runner dicts.
        Returns count of runners enriched.
        """
        if not runners:
            return 0

        lines = raw_text.split("\n")
        in_expanded = False
        enriched = 0

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            if self._EXPANDED_HEADER.search(line):
                in_expanded = True
                continue

            if not in_expanded:
                continue

            if "FAST FORM" in line or "CFORM RATINGS" in line:
                in_expanded = False
                continue

            if "COMPUTAFORM RATINGS" in line or "SPEED RATINGS" in line:
                in_expanded = False
                continue

            if "Crse Record" in line or re.match(r'^\d{5}$', line):
                continue

            if self._parse_expanded_row(line, runners):
                enriched += 1

        if enriched:
            logger.info(f"[PDF] Expanded section enriched {enriched} runners")
        return enriched

    def _parse_expanded_row(self, line: str, runners: List[Dict]) -> bool:
        """Parse a single expanded-section row by matching horse name."""
        # Normalize apostrophes to handle PDF encoding differences
        n_line = line.replace('\u2019', "'").replace('\u2018', "'")
        for runner in runners:
            name = runner.get("name", "")
            if not name:
                continue
            n_name = name.replace('\u2019', "'").replace('\u2018', "'")
            if n_name not in n_line:
                continue

            name_idx = n_line.index(n_name)
            right = n_line[name_idx + len(n_name):].strip()
            if not right:
                continue

            rt = right.split()
            if len(rt) < 8:
                continue

            idx = 0

            # R-1-2-3 may be concatenated with F3% (e.g. "2-0-1-1100%")
            r_match = re.match(r'(\d+)-(\d+)-(\d+)-(\d+?)(\d*%)?$', rt[idx])
            if not r_match:
                continue

            runner["career_runs"] = int(r_match.group(1))
            runner["career_wins"] = int(r_match.group(2))
            runner["career_seconds"] = int(r_match.group(3))
            runner["career_thirds"] = int(r_match.group(4))
            runner["career_places"] = (
                runner["career_wins"] + runner["career_seconds"] + runner["career_thirds"]
            )

            if r_match.group(5):
                # F3% was attached to R-1-2-3
                runner["f3_pct"] = int(r_match.group(5).rstrip('%'))
                idx = 1
            else:
                # F3% is a separate token
                idx = 1
                try:
                    runner["f3_pct"] = int(rt[idx].rstrip('%'))
                except ValueError:
                    runner["f3_pct"] = 0
                idx = 2

            # Earnings + Ave Earn
            runner["pdf_earnings"] = rt[idx]
            runner["pdf_ave_earnings"] = rt[idx + 1]
            idx += 2

            # ACs (age/sex/something)
            runner["pdf_acs"] = rt[idx]
            idx += 1

            # Weight
            try:
                runner["pdf_weight_kg"] = float(rt[idx])
            except ValueError:
                pass
            idx += 1

            # Draw
            try:
                runner["pdf_draw"] = int(rt[idx])
            except ValueError:
                pass
            idx += 1

            # Remaining: trainer name+win% + jockey name+win% + HMR CMR + comment + Fcst
            remaining = rt[idx:]
            pct_indices = [i for i, t in enumerate(remaining) if t.endswith('%')]

            if len(pct_indices) >= 2:
                # Trainer name = tokens before first %
                trainer_tokens = remaining[:pct_indices[0]]
                runner["trainer"] = " ".join(trainer_tokens)
                runner["trainer_win_pct"] = self._clean_pct(remaining[pct_indices[0]])

                # Jockey name = tokens between first % and second %
                jockey_start = pct_indices[0] + 1
                jockey_tokens = remaining[jockey_start:pct_indices[1]]
                runner["jockey"] = " ".join(jockey_tokens)
                runner["jockey_win_pct"] = self._clean_pct(remaining[pct_indices[1]])

                # Post jockey: HMR CMR (comment...) Fcst
                post = remaining[pct_indices[1] + 1:]
                if len(post) >= 3:
                    hmr_val = post[0]
                    cmr_val = post[1]
                    runner["hmr"] = int(hmr_val) if hmr_val != '--' else 0
                    runner["cmr"] = int(cmr_val) if cmr_val != '--' else 0

                    fcst_str = post[-1]
                    fcst_m = re.match(r'(\d+)-(\d+)', fcst_str)
                    if fcst_m:
                        num, den = int(fcst_m.group(1)), int(fcst_m.group(2))
                        runner["forecast_odds_raw"] = fcst_str
                        runner["forecast_odds_decimal"] = (
                            round((num / den) + 1, 2) if den > 0 else 0
                        )

                    if len(post) > 3:
                        pdf_comment = " ".join(post[2:-1])
                        if pdf_comment and pdf_comment not in ('--', ''):
                            runner["pdf_comment"] = pdf_comment
                elif len(post) == 2:
                    runner["hmr"] = int(post[0]) if post[0] != '--' else 0
                    runner["cmr"] = int(post[1]) if post[1] != '--' else 0

            elif len(pct_indices) == 1:
                # Only trainer win% — jockey data might be in a different format
                trainer_tokens = remaining[:pct_indices[0]]
                runner["trainer"] = " ".join(trainer_tokens)
                runner["trainer_win_pct"] = self._clean_pct(remaining[pct_indices[0]])

            return True

        return False

    def _stub_intelligence(self, track: str, today: str) -> Dict:
        return {
            "source": "stub",
            "track": track,
            "date": today,
            "parsed_tips": [],
            "raw_text": "",
            "cached": False,
        }
