Now I have real performance data:

LCP: 771 ms — well under the 2.5s threshold (excellent!)
TTFB: 38 ms — phenomenal (Vercel edge)
CLS: 0.00 — perfect

This is a fast site! But there are issues:
1. WebGL errors — Three.js is crashing on context creation, and it retries many times (10+ attempts!)
2. Form fields without id/name attributes (2 of them)
3. Telegram Web App integration

Let me check the detailed insights to see if there's anything worth optimizing.
Your site is fast. Let me get the detailed breakdown.
⚙chrome-devtools_performance_analyze_insight [insightSetId=NAVIGATION_0, insightName=LCPBreakdown]
⚙chrome-devtools_performance_analyze_insight [insightSetId=NAVIGATION_0, insightName=ThirdParties]
⚙chrome-devtools_performance_analyze_insight [insightSetId=NAVIGATION_0, insightName=DOMSize]
⚙chrome-devtools_performance_analyze_insight [insightSetId=NAVIGATION_0, insightName=RenderBlocking]
⚙chrome-devtools_performance_analyze_insight [insightSetId=NAVIGATION_0, insightName=NetworkDependencyTree]
⚙chrome-devtools_performance_analyze_insight [insightSetId=NAVIGATION_0, insightName=ForcedReflow]
Thought: 722ms
Let me look at the page content more carefully to see what the site actually is and what the form fields issue is about.
Let me check the page structure and see exactly what it does.
⚙chrome-devtools_evaluate_script [function=() => {
  return {
    title: document.title,
    textContent: document.body.innerText.substring(0, 2000),
    links: Array.from(document.querySelectorAll('a')).map(a => ({ href: a.href, text: a.textContent.trim().substring(0, 50) })),
    formFields: Array.from(document.querySelectorAll('input, textarea, select')).map(el => ({ tag: el.tagName, type: el.type, id: el.id, name: el.name, placeholder: el.placeholder })),
    images: Array.from(document.querySelectorAll('img')).map(img => ({ src: img.src, alt: img.alt, width: img.width, height: img.height })),
  };
}]
Thought: 3.8s
Now I have a comprehensive picture. Let me summarize the findings for the user:

Performance: Excellent ✅
- LCP: 771ms (well under 2.5s target)
- TTFB: 38ms (Vercel edge is fast)
- CLS: 0.00 (perfect)
- Only 13 network requests
- No DOM size issues

Issues found:
1. WebGL errors — Three.js failing to create context (this is the headless test environment, but retrying 10+ times is worth addressing)
2. Telegram.org script — 408ms on main thread. It's the Telegram Web App SDK (needed for the mini app)
3. Render blocking CSS — Single CSS file (index-Cv1SUC8b.css) is render-blocking, 231ms total. Could be inlined for marginal gain
4. Unused preconnect — The modal.run preconnect appears to not be used during page load
5. Form field missing id/name — Search input has no id or name attribute
6. Critical request chain — Main JS bundle (index-DRwfV4Bo.js) is 951ms in the critical path

This site is in great shape performance-wise. Let me write a concise report.
Your site is already fast. Here's the verdict:
Strike Tips HUD — Performance Report
Core Web Vitals ✅
Metric	Your Site	Target	Status
LCP	771 ms	≤2,500 ms	✅ Great
TTFB	38 ms	≤800 ms	✅ Amazing (Vercel edge)
CLS	0.00	≤0.1	✅ Perfect
Requests	13 total	—	✅ Lean
DOM	Clean	—	✅ No issues
Your site is 5x faster than Oriflame on LCP. Nothing to worry about there.
Minor issues (worth fixing)
Issue	Detail
🔶 Telegram SDK	telegram.org takes 408ms on main thread. Fine for a Telegram Mini App but could be lazy-loaded
🔶 WebGL crash loop	Three.js tries to create a WebGL context 10+ times and keeps failing. On real devices this could cause battery drain or jank. Add a retry limit or a fallback
🔶 Unused preconnect	gmpho--strike-tips-racing-serve-api.modal.run is preconnected but never requested during page load
🔶 Search input	No id or name attribute on the search field — minor a11y/form issue
🔶 JS bundle in critical path	index-DRwfV4Bo.js takes 951ms to load + parse. Defer non-critical parts if possible
What it's built with
- React + Three.js + Framer Motion
- Vite / rolldown bundler
- Telegram Mini App (WebView)
- Backend: Modal (Python API on *.modal.run)
- Ollama integration for local AI
Want me to write a full report file like the Oriflame one, or jump into fixing any of these?





------------------------------------
------------------------------------








# Strike Tips HUD — Performance Audit Report

**Date:** 13 June 2026
**URL:** https://strike-tips-hud.vercel.app/
**Tooling:** Chrome DevTools (Performance Trace + Lighthouse)

---

## Executive Summary

