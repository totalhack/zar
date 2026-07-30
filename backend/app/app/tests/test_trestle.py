import json

from app import trestle


class FakeCache:
    def __init__(self):
        self.storage = {}
        self.expirations = {}

    def get(self, key):
        return self.storage.get(key)

    def set(self, key, value, ex=None):
        self.storage[key] = value
        self.expirations[key] = ex


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "belongs_to": {
                "age_range": "30-35",
                "alternate_names": [],
                "firstname": "Avery",
                "gender": "X",
                "id": "Person.synthetic-test-id",
                "industry": None,
                "lastname": "Example",
                "link_to_phone_start_date": "2020-01-01",
                "middlename": "Test",
                "name": "Avery Test Example",
                "type": "Person",
            },
            "carrier": "Example Wireless",
            "current_address": {
                "city": "Exampleville",
                "country_code": "US",
                "delivery_point": "SingleUnit",
                "id": "Location.synthetic-test-id",
                "is_active": None,
                "lat_long": {
                    "accuracy": "RoofTop",
                    "latitude": 0.0,
                    "longitude": 0.0,
                },
                "link_to_person_start_date": "2024-01-01",
                "location_type": "Address",
                "postal_code": "02903-0001",
                "state_code": "RI",
                "street_line_1": "100 Example Ave",
                "street_line_2": None,
                "zip4": "0001",
            },
            "emails": ["person@example.test"],
            "id": "Phone.synthetic-test-id",
            "is_commercial": False,
            "is_prepaid": False,
            "is_valid": True,
            "line_type": "Mobile",
            "phone_number": "+12025550100",
        }


EXPECTED_TRESTLE_DATA = {
    "belongs_to": {
        "age_range": "30-35",
        "firstname": "Avery",
        "gender": "X",
        "lastname": "Example",
        "link_to_phone_start_date": "2020-01-01",
        "middlename": "Test",
        "type": "Person",
    },
    "carrier": "Example Wireless",
    "current_address": {
        "city": "Exampleville",
        "country_code": "US",
        "delivery_point": "SingleUnit",
        "is_active": None,
        "link_to_person_start_date": "2024-01-01",
        "location_type": "Address",
        "postal_code": "02903-0001",
        "state_code": "RI",
        "street_line_1": "100 Example Ave",
    },
    "is_commercial": False,
    "is_prepaid": False,
    "is_valid": True,
    "line_type": "Mobile",
}


def test_get_trestle_zip_uses_cached_normalized_result(monkeypatch):
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append((url, headers, params, timeout))
        return FakeResponse()

    monkeypatch.setattr(trestle.requests, "get", fake_get)
    cache = FakeCache()

    assert trestle.get_trestle_zip("+1 (401) 555-0100", "secret", cache) == "02903"
    assert trestle.get_trestle_zip("14015550100", "secret", cache) == "02903"
    assert len(calls) == 1
    assert calls[0][1] == {"x-api-key": "secret"}
    assert calls[0][2] == {
        "phone": "14015550100",
        "phone.country_hint": "US",
    }
    assert calls[0][3] == trestle.TRESTLE_REQUEST_TIMEOUT
    cache_key = f"{trestle.TRESTLE_CACHE_KEY_PREFIX}:14015550100"
    assert cache.expirations[cache_key] == trestle.TRESTLE_CACHE_TTL_SECONDS
    assert json.loads(cache.storage[cache_key]) == EXPECTED_TRESTLE_DATA


def test_filter_trestle_response_keeps_only_allowed_fields():
    assert (
        trestle.filter_trestle_response(FakeResponse().json()) == EXPECTED_TRESTLE_DATA
    )


def test_get_trestle_lookup_marks_cached_results(monkeypatch):
    monkeypatch.setattr(trestle.requests, "get", lambda *args, **kwargs: FakeResponse())
    cache = FakeCache()

    first = trestle.get_trestle_lookup("14015550100", "secret", cache)
    second = trestle.get_trestle_lookup("14015550100", "secret", cache)

    assert first["status"] == "success"
    assert first["from_cache"] is False
    assert second["status"] == "success"
    assert second["from_cache"] is True
    assert second["data"] == EXPECTED_TRESTLE_DATA


def test_trusted_trestle_zip_accepts_exact_from_zip_match(monkeypatch):
    monkeypatch.setattr(trestle, "get_trestle_zip", lambda *args, **kwargs: "02903")

    assert (
        trestle.get_trusted_trestle_zip("4015550100", "02903-0001", "401", "secret")
        == "02903"
    )


def test_trusted_trestle_zip_accepts_nearby_corroborating_signals(monkeypatch):
    monkeypatch.setattr(trestle, "get_trestle_zip", lambda *args, **kwargs: "02903")
    monkeypatch.setattr(trestle, "zip_to_zip_distance", lambda *args: 10)
    monkeypatch.setattr(trestle, "_zip_to_area_code_distance", lambda *args: 30)

    assert (
        trestle.get_trusted_trestle_zip("4015550100", "02904", "401", "secret")
        == "02903"
    )


def test_trusted_trestle_zip_rejects_conflicting_from_zip(monkeypatch):
    monkeypatch.setattr(trestle, "get_trestle_zip", lambda *args, **kwargs: "02903")
    monkeypatch.setattr(trestle, "zip_to_zip_distance", lambda *args: 100)
    monkeypatch.setattr(trestle, "_zip_to_area_code_distance", lambda *args: 10)

    assert (
        trestle.get_trusted_trestle_zip("4015550100", "90210", "401", "secret") is None
    )


def test_trusted_trestle_zip_accepts_close_area_code_without_from_zip(monkeypatch):
    monkeypatch.setattr(trestle, "get_trestle_zip", lambda *args, **kwargs: "02903")
    monkeypatch.setattr(trestle, "_zip_to_area_code_distance", lambda *args: 20)

    assert (
        trestle.get_trusted_trestle_zip("4015550100", None, "401", "secret") == "02903"
    )


def test_trusted_trestle_zip_rejects_distant_area_code_without_from_zip(
    monkeypatch,
):
    monkeypatch.setattr(trestle, "get_trestle_zip", lambda *args, **kwargs: "02903")
    monkeypatch.setattr(trestle, "_zip_to_area_code_distance", lambda *args: 30)

    assert trestle.get_trusted_trestle_zip("4015550100", None, "401", "secret") is None
