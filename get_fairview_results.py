
import asyncio
import json
import sys
import os
from datetime import datetime

# Add strike-tips to path
sys.path.insert(0, os.path.join(os.getcwd(), "strike-tips"))

from skills.parsers.tab4racing import TAB4RacingScraper

async def get_results():
    scraper = TAB4RacingScraper()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🔍 Fetching results for Fairview on {today}...")
    
    try:
        races = await scraper.scrape_racecard("fairview", today)
        if not races:
            print("❌ No races found for Fairview today.")
            return

        results_summary = []
        for race in races:
            winners = [r.number for r in race.runners if r.result_position == 1]
            seconds = [r.number for r in race.runners if r.result_position == 2]
            thirds = [r.number for r in race.runners if r.result_position == 3]
            
            results_summary.append({
                "race": race.race_number,
                "time": race.race_time,
                "status": race.race_status,
                "winners": winners,
                "seconds": seconds,
                "thirds": thirds
            })
            
        print("\n🏁 FAIRVIEW RESULTS:")
        for res in results_summary:
            winner_str = f"Winner: {res['winners'][0]}" if res['winners'] else "No result yet"
            print(f"Race {res['race']} ({res['time']}): {res['status']} | {winner_str}")
            if res['seconds']: print(f"  2nd: {res['seconds'][0]}")
            if res['thirds']: print(f"  3rd: {res['thirds'][0]}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(get_results())