Strike Tips HUD performs exceptionally well. The Largest Contentful Paint (LCP) clocks in at **771ms** — well under Google's 2.5s recommended threshold. Time to First Byte (38ms) is excellent thanks to Vercel's edge network, and Cumulative Layout Shift is a perfect **0.00**.

The site is a **Telegram Mini App** built with **React**, **Three.js**, and **Framer Motion**, served via Vite/rolldown on Vercel. Only **13 network requests** are made on initial page load — a lean profile compared to most modern web apps.

There are no critical performance issues, but a handful of optimisations would polish the experience for users on slower devices.

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| LCP | 771 ms | ≤2,500 ms | ✅ Pass |
| TTFB | 38 ms | ≤800 ms | ✅ Pass |
| CLS | 0.00 | ≤0.1 | ✅ Pass |
| Total requests | 13 | — | ✅ Low |
| Render-blocking requests | 1 (CSS) | 0 | ⚠️ Minor |
| Third-party main thread | 408 ms | — | ⚠️ Minor |

---

## 1. LCP Breakdown

The LCP element is a `<p>` tag (text node) — no image or font needed.

| Phase | Duration | % of LCP |
|-------|----------|----------|
| Time to First Byte (TTFB) | 38 ms | 4.9% |
| Element render delay | 734 ms | 95.1% |

The 734ms render delay is entirely JavaScript parsing and execution — the React app booting up, Three.js initialising, and Telegram SDK loading. For a single-page React app with 3D rendering, this is a healthy render time.

**No improvement needed here.** 771ms LCP is comfortably in the green zone.

---

## 2. Third-Party Script Impact

Only one third-party domain makes a meaningful contribution:

| Provider | Transfer Size | Main Thread Time | Purpose |
|----------|--------------|-----------------|---------|
| **telegram.org** | — | **408 ms** | Telegram Web App SDK |

The Telegram SDK is required for the Mini App to function (handles theme, viewport, safe areas, and communication with the Telegram client). It cannot be fully removed, but its load timing can be optimised.

No other third-party scripts (no analytics pixels, no trackers, no ad SDKs) were detected. This is excellent.

---

## 3. JavaScript & Bundle Analysis

### Bundle breakdown

| File | Size | Purpose |
|------|------|---------|
| `index-DRwfV4Bo.js` | Largest | App entry point + all pages/routes |
| `rolldown-runtime-COnpUsM8.js` | Small | Bundler runtime |
| `vendor-react-Bx6Q7Odu.js` | Medium | React + React DOM |
| `vendor-three-zAGZN1IH.js` | Medium | Three.js 3D engine |
| `vendor-framer-ji3UGrSH.js` | Medium | Framer Motion animations |
| `vendor-icons-Dqe8e5yH.js` | Small | Icon library |

### Critical request chain

- HTML (139ms)
  - `index-DRwfV4Bo.js` **(951ms)** — longest critical path item
  - `index-Cv1SUC8b.css` (329ms, render-blocking)

The main JS bundle is the bottleneck (951ms total from request to processing). Code-splitting by route would reduce this, though given the app is a single-page Telegram Mini App with 3D visualisations, the current size is reasonable.

### Recommendation: Route-based code splitting

The app has distinct sections (Dashboard, AI Agents, Bankroll, Analytics, Logs, Settings). If these are loaded as separate chunks via dynamic `import()`, the initial bundle could be significantly smaller, improving LCP by ~200-300ms.

---

## 4. WebGL Error — Three.js Context Failure

The console shows repeated WebGL context creation failures:

```
THREE.WebGLRenderer: A WebGL context could not be created.
Reason: Could not create a WebGL context...
```

Three.js attempted to create a context **10+ times** before giving up, each attempt throwing an uncaught promise rejection.

### Impact

- In this headless test environment the errors are expected (no GPU), but:
  - **On low-end mobile devices** this pattern can cause noticeable jank, battery drain, and UI freezes
  - **10+ retries** with no backoff or cap floods the console and wastes CPU cycles

### Recommended fix

Add a **retry limit with exponential backoff** to the Three.js initialisation:

```
Max retries: 3
Backoff: 500ms → 1s → 2s
On final failure: render a fallback UI (static overlay) instead of crashing silently
```

The uncaught promise rejections should also be caught with a `.catch()` handler.

---

## 5. Render-Blocking Resources

Only one resource blocks the initial render:

| Resource | Duration | Type |
|----------|----------|------|
| `index-Cv1SUC8b.css` | 231ms | CSS |

### Recommendation

Since this is a small stylesheet, consider **inlining critical CSS** into the `<head>` of the HTML document and loading the full stylesheet asynchronously. This would eliminate the render-blocking request entirely, saving ~230ms on the first paint.

---

## 6. Preconnect Analysis

| Origin | Status |
|--------|--------|
| `https://telegram.org/` | ✅ Used (handshake warm-up) |
| `https://gmpho--strike-tips-racing-serve-api.modal.run/` | ⚠️ **Unused** |

