from fastmcp.tools import tool

from tools.client import query


@tool
async def get_accounts() -> dict:
    """Get all financial accounts with balances, types, and connection status."""
    query_text = """
    query GetAccounts($filters: AccountFilters) {
      accountTypeSummaries(filters: $filters) {
        type { name display group }
        accounts {
          id displayName displayBalance signedBalance
          updatedAt syncDisabled isAsset includeInNetWorth
          type { name display }
          subtype { display }
          institution { name status }
          credential { updateRequired disconnectedFromDataProviderAt }
        }
        isAsset totalDisplayBalance
      }
    }
    """
    return await query("GetAccounts", query_text, {"filters": {}})


@tool
async def get_account_balances_summary() -> dict:
    """Get a quick summary of total assets, liabilities, and net worth."""
    data = await get_accounts()
    summaries = data.get("data", {}).get("accountTypeSummaries", [])
    assets = sum(s["totalDisplayBalance"] for s in summaries if s["isAsset"])
    liabilities = sum(s["totalDisplayBalance"] for s in summaries if not s["isAsset"])
    return {
        "net_worth": round(assets - liabilities, 2),
        "total_assets": round(assets, 2),
        "total_liabilities": round(liabilities, 2),
        "account_groups": [
            {
                "type": s["type"]["display"],
                "group": s["type"]["group"],
                "total": s["totalDisplayBalance"],
                "accounts": [
                    {"name": a["displayName"], "balance": a["displayBalance"]}
                    for a in s["accounts"]
                ],
            }
            for s in summaries
        ],
    }


@tool
async def get_account_history(account_id: str) -> dict:
    """Get balance history snapshots for a specific account.

    Args:
        account_id: The account UUID from get_accounts.
    """
    query_text = """
    query GetAccountHistory($id: UUID!) {
      snapshots: snapshotsForAccount(accountId: $id) {
        date signedBalance
      }
      account(id: $id) {
        id displayName displayBalance
        type { display }
        subtype { display }
      }
    }
    """
    return await query("GetAccountHistory", query_text, {"id": account_id})
