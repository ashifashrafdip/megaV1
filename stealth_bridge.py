"""Non-enumerable page bridge — keeps automation APIs off window enumeration."""

from __future__ import annotations

import json
import secrets


def create_bridge_token() -> str:
    return secrets.token_hex(16)


def bridge_ref(token: str) -> str:
    return f"window[{json.dumps(token)}]"


def js_bridge_present(token: str) -> str:
    return f"Boolean({bridge_ref(token)})"


def js_cam_ready(token: str) -> str:
    return f"Boolean({bridge_ref(token)}?.cam)"


def js_vid_tick(token: str) -> str:
    return (
        f"() => {bridge_ref(token)}?.vid?.tick?.() "
        f"|| {{ ok: false, phase: 'missing' }}"
    )


def js_vid_result(token: str) -> str:
    return (
        f"() => {bridge_ref(token)}?.vid?.result?.() "
        f"|| {{ status: 'pending' }}"
    )


def js_install_hub(token: str, *, guard: str, body: str) -> str:
    """Wrap injected script: skip if guard true; assign hub.cam or hub.vid."""
    token_json = json.dumps(token)
    return f"""
(() => {{
  const TOKEN = {token_json};
  {body}
}})();
"""


def js_define_hub(token: str, property_name: str, value_expr: str) -> str:
    token_json = json.dumps(token)
    prop_json = json.dumps(property_name)
    return f"""
{{
  let hub = window[TOKEN];
  if (!hub) hub = {{}};
  if (hub[{prop_json}]) return;
  hub[{prop_json}] = {value_expr};
  Object.defineProperty(window, TOKEN, {{
    value: hub,
    enumerable: false,
    configurable: false,
    writable: false,
  }});
}}
""".replace("TOKEN", token_json)
