"""
MAF ContextProvider that injects ChromaDB RAG results before each agent run.
Replaces the manual grounding block in ModelPipeline.chat().
"""

from typing import Any
from agent_framework import BaseContextProvider as ContextProvider

_RACING_KEYWORDS = {
    "race",
    "track",
    "form",
    "odds",
    "runner",
    "horse",
    "jockey",
    "trainer",
    "turffontein",
    "vaal",
    "greyville",
    "scottsville",
    "kenilworth",
    "fairview",
    "durbanville",
    "flamingo",
}


class ChromaContextProvider(ContextProvider):
    source_id = "chroma_memory"

    def __init__(self, memory):
        super().__init__(self.source_id)
        self._memory = memory

    async def before_run(
        self, *, agent: Any, session: Any, context: Any, state: dict
    ) -> None:
        # Extract user message text
        msg = ""
        for m in getattr(context, "input_messages", []):
            text = getattr(m, "text", "") or ""
            if isinstance(text, str):
                msg += text.lower() + " "

        # Only activate for racing-related messages
        if not any(kw in msg for kw in _RACING_KEYWORDS):
            return

        try:
            results = self._memory.search_form_insights(msg.strip(), n_results=3)
            if results:
                snippets = "\n".join(r.get("content", "") for r in results)
                context.extend_instructions(
                    self.source_id,
                    f"## Relevant Past Race Data\n{snippets}",
                )
        except Exception:
            pass  # Memory unavailable — degrade gracefully
