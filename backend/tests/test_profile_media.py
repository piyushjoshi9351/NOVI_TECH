"""LinkedIn-style profile media + About copy on PATCH /auth/me.

Covers persistence, validation of untrusted image payloads, link sanitising and
the "" clears / None leaves-alone contract the editor depends on.
"""
import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.core.database import get_db
from app.core.deps import _get_current_user


@pytest.fixture()
def client(db, user):
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[_get_current_user] = lambda: user
    return TestClient(app)


PNG = (
    "data:image/png;base64,"
    + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"payload-bytes" * 6).decode()
)
JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"x" * 40).decode()


def _patch(client, payload):
    return client.patch("/api/v1/auth/me", json=payload)


# ---------------------------------------------------------------- text fields

def test_saves_headline_about_and_location(client):
    r = _patch(client, {
        "headline": "Aspiring aerospace engineer",
        "about_me": "I love building rockets and breaking things.",
        "location": "Bengaluru, India",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["headline"] == "Aspiring aerospace engineer"
    assert body["about_me"].startswith("I love building rockets")
    assert body["location"] == "Bengaluru, India"


def test_text_fields_are_trimmed(client):
    body = _patch(client, {"headline": "  spaced  ", "about_me": "  hi  "}).json()
    assert body["headline"] == "spaced"
    assert body["about_me"] == "hi"


def test_empty_string_clears_a_field(client):
    _patch(client, {"about_me": "something", "headline": "keep me"})
    body = _patch(client, {"about_me": ""}).json()
    assert body["about_me"] is None
    assert body["headline"] == "keep me", "clearing one field must not wipe others"


def test_omitted_field_is_left_alone(client):
    _patch(client, {"about_me": "keep me", "location": "Delhi"})
    body = _patch(client, {"headline": "new"}).json()
    assert body["about_me"] == "keep me"
    assert body["location"] == "Delhi"


def test_about_me_length_is_capped(client):
    assert _patch(client, {"about_me": "x" * 2600}).status_code == 200
    assert _patch(client, {"about_me": "x" * 2601}).status_code == 422


def test_headline_length_is_capped(client):
    assert _patch(client, {"headline": "h" * 255}).status_code == 200
    assert _patch(client, {"headline": "h" * 256}).status_code == 422


# ---------------------------------------------------------------- media fields

def test_saves_profile_photo_and_banner(client):
    body = _patch(client, {"profile_photo": PNG, "banner_photo": JPEG}).json()
    assert body["profile_photo"] == PNG
    assert body["banner_photo"] == JPEG


def test_photo_survives_a_refetch(client):
    _patch(client, {"profile_photo": PNG})
    assert client.get("/api/v1/auth/me").json()["profile_photo"] == PNG


@pytest.mark.parametrize("mime", ["png", "jpeg", "gif", "webp"])
def test_allowed_image_types(client, mime):
    url = f"data:image/{mime};base64," + base64.b64encode(b"binary-bytes").decode()
    assert _patch(client, {"profile_photo": url}).status_code == 200


@pytest.mark.parametrize("bad", [
    "https://evil.example/x.png",       # remote fetch / SSRF + tracking
    "javascript:alert(1)",              # script injection
    "data:text/html;base64,PHNjcmlwdD4=",  # html payload
    "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",  # svg can carry script
    "not-an-image",
    "",
    "data:image/png,notbase64",
])
def test_rejects_unsafe_photo_payloads(client, bad):
    r = _patch(client, {"profile_photo": bad})
    if bad == "":
        assert r.status_code == 200
        assert client.get("/api/v1/auth/me").json()["profile_photo"] is None   # "" clears
    else:
        assert r.status_code == 422, bad
        # nothing was written
        assert client.get("/api/v1/auth/me").json()["profile_photo"] is None


def test_oversize_photo_is_rejected(client):
    huge = "data:image/png;base64," + "A" * (3 * 1024 * 1024)
    r = _patch(client, {"profile_photo": huge})
    assert r.status_code == 413
    assert client.get("/api/v1/auth/me").json()["profile_photo"] is None


def test_unsafe_payload_does_not_overwrite_a_good_photo(client):
    _patch(client, {"profile_photo": PNG})
    assert _patch(client, {"profile_photo": "javascript:alert(1)"}).status_code == 422
    assert client.get("/api/v1/auth/me").json()["profile_photo"] == PNG


# ---------------------------------------------------------------- links

def test_links_are_saved(client):
    body = _patch(client, {"links": [
        {"label": "Portfolio", "url": "https://me.test"},
        {"label": "GitHub", "url": "http://github.com/me"},
    ]}).json()
    assert body["links"] == [
        {"label": "Portfolio", "url": "https://me.test"},
        {"label": "GitHub", "url": "http://github.com/me"},
    ]


def test_non_http_link_urls_are_stripped(client):
    body = _patch(client, {"links": [
        {"label": "Evil", "url": "javascript:alert(1)"},
        {"label": "Data", "url": "data:text/html,<script>"},
    ]}).json()
    assert all(link["url"] == "" for link in body["links"])


def test_link_label_is_length_capped(client):
    body = _patch(client, {"links": [{"label": "L" * 500, "url": "https://x.test"}]}).json()
    assert len(body["links"][0]["label"]) == 60


def test_empty_links_list_clears(client):
    _patch(client, {"links": [{"label": "a", "url": "https://x.test"}]})
    assert _patch(client, {"links": []}).json()["links"] is None


# ---------------------------------------------------------------- isolation

def test_profile_media_is_per_user(db, client):
    from app.models.user import User
    mate = User(email="mate@test.local", password_hash="x", grade=9)
    db.add(mate)
    db.commit()
    _patch(client, {"about_me": "mine", "profile_photo": PNG})
    assert mate.profile_photo is None and mate.about_me is None


def test_existing_profile_fields_untouched_by_omission(client):
    _patch(client, {"first_name": "Ada", "grade": 11})
    body = _patch(client, {"about_me": "hello"}).json()
    assert body["first_name"] == "Ada"
    assert body["grade"] == 11
    assert body["about_me"] == "hello"