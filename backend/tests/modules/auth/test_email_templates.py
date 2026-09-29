from core.config import get_settings
from modules.auth import emails


def test_verification_email_carries_the_code_in_both_parts():
    message = emails.verification_email("a@example.com", "331242", "creator")
    assert "331242" in message.text and "331242" in message.html
    assert "Complete your profile" in message.html
    assert "Copy code" in message.html
    assert "navigator.clipboard.writeText('331242')" in message.html
    assert "user-select:all" in message.html


def test_brand_verification_gets_brand_steps_and_unknown_roles_get_none():
    brand = emails.verification_email("b@example.com", "123456", "organisation").html
    assert "Create a campaign" in brand and "Complete your profile" not in brand
    admin = emails.verification_email("c@example.com", "123456", "admin").html
    assert "What happens next" not in admin


def test_all_code_emails_use_the_shared_copyable_code_strip():
    messages = [
        emails.verification_email("a@example.com", "331242", "creator"),
        emails.recovery_email("a@example.com", "804517"),
        emails.remember_device_email("a@example.com", "625190"),
    ]
    for message in messages:
        assert "Copy code" in message.html
        assert "Verification code" in message.html
        assert "user-select:all" in message.html


def test_notification_email_escapes_user_text_and_absolutises_links():
    message = emails.notification_email("a@example.com", "<b>Hi</b>", "Tom & Jerry", "/dashboard/clips")
    assert "<b>Hi</b>" not in message.html and "&lt;b&gt;Hi&lt;/b&gt;" in message.html
    assert "Tom &amp; Jerry" in message.html
    url = f"{get_settings().app_url}/dashboard/clips"
    assert url in message.html and url in message.text
