# October 2026 security advisories — repo impact

Three advisories landed in the same week (19–22 Oct 2026). This note records
the repo inventory and the concrete fixes so the next rebuild/upgrade does not
regress them.

## 1. Python — eMudhra / emSign CA compromise (TLS MITM)

**What happened:** Eight eMudhra intermediate CA private keys were weak
(`d < 256`, recoverable by brute force). The emSign root was removed from CA
bundles. pip, uv, Node.js and Go each vendor their own trust store, so a
browser or OS update alone does **not** protect them. No exploitation observed.

**Fixed versions:** `pip >= 26.2.2` (bundles certifi 2026.10.19), `certifi >=
2026.10.19`, `uv >= 0.13.4`, `sigstore >= 4.5.1`, CPython 3.13.17 / 3.14.9 /
3.15.1 (bundled pip only). Node 22.23.4 / 24.22.1 / 26.12.1 block the keys.

**Why pip is special:** pip loads its vendored certifi *in addition to* the OS
store and it cannot be disabled. `REQUESTS_CA_BUNDLE`/`--cert` only add CAs.
Any pip < 26.2.2 keeps trusting the revoked intermediates regardless of the
system trust store.

**Repo exposure (before this change):**
- `requirements.txt` did not pin certifi → whatever resolved at build time was
  baked into the Modal image (last image build predates 20 Oct).
- `pinned-requirements.txt` (used by `Dockerfile.odds`, the odds-monitor
  container) pinned `certifi==2026.6.17` → vulnerable.
- `Dockerfile` upgraded `pip` unpinned and never refreshed OS ca-certificates.
- `Dockerfile.odds` installed `uv` unpinned from a mirror with
  `--trusted-host` (TLS verification off for that host).

**Fixed here:** certifi pinned to 2026.10.19 in both requirement files;
`Dockerfile` installs `pip>=26.2.2` and refreshes `ca-certificates`;
`Dockerfile.odds` pins `uv>=0.13.4` and refreshes `ca-certificates`.

**Verify inside a rebuilt image:**
```bash
docker run --rm <image> python -m pip --version      # >= 26.2.2
docker run --rm <image> python -c "import certifi;print(certifi.__version__)"  # >= 2026.10.19
docker run --rm <image> uv --version                 # >= 0.13.4 (odds image)
```
Rebuild with the layer cache off once, or the pinned layer is reused:
`modal deploy` after this Dockerfile change is enough (the layer hash changed).

## 2. PHP — CVE-2026-109618 / CVE-2026-109619 ("php2shell")

Unauthenticated RCE / memory disclosure in PHP request handling, CVSS 9.2–9.8,
all versions 5.4 → 8.5.11. PoC public, exploitation not confirmed. Fixed in
**8.5.12, 8.4.27, 8.3.36, 8.2.35** (8.1 and earlier are EOL, no fix).

**Repo exposure: none.** Zero `.php` files, no PHP in either Dockerfile, no PHP
binary on the dev host. Nothing to patch here. If any dev machine, legacy site
or vendor appliance runs PHP, patch to the versions above (or take it offline
per CISA) and check web logs for PHP workers spawning shells.

## 3. Node.js — October 21 security releases

Ten fixes, highest severity HIGH:
- **CVE-2026-111497** — Brotli decoder OOB write, RCE (22/24/26.x). Reachable
  via `node:zlib` or `fetch()` of a Brotli response.
- **CVE-2026-105482 / 105483 / 106069 / 106072** — DNS NUL truncation and TLS
  hostname-verification bypasses.
- **CVE-2026-106074** — `randomUUID()`/`randomInt()` cache reuse in SEA/snapshot
  builds (entropy collapse).
- Plus medium/low: keep-alive response mix-up, ZipFile prefix leak, Permission
  Model grants.

Fixed: **22.23.4, 24.22.1, 26.12.1**. Node 20 is EOL and will not be patched.
The same releases also block the eight compromised eMudhra keys and refresh the
bundled NSS roots.

**Repo exposure:**
- HUD build tooling ran **Node 24.11.0** locally (< 24.22.1). Pinned via
  `strike-tips-hud/.nvmrc` → `24.22.1`.
- No `engines` field and no Node stage in either Dockerfile, so containers are
  unaffected. Cloudflare Pages/Workers runtimes are CF-managed and patched.
- Browser-side WebLLM is unaffected (browser TLS stack, already blocked by
  Chrome/Firefox CRLSets).

## Local developer machines (do these once)

```bash
# every venv you use (the repo has .venv and venv_linux)
python -m pip install "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
python -m pip install --upgrade "certifi>=2026.10.19" "uv>=0.13.4"

# Node toolchain
nvm install 24.22.1 && nvm use 24.22.1
```

State on the dev host at time of writing: system `pip 25.1.1`, `certifi
2026.1.4`, Node `v24.11.0` — all below the fixed versions. The system Python is
distro-managed; upgrade inside the venvs rather than with `--break-system-packages`.

## Open follow-up (not done here)

`Dockerfile` still uses `python:3.10-slim`; Python 3.10 is end-of-life and no
longer receives these fixes. Moving to `python:3.12-slim` (matching
`Dockerfile.odds`) is the durable fix but needs a full dependency rebuild and
settlement-suite run — treat it as its own change.
