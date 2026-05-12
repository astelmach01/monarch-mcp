import os

from fastmcp.tools import tool

from tools.client import login_with_stored_credentials, write_env_values


@tool
async def login(email: str, password: str) -> dict:
    """Login to Monarch Money, save credentials, and refresh the auth token.

    Args:
        email: Your Monarch Money email.
        password: Your Monarch Money password.
    """
    write_env_values(
        {
            "MONARCH_EMAIL": email,
            "MONARCH_PASSWORD": password,
        }
    )

    os.environ["MONARCH_EMAIL"] = email
    os.environ["MONARCH_PASSWORD"] = password

    try:
        token = await login_with_stored_credentials()
        return {
            "success": True,
            "message": f"Logged in. Token saved to .env (starts with {token[:12]}...).",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
