from playwright.sync_api import sync_playwright
import json

def capture_requests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Intercept network requests
        def on_request(request):
            if "api" in request.url or "json" in request.url:
                print(f"📡 API Request: {request.url}")
        
        page.on("request", on_request)
        
        print("🔍 Navigating to Oddschecker International...")
        page.goto("https://www.oddschecker.com/horse-racing/international")
        page.wait_for_timeout(5000)
        browser.close()

if __name__ == "__main__":
    capture_requests()
