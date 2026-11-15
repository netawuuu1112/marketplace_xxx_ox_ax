CREATE TABLE IF NOT EXISTS mf_products (
 id TEXT PRIMARY KEY, data JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS mf_variants (
 id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES mf_products(id), data JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS mf_offers (
 id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES mf_products(id), variant_id TEXT NOT NULL,
 source TEXT NOT NULL, native_id TEXT NOT NULL, data JSONB NOT NULL, checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mf_offers_product ON mf_offers(product_id);
CREATE TABLE IF NOT EXISTS mf_searches (
 id TEXT PRIMARY KEY, user_id BIGINT NOT NULL, query TEXT NOT NULL, data JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mf_searches_owner ON mf_searches(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS mf_user_products (
 user_id BIGINT NOT NULL, product_id TEXT NOT NULL REFERENCES mf_products(id),
 PRIMARY KEY(user_id,product_id)
);
CREATE TABLE IF NOT EXISTS mf_favorites (
 user_id BIGINT NOT NULL, product_id TEXT NOT NULL REFERENCES mf_products(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(user_id,product_id)
);
CREATE TABLE IF NOT EXISTS mf_profiles (
 user_id BIGINT PRIMARY KEY, region TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS mf_price_observations (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, product_id TEXT NOT NULL,
 variant_id TEXT NOT NULL, offer_id TEXT NOT NULL, source TEXT NOT NULL,
 price BIGINT NOT NULL CHECK(price>0), currency TEXT NOT NULL, region TEXT NOT NULL,
 captured_at TIMESTAMPTZ NOT NULL, UNIQUE(user_id,offer_id,captured_at)
);
CREATE INDEX IF NOT EXISTS mf_price_observations_product ON mf_price_observations(user_id,product_id,captured_at);
CREATE TABLE IF NOT EXISTS mf_llm_usage (
 id BIGSERIAL PRIMARY KEY, user_id BIGINT, task TEXT NOT NULL, provider TEXT NOT NULL,
 model TEXT NOT NULL, input_tokens BIGINT NOT NULL DEFAULT 0, output_tokens BIGINT NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
