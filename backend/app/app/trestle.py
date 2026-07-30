import json
import re
import time

import requests
from tlbx import warn, st

from app.geo import zip_to_area_code_distance, zip_to_zip_distance


TRESTLE_API_URL = "https://api.trestleiq.com/3.1/caller_id"
TRESTLE_REQUEST_TIMEOUT = 1.0
TRESTLE_CACHE_TTL_SECONDS = 14 * 24 * 60 * 60
TRESTLE_CACHE_KEY_PREFIX = "trestle:caller"
TRESTLE_FROM_ZIP_DISTANCE_LIMIT_MILES = 25
TRESTLE_AREA_CODE_DISTANCE_LIMIT_MILES = 50
TRESTLE_AREA_CODE_ONLY_DISTANCE_LIMIT_MILES = 25

_CACHE_MISS = object()

TRESTLE_BELONGS_TO_KEYS = {
    "age_range",
    "firstname",
    "gender",
    "lastname",
    "link_to_phone_start_date",
    "middlename",
    "type",
}
TRESTLE_CURRENT_ADDRESS_KEYS = {
    "city",
    "country_code",
    "delivery_point",
    "is_active",
    "link_to_person_start_date",
    "location_type",
    "postal_code",
    "state_code",
    "street_line_1",
}
TRESTLE_TOP_LEVEL_KEYS = {
    "carrier",
    "is_commercial",
    "is_prepaid",
    "is_valid",
    "line_type",
}


def normalize_us_zip(zip_code):
    if zip_code is None:
        return None

    value = str(zip_code).strip()
    if not re.fullmatch(r"\d{5}(?:-?\d{4})?", value):
        return None
    return value[:5]


def filter_trestle_response(data):
    if not isinstance(data, dict):
        return None

    filtered = {key: data[key] for key in TRESTLE_TOP_LEVEL_KEYS if key in data}

    belongs_to = data.get("belongs_to")
    if isinstance(belongs_to, dict):
        filtered["belongs_to"] = {
            key: belongs_to[key] for key in TRESTLE_BELONGS_TO_KEYS if key in belongs_to
        }

    current_address = data.get("current_address")
    if isinstance(current_address, dict):
        filtered["current_address"] = {
            key: current_address[key]
            for key in TRESTLE_CURRENT_ADDRESS_KEYS
            if key in current_address
        }

    return filtered or None


def _get_cached_trestle_data(cache_conn, phone_number):
    if not cache_conn:
        return _CACHE_MISS

    try:
        value = cache_conn.get(f"{TRESTLE_CACHE_KEY_PREFIX}:{phone_number}")
        if value is None:
            return _CACHE_MISS
        return json.loads(value) or None
    except Exception as e:
        warn(f"Failed to read Trestle caller cache: {str(e)}")
        return _CACHE_MISS


def _set_cached_trestle_data(cache_conn, phone_number, data):
    if not cache_conn:
        return

    try:
        cache_conn.set(
            f"{TRESTLE_CACHE_KEY_PREFIX}:{phone_number}",
            json.dumps(data or {}),
            ex=TRESTLE_CACHE_TTL_SECONDS,
        )
    except Exception as e:
        warn(f"Failed to write Trestle caller cache: {str(e)}")


def get_trestle_lookup(phone_number, api_key, cache_conn=None):
    start = time.perf_counter()
    phone_number = "".join(ch for ch in str(phone_number) if ch.isdigit())
    if not phone_number or not api_key:
        return dict(
            data=None,
            status="not_configured",
            latency_ms=round((time.perf_counter() - start) * 1000),
            from_cache=False,
        )

    cached_data = _get_cached_trestle_data(cache_conn, phone_number)
    if cached_data is not _CACHE_MISS:
        return dict(
            data=cached_data,
            status="success" if cached_data else "no_result",
            latency_ms=round((time.perf_counter() - start) * 1000),
            from_cache=True,
        )

    try:
        response = requests.get(
            TRESTLE_API_URL,
            headers={"x-api-key": api_key},
            params={"phone": phone_number, "phone.country_hint": "US"},
            timeout=TRESTLE_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        response_data = response.json()
        if not isinstance(response_data, dict):
            return dict(
                data=None,
                status="invalid_response",
                latency_ms=round((time.perf_counter() - start) * 1000),
                from_cache=False,
            )
        data = filter_trestle_response(response_data)
        _set_cached_trestle_data(cache_conn, phone_number, data)
        status = "success" if data else "no_result"
    except requests.Timeout as e:
        warn(f"Trestle caller lookup timed out for {phone_number}: {str(e)}")
        data = None
        status = "timeout"
    except requests.HTTPError as e:
        warn(f"Trestle caller HTTP error for {phone_number}: {str(e)}")
        data = None
        status = "http_error"
    except requests.RequestException as e:
        warn(f"Trestle caller lookup failed for {phone_number}: {str(e)}")
        data = None
        status = "request_error"
    except (ValueError, AttributeError) as e:
        warn(f"Trestle caller response invalid for {phone_number}: {str(e)}")
        data = None
        status = "invalid_response"

    return dict(
        data=data,
        status=status,
        latency_ms=round((time.perf_counter() - start) * 1000),
        from_cache=False,
    )


def get_trestle_data(phone_number, api_key, cache_conn=None):
    lookup = get_trestle_lookup(phone_number, api_key, cache_conn=cache_conn)
    return lookup["data"]


def get_trestle_zip(phone_number, api_key, cache_conn=None):
    data = get_trestle_data(phone_number, api_key, cache_conn=cache_conn)
    current_address = (data or {}).get("current_address") or {}
    if current_address.get("location_type") != "Address":
        return None
    return normalize_us_zip(current_address.get("postal_code"))


def _zip_to_area_code_distance(zip_code, area_code):
    try:
        return zip_to_area_code_distance(zip_code, area_code)
    except Exception:
        return None


def _get_trestle_zip_trust(trestle_zip, from_zip, user_area_code):
    if not trestle_zip:
        return None, "invalid_zip"

    from_zip = normalize_us_zip(from_zip)
    if from_zip == trestle_zip:
        return trestle_zip, "exact_from_zip"

    trestle_area_code_distance = _zip_to_area_code_distance(trestle_zip, user_area_code)
    if from_zip is None:
        if (
            trestle_area_code_distance is not None
            and trestle_area_code_distance
            <= TRESTLE_AREA_CODE_ONLY_DISTANCE_LIMIT_MILES
        ):
            return trestle_zip, "nearby_area_code"
        return None, "conflicting_signals"

    from_area_code_distance = _zip_to_area_code_distance(from_zip, user_area_code)
    try:
        from_zip_distance = zip_to_zip_distance(trestle_zip, from_zip)
    except Exception:
        return None, "invalid_zip"

    if (
        from_zip_distance is not None
        and from_zip_distance <= TRESTLE_FROM_ZIP_DISTANCE_LIMIT_MILES
        and trestle_area_code_distance is not None
        and trestle_area_code_distance <= TRESTLE_AREA_CODE_DISTANCE_LIMIT_MILES
        and from_area_code_distance is not None
        and from_area_code_distance <= TRESTLE_AREA_CODE_DISTANCE_LIMIT_MILES
    ):
        return trestle_zip, "nearby_from_zip_and_area_code"
    return None, "conflicting_signals"


def _get_trusted_trestle_zip(trestle_zip, from_zip, user_area_code):
    trusted_zip, _ = _get_trestle_zip_trust(trestle_zip, from_zip, user_area_code)
    return trusted_zip


def get_trusted_trestle_zip(
    phone_number, from_zip, user_area_code, api_key, cache_conn=None
):
    trestle_zip = get_trestle_zip(phone_number, api_key, cache_conn=cache_conn)
    return _get_trusted_trestle_zip(trestle_zip, from_zip, user_area_code)


def get_trestle_enrichment(
    phone_number, from_zip, user_area_code, api_key, cache_conn=None
):
    lookup = get_trestle_lookup(phone_number, api_key, cache_conn=cache_conn)
    data = lookup["data"]
    current_address = (data or {}).get("current_address") or {}
    trestle_zip = None
    if current_address.get("location_type") == "Address":
        trestle_zip = normalize_us_zip(current_address.get("postal_code"))
    trusted_zip, trust_reason = _get_trestle_zip_trust(
        trestle_zip, from_zip, user_area_code
    )
    if lookup["status"] != "success":
        trust_reason = "not_applicable"
    return {
        **lookup,
        "trusted_zip": trusted_zip,
        "trust_reason": trust_reason,
    }
