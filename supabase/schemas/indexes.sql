-- Indexes: every FK + RLS predicate column indexed; partial index keeps
-- OPEN-bet lookups (settlement scans) off the settled history.

create index if not exists bankroll_snapshots_user_time_idx
  on public.bankroll_snapshots (user_id, recorded_at desc);

create index if not exists ledger_epochs_user_idx
  on public.ledger_epochs (user_id);

create index if not exists bets_user_idx on public.bets (user_id);
create index if not exists bets_open_idx on public.bets (user_id)
  where status = 'OPEN';

create index if not exists settlements_bet_idx on public.settlements (bet_id);

create index if not exists exotics_user_idx on public.exotics (user_id);

create index if not exists telegram_links_user_idx
  on public.telegram_links (user_id);
create index if not exists telegram_links_chat_idx
  on public.telegram_links (telegram_chat_id)
  where telegram_chat_id is not null;
