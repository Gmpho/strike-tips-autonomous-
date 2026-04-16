# Frontend Healing Swarm Dashboard Plan

## Overview
Add a new **Healing Cloud** tab to the sidebar and integrate system monitoring for the MAF healing swarm.

## Current Sidebar (page.tsx lines 243-250)

```typescript
const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'chat', label: 'AI Agent', icon: MessageSquare },
  { id: 'races', label: 'Race Analyzer', icon: Zap },
  { id: 'search', label: 'Intelligence', icon: Search },
  { id: 'bets', label: 'My Portfolio', icon: Wallet },
  { id: 'settings', label: 'Settings', icon: Settings },
]
```

## Proposed Sidebar Additions

```typescript
const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'healing', label: 'Healing Cloud', icon: HeartPulse },    // NEW
  { id: 'chat', label: 'AI Agent', icon: MessageSquare },
  { id: 'races', label: 'Race Analyzer', icon: Zap },
  { id: 'search', label: 'Intelligence', icon: Search },
  { id: 'bets', label: 'My Portfolio', icon: Wallet },
  { id: 'system', label: 'System Vitals', icon: Cpu },              // NEW
  { id: 'settings', label: 'Settings', icon: Settings },
]
```

## New Tab: Healing Cloud Dashboard

### Features

1. **Real-time Selector Health Grid**
   - Visual cards for each element type (odds, horse_name, jockey, etc.)
   - Color-coded: Green (healthy), Yellow (degraded), Red (failed)
   - Shows success rate percentage

2. **Patch Status Panel**
   - Pending patches count
   - Applied patches count
   - Rejected patches count
   - Latest patch timestamp

3. **Healing Events Feed**
   - Real-time log of healing events
   - Event types: PATCH_APPLIED, PATCH_REJECTED, SELECTOR_FAILED
   - Timestamp and details

4. **Mode Indicator**
   - ACTIVE MODE (green) - auto-healing enabled
   - ADVISORY MODE (yellow) - human intervention needed

### UI Components

