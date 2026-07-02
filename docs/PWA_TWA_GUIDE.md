# 📱 Progressive Web App (PWA) & Trusted Web Activity (TWA) Guide

This guide details how the **Strike Tips HUD** is structured as a installable **Progressive Web App (PWA)** and how it can be packaged as a native Android app using **Trusted Web Activity (TWA)**.

---

## ⚡ Progressive Web App (PWA) Architecture

The PWA setup enables the Strike Tips web dashboard to behave like a native client-side application. It allows installation on iOS, Android, macOS, and Windows with a standalone borderless layout and offline caching.

### 1. Key Components
*   **[`public/manifest.json`](file:///home/giftmpho/Kimi_Agent_Strike%20Tips%20Racing%20Bot/strike-tips-hud/public/manifest.json)**: Defines the app metadata (names, theme colors, standalone display mode, and maskable icons for smooth adaptive launcher fits).
*   **[`public/sw.js`](file:///home/giftmpho/Kimi_Agent_Strike%20Tips%20Racing%20Bot/strike-tips-hud/public/sw.js)**: The service worker. Implements advanced caching strategies:
    *   **Cache-First** for static assets (JS, CSS, SVGs, images) to enable fast loading.
    *   **Network-First** for page navigation and API requests, fallback to offline caching.
    *   **Offline Fallback**: Displays [`offline.html`](file:///home/giftmpho/Kimi_Agent_Strike%20Tips%20Racing%20Bot/strike-tips-hud/public/offline.html) if there's no internet connection and the requested resource isn't cached.
    *   *Note: Skips caching for dev HMR, swagger docs, and local Ollama ports to prevent development database/compilation clashes.*
*   **[`src/hooks/usePWA.ts`](file:///home/giftmpho/Kimi_Agent_Strike%20Tips%20Racing%20Bot/strike-tips-hud/src/hooks/usePWA.ts)**: A React hook that captures the browser's `beforeinstallprompt` event and exposes a custom installation trigger inside Settings and Footer.

---

## 🤖 Trusted Web Activity (TWA) Integration (Android Play Store)

A **Trusted Web Activity (TWA)** is a specialized browser tab that runs your PWA in fullscreen mode inside an Android app shell. It allows you to publish the Strike Tips HUD directly into the **Google Play Store**.

```
┌────────────────────────────────────────────────────────┐
│                  GOOGLE PLAY STORE APP                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │             ANDROID APP CONTAINER (TWA)          │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │            STRIKE TIPS PWA HUD             │  │  │
│  │  │  • Fullscreen standalone mode              │  │  │
│  │  │  • Hardware-accelerated GPU WebGL/WebGPU   │  │  │
│  │  │  • Service Worker caching & offline modes   │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

### 1. Verification & Trust (Digital Asset Links)
To remove the URL address bar and run the app in fullscreen mode, you must verify ownership of both the web domain and the Android package using **Digital Asset Links**.

1.  **Generate SHA256 Fingerprint**: Compile and sign your Android app (using Android Studio or Bubblewrap) to get your signing certificate SHA256 fingerprint.
2.  **Create `assetlinks.json`**: Create a file at the path `public/.well-known/assetlinks.json` on your host domain:
    ```json
    [
      {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
          "namespace": "android_app",
          "package_name": "app.verity.striketips.hud",
          "sha256_cert_fingerprints": [
            "XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX"
          ]
        }
      }
    ]
    ```
3.  **Vercel/Static Configuration**: Ensure your server configuration serves this file with Content-Type `application/json` without redirects.

### 2. Packaging the TWA via CLI (Bubblewrap)
The fastest way to build your TWA Android package (.apk / .aab) is using Google's **Bubblewrap CLI**:

1.  **Initialize Bubblewrap**:
    ```bash
    npm install -g @bubblewrap/cli
    bubblewrap init --manifest=https://strike-tips-hud.vercel.app/manifest.json
    ```
2.  **Configure App parameters**:
    Bubblewrap will read your PWA manifest and prompt you for:
    *   Package ID (e.g. `app.verity.striketips.hud`)
    *   Status bar/theme colors
    *   Version codes
3.  **Build the Signing Key & Package**:
    ```bash
    bubblewrap build
    ```
    This generates a signed Release App Bundle (`app-release-bundle.aab`) ready to upload to the Google Play Console!

### 3. Benefits of PWA + TWA:
*   **Instant Updates**: Because the app runs your PWA, any frontend updates you push to Vercel/GitHub are instantly visible to Android app users without needing to re-submit packages to the Google Play Store!
*   **Native Feel**: Access to full native sharing sheets, notification trays, launcher shortcuts, and standalone task switcher entries.
*   **Ultra-lightweight**: The native APK size is under **2 MB**, as the browser engine (Chrome/custom tabs) is shared.
