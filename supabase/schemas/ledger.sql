-- Strike Tips ledger schema (declarative).
-- Conventions: lowercase identifiers, identity PKs, numeric money,
-- FK cascade to profiles, unique(user_id, ref) for idempotent imports.

-- Profiles: app mirror of auth.users (auth is the source of truth).
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  telegram_chat_id bigint unique,
  telegram_username text,
  display_name text,
  created_at timestamptz not null default now()
);

-- Ledger epochs: a "start fresh" writes a new opening row; history is
-- never deleted. Live P&L computes from the latest epoch forward.
create table if not exists public.ledger_epochs (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  opening_balance numeric(12, 2) not null,
  note text not null default '',
  started_at timestamptz not null default now()
);

create table if not exists public.bankroll_snapshots (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  balance numeric(12, 2) not null,
  peak numeric(12, 2) not null,
  total_pnl numeric(12, 2) not null,
  drawdown_pct numeric(6, 3) not null,
  paper_balance numeric(12, 2),
  recorded_at timestamptz not null default now()
);

create table if not exists public.bets (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  ref text not null,
  track text not null,
  race_number integer not null,
  horse text not null,
  odds numeric(10, 2) not null,
  stake numeric(10, 2) not null,
  edge numeric(7, 3),
  confidence text,
  status text not null default 'OPEN'
    check (status in ('OPEN', 'WON', 'LOST', 'VOID')),
  placed_at timestamptz not null default now(),
  settled_at timestamptz,
  returned numeric(10, 2),
  -- paper and real share the ref namespace; uniqueness covers the flag.
  is_paper boolean not null default false,
  unique (user_id, ref, is_paper)
);

create table if not exists public.settlements (
  id bigint generated always as identity primary key,
  bet_id bigint not null references public.bets (id) on delete cascade,
  result text not null,
  profit numeric(10, 2) not null,
  source text not null default 'auto',
  settled_at timestamptz not null default now()
);

create table if not exists public.exotics (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  track text not null,
  pool_type text not null,
  legs jsonb not null,
  stake numeric(10, 2) not null,
  status text not null default 'OPEN',
  dividend numeric(12, 2),
  placed_at timestamptz not null default now()
);

-- Telegram passcode links. Only the sha256 hash is stored; the code is
-- shown once at generation and never persisted in cleartext.
create table if not exists public.telegram_links (
  code_hash text primary key,
  user_id uuid not null references public.profiles (id) on delete cascade,
  telegram_chat_id bigint,
  telegram_username text,
  status text not null default 'PENDING'
    check (status in ('PENDING', 'LINKED', 'REVOKED')),
  expires_at timestamptz not null,
  linked_at timestamptz,
  created_at timestamptz not null default now()
);
