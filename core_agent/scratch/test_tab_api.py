import httpx
import asyncio
import json

async def test_tab_api():
    url = 'https://totex-vasx.4racing.com/PRODUCTS/webservice/phumelelaV4/get/GamePlayRequest/horseracing/4RACINGWEB_TAB'
    params = {'msisdn': '0000', 'game': 'horseracing', 'selectionType': '0'}
    
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # Save a sample to check structure
            with open("core_agent/scratch/tab_api_sample.json", "w") as f:
                json.dump(data, f, indent=2)
            
            programs = data.get('data', {}).get('option_list', {})
            print(f"Found {len(programs)} programs")
            
            for k, v in list(programs.items())[:2]:
                print(f"Program: {v.get('ProgramName')} ({v.get('ProgramCode')})")
                races = v.get('RaceList', [])
                print(f"  Races: {len(races)}")
                if races:
                    first_race = races[0]
                    print(f"  First Race Sample: {json.dumps(first_race, indent=2)[:500]}...")

if __name__ == "__main__":
    asyncio.run(test_tab_api())
