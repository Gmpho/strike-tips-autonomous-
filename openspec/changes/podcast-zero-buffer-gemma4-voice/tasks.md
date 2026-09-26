## Phase 1: Podcast Zero-Buffer Lookahead Pre-Fetching

- [x] 1.1 In `SwarmPodcastView.tsx`, implement proactive background audio pre-fetching (`prefetchLineAudio`) for lines $N+1$ and $N+2$ with in-flight deduplication.
- [x] 1.2 Wire playback transitions so that when line $N$ finishes, line $N+1$ begins playback with 0ms buffering gap.
- [x] 1.3 Pre-fetch the first 2 lines immediately upon episode generation/loading.

## Phase 2: Groq & Gemma 4 Multi-Engine Podcast Scripting

- [x] 2.1 Update `strike-tips-hud/server/podcast-service.ts` to add "Gemma AI" to the Swarm Roster (`voice: 'Fenrir'`, `role: 'Exotic Permutations & Scenario Reasoning'`).
- [x] 2.2 Support `engine: 'gemini' | 'groq' | 'gemma4'` in `generatePodcastScript`, routing to Groq LPUs or Google AI Studio Gemma 4.
- [x] 2.3 Add script generation engine selector in `SwarmPodcastView.tsx` UI.

## Phase 3: Hands-Free Auto-Voice Chat with Gemma 4

- [x] 3.1 In `strike-tips-hud/src/components/AIChat.tsx`, add an `Auto-Voice` toggle button with audio icon indicator.
- [x] 3.2 Trigger natural speech playback automatically when streaming completes if `autoSpeak` is active.
- [x] 3.3 Verify build compilation and test end-to-end flow across all components.
