## 1. Perimeter

- [x] 1.1 `security.py`: `/v1/*` + `/ws/chat` keyed (header/Bearer/query), fail-closed, SAFE intact
- [x] 1.2 Pages api Function: caller key on write families + 20/min writes cap
- [x] 1.3 Pages v1 Function: 30/min/IP cap on LLM path

## 2. Brute force + waste

- [x] 2.1 PIN 5-fails/30-min volume-shared lockout + wire into `/auth`
- [x] 2.2 Chroma `$and` freshness gate

## 3. Verify + record

- [x] 3.1 6 new security tests green; full suite 216 green
- [x] 3.2 Live probes: anon /v1 401, anon write 401, reads 200, keyed chat 200 PONG
- [x] 3.3 Modal + Pages deployed; local docker needs `compose restart` (bind mount)
- [ ] 3.4 Cloudflare WAF rules — blocked on custom domain (owner task, later)
