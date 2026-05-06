import asyncio
import json
import os
import sys

# Add project root to sys.path
sys.path.append("/home/giftmpho/Kimi_Agent_Strike Tips Racing Bot")

from core_agent.skills.parsers.betway_api import BetwayAPI

async def test_betway_snapshot():
    print("🚀 Initializing BetwayAPI...")
    api = BetwayAPI()
    
    print("📡 Fetching snapshot data...")
    try:
        snapshot = await api.get_snapshot_format()
        
        print(f"✅ Received snapshot with {len(snapshot.get('events', {}))} events.")
        
        # Save for inspection
        output_path = "/home/giftmpho/Kimi_Agent_Strike Tips Racing Bot/data/test_snapshot_debug.json"
        with open(output_path, "w") as f:
            json.dump(snapshot, f, indent=2)
        print(f"💾 Snapshot saved to {output_path}")
        
        # Verify first runner in first event
        if snapshot["events"]:
            eid = next(iter(snapshot["events"]))
            event = snapshot["events"][eid]
            print(f"\n🔍 Inspecting Event: {event.get('en')}")
            
            runners = event.get("runners", [])
            if runners:
                r = runners[0]
                print(f"🏇 Horse: {r.get('outcomeName')}")
                print(f"👤 Jockey: {r.get('jockeyName')}")
                print(f"👔 Trainer: {r.get('trainerName')}")
                print(f"⭐ Star Rating: {r.get('starRating')}")
                print(f"📅 Age: {r.get('age')}")
                print(f"⚖️ Weight: {r.get('weight')}")
                print(f"📝 Form: {r.get('form')}")
                print(f"🔢 Number: {r.get('number')}")
            else:
                print("⚠️ No runners found in this event.")
        else:
            print("⚠️ No events found.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_betway_snapshot())
