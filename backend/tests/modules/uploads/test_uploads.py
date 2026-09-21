import pytest

from core.config import get_settings
from tests.http_app import api, signup  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def _auth(body):
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    from core import storage

    monkeypatch.setattr(get_settings(), "storage_local_dir", str(tmp_path))
    storage.get_storage.cache_clear()
    yield
    storage.get_storage.cache_clear()


async def test_image_upload_returns_a_url_and_records_the_owner(api):
    _, body = await signup(api, "creator")
    r = await api.post("/uploads/images", headers=_auth(body), files={"file": ("me.png", PNG, "image/png")})
    assert r.status_code == 201
    out = r.json()
    assert out["kind"] == "image" and out["content_type"] == "image/png"
    assert out["url"].endswith(".png") and "/media/image/" in out["url"]
    assert out["size_bytes"] == len(PNG)


async def test_upload_type_is_sniffed_not_trusted(api):
    _, body = await signup(api, "creator")
    # Claims to be a PNG; the bytes are text.
    r = await api.post("/uploads/images", headers=_auth(body), files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 422


async def test_a_video_is_not_accepted_as_an_image(api):
    _, body = await signup(api, "creator")
    r = await api.post("/uploads/images", headers=_auth(body), files={"file": ("x.mp4", MP4, "video/mp4")})
    assert r.status_code == 422


async def test_video_upload_and_size_limit(api, monkeypatch):
    _, body = await signup(api, "creator")
    ok = await api.post("/uploads/videos", headers=_auth(body), files={"file": ("clip.mp4", MP4, "video/mp4")})
    assert ok.status_code == 201 and ok.json()["content_type"] == "video/mp4"

    monkeypatch.setattr(get_settings(), "max_video_bytes", 32)
    big = await api.post("/uploads/videos", headers=_auth(body), files={"file": ("clip.mp4", MP4, "video/mp4")})
    assert big.status_code == 413


async def test_oversized_upload_leaves_nothing_on_disk(api, tmp_path, monkeypatch):
    _, body = await signup(api, "creator")
    monkeypatch.setattr(get_settings(), "max_image_bytes", 16)
    r = await api.post("/uploads/images", headers=_auth(body), files={"file": ("x.png", PNG, "image/png")})
    assert r.status_code == 413
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


async def test_empty_file_is_rejected(api):
    _, body = await signup(api, "creator")
    r = await api.post("/uploads/images", headers=_auth(body), files={"file": ("x.png", b"", "image/png")})
    assert r.status_code == 422


async def test_evidence_accepts_image_or_video(api):
    _, body = await signup(api, "creator")
    for name, data, ctype in (("a.jpg", JPEG, "image/jpeg"), ("b.mp4", MP4, "video/mp4")):
        r = await api.post("/uploads/evidence", headers=_auth(body), files={"file": (name, data, ctype)})
        assert r.status_code == 201


async def test_uploads_require_a_session(api):
    r = await api.post("/uploads/images", files={"file": ("x.png", PNG, "image/png")})
    assert r.status_code == 401


async def test_uploaded_file_is_served(api):
    _, body = await signup(api, "creator")
    out = (await api.post("/uploads/images", headers=_auth(body), files={"file": ("me.png", PNG, "image/png")})).json()
    path = out["url"].split("/media/", 1)[1]
    served = await api.get(f"/media/{path}")
    assert served.status_code == 200 and served.content == PNG


def test_storage_refuses_paths_outside_its_root(tmp_path):
    from core.storage import LocalStorage

    storage = LocalStorage(str(tmp_path / "root"), "http://x")
    (tmp_path / "secret.txt").write_text("nope")
    assert storage.path_for("../secret.txt") is None
    assert storage.path_for("/etc/passwd") is None
    assert storage.path_for("image/missing.png") is None
