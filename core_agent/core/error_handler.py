"""
Strike Tips - Error Handler
Simple error handling with retry logic
"""
import functools
import time
from typing import Callable, Any, Optional


class StrikeTipsError(Exception):
    """Base exception for Strike Tips"""
    pass


class ScraperError(StrikeTipsError):
    """Scraping failed"""
    pass


class AIError(StrikeTipsError):
    """AI provider failed"""
    pass


class TelegramError(StrikeTipsError):
    """Telegram notification failed"""
    pass


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,)
):
    """
    Retry decorator with exponential backoff
    
    Usage:
        @retry_on_error(max_retries=3, delay=1.0)
        def scrape_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait = delay * (2 ** attempt)  # Exponential backoff
                        print(f"[WARN]  {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}")
                        print(f"   Retrying in {wait:.1f}s...")
                        time.sleep(wait)
            
            # All retries failed
            raise last_exception
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    default_return: Any = None,
    error_message: str = "Operation failed",
    log_error: bool = True
) -> Any:
    """
    Safely execute a function, return default on error
    
    Usage:
        result = safe_execute(
            lambda: scrape_racecard(track),
            default_return=[],
            error_message=f"Failed to scrape {track}"
        )
    """
    try:
        return func()
    except Exception as e:
        if log_error:
            print(f"[ERR] {error_message}: {e}")
        return default_return


class ErrorTracker:
    """Track errors for monitoring"""
    
    def __init__(self):
        self.errors = []
    
    def log(self, error: Exception, context: str = ""):
        """Log an error"""
        self.errors.append({
            "time": time.time(),
            "error": str(error),
            "type": type(error).__name__,
            "context": context
        })
        print(f"[ERR] Error in {context}: {error}")
    
    def get_summary(self) -> dict:
        """Get error summary"""
        return {
            "total_errors": len(self.errors),
            "recent_errors": self.errors[-5:]  # Last 5
        }
    
    def has_errors(self) -> bool:
        """Check if any errors occurred"""
        return len(self.errors) > 0


# Global error tracker
error_tracker = ErrorTracker()


def with_error_tracking(func: Callable) -> Callable:
    """Decorator to track errors"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_tracker.log(e, context=func.__name__)
            raise
    return wrapper


# Example usage patterns
if __name__ == "__main__":
    # Example 1: Retry decorator
    @retry_on_error(max_retries=3, delay=1.0)
    def flaky_function():
        import random
        if random.random() < 0.7:
            raise Exception("Random failure")
        return "Success!"
    
    try:
        result = flaky_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"All retries failed: {e}")
    
    # Example 2: Safe execute
    result = safe_execute(
        lambda: 1 / 0,  # This will fail
        default_return=0,
        error_message="Division failed"
    )
    print(f"Safe result: {result}")
