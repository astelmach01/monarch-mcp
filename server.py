import base64
import hashlib
import hmac
import os
import struct
import time
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


async def _login() -> str:
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
        # Step 1: attempt login without TOTP
        resp = await client.post(LOGIN_URL, headers=login_headers, json=base_body, timeout=30)

        # Step 2: 403 = MFA required — retry with TOTP code
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


def _drop_none(data: dict) -> dict:
    """Remove unset values while preserving explicit falsey edits."""
    return {key: value for key, value in data.items() if value is not None}


def _transaction_mutation_fields() -> str:
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
async def get_transaction(transaction_id: str) -> dict:
    """Get full details for a single transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
    """
    query = """
    query Common_TransactionDetailQuery($id: UUID!) {
      getTransaction(id: $id) {
        id
        amount
        pending
        date
        hideFromReports
        hiddenByAccount
        plaidName
        notes
        isRecurring
        reviewStatus
        needsReview
        isSplitTransaction
        dataProviderDescription
        deletedAt
        deletedByType
        attachments { id filename originalAssetUrl __typename }
        category { id name icon systemCategory group { id type __typename } __typename }
        merchant { id name transactionsCount logoUrl __typename }
        tags { id name color order __typename }
        account { id displayName icon logoUrl __typename }
        goal { id name __typename }
        savingsGoalEvent { id goal { id name __typename } __typename }
        ownedByUser { id displayName profilePictureUrl __typename }
        businessEntity { id name logoUrl color __typename }
        __typename
      }
    }
    """
    return await _query("Common_TransactionDetailQuery", query, {"id": transaction_id})


@mcp.tool
async def update_transaction(
    transaction_id: str,
    category_id: str | None = None,
    merchant_name: str | None = None,
    notes: str | None = None,
    transaction_date: str | None = None,
    amount: float | None = None,
    hide_from_reports: bool | None = None,
    review_status: str | None = None,
    tag_ids: list[str] | None = None,
    is_recurring: bool | None = None,
    raw_updates: dict | None = None,
) -> dict:
    """Update a transaction's categorization/details.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        category_id: Category ID from get_categories. Sends Monarch's app-native
            `category` field.
        merchant_name: New merchant/display name.
        notes: Notes text. Use an empty string to clear notes.
        transaction_date: Transaction date as YYYY-MM-DD.
        amount: Transaction amount, using Monarch's sign convention.
        hide_from_reports: Whether to hide the transaction from reports.
        review_status: Monarch review status such as needs_review or approved.
        tag_ids: Replace tags with these tag IDs.
        is_recurring: Whether the transaction should be recurring.
        raw_updates: Extra app-native UpdateTransactionMutationInput fields.
    """
    input_data = _drop_none(
        {
            "id": transaction_id,
            "category": category_id,
            "merchantName": merchant_name,
            "notes": notes,
            "date": transaction_date,
            "amount": amount,
            "hideFromReports": hide_from_reports,
            "reviewStatus": review_status,
            "isRecurring": is_recurring,
        }
    )
    if raw_updates:
        input_data.update(raw_updates)

    query = f"""
    mutation Web_UpdateTransactionOverview($input: UpdateTransactionMutationInput!) {{
      updateTransaction(input: $input) {{
        {_transaction_mutation_fields()}
      }}
    }}
    """
    result = await _query("Web_UpdateTransactionOverview", query, {"input": input_data})
    if tag_ids is not None:
        result["set_tags"] = await set_transaction_tags(transaction_id, tag_ids)
    return result


@mcp.tool
async def mark_transaction_reviewed(transaction_id: str, reviewed: bool = True) -> dict:
    """Mark a transaction reviewed or back to needs-review.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        reviewed: True marks approved; False marks needs_review.
    """
    return await update_transaction(
        transaction_id=transaction_id,
        review_status="approved" if reviewed else "needs_review",
    )


