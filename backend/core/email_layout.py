"""The one branded HTML shell every Clippit email is rendered into.

Email clients ignore <style> blocks and modern layout inconsistently, so
this is table-based with inline styles only. Images are hot-linked from
the live site; the text still reads correctly with images blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .config import get_settings

INK = "#151713"
LIME = "#b8ff38"
PAPER = "#f7f8f2"
LINE = "#dce2d2"
MUTED = "#61665a"
SOFT = "#eef2e6"

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


def _paragraphs(text: str, color: str = MUTED, size: int = 16) -> str:
    return "".join(
        f'<p style="margin:0 0 14px;font-family:{SANS};font-size:{size}px;line-height:1.6;color:{color};">'
        f"{escape(chunk).replace(chr(10), '<br>')}</p>"
        for chunk in text.split("\n\n")
        if chunk.strip()
    )


def _code_block(code: str, expires: str | None) -> str:
    expiry = (
        f'<p style="margin:14px 0 0;font-family:{SANS};font-size:13px;line-height:1.4;color:#a9ae9f;">'
        f'<span style="display:inline-block;width:7px;height:7px;border-radius:7px;background:{LIME};'
        f'margin-right:8px;vertical-align:1px;"></span>{escape(expires)}</p>'
        if expires
        else ""
    )
    return f"""
      <tr><td style="padding:10px 40px 6px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="background:{INK};border-radius:18px;">
          <tr><td align="center" style="padding:30px 20px 28px;">
            <p style="margin:0 0 12px;font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#8d9384;">Your code</p>
            <p style="margin:0;font-family:{MONO};font-size:44px;line-height:1;font-weight:700;letter-spacing:.22em;color:{LIME};padding-left:.22em;">{escape(code)}</p>
            {expiry}
          </td></tr>
        </table>
      </td></tr>"""


def _button(button: Button) -> str:
    return f"""
      <tr><td style="padding:10px 40px 6px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td style="background:{LIME};border-radius:999px;border:2px solid {INK};">
            <a href="{escape(button.url, quote=True)}" target="_blank"
               style="display:inline-block;padding:15px 28px;font-family:{SANS};font-size:16px;font-weight:700;color:{INK};text-decoration:none;">{escape(button.label)}&nbsp;&nbsp;&rarr;</a>
          </td>
        </tr></table>
        <p style="margin:14px 0 0;font-family:{SANS};font-size:12px;line-height:1.5;color:{MUTED};">
          Button not working? Paste this into your browser:<br>
          <a href="{escape(button.url, quote=True)}" style="color:{INK};word-break:break-all;">{escape(button.url)}</a></p>
      </td></tr>"""


def _steps(title: str, steps: list[tuple[str, str]]) -> str:
    rows = "".join(
        f"""
          <tr>
            <td valign="top" width="40" style="padding:14px 0 14px 18px;">
              <span style="display:inline-block;width:26px;height:26px;line-height:26px;border-radius:26px;background:{LIME};border:1.5px solid {INK};text-align:center;font-family:{SANS};font-size:12px;font-weight:800;color:{INK};">{i}</span>
            </td>
            <td valign="top" style="padding:14px 18px 14px 12px;{'border-bottom:1px solid ' + LINE + ';' if i < len(steps) else ''}">
              <p style="margin:0;font-family:{SANS};font-size:15px;font-weight:700;line-height:1.35;color:{INK};">{escape(head)}</p>
              <p style="margin:3px 0 0;font-family:{SANS};font-size:13px;line-height:1.5;color:{MUTED};">{escape(detail)}</p>
            </td>
          </tr>"""
        for i, (head, detail) in enumerate(steps, start=1)
    )
    return f"""
      <tr><td style="padding:24px 40px 4px;">
        <p style="margin:0 0 10px;font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:{MUTED};">{escape(title)}</p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="border:1px solid {LINE};border-radius:16px;background:#fbfcf8;">{rows}
        </table>
      </td></tr>"""


def _note(note: str) -> str:
    lead, _, rest = note.partition(" — ")
    if rest and not lead.endswith(("?", ".", "!")):
        lead += "."
    body = f"<strong style=\"color:{INK};\">{escape(lead)}</strong> {escape(rest)}" if rest else escape(note)
    return f"""
      <tr><td style="padding:22px 40px 8px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="background:{SOFT};border-radius:14px;border-left:4px solid {LIME};">
          <tr><td style="padding:16px 18px;font-family:{SANS};font-size:14px;line-height:1.55;color:{MUTED};">{body}</td></tr>
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
    steps_title: str = "What's next",
    note: str | None = None,
    preheader: str = "",
    reason: str = "You're receiving this because this address is registered on Clippit.",
) -> str:
    """`note` renders its text before " — " in bold, as a lead-in."""
    site = get_settings().app_url
    parts = [
        _paragraphs(intro) and f'<tr><td style="padding:0 40px 8px;">{_paragraphs(intro)}</td></tr>',
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
</head>
<body style="margin:0;padding:0;background:{PAPER};-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape(preheader)}&#8199;&#65279;&#847;&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{PAPER};">
  <tr><td align="center" style="padding:36px 14px 28px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="max-width:560px;background:#ffffff;border-radius:22px;border:1px solid {LINE};overflow:hidden;">

      <tr><td style="background:{INK};padding:22px 28px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td valign="middle">
            <a href="{site}" target="_blank" style="text-decoration:none;">
              <img src="{_asset('clippit-mark-light.png')}" width="36" height="36" alt=""
                   style="display:inline-block;vertical-align:middle;border:0;">
              <span style="display:inline-block;vertical-align:middle;margin-left:10px;font-family:{SANS};font-size:22px;font-weight:800;letter-spacing:-.03em;color:#ffffff;">Clippit</span>
            </a>
          </td>
          <td valign="middle" align="right">
            <span style="display:inline-block;background:{LIME};color:{INK};border-radius:999px;padding:7px 12px;font-family:{SANS};font-size:10px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;">{escape(tag)}</span>
          </td>
        </tr></table>
      </td></tr>
      <tr><td style="height:5px;line-height:5px;font-size:0;background:{LIME};">&nbsp;</td></tr>

      <tr><td style="padding:38px 40px 6px;">
        <p style="margin:0 0 14px;font-family:{SANS};font-size:12px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:{MUTED};">
          <span style="display:inline-block;width:8px;height:8px;border-radius:8px;background:{LIME};border:1.5px solid {INK};margin-right:8px;vertical-align:0;"></span>{escape(eyebrow)}</p>
        <h1 style="margin:0 0 16px;font-family:{SANS};font-size:32px;line-height:1.12;font-weight:800;letter-spacing:-.035em;color:{INK};">{escape(title)}</h1>
      </td></tr>
      {''.join(p for p in parts if p)}

      <tr><td style="padding:30px 40px 0;"><div style="height:1px;background:{LINE};line-height:1px;font-size:0;">&nbsp;</div></td></tr>
      <tr><td style="padding:22px 40px 30px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
          <td valign="middle" style="font-family:{SANS};font-size:13px;line-height:1.5;color:{MUTED};">
            <strong style="color:{INK};">Post clips. Get paid for verified views.</strong><br>
            <a href="{site}" style="color:{MUTED};text-decoration:underline;">clippit.click</a>
            &nbsp;&middot;&nbsp;<a href="{site}/help" style="color:{MUTED};text-decoration:underline;">Help</a>
            &nbsp;&middot;&nbsp;<a href="{site}/legal/privacy" style="color:{MUTED};text-decoration:underline;">Privacy</a>
          </td>
          <td valign="middle" align="right" width="44">
            <img src="{_asset('clippit-mark.png')}" width="34" height="34" alt="Clippit" style="display:block;border:0;">
          </td>
        </tr></table>
      </td></tr>
    </table>

    <p style="max-width:520px;margin:18px auto 0;font-family:{SANS};font-size:12px;line-height:1.5;color:#8d9384;text-align:center;">
      {escape(reason)}<br>&copy; Clippit</p>
  </td></tr>
</table>
</body>
</html>"""
