"""One-shot probe: news source mix + published coverage."""
import json
import urllib.request

with urllib.request.urlopen(
    "https://strike-tips-hud.pages.dev/api/news", timeout=20
) as r:
    d = json.load(r)
items = d.get("items", [])
print("total:", len(items))
srcs = {}
for i in items:
    srcs[i.get("source")] = srcs.get(i.get("source"), 0) + 1
print(srcs)
print("missing published:",
      sum(1 for i in items if not i.get("published")), "/", len(items))
for i in items[:6]:
    print(repr(str(i.get("published"))[:40]), "|", str(i.get("source")),
          "|", str(i.get("title"))[:60])
