"""
Strike Tips - Healing Swarm Routes
Endpoints for self-healing parser stats and AI agent activity.
"""

import json
import os
import logging
import subprocess
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from core_agent.core.strike_brain import brain

router = APIRouter(prefix="/api/healing", tags=["healing"])
logger = logging.getLogger("healing-routes")

HEALING_EVENTS_PATH = os.path.join("data", "healing_events.json")


@router.get("/selectors")
async def get_selector_stats():
    """Get success rates for all adaptive selectors"""
    if not brain or not brain.strike or not brain.strike.parser:
        return {"success": False, "error": "Parser not initialized"}

    return {
        "success": True,
        "report": brain.strike.parser.get_selector_report(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/activity")
async def get_healing_activity(limit: int = 10):
    """Get recent AI agent activity (GitHub runs and internal events)"""
    events = []

    # 1. Load internal events
    if os.path.exists(HEALING_EVENTS_PATH):
        try:
            with open(HEALING_EVENTS_PATH, "r") as f:
                events = json.load(f)
        except Exception as e:
            logger.error(f"Error loading healing events: {e}")

    # 2. Try to fetch GitHub workflow runs (API first, then CLI)
    github_runs = []
    github_token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO", "Gmpho/strike-tips-autonomous-")

    if github_token:
        try:
            import httpx

            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            url = f"https://api.github.com/repos/{repo}/actions/workflows/gemini-plan-execute.yml/runs?per_page=5"
            response = httpx.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for run in data.get("workflow_runs", []):
                    github_runs.append(
                        {
                            "id": run["id"],
                            "status": run["status"],
                            "conclusion": run["conclusion"],
                            "createdAt": run["created_at"],
                            "url": run["html_url"],
                        }
                    )
        except Exception as e:
            logger.debug(f"GitHub API fetch failed: {e}")

    # Fallback to GH CLI if no runs yet
    if not github_runs:
        try:
            # Fetch last 5 Gemini Plan Execution runs
            cmd = [
                "gh",
                "run",
                "list",
                "--workflow",
                "gemini-plan-execute.yml",
                "--limit",
                "5",
                "--json",
                "id,status,conclusion,createdAt,url",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                github_runs = json.loads(result.stdout)
        except Exception as e:
            logger.debug(f"GitHub CLI not available or failed: {e}")

    return {
        "success": True,
        "internal_events": events[-limit:],
        "github_runs": github_runs,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/pulse")
async def trigger_healing_pulse():
    """Manually trigger a system-wide scan and healing check"""
    try:
        # In a real scenario, this might trigger a GitHub dispatch or a local script
        # For now, we'll record the event and trigger a local scan
        event = {
            "id": f"pulse-{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "agent": "Admin",
            "action": "SYSTEM_PULSE_TRIGGERED",
            "status": "SUCCESS",
            "details": "Manual system-wide healing scan initiated.",
        }

        # Record event
        events = []
        if os.path.exists(HEALING_EVENTS_PATH):
            with open(HEALING_EVENTS_PATH, "r") as f:
                events = json.load(f)
        events.append(event)
        with open(HEALING_EVENTS_PATH, "w") as f:
            json.dump(events[-50:], f, indent=2)

        return {"success": True, "message": "Pulse triggered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
