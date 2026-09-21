from tests.http_app import api, signup  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _auth(body):
    return {"Authorization": f"Bearer {body['access_token']}"}


async def test_profile_defaults_then_updates(api):
    email, org = await signup(api, "organisation")
    r = await api.get("/organisations/me/profile", headers=_auth(org))
    assert r.status_code == 200
    out = r.json()
    assert out["name"] == "Test organisation"
    assert out["finance_email"] == email
    assert out["business_verified"] is False

    r = await api.put(
        "/organisations/me/profile",
        headers=_auth(org),
        json={"name": "Gbedu Records", "bio": "Independent Lagos music label.", "website": "gbedurecords.com",
              "finance_email": "finance@gbedurecords.com"},
    )
    out = r.json()
    assert out["name"] == "Gbedu Records" and out["finance_email"] == "finance@gbedurecords.com"
    # A partial update leaves the rest alone.
    r = await api.put("/organisations/me/profile", headers=_auth(org), json={"bio": "Lagos label."})
    assert r.json()["name"] == "Gbedu Records" and r.json()["bio"] == "Lagos label."


async def test_organisation_cannot_verify_its_own_business(api):
    _, org = await signup(api, "organisation")
    r = await api.put(
        "/organisations/me/profile", headers=_auth(org), json={"business_verified": True, "business_legal_name": "X Ltd"}
    )
    assert r.status_code == 200  # unknown fields are ignored, not applied
    assert r.json()["business_verified"] is False and r.json()["business_legal_name"] is None


async def test_onboarding_flags_the_user_and_stores_answers(api):
    _, org = await signup(api, "organisation")
    photo = (await api.post("/uploads/images", headers=_auth(org), files={"file": ("l.png", PNG, "image/png")})).json()["id"]
    r = await api.put(
        "/organisations/me/onboarding",
        headers=_auth(org),
        json={"name": "Indomie", "bio": "Instant noodles.", "photo_upload_id": photo,
              "production_workflow": "Agency partners", "team_size": "11–50 people",
              "campaign_goal": "Build awareness and recall", "budget_range": "₦250,000–₦750,000"},
    )
    assert r.status_code == 200
    out = r.json()
    assert out["name"] == "Indomie" and out["photo_url"] and out["budget_range"] == "₦250,000–₦750,000"
    assert (await api.get("/auth/me", headers=_auth(org))).json()["onboarding_completed"] is True


async def test_organisation_endpoints_are_organisation_only(api):
    _, cr = await signup(api, "creator")
    assert (await api.get("/organisations/me/profile", headers=_auth(cr))).status_code == 403
    assert (await api.put("/organisations/me/onboarding", headers=_auth(cr), json={"name": "Nope"})).status_code == 403


async def test_name_must_be_real(api):
    _, org = await signup(api, "organisation")
    assert (await api.put("/organisations/me/profile", headers=_auth(org), json={"name": "G"})).status_code == 422
