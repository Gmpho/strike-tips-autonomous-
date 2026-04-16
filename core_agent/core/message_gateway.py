"""
Strike Tips - Message Gateway
Unified message routing for Telegram, WhatsApp, and REST API with security-first design.

Following OpenCLAW patterns for secure agent interaction.
"""
import os
import sys
import json
import hashlib
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import logging

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & CONFIGURATION
# =============================================================================

class Channel(Enum):
    """Supported message channels"""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    REST_API = "rest_api"
    INTERNAL = "internal"


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityProfile:
    """Security configuration for an agent/session"""
    agent_id: str
    allowed_tools: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)
    rate_limit_per_minute: int = 10
    max_message_length: int = 4000
    require_verification: bool = True
    sandbox_mode: bool = False


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""
    tokens: float
    last_refill: float
    capacity: float = 60.0
    refill_rate: float = 1.0  # tokens per second


# =============================================================================
# MESSAGE GATEWAY
# =============================================================================

class MessageGateway:
    """
    Unified message gateway with security-first design.
    
    Features:
    - Channel-agnostic message handling
    - Rate limiting per user/channel
    - Security profile enforcement
    - Message validation & sanitization
    - Session management
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self._rate_limits: Dict[str, RateLimitBucket] = {}
        self._sessions: Dict[str, Dict] = {}
        self._security_profiles: Dict[str, SecurityProfile] = {}
        
        # Load configuration
        self._load_config()
        
        # Initialize default security profile
        self._init_default_profiles()
        
        logger.info("[START] Message Gateway initialized")
    
    def _load_config(self):
        """Load gateway configuration"""
        config_path = os.path.join(self.data_dir, "gateway_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self._config = json.load(f)
        else:
            self._config = self._default_config()
    
    def _default_config(self) -> Dict:
        """Default gateway configuration"""
        return {
            "rate_limits": {
                "telegram": {"per_minute": 20, "per_hour": 100},
                "whatsapp": {"per_minute": 30, "per_hour": 200},
                "rest_api": {"per_minute": 60, "per_hour": 1000},
            },
            "security": {
                "max_message_length": 4000,
                "require_verification": True,
                "sandbox_mode": False,
            },
            "channels": {
                "telegram": {"enabled": True},
                "whatsapp": {"enabled": True},
                "rest_api": {"enabled": True},
            }
        }
    
    def _init_default_profiles(self):
        """Initialize default security profiles"""
        
        # Racing Assistant Profile (default for users)
        self._security_profiles["racing_assistant"] = SecurityProfile(
            agent_id="racing_assistant",
            allowed_tools=[
                "run_daily_scan",
                "get_bankroll_status",
                "query_memory",
                "search_racing_info",
                "place_bet",
                "get_market_snapshot",
            ],
            denied_tools=[
                "exec",
                "write",
                "edit",
                "apply_patch",
                "process",
                "browser",
            ],
            rate_limit_per_minute=10,
            max_message_length=4000,
            require_verification=True,
            sandbox_mode=False,
        )
        
        # Admin Profile (full access)
        self._security_profiles["admin"] = SecurityProfile(
            agent_id="admin",
            allowed_tools=[],  # Empty = all allowed
            denied_tools=[],
            rate_limit_per_minute=60,
            max_message_length=10000,
            require_verification=False,
            sandbox_mode=False,
        )
        
        # Read-only Profile (no betting)
        self._security_profiles["readonly"] = SecurityProfile(
            agent_id="readonly",
            allowed_tools=[
                "get_bankroll_status",
                "query_memory",
                "search_racing_info",
                "get_market_snapshot",
            ],
            denied_tools=[
                "place_bet",
                "settle_bet",
                "run_daily_scan",
            ],
            rate_limit_per_minute=30,
            max_message_length=2000,
            require_verification=False,
            sandbox_mode=True,
        )
    
    # =========================================================================
    # RATE LIMITING
    # =========================================================================
    
    def _get_rate_limit_key(self, channel: Channel, user_id: str) -> str:
        """Generate rate limit key"""
        return f"{channel.value}:{user_id}"
    
    def check_rate_limit(self, channel: Channel, user_id: str) -> tuple[bool, str]:
        """
        Check if request is within rate limits.
        
        Returns:
            (allowed: bool, reason: str)
        """
        key = self._get_rate_limit_key(channel, user_id)
        
        # Get rate limit config for channel
        limits = self._config["rate_limits"].get(channel.value, {"per_minute": 20})
        per_minute = limits["per_minute"]
        
        # Initialize bucket if needed
        if key not in self._rate_limits:
            self._rate_limits[key] = RateLimitBucket(
                tokens=per_minute,
                last_refill=time.time(),
                capacity=per_minute,
                refill_rate=per_minute / 60.0,
            )
        
        bucket = self._rate_limits[key]
        
        # Refill tokens
        now = time.time()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_rate)
        bucket.last_refill = now
        
        # Check if allowed
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return True, "[OK] Rate limit OK"
        
        return False, f"[ERR] Rate limit exceeded. Try again in {int(60 / bucket.refill_rate)} seconds"
    
    # =========================================================================
    # MESSAGE PROCESSING
    # =========================================================================
    
    def process_message(
        self,
        message: str,
        channel: Channel,
        user_id: str,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Process an incoming message through the gateway.
        
        Args:
            message: The message text
            channel: The source channel (TELEGRAM, WHATSAPP, etc.)
            user_id: Unique identifier for the user
            metadata: Optional metadata (chat_id, username, etc.)
            
        Returns:
            Dict with status, sanitized message, and routing info
        """
        # 1. Rate limiting check
        allowed, reason = self.check_rate_limit(channel, user_id)
        if not allowed:
            return {
                "status": "RATE_LIMITED",
                "message": reason,
                "channel": channel.value,
                "user_id": user_id,
            }
        
        # 2. Get or create session
        session = self._get_or_create_session(channel, user_id)
        
        # 3. Get security profile
        profile = self._get_security_profile(session.get("profile", "racing_assistant"))
        
        # 4. Sanitize message
        sanitized = self._sanitize_message(message, profile)
        
        # 5. Build routing context
        context = {
            "channel": channel.value,
            "user_id": user_id,
            "session_id": session["session_id"],
            "profile": profile.agent_id,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        
        # 6. Log for observability
        logger.info(f"[{channel.value.upper()}] User {user_id}: {sanitized[:50]}...")
        
        return {
            "status": "PROCESSED",
            "message": sanitized,
            "context": context,
            "session_id": session["session_id"],
        }
    
    def _sanitize_message(self, message: str, profile: SecurityProfile) -> str:
        """Sanitize message content"""
        # Trim to max length
        if len(message) > profile.max_message_length:
            message = message[:profile.max_message_length] + "..."
        
        # Basic sanitization (remove potentially dangerous content)
        # In production, add more sophisticated filtering
        dangerous_patterns = ["<script", "javascript:", "onerror="]
        for pattern in dangerous_patterns:
            message = message.replace(pattern, "")
        
        return message.strip()
    
    def _get_or_create_session(self, channel: Channel, user_id: str) -> Dict:
        """Get or create a session for the user"""
        session_key = f"{channel.value}:{user_id}"
        
        if session_key not in self._sessions:
            self._sessions[session_key] = {
                "session_id": hashlib.md5(f"{session_key}:{time.time()}".encode()).hexdigest()[:16],
                "channel": channel.value,
                "user_id": user_id,
                "profile": "racing_assistant",  # Default profile
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "message_count": 0,
            }
        
        session = self._sessions[session_key]
        session["last_activity"] = datetime.now().isoformat()
        session["message_count"] += 1
        
        return session
    
    def _get_security_profile(self, profile_id: str) -> SecurityProfile:
        """Get security profile by ID"""
        return self._security_profiles.get(profile_id, self._security_profiles["racing_assistant"])
    
    # =========================================================================
    # SECURITY PROFILE MANAGEMENT
    # =========================================================================
    
    def set_user_profile(self, channel: Channel, user_id: str, profile_id: str) -> bool:
        """Assign a security profile to a user"""
        if profile_id not in self._security_profiles:
            return False
        
        session_key = f"{channel.value}:{user_id}"
        if session_key in self._sessions:
            self._sessions[session_key]["profile"] = profile_id
            return True
        
        return False
    
    def get_user_profile(self, channel: Channel, user_id: str) -> Optional[str]:
        """Get user's current security profile"""
        session_key = f"{channel.value}:{user_id}"
        if session_key in self._sessions:
            return self._sessions[session_key].get("profile")
        return None
    
    def list_profiles(self) -> List[str]:
        """List available security profiles"""
        return list(self._security_profiles.keys())
    
    # =========================================================================
    # CHANNEL ROUTING
    # =========================================================================
    
    def route_message(self, message: str, channel: Channel, **kwargs) -> Dict[str, Any]:
        """
        Route a message to the appropriate handler based on channel.
        """
        handlers = {
            Channel.TELEGRAM: self._handle_telegram,
            Channel.WHATSAPP: self._handle_whatsapp,
            Channel.REST_API: self._handle_rest_api,
            Channel.INTERNAL: self._handle_internal,
        }
        
        handler = handlers.get(channel, self._handle_internal)
        return handler(message, **kwargs)
    
    def _handle_telegram(self, message: str, **kwargs) -> Dict:
        """Handle Telegram message"""
        chat_id = kwargs.get("chat_id", "unknown")
        return {
            "handler": "telegram",
            "output": f"Telegram message queued for user {chat_id}",
            "message": message,
        }
    
    def _handle_whatsapp(self, message: str, **kwargs) -> Dict:
        """Handle WhatsApp message"""
        phone = kwargs.get("phone", "unknown")
        return {
            "handler": "whatsapp",
            "output": f"WhatsApp message queued for {phone}",
            "message": message,
        }
    
    def _handle_rest_api(self, message: str, **kwargs) -> Dict:
        """Handle REST API message"""
        return {
            "handler": "rest_api",
            "output": "REST API message processed",
            "message": message,
        }
    
    def _handle_internal(self, message: str, **kwargs) -> Dict:
        """Handle internal message"""
        return {
            "handler": "internal",
            "output": "Internal message processed",
            "message": message,
        }
    
    # =========================================================================
    # RESPONSE FORMATTING
    # =========================================================================
    
    def format_response(
        self,
        response: Any,
        channel: Channel,
        includeMarkdown: bool = True,
    ) -> str:
        """
        Format agent response for the specific channel.
        """
        if channel == Channel.TELEGRAM:
            return self._format_telegram(response, includeMarkdown)
        elif channel == Channel.WHATSAPP:
            return self._format_whatsapp(response)
        else:
            return str(response)
    
    def _format_telegram(self, response: Any, markdown: bool) -> str:
        """Format response for Telegram (supports Markdown)"""
        if isinstance(response, dict):
            if "status" in response:
                status = response["status"]
                if status == "PLACED":
                    return f"[OK] Bet placed!\n{response.get('bet_id', '')}\nReturn: R{response.get('potential_return', 0):.2f}"
                elif status == "REJECTED":
                    return f"[ERR] {response.get('reason', 'Bet rejected')}"
                elif status == "VALUE_BETS_FOUND":
                    top = response.get("top_selection", {})
                    return f"[HIT] Value Bet Found!\n{top.get('horse', 'N/A')}\nEdge: +{top.get('edge_percent', 0):.1f}%\nStake: R{top.get('stake', 0):.2f}"
            
            return json.dumps(response, indent=2)
        
        return str(response)
    
    def _format_whatsapp(self, response: Any) -> str:
        """Format response for WhatsApp (plain text only)"""
        if isinstance(response, dict):
            if "status" in response:
                status = response["status"]
                if status == "PLACED":
                    return f"Bet placed! ID: {response.get('bet_id', '')}"
                elif status == "REJECTED":
                    return f"Bet rejected: {response.get('reason', '')}"
                elif status == "VALUE_BETS_FOUND":
                    top = response.get("top_selection", {})
                    return f"Value Bet: {top.get('horse', 'N/A')} @ {top.get('edge_percent', 0):.1f}% edge"
        
        return str(response)[:1600]  # WhatsApp max length
    
    # =========================================================================
    # TELEGRAM WEBHOOK HANDLER
    # =========================================================================
    
    async def handle_telegram_update(self, update: Dict) -> Optional[str]:
        """
        Handle incoming Telegram webhook update.
        
        Args:
            update: Telegram Update object
            
        Returns:
            Response message to send back
        """
        if "message" not in update:
            return None
        
        message = update["message"]
        text = message.get("text", "")
        chat_id = str(message["chat"]["id"])
        user_id = str(message["from"]["id"] if "from" in message else chat_id)
        
        # Process through gateway
        result = self.process_message(
            message=text,
            channel=Channel.TELEGRAM,
            user_id=user_id,
            metadata={"chat_id": chat_id},
        )
        
        if result["status"] == "RATE_LIMITED":
            return result["message"]
        
        if result["status"] == "PROCESSED":
            # Return the sanitized message for agent processing
            return result["message"]
        
        return "[ERR] Unable to process message"
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    def health_check(self) -> Dict:
        """Return gateway health status"""
        return {
            "status": "healthy",
            "channels": {
                "telegram": self._config["channels"]["telegram"]["enabled"],
                "whatsapp": self._config["channels"]["whatsapp"]["enabled"],
                "rest_api": self._config["channels"]["rest_api"]["enabled"],
            },
            "active_sessions": len(self._sessions),
            "security_profiles": list(self._security_profiles.keys()),
            "rate_limited_users": len([k for k, v in self._rate_limits.items() if v.tokens < 1]),
        }


# =============================================================================
# MAIN - CLI for testing
# =============================================================================

def main():
    """CLI for testing the message gateway"""
    print("[SIGNAL] Strike Tips Message Gateway")
    print("=" * 50)
    
    gateway = MessageGateway()
    
    # Test health check
    print("\n[HEALTH] Health Check:")
    print(json.dumps(gateway.health_check(), indent=2))
    
    # Test profiles
    print("\n[SEC] Available Security Profiles:")
    for profile in gateway.list_profiles():
        print(f"  • {profile}")
    
    # Test message processing
    print("\n[MSG] Testing message processing...")
    
    result = gateway.process_message(
        message="What's the bankroll status?",
        channel=Channel.TELEGRAM,
        user_id="test_user_123",
    )
    
    print(f"\n[OK] Processed: {result['status']}")
    print(f"   Session: {result['session_id']}")
    print(f"   Profile: {result['context']['profile']}")
    
    # Test rate limiting
    print("\n[FAST] Rate Limit Test:")
    for i in range(22):
        allowed, reason = gateway.check_rate_limit(Channel.TELEGRAM, "test_user_123")
        if not allowed:
            print(f"   Request {i+1}: {reason}")
            break
    else:
        print("   All 20 requests passed!")
    
    print("\n[START] Gateway initialized successfully!")


if __name__ == "__main__":
    main()
