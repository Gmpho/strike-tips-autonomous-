"""
Strike Tips - Modal Deployment Script
Deploy to Modal with free $30 credit
"""

import subprocess
import sys
import os


def check_modal_setup():
    """Check if Modal is set up correctly"""
    try:
        result = subprocess.run(
            ["modal", "token", "show"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("[OK] Modal is authenticated")
            return True
        else:
            print("[ERR] Modal not authenticated")
            return False
    except FileNotFoundError:
        print("[ERR] Modal CLI not found. Install with: pip install modal")
        return False


def setup_secrets():
    """Set up Modal secrets"""
    print("\n[SEC] Setting up Modal secrets...")

    secrets = {}

    # Required secrets
    print("\n📱 Telegram Configuration (Required):")
    secrets["TELEGRAM_BOT_TOKEN"] = input("Telegram Bot Token: ").strip()
    secrets["TELEGRAM_CHAT_ID"] = input("Telegram Chat ID: ").strip()

    # AI Provider secrets (at least one recommended)
    print("\n[BOT] AI Provider Configuration (at least one recommended):")

    gemini = input("Gemini API Key (press Enter to skip): ").strip()
    if gemini:
        secrets["GEMINI_API_KEY"] = gemini

    claude = input("Anthropic API Key (press Enter to skip): ").strip()
    if claude:
        secrets["ANTHROPIC_API_KEY"] = claude

    openai = input("OpenAI API Key (press Enter to skip): ").strip()
    if openai:
        secrets["OPENAI_API_KEY"] = openai

    ollama = input("Ollama Host URL (default: http://localhost:11434): ").strip()
    secrets["OLLAMA_HOST"] = ollama or "http://localhost:11434"

    # Create secret
    secret_dict = " ".join([f"{k}={v}" for k, v in secrets.items()])

    cmd = f"modal secret create strike-tips-secrets {secret_dict}"
    print(f"\nRunning: {cmd}")

    result = subprocess.run(cmd, shell=True)

    if result.returncode == 0:
        print("[OK] Secrets created successfully")
    else:
        print("[ERR] Failed to create secrets")

    return result.returncode == 0


def deploy():
    """Deploy to Modal"""
    print("\n[START] Deploying Strike Tips to Modal...")

    # Create volumes
    print("\n[PKG] Creating data volume...")
    subprocess.run(
        ["modal", "volume", "create", "strike-tips-data"], capture_output=True
    )
    print("\n[PKG] Creating Ollama models volume...")
    subprocess.run(
        ["modal", "volume", "create", "ollama-models"], capture_output=True
    )

    # Deploy the app
    print("\n[START] Deploying application...")
    result = subprocess.run(["modal", "deploy", "core_agent.core.modal_app"], capture_output=False)

    if result.returncode == 0:
        print("\n[OK] Deployment successful!")
        
        # Pull models after deploy
        print("\n[MODEL] Pulling Ollama models (functiongemma:270m, qwen3.5:0.8b, embeddinggemma:300m)...")
        pull_result = subprocess.run(
            ["modal", "run", "core_agent.core.modal_app::pull_ollama_models"], 
            capture_output=False
        )
        if pull_result.returncode == 0:
            print("[OK] Models pulled successfully")
        else:
            print("[WARN] Model pull had issues - check logs")
        
        print("\n[LIST] Next steps:")
        print("  1. Test the deployment: modal run core_agent.core.modal_app::run_scan")
        print("  2. Check logs: modal app logs strike-tips-racing")
        print("  3. Check Ollama: curl https://gmpho--strike-tips-racing-ollama-server.modal.run/api/tags")
    else:
        print("\n[ERR] Deployment failed")

    return result.returncode == 0


def main():
    """Main deployment flow"""
    print("=" * 60)
    print("[RACE] STRIKE TIPS - Modal Deployment")
    print("=" * 60)

    # Check Modal setup
    if not check_modal_setup():
        print("\n[WARN]  Please set up Modal first:")
        print("  1. pip install modal")
        print("  2. modal setup")
        sys.exit(1)

    # Check if secrets exist
    result = subprocess.run(["modal", "secret", "list"], capture_output=True, text=True)

    if "strike-tips-secrets" not in result.stdout:
        print("\n[WARN]  Secrets not found. Let's set them up.")
        if not setup_secrets():
            print("[ERR] Secret setup failed")
            sys.exit(1)
    else:
        print("[OK] Secrets already configured")
        update = input("\nUpdate secrets? (y/N): ").strip().lower()
        if update == "y":
            setup_secrets()

    # Deploy
    deploy()


if __name__ == "__main__":
    main()
