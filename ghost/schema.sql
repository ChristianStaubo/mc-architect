-- The ghost's store (docs/ghost/design.md). Applied by ghost/db.py migrate(); safe to run again.
-- Stored first, done after: every event, task, approval and effect is a row before anything happens.

CREATE TABLE IF NOT EXISTS members (            -- who is in which house, with which role
  player     text PRIMARY KEY,                  -- Minecraft name (lower case)
  uuid       text,
  house      text,                              -- null: hasn't picked (a guest)
  role       text NOT NULL DEFAULT 'guest',     -- owner | head | member | guest
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (             -- everything the plugin sent, before any decision
  id         bigserial PRIMARY KEY,
  plugin_id  text UNIQUE,                       -- the plugin's inbox id and time: a repeat delivery is ignored
  kind       text NOT NULL,                     -- chat | command | button | join | pick_house | sign
  player     text,
  house      text,                              -- the player's house when it arrived
  addressed  text NOT NULL,                     -- explicit | candidate | ignored
  text       text,
  context    jsonb NOT NULL DEFAULT '{}',
  verdict    text,                              -- what the filter decided (for the listening eval)
  thread_id  bigint,
  at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS threads (            -- a player's conversation with their house's ghost
  id         bigserial PRIMARY KEY,
  player     text NOT NULL,
  ghost      text NOT NULL,                     -- house id, or 'spirit'
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (player, ghost)
);

CREATE TABLE IF NOT EXISTS messages (           -- what was said in a thread, both ways
  id         bigserial PRIMARY KEY,
  thread_id  bigint NOT NULL REFERENCES threads,
  who        text NOT NULL,                     -- player | ghost
  text       text NOT NULL,
  at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (              -- a piece of work a worker does (one Temporal workflow)
  id         bigserial PRIMARY KEY,
  kind       text NOT NULL,                     -- build
  player     text NOT NULL,
  ghost      text NOT NULL,
  thread_id  bigint REFERENCES threads,
  request    text NOT NULL,
  state      text NOT NULL DEFAULT 'new',       -- ghost/tasks.py: new designing waiting approval building done | dropped failed denied undone
  detail     jsonb NOT NULL DEFAULT '{}',       -- plan, box, blocks, preview, edit ids
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approvals (          -- who said yes to what (bound to a plan hash)
  id         bigserial PRIMARY KEY,
  task_id    bigint NOT NULL REFERENCES tasks,
  approver   text NOT NULL,
  kind       text NOT NULL,                     -- asker | head | zone_head
  plan_hash  text NOT NULL,
  at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (task_id, kind)
);

CREATE TABLE IF NOT EXISTS budget (             -- reserve before, settle after: one row per spend
  id         bigserial PRIMARY KEY,
  house      text NOT NULL,
  day        date NOT NULL DEFAULT current_date,
  task_id    bigint,
  kind       text NOT NULL,                     -- requests | blocks
  amount     integer NOT NULL,
  state      text NOT NULL DEFAULT 'reserved',  -- reserved | settled | released
  at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leases (             -- a worker must hold the area to build in it
  area       text PRIMARY KEY,                  -- chunk key "world:cx:cz"
  holder     text NOT NULL,                     -- task id
  expires_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (              -- one row per tool call, written before the action
  id         bigserial PRIMARY KEY,
  at         timestamptz NOT NULL DEFAULT now(),
  trace_id   text,
  task_id    bigint,
  ghost      text,
  requester  text,
  action     text NOT NULL,
  resource   text,
  decision   text NOT NULL,                     -- allow | deny
  rules      text[] NOT NULL DEFAULT '{}',
  approval   bigint,
  untrusted  boolean NOT NULL DEFAULT false,    -- was untrusted text (signs, books) in the context?
  detail     jsonb NOT NULL DEFAULT '{}',
  result     text                               -- filled after: ok | error: ... | skipped
);

CREATE TABLE IF NOT EXISTS traces (             -- one row per model call; big text kept 30 days
  id         bigserial PRIMARY KEY,
  at         timestamptz NOT NULL DEFAULT now(),
  trace_id   text NOT NULL,
  span_id    text NOT NULL,
  task_id    bigint,
  role       text NOT NULL,                     -- filter | router | worker
  model      text,
  prompt_hash text,                             -- the system prompt, stored once in prompts
  input      text,
  output     text,
  ms         integer,
  ok         boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS prompts (
  hash       text PRIMARY KEY,
  body       text NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (             -- replies are written with the state change, sent by a loop
  id         bigserial PRIMARY KEY,
  at         timestamptz NOT NULL DEFAULT now(),
  ghost      text NOT NULL,
  player     text,                              -- null: everyone
  text       text NOT NULL,
  buttons    jsonb NOT NULL DEFAULT '[]',
  sent_at    timestamptz,
  tries      integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS heartbeats (         -- each process says it's alive; the watchdog reads them
  process    text PRIMARY KEY,
  at         timestamptz NOT NULL DEFAULT now(),
  detail     jsonb NOT NULL DEFAULT '{}'
);

ALTER TABLE events ADD COLUMN IF NOT EXISTS handled_at timestamptz;   -- set when its work is done
ALTER TABLE events ADD COLUMN IF NOT EXISTS decision jsonb;           -- the router's answer, stored before acting on it
ALTER TABLE events ADD COLUMN IF NOT EXISTS task_id bigint;           -- the task it started, if any
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS key text UNIQUE;          -- a retried step's line is queued once

CREATE INDEX IF NOT EXISTS outbox_unsent ON outbox (id) WHERE sent_at IS NULL;
CREATE INDEX IF NOT EXISTS audit_task ON audit (task_id);
CREATE INDEX IF NOT EXISTS events_player ON events (player, id);
CREATE INDEX IF NOT EXISTS messages_thread ON messages (thread_id, id);

-- Wake the outbox sender the moment there's something to send.
CREATE OR REPLACE FUNCTION outbox_notify() RETURNS trigger AS $$
BEGIN PERFORM pg_notify('outbox', NEW.id::text); RETURN NEW; END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS outbox_notify ON outbox;
CREATE TRIGGER outbox_notify AFTER INSERT ON outbox FOR EACH ROW EXECUTE FUNCTION outbox_notify();

-- The city harness (ghost/city): one row per agent run, one per plot.
CREATE TABLE IF NOT EXISTS city_agents (
  id         bigserial PRIMARY KEY,
  run        text NOT NULL,
  role       text NOT NULL,                     -- macro | district | builder | critic
  key        text NOT NULL,                     -- the district or plot it worked on
  attempt    integer NOT NULL,
  model      text,
  start_at   timestamptz NOT NULL DEFAULT now(),
  end_at     timestamptz,
  result     jsonb                              -- end, minutes, usd, turns, denials (tools it tried and was refused)
);
CREATE TABLE IF NOT EXISTS city_plots (
  run        text NOT NULL,
  city       text NOT NULL,
  plot       text NOT NULL,
  state      text NOT NULL,                     -- building | done | flawed
  detail     jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run, plot)
);
