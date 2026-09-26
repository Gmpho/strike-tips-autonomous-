# Change: Zero-Buffer Swarm Podcast, Groq & Gemma 4 Scripting, and Hands-Free Chat Voice

## Why

1. **Podcast Playback Buffering**: The Swarm Podcast currently requests synthesized speech on demand only after the previous speaker finishes, creating an awkward 2-4 second silence between every turn. Punters need a seamless, broadcast-quality radio experience with gapless playback.
2. **Groq & Gemma 4 Podcast Generation**: Currently the podcast generator only supports Gemini. Users want Groq (Qwen 3.8 / Llama 70B for sub-second generation) and Google AI Studio Gemma 4 (deep exotic reasoning and track storylines leveraging the 1,500 daily free tier) with Gemma added to the agent roster.
3. **Hands-Free Conversational Voice for Gemma 4**: Punters trackside or driving need an "Auto-Voice" mode in chat where Gemma 4 reads out its verdict automatically upon completion, completing a true voice-in, voice-out assistant loop.

## What Changes

### 1. Podcast Lookahead Audio Pre-Fetching (`SwarmPodcastView.tsx`)
- Implement a background lookahead pre-fetch queue for the dialogue lines.
- As soon as Line N starts playing, Line N+1 and Line N+2 are fetched in parallel into `audioCacheRef`.
- Hook `onended` to transition with 0ms delay to the pre-cached audio buffer.

### 2. Groq & Gemma 4 Podcast Engines (`podcast-service.ts` & `SwarmPodcastView.tsx`)
- Add engine selection (`gemini` | `groq` | `gemma4`) in `GeneratePodcastRequest`.
- Support Groq (`qwen/qwen3.8-27b` / `llama-3.3-70b`) for $<1$s instant script generation.
- Support Google AI Studio Gemma 4 (`gemma-2-27b-it` / `gemma-4-31b-it`) for exotic permutations and scenario reasoning.
- Add "Gemma AI" (Voice: Fenrir, Role: Exotic Permutations & Scenario Reasoning) to `SWARM_ROSTER`.
- Add an engine selector dropdown in `SwarmPodcastView.tsx`.

### 3. Hands-Free Auto-Voice Chat Mode (`AIChat.tsx`)
- Add an `Auto-Voice` (`autoSpeak`) toggle in the chat controls.
- When enabled, as soon as model generation finishes streaming, automatically synthesize and play the speech response using the natural TTS voice pipeline.

## Capabilities
- `podcast-zero-buffer-audio`: Lookahead pre-fetching cache for seamless line-by-line broadcast playback.
- `podcast-multi-engine-scripting`: Script generation across Google AI Studio (Gemma 4 / Gemini) and Groq Cloud.
- `hands-free-chat-voice`: Auto-voice speech playback for conversational hands-free trackside chat.
