import os
import httpx
from datetime import date, timedelta
from calendar import monthrange
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Monarch Money")

GRAPHQL_URL = "https://api.monarch.com/graphql"
LOGIN_URL = "https://api.monarch.com/auth/login/"

# Mutable state for token
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


async def _login() -> str:
    """Re-authenticate using stored credentials and return new token."""
    email = os.environ.get("MONARCH_EMAIL", "")
    password = os.environ.get("MONARCH_PASSWORD", "")
    if not email or not password:
        raise RuntimeError(
            "MONARCH_TOKEN expired and MONARCH_EMAIL/MONARCH_PASSWORD not set. "
            "Cannot re-authenticate. Please update MONARCH_TOKEN in your .env file."
        )

    # Try GraphQL login mutation (no auth header needed for login)
    login_query = """
    mutation LoginMutation($email: String!, $password: String!, $totpToken: String, $rememberMe: Boolean) {
      login(email: $email, password: $password, totpToken: $totpToken, rememberMe: $rememberMe) {
        token
        user { id email }
        errors { field messages }
      }
    }
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPHQL_URL,
            headers={
                "content-type": "application/json",
                "client-platform": "web",
                "monarch-client-version": "v1.0.1715",
                "origin": "https://app.monarch.com",
            },
            json={
                "operationName": "LoginMutation",
                "query": login_query,
                "variables": {"email": email, "password": password, "rememberMe": True},
            },
            timeout=30,
        )

        if resp.status_code == 401:
            # Fallback: try REST login
            resp = await client.post(
                LOGIN_URL,
                headers={
                    "content-type": "application/json",
                    "client-platform": "web",
                    "monarch-client-version": "v1.0.1715",
                    "origin": "https://app.monarch.com",
                },
                json={
                    "username": email,
                    "password": password,
                    "trusted_device": True,
                    "supports_mfa": True,
                    "supports_email_otp": True,
                },
                timeout=30,
            )

        resp.raise_for_status()
        data = resp.json()

    # Extract token from either response format
    token = None
    if "data" in data and "login" in data["data"]:
        login_data = data["data"]["login"]
        if login_data.get("errors"):
            raise RuntimeError(f"Login failed: {login_data['errors']}")
        token = login_data.get("token")
    elif "token" in data:
        token = data["token"]

    if not token:
        raise RuntimeError(f"Login failed - no token in response: {data}")

    _state["token"] = token

    # Update .env file for persistence
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = [l for l in f.readlines() if not l.startswith("MONARCH_TOKEN=")]
    lines.append(f"MONARCH_TOKEN={token}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)

    return token


async def _query(operation_name: str, query: str, variables: dict | None = None) -> dict:
    for attempt in range(2):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GRAPHQL_URL,
                headers=_headers(),
                json={
                    "operationName": operation_name,
                    "query": query,
                    "variables": variables or {},
                },
                timeout=30,
            )

            if resp.status_code in (401, 403) and attempt == 0:
                # Token expired — try to re-authenticate
                await _login()
                continue

            resp.raise_for_status()
            return resp.json()

    raise RuntimeError("Failed after retry")


def _month_range(month: str | None = None) -> tuple[str, str]:
    """Return (start_date, end_date) for a YYYY-MM month string."""
    if not month:
        month = date.today().strftime("%Y-%m")
    year, mo = int(month[:4]), int(month[5:])
    last_day = monthrange(year, mo)[1]
    return f"{month}-01", f"{month}-{last_day}"


# ── Tools ──────────────────────────────────────────────────────────


@mcp.tool
async def get_accounts() -> dict:
    """Get all financial accounts with balances, types, and connection status."""
    query = """
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
    return await _query("GetAccounts", query, {"filters": {}})


@mcp.tool
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


