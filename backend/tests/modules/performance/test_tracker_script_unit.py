from modules.performance.router import tracker_script


async def test_tracker_script_is_public_first_party_attribution_code():
    response = await tracker_script()
    body = response.body.decode()

    assert response.media_type == "application/javascript"
    assert "window.ClippitTracking" in body
    assert "clippit_ref" in body
    assert "localStorage" in body
    assert "SameSite=Lax" in body
    assert "X-Clippit-Secret" not in body