@mcp.tool
async def create_transaction(
    account_id: str,
    amount: float,
    transaction_date: str,
    merchant_name: str,
    category_id: str | None = None,
    notes: str | None = None,
    review_status: str | None = None,
    hide_from_reports: bool | None = None,
    should_update_balance: bool = True,
    tag_ids: list[str] | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Create a manual transaction in Monarch.

    Args:
        account_id: Account ID from get_accounts.
        amount: Transaction amount, using Monarch's sign convention.
        transaction_date: Transaction date as YYYY-MM-DD.
        merchant_name: Merchant/display name.
        category_id: Category ID from get_categories.
        notes: Optional notes.
        review_status: Optional review status such as approved.
        hide_from_reports: Whether to hide from reports.
        should_update_balance: Whether to adjust the manual account balance.
        tag_ids: Optional tag IDs.
        raw_input: Extra app-native CreateTransactionMutationInput fields.
    """
    input_data = _drop_none(
        {
            "accountId": account_id,
            "amount": amount,
            "date": transaction_date,
            "merchantName": merchant_name,
            "categoryId": category_id,
            "notes": notes,
            "reviewStatus": review_status,
            "hideFromReports": hide_from_reports,
            "shouldUpdateBalance": should_update_balance,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query = """
    mutation Common_CreateTransactionMutation($input: CreateTransactionMutationInput!) {
      createTransaction(input: $input) {
        transaction { id __typename }
        errors {
          fieldErrors { field messages __typename }
          message
          code
          __typename
        }
        __typename
      }
    }
    """
    result = await _query("Common_CreateTransactionMutation", query, {"input": input_data})
    create_payload = (result.get("data") or {}).get("createTransaction") or {}
    transaction_id = (create_payload.get("transaction") or {}).get("id")
    if transaction_id and tag_ids is not None:
        result["set_tags"] = await set_transaction_tags(transaction_id, tag_ids)
    return result


@mcp.tool
async def set_transaction_tags(transaction_id: str, tag_ids: list[str]) -> dict:
    """Replace a transaction's tags.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        tag_ids: Tag IDs to set. Use an empty list to clear tags.
    """
    query = """
    mutation Web_SetTransactionTags($input: SetTransactionTagsInput!) {
      setTransactionTags(input: $input) {
        errors {
          fieldErrors { field messages __typename }
          message
          code
          __typename
        }
        transaction {
          id
          tags { id name color order __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await _query(
        "Web_SetTransactionTags",
        query,
        {"input": {"transactionId": transaction_id, "tagIds": tag_ids}},
    )


@mcp.tool
async def delete_transaction(transaction_id: str) -> dict:
    """Delete one transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
    """
    query = """
    mutation Common_DeleteTransactionMutation($input: DeleteTransactionMutationInput!) {
      deleteTransaction(input: $input) {
        deleted
        errors {
          fieldErrors { field messages __typename }
          message
          code
          __typename
        }
        __typename
      }
    }
    """
    return await _query("Common_DeleteTransactionMutation", query, {"input": {"transactionId": transaction_id}})


@mcp.tool
async def bulk_update_transactions(
    transaction_ids: list[str],
    updates: dict | None = None,
    category_id: str | None = None,
    merchant_name: str | None = None,
    notes: str | None = None,
    transaction_date: str | None = None,
    hide_from_reports: bool | None = None,
    review_status: str | None = None,
    tag_ids: list[str] | None = None,
) -> dict:
    """Bulk-update selected transactions.

    Args:
        transaction_ids: Transaction UUIDs from get_transactions.
        updates: App-native TransactionUpdateParams. Merged after convenience args.
        category_id: Category ID from get_categories.
        merchant_name: New merchant/display name.
        notes: Notes text. Use an empty string to clear notes.
        transaction_date: Transaction date as YYYY-MM-DD.
        hide_from_reports: Whether to hide from reports.
        review_status: Monarch review status such as needs_review or approved.
        tag_ids: Replace tags with these tag IDs.
    """
    update_data = _drop_none(
        {
            "categoryId": category_id,
            "merchantName": merchant_name,
            "notes": notes,
            "date": transaction_date,
            "hideFromReports": hide_from_reports,
            "reviewStatus": review_status,
            "tags": tag_ids,
        }
    )
    if updates:
        update_data.update(updates)

    query = """
    mutation Common_BulkUpdateTransactionsMutation(
      $selectedTransactionIds: [ID!]
      $excludedTransactionIds: [ID!]
      $allSelected: Boolean!
      $expectedAffectedTransactionCount: Int!
      $updates: TransactionUpdateParams!
      $filters: TransactionFilterInput
    ) {
      bulkUpdateTransactions(
        selectedTransactionIds: $selectedTransactionIds
        excludedTransactionIds: $excludedTransactionIds
        updates: $updates
        allSelected: $allSelected
        expectedAffectedTransactionCount: $expectedAffectedTransactionCount
        filters: $filters
      ) {
        success
        affectedCount
        errors { message __typename }
        __typename
      }
    }
    """
    return await _query(
        "Common_BulkUpdateTransactionsMutation",
        query,
        {
            "selectedTransactionIds": transaction_ids,
            "excludedTransactionIds": [],
            "allSelected": False,
            "expectedAffectedTransactionCount": len(transaction_ids),
            "updates": update_data,
            "filters": {},
        },
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
