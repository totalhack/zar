import time

import pytest
from tlbx import st, pp

from app.number_pool import (
    NumberPoolAPI,
    NumberMaxRenewalExceeded,
    NumberPoolEmpty,
    NumberNotFound,
)


pool_api = NumberPoolAPI()
pool_api.init_pools()
DEFAULT_POOL_ID = 1
OTHER_POOL_ID = 2


def test_pool_lease_number():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)
    num = pool_api.lease_number(DEFAULT_POOL_ID, {})  # Should lease random number
    assert num
    print("number:", num)
    new_num = pool_api.lease_number(DEFAULT_POOL_ID, {}, target_number=num)
    assert num != new_num  # Not available, should lease random number
    print("number:", new_num)
    new_num = pool_api.lease_number(DEFAULT_POOL_ID, {}, target_number=num, renew=True)
    assert num == new_num  # Should renew the number
    print("number:", new_num)
    taken = pool_api._get_taken_numbers(DEFAULT_POOL_ID)
    assert len(taken) == 2
    pp(taken)


def test_pool_lease_invalid_number():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)
    with pytest.raises(NumberNotFound):
        num = pool_api.lease_number(DEFAULT_POOL_ID, {}, target_number="1234")


def test_pool_take_expired_number():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)
    num = pool_api.lease_number(DEFAULT_POOL_ID, {})
    pool_api._set_number_renewed_at(num, time.time() - 2e6)  # Should be expired...

    num2 = pool_api.lease_number(DEFAULT_POOL_ID, {})
    pool_api._set_number_renewed_at(num2, time.time() - 1e6)  # Should be expired...

    # Take remaining 2 numbers to none are free: assumes there are still 4 in test pool!
    num3 = pool_api.lease_number(DEFAULT_POOL_ID, {})
    num4 = pool_api.lease_number(DEFAULT_POOL_ID, {})

    new_num = pool_api.lease_number(DEFAULT_POOL_ID, dict(foo="bar"))
    assert num == new_num  # Should take the oldest expired number
    ctx = pool_api.get_number_context(num)
    assert "foo" in ctx.get("request_context", None)


def test_pool_max_renewal_time():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)
    num = pool_api.lease_number(DEFAULT_POOL_ID, {})
    ctx = pool_api.get_number_context(num)
    ctx["leased_at"] = time.time() - 1e6
    pool_api.set_number_context(num, ctx)
    with pytest.raises(NumberMaxRenewalExceeded):
        pool_api.lease_number(DEFAULT_POOL_ID, {}, target_number=num, renew=True)


def test_pool_full():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)
    numbers = pool_api._get_pool_numbers(DEFAULT_POOL_ID)
    first = None
    for number in numbers:
        num = pool_api.lease_number(DEFAULT_POOL_ID, {}, target_number=number)
        if not first:
            first = num

    with pytest.raises(NumberPoolEmpty):
        res = pool_api.lease_number(DEFAULT_POOL_ID, {})

    assert pool_api._get_least_recently_renewed(DEFAULT_POOL_ID)[0] == first


def test_pool_reinit():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)
    pool_api.init_pools()
    res = pool_api.lease_number(DEFAULT_POOL_ID, {})
    taken = pool_api._get_taken_numbers(DEFAULT_POOL_ID)
    assert len(taken) == 1


def test_pool_get_stats():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)
    pool_api.lease_number(DEFAULT_POOL_ID, dict(foo="bar", baz="bar"))
    stats = pool_api.get_all_pool_stats(with_contexts=True)
    pp(stats)


def test_pool_renew_with_session_id():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)

    ctx = dict(sid="1234", visits={1: dict(foo="bar")})
    num = pool_api.lease_number(DEFAULT_POOL_ID, ctx)  # Should lease random number
    assert num
    print("number:", num)

    ctx = dict(sid="1234", visits={2: dict(baz="bar")})
    new_num = pool_api.lease_number(DEFAULT_POOL_ID, ctx, target_number=num, renew=True)
    assert new_num == num
    num_ctx = pool_api.get_number_context(num)
    assert len(num_ctx["request_context"]["visits"]) == 2

    # Retry renewal with SID mismatch, should get random number
    ctx["sid"] = "5678"
    new_num = pool_api.lease_number(DEFAULT_POOL_ID, ctx, target_number=num, renew=True)
    assert new_num != num


def test_pool_session_number_map():
    pool_api._reset_pool(DEFAULT_POOL_ID, preserve=False)

    ctx = dict(sid="1234", visits={1: dict(foo="bar")})
    num = pool_api.lease_number(DEFAULT_POOL_ID, ctx)  # Should lease random number
    assert num
    print("number:", num)

    # no target specified, but sid->number map should have it
    new_num = pool_api.lease_number(DEFAULT_POOL_ID, ctx)  # Should lease same number
    assert new_num == num
    print("number:", num)

    # target matches
    new_num = pool_api.lease_number(
        DEFAULT_POOL_ID, ctx, target_number=num, renew=True
    )  # Should lease same number
    assert new_num == num
    print("number:", num)

    # Get another random number
    ctx2 = dict(sid="5678", visits={2: dict(foo="bar")})
    num2 = pool_api.lease_number(DEFAULT_POOL_ID, ctx2)  # Should lease random number
    assert num2
    print("number:", num2)

    # target and session number mismatch
    new_num = pool_api.lease_number(
        DEFAULT_POOL_ID, ctx, target_number=num2, renew=True
    )  # Should return previous num
    assert new_num == num
    print("number:", num)


def test_pool_multi_pool_sid():
    pool_api._reset_pools(preserve=False)

    ctx = dict(sid="1234", visits={1: dict(foo="bar")})
    num = pool_api.lease_number(DEFAULT_POOL_ID, ctx)  # Should lease random number
    assert num
    print("number:", num)

    new_num = pool_api.lease_number(
        OTHER_POOL_ID, ctx
    )  # Should lease diff number from second pool
    assert new_num != num
    print("number:", num)

    new_num2 = pool_api.lease_number(
        OTHER_POOL_ID, ctx
    )  # Should get same number due to SID
    assert new_num2 == new_num
    print("number:", num)

    taken = pool_api._get_taken_numbers(DEFAULT_POOL_ID)
    assert len(taken) == 1

    taken = pool_api._get_taken_numbers(OTHER_POOL_ID)
    assert len(taken) == 1
