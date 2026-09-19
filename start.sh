#!/bin/sh
# Pre-warm the default Ollama model in background.
# The model comes from env so it can never drift from the documented set
# (OLLAMA_LOCAL_FAST / MODEL_FAST_LOCAL in .env); the fallback matches the
# fast-local model recorded in openspec/project.md.
python3 -c "
import urllib.request, json, threading, time, os
def warm():
    time.sleep(3)
    model = os.environ.get('OLLAMA_LOCAL_FAST') or os.environ.get('MODEL_FAST_LOCAL') or 'racing_llama'
    try:
        req = urllib.request.Request('http://ollama:11434/api/generate',
            data=json.dumps({'model':model,'prompt':'ping','stream':False,'options':{'num_predict':1}}).encode(),
            headers={'Content-Type':'application/json'})
        urllib.request.urlopen(req, timeout=600)
    except:
        pass
threading.Thread(target=warm, daemon=True).start()
" &

# Start uvicorn
exec uvicorn core_agent.api_pkg:app --host 0.0.0.0 --port 8000
