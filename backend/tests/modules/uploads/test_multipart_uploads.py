"""Multipart uploads, upload status, and delete
(production-api-inventory.md §P). See core.storage.Storage's docstring:
this local backend simulates the contract with one part on our own disk,
not real signed R2 PUT URLs."""

import pytest

from core.config import get_settings
from tests.http_app import api, auth, campaign_body, fund_campaign, signup

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    from core import storage

    monkeypatch.setattr(get_settings(), "storage_local_dir", str(tmp_path))
    storage.get_storage.cache_clear()
    yield
    storage.get_storage.cache_clear()


async def test_a_multipart_video_upload_round_trips(api):
    _, creator = await signup(api, "creator")
    created = await api.post(
        "/uploads/multipart", headers=auth(creator),
        json={"kind": "video", "filename": "clip.mp4", "declared_size_bytes": len(MP4), "content_type": "video/mp4"},
    )
    assert created.status_code == 201
    body = created.json()
    upload_id = body["upload_id"]
    assert body["part_urls"] == [f"/uploads/multipart/{upload_id}/parts/1"]

    part = await api.put(f"/uploads/multipart/{upload_id}/parts/1", headers=auth(creator), files={"file": ("clip.mp4", MP4, "video/mp4")})
    assert part.status_code == 204

    completed = await api.post(f"/uploads/multipart/{upload_id}/complete", headers=auth(creator), json={"part_numbers": [1]})
    assert completed.status_code == 200
    out = completed.json()
    assert out["id"] == upload_id and out["content_type"] == "video/mp4" and out["size_bytes"] == len(MP4)

    status_check = await api.get(f"/uploads/{upload_id}", headers=auth(creator))
    assert status_check.json()["status"] == "ready"


async def test_completing_before_any_part_landed_fails_cleanly(api):
    _, creator = await signup(api, "creator")
    created = (await api.post(
        "/uploads/multipart", headers=auth(creator),
        json={"kind": "video", "filename": "clip.mp4", "declared_size_bytes": 100, "content_type": "video/mp4"},
    )).json()
    r = await api.post(f"/uploads/multipart/{created['upload_id']}/complete", headers=auth(creator), json={"part_numbers": [1]})
    assert r.status_code == 422
    status_check = (await api.get(f"/uploads/{created['upload_id']}", headers=auth(creator))).json()
    assert status_check["status"] == "failed"


async def test_a_declared_size_over_the_limit_is_refused_up_front(api):
    _, creator = await signup(api, "creator")
    huge = get_settings().max_video_bytes + 1
    r = await api.post(
        "/uploads/multipart", headers=auth(creator),
        json={"kind": "video", "filename": "clip.mp4", "declared_size_bytes": huge, "content_type": "video/mp4"},
    )
    assert r.status_code == 413


async def test_only_the_owner_can_upload_a_part_or_complete(api):
    _, creator = await signup(api, "creator")
    _, stranger = await signup(api, "creator")
    created = (await api.post(
        "/uploads/multipart", headers=auth(creator),
        json={"kind": "video", "filename": "clip.mp4", "declared_size_bytes": len(MP4), "content_type": "video/mp4"},
    )).json()

    denied_part = await api.put(
        f"/uploads/multipart/{created['upload_id']}/parts/1", headers=auth(stranger), files={"file": ("x.mp4", MP4, "video/mp4")}
    )
    assert denied_part.status_code == 404
    denied_complete = await api.post(
        f"/uploads/multipart/{created['upload_id']}/complete", headers=auth(stranger), json={"part_numbers": [1]}
    )
    assert denied_complete.status_code == 404


async def test_get_upload_hides_other_peoples_uploads(api):
    _, creator = await signup(api, "creator")
    _, stranger = await signup(api, "creator")
    out = (await api.post("/uploads/images", headers=auth(creator), files={"file": ("me.png", PNG, "image/png")})).json()
    r = await api.get(f"/uploads/{out['id']}", headers=auth(stranger))
    assert r.status_code == 404


async def test_deleting_an_unattached_upload_works_but_an_attached_one_is_refused(api):
    _, org = await signup(api, "organisation")
    cover = (await api.post("/uploads/images", headers=auth(org), files={"file": ("cover.png", PNG, "image/png")})).json()

    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body(cover_image_upload_id=cover["id"]))).json()
    attached = await api.delete(f"/uploads/{cover['id']}", headers=auth(org))
    assert attached.status_code == 409

    spare = (await api.post("/uploads/images", headers=auth(org), files={"file": ("spare.png", PNG, "image/png")})).json()
    freed = await api.delete(f"/uploads/{spare['id']}", headers=auth(org))
    assert freed.status_code == 204
    assert (await api.get(f"/uploads/{spare['id']}", headers=auth(org))).status_code == 404


async def test_support_attachment_upload_uses_the_evidence_pipeline(api):
    _, creator = await signup(api, "creator")
    r = await api.post("/uploads/support-attachments", headers=auth(creator), files={"file": ("proof.png", PNG, "image/png")})
    assert r.status_code == 201 and r.json()["kind"] == "evidence"


async def test_a_pending_multipart_upload_cannot_be_attached_to_anything(api):
    from tests.http_app import connect_account

    _, org = await signup(api, "organisation")
    campaign = (await api.post("/campaigns", headers=auth(org), json=campaign_body())).json()
    await fund_campaign(api, org, campaign["id"])
    _, creator = await signup(api, "creator")
    await connect_account(creator["user"]["id"], "tiktok", "@creator")

    created = (await api.post(
        "/uploads/multipart", headers=auth(creator),
        json={"kind": "video", "filename": "x.mp4", "declared_size_bytes": len(MP4), "content_type": "video/mp4"},
    )).json()
    r = await api.post(
        "/submissions", headers=auth(creator),
        json={"campaign_id": campaign["id"], "platform": "tiktok", "url": "https://tiktok.com/x", "video_upload_id": created["upload_id"]},
    )
    assert r.status_code == 422
