"""
MAF Workflow for the daily race scan pipeline.
ScrapeExecutor → AnalyseExecutor → BankrollExecutor → NotifyExecutor
"""

import logging
from typing import Any
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

logger = logging.getLogger("strike-workflow")


class ScrapeExecutor(Executor):
    def __init__(self, strike):
        super().__init__(id="scrape")
        self._strike = strike

    @handler
    async def scrape(self, tracks: list[str], ctx: WorkflowContext[list]) -> None:
        races = []
        try:
            # 1. Fetch all races from Betway (Primary source)
            all_betway_races = await self._strike.betway.get_races()
            
            # 2. Filter for the requested tracks
            for track in tracks:
                matched = [r for r in all_betway_races if track.lower() in r.track.lower()]
                if matched:
                    races.extend(matched)
                else:
                    logger.info(f"[SCRAPE] No Betway data for {track}")
        except Exception as e:
            logger.warning(f"[SCRAPE] Betway fetch failed: {e}")
            
        await ctx.send_message(races)


class AnalyseExecutor(Executor):
    def __init__(self, analyst_agent):
        super().__init__(id="analyse")
        self._agent = analyst_agent

    @handler
    async def analyse(self, races: list, ctx: WorkflowContext[list]) -> None:
        results = []
        for race in races:
            try:
                session = self._agent.create_session()
                result = await self._agent.run(
                    f"Analyse race {race.get('race_number', '?')} at {race.get('track', '?')}",
                    session=session,
                )
                results.append(
                    {
                        "race": race,
                        "analysis": (
                            result.text if hasattr(result, "text") else str(result)
                        ),
                    }
                )
            except Exception as e:
                logger.warning(f"[ANALYSE] Race failed: {e}")
        await ctx.send_message(results)


class BankrollExecutor(Executor):
    def __init__(self, bankroll_agent):
        super().__init__(id="bankroll")
        self._agent = bankroll_agent

    @handler
    async def govern(self, analyses: list, ctx: WorkflowContext[list]) -> None:
        decisions = []
        for item in analyses:
            try:
                session = self._agent.create_session()
                result = await self._agent.run(
                    f"Evaluate this analysis for a selection: {item['analysis']}",
                    session=session,
                )
                decisions.append(
                    {
                        "race": item["race"],
                        "analysis": item["analysis"],
                        "decision": (
                            result.text if hasattr(result, "text") else str(result)
                        ),
                    }
                )
            except Exception as e:
                logger.warning(f"[BANKROLL] Decision failed: {e}")
        await ctx.send_message(decisions)


class NotifyExecutor(Executor):
    def __init__(self, strike):
        super().__init__(id="notify")
        self._strike = strike

    @handler
    async def notify(self, decisions: list, ctx: WorkflowContext[None, list]) -> None:
        outputs = []
        for item in decisions:
            decision_text = item.get("decision", "")
            if "RECORD" in decision_text.upper() and self._strike.telegram:
                try:
                    await self._strike.telegram.send_message(
                        f"🏇 Strike Tips Value Alert\n{decision_text}"
                    )
                except Exception as e:
                    logger.warning(f"[NOTIFY] Telegram failed: {e}")
            outputs.append(item)
        await ctx.yield_output(outputs)


def build_race_scan_workflow(strike, agents: dict):
    """
    Build the MAF Workflow for the daily race scan.
    agents dict must have keys: 'analyst', 'bankroll'
    """
    scrape = ScrapeExecutor(strike)
    analyse = AnalyseExecutor(agents["analyst"])
    bankroll = BankrollExecutor(agents["bankroll"])
    notify = NotifyExecutor(strike)

    return (
        WorkflowBuilder(start_executor=scrape)
        .add_edge(scrape, analyse)
        .add_edge(analyse, bankroll)
        .add_edge(bankroll, notify)
        .build()
    )
