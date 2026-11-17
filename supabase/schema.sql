-- Karvon database. paste all into SQL Editor -> Run (safe to rerun)

-- 1. profiles + roles
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  email       text,
  full_name   text,
  phone       text,
  telegram_id bigint unique,
  role        text not null default 'passenger'
              check (role in ('passenger', 'hokimiyat', 'developer')),
  created_at  timestamptz not null default now()
);
alter table public.profiles enable row level security;

drop policy if exists "read own profile" on public.profiles;
create policy "read own profile" on public.profiles
  for select to authenticated using (id = auth.uid());
-- no update policy: roles only changed in table editor

-- new user -> profile
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email,
          coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- caller role
create or replace function public.my_role()
returns text language sql stable security definer set search_path = public as $$
  select role from public.profiles where id = auth.uid()
$$;

-- 2. gps boxes + their keys
create table if not exists public.devices (
  bus_id     text primary key,          -- '1-1'
  route      text not null,             -- route number
  device_key text not null              -- secret
);
alter table public.devices enable row level security;
-- no policies = keys not readable

-- 3. latest position per bus
create table if not exists public.bus_positions (
  bus_id     text primary key references public.devices (bus_id) on delete cascade,
  route      text not null,
  lat        double precision not null,
  lng        double precision not null,
  passengers int not null default 0,
  updated_at timestamptz not null default now()
);
alter table public.bus_positions enable row level security;
drop policy if exists "logged in users see buses" on public.bus_positions;
create policy "logged in users see buses" on public.bus_positions
  for select to authenticated using (true);

-- all reports (for forecast / analytics)
create table if not exists public.bus_history (
  id         bigserial primary key,
  bus_id     text not null,
  route      text not null,
  lat        double precision not null,
  lng        double precision not null,
  passengers int not null,
  time       timestamptz not null default now()
);
alter table public.bus_history enable row level security;
drop policy if exists "staff see history" on public.bus_history;
create policy "staff see history" on public.bus_history
  for select to authenticated using (public.my_role() in ('hokimiyat', 'developer'));

-- 4. hardware endpoint: POST /rest/v1/rpc/report_position
drop function if exists public.report_position(text, text, double precision, double precision, int);
create function public.report_position(
  bus_id text, device_key text, lat double precision, lng double precision, passengers int)
returns text language plpgsql security definer set search_path = public as $$
#variable_conflict use_column
declare
  v_route text;
begin
  -- check key
  select d.route into v_route from devices d
   where d.bus_id = report_position.bus_id
     and d.device_key = report_position.device_key;
  if v_route is null then
    raise exception 'wrong bus_id or device_key';
  end if;

  -- inside fergana region?
  if report_position.lat not between 39 and 42 or report_position.lng not between 69 and 74 then
    raise exception 'position outside Fergana region';
  end if;

  -- upsert latest
  insert into bus_positions (bus_id, route, lat, lng, passengers, updated_at)
  values (report_position.bus_id, v_route, report_position.lat, report_position.lng,
          greatest(0, least(200, report_position.passengers)), now())
  on conflict on constraint bus_positions_pkey do update
     set route = excluded.route, lat = excluded.lat, lng = excluded.lng,
         passengers = excluded.passengers, updated_at = now();

  -- history
  insert into bus_history (bus_id, route, lat, lng, passengers)
  values (report_position.bus_id, v_route, report_position.lat, report_position.lng,
          greatest(0, least(200, report_position.passengers)));
  return 'ok';
end $$;
revoke all on function public.report_position(text, text, double precision, double precision, int) from public;
grant execute on function public.report_position(text, text, double precision, double precision, int) to anon, authenticated;

-- 5. stop requests (demand)
create table if not exists public.stop_requests (
  id         bigserial primary key,
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  route_id   text not null,
  stop_index int,
  time       timestamptz not null default now()
);
alter table public.stop_requests enable row level security;
drop policy if exists "users add own requests" on public.stop_requests;
create policy "users add own requests" on public.stop_requests
  for insert to authenticated with check (user_id = auth.uid());
drop policy if exists "staff see requests" on public.stop_requests;
create policy "staff see requests" on public.stop_requests
  for select to authenticated using (public.my_role() in ('hokimiyat', 'developer'));

-- 6. telegram phones (bot only)
create table if not exists public.telegram_users (
  tg_id      bigint primary key,
  phone      text,
  first_name text,
  username   text,
  updated_at timestamptz not null default now()
);
alter table public.telegram_users add column if not exists lang text;
alter table public.telegram_users add column if not exists full_name text;
alter table public.telegram_users enable row level security;

-- 7. crowding forecast: avg passengers per hour, last 28 days
create index if not exists bus_history_time_idx on public.bus_history (time);

drop function if exists public.crowd_forecast(text, int);
create function public.crowd_forecast(p_route text default null, p_days int default 28)
returns table (route text, hour int, avg_passengers numeric, samples bigint)
language sql stable security definer set search_path = public as $$
  select h.route,
         extract(hour from h.time at time zone 'Asia/Tashkent')::int as hour,
         round(avg(h.passengers)::numeric, 1) as avg_passengers,
         count(*) as samples
    from bus_history h
   where h.time > now() - make_interval(days => least(greatest(p_days, 1), 90))
     and (p_route is null or h.route = p_route)
   group by 1, 2
   order by 1, 2
$$;
revoke all on function public.crowd_forecast(text, int) from public;
grant execute on function public.crowd_forecast(text, int) to authenticated, service_role;

-- 8. test boxes (change keys before demo)
insert into public.devices (bus_id, route, device_key) values
  ('1-1', '1', 'change-me-box-1'),
  ('2-1', '2', 'change-me-box-2')
on conflict (bus_id) do nothing;
