import React, { useEffect, useState } from 'react';
import { Newspaper, ExternalLink, Clock, Loader2, RefreshCw, Brain } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import { dataBridge } from '../../engine/data-bridge';
import { useSentiment, type SentimentResult } from '../../hooks/useSentiment';
import { OFFLINE_MODELS } from '../../lib/offline-models';
import type { NewsItem } from '../../types';

function formatRelativeTime(published: string): string {
  if (!published) return 'Unknown time';
  try {
    const date = new Date(published);
    if (isNaN(date.getTime())) return published;
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return published;
  }
}

function cleanSummary(text: string): string {
  if (!text) return '';
  try {
    // Guardian RSS embeds HTML (<ul><li>...) in summaries; DOMParser strips
    // tags and decodes entities in one pass.
    const doc = new DOMParser().parseFromString(text, 'text/html');
    return (doc.body.textContent || '').replace(/\s+/g, ' ').trim();
  } catch {
    return text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  }
}

function SentimentBadge({ result }: { result: SentimentResult }) {
  const weak = result.score < 0.6;
  const cls = weak
    ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
    : result.label === 'POSITIVE'
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
      : 'bg-red-500/10 text-red-400 border-red-500/25';
  const text = weak ? 'NEUTRAL' : result.label;
  return (
    <span
      title={`On-device mood score ${(result.score * 100).toFixed(0)}% — computed on your phone, nothing uploaded`}
      className={`px-2 py-0.5 text-[8px] font-black rounded border uppercase shrink-0 ${cls}`}
    >
      {text}
    </span>
  );
}

function NewsCard({
  item,
  analyze,
}: {
  item: NewsItem;
  analyze: (text: string) => Promise<SentimentResult | null>;
}) {
  const [imgError, setImgError] = useState(false);
  const [sentiment, setSentiment] = useState<SentimentResult | null>(null);
  const imgUrl = item.image_url ? `/api/news/images?url=${encodeURIComponent(item.image_url)}` : null;

  useEffect(() => {
    let live = true;
    analyze(`${item.title}. ${item.summary ?? ''}`).then((r) => {
      if (live) setSentiment(r);
    });
    return () => {
      live = false;
    };
  }, [item.id, item.title, item.summary, analyze]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="group rounded-2xl bg-theme-panel border border-theme sidebar-card overflow-hidden hover:border-purple-500/40 transition-all duration-200"
    >
      {imgUrl && !imgError && (
        <div className="relative h-40 bg-white/5 overflow-hidden">
          <img
            src={imgUrl}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        </div>
      )}
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <span className="px-2 py-0.5 text-[8px] font-black rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 uppercase shrink-0">
              {item.source}
            </span>
            {item.region && (
              <span className="px-2 py-0.5 text-[8px] font-black rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 uppercase shrink-0">
                {item.region}
              </span>
            )}
            {sentiment && <SentimentBadge result={sentiment} />}
          </div>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 p-1.5 rounded-lg bg-white/5 border border-white/10 hover:bg-purple-500/10 hover:border-purple-500/20 text-theme-secondary hover:text-purple-400 transition-all"
            aria-label={`Read full article: ${item.title}`}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
        <h3 className="text-sm font-black text-theme-primary leading-snug group-hover:text-purple-300 transition-colors">
          {item.title}
        </h3>
        {item.summary && (
          <p className="text-[10px] text-theme-secondary leading-snug line-clamp-3">
            {cleanSummary(item.summary)}
          </p>
        )}
        <div className="flex items-center gap-2 pt-2 border-t border-theme/30">
          <Clock className="w-3 h-3 text-theme-secondary/50 shrink-0" />
          <span className="text-[9px] font-bold text-theme-secondary uppercase tracking-wider">
            {formatRelativeTime(item.published)}
          </span>
        </div>
      </div>
    </motion.div>
  );
}

