# Capability: Podcast Zero-Buffer Playback & Hands-Free Chat Voice

## Requirements

### Lookahead Audio Pre-Fetching
- The podcast player MUST maintain a pre-fetch cache (`audioCacheRef`) for synthesized line audio.
- When dialogue line $N$ is playing, the player MUST proactively pre-fetch audio for lines $N+1$ and $N+2$ in the background.
- Line transitions MUST be gapless when next-line audio is cached.
- Duplicate in-flight network requests for the same line index MUST be prevented using an active promise registry.

### Multi-Engine Podcast Scripting
- The `/api/podcast/generate` endpoint MUST support an `engine` parameter:
  - `gemini`: Gemini 3.5 Flash
  - `groq`: Groq LPU (`qwen/qwen3.8-27b` or `llama-3.3-70b-versatile`)
  - `gemma4`: Google AI Studio Gemma 4 (`gemma-2-27b-it` / `gemma-4-31b-it`)
- The podcast roster MUST include "Gemma AI" as an available persona with voice `Fenrir`.
- The HUD Swarm Podcast view MUST provide an engine selector allowing users to choose the scriptwriter.

### Hands-Free Auto-Voice Chat
- The HUD AI Chat view MUST offer an `Auto-Voice` toggle button in the audio controls.
- When enabled, completed assistant responses MUST automatically trigger speech synthesis without requiring a manual click.
- Audio playback MUST respect the mute and volume settings.
