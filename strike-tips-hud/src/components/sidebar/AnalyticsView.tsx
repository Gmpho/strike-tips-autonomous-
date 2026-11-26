import React, { Suspense } from 'react';
import { TrendingUp, Activity, Target, BarChart2, Layers, AlertTriangle, ShieldCheck } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import type { BookStats, BookTracks, RankedTrack } from '../../types';
import { settledBets as toSettled, isPoolTicket } from '../../lib/analytics';
import type { BetLike } from '../../lib/analytics';

// ApexCharts suite ships in its own on-demand chunk (treeshaken core +
// 7 types) so the dashboard first paint never pays for it. Loaded inside
// ApexSuite below via dynamic import.

function ChartSkeleton() {
  return (
    <div className="p-6 rounded-2xl bg-theme-panel border border-theme animate-pulse">
      <div className="h-3 w-40 rounded bg-white/10 mb-4" />
      <div className="h-56 rounded-xl bg-white/5" />
    </div>
  );
}

const fmtR = (v: number | undefined | null) =>
  v == null ? '—' : `R${Number(v).toLocaleString('en-ZA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const fmtDay = (value: string | null | undefined) =>
  value ? new Date(`${String(value).slice(0, 10)}T12:00:00`).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';

const signed = (v: number | undefined | null, digits = 1) =>
  `${Number(v ?? 0) >= 0 ? '+' : ''}${Number(v ?? 0).toFixed(digits)}`;

interface Kpi {
  label: string;
  value: string;
  icon: typeof TrendingUp;
  color: string;
  sub?: string;
}

/** One book's KPI row. Real and paper are never averaged into a third set. */
function bookKpis(stats: BookStats | undefined): Kpi[] {
  if (!stats) return [];
  return [
    {
      label: 'WIN RATE',
      value: `${Number(stats.winRate ?? 0).toFixed(1)}%`,
      icon: TrendingUp,
      color: 'text-emerald-500',
      sub: `${stats.wins} won · ${stats.losses} lost`,
    },
    {
      label: 'PROVEN WINS',
      value: `${stats.provenWins ?? stats.wins}`,
      icon: ShieldCheck,
      color: 'text-emerald-400',
      sub: Number(stats.unprovenWins ?? 0) > 0
        ? `${stats.unprovenWins} settled as WON without a stake or payout — unproven`
        : `${stats.provenLosses ?? stats.losses} proven losses`,
    },
    {
      label: 'SETTLED',
      value: `${stats.settledBets}`,
      icon: BarChart2,
      color: 'text-blue-500',
      sub: `${Number(stats.settlementRate ?? 0).toFixed(1)}% of ${stats.totalBets} tickets`,
    },
    {
      label: 'UNRESOLVED',
      value: `${Number(stats.unresolvedShare ?? 0).toFixed(1)}%`,
      icon: AlertTriangle,
      color: Number(stats.unresolvedShare ?? 0) >= 50 ? 'text-amber-500' : 'text-slate-400',
      sub: `${stats.unresolved ?? 0} expired without a result`,
    },
    {
      label: 'STAKED',
      value: fmtR(stats.stakeTotal),
      icon: Layers,
      color: 'text-amber-500',
      sub: `avg ${fmtR(stats.avgStake)} per settled ticket`,
    },
    {
      label: 'ROI',
      value: `${signed(stats.roi)}%`,
      icon: Target,
      color: Number(stats.roi) >= 0 ? 'text-emerald-500' : 'text-red-500',
      sub: `settled tickets only · ${fmtR(stats.payoutTotal)} returned`,
    },
    {
      label: 'LAST SETTLED',
      value: fmtDay(stats.lastSettled),
      icon: Activity,
      color: 'text-cyan-500',
      sub: 'no settlement since this date',
    },
  ];
}

function KpiGrid({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
      {kpis.map((stat, i) => (
        <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme group hover:border-theme-primary transition-colors">
          <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
          <div className="text-xl font-black text-theme-primary mb-0.5 tabular">{stat.value}</div>
          <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          {stat.sub && (
            <div className="text-[9px] text-theme-secondary/70 font-bold mt-1 normal-case">{stat.sub}</div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Best/worst card. Shows the capped number, then what the raw number was. */
function TrackCard({ label, track, tone }: { label: string; track: RankedTrack; tone: 'good' | 'bad' }) {
  const capped = track.roiCapped ?? track.roi;
  const cappedUp = capped >= 0;
  const border = tone === 'good' ? 'border-emerald-500/20' : 'border-red-500/20';
  const color = cappedUp ? 'text-emerald-400' : 'text-red-400';
  return (
    <div className={`p-4 rounded-2xl bg-theme-panel border ${border}`}>
      <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">{label}</div>
      <div className="text-theme-primary font-black">{track.name}</div>
      <div className={`font-black tabular ${color}`}>{signed(capped)}% ROI</div>
      <div className="text-[9px] text-theme-secondary/70 font-bold mt-1">
        {track.n} settled · capped at {track.cap ?? 10}× stake
        {lastRun(track.lastSeen) ? ` · last ${lastRun(track.lastSeen)}` : ''}
      </div>
      {Math.abs(track.roi - capped) >= 1 && (
        <div className="text-[9px] text-theme-secondary/60 font-bold mt-0.5">
          uncapped reads {signed(track.roi)}%
          {track.topShare != null ? ` · one ticket = ${Number(track.topShare).toFixed(0)}% of returns` : ''}
        </div>
      )}
    </div>
  );
}

function lastRun(value: string | null | undefined) {
  return value ? new Date(`${String(value).slice(0, 10)}T12:00:00`).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short' }) : null;
}

/** Every settled track, ranked on the capped ROI (one jackpot can't win this). */
function TrackTable({ books, note }: { books: BookTracks; note: string }) {
  const rows = Object.entries(books.trackStats || {})
    .map(([name, row]) => ({ name, ...row }))
    .sort((a, b) => (b.roiCapped ?? b.roi) - (a.roiCapped ?? a.roi));
  if (rows.length === 0) return null;
  return (
    <div className="p-4 sm:p-6 rounded-2xl bg-theme-panel border border-theme">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">Track Ledger</h3>
        <span className="text-[10px] font-black text-theme-secondary">{note}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-theme-secondary">
              <th className="text-left py-2 pr-3 font-black">Track</th>
              <th className="text-right py-2 px-2 font-black">Settled</th>
              <th className="text-right py-2 px-2 font-black">Capped ROI</th>
              <th className="text-right py-2 px-2 font-black">Uncapped</th>
              <th className="text-right py-2 px-2 font-black">Top ticket</th>
              <th className="text-right py-2 pl-2 font-black">Last run</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const capped = r.roiCapped ?? r.roi;
              const top = r.topTicket;
              return (
                <tr key={r.name} className="border-t border-theme">
                  <td className="py-2 pr-3 font-bold text-theme-primary whitespace-nowrap">
                    {r.name}
                    {!r.eligible && <span className="ml-1 text-[9px] text-theme-secondary/60 font-bold">(under sample)</span>}
                  </td>
                  <td className="py-2 px-2 text-right tabular text-theme-secondary">{r.n}</td>
                  <td className={`py-2 px-2 text-right tabular font-black ${capped >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {signed(capped)}%
                  </td>
                  <td className="py-2 px-2 text-right tabular text-theme-secondary">{signed(r.roi)}%</td>
                  <td className="py-2 px-2 text-right tabular text-theme-secondary">
                    {top && r.topShare != null ? `${Number(r.topShare).toFixed(0)}%` : '—'}
                  </td>
                  <td className="py-2 pl-2 text-right tabular text-theme-secondary">{lastRun(r.lastSeen) ?? '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[10px] leading-relaxed text-theme-secondary">
        Capped ROI counts each ticket's return at most {books.cap ?? 10}× its stake — the number the
        track ranking uses. A track above shows how much of its raw return came from a single pool
        dividend under “top ticket”. Minimum sample {books.minSample ?? 20} settled, last run within{' '}
        {books.recencyDays ?? 90} days.
      </p>
    </div>
  );
}