export const NewsView: React.FC = () => {
  const { news } = useHUD();
  const [isLoading, setIsLoading] = useState(news.length === 0);
  const sentiment = useSentiment();

  // DataBridge hydrates the store via REST + SSE 'news' events.
  // Stop spinning once data lands, or after a safety timeout.
  useEffect(() => {
    if (news.length > 0) setIsLoading(false);
  }, [news.length]);

  useEffect(() => {
    const timer = window.setTimeout(() => setIsLoading(false), 8000);
    return () => window.clearTimeout(timer);
  }, []);

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="p-6 space-y-6 h-full flex flex-col"
      >
        <div className="shrink-0">
          <h2 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            Racing News
          </h2>
          <p className="text-xs text-theme-secondary mt-1 font-semibold">
            Live from BBC, Guardian, Mirror — zero-cost, real-time
          </p>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <Loader2 className="w-10 h-10 text-cyan-400 animate-spin mx-auto" />
            <p className="text-sm font-semibold text-theme-secondary">Loading latest racing news…</p>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-3.5 sm:p-6 space-y-4 sm:space-y-6 w-full flex flex-col min-h-0"
    >
      <div className="shrink-0 space-y-3 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            Racing News
          </h2>
          <p className="text-xs text-theme-secondary mt-1 font-semibold">
            Live from BBC, Guardian, Mirror — zero-cost, real-time
          </p>
        </div>
        <button
          onClick={async () => {
            setIsLoading(true);
            await dataBridge.refreshNews();
            setIsLoading(false);
          }}
          disabled={isLoading}
          className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 border border-white/10 text-theme-secondary hover:bg-white/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span className="text-[9px] font-black uppercase tracking-wider">Refresh</span>
        </button>
      </div>

      {!sentiment.enabled && (
        <div className="shrink-0 flex items-center gap-2.5 p-3 rounded-2xl bg-white/[0.03] border border-white/10">
          <Brain className="w-4 h-4 text-purple-400 shrink-0" />
          <p className="text-[10px] text-theme-secondary font-semibold flex-1 leading-snug">
            On-device mood tags ({OFFLINE_MODELS.sentiment.blurb})
            {sentiment.downloading && (
              <span className="block text-purple-300 font-bold mt-0.5">
                Downloading {Math.round(sentiment.progress * 100)}% — {sentiment.progressText}
              </span>
            )}
            {sentiment.deniedReason && (
              <span className="block text-red-400 font-bold mt-0.5">{sentiment.deniedReason}</span>
            )}
          </p>
          <button
            onClick={() => void sentiment.enable()}
            disabled={sentiment.downloading}
            className="shrink-0 px-3 py-1.5 rounded-xl bg-purple-500/20 border border-purple-500/30 text-purple-300 text-[9px] font-black uppercase tracking-wider hover:bg-purple-500/30 transition-all disabled:opacity-50"
          >
            {sentiment.downloading ? 'Loading…' : 'Enable'}
          </button>
        </div>
      )}

      {news.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-theme-secondary">
          <div className="p-8 rounded-3xl bg-white/5 border border-white/10 flex flex-col items-center gap-4 max-w-xs text-center">
            <Newspaper className="w-14 h-14 opacity-30" />
            <div className="space-y-1.5">
              <p className="text-sm font-black text-theme-primary/60">No News Yet</p>
              <p className="text-xs text-theme-secondary leading-relaxed">
                Free feeds are being polled. News will appear here shortly.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar scroll-container pr-1 -mr-1">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {news.map((item) => (
              <NewsCard key={item.id} item={item} analyze={sentiment.analyze} />
            ))}
          </div>
        </div>
      )}

      <div className="shrink-0 pt-3 border-t border-theme">
        <p className="text-[10px] text-theme-secondary font-semibold">
          {news.length} articles — BBC Sport, The Guardian, Daily Mirror (RSS, no API keys)
        </p>
      </div>
    </motion.div>
  );
};