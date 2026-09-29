"""The shared Clippit shell for every customer-facing HTML email.

The markup intentionally stays table-based and mostly inline because inboxes
render a much smaller version of the web platform. The layout remains useful
with remote images, web fonts, media queries, and clipboard APIs disabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .config import get_settings

INK = "#151713"
LIME = "#b8ff38"
PAPER = "#f7f8f2"
WHITE = "#ffffff"
LINE = "#d8ddcf"
MUTED = "#60665a"

SANS = "'Geist','Helvetica Neue',Helvetica,Arial,sans-serif"
MONO = "'SF Mono','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"


@dataclass(frozen=True)
class Button:
    label: str
    url: str


def _asset(name: str) -> str:
    return f"{get_settings().app_url}/assets/{name}"


def absolute_link(link: str) -> str:
    return link if link.startswith(("http://", "https://")) else f"{get_settings().app_url}/{link.lstrip('/')}"


def _paragraphs(text: str, color: str = MUTED, size: int = 17) -> str:
    return "".join(
        f'<p style="margin:0 0 15px;font-family:{SANS};font-size:{size}px;line-height:1.58;color:{color};">'
        f"{escape(chunk).replace(chr(10), '<br>')}</p>"
        for chunk in text.split("\n\n")
        if chunk.strip()
    )


def _code_block(code: str, expires: str | None) -> str:
    safe_code = escape(code)
    # JavaScript is stripped by many mail clients. This handler is progressive
    # enhancement only; user-select:all keeps the code easy to copy without it.
    copy_script = (
        "if(navigator.clipboard){navigator.clipboard.writeText('"
        + safe_code
        + "');this.innerHTML='Copied &#10003;';}return false;"
    )
    expiry = escape(expires) if expires else "Use this code once"
    return f"""
      <tr><td class="content-pad" style="padding:18px 48px 12px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="border-collapse:separate;background:{INK};border:2px solid {INK};">
          <tr>
            <td width="14" style="width:14px;background:{LIME};font-size:0;line-height:0;">&nbsp;</td>
            <td class="code-main" style="padding:25px 24px 23px;">
              <p style="margin:0 0 8px;font-family:{SANS};font-size:12px;line-height:1.2;font-weight:700;color:#b6bbaf;">Verification code</p>
              <p id="clippit-code-{safe_code}" title="Select and copy this code"
                 style="margin:0;font-family:{MONO};font-size:42px;line-height:1;font-weight:700;letter-spacing:.18em;color:{WHITE};white-space:nowrap;-webkit-user-select:all;user-select:all;cursor:text;">{safe_code}</p>
              <p style="margin:11px 0 0;font-family:{SANS};font-size:12px;line-height:1.4;color:#b6bbaf;">
                <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{LIME};margin-right:7px;vertical-align:1px;"></span>{expiry}
              </p>
            </td>
            <td class="copy-cell" width="126" valign="middle" align="center"
                style="width:126px;padding:18px;border-left:1px dashed #52564e;">
              <a href="#clippit-code-{safe_code}" onclick="{copy_script}"
                 style="display:block;padding:13px 12px;background:{LIME};border:1px solid {LIME};font-family:{SANS};font-size:14px;line-height:1;font-weight:800;color:{INK};text-decoration:none;text-align:center;box-shadow:4px 4px 0 #000000;">Copy code</a>
              <p style="margin:12px 0 0;font-family:{SANS};font-size:10px;line-height:1.35;color:#b6bbaf;">Or tap the code<br>to select it</p>
            </td>
          </tr>
        </table>
      </td></tr>"""


def _button(button: Button) -> str:
    url = escape(button.url, quote=True)
    return f"""
      <tr><td class="content-pad" style="padding:18px 48px 10px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="background:{INK};box-shadow:5px 5px 0 {LIME};">
            <a href="{url}" target="_blank"
               style="display:inline-block;padding:16px 25px;font-family:{SANS};font-size:16px;line-height:1;font-weight:800;color:{WHITE};text-decoration:none;">{escape(button.label)}&nbsp;&nbsp;&#8599;</a>
          </td>
        </tr></table>
        <p style="margin:19px 0 0;font-family:{SANS};font-size:12px;line-height:1.5;color:{MUTED};">
          If the button does not open, copy this address into your browser:<br>
          <a href="{url}" style="color:{INK};word-break:break-all;text-decoration:underline;text-underline-offset:3px;">{escape(button.url)}</a></p>
      </td></tr>"""


def _steps(title: str, steps: list[tuple[str, str]]) -> str:
    rows = "".join(
        f"""
          <tr>
            <td valign="top" width="38" style="width:38px;padding:17px 0;border-top:1px solid {LINE};">
              <span style="display:inline-block;width:25px;height:25px;line-height:25px;background:{INK};text-align:center;font-family:{SANS};font-size:12px;font-weight:800;color:{LIME};">{i}</span>
            </td>
            <td valign="top" style="padding:17px 0 17px 8px;border-top:1px solid {LINE};">
              <p style="margin:0;font-family:{SANS};font-size:15px;font-weight:800;line-height:1.35;color:{INK};">{escape(head)}</p>
              <p style="margin:4px 0 0;font-family:{SANS};font-size:13px;line-height:1.5;color:{MUTED};">{escape(detail)}</p>
            </td>
          </tr>"""
        for i, (head, detail) in enumerate(steps, start=1)
    )
    return f"""
      <tr><td class="content-pad" style="padding:27px 48px 3px;">
        <p style="margin:0 0 11px;font-family:{SANS};font-size:13px;font-weight:800;line-height:1.3;color:{INK};">{escape(title)}</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>
      </td></tr>"""


def _note(note: str) -> str:
    return f"""
      <tr><td class="content-pad" style="padding:24px 48px 5px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td width="34" valign="top" style="width:34px;padding-top:1px;">
              <span style="display:inline-block;width:24px;height:24px;line-height:24px;border:1px solid {INK};text-align:center;font-family:{SANS};font-size:13px;font-weight:800;color:{INK};">!</span>
            </td>
            <td style="font-family:{SANS};font-size:13px;line-height:1.55;color:{MUTED};">
              <strong style="display:block;margin-bottom:2px;color:{INK};">Keep your account safe</strong>{escape(note)}
            </td>
          </tr>
        </table>
      </td></tr>"""


def render(
    *,
    tag: str,
    eyebrow: str,
    title: str,
    intro: str = "",
    code: str | None = None,
    expires: str | None = None,
    button: Button | None = None,
    steps: list[tuple[str, str]] | None = None,
    steps_title: str = "What happens next",
    note: str | None = None,
    preheader: str = "",
    reason: str = "You are receiving this because this address is registered on Clippit.",
) -> str:
    """Render one resilient, branded email document."""
    site = get_settings().app_url
    intro_html = _paragraphs(intro)
    parts = [
        f'<tr><td class="content-pad" style="padding:0 48px 5px;">{intro_html}</td></tr>' if intro_html else "",
        _code_block(code, expires) if code else "",
        _button(button) if button else "",
        _steps(steps_title, steps) if steps else "",
        _note(note) if note else "",
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  @media only screen and (max-width:620px) {{
    .email-wrap {{ padding:0 !important; }}
    .email-sheet {{ width:100% !important; }}
    .header-pad {{ padding:20px 22px !important; }}
    .hero-pad {{ padding:34px 24px 8px !important; }}
    .content-pad {{ padding-left:24px !important;padding-right:24px !important; }}
    .email-title {{ font-size:34px !important;line-height:1.05 !important; }}
    .code-main {{ padding:22px 15px 21px !important; }}
    .code-main p[id] {{ font-size:31px !important;letter-spacing:.12em !important; }}
    .copy-cell {{ width:98px !important;padding:12px 10px !important; }}
    .copy-cell a {{ padding:12px 6px !important;font-size:12px !important;box-shadow:3px 3px 0 #000000 !important; }}
    .copy-cell p {{ font-size:9px !important; }}
    .footer-copy {{ display:block !important;width:100% !important;padding-bottom:18px !important; }}
    .footer-mark {{ display:block !important;width:100% !important;text-align:left !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{PAPER};-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape(preheader)}&#8199;&#65279;&#847;&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{PAPER};">
  <tr><td class="email-wrap" align="center" style="padding:38px 14px 32px;">
    <table class="email-sheet" role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
           style="width:100%;max-width:600px;background:{WHITE};border-top:7px solid {LIME};border-bottom:2px solid {INK};">

      <tr><td class="header-pad" style="background:{INK};padding:23px 30px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td valign="middle">
            <a href="{site}" target="_blank" style="text-decoration:none;white-space:nowrap;">
              <img src="{_asset('clippit-mark-light.png')}" width="38" height="38" alt=""
                   style="display:inline-block;vertical-align:middle;border:0;outline:none;">
              <span style="display:inline-block;vertical-align:middle;margin-left:10px;font-family:{SANS};font-size:23px;font-weight:800;letter-spacing:-.04em;color:{WHITE};">Clippit</span>
            </a>
          </td>
          <td valign="middle" align="right">
            <span style="display:inline-block;padding:7px 10px;border:1px solid #62675e;font-family:{SANS};font-size:11px;line-height:1;font-weight:700;color:#dce1d7;">{escape(tag)}</span>
          </td>
        </tr></table>
      </td></tr>

      <tr><td class="hero-pad" style="padding:43px 48px 9px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td width="18" valign="middle" style="width:18px;"><span style="display:block;width:8px;height:8px;background:{LIME};border:1px solid {INK};"></span></td>
          <td style="font-family:{SANS};font-size:13px;line-height:1.2;font-weight:700;color:{MUTED};">{escape(eyebrow)}</td>
        </tr></table>
        <h1 class="email-title" style="margin:15px 0 18px;font-family:{SANS};font-size:42px;line-height:1.04;font-weight:800;letter-spacing:-.045em;color:{INK};">{escape(title)}</h1>
      </td></tr>
      {''.join(part for part in parts if part)}

      <tr><td class="content-pad" style="padding:36px 48px 0;"><div style="height:1px;background:{LINE};line-height:1px;font-size:0;">&nbsp;</div></td></tr>
      <tr><td class="content-pad" style="padding:22px 48px 31px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td class="footer-copy" valign="top" style="font-family:{SANS};font-size:12px;line-height:1.6;color:{MUTED};">
            <strong style="font-size:13px;color:{INK};">Clippit</strong><br>
            <a href="{site}" style="color:{MUTED};text-decoration:underline;text-underline-offset:3px;">Open Clippit</a>
            &nbsp;&nbsp;<a href="{site}/help" style="color:{MUTED};text-decoration:underline;text-underline-offset:3px;">Help</a>
            &nbsp;&nbsp;<a href="{site}/legal/privacy" style="color:{MUTED};text-decoration:underline;text-underline-offset:3px;">Privacy</a>
          </td>
          <td class="footer-mark" valign="top" align="right" width="48">
            <img src="{_asset('clippit-mark.png')}" width="38" height="38" alt="Clippit" style="display:inline-block;border:0;outline:none;">
          </td>
        </tr></table>
      </td></tr>
    </table>

    <p style="max-width:550px;margin:18px auto 0;padding:0 20px;font-family:{SANS};font-size:11px;line-height:1.55;color:#7d8376;text-align:center;">
      {escape(reason)}<br>&copy; Clippit</p>
  </td></tr>
</table>
</body>
</html>"""
