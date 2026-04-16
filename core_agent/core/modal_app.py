"""
Strike Tips - Modal Application
Simplified for Modal free tier deployment
"""
import modal
import json
import os
from datetime import datetime, date
import pytz

# Helper to get local date
def get_sa_date():
    sa_tz = pytz.timezone('Africa/Johannesburg')
    return datetime.now(sa_tz).date()

@app.function(
    image=image,
    secrets=secrets + [ai_secrets],
    schedule=modal.Cron("0 11 * * *"),  # Daily at 11 AM SAST
    timeout=300,  # 5 minute timeout
)
def daily_racing_scan():
    """
    Daily racing scan - runs automatically at 11 AM SAST
    """
    print(f"[RACE] Strike Tips Daily Scan - {datetime.now()}")
    
    today = get_sa_date()
    
    try:
        # Get today's tracks
        tracks = get_todays_tracks()
        print(f"[LOC] Today's tracks: {tracks}")
        
        all_results = {}
        total_bets = 0
        
        for track in tracks:
            try:
                result = analyze_track(track)
                all_results[track] = result
                total_bets += len(result.get("value_bets", []))
            except Exception as e:
                print(f"[ERR] Error analyzing {track}: {e}")
                all_results[track] = {"error": str(e)}
        
        # Send summary
        send_telegram_summary(all_results, total_bets)
        
        return {
            "date": today.isoformat(),
            "tracks": len(tracks),
            "value_bets": total_bets,
            "results": all_results
        }
        
    except Exception as e:
        error_msg = f"Daily scan failed: {str(e)}"
        print(f"[ERR] {error_msg}")
        send_telegram_message(f"[WARN] <b>Strike Tips Error</b>\n\n{error_msg}")
        raise

@app.function(image=image, secrets=secrets)
def send_telegram_summary(results: Dict, total_bets: int):
    """Send daily summary to Telegram"""
    today = get_sa_date()
    message = f"""
[RACE] <b>STRIKE TIPS - Daily Tips</b>
[DATE] {today.strftime('%A, %d %B %Y')}

[STATS] <b>Summary</b>
Total Value Bets: {total_bets}
"""
    
    for track, data in results.items():
        if "error" in data:
            message += f"\n[ERR] {track.title()}: Error"
        else:
            bets = len(data.get("value_bets", []))
            message += f"\n[LOC] {track.title()}: {bets} value bet(s)"
    
    # Send top 3 value bets
    all_bets = []
    for track, data in results.items():
        if "value_bets" in data:
            all_bets.extend(data["value_bets"])
    
    all_bets.sort(key=lambda x: x.get("edge", 0), reverse=True)
    
    if all_bets:
        message += "\n\n🔥 <b>Top Value Bets:</b>"
        for i, bet in enumerate(all_bets[:3], 1):
            message += f"""
{i}. {bet['horse']}
   [LOC] {bet['track']} R{bet['race_number']}
   💰 Edge: +{bet['edge']}% | Est: {bet['estimated_prob']}%
"""
    
    send_telegram_message(message)


@app.function(image=image, secrets=secrets)
def send_telegram_message(text: str):
    """Send message to Telegram"""
    import httpx
    
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    response = httpx.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })
    
    response.raise_for_status()
    return response.json()


def get_todays_tracks() -> List[str]:
    """Get tracks racing today"""
    from datetime import datetime
    
    tracks_by_day = {
        "Monday": ["fairview"],
        "Tuesday": ["vaal"],
        "Wednesday": ["kenilworth"],
        "Thursday": ["vaal", "flamingo"],
        "Friday": ["greyville", "fairview"],
        "Saturday": ["turffontein", "kenilworth", "flamingo"],
        "Sunday": ["greyville"]
    }
    
    today = datetime.now().strftime("%A")
    return tracks_by_day.get(today, [])


# Manual trigger endpoint
@app.function(image=image, secrets=secrets + [ai_secrets])
@modal.web_endpoint(method="POST")
def manual_scan(request: Dict):
    """Manual scan endpoint - call via HTTP POST"""
    try:
        result = daily_racing_scan.remote()
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Health check endpoint
@app.function(image=image)
@modal.web_endpoint(method="GET")
def health():
    """Health check"""
    return {
        "status": "ok",
        "service": "Strike Tips",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    # Local testing
    print("Testing Strike Tips on Modal...")
    # with app.run():
    #     result = daily_racing_scan.remote()
    #     print(json.dumps(result, indent=2))