@mcp.tool
async def get_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    category_ids: list[str] | None = None,
    account_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Search and list transactions with optional filters.

    Args:
        start_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        end_date: End date (YYYY-MM-DD). Defaults to today.
        search: Search term for merchant name or description.
        category_ids: Filter by category IDs (use get_categories to find IDs).
        account_ids: Filter by account IDs (use get_accounts to find IDs).
        tag_ids: Filter by tag IDs.
        limit: Max results to return (default 50).
        offset: Offset for pagination.
    """
    if not start_date:
        start_date = (date.today() - timedelta(days=30)).isoformat()
    if not end_date:
        end_date = date.today().isoformat()

    filters: dict = {
        "startDate": start_date,
        "endDate": end_date,
        "transactionVisibility": "non_hidden_transactions_only",
    }
    if search:
        filters["search"] = search
    if category_ids:
        filters["categories"] = category_ids
    if account_ids:
        filters["accounts"] = account_ids
    if tag_ids:
        filters["tags"] = tag_ids

    # Exact query from Monarch web app
    query = """
    query Web_GetTransactionsList($offset: Int, $limit: Int, $filters: TransactionFilterInput, $orderBy: TransactionOrdering) {
      allTransactions(filters: $filters) {
        totalCount
        results(offset: $offset, limit: $limit, orderBy: $orderBy) {
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
          category {
            id name icon systemCategory
            group { id type __typename }
            __typename
          }
          merchant {
            name id transactionsCount logoUrl
            recurringTransactionStream { frequency isActive __typename }
            __typename
          }
          tags { id name color order __typename }
          account { id displayName icon logoUrl __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await _query(
        "Web_GetTransactionsList",
        query,
        {"filters": filters, "limit": limit, "offset": offset, "orderBy": "date"},
    )


@mcp.tool
async def get_cash_flow(month: str | None = None) -> dict:
    """Get monthly cash flow summary with income and expenses by category.

    Args:
        month: Month in YYYY-MM format. Defaults to current month.
    """
    start, end = _month_range(month)

    # Use the transactions query to compute cash flow by category
    query = """
    query Web_GetTransactionsList($offset: Int, $limit: Int, $filters: TransactionFilterInput, $orderBy: TransactionOrdering) {
      allTransactions(filters: $filters) {
        totalCount
        results(offset: $offset, limit: $limit, orderBy: $orderBy) {
          id amount date
          category { id name icon group { id type name __typename } __typename }
          merchant { name __typename }
          account { id displayName __typename }
          __typename
        }
        __typename
      }
    }
    """
    filters = {
        "startDate": start,
        "endDate": end,
        "transactionVisibility": "non_hidden_transactions_only",
    }
    data = await _query(
        "Web_GetTransactionsList",
        query,
        {"filters": filters, "limit": 500, "offset": 0, "orderBy": "date"},
    )

    txns = data.get("data", {}).get("allTransactions", {}).get("results", [])

    income_by_cat: dict[str, float] = {}
    expense_by_cat: dict[str, float] = {}
    total_income = 0.0
    total_expense = 0.0

    for t in txns:
        amt = t.get("amount", 0)
        cat = t.get("category", {})
        cat_name = cat.get("name", "Uncategorized")
        cat_icon = cat.get("icon", "")
        group_type = (cat.get("group") or {}).get("type", "")

        if group_type == "transfer":
            continue

        if group_type == "income":
            total_income += amt
            key = f"{cat_icon} {cat_name}"
            income_by_cat[key] = income_by_cat.get(key, 0) + amt
        elif group_type == "expense" or amt < 0:
            total_expense += abs(amt)
            key = f"{cat_icon} {cat_name}"
            expense_by_cat[key] = expense_by_cat.get(key, 0) + abs(amt)

    savings = total_income - total_expense
    savings_rate = (savings / total_income * 100) if total_income > 0 else 0

    return {
        "month": month or date.today().strftime("%Y-%m"),
        "income": round(total_income, 2),
        "expenses": round(total_expense, 2),
        "savings": round(savings, 2),
        "savings_rate": f"{savings_rate:.1f}%",
        "income_by_category": {k: round(v, 2) for k, v in sorted(income_by_cat.items(), key=lambda x: -x[1])},
        "expenses_by_category": {k: round(v, 2) for k, v in sorted(expense_by_cat.items(), key=lambda x: -x[1])},
    }


@mcp.tool
async def get_budgets(month: str | None = None) -> dict:
    """Get budget status for a given month.

    Args:
        month: Month in YYYY-MM format. Defaults to current month.
    """
    if not month:
        month = date.today().strftime("%Y-%m")

    start = f"{month}-01"

    query = """
    query GetBudgets($startDate: Date!) {
      budgetData(startDate: $startDate) {
        monthlyAmountsByCategory {
          category { id name icon }
          budgetAmount { amount }
          actualAmount
          remainingAmount
          monthStartDate
        }
        totalBudgetAmount { amount }
        totalActualAmount
        totalRemainingAmount
      }
    }
    """
    return await _query("GetBudgets", query, {"startDate": start})


@mcp.tool
async def get_categories() -> dict:
    """Get all transaction categories and their groups."""
    query = """
    query GetCategories {
      categories {
        id order name icon systemCategory isSystemCategory isDisabled
        group { id name type __typename }
        __typename
      }
    }
    """
    return await _query("GetCategories", query)


@mcp.tool
async def get_recurring(month: str | None = None) -> dict:
    """Get recurring transactions/bills for a given month.

    Args:
        month: Month in YYYY-MM format. Defaults to current month.
    """
    start, end = _month_range(month)

    # Exact query from Monarch web app
    query = """
    query Common_GetAggregatedRecurringItems($startDate: Date!, $endDate: Date!, $filters: RecurringTransactionFilter) {
      aggregatedRecurringItems(
        startDate: $startDate
        endDate: $endDate
        groupBy: "status"
        filters: $filters
      ) {
        groups {
          groupBy { status __typename }
          results {
            stream {
              id frequency isActive amount isApproximate name logoUrl
              merchant { id name logoUrl __typename }
              __typename
            }
            date isPast isLate markedPaidAt isCompleted transactionId
            amount amountDiff isAmountDifferentThanOriginal
            category { id name icon __typename }
            account { id displayName icon logoUrl __typename }
            __typename
          }
          summary {
            expense { total __typename }
            creditCard { total __typename }
            income { total __typename }
            __typename
          }
          __typename
        }
        aggregatedSummary {
          expense { completed remaining total count __typename }
          creditCard { completed remaining total count __typename }
          income { completed remaining total __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await _query(
        "Common_GetAggregatedRecurringItems",
        query,
        {"startDate": start, "endDate": end, "filters": {}},
    )


@mcp.tool
async def get_net_worth_snapshots(timeframe: str = "1M") -> dict:
    """Get historical net worth data points.

    Args:
        timeframe: One of 1M, 3M, 6M, 1Y, ALL.
    """
    query = """
    query GetNetWorthSnapshots($timeframe: String!) {
      accountChartData(chartType: "performance", dateRange: $timeframe) {
        date
        balance
      }
    }
    """
    return await _query("GetNetWorthSnapshots", query, {"timeframe": timeframe})


@mcp.tool
async def get_investments() -> dict:
    """Get investment holdings and performance."""
    query = """
    query GetInvestments {
      portfolioPerformance {
        totalValue
        totalCostBasis
        totalGainLoss
        totalGainLossPercent
        todayChangeAmount
        todayChangePercent
      }
      holdings {
        id name ticker quantity costBasis currentValue
        todayChangeAmount todayChangePercent
        account { displayName }
      }
    }
    """
    return await _query("GetInvestments", query)


@mcp.tool
async def get_account_history(account_id: str) -> dict:
    """Get balance history snapshots for a specific account.

    Args:
        account_id: The account UUID from get_accounts.
    """
    query = """
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
    return await _query("GetAccountHistory", query, {"id": account_id})


@mcp.tool
async def login(email: str, password: str) -> dict:
    """Login to Monarch Money, save credentials, and refresh the auth token.

    Args:
        email: Your Monarch Money email.
        password: Your Monarch Money password.
    """
    # Save credentials to .env for future auto-retry
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = [l for l in f.readlines()
                     if not l.startswith("MONARCH_EMAIL=") and not l.startswith("MONARCH_PASSWORD=")]
    lines.append(f"MONARCH_EMAIL={email}\n")
    lines.append(f"MONARCH_PASSWORD={password}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)

    os.environ["MONARCH_EMAIL"] = email
    os.environ["MONARCH_PASSWORD"] = password

    try:
        token = await _login()
        return {
            "success": True,
            "message": f"Logged in. Token saved to .env (starts with {token[:12]}...).",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()
