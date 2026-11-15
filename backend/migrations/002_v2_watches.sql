-- Additive: preserve all query-only legacy rows and history, but never poll them.
ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS product_id TEXT;
ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS variant_id TEXT;
ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS state TEXT NOT NULL DEFAULT 'needs_selection';
UPDATE watchlists SET active=false,state='needs_selection' WHERE product_id IS NULL OR variant_id IS NULL;

CREATE TABLE IF NOT EXISTS v2_watches (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    offer_id TEXT,
    bound_source TEXT,
    bound_native_id TEXT,
    mode TEXT NOT NULL CHECK(mode IN ('offer','minimum')),
    title TEXT NOT NULL,
    target_json JSONB NOT NULL,
    region TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'RUB',
    sources TEXT[],
    threshold BIGINT CHECK(threshold>0),
    interval_minutes INTEGER NOT NULL DEFAULT 60 CHECK(interval_minutes IN (15,30,60,180,360,720,1440)),
    cooldown_minutes INTEGER NOT NULL DEFAULT 60 CHECK(cooldown_minutes>=0),
    rules JSONB NOT NULL DEFAULT '{}',
    rule_state JSONB NOT NULL DEFAULT '{}',
    active BOOLEAN NOT NULL DEFAULT true,
    state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','paused','needs_selection')),
    last_price BIGINT,
    last_source TEXT,
    last_checked_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    next_run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_token TEXT,
    lease_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK(mode <> 'offer' OR (offer_id IS NOT NULL AND bound_source IS NOT NULL AND bound_native_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_v2_watches_due ON v2_watches(next_run_at) WHERE active AND state='active';
CREATE INDEX IF NOT EXISTS idx_v2_watches_user ON v2_watches(user_id,created_at DESC);

CREATE TABLE IF NOT EXISTS v2_observations (
    id BIGSERIAL PRIMARY KEY,
    watch_id BIGINT REFERENCES v2_watches(id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL,
    product_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    offer_id TEXT NOT NULL,
    source TEXT NOT NULL,
    price BIGINT NOT NULL CHECK(price>0),
    currency TEXT NOT NULL,
    region TEXT NOT NULL,
    product_url TEXT NOT NULL,
    is_winner BOOLEAN NOT NULL DEFAULT false,
    captured_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_v2_observations_watch ON v2_observations(watch_id,captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_v2_observations_product ON v2_observations(user_id,product_id,region,currency,captured_at DESC);

CREATE TABLE IF NOT EXISTS v2_alert_events (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    watch_id BIGINT REFERENCES v2_watches(id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ,
    delivery_state TEXT NOT NULL DEFAULT 'pending' CHECK(delivery_state IN ('pending','sending','sent','uncertain','failed')),
    send_started_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    telegram_message_id BIGINT,
    delivery_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_v2_alert_events_pending ON v2_alert_events(id) WHERE delivery_state='pending';
CREATE INDEX IF NOT EXISTS idx_v2_alert_events_user ON v2_alert_events(user_id,created_at DESC);
