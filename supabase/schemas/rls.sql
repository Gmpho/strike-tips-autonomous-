-- RLS: every table locked to its owner.
-- (select auth.uid()) form: evaluated once per query, not per row.
-- Service role bypasses RLS (crons/settlement); HUD uses publishable key.

alter table public.profiles enable row level security;
alter table public.ledger_epochs enable row level security;
alter table public.bankroll_snapshots enable row level security;
alter table public.bets enable row level security;
alter table public.settlements enable row level security;
alter table public.exotics enable row level security;
alter table public.telegram_links enable row level security;

-- Profiles: users read/update only their own row.
create policy "own profile only" on public.profiles for all
  to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

-- Owner-scoped tables: one pattern, USING + WITH CHECK.
create policy "own epochs only" on public.ledger_epochs for all
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "own snapshots only" on public.bankroll_snapshots for all
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "own bets only" on public.bets for all
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "own exotics only" on public.exotics for all
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "own links only" on public.telegram_links for all
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- Settlements inherit ownership via the parent bet (indexed lookup,
-- not a per-row auth call on a joined table the client can't see).
create policy "own settlements only" on public.settlements for all
  to authenticated
  using (exists (
    select 1 from public.bets b
    where b.id = settlements.bet_id and b.user_id = (select auth.uid())
  ))
  with check (exists (
    select 1 from public.bets b
    where b.id = settlements.bet_id and b.user_id = (select auth.uid())
  ));