```typescript
// Healing Cloud Tab Layout
<motion.div key="healing" className="space-y-8">
  {/* Mode Banner */}
  <div className={`p-4 rounded-2xl ${isActiveMode ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-yellow-500/10 border-yellow-500/30'}`}>
    <div className="flex items-center gap-3">
      {isActiveMode ? <CheckCircle className="w-6 h-6 text-emerald-500" /> : <AlertTriangle className="w-6 h-6 text-yellow-500" />}
      <span className="font-bold">{isActiveMode ? 'ACTIVE MODE' : 'ADVISORY MODE'}</span>
      <span className="text-sm text-slate-400">{isActiveMode ? 'Auto-healing enabled' : 'Manual intervention required'}</span>
    </div>
  </div>

  {/* Selector Health Grid */}
  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
    {selectorHealth.map(selector => (
      <div className={`p-4 rounded-xl border ${selector.status}`}>
        <div className="font-bold">{selector.name}</div>
        <div className="text-2xl">{selector.successRate}%</div>
        <div className="text-xs text-slate-500">{selector.failCount} failures</div>
      </div>
    ))}
  </div>

  {/* Patch Stats */}
  <div className="grid grid-cols-3 gap-4">
    <div className="p-4 bg-blue-500/10 rounded-xl">
      <div className="text-2xl font-bold text-blue-400">{pendingPatches}</div>
      <div className="text-sm text-slate-400">Pending</div>
    </div>
    <div className="p-4 bg-emerald-500/10 rounded-xl">
      <div className="text-2xl font-bold text-emerald-400">{appliedPatches}</div>
      <div className="text-sm text-slate-400">Applied</div>
    </div>
    <div className="p-4 bg-rose-500/10 rounded-xl">
      <div className="text-2xl font-bold text-rose-400">{rejectedPatches}</div>
      <div className="text-sm text-slate-400">Rejected</div>
    </div>
  </div>

  {/* Healing Events */}
  <div className="glass-card p-6 rounded-3xl">
    <h3 className="font-bold mb-4">Healing Events</h3>
    <div className="space-y-2 max-h-64 overflow-y-auto">
      {healingEvents.map(event => (
        <div className="flex items-center gap-2 text-sm">
          <span className={`text-xs ${event.type === 'APPLIED' ? 'text-emerald-500' : 'text-rose-500'}`}>
            {event.type}
          </span>
          <span className="text-slate-400">{event.message}</span>
          <span className="ml-auto text-xs text-slate-600">{event.time}</span>
        </div>
      ))}
    </div>
  </div>
</motion.div>
```

## New Tab: System Vitals Dashboard

### Features

1. **Ollama Status**
   - Model list with status (loaded/not loaded, local/cloud)
   - Response time indicator
   - GPU memory usage (if available)

2. **Cloud Models**
   - nemotron-3-nano:30b - Fast agentic
   - nemotron-3-super - Deep reasoning
   - Connection status indicators

3. **API Health**
   - Backend API status
   - Response times
   - Error rate

3. **MAF Agent Status**
   - Current model in use
   - Tool execution stats
   - Session count

### UI Components

```typescript
{activeTab === 'system' && (
  <motion.div key="system" className="space-y-8">
    {/* Ollama Models */}
    <div className="glass-card p-6 rounded-3xl">
      <h3 className="font-bold flex items-center gap-2 mb-4">
        <Cpu className="w-5 h-5 text-orange-500" />
        Ollama Models
      </h3>
      
      {/* Local Models */}
      <div className="mb-4">
        <div className="text-xs font-bold text-slate-500 uppercase mb-2">Local (Offline)</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {ollamaModels.local.map(model => (
            <div className={`p-4 rounded-xl border ${model.loaded ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-white/10'}`}>
              <div className="font-bold text-sm">{model.name}</div>
              <div className="text-xs text-slate-500">{model.size}</div>
              <div className={`mt-2 text-xs ${model.loaded ? 'text-emerald-500' : 'text-slate-500'}`}>
                {model.loaded ? '● Loaded' : '○ Not loaded'}
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Cloud Models */}
      <div>
        <div className="text-xs font-bold text-slate-500 uppercase mb-2">Cloud (Online)</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {ollamaModels.cloud.map(model => (
            <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-500/5">
              <div className="font-bold text-sm text-blue-400">{model.name}</div>
              <div className="text-xs text-slate-500">{model.description}</div>
              <div className="mt-2 text-xs text-blue-500">☁️ Available</div>
            </div>
          ))}
        </div>
      </div>
    </div>

    {/* API Status */}
    <div className="glass-card p-6 rounded-3xl">
      <h3 className="font-bold flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-blue-500" />
        API Health
      </h3>
      <div className="grid grid-cols-3 gap-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-emerald-400">{apiStatus.uptime}</div>
          <div className="text-xs text-slate-500">Uptime</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-400">{apiStatus.avgResponse}ms</div>
          <div className="text-xs text-slate-500">Avg Response</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-orange-400">{apiStatus.errorRate}%</div>
          <div className="text-xs text-slate-500">Error Rate</div>
        </div>
      </div>
    </div>

    {/* MAF Agent Stats */}
    <div className="glass-card p-6 rounded-3xl">
      <h3 className="font-bold flex items-center gap-2 mb-4">
        <Bot className="w-5 h-5 text-purple-500" />
        MAF Agent
      </h3>
      <div className="space-y-2">
        <div className="flex justify-between">
          <span className="text-slate-400">Current Model</span>
          <span className="font-bold text-orange-500">{agentStats.currentModel}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Tools Executed</span>
          <span className="font-bold">{agentStats.toolsExecuted}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Active Sessions</span>
          <span className="font-bold">{agentStats.sessions}</span>
        </div>
      </div>
    </div>
  </motion.div>
)}
```

## Required API Endpoints

Add to backend:

| Endpoint | Returns |
|----------|---------|
| `GET /api/healing/status` | Selector health, patch counts, mode |
| `GET /api/healing/events` | Recent healing events |
| `POST /api/healing/trigger` | Manual trigger of healing |
| `GET /api/system/ollama` | Ollama model status |
| `GET /api/system/health` | API health metrics |

## Implementation Steps

1. Add new tab types: `'healing' | 'system'`
2. Add icons: `HeartPulse` (lucide-react), `Cpu`, `Activity`
3. Create healing tab UI components
4. Create system tab UI components
5. Add API calls to fetch healing/system data
6. Add polling for real-time updates

## File Changes

| File | Change |
|------|--------|
| `page.tsx` | Add tabs, UI components |
| `lib/api.ts` | Add API functions |