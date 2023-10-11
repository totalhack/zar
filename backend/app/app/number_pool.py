import time

import redis
from redis.exceptions import LockError
import rollbar
from tlbx import (
    st,
    json,
    dictmerge,
    pp,
    dbg,
    info,
    warn,
    error,
    ClassValueContainsMeta,
    raiseif,
    raiseifnot,
)

from app.core.config import settings
from app.db.session import engine
from app.schemas.zar import NumberPoolCacheValue


MINUTES = 60
HOURS = 60 * MINUTES
DAYS = 24 * HOURS
NUMBER_POOL_CONNECT_TRIES = 5
# TODO read these from pool configs
# If number hasn't been renewed in this time, mark expired (eligible to be taken)
NUMBER_POOL_CACHE_EXPIRATION = 4 * MINUTES
# Numbers can get renewed for this amount of time max
NUMBER_POOL_MAX_RENEWAL_AGE = 7 * DAYS
# How long we keep call_from -> call_to route contexts cached
NUMBER_POOL_ROUTE_CACHE_EXPIRATION = 14 * DAYS

LOCK_WAIT_TIMEOUT = 5
LOCK_HOLD_TIMEOUT = 5
INIT_LOCK_TIMEOUT = 2
POOL_SESSION_KEY = "sid"


class NumberPoolUnavailable(Exception):
    pass


class NumberPoolEmpty(Exception):
    pass


class SessionNumberUnavailable(Exception):
    pass


class NumberNotFound(Exception):
    pass


class NumberMaxRenewalExceeded(Exception):
    pass


class NumberSessionKeyMismatch(Exception):
    pass


class NumberStatus(metaclass=ClassValueContainsMeta):
    FREE = "free"
    TAKEN = "taken"
    EXPIRED = "expired"


class NumberPoolResponseStatus(metaclass=ClassValueContainsMeta):
    ERROR = "error"
    SUCCESS = "success"


class NumberPoolResponseMessages(metaclass=ClassValueContainsMeta):
    POOL_UNAVAILABLE = "pool unavailable"
    NUMBER_UNAVAILABLE = "number unavailable"
    EMPTY = "pool empty"
    NO_SID = "no session ID"
    EXPIRED = "expired"
    NOT_FOUND = "not found"
    MAX_RENEWAL = "maximum renewal exceeded"
    INTERNAL_ERROR = "internal error"


number_pool_conn = None


def get_number_pool_conn(tries=NUMBER_POOL_CONNECT_TRIES, refresh=False):
    global number_pool_conn
    if (not number_pool_conn) or refresh:
        while True:
            try:
                number_pool_conn = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=6379,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True,
                )
                info("Connected to Redis number pool")
                break
            except Exception as e:
                tries -= 1
                if tries <= 0:
                    msg = f"Could not connect to Redis number pool: {str(e)}"
                    error(msg)
                    rollbar.report_message(dict(msg=msg), "error")
                    break
                warn("Retrying Redis number pool connection...")
                time.sleep(1)
    return number_pool_conn


class NumberPoolAPI:
    """An API to manage leasing numbers from a set of dynamic phone number
    tracking pools. The pools are hydrated from the database and are managed in
    Redis in the data structures described below. It is expected `init_pools`
    has been called prior to initialiation of this class (such as at app startup
    time). This will hydrate the Redis data structures from the pools described
    in the database. If the pools already exist they will be "reset" to only have
    the numbers specified in the database, leaving overlapping numbers/contexts
    intact.

    The numbers are managed across 3 data structures:

    * Top level keys mapping phone numbers to contexts (JSON)
    * A Redis Set of free numbers per pool
    * A Redis Sorted Set of taken numbers per pool. A sorted set is used so we can
    track the numbers with the oldest renewal time for reclaiming to the pool (if
    they are past expiration).

    * TODO add number limits by request ip/user agent/host
    """

    def __init__(self, conn_tries=NUMBER_POOL_CONNECT_TRIES):
        # NOTE: It is assumed the pool has been initialized by an outside process,
        # such as in a prestart command for the service.
        self.conn = get_number_pool_conn(tries=conn_tries)
        if not self.conn:
            raise NumberPoolUnavailable("could not connect to pool")

    @classmethod
    def get_pools_from_db(cls):
        res = engine.execute("select * from zar.pools where active=1")
        return res.fetchall()

    @classmethod
    def get_pool_numbers_from_db(cls, pool_id):
        res = engine.execute(
            "select number from zar.pool_numbers where pool_id=%(pool_id)s",
            dict(pool_id=pool_id),
        )
        return set([x["number"] for x in res.fetchall()])

    def init_pools(self):
        start = time.time()
        pools = []
        errors = []

        try:
            with self._get_init_lock():
                info("Initializing number pools...")
                counts = {}
                pools = self.get_pools_from_db()  # TODO store pool configs in redis
                for pool in pools:
                    pool_id = pool["id"]
                    try:
                        with self._get_pool_lock(pool_id):
                            numbers = self.get_pool_numbers_from_db(pool_id)
                            if self._pool_exists(pool_id):
                                info(f"Resetting pool {pool_id}, preserve=True")
                                self._reset_pool(
                                    pool_id, numbers=numbers, preserve=True
                                )
                            elif numbers:
                                info(
                                    f"Adding {len(numbers)} numbers for pool {pool_id}"
                                )
                                self._add_numbers(pool_id, numbers)
                            counts[pool["name"]] = len(numbers)
                    except LockError as e:
                        errors.append(
                            f"Unable to init pool {pool_id}/{pool['name']}: LockError"
                        )
        except LockError as e:
            info("Could not get init lock, moving on")
            return

        if errors:
            msg = f"unable to init {len(errors)}/{len(pools)} pools:\n{errors}"
            error(msg)
            rollbar.report_message(dict(msg=msg), "error")

        pp(counts)
        info(f"took {time.time() - start:.3f}s")
        return counts

    def refresh_conn(self, conn_tries=NUMBER_POOL_CONNECT_TRIES):
        self.conn = get_number_pool_conn(tries=conn_tries, refresh=True)

    def get_number_context(self, number, with_age=False):
        res = self.conn.get(number)
        res = json.loads(res) if res else None
        if res and with_age:
            res["age"] = self._number_context_age(res)
            res["expired"] = self._number_context_expired(res)
        dbg(f"{number}: {res}")
        return res

    def set_number_context(self, number, context):
        dbg(f"{number}: {context}")
        context = NumberPoolCacheValue(**context)
        self.conn.set(number, context.json())

    def get_number_status(self, number, with_age=False):
        res = self.get_number_context(number, with_age=with_age)
        if not res:
            return NumberStatus.FREE, None
        if self._number_context_expired(res):
            return NumberStatus.EXPIRED, res
        return NumberStatus.TAKEN, res

    def get_cached_route_key(self, call_from, call_to):
        return f"{call_from}->{call_to}"

    def set_cached_route_context(self, call_from, call_to, context):
        context = NumberPoolCacheValue(**context)
        key = self.get_cached_route_key(call_from, call_to)
        self.conn.set(key, context.json(), ex=NUMBER_POOL_ROUTE_CACHE_EXPIRATION)

    def get_cached_route_context(self, call_from, call_to):
        key = self.get_cached_route_key(call_from, call_to)
        res = self.conn.get(key)
        return json.loads(res) if res else None

    def get_all_pool_stats(self, with_contexts=False):
        stats = {}
        pools = self.get_pools_from_db()
        for pool in pools:
            pool_id = pool["id"]
            free = self._get_free_numbers(pool_id)
            taken = self._get_taken_numbers(pool_id)
            pool_res = dict(
                counts=dict(
                    free=len(free), taken=len(taken), total=len(free) + len(taken)
                )
            )
            if with_contexts:
                pool_res["contexts"] = self._get_number_contexts(taken, with_age=True)
            stats[f"{pool_id}/{pool['name']}"] = pool_res
        return stats

    def lease_number(self, pool_id, request_context, target_number=None, renew=False):
        request_context = request_context or {}
        start = time.time()
        number = None
        from_sid = False
        key_mismatch = False
        sid_number_mismatch = False
        request_sid = self._get_session_id(pool_id, request_context)

        dbg(f"{request_sid}: pool_id: {pool_id}, target number {target_number}")

        try:
            with self._get_pool_lock(pool_id):
                # HACK: ensure we are targeting the session number for renewal if one
                # exists. Roughly tries to enforce a single number per session.
                sid_number = self._get_session_number(pool_id, request_context)
                if sid_number:
                    if target_number and sid_number != target_number:
                        warn(
                            f"{request_sid}: Session / Target number mismatch: {sid_number} / {target_number}"
                        )
                        sid_number_mismatch = True
                    from_sid = True
                    renew = True
                    target_number = sid_number

                if target_number:
                    status, ctx = self.get_number_status(target_number, with_age=True)
                    info(f"{request_sid}: target number {target_number} ctx: {ctx}")
                    if status == NumberStatus.FREE:
                        dbg(f"{request_sid}: target number {target_number} free")
                        number = self._lease_free_number(
                            pool_id, target_number, request_context
                        )
                    elif status == NumberStatus.EXPIRED:
                        dbg(f"{request_sid}: target number {target_number} expired")
                        number = self._lease_expired_number(
                            pool_id, target_number, request_context
                        )
                    elif status == NumberStatus.TAKEN and renew:
                        dbg(
                            f"{request_sid}: target number {target_number} taken, renewal requested"
                        )
                        if request_context:
                            ctx["request_context"].update(request_context)
                        try:
                            res = self._renew_number(
                                pool_id, target_number, context=ctx, from_sid=from_sid
                            )
                            if res:
                                number = target_number
                        except NumberSessionKeyMismatch as e:
                            # Can happen if, for example, a user comes back later and their
                            # number has been leased out to another session. Let it go on to
                            # leasing a random number instead.
                            key_mismatch = True

                if (not number) and (
                    (not from_sid) or (key_mismatch and not sid_number_mismatch)
                ):
                    number = self._lease_random_number(pool_id, request_context)
        except LockError as e:
            raise NumberPoolUnavailable(f"Could not acquire pool {pool_id} lock")

        dbg(f"{request_sid}: took {time.time() - start:0.3f}s, number: {number}")
        if not number:
            msg = "No numbers available"
            exc = NumberPoolEmpty
            if from_sid:
                msg = "Session number unavailable"
                exc = SessionNumberUnavailable
            error(msg + f": {locals()}")
            raise exc(msg)
        return number

    def _get_init_lock(self):
        init_lock_name = "Pool Init"
        return self.conn.lock(init_lock_name, blocking_timeout=INIT_LOCK_TIMEOUT)

    def _get_pool_lock(
        self,
        pool_id,
        timeout=LOCK_HOLD_TIMEOUT,
        blocking_timeout=LOCK_WAIT_TIMEOUT,
    ):
        name = f"Pool: {pool_id} / Lock"
        return self.conn.lock(name, timeout=timeout, blocking_timeout=blocking_timeout)

    def _free_pool_exists(self, pool_id):
        return True if self.conn.exists(self._get_free_pool_name(pool_id)) else False

    def _taken_pool_exists(self, pool_id):
        return True if self.conn.exists(self._get_taken_pool_name(pool_id)) else False

    def _pool_exists(self, pool_id):
        if self._free_pool_exists(pool_id):
            return True
        if self._taken_pool_exists(pool_id):
            warn("Taken pool exists without free pool")
            return True
        return False

    def _get_free_pool_name(self, pool_id):
        return f"Pool: {pool_id} / Free"

    def _get_taken_pool_name(self, pool_id):
        return f"Pool: {pool_id} / Taken"

    def _get_session_number_hash_name(self, pool_id):
        return f"Pool: {pool_id} / SID Number Hash"

    def _get_free_numbers(self, pool_id):
        return set(self.conn.smembers(self._get_free_pool_name(pool_id)))

    def _get_taken_numbers(self, pool_id):
        return set(self.conn.zrange(self._get_taken_pool_name(pool_id), 0, -1))

    def _get_pool_session_key(self, pool_id):
        # TODO make this configurable per pool
        return POOL_SESSION_KEY

    def _get_session_id(self, pool_id, request_context):
        key = self._get_pool_session_key(pool_id)
        return request_context.get(key, None)

    def _get_session_number(self, pool_id, request_context):
        sid = self._get_session_id(pool_id, request_context)
        if not sid:
            return None
        return self.conn.hget(self._get_session_number_hash_name(pool_id), sid)

    def _get_number_contexts(self, numbers, with_age=False):
        res = {}
        for number in numbers:
            res[number] = self.get_number_context(number, with_age=with_age)
        return res

    def _create_number_context(self, pool_id, request_context):
        now = time.time()
        return dict(
            pool_id=pool_id,
            request_context=request_context,
            leased_at=now,
            renewed_at=now,
        )

    def _number_context_age(self, context):
        renewed_at = context["renewed_at"]
        return int(time.time() - renewed_at)

    def _number_context_expired(self, context):
        # TODO support different expirations per pool
        if self._number_context_age(context) >= NUMBER_POOL_CACHE_EXPIRATION:
            return True
        return False

    def _pop_random_number(self, pool_id):
        return self.conn.spop(self._get_free_pool_name(pool_id))

    def _pop_free_number(self, pool_id, number):
        return self.conn.srem(self._get_free_pool_name(pool_id), number)

    def _add_taken_number(self, pool_id, number, context):
        return self.conn.zadd(
            self._get_taken_pool_name(pool_id), {number: str(context["renewed_at"])}
        )

    def _update_taken_number(self, pool_id, number, context):
        return self.conn.zadd(
            self._get_taken_pool_name(pool_id),
            {number: str(context["renewed_at"])},
            xx=True,  # Only update
            ch=True,  # Return count of changed
        )

    def _get_least_recently_renewed(self, pool_id):
        """Get the member with the earliest timestamp"""
        res = self.conn.zrangebyscore(
            self._get_taken_pool_name(pool_id),
            "-inf",
            "+inf",
            withscores=True,
            start=0,
            num=1,
        )
        return res[0] if res else None

    # NOTE Everything below is expected to be called with a pool lock held!

    def _add_session_number(self, pool_id, sid, number):
        return self.conn.hset(
            self._get_session_number_hash_name(pool_id), sid, value=number
        )

    def _get_pool_numbers(self, pool_id):
        return self._get_free_numbers(pool_id) | self._get_taken_numbers(pool_id)

    def _add_numbers(self, pool_id, numbers):
        return self.conn.sadd(self._get_free_pool_name(pool_id), *numbers)

    def _remove_numbers(self, pool_id, numbers):
        """Completely remove numbers from the pool"""
        info(f"removing {len(numbers)} numbers from the pool")
        # remove from taken
        self.conn.zrem(self._get_taken_pool_name(pool_id), *numbers)
        # remove from keys
        self.conn.delete(*numbers)
        # remove from free
        self.conn.srem(self._get_free_pool_name(pool_id), *numbers)
        # remove session -> number mappings
        sids = []
        for number in numbers:
            ctx = self.get_number_context(number)
            if not ctx:
                continue
            sids.append(self._get_session_id(pool_id, ctx["request_context"]))
        if sids:
            self.conn.hdel(self._get_session_number_hash_name(pool_id), *sids)

    def _take_number(self, pool_id, number, request_context, update=False):
        context = self._create_number_context(pool_id, request_context)
        if update:
            res = self._update_taken_number(pool_id, number, context)
        else:
            res = self._add_taken_number(pool_id, number, context)
        raiseifnot(res, f"Failed to take number: {pool_id}/{number}")
        self.set_number_context(number, context)
        sid = self._get_session_id(pool_id, request_context)
        if sid:
            self._add_session_number(pool_id, sid, number)
        return res

    def _renew_number(self, pool_id, number, context=None, from_sid=False):
        """Expected to be called with a number that is 'taken'"""
        dbg(f"Renewing number {pool_id}/{number}")

        curr_context = self.get_number_context(number)
        raiseif(curr_context is None, "Trying to renew inactive number")
        if not context:
            warn(f"No context provided, using number {number} context")
            context = curr_context

        sid = self._get_session_id(pool_id, context["request_context"])
        curr_sid = self._get_session_id(pool_id, curr_context["request_context"])
        if sid != curr_sid:
            msg = f"session key mismatch for {pool_id}/{number} {sid}/{curr_sid}, can not renew"
            warn(msg)
            raise NumberSessionKeyMismatch(msg)

        if context != curr_context:
            # 2nd arg overwrites 1st on conflict
            context = dictmerge(curr_context, context, overwrite=True)

        context["renewed_at"] = time.time()
        if (context["renewed_at"] - context["leased_at"]) > NUMBER_POOL_MAX_RENEWAL_AGE:
            msg = f"Not renewing number {pool_id}/{number} due to max renewal time"
            warn(msg)
            raise NumberMaxRenewalExceeded(msg)

        res = self._update_taken_number(pool_id, number, context)
        raiseifnot(res, f"Failed to renew number: {pool_id}/{number}")
        self.set_number_context(number, context)
        if sid and (not from_sid):
            # Ensure this SID is associated with this number
            self._add_session_number(pool_id, sid, number)
        return res

    def _lease_random_number(self, pool_id, request_context):
        number = self._pop_random_number(pool_id)
        if not number:
            dbg("No free numbers found, checking expired...")
            res = self._get_least_recently_renewed(pool_id)
            raiseifnot(res, "No least recently renewed number?")
            target_number, renewed_at = res
            status, _ = self.get_number_status(target_number)
            if status == NumberStatus.EXPIRED:
                return self._lease_expired_number(
                    pool_id, target_number, request_context
                )
            else:
                return None

        info(f"Leasing random number {pool_id}/{number}")
        self._take_number(pool_id, number, request_context)
        return number

    def _lease_free_number(self, pool_id, number, request_context):
        info(f"Leasing free number: {pool_id}/{number}")
        res = self._pop_free_number(pool_id, number)
        if not res:
            raise NumberNotFound(f"could not find free number {pool_id}/{number}")
        self._take_number(pool_id, number, request_context)
        return number

    def _lease_expired_number(self, pool_id, number, request_context):
        """This will just take over an already-taken-but-expired number"""
        info(f"Leasing expired number: {pool_id}/{number}")
        self._take_number(pool_id, number, request_context, update=True)
        return number

    def _set_number_renewed_at(self, number, renewed_at):
        status, _ = self.get_number_status(number)
        raiseifnot(
            status == NumberStatus.TAKEN,
            f"Trying to set renewed_at on number with invalid status: {status}",
        )
        ctx = self.get_number_context(number)
        ctx["renewed_at"] = renewed_at
        self.set_number_context(number, ctx)

    def _reset_pool(self, pool_id, numbers=None, preserve=True):
        target_numbers = numbers or self.get_pool_numbers_from_db(pool_id)
        current_numbers = self._get_pool_numbers(pool_id)
        if preserve:
            # Remove only numbers that no longer exist
            removes = current_numbers - target_numbers
            # Add only new numbers
            adds = target_numbers - current_numbers
        else:
            # Remove and re-add all
            removes = target_numbers
            adds = target_numbers
        if removes:
            self._remove_numbers(pool_id, removes)
        if adds:
            self._add_numbers(pool_id, adds)
        info(f"{len(target_numbers)} total, {len(removes)} removes, {len(adds)} adds")

    def _reset_pools(self, preserve=True):
        pools = self.get_pools_from_db()
        info(f"Resetting {len(pools)} pools")
        for pool in pools:
            self._reset_pool(pool["id"], preserve=preserve)
