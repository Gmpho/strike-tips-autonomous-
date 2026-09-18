#!/bin/sh
# Pre-warm default Ollama model in background
python3 -c "
import urllib.request, json, threading, time
def warm():
    time.sleep(3)
    try:
        req = urllib.request.Request('http://ollama:11434/api/generate',
            data=json.dumps({'model':'qwen3.5:0.8b','prompt':'ping','stream':False,'options':{'num_predict':1}}).encode(),
            headers={'Content-Type':'application/json'})
        urllib.request.urlopen(req, timeout=600)
    except:
        pass
threading.Thread(target=warm, daemon=True).start()
" &

# Start uvicorn
exec uvicorn core_agent.api_pkg:app --host 0.0.0.0 --port 8000
