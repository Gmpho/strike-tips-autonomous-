-- Strike Tips predictor league schema (v1, 2026-11).
-- Apply with: supabase db push  (or psql -f) on the strike-tips project.
-- All money/ledger tables are untouched; league points never touch them.

create table if not exists public.league_players (
    user_id uuid primary key references auth.users(id) on delete cascade,
    handle text not null unique,
    display_name text,
    region text not null default 'SA',
    telegram_link_id uuid,
    joined_at timestamptz not null default now(),
    unique (telegram_link_id)
);

create table if not exists public.league_meetings (
    id uuid primary key default gen_random_uuid(),
    course text not null,
    region text not null,
    meet_date date not null,
    unique (course, meet_date)
);

create table if not exists public.league_races (
    id uuid primary key default gen_random_uuid(),
    meeting_id uuid not null references public.league_meetings(id) on delete cascade,
    race_number int not null,
    off_at timestamptz not null,
    field_size int not null default 0,
    status text not null default 'open' check (status in ('open','locked','settled','void')),
    winner_number int,
    winner_sp numeric,
    unique (meeting_id, race_number)
);

-- DB-enforced lock: no pick insert/update inside 5 minutes of the off.
create or replace function public.league_pick_locked(off timestamptz)
returns boolean language sql immutable set search_path = public as $$
    select now() >= (off - interval '5 minutes');
$$;

create table if not exists public.league_picks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.league_players(user_id) on delete cascade,
    race_id uuid not null references public.league_races(id) on delete cascade,
    rank_in_slip int not null default 1 check (rank_in_slip between 1 and 3),
    runner_number int not null,
    runner_name text not null,
    taken_odds numeric not null,
    created_at timestamptz not null default now(),
    unique (user_id, race_id, rank_in_slip)
);

-- Prevent late picks at the data layer.
create or replace function public.league_enforce_lock()
returns trigger language plpgsql set search_path = public as $$
declare off timestamptz;
begin
    select off_at into off from public.league_races where id = new.race_id;
    if off is null then
        raise exception 'race not found';
    end if;
    if now() >= (off - interval '5 minutes') then
        raise exception 'locked: pick window closed';
    end if;
    return new;
end;
$$;

drop trigger if exists league_picks_lock on public.league_picks;
create trigger league_picks_lock
    before insert or update on public.league_picks
    for each row execute function public.league_enforce_lock();

-- One Telegram link per player.
create unique index if not exists league_players_telegram_uidx
    on public.league_players (telegram_link_id) where telegram_link_id is not null;

create table if not exists public.league_settlements (
    pick_id uuid primary key references public.league_picks(id) on delete cascade,
    points_position int not null default 0,
    points_sp_bonus int not null default 0,
    value_index numeric not null default 0,
    settled_at timestamptz not null default now()
);

create table if not exists public.league_rollups (
    entity_type text not null,          -- 'player' | 'cohort'
    entity_id text not null,
    region text not null,
    settled int not null default 0,
    wins int not null default 0,
    total_points int not null default 0,
    weekly_points int not null default 0,
    form_rating numeric not null default 0,
    value_index numeric not null default 0,
    strike_rate numeric not null default 0,
    last_settled timestamptz,
    updated_at timestamptz not null default now(),
    primary key (entity_type, entity_id, region)
);

-- RLS
alter table public.league_players enable row level security;
alter table public.league_picks enable row level security;
alter table public.league_settlements enable row level security;
alter table public.league_rollups enable row level security;
alter table public.league_meetings enable row level security;
alter table public.league_races enable row level security;

-- Public read: rollups + meetings + races (board + cards).
create policy league_rollups_public_read on public.league_rollups for select using (true);
create policy league_meetings_public_read on public.league_meetings for select using (true);
create policy league_races_public_read on public.league_races for select using (true);

-- Players: public read of handle/region; owner writes own row.
create policy league_players_public_read on public.league_players for select using (true);
create policy league_players_owner_insert on public.league_players for insert
    to authenticated with check ((select auth.uid()) = user_id);
create policy league_players_owner_update on public.league_players for update
    to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy league_players_owner_delete on public.league_players for delete
    to authenticated using ((select auth.uid()) = user_id);

-- Picks: public read; owner writes own picks.
create policy league_picks_public_read on public.league_picks for select using (true);
create policy league_picks_owner_insert on public.league_picks for insert
    to authenticated with check ((select auth.uid()) = user_id);
create policy league_picks_owner_update on public.league_picks for update
    to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy league_picks_owner_delete on public.league_picks for delete
    to authenticated using ((select auth.uid()) = user_id);

-- Settlements: service role only.
create policy league_settlements_service on public.league_settlements for all
    to service_role using (true) with check (true);

create index if not exists league_picks_user_race_idx on public.league_picks (user_id, race_id);
create index if not exists league_picks_race_id_idx on public.league_picks (race_id);
create index if not exists league_rollups_region_idx on public.league_rollups (region);
create index if not exists league_races_off_idx on public.league_races (off_at);