export const AnalyticsView: React.FC = () => {
  const { learning, betStats, bankrollHistory, betHistory } = useHUD();

  const real = betStats?.books?.real;
  const paper = betStats?.books?.paper;
  // Backend not yet redeployed: the payload has no per-book split. Say so
  // instead of quietly showing a blended number as if it were a book.
  const hasBooks = Boolean(real && paper);

  const paperTracks: BookTracks | undefined = learning?.books?.paper;
  const realTracks: BookTracks | undefined = learning?.books?.real;
  const calibration = learning?.calibration;

  const paperBets = React.useMemo(
    () => (betHistory || []).filter((b) => b.is_paper === true),
    [betHistory],
  );
  const paperSettled = React.useMemo(
    () => paperBets.filter((b) => b.settled).length,
    [paperBets],
  );

  // The four insight charts are all-time aggregates: with ~1,300 settled
  // tickets, a day's new results barely moves a rounded ROI, so the page
  // looks frozen for weeks. Default them to a rolling 7-day window while
  // keeping an explicit all-time option. No data is invented or re-scoped.
  const [chartWindow, setChartWindow] = React.useState<'7d' | 'all'>('7d');
  const scopedBets = React.useMemo(() => {
    if (chartWindow === 'all') return paperBets;
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    return paperBets.filter((b) => {
      const t = Date.parse(String(b.placedAt || ''));
      return Number.isFinite(t) && t >= cutoff;
    });
  }, [paperBets, chartWindow]);
  const windowNote = chartWindow === '7d' ? 'last 7 days' : 'all time';
  const recentWinRate = React.useMemo(() => {
    const market = toSettled(scopedBets).filter((b) => !isPoolTicket(b));
    const n = market.length;
    return {
      n,
      actual: n ? (market.filter((b) => b.won).length / n) * 100 : 0,
      implied: n ? market.reduce((s, b) => s + (b.odds > 0 ? 100 / b.odds : 0), 0) / n : 0,
    };
  }, [scopedBets]);

  const openExposure = (betHistory || [])
    .filter((b) => String(b.status || '').toUpperCase() === 'PENDING')
    .reduce((s, b) => s + (Number(b.stake) || 0), 0);

  const realTracksWithSample = realTracks
    ? Object.entries(realTracks.trackStats || {})
        .map(([name, row]) => ({ name, ...row }))
        .sort((a, b) => b.n - a.n)[0]
    : undefined;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-3.5 sm:p-6 space-y-5 sm:space-y-8 w-full"
    >
      <div>
        <h2 className="text-xl sm:text-2xl font-bold bg-linear-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          Intelligence Analytics
        </h2>
        <p className="text-[10px] sm:text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          Real money first · paper simulation below · never averaged
        </p>
      </div>

      {!hasBooks && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200/90">
          Per-book split unavailable from the API (the backend has not been redeployed). Win rate and
          ROI on this page are the blended ledger — treat them as provisional.
        </div>
      )}

      {/* ── Ledger record: the number that reconciles with the bankroll ──
          One line, both books, so the headline wins/losses can never be read
          as a single book's. The book sections below sum to this line. */}
      <div className="p-4 sm:p-5 rounded-2xl bg-theme-panel border border-theme space-y-2">
        <div className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">
          Ledger record · both books
        </div>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm font-black text-theme-primary">
          <span>{Number(betStats?.settledBets ?? 0).toLocaleString()} settled</span>
          <span className="text-emerald-400">{betStats?.wins ?? 0} won</span>
          <span className="text-red-400">{betStats?.losses ?? 0} lost</span>
          <span className="text-theme-secondary font-bold">{betStats?.voidBets ?? 0} void</span>
          <span className="text-theme-secondary font-bold">{betStats?.expiredBets ?? 0} expired</span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-bold text-theme-secondary">
          <span>
            real: {real?.wins ?? 0} won · {real?.losses ?? 0} lost
          </span>
          <span>
            paper: {paper?.wins ?? 0} won · {paper?.losses ?? 0} lost
          </span>
          <span className="text-theme-secondary/70">
            the two books above add up to this line — they are never averaged
          </span>
        </div>
      </div>

      {/* ── Real money ─────────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-black uppercase tracking-widest text-theme-primary">Real money</h3>
        </div>

        {real && real.losses === 0 && real.settledBets > 0 && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-200/90">
            <div className="font-black text-amber-300 mb-1 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" /> Provisional — not a measured record
            </div>
            All {real.settledBets} settled real tickets won and {real.expiredBets} of{' '}
            {(real.settledBets + real.expiredBets).toLocaleString()} real tickets expired with no result
            ({Number(real.unresolvedShare ?? 0).toFixed(1)}% unresolved). A 100% win rate here is missing
            data, not skill: the losses were never recorded. Last real settlement {fmtDay(real.lastSettled)}.
            {Number(real.unprovenWins ?? 0) > 0 && (
              <>
                {' '}
                {real.unprovenWins} of those {real.settledBets} "wins" carry no stake and no payout, so
                they are unproven and are excluded from the PROVEN WINS tile.
              </>
            )}
          </div>
        )}

        <KpiGrid kpis={bookKpis(real)} />

        {realTracks && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {realTracks.bestTrack && realTracks.worstTrack ? (
              <>
                <TrackCard label="Best real track" track={realTracks.bestTrack} tone="good" />
                <TrackCard label="Worst real track" track={realTracks.worstTrack} tone="bad" />
              </>
            ) : (
              <div className="sm:col-span-2 p-4 rounded-2xl bg-theme-panel border border-theme text-[11px] text-theme-secondary leading-relaxed">
                No real track qualifies for a ranking yet: the gate is {realTracks.minSample ?? 20}{' '}
                settled tickets inside {realTracks.recencyDays ?? 90} days.
                {realTracksWithSample
                  ? ` The largest real sample is ${realTracksWithSample.name} with ${realTracksWithSample.n} settled and last run ${lastRun(realTracksWithSample.lastSeen) ?? 'unknown'} — not enough to name a best or worst track.`
                  : ' No real track has a settled ticket yet.'}
              </div>
            )}
          </div>
        )}

        {realTracks && (realTracks.bestTrack || realTracksWithSample) && (
          <TrackTable books={realTracks} note="real money · capped ranking" />
        )}
      </section>

      <Suspense fallback={<ChartSkeleton />}>
        <ApexSuite.Equity history={bankrollHistory} />
      </Suspense>

      {/* ── Paper simulation ───────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-black uppercase tracking-widest text-theme-primary">Paper simulation</h3>
          <span className="text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300">
            {paper?.settledBets ?? paperSettled} settled · not real money
          </span>
        </div>
        <p className="text-[11px] text-theme-secondary leading-relaxed max-w-3xl">
          The simulator is where the volume is: {paper?.settledBets ?? 0} settled tickets,{' '}
          {paper?.wins ?? 0} won and {paper?.losses ?? 0} lost. Its ROI is carried by pool dividends,
          so the sections below show the median ticket, the capped track ranking, and the pool book
          separately. Real money is the record above; this is the laboratory.
        </p>

        <KpiGrid kpis={bookKpis(paper)} />

        {paperTracks && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {paperTracks.bestTrack && <TrackCard label="Best paper track (capped)" track={paperTracks.bestTrack} tone="good" />}
            {paperTracks.worstTrack && <TrackCard label="Worst paper track (capped)" track={paperTracks.worstTrack} tone="bad" />}
          </div>
        )}

        {paperTracks && <TrackTable books={paperTracks} note="paper · capped ranking" />}

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] uppercase tracking-widest text-theme-secondary font-black">Insight window</span>
          {(['7d', 'all'] as const).map((w) => (
            <button
              key={w}
              onClick={() => setChartWindow(w)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold transition-colors ${
                chartWindow === w
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-theme-panel border border-theme text-theme-secondary'
              }`}
            >
              {w === '7d' ? 'Last 7 days' : 'All time'}
            </button>
          ))}
          <span className="text-[10px] text-theme-secondary/70">
            {scopedBets.filter((b) => b.settled).length.toLocaleString()} settled paper tickets · {windowNote}
          </span>
        </div>

        <Suspense fallback={<><ChartSkeleton /><ChartSkeleton /></>}>
          <ApexSuite.Paper
            bets={scopedBets}
            stats={paper}
            tracks={paperTracks}
            windowNote={windowNote}
          />
        </Suspense>
      </section>

      {/* ── Learning insights ──────────────────────────────────── */}
      <div className="p-6 rounded-2xl bg-theme-panel border border-theme group hover:border-emerald-500/30 transition-all duration-500">
        <div className="flex items-center gap-3 mb-4">
          <Target className="w-4 h-4 text-blue-500" />
          <h3 className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">
            Learning Engine Insights
          </h3>
        </div>
        <div className="space-y-2 text-sm text-theme-secondary leading-relaxed font-bold group-hover:text-theme-primary transition-colors">
          <p>
            Recent paper calibration ({windowNote}):{' '}
            <span className={recentWinRate.actual >= recentWinRate.implied ? 'text-emerald-500' : 'text-red-400'}>
              {signed(recentWinRate.actual - recentWinRate.implied)}pp
            </span>
            {' actual vs implied across '}
            <span className="text-theme-primary">{recentWinRate.n}</span>
            {' settled win-market tickets.'}
          </p>
          <p>
            Paper calibration (all time):{' '}
            <span className={Number(calibration?.books?.paper?.accuracy ?? 0) >= 0 ? 'text-emerald-500' : 'text-red-400'}>
              {signed(calibration?.books?.paper?.accuracy)}%
            </span>
            {' actual vs implied across '}
            <span className="text-theme-primary">{calibration?.books?.paper?.samples ?? paper?.settledBets ?? 0}</span>
            {' settled paper tickets'}
            {calibration?.books?.paper
              ? ` (${Number(calibration.books.paper.actualWinRate).toFixed(1)}% actual, ${Number(calibration.books.paper.impliedWinRate).toFixed(1)}% implied).`
              : '.'}
          </p>
          <p>
            Real calibration:{' '}
            <span className="text-theme-primary">
              {calibration?.books?.real ? `${signed(calibration.books.real.accuracy)}pp` : '—'}
            </span>
            {calibration?.books?.real
              ? ` across ${calibration.books.real.samples} settled real tickets. With ${real?.losses ?? 0} recorded losses this figure cannot be read as an edge — it is the size of the missing results.`
              : ' — no settled real sample.'}
          </p>
          <p>
            Best settled track:{' '}
            <span className="text-emerald-500">{paperTracks?.bestTrack?.name ?? 'N/A'}</span>
            {paperTracks?.bestTrack
              ? ` (${signed(paperTracks.bestTrack.roiCapped ?? paperTracks.bestTrack.roi)}% capped ROI, ${paperTracks.bestTrack.n} settled, last run ${lastRun(paperTracks.bestTrack.lastSeen) ?? 'unknown'})`
              : ''}
            {`, minimum ${paperTracks?.minSample ?? 20} settled within ${paperTracks?.recencyDays ?? 90} days.`}
          </p>
          {paper?.roiIncludingExpired != null && (
            <p className="text-theme-secondary/80">
              Disclosure, not a stress test: expired tickets are refunds. Counting them as losses would
              put paper ROI at {signed(paper.roiIncludingExpired)}% instead of {signed(paper.roi)}%. The
              expired stake is small next to the settled book, so this changes the story less than it
              appears to.
            </p>
          )}
          <p className="text-theme-secondary/80">
            {betHistory.length.toLocaleString()} ledger rows loaded · {fmtR(openExposure)} currently
            pending (stake not yet at risk). Nothing here is settled until a result is proven.
          </p>
        </div>
      </div>
    </motion.div>
  );
};

