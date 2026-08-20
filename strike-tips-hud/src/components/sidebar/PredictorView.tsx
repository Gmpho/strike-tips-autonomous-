import React, { useState, useMemo } from 'react';
import { Sparkles, Brain, ChevronDown, ChevronUp, Star, BookOpen, BarChart, Target, X, Maximize2, Copy, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import type { Predictor, RaceEvent, Runner } from '../../types';

// ─── Confidence badge from prediction text ────────────────────────────────────
function extractConfidence(text: string): { label: string; color: string } | null {
  if (!text) return null;
  const t = text.toLowerCase();
  if (t.includes('strong') || t.includes('high confidence') || t.includes('prime')) {
    return { label: 'High Confidence', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25' };
  }
  if (t.includes('good') || t.includes('medium') || t.includes('moderate')) {
    return { label: 'Medium Confidence', color: 'text-amber-400 bg-amber-500/10 border-amber-500/25' };
  }
  if (t.includes('low') || t.includes('speculative') || t.includes('risky')) {
    return { label: 'Speculative', color: 'text-red-400 bg-red-500/10 border-red-500/25' };
  }
  return { label: 'AI Pick', color: 'text-purple-400 bg-purple-500/10 border-purple-500/25' };
}

// ─── Live-market cross-reference: horse name → matching runner in the Betway snapshot ──
function buildRunnerIndex(events: Record<string, RaceEvent>): Map<string, Runner> {
  const index = new Map<string, Runner>();
  Object.values(events || {}).forEach((event: RaceEvent) => {
    (event.runners || []).forEach((r) => {
      const key = r.name.trim().toLowerCase();
      if (key && !index.has(key)) index.set(key, r);
    });
  });
  return index;
}

// ─── Main Predictor View ──────────────────────────────────────────────────────
export const PredictorView: React.FC = () => {
  const store = useHUD();
  const predictions = Array.isArray(store.predictions) ? store.predictions : [];
  const runnerIndex = useMemo(() => buildRunnerIndex(store.events), [store.events]);
  const [expandAll, setExpandAll] = useState(false);
  const [selectedPrediction, setSelectedPrediction] = useState<Predictor | null>(null);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [confidenceFilter, setConfidenceFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'SPECULATIVE' | 'AI_PICK'>('ALL');
  const [limit, setLimit] = useState(15);

  const openDetail = (pred: Predictor) => {
    setSelectedPrediction(pred);
  };

  const closeDetail = () => {
    setSelectedPrediction(null);
  };

  const filteredPredictions = predictions.filter((pred) => {
    const matchesSearch = pred.horse.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (!matchesSearch) return false;
    if (confidenceFilter === 'ALL') return true;
    
    const conf = extractConfidence(pred.prediction || pred.raw || '');
    if (!conf) return confidenceFilter === 'AI_PICK';
    
    const label = conf.label;
    if (confidenceFilter === 'HIGH') return label === 'High Confidence';
    if (confidenceFilter === 'MEDIUM') return label === 'Medium Confidence';
    if (confidenceFilter === 'SPECULATIVE') return label === 'Speculative';
    if (confidenceFilter === 'AI_PICK') return label === 'AI Pick';
    return true;
  });

  const displayedPredictions = filteredPredictions.slice(0, limit);
  const runnerFor = (horse: string) => runnerIndex.get(horse.trim().toLowerCase());

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-6 h-full flex flex-col"
    >
      {/* ── Header ── */}
      <div className="shrink-0 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
              AI Predictor
            </h2>
            <p className="text-xs text-theme-secondary mt-1 font-semibold">
              Machine learning race outcome predictions — tap any card to expand analysis
            </p>
          </div>

          {/* Expand-all toggle (only when there are predictions) */}
          {predictions.length > 0 && (
            <button
              onClick={() => setExpandAll(v => !v)}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 text-[9px] font-black uppercase tracking-wider hover:bg-purple-500/20 transition-colors"
            >
              <BarChart className="w-3 h-3" />
              {expandAll ? 'Collapse All' : 'Expand All'}
            </button>
          )}
        </div>

        {/* Count badges */}
        {predictions.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-500/10 border border-purple-500/20">
              <Sparkles className="w-3 h-3 text-purple-400" />
              <span className="text-[10px] font-black text-purple-400 uppercase tracking-wider">
                {predictions.length} Predictions Loaded
              </span>
            </div>
            <p className="text-[10px] text-theme-secondary font-semibold">
              Click any card to read full AI analysis
            </p>
          </div>
        )}

        {/* Search & Filter Controls */}
        {predictions.length > 0 && (
          <div className="space-y-2">
            {/* Search Input */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search horse..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50 transition-all font-semibold"
              />
            </div>
            
            {/* Confidence Filter Row */}
            <div className="flex flex-wrap gap-1">
              {(['ALL', 'HIGH', 'MEDIUM', 'SPECULATIVE', 'AI_PICK'] as const).map((filter) => {
                const label = 
                  filter === 'ALL' ? 'All' :
                  filter === 'HIGH' ? 'High' :
                  filter === 'MEDIUM' ? 'Medium' :
                  filter === 'SPECULATIVE' ? 'Speculative' : 'AI Pick';
                
                const activeClass = 
                  filter === 'ALL' ? 'bg-white/10 text-white border-white/20' :
                  filter === 'HIGH' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
                  filter === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
                  filter === 'SPECULATIVE' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                  'bg-purple-500/20 text-purple-400 border-purple-500/30';

                const inactiveClass = 'bg-white/5 text-slate-400 border-white/5 hover:bg-white/10 hover:text-slate-200';
                
                const isSelected = confidenceFilter === filter;
                
                return (
                  <button
                    key={filter}
                    onClick={() => setConfidenceFilter(filter)}
                    className={`px-2.5 py-1.5 rounded-lg border text-[9px] font-black uppercase tracking-wider transition-all cursor-pointer ${
                      isSelected ? activeClass : inactiveClass
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Content ── */}
      {predictions.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-theme-secondary">
          <div className="p-8 rounded-3xl bg-white/5 border border-white/10 flex flex-col items-center gap-4 max-w-xs text-center">
            <Brain className="w-12 h-12 opacity-30" />
            <div className="space-y-1.5">
              <p className="text-sm font-black text-theme-primary/60">No Predictions Available</p>
              <p className="text-xs text-theme-secondary leading-relaxed">
                The AI predictor is analysing upcoming races. Predictions will appear here once processed.
              </p>
              <p className="text-[10px] text-theme-secondary/60 font-semibold mt-2">
                Data refreshes every 30 seconds
              </p>
            </div>
          </div>
        </div>
      ) : filteredPredictions.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-theme-secondary">
          <div className="p-6 rounded-3xl bg-white/5 border border-white/10 flex flex-col items-center gap-4">
            <Sparkles className="w-10 h-10 opacity-30" />
            <div className="text-center space-y-1">
              <p className="text-sm font-bold text-theme-primary/60">No Predictions Match Filters</p>
              <p className="text-xs text-theme-secondary">
                Try adjusting your search query or confidence filter
              </p>
            </div>
          </div>
        </div>
      ) : (
        /* Scrollable card list */
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar scroll-container pr-1 -mr-1">
          <div className="space-y-3 pb-2">
            {displayedPredictions.map((pred, i) => (
              <PredictionCardWrapper
                key={`${pred.horse}-${i}`}
                pred={pred}
                index={i}
                forceExpand={expandAll}
                runner={runnerFor(pred.horse)}
                onOpenDetail={openDetail}
              />
            ))}
            {filteredPredictions.length > limit && (
              <button
                onClick={() => setLimit(prev => prev + 25)}
                className="w-full py-2.5 text-[10px] font-black uppercase tracking-widest text-purple-400 bg-purple-500/5 hover:bg-purple-500/10 border border-purple-500/20 rounded-xl transition-all cursor-pointer mt-3"
              >
                Show More (+{Math.min(25, filteredPredictions.length - limit)})
              </button>
            )}
          </div>
        </div>
      )}

      {/* Footer */}
      {predictions.length > 0 && (
        <div className="shrink-0 pt-3 border-t border-theme">
          <p className="text-[10px] text-theme-secondary font-semibold">
            Predictions sourced from ATR Intelligence — updated every 30s
          </p>
        </div>
      )}

      {/* Detail Modal */}
      <PredictionDetailModal pred={selectedPrediction} runner={selectedPrediction ? runnerFor(selectedPrediction.horse) : undefined} onClose={closeDetail} />
    </motion.div>
  );
};

// ─── Live market strip (shared) ──────────────────────────────────────────────
function LiveMarketStrip({ runner, horse }: { runner?: Runner; horse: string }) {
  if (!runner) {
    return (
      <div className="p-4 rounded-2xl bg-white/5 border border-white/8 flex items-center gap-2">
        <Zap className="w-4 h-4 text-slate-500 shrink-0" />
        <p className="text-xs font-semibold text-theme-secondary">
          No live market data for <span className="font-black text-theme-primary">{horse}</span> in the current snapshot
        </p>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20">
        <p className="text-[9px] font-black text-emerald-500/70 uppercase tracking-wider mb-1">Live Odds</p>
        <p className="text-sm font-black text-emerald-400 tabular-nums">
          {(typeof runner.odds === 'number' && runner.odds > 0) ? runner.odds.toFixed(2) : (runner.odds || 'SP')}
        </p>
      </div>
      <div className="p-3 rounded-2xl bg-white/5 border border-white/8">
        <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1">Draw</p>
        <p className="text-sm font-black text-theme-primary">{typeof runner.draw === 'number' ? runner.draw : '-'}</p>
      </div>
      <div className="p-3 rounded-2xl bg-white/5 border border-white/8">
        <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1">Jockey</p>
        <p className="text-xs font-black text-theme-primary truncate">{runner.jockeyName || 'TBA'}</p>
      </div>
      <div className="p-3 rounded-2xl bg-white/5 border border-white/8">
        <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1">Star</p>
        <p className="text-sm font-black text-amber-400">
          {runner.starRating && runner.starRating > 0 ? '★'.repeat(Math.min(runner.starRating, 5)) : '-'}
        </p>
      </div>
    </div>
  );
}

// ─── Centered Detail Modal ──
function PredictionDetailModal({
  pred,
  runner,
  onClose,
}: { pred: Predictor | null; runner?: Runner; onClose: () => void }) {
  if (!pred) return null;
  const confidence = extractConfidence(pred.prediction || pred.raw || '');

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="w-full max-w-2xl max-h-[85vh] bg-theme-panel border border-purple-500/30 rounded-3xl overflow-hidden shadow-[0_0_60px_rgba(168,85,247,0.2)]"
          onClick={e => e.stopPropagation()}
        >
          {/* Modal Header */}
          <div className="flex items-start justify-between p-5 sm:p-6 border-b border-theme/50 bg-gradient-to-r from-purple-500/10 to-pink-500/10">
            <div className="flex items-start gap-4 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center shrink-0">
                <Sparkles className="w-5 h-5 text-purple-400" />
              </div>
              <div className="min-w-0">
                <h3 className="text-lg sm:text-xl font-black text-white leading-tight truncate">
                  {pred.horse}
                </h3>
                <p className="text-xs text-theme-secondary font-medium mt-1">
                  AI Prediction Analysis
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="shrink-0 p-1.5 rounded-lg bg-white/5 border border-white/10 hover:bg-red-500/10 hover:border-red-500/20 text-theme-secondary hover:text-red-400 transition-all"
              aria-label="Close detail modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Modal Content */}
          <div className="p-5 sm:p-6 overflow-y-auto max-h-[65vh] custom-scrollbar space-y-6">
            {/* Confidence Badge */}
            {confidence && (
              <div className="flex items-center gap-2">
                <Star className="w-4 h-4" style={{ color: confidence.color.split(' ')[0].replace('text-', '') }} />
                <span className={`px-3 py-1 rounded-full border text-xs font-black uppercase tracking-wider ${confidence.color}`}>
                  {confidence.label}
                </span>
              </div>
            )}

            {/* Live Market Cross-reference */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <p className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">
                  Live Market
                </p>
              </div>
              <LiveMarketStrip runner={runner} horse={pred.horse} />
            </div>

            {/* AI Assessment */}
            {pred.prediction && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Target className="w-4 h-4 text-purple-400 shrink-0" />
                  <p className="text-xs font-black text-purple-400 uppercase tracking-widest">
                    AI Assessment
                  </p>
                </div>
                <div className="bg-purple-500/5 border border-purple-500/15 rounded-2xl p-5">
                  <p className="text-base text-white/90 font-medium leading-relaxed whitespace-pre-wrap">
                    {pred.prediction}
                  </p>
                </div>
              </div>
            )}

            {/* Full Raw Analysis */}
            {pred.raw && pred.raw !== pred.prediction && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-indigo-400 shrink-0" />
                  <p className="text-xs font-black text-indigo-400 uppercase tracking-widest">
                    Full Analysis
                  </p>
                </div>
                <div className="bg-black/30 border border-white/8 rounded-2xl p-5 max-h-60 overflow-y-auto custom-scrollbar">
                  <p className="text-sm text-slate-300 font-mono leading-relaxed whitespace-pre-wrap">
                    {pred.raw}
                  </p>
                </div>
              </div>
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-4 rounded-2xl bg-white/5 border border-white/8">
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1.5">Horse</p>
                <p className="text-sm font-black text-theme-primary truncate">{pred.horse}</p>
              </div>
              <div className="p-4 rounded-2xl bg-white/5 border border-white/8">
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1.5">Signal</p>
                <div className={`inline-flex items-center gap-1.5 text-xs font-black uppercase rounded-full px-3 py-1 ${confidence?.color ?? 'text-purple-400 bg-purple-500/10 border-purple-500/25'}`}>
                  <Star className="w-3.5 h-3.5" />
                  {confidence?.label ?? 'AI Pick'}
                </div>
              </div>
              <div className="p-4 rounded-2xl bg-white/5 border border-white/8">
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1.5">Source</p>
                <p className="text-sm font-medium text-purple-400">ATR Intelligence</p>
              </div>
              <div className="p-4 rounded-2xl bg-white/5 border border-white/8">
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1.5">Updated</p>
                <p className="text-sm font-medium text-theme-secondary">Every 30s</p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-2 border-t border-theme/50">
              <button
                onClick={() => navigator.clipboard.writeText(pred.raw || pred.prediction || '')}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-theme-secondary hover:text-theme-primary hover:bg-white/10 transition-all"
              >
                <Copy className="w-4 h-4" />
                Copy Raw
              </button>
              <button
                onClick={onClose}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 text-white font-black text-xs uppercase tracking-wider hover:bg-purple-500 transition-all"
              >
                <Maximize2 className="w-4 h-4" />
                Close
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ─── Wrapper that supports forceExpand from parent ────────────────────────────
function PredictionCardWrapper({
  pred,
  index,
  forceExpand,
  runner,
  onOpenDetail,
}: {
  pred: Predictor;
  index: number;
  forceExpand: boolean;
  runner?: Runner;
  onOpenDetail: (pred: Predictor) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const expanded = forceExpand || isExpanded;
  const confidence = extractConfidence(pred.prediction || pred.raw || '');

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl bg-theme-panel border border-theme sidebar-card overflow-hidden group hover:border-purple-500/40 transition-all duration-200"
    >
      {/* Clickable Header */}
      <button
        onClick={() => setIsExpanded(prev => !prev)}
        className="w-full text-left p-4 sm:p-5 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/50 hover:bg-white/5 transition-colors duration-150"
        aria-expanded={expanded}
        aria-label={`${expanded ? 'Collapse' : 'Expand'} prediction for ${pred.horse}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <div className="w-7 h-7 rounded-lg bg-purple-500/15 border border-purple-500/25 flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-[10px] font-black text-purple-400">{index + 1}</span>
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-base font-black text-theme-primary group-hover:text-purple-300 transition-colors leading-snug truncate">
                {pred.horse}
              </h3>
              {runner && (
                <p className="flex items-center gap-1.5 mt-1 text-[10px] font-bold tabular-nums">
                  <Zap className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
                  <span className="text-emerald-400">
                    {(typeof runner.odds === 'number' && runner.odds > 0) ? runner.odds.toFixed(2) : (runner.odds || 'SP')}
                  </span>
                  <span className="text-theme-secondary">
                    {typeof runner.draw === 'number' && <span className="mr-1">D{runner.draw}</span>}
                    {runner.jockeyName && <span className="truncate max-w-[100px]">{runner.jockeyName}</span>}
                  </span>
                  {runner.starRating ? <span className="text-amber-400">{'★'.repeat(Math.min(runner.starRating, 5))}</span> : null}
                </p>
              )}
              {pred.prediction && (
                <p className="text-xs text-theme-secondary font-medium leading-snug mt-1 line-clamp-2">
                  {pred.prediction}
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            {confidence && (
              <span className={`px-2 py-0.5 rounded-full border text-[9px] font-black uppercase tracking-wider ${confidence.color}`}>
                {confidence.label}
              </span>
            )}
            <div className="flex flex-col items-end gap-1.5">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenDetail(pred);
                }}
                className="p-1.5 rounded-lg bg-white/5 border border-white/10 hover:bg-purple-500/10 hover:border-purple-500/20 text-theme-secondary hover:text-purple-400 transition-all"
                aria-label={`View full details for ${pred.horse}`}
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
              <div className="p-1 rounded-lg bg-white/5 border border-white/10 group-hover:bg-purple-500/10 group-hover:border-purple-500/20 transition-colors">
                {expanded
                  ? <ChevronUp className="w-3.5 h-3.5 text-purple-400" />
                  : <ChevronDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-purple-400 transition-colors" />
                }
              </div>
            </div>
          </div>
        </div>
      </button>

      {/* Expandable Panel */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-theme/50 px-4 sm:px-5 py-4 space-y-4">

              {pred.prediction && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5">
                    <Target className="w-3 h-3 text-purple-400 shrink-0" />
                    <p className="text-[9px] font-black text-purple-400 uppercase tracking-widest">
                      AI Assessment
                    </p>
                  </div>
                  <div className="bg-purple-500/5 border border-purple-500/15 rounded-xl p-3">
                    <p className="text-sm text-white/80 font-medium leading-relaxed">
                      {pred.prediction}
                    </p>
                  </div>
                </div>
              )}

              {pred.raw && pred.raw !== pred.prediction && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="w-3 h-3 text-indigo-400 shrink-0" />
                    <p className="text-[9px] font-black text-indigo-400 uppercase tracking-widest">
                      Full Analysis
                    </p>
                  </div>
                  <div className="bg-black/30 border border-white/8 rounded-xl p-3 max-h-44 overflow-y-auto custom-scrollbar">
                    <p className="text-xs text-slate-300 font-mono leading-relaxed whitespace-pre-wrap">
                      {pred.raw}
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-xl bg-white/5 border border-white/8">
                  <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1">Horse</p>
                  <p className="text-xs font-black text-theme-primary truncate">{pred.horse}</p>
                </div>
                <div className="p-2.5 rounded-xl bg-white/5 border border-white/8">
                  <p className="text-[9px] font-black text-slate-500 uppercase tracking-wider mb-1">Signal</p>
                  <div className={`inline-flex items-center gap-1 text-[9px] font-black uppercase rounded-full px-2 py-0.5 ${confidence?.color ?? ''}`}>
                    <Star className="w-2.5 h-2.5" />
                    {confidence?.label ?? 'AI Pick'}
                  </div>
                </div>
              </div>

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
