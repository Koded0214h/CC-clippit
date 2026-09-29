"""Render every transactional email to HTML files for a visual check.

    python -m scripts.preview_emails            # writes ./var/email-preview/*.html
    python -m scripts.preview_emails --open     # ...and opens them
"""

import argparse
import subprocess
import sys
from pathlib import Path

from modules.auth import emails

SAMPLES = {
    "verification": emails.verification_email("tobi@example.com", "331242", "creator"),
    "recovery": emails.recovery_email("tobi@example.com", "804517"),
    "remember-device": emails.remember_device_email("tobi@example.com", "625190"),
    "admin-invite": emails.admin_invitation_email(
        "ops@example.com", "https://clippit.click/admin/invite?token=sample", "Adam Lawal"
    ),
    "notification": emails.notification_email(
        "tobi@example.com",
        "Your clip was approved",
        '"The main-character entrance" passed every requirement for No Long Thing. '
        "Views now count toward your earnings.",
        "/dashboard/submissions/approved?id=sample",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./var/email-preview")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, message in SAMPLES.items():
        path = out / f"{name}.html"
        path.write_text(message.html or "", encoding="utf-8")
        print(path.resolve())
        if args.open and sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)


if __name__ == "__main__":
    main()
