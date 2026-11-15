"""Rules use measured ordinary prices, persistent state and conservative rearming."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def rules(**kw):
    from catalog_v2.watches import evaluate_rules
    defaults = dict(price=490000, previous=550000, threshold=500000, rules={},
                    state={}, now=datetime(2026, 11, 15, tzinfo=timezone.utc),
                    cooldown_minutes=60, historic_min=None, low30=None, low90=None,
                    in_stock=True, source="wb", previous_source="wb")
    defaults.update(kw)
    return evaluate_rules(**defaults)


def test_threshold_dedup_hysteresis_and_rearm():
    fired, state = rules()
    assert fired == ["threshold"]
    assert rules(state=state)[0] == []
    _, state = rules(price=500001, state=state)
    assert rules(state=state)[0] == []
    _, state = rules(price=510000, state=state)
    later = datetime(2026, 11, 15, 2, tzinfo=timezone.utc)
    assert rules(state=state, now=later)[0] == ["threshold"]


@pytest.mark.parametrize("rule,changes,expected", [
    ({"drop_amount": 50000}, {}, "drop_amount"),
    ({"drop_percent": 10}, {}, "drop_percent"),
    ({"historical_low": True}, {"historic_min": 500000}, "historical_low"),
    ({"low_30": True}, {"low30": 500000}, "low_30"),
    ({"low_90": True}, {"low90": 500000}, "low_90"),
    ({"back_in_stock": True}, {"state": {"in_stock": False}}, "back_in_stock"),
    ({"cheaper_source": True}, {"previous_source": "ozon"}, "cheaper_source"),
])
def test_each_rule_uses_real_baseline_and_deduplicates(rule, changes, expected):
    fired, state = rules(threshold=None, rules=rule, **changes)
    assert fired == [expected]
    assert rules(threshold=None, rules=rule, state=state, **{k:v for k,v in changes.items() if k != "state"})[0] == []


def test_missing_price_is_not_zero_or_a_restock_and_history_needs_measurements():
    assert rules(price=None, rules={"historical_low": True, "back_in_stock": True}, state={"in_stock": False}, in_stock=None)[0] == []
    assert rules(threshold=None, rules={"historical_low": True, "low_30": True, "low_90": True})[0] == []


def test_cooldown_does_not_lose_new_price_drop():
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    fired, state = rules(threshold=None, rules={"drop_amount": 50000}, now=now)
    assert fired == ["drop_amount"]
    assert rules(price=420000, previous=490000, threshold=None, rules={"drop_amount": 50000}, state=state, now=now + timedelta(minutes=30))[0] == []
    assert rules(price=420000, previous=420000, threshold=None, rules={"drop_amount": 50000}, state=state, now=now + timedelta(minutes=61))[0] == ["drop_amount"]


def test_watch_requires_selected_offer_and_allowed_intervals():
    from catalog_v2.watches import WatchCreate, WatchPatch
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        WatchCreate(product_id="p1", mode="offer", region="Москва")
    with pytest.raises(ValidationError):
        WatchCreate(product_id="p1", mode="minimum", region="Москва", interval_minutes=1)
    with pytest.raises(ValidationError):
        WatchPatch(product_id="other")
    with pytest.raises(ValidationError):
        WatchCreate(product_id="p1", mode="minimum", region="Москва", rules={"drop_percent": 101})


def test_unchanged_threshold_and_historical_lows_do_not_repeat_after_cooldown():
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    fired, state = rules(rules={"historical_low": True}, historic_min=500000, now=now)
    assert fired == ["threshold", "historical_low"]
    assert rules(rules={"historical_low": True}, historic_min=490000,
                 state=state, now=now + timedelta(days=1))[0] == []


@pytest.mark.parametrize('key,baseline,window',[('low_30','low30',30),('low_90','low90',90)])
def test_rolling_low_rearms_when_previous_emitted_low_leaves_window(key,baseline,window):
    now=datetime(2026,11,15,tzinfo=timezone.utc)
    fired,state=rules(threshold=None,rules={key:True},now=now,**{baseline:500000})
    assert fired==[key]
    fired,state=rules(price=500000,previous=550000,threshold=None,rules={key:True},
                      state=state,now=now+timedelta(days=window+1),**{baseline:550000})
    assert fired==[key]
    assert rules(price=500000,threshold=None,rules={key:True},state=state,
                 now=now+timedelta(days=window+2),**{baseline:500000})[0]==[]


def test_expired_rolling_low_keeps_pending_candidate_during_other_rule_cooldown():
    now=datetime(2026,11,15,tzinfo=timezone.utc)
    state={'low_30_emitted':490000,'low_30_emitted_at':(now-timedelta(days=40)).isoformat(),
           'last_notified_at':now.isoformat()}
    fired,state=rules(price=500000,threshold=None,rules={'low_30':True},low30=550000,
                      state=state,now=now+timedelta(minutes=15))
    assert fired==[] and state['low_30_pending']==500000
    _,state=rules(price=500000,threshold=None,rules={'low_30':True},low30=500000,
                  state=state,now=now+timedelta(minutes=30))
    assert rules(price=500000,threshold=None,rules={'low_30':True},low30=500000,
                 state=state,now=now+timedelta(minutes=61))[0]==['low_30']
