from core.config import get_settings
from modules.auth import emails


def test_verification_email_carries_the_code_in_both_parts():
    message = emails.verification_email("a@example.com", "331242", "creator")
    assert "331242" in message.text and "331242" in message.html
    assert "Connect your account" in message.html


def test_brand_verification_gets_brand_steps_and_unknown_roles_get_none():
    brand = emails.verification_email("b@example.com", "123456", "organisation").html
    assert "Launch a campaign" in brand and "Connect your account" not in brand
    admin = emails.verification_email("c@example.com", "123456", "admin").html
    assert "What&#x27;s next" not in admin and "What's next" not in admin


def test_notification_email_escapes_user_text_and_absolutises_links():
    message = emails.notification_email("a@example.com", "<b>Hi</b>", "Tom & Jerry", "/dashboard/clips")
    assert "<b>Hi</b>" not in message.html and "&lt;b&gt;Hi&lt;/b&gt;" in message.html
    assert "Tom &amp; Jerry" in message.html
    url = f"{get_settings().app_url}/dashboard/clips"
    assert url in message.html and url in message.text
