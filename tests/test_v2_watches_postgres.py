"""Real isolated PostgreSQL checks; marketplace and Telegram boundaries stay offline."""
import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from catalog_v2 import watches


async def isolated():
    url = os.getenv("MARKETFUSION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set MARKETFUSION_TEST_DATABASE_URL for isolated PostgreSQL tests")
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    schema = "watches_test_" + uuid4().hex
    await pool.execute(f'CREATE SCHEMA "{schema}"')
    await pool.close()
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5, server_settings={"search_path": schema})
    await pool.execute("""CREATE TABLE watchlists(id BIGSERIAL PRIMARY KEY,user_id BIGINT,query TEXT,
        sources TEXT[],threshold_rub NUMERIC,interval_minutes INT DEFAULT 60,active BOOLEAN DEFAULT true,
        last_price_rub NUMERIC,last_checked_at TIMESTAMPTZ,next_run_at TIMESTAMPTZ DEFAULT now(),
        last_error TEXT,created_at TIMESTAMPTZ DEFAULT now());
        INSERT INTO watchlists(user_id,query) VALUES(1,'unbound old query');
        CREATE TABLE notifications(id BIGSERIAL PRIMARY KEY,user_id BIGINT,title TEXT,body TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),read_at TIMESTAMPTZ);""")
    migration = (Path(__file__).resolve().parents[1] / "backend/migrations/002_v2_watches.sql").read_text(encoding="utf-8")
    await pool.execute(migration)
    await pool.execute(migration)
    return SimpleNamespace(pool=pool), schema


async def cleanup(db, schema):
    await db.pool.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await db.pool.close()


def group(capacity="1tb", price=490000, source="wb", native="123", stock=True):
    from catalog_v2.models import ProductGroup, CatalogProduct, ProductVariant, MarketplaceOffer
    variant = ProductVariant(id="v" + capacity, product_id="p" + capacity,
                             brand="kingston", model="nv3", category="ssd",
                             attributes={"capacity": capacity}, condition="new")
    offer = MarketplaceOffer(id=source + native, product_id=variant.product_id, variant_id=variant.id,
                             source=source, native_id=native, title="Kingston NV3 " + capacity,
                             url="https://example.test/" + native, price=price, currency="RUB",
                             region="Москва", match_status="exact", in_stock=stock)
    return ProductGroup(product=CatalogProduct(id=variant.product_id,title=offer.title,brand="kingston",model="nv3",category="ssd"),
                        variant=variant, offers=[offer], match_status="exact")


def service(monkeypatch, initial, refresh):
    class Service:
        async def get_product(self, user, product_id):
            if user != 1 or product_id != initial.product.id:
                raise LookupError("not owned")
            return initial

        async def search(self, user, request):
            assert user == 1
            assert "1tb" in request.query.lower()
            return SimpleNamespace(groups=refresh, sources=[])
    monkeypatch.setattr(watches, "_service", lambda db: Service())


def test_migration_crud_ownership_and_concurrent_leases(monkeypatch):
    async def run():
        db, schema = await isolated()
        try:
            old = await db.pool.fetchrow("SELECT * FROM watchlists")
            assert old["active"] is False and old["state"] == "needs_selection"
            service(monkeypatch, group(), [group()])
            watch = await watches.create_watch(db, 1, watches.WatchCreate(product_id="p1tb", region="Москва", threshold=500000))
            assert watch["product_id"] == "p1tb"
            assert await watches.list_watches(db, 2) == []
            assert await watches.update_watch(db, 2, watch["id"], watches.WatchPatch(active=False)) is None
            assert await watches.delete_watch(db, 2, watch["id"]) is False
            claims = await asyncio.gather(*(watches.claim_due_watch(db) for _ in range(5)))
            assert sum(row is not None for row in claims) == 1
            claimed = next(row for row in claims if row is not None)
            await db.pool.execute("UPDATE v2_watches SET lease_until=now()-interval '1 second'")
            replacement = await watches.claim_due_watch(db)
            assert replacement["lease_token"] != claimed["lease_token"]
            await watches.check_watch(db, claimed)
            assert await db.pool.fetchval("SELECT count(*) FROM v2_observations") == 0
            await watches.check_watch(db, replacement)
            assert await db.pool.fetchval("SELECT count(*) FROM v2_alert_events") == 1
            assert len(await watches.notifications(db, 1)) == 1
            assert await watches.notifications(db, 2) == []
            assert (await watches.history(db, 1, "p1tb", "30"))["summary"]["min"] == 490000
            with pytest.raises(LookupError):
                await watches.history(db, 2, "p1tb", "30")
            await db.pool.execute("UPDATE v2_watches SET next_run_at=now()")
            await watches.check_watch(db, await watches.claim_due_watch(db))
            assert await db.pool.fetchval("SELECT count(*) FROM v2_alert_events") == 1
            await watches.update_watch(db, 1, watch["id"], watches.WatchPatch(threshold=495000, cooldown_minutes=0))
            await watches.check_watch(db, await watches.claim_due_watch(db))
            assert await db.pool.fetchval("SELECT count(*) FROM v2_alert_events") == 2
            # Changing settings must not reuse a previously emitted event key.
        finally:
            await cleanup(db, schema)
    asyncio.run(run())


