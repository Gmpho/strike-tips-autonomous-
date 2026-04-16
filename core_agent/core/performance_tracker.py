"""
Strike Tips - Performance Tracker
Tracks AI model performance, costs, and success rates.
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

class ModelMetrics(BaseModel):
    model_name: str
    total_requests: int = 0
    successful_requests: int = 0
    total_latency: float = 0.0
    total_cost: float = 0.0
    last_used: str = ""

class PerformanceTracker:
    """
    Tracks AI model performance and costs.
    Saves metrics to JSON for persistence.
    """
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.metrics_file = os.path.join(data_dir, "performance_metrics.json")
        self.metrics: Dict[str, ModelMetrics] = self._load_metrics()
        
    def _load_metrics(self) -> Dict[str, ModelMetrics]:
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    return {k: ModelMetrics(**v) for k, v in data.items()}
            except Exception as e:
                print(f"[WARN] Error loading performance metrics: {e}")
        return {}

    def _save_metrics(self):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.metrics_file, 'w') as f:
                # Use model_dump for Pydantic v2
                data = {k: v.model_dump() for k, v in self.metrics.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[WARN] Error saving performance metrics: {e}")

    def track_request(
        self, 
        model_name: str, 
        latency: float, 
        cost: float, 
        success: bool = True
    ):
        """Record a single AI request's metrics"""
        if model_name not in self.metrics:
            self.metrics[model_name] = ModelMetrics(model_name=model_name)
            
        m = self.metrics[model_name]
        m.total_requests += 1
        if success:
            m.successful_requests += 1
        m.total_latency += latency
        m.total_cost += cost
        m.last_used = datetime.now().isoformat()
        
        self._save_metrics()

    def get_summary(self) -> Dict:
        """Get human-readable summary of all model performance"""
        summary = {}
        for name, m in self.metrics.items():
            avg_latency = m.total_latency / m.total_requests if m.total_requests > 0 else 0
            success_rate = (m.successful_requests / m.total_requests * 100) if m.total_requests > 0 else 0
            
            summary[name] = {
                "success_rate": f"{success_rate:.1f}%",
                "avg_latency": f"{avg_latency:.2f}s",
                "total_cost": f"${m.total_cost:.4f}",
                "requests": m.total_requests,
                "last_used": m.last_used
            }
        return summary

# Global instance for easy import
tracker = PerformanceTracker() 