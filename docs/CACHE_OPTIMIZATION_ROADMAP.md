# Strike Tips Racing Bot Cache Optimization Roadmap

## Current State Assessment (as of 2026-05-31)

The cache system is currently healthy and self-maintaining:
- **Intelligence Cache**: 784K (180 files) - well under thresholds
- **Alert History**: 56K (364 lines) - far below 5MB rotation threshold
- **PDF Cache**: 108K (7 files) - minimal footprint
- **Chroma DB**: 3.8M (10 files) - healthy vector memory size
- **Market Snapshot**: 908K - refreshed every ~45s

Key mechanisms already in place:
✅ Intelligence Cache TTL: 6-hour automatic pruning of stale baseline data  
✅ Alert History Rotation: Size-based rotation at 5MB threshold  
✅ Automatic cleanup via adaptive odds monitor loop (every ~45s)  
✅ Ephemeral container benefits from Modal deployment  

## Near-Term Optimizations (0-3 Months)
*Low effort, high impact improvements*

1. **Dynamic TTL Adjustment**
   - Problem: Fixed 6-hour TTL may not align with race schedules (some races run daily, others weekly)
   - Solution: Adjust TTL based on next scheduled race time for each event
   - Impact: More relevant baseline data, reduced cache churn
   - Effort: Low (modify `intelligence_cache_manager.py`)
   - Metrics: Cache hit rate for active races

2. **Cache Warming for Peak Hours**
   - Problem: Cold cache during high-traffic periods causes latency spikes
   - Solution: Pre-load anticipated race data before known peak windows
   - Impact: Reduced latency during critical betting windows
   - Effort: Low-Medium (integrate with scheduler)
   - Metrics: 95th percentile latency during peak hours

3. **Enhanced Cache Metrics & Logging**
   - Problem: Limited visibility into cache performance
   - Solution: Add Prometheus-style metrics for cache hits/misses, size, eviction rates
   - Impact: Data-driven optimization capacity
   - Effort: Low (add lightweight metrics collection)
   - Metrics: Cache efficiency ratio (hits/(hits+misses))

## Mid-Term Optimizations (3-12 Months)
*Moderate effort, strategic improvements*

1. **Hierarchical Caching Strategy**
   - Problem: All cache treated equally despite varying access patterns
   - Solution: Implement L1 (in-memory, hot data) and L2 (persistent, warm data) tiers
   - Impact: Optimized for different data access patterns (real-time odds vs historical analysis)
   - Effort: Medium (requires cache abstraction layer)
   - Metrics: Latency reduction for hot data paths

2. **Intelligent Cache Prevalence**
   - Problem: Baseline odds updates may cause cache thrashing during volatile periods
   - Solution: Implement adaptive write-behind buffering for baseline updates
   - Impact: Reduced write amplification during high-volatility races
   - Effort: Medium (modify intelligence cache update logic)
   - Metrics: Write operation reduction during volatile periods

3. **Cross-Cache Intelligence**
   - Problem: Cache systems operate in isolation despite related data
   - Solution: Implement cache coherence hints between related systems (e.g., alert engine → intelligence cache)
   - Impact: Reduced redundant data fetching
   - Effort: Medium-High (requires event-driven cache coordination)
   - Metrics: Reduction in duplicate data retrieval operations

## Long-Term Vision (12+ Months)
*Strategic investments for scale*

1. **Predictive Cache Prefetching**
   - Problem: Reactive caching misses anticipation opportunities
   - Solution: ML-based prediction of likely race queries based on time, user behavior, and historical patterns
   - Impact: Near-zero latency for predictable requests
   - Effort: High (requires ML model integration)
   - Prerequisites: Sufficient historical query data

2. **Geo-Distributed Cache Layer**
   - Problem: Single-point cache latency for distributed users
   - Solution: Implement edge caching for regional users (if expanding geographically)
   - Impact: Reduced latency for global user base
   - Effort: High (infrastructure changes)
   - Prerequisites: Geographic user distribution

3. **Cache-as-a-Service Abstraction**
   - Problem: Tight coupling between cache implementations and business logic
   - Solution: Abstract cache interactions behind a unified service interface
   - Impact: Easier experimentation with different cache technologies (Redis, Memcached, etc.)
   - Effort: High (refactoring)
   - Prerequisites: Stable cache interfaces

## Monitoring & Success Metrics

### Key Performance Indicators to Track:
1. **Cache Efficiency Ratio** = (Cache Hits) / (Cache Hits + Cache Misses) - Target: >85%
2. **95th Percentile Latency** for cache-dependent operations - Target: <100ms
3. **Cache Size Growth Rate** - Target: Stable or slowly growing (not exponential)
4. **Eviction Rate** - Should correlate with TTL settings and race schedules
5. **Memory Utilization** - Percentage of allocated cache actually used

### Implementation Phases:
```
Phase 1 (0-1mo): Implement near-term optimizations
Phase 2 (1-3mo): Deploy monitoring dashboards
Phase 3 (3-6mo): Validate and refine based on metrics
Phase 4 (6-12mo): Plan and initiate mid-term optimizations
```

## Risk Mitigation
- All optimizations should be feature-flagged for safe rollout
- Maintain backward compatibility with existing cache interfaces
- Performance testing in staging before production deployment
- Rollback procedures for each optimization phase

## Conclusion
The current cache system is fundamentally sound and requires no immediate intervention. This roadmap provides a structured path for incremental improvements that will enhance performance as the system scales, while maintaining the current "smooth as is" operational state.

*Last updated: 2026-05-31*