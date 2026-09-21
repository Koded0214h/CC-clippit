from tests.http_app import api, signup  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _auth(body):
    return {"Authorization": f"Bearer {body['access_token']}"}


async def _photo(api, body) -> str:
    r = await api.post("/uploads/images", headers=_auth(body), files={"file": ("p.png", PNG, "image/png")})
    return r.json()["id"]


async def test_creator_onboarding_saves_answers_and_flags_the_user(api):
    _, body = await signup(api, "creator")
    assert body["user"]["onboarding_completed"] is False
    photo_id = await _photo(api, body)

    r = await api.put(
        "/creators/me/onboarding",
        headers=_auth(body),
        json={
            "display_name": "Tobi On Cam",
            "interests": ["Comedy", "Food", "Comedy"],
            "platforms": ["tiktok", "instagram"],
            "photo_upload_id": photo_id,
            "discovery_source": "TikTok or Instagram",
            "experience": "I publish consistently",
            "goals": ["Earn from what I already make"],
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["display_name"] == "Tobi On Cam"
    assert out["interests"] == ["Comedy", "Food"]  # de-duplicated
    assert out["platforms"] == ["tiktok", "instagram"]
    assert out["photo_url"] and out["onboarding_completed"] is True

    me = await api.get("/auth/me", headers=_auth(body))
    assert me.json()["onboarding_completed"] is True


async def test_onboarding_needs_a_name_and_a_lane(api):
    _, body = await signup(api, "creator")
    assert (await api.put("/creators/me/onboarding", headers=_auth(body), json={"display_name": "T", "interests": ["x"]})).status_code == 422
    assert (await api.put("/creators/me/onboarding", headers=_auth(body), json={"display_name": "Tobi", "interests": []})).status_code == 422
    assert (await api.put("/creators/me/onboarding", headers=_auth(body), json={"display_name": "Tobi", "interests": ["  "]})).status_code == 422


async def test_onboarding_is_creator_only_and_can_be_repeated(api):
    _, org = await signup(api, "organisation")
    r = await api.put("/creators/me/onboarding", headers=_auth(org), json={"display_name": "Tobi", "interests": ["Comedy"]})
    assert r.status_code == 403

    _, cr = await signup(api, "creator")
    payload = {"display_name": "Tobi", "interests": ["Comedy"]}
    assert (await api.put("/creators/me/onboarding", headers=_auth(cr), json=payload)).status_code == 200
    payload["interests"] = ["Music"]
    again = await api.put("/creators/me/onboarding", headers=_auth(cr), json=payload)
    assert again.json()["interests"] == ["Music"]


async def test_cannot_use_someone_elses_upload_as_a_photo(api):
    _, alice = await signup(api, "creator")
    _, bob = await signup(api, "creator")
    alices_photo = await _photo(api, alice)
    r = await api.put(
        "/creators/me/onboarding",
        headers=_auth(bob),
        json={"display_name": "Bob", "interests": ["Comedy"], "photo_upload_id": alices_photo},
    )
    assert r.status_code == 422


async def test_cannot_use_a_video_as_a_photo(api):
    _, body = await signup(api, "creator")
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
    vid = (await api.post("/uploads/videos", headers=_auth(body), files={"file": ("a.mp4", mp4, "video/mp4")})).json()["id"]
    r = await api.put(
        "/creators/me/onboarding",
        headers=_auth(body),
        json={"display_name": "Tobi", "interests": ["Comedy"], "photo_upload_id": vid},
    )
    assert r.status_code == 422


async def test_profile_defaults_to_signup_name_and_updates_partially(api):
    _, body = await signup(api, "creator")
    first = await api.get("/creators/me/profile", headers=_auth(body))
    assert first.status_code == 200 and first.json()["display_name"] == "Test creator"

    r = await api.put("/creators/me/profile", headers=_auth(body), json={"bio": "Skits about food."})
    assert r.json()["bio"] == "Skits about food." and r.json()["display_name"] == "Test creator"
    r = await api.put("/creators/me/profile", headers=_auth(body), json={"display_name": "Tobi On Cam"})
    assert r.json()["display_name"] == "Tobi On Cam" and r.json()["bio"] == "Skits about food."


async def test_profile_rejects_overlong_bio(api):
    _, body = await signup(api, "creator")
    r = await api.put("/creators/me/profile", headers=_auth(body), json={"bio": "x" * 241})
    assert r.status_code == 422