// ── Lazy chart chunks ─────────────────────────────────────────────
// Two explicit dynamic-import boundaries so the KPI paint never waits for
// ApexCharts and each section loads its own chart module.
type ChartsModule = typeof import('../analytics/AnalyticsCharts');

function useChartsModule() {
  const [Charts, setCharts] = React.useState<ChartsModule | null>(null);
  React.useEffect(() => {
    let live = true;
    import('../analytics/AnalyticsCharts').then((m) => {
      if (live) setCharts(m);
    });
    return () => {
      live = false;
    };
  }, []);
  return Charts;
}

const Equity = ({ history }: { history: { t: string; balance: number }[] }) => {
  const Charts = useChartsModule();
  if (!Charts) return <ChartSkeleton />;
  return <Charts.EquityChart history={history} />;
};

const Paper = ({
  bets,
  stats,
  tracks,
  windowNote,
}: {
  bets: BetLike[];
  stats: BookStats | undefined;
  tracks: BookTracks | undefined;
  windowNote: string;
}) => {
  const Charts = useChartsModule();
  if (!Charts) return <><ChartSkeleton /><ChartSkeleton /></>;
  const capped = tracks?.roiCappedByTrack ?? {};
  return (
    <div className="space-y-5 sm:space-y-8">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 sm:gap-8">
        <Charts.TrackRoiChart
          roiByTrack={capped}
          title="ROI by Track · capped"
          note={`each ticket ≤ ${tracks?.cap ?? 10}× stake`}
        />
        <Charts.WinLossDonut
          wins={stats?.wins ?? 0}
          losses={stats?.losses ?? 0}
          title="Win / Loss · paper"
          note={`${stats?.settledBets ?? 0} settled`}
        />
      </div>
      <Charts.ExoticsTable bets={bets} />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 sm:gap-8">
        <Charts.BracketChart
          bets={bets}
          winMarketOnly
          title={`ROI by Odds Bracket · win market (${windowNote})`}
        />
        <Charts.PnlHistogram bets={bets} />
      </div>
      <Charts.RoiHeatmap bets={bets} title={`ROI Heatmap · Track × Odds (median) · ${windowNote}`} />
      <Charts.DailyPnlChart bets={bets} />
    </div>
  );
};

const ApexSuite = { Equity, Paper };
