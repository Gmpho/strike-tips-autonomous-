
import asyncio
from skills.parsers.duckduckgo import DuckDuckGoRacingParser

async def test_grounded_search():
    parser = DuckDuckGoRacingParser()
    
    print("\n--- Test 1: Horse Form Deep Search ---")
    print("Querying for: Splittheeights (Turffontein runner)")
    report1 = await parser.find_horse_form("Splittheeights")
    print("\n[RESULT 1]:\n", report1)
    
    print("\n--- Test 2: Today's Racecard Target ---")
    print("Querying for: Turffontein today's racecard")
    report2 = await parser.get_todays_races("Turffontein")
    print("\n[RESULT 2]:\n")
    for r in report2:
        print(f"- {r.get('title')}: {r.get('url')}")
    
    print("\n--- Test 3: Future Meets (South Africa) ---")
    print("Querying for: South Africa horse racing future fixtures schedule 2026")
    report3 = await parser.search("South Africa horse racing future fixtures schedule 2026", max_results=3)
    print("\n[RESULT 3]:\n")
    for r in report3:
        print(f"- {r.get('title')}: {r.get('url')}")
        
    print("\n--- Test 4: Jockey Information Deep Search ---")
    print("Querying for: Richard Fourie jockey stats South Africa")
    report4 = await parser.search("Richard Fourie horse racing jockey stats winner South Africa", max_results=3)
    print("\n[RESULT 4]:\n")
    for r in report4:
        print(f"- {r.get('title')}: {r.get('url')}")
        snippet = r.get('snippet', '')
        print(f"  Snippet preview: {snippet[:150]}...\n")

    print("\n--- Test 5: International Track (UK) ---")
    print("Querying for: Cheltenham today's racecard UK")
    report5 = await parser.get_todays_races("Cheltenham", country="UK")
    print("\n[RESULT 5]:\n")
    for r in report5:
        print(f"- {r.get('title')}: {r.get('url')}")
        
    print("\n--- Test 6: International Race Verification (UAE) ---")
    print("Querying for: Meydan race 1 UAE 2026-03-14")
    report6 = await parser.verify_race_event("Meydan", 1, date_str="2026-03-14", country="UAE")
    print("\n[RESULT 6]:\n", report6)

if __name__ == "__main__":
    asyncio.run(test_grounded_search()) 