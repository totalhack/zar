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
from app.schemas.zar import NumberPoolCacheValue, UserIDTypes


MINUTES = 60
HOURS = 60 * MINUTES
DAYS = 24 * HOURS
NUMBER_POOL_CONNECT_TRIES = 5
# TODO read these from pool configs
# If number hasn't been renewed in this time, mark expired (eligible to be taken)
NUMBER_POOL_CACHE_EXPIRATION = 6 * MINUTES
# Numbers can get renewed for this amount of time max
NUMBER_POOL_MAX_RENEWAL_AGE = 7 * DAYS
# How long we keep call_from -> call_to route contexts cached
NUMBER_POOL_ROUTE_CACHE_EXPIRATION = 30 * DAYS
NUMBER_POOL_USER_CONTEXT_EXPIRATION = 14 * DAYS

LOCK_WAIT_TIMEOUT = 5
LOCK_HOLD_TIMEOUT = 5
INIT_LOCK_TIMEOUT = 2
POOL_SESSION_KEY = "sid"
POOL_IP_KEY = "ip"
POOL_USER_AGENT_KEY = "user_agent"

IGNORED_USER_CONTEXT_CALLER_IDS = {
    # Don't cache user context for these...
    "anonymous",
    "266696687",
}


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

    Pool properties are stored in Redis under keys like 'pool_properties:{pool_id}'.

    * TODO add number limits by request ip/user agent/host
    """

    def __init__(self, conn_tries=NUMBER_POOL_CONNECT_TRIES):
        # NOTE: It is assumed the pool has been initialized by an outside process,
        # such as in a prestart command for the service.
        self.conn = get_number_pool_conn(tries=conn_tries)
        self._pool_properties_cache = {}
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

    def _get_pool_properties_key(self, pool_id):
        return f"pool_properties:{pool_id}"

    def get_pool_properties(self, pool_id):
        if pool_id in self._pool_properties_cache:
            return self._pool_properties_cache[pool_id]
        key = self._get_pool_properties_key(pool_id)
        properties_json = self.conn.get(key)
        if properties_json:
            res = json.loads(properties_json)
            self._pool_properties_cache[pool_id] = res
            return res
        msg = f"Pool properties not found for pool {pool_id}"
        rollbar.report_message(dict(msg=msg), "warning")
        return {}

    def set_pool_properties(self, pool_id, pool_row):
        key = self._get_pool_properties_key(pool_id)
        pool_data = dict(pool_row)
        properties_str = pool_data.get("properties", None) or "{}"
        properties = json.loads(properties_str)  # Validate JSON
        self.conn.set(key, json.dumps(properties))
        self._pool_properties_cache[pool_id] = properties
        dbg(f"Stored properties for pool {pool_id}")

    def reset_pool_properties(self):
        info("Repopulating all pool properties in Redis...")
        start = time.time()
        pools = self.get_pools_from_db()
        count = 0
        errors = 0
        self._pool_properties_cache = {}

        for pool in pools:
            pool_id = pool["id"]
            try:
                self.set_pool_properties(pool_id, pool)
                count += 1
            except Exception as e:
                error(f"Failed to set properties for pool {pool_id}: {e}")
                errors += 1
        info(
            f"Repopulated {count} pool configs ({errors} errors) in {time.time() - start:.3f}s"
        )
        return {"success": count, "errors": errors}

    def init_pools(self, pool_ids=None):
        start = time.time()
        pools = []
        errors = []

        try:
            with self._get_init_lock():
                info("Initializing number pools...")
                counts = {}
                pools = self.get_pools_from_db()
                for pool in pools:
                    pool_id = pool["id"]
                    if pool_ids and (pool_id not in pool_ids):
                        info(f"Skipping pool {pool_id}/{pool['name']}")
                        continue

                    self.set_pool_properties(pool_id, pool)

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
                    except LockError:
                        errors.append(
                            f"Unable to init pool {pool_id}/{pool['name']}: LockError"
                        )
        except LockError:
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

    def get_pool_number_context(self, number, with_age=False):
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
        self.conn.set(number, context.model_dump_json())

    def get_number_status(self, number, with_age=False):
        res = self.get_pool_number_context(number, with_age=with_age)
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
        self.conn.set(
            key, context.model_dump_json(), ex=NUMBER_POOL_ROUTE_CACHE_EXPIRATION
        )

    def get_cached_route_context(self, call_from, call_to):
        key = self.get_cached_route_key(call_from, call_to)
        res = self.conn.get(key)
        return json.loads(res) if res else None

    def get_user_context_key(self, id_type, user_id):
        return f"{id_type}:{user_id}"

    def get_user_context(self, id_type, user_id):
        if (
            id_type == UserIDTypes.PHONE
            and user_id.lower().lstrip("+") in IGNORED_USER_CONTEXT_CALLER_IDS
        ):
            return None
        key = self.get_user_context_key(id_type, user_id)
        res = self.conn.get(key)
        return json.loads(res) if res else None

    def set_user_context(self, id_type, user_id, context):
        if (
            id_type == UserIDTypes.PHONE
            and user_id.lower().lstrip("+") in IGNORED_USER_CONTEXT_CALLER_IDS
        ):
            return
        key = self.get_user_context_key(id_type, user_id)
        self.conn.set(key, json.dumps(context), ex=NUMBER_POOL_USER_CONTEXT_EXPIRATION)

    def update_user_context(self, id_type, user_id, context):
        current_ctx = self.get_user_context(id_type, user_id)
        if current_ctx:
            # Second arg overwrites first on conflict
            context = dictmerge(current_ctx, context, overwrite=True)
        self.set_user_context(id_type, user_id, context)
        return context

    def remove_user_context(self, id_type, user_id):
        if (
            id_type == UserIDTypes.PHONE
            and user_id.lower().lstrip("+") in IGNORED_USER_CONTEXT_CALLER_IDS
        ):
            return
        key = self.get_user_context_key(id_type, user_id)
        self.conn.delete(key)

    def get_static_number_key(self, number):
        return f"static:{number}"

    def get_static_number_context(self, number):
        key = self.get_static_number_key(number)
        res = self.conn.get(key)
        return json.loads(res) if res else None

    def set_static_number_context(self, number, context):
        key = self.get_static_number_key(number)
        self.conn.set(key, json.dumps(context))

    def is_same_ip_user_agent(self, pool_id, req_ctx1, req_ctx2):
        ip1 = self._get_session_ip(pool_id, req_ctx1)
        ip2 = self._get_session_ip(pool_id, req_ctx2)
        ua1 = self._get_session_user_agent(pool_id, req_ctx1)
        ua2 = self._get_session_user_agent(pool_id, req_ctx2)
        if not (ip1 and ip2 and ua1 and ua2):
            return False
        return (ip1 == ip2) and (ua1 == ua2)

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

    def is_area_code_pool(self, pool_id):
        pool_props = self.get_pool_properties(pool_id) or {}
        return (pool_props.get("area_code", None) or "").lower() == "all"

    def lease_number(
        self,
        pool_id,
        request_context,
        target_number=None,
        target_area_codes=None,
        renew=False,
    ):
        request_context = request_context or {}
        start = time.time()
        number = None
        from_sid = False
        key_mismatch = False
        sid_number_mismatch = False
        request_sid = self._get_session_id(pool_id, request_context)

        # Flag if this is a pool that tries to choose a tracking number to match
        # the user's area code. Need to use special logic even if a target
        # area code is not specified.
        area_code_pool = self.is_area_code_pool(pool_id)

        dbg(f"{request_sid}: pool_id: {pool_id}, target number {target_number}")

        try:
            with self._get_pool_lock(pool_id):
                # HACK: ensure we are targeting the session number for renewal if one
                # exists. Roughly tries to enforce a single number per session.
                sid_number = self._get_session_number(pool_id, request_context)
                if sid_number:
                    if target_number and sid_number != target_number:
                        warn(
                            f"{request_sid}: Session / Target number mismatch: {sid_number} / {target_number}: {request_context}"
                        )
                        sid_number_mismatch = True
                    from_sid = True
                    renew = True
                    target_number = sid_number

                if target_number:
                    status, ctx = self.get_number_status(target_number, with_age=True)
                    if sid_number_mismatch:
                        # Additional logging to debug this case
                        warn(f"{request_sid}: target number {target_number} ctx: {ctx}")

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
                            # HACK: we can overwrite everything besides these dicts which need to be merged
                            # such that the new request_context values take precedence. We should
                            # probably change this to a more proper dict merge!
                            visits = ctx["request_context"].get("visits", None) or {}
                            visits.update(request_context.get("visits", None) or {})
                            request_context["visits"] = visits

                            latest_context = (
                                ctx["request_context"].get("latest_context", {}) or {}
                            )
                            latest_context.update(
                                request_context.get("latest_context", {}) or {}
                            )
                            request_context["latest_context"] = latest_context

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
                    if area_code_pool:
                        number = self._lease_area_code_number(
                            pool_id, request_context, target_area_codes
                        )
                    else:
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

    def update_number(self, pool_id, number, request_context, merge=False):
        start = time.time()
        request_sid = self._get_session_id(pool_id, request_context)

        dbg(
            f"{request_sid}: pool_id: {pool_id}, number {number}, request_context: {request_context}, merge: {merge}"
        )

        try:
            with self._get_pool_lock(pool_id):
                status, ctx = self.get_number_status(number)
                if not ctx:
                    warn(
                        f"{request_sid}: number {number} has no context, can not update"
                    )
                    return {}

                curr_request_ctx = ctx.get("request_context", {}) or {}
                curr_sid = self._get_session_id(pool_id, curr_request_ctx)
                if request_sid != curr_sid:
                    msg = f"session key mismatch for {pool_id}/{number} {request_sid}/{curr_sid}, can not update"
                    warn(msg)
                    return ctx

                if merge:
                    ctx["request_context"] = dictmerge(
                        curr_request_ctx, request_context, overwrite=True
                    )
                else:
                    ctx["request_context"] = request_context

                self.set_number_context(number, ctx)
        except LockError as e:
            raise NumberPoolUnavailable(f"Could not acquire pool {pool_id} lock")

        dbg(f"{request_sid}: took {time.time() - start:0.3f}s, number: {number}")
        return ctx

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

    def _get_pool_ip_key(self, pool_id):
        # TODO make this configurable per pool
        return POOL_IP_KEY

    def _get_session_ip(self, pool_id, request_context):
        key = self._get_pool_ip_key(pool_id)
        return request_context.get(key, None)

    def _get_pool_user_agent_key(self, pool_id):
        # TODO make this configurable per pool
        return POOL_USER_AGENT_KEY

    def _get_session_user_agent(self, pool_id, request_context):
        key = self._get_pool_user_agent_key(pool_id)
        return request_context.get(key, None)

    def _get_number_contexts(self, numbers, with_age=False):
        res = {}
        for number in numbers:
            res[number] = self.get_pool_number_context(number, with_age=with_age)
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
            ctx = self.get_pool_number_context(number)
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

        curr_context = self.get_pool_number_context(number)
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

    def _lease_area_code_number(self, pool_id, request_context, area_codes):
        fallback_area_code = self.get_pool_properties(pool_id).get(
            "fallback_area_code", None
        )
        raiseifnot(
            fallback_area_code, f"No fallback area code specified for pool {pool_id}"
        )
        if not area_codes:
            # This can happen if the area code pool is in use but we didn't have
            # enough info to target a specific area code. We still want to force
            # picking a number from the fallback area code.
            warn(f"Area code not specified, using fallback {fallback_area_code}")
            area_codes = [fallback_area_code]

        for area_code in area_codes:
            raiseifnot(
                isinstance(area_code, str)
                and len(area_code) == 3
                and area_code.isdigit(),
                f"Invalid area code: {area_code}",
            )

            pattern = f"{area_code}*"
            dbg(f"Searching for number with area code {area_code} in {pool_id}")

            for number in self.conn.sscan_iter(
                self._get_free_pool_name(pool_id), match=pattern, count=10
            ):
                leased_number = self._lease_free_number(
                    pool_id, number, request_context
                )
                if leased_number:
                    return leased_number

            dbg(f"No free number found for area code {area_code}, checking expired...")

            max_expired_tries = 3
            for number in self.conn.zrange(self._get_taken_pool_name(pool_id), 0, -1):
                if not number.startswith(area_code):
                    continue

                status, _ = self.get_number_status(number)
                if status != NumberStatus.EXPIRED:
                    dbg(
                        f"Least recently renewed taken number {number} for {area_code} is not expired. Stopping search!"
                    )
                    break

                dbg(f"Found expired number {number} matching area code {area_code}")
                leased_number = self._lease_expired_number(
                    pool_id, number, request_context
                )
                if leased_number:
                    return leased_number

                # This really shouldn't happen, but let it try a few times if needed
                max_expired_tries -= 1
                if max_expired_tries <= 0:
                    warn(
                        f"Max tries checking expired numbers for area code {area_code} in {pool_id}"
                    )
                    break

            dbg(f"No free or expired number found for area code {area_code}")

        # If we didn't find a number, try the fallback area code
        if fallback_area_code not in area_codes:
            # TODO: record stats in redis or db
            warn(
                f"Trying fallback area code {fallback_area_code}. Target was {area_codes}"
            )
            leased_number = self._lease_area_code_number(
                pool_id, request_context, [fallback_area_code]
            )
            if leased_number:
                return leased_number

        warn(f"No free number found with area code {area_code} in {pool_id}")
        return None

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
        ctx = self.get_pool_number_context(number)
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
        self._pool_properties_cache = {}
        info(f"Resetting {len(pools)} pools")
        for pool in pools:
            self.set_pool_properties(pool["id"], pool)
            self._reset_pool(pool["id"], preserve=preserve)