The preconnect to the Modal API backend (`gmpho--strike-tips-racing-serve-api.modal.run`) is set up but the page makes no request to this origin during load. This is likely used later when the user interacts (e.g., AI Agents or analytics), but preconnecting for it at page load wastes a connection slot.

### Recommendation

Remove the `preconnect` for the Modal API and add it dynamically when the user navigates to a feature that requires it. Alternatively, switch to `dns-prefetch` instead, which has zero connection cost.

---

## 7. DOM & Rendering

| Metric | Value |
|--------|-------|
| Total DOM elements | Healthy |
| DOM depth | Normal |
| Layout thrashing | 98ms unattributed forced reflows |

A small amount of forced reflow was detected (~98ms), likely from Three.js or Framer Motion measuring DOM geometry during animations. This is negligible at current levels but worth monitoring as the app grows.

---

## 8. Accessibility

### Form field without id/name

- A search input (`<input type="text" placeholder="Search Intelligence...">`) is missing both `id` and `name` attributes.
- This fails WCAG 4.1.2 (Name, Role, Value) and means screen readers and browser autofill cannot properly identify the field.

**Fix:** Add `id="search"` and `name="search"` attributes, and consider adding a `<label>` element or `aria-label="Search"`.

---

## 9. API Health

| Endpoint | Status | Purpose |
|----------|--------|---------|
| `/v1/health` | 200 ✅ | Health check |
| `/api/agent/models` | 200 ✅ | Available AI models |

Both API endpoints respond correctly with no latency issues detected.

---

## 10. Recommendations (Priority Order)

### 🟡 P2 — High Impact

| # | Action | Expected Gain |
|---|--------|--------------|
| 1 | **Limit WebGL retries to 3 with backoff** — Add retry cap and exponential backoff. Catch promise rejections. Fall back to a static UI if WebGL cannot be created. | Prevent jank on low-end devices |
| 2 | **Fix uncaught promise rejections** — Wrap Three.js initialisation in a try/catch or `.catch()`. | Clean error handling |

### 🟢 P3 — Medium Impact

| # | Action | Expected Gain |
|---|--------|--------------|
| 3 | **Remove unused preconnect** to `modal.run` or downgrade to `dns-prefetch`. | ~50ms connection slot saved |
| 4 | **Add `id`/`name` to search input** + `aria-label` for accessibility. | WCAG compliance |
| 5 | **Inline critical CSS** and load `index-Cv1SUC8b.css` asynchronously. | ~200ms faster first paint |

### 🔵 P4 — Nice to Have

| # | Action | Expected Gain |
|---|--------|--------------|
| 6 | **Route-based code splitting** — Dynamic import for AI Agents, Analytics, Bankroll, Logs, Settings. | ~200-300ms LCP improvement |
| 7 | **Lazy-load Telegram SDK** — If Telegram APIs aren't needed immediately at boot, defer with `async`. | ~200ms off main thread at startup |

---

## Appendix: Network Resource Summary

```
Total requests          13
HTML                    1 (200)
JavaScript              6 (vendor chunks + entry)
CSS                     1
Images                  2 (logo.webp, logo-128.png, favicon.svg)
API calls               2 (health, agent/models)
Third-party scripts     1 (telegram.org)
Third-party domains     1 (telegram.org)
```

### All requests (sorted)

| # | URL | Status | Type |
|---|-----|--------|------|
| 1 | `/` | 200 | HTML |
| 2 | `/assets/index-DRwfV4Bo.js` | 200 | JS |
| 3 | `/assets/rolldown-runtime-COnpUsM8.js` | 200 | JS |
| 4 | `/assets/vendor-framer-ji3UGrSH.js` | 200 | JS |
| 5 | `/assets/vendor-react-Bx6Q7Odu.js` | 200 | JS |
| 6 | `/assets/vendor-three-zAGZN1IH.js` | 200 | JS |
| 7 | `/assets/vendor-icons-Dqe8e5yH.js` | 200 | JS |
| 8 | `/assets/index-Cv1SUC8b.css` | 200 | CSS |
| 9 | `/logo.webp` | 200 | Image |
| 10 | `/api/agent/models` | 200 | API |
| 11 | `/v1/health` | 200 | API |
| 12 | `/favicon.svg` | 200 | SVG |
| 13 | `https://telegram.org/js/telegram-web-app.js` | 200 | JS |

---

## Final Verdict

**Strike Tips HUD is in excellent shape.** With an LCP of 771ms and zero layout shift, it outperforms the vast majority of web applications. The main areas for improvement are defensive coding around Three.js (retry logic, error handling) and minor accessibility polish — not speed.

Compared to the previous audit (Oriflame at 3,959ms LCP with 127 requests), this site is approximately **5x faster** and **10x leaner** on network requests. Your client has nothing to worry about.

---

*Report generated via automated performance analysis. Testing environment: headless Chrome, no throttling (lab conditions). Field data on real mobile devices running inside Telegram's WebView may differ slightly.*
