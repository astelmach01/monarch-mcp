import base64
import hashlib
import hmac
import os
import struct
import time
from calendar import monthrange
from datetime import date

import httpx

GRAPHQL_URL = "https://api.monarch.com/graphql"
LOGIN_URL = "https://api.monarch.com/auth/login/"

_state = {
    "token": os.environ.get("MONARCH_TOKEN", ""),
}


def _headers() -> dict:
    return {
        "authorization": f"Token {_state['token']}",
        "content-type": "application/json",
        "monarch-client": "monarch-mcp-server",
        "monarch-client-version": "v1.0.1715",
        "client-platform": "web",
        "origin": "https://app.monarch.com",
    }


def _totp() -> str | None:
    secret = os.environ.get("MONARCH_TOTP_SECRET", "")
    if not secret:
        return None
    key = base64.b32decode(secret.upper())
    msg = struct.pack(">Q", int(time.time()) // 30)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0xF
    code = (struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


async def login_with_stored_credentials() -> str:
    """Re-authenticate using stored credentials and return new token."""
    email = os.environ.get("MONARCH_EMAIL", "")
    password = os.environ.get("MONARCH_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "MONARCH_TOKEN expired and MONARCH_EMAIL/MONARCH_PASSWORD not set. "
            "Cannot re-authenticate. Please update MONARCH_TOKEN in your .env file."
        )

    login_headers = {
        "content-type": "application/json",
        "client-platform": "web",
    }
    base_body = {
        "username": email,
        "password": password,
        "supports_mfa": True,
        "trusted_device": True,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(LOGIN_URL, headers=login_headers, json=base_body, timeout=30)

        if resp.status_code == 403:
            totp_code = _totp()
            if not totp_code:
                raise RuntimeError("MFA required but MONARCH_TOTP_SECRET not set.")
            resp = await client.post(
                LOGIN_URL,
                headers=login_headers,
                json={**base_body, "totp": totp_code},
                timeout=30,
            )

        resp.raise_for_status()
        data = resp.json()

    token = data.get("token")
    if not token:
        raise RuntimeError(f"Login failed - no token in response: {data}")

    _state["token"] = token
    write_env_values({"MONARCH_TOKEN": token})
    return token


async def query(operation_name: str, query_text: str, variables: dict | None = None) -> dict:
    for attempt in range(2):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GRAPHQL_URL,
                headers=_headers(),
                json={
                    "operationName": operation_name,
                    "query": query_text,
                    "variables": variables or {},
                },
                timeout=30,
            )

            if resp.status_code in (401, 403) and attempt == 0:
                await login_with_stored_credentials()
                continue

            resp.raise_for_status()
            return resp.json()

    raise RuntimeError("Failed after retry")


def month_range(month: str | None = None) -> tuple[str, str]:
    """Return (start_date, end_date) for a YYYY-MM month string."""
    if not month:
        month = date.today().strftime("%Y-%m")
    year, mo = int(month[:4]), int(month[5:])
    last_day = monthrange(year, mo)[1]
    return f"{month}-01", f"{month}-{last_day}"


def drop_none(data: dict) -> dict:
    """Remove unset values while preserving explicit falsey edits."""
    return {key: value for key, value in data.items() if value is not None}


def write_env_values(values: dict[str, str]) -> None:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = [
                line
                for line in f.readlines()
                if not any(line.startswith(f"{key}=") for key in values)
            ]
    lines.extend(f"{key}={value}\n" for key, value in values.items())
    with open(env_path, "w") as f:
        f.writelines(lines)


def transaction_mutation_fields() -> str:
    return """
      transaction {
        id
        amount
        pending
        date
        hideFromReports
        notes
        isRecurring
        reviewStatus
        needsReview
        isSplitTransaction
        category { id name icon systemCategory group { id type __typename } __typename }
        merchant { id name transactionsCount logoUrl __typename }
        tags { id name color order __typename }
        account { id displayName icon logoUrl __typename }
        __typename
      }
      errors {
        fieldErrors { field messages __typename }
        message
        code
        __typename
      }
      __typename
    """