def test_history_never_blends_price_regions(monkeypatch):
    async def run():
        db, schema = await isolated()
        try:
            service(monkeypatch, group(), [group()])
            await watches.create_watch(db, 1, watches.WatchCreate(product_id="p1tb", region="Москва"))
            await watches.check_watch(db, await watches.claim_due_watch(db))
            await db.pool.execute("""INSERT INTO v2_observations(user_id,product_id,variant_id,offer_id,source,price,currency,region,product_url,is_winner,captured_at)
                VALUES(1,'p1tb','v1tb','elsewhere','wb',100000,'RUB','Владивосток','https://example.test',true,now())""")
            result = await watches.history(db, 1, "p1tb", "all")
            assert result["summary"]["min"] == 490000
            assert len(result["points"]) == 1
        finally:
            await cleanup(db, schema)
    asyncio.run(run())


def test_wrong_capacity_and_offer_replacement_cannot_trigger(monkeypatch):
    async def run():
        db, schema = await isolated()
        try:
            for mode, candidates in (("minimum", [group("500gb", 300000)]),
                                     ("offer", [group(price=300000, native="different")])):
                service(monkeypatch, group(), candidates)
                await watches.create_watch(db, 1, watches.WatchCreate(product_id="p1tb", region="Москва", mode=mode,
                    offer_id="wb123" if mode == "offer" else None, threshold=500000))
                await watches.check_watch(db, await watches.claim_due_watch(db))
            assert await db.pool.fetchval("SELECT count(*) FROM v2_alert_events") == 0
            assert await db.pool.fetchval("SELECT count(*) FROM v2_observations") == 0
        finally:
            await cleanup(db, schema)
    asyncio.run(run())


def test_ambiguous_delivery_is_never_automatically_retried(monkeypatch):
    async def run():
        db, schema = await isolated()
        try:
            service(monkeypatch, group(), [group()])
            await watches.create_watch(db, 1, watches.WatchCreate(product_id="p1tb", region="Москва", threshold=500000))
            await watches.check_watch(db, await watches.claim_due_watch(db))
            attempts = []
            async def lost_ack(*args):
                attempts.append(args)
                raise asyncio.TimeoutError()
            monkeypatch.setattr(watches, "_send_telegram", lost_ack)
            await watches.deliver_one(db, "fake-offline-token")
            await watches.deliver_one(db, "fake-offline-token")
            assert len(attempts) == 1
            assert await db.pool.fetchval("SELECT delivery_state FROM v2_alert_events") == "uncertain"
            assert len(await watches.notifications(db, 1)) == 1
            # A process crash after starting a send is just as ambiguous as a timeout.
            await db.pool.execute("UPDATE v2_alert_events SET delivery_state='sending',send_started_at=now()-interval '3 minutes'")
            await watches.deliver_one(db, "fake-offline-token")
            assert len(attempts) == 1
            assert await db.pool.fetchval("SELECT delivery_state FROM v2_alert_events") == "uncertain"
        finally:
            await cleanup(db, schema)
    asyncio.run(run())


def test_outbox_parallel_claims_send_once_and_persist_receipt(monkeypatch):
    async def run():
        db, schema = await isolated()
        try:
            service(monkeypatch, group(), [group()])
            await watches.create_watch(db, 1, watches.WatchCreate(product_id="p1tb", region="Москва", threshold=500000))
            await watches.check_watch(db, await watches.claim_due_watch(db))
            attempts = []
            async def sent(*args):
                attempts.append(args)
                await asyncio.sleep(.02)
                return 456
            monkeypatch.setattr(watches, "_send_telegram", sent)
            await asyncio.gather(*(watches.deliver_one(db, "fake-offline-token") for _ in range(5)))
            assert len(attempts) == 1
            row = await db.pool.fetchrow("SELECT * FROM v2_alert_events")
            assert row["delivery_state"] == "sent" and row["telegram_message_id"] == 456
        finally:
            await cleanup(db, schema)
    asyncio.run(run())


def test_offer_watch_requires_selected_offers_region_not_another_offer(monkeypatch):
    async def run():
        db,schema=await isolated()
        try:
            target=group()
            other=target.offers[0].model_copy(update={'id':'other-region','native_id':'other','region':'Омск'})
            target.offers.append(other)
            service(monkeypatch,target,[target])
            with pytest.raises(ValueError):
                await watches.create_watch(db,1,watches.WatchCreate(product_id=target.product.id,
                    mode='offer',offer_id=other.id,region='Москва'))
            assert await db.pool.fetchval('SELECT count(*) FROM v2_watches')==0
        finally: await cleanup(db,schema)
    asyncio.run(run())


def test_minimum_watch_requires_region_evidence_from_selected_sources(monkeypatch):
    async def run():
        db,schema=await isolated()
        try:
            target=group(source='yandex_market')
            target.offers.append(target.offers[0].model_copy(update={'id':'wb-unknown','source':'wb','region':''}))
            service(monkeypatch,target,[target])
            with pytest.raises(ValueError):
                await watches.create_watch(db,1,watches.WatchCreate(product_id=target.product.id,
                    sources=['wb'],region='Москва'))
        finally: await cleanup(db,schema)
    asyncio.run(run())


def test_targeted_one_shot_claim_leaves_other_due_watches_untouched(monkeypatch):
    async def run():
        db,schema=await isolated()
        try:
            service(monkeypatch,group(),[group()])
            first=await watches.create_watch(db,1,watches.WatchCreate(product_id='p1tb',region='Москва'))
            second=await watches.create_watch(db,1,watches.WatchCreate(product_id='p1tb',region='Москва'))
            claimed=await watches.claim_due_watch(db,watch_id=second['id'])
            assert claimed['id']==second['id']
            assert (await watches.claim_due_watch(db))['id']==first['id']
        finally: await cleanup(db,schema)
    asyncio.run(run())
