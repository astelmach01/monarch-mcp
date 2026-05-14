from datetime import date, timedelta

from tools.decorators import read_tool, write_tool

from tools.client import drop_none, month_range, month_start, query
from tools.output import ensure_context_safe_response, page_items, save_json_response


def _date_range_for_timeframe(timeframe: str) -> tuple[str, str]:
    today = date.today()
    normalized = timeframe.upper()
    days = {
        "1M": 30,
        "3M": 90,
        "6M": 182,
        "1Y": 365,
        "ALL": 3650,
    }.get(normalized, 30)
    return (today - timedelta(days=days)).isoformat(), today.isoformat()


def _net_worth_timeframe(timeframe: str) -> str:
    normalized = timeframe.upper()
    if normalized in {"1Y", "ALL"}:
        return "quarter" if normalized == "1Y" else "year"
    return "month"


def _holding_summary(edge: dict) -> dict:
    node = edge.get("node") or edge
    security = node.get("security") or {}
    holdings = node.get("holdings") or []
    accounts = []
    for holding in holdings:
        account = holding.get("account") or {}
        accounts.append(
            {
                "id": account.get("id"),
                "displayName": account.get("displayName"),
                "type": (account.get("type") or {}).get("display"),
                "subtype": (account.get("subtype") or {}).get("display"),
                "value": holding.get("value"),
                "quantity": holding.get("quantity"),
                "costBasis": holding.get("costBasis"),
            }
        )
    return {
        "id": node.get("id"),
        "quantity": node.get("quantity"),
        "costBasis": node.get("costBasis"),
        "totalValue": node.get("totalValue"),
        "securityPriceChangeDollars": node.get("securityPriceChangeDollars"),
        "securityPriceChangePercent": node.get("securityPriceChangePercent"),
        "lastSyncedAt": node.get("lastSyncedAt"),
        "security": {
            "id": security.get("id"),
            "name": security.get("name"),
            "ticker": security.get("ticker"),
            "currentPrice": security.get("currentPrice"),
            "type": security.get("type"),
            "typeDisplay": security.get("typeDisplay"),
            "categoryGroup": security.get("categoryGroup"),
        },
        "holdingCount": len(holdings),
        "accounts": accounts,
    }


@read_tool()
async def get_cash_flow(month: str | None = None) -> dict:
    """Get monthly cash flow summary with income and expenses by category.

    Args:
        month: Month in YYYY-MM format. Defaults to current month.
    """
    start, end = month_range(month)

    query_text = """
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
    data = await query(
        "Web_GetTransactionsList",
        query_text,
        {"filters": filters, "limit": 500, "offset": 0, "orderBy": "date"},
    )

    txns = data.get("data", {}).get("allTransactions", {}).get("results", [])

    income_by_cat: dict[str, float] = {}
    expense_by_cat: dict[str, float] = {}
    total_income = 0.0
    total_expense = 0.0

    for txn in txns:
        amount = txn.get("amount", 0)
        category = txn.get("category", {})
        category_name = category.get("name", "Uncategorized")
        category_icon = category.get("icon", "")
        group_type = (category.get("group") or {}).get("type", "")

        if group_type == "transfer":
            continue

        if group_type == "income":
            total_income += amount
            key = f"{category_icon} {category_name}"
            income_by_cat[key] = income_by_cat.get(key, 0) + amount
        elif group_type == "expense" or amount < 0:
            total_expense += abs(amount)
            key = f"{category_icon} {category_name}"
            expense_by_cat[key] = expense_by_cat.get(key, 0) + abs(amount)

    savings = total_income - total_expense
    savings_rate = (savings / total_income * 100) if total_income > 0 else 0

    return {
        "month": month or date.today().strftime("%Y-%m"),
        "income": round(total_income, 2),
        "expenses": round(total_expense, 2),
        "savings": round(savings, 2),
        "savings_rate": f"{savings_rate:.1f}%",
        "income_by_category": {key: round(value, 2) for key, value in sorted(income_by_cat.items(), key=lambda x: -x[1])},
        "expenses_by_category": {key: round(value, 2) for key, value in sorted(expense_by_cat.items(), key=lambda x: -x[1])},
    }


@read_tool()
async def get_budgets(month: str | None = None) -> dict:
    """Get budget status for a given month.

    Args:
        month: Month in YYYY-MM format. Defaults to current month.
    """
    if not month:
        month = date.today().strftime("%Y-%m")

    start, end = month_range(month)

    query_text = """
    query Common_BudgetDataQuery($startDate: Date!, $endDate: Date!) {
      budgetSystem
      budgetStatus {
        hasBudget
        hasTransactions
        willCreateBudgetFromEmptyDefaultCategories
        __typename
      }
      budgetData(startMonth: $startDate, endMonth: $endDate) {
        monthlyAmountsByCategory {
          category { id name icon __typename }
          monthlyAmounts {
            month
            plannedCashFlowAmount
            plannedSetAsideAmount
            actualAmount
            remainingAmount
            previousMonthRolloverAmount
            rolloverType
            cumulativeActualAmount
            rolloverTargetAmount
            __typename
          }
          __typename
        }
        monthlyAmountsByCategoryGroup {
          categoryGroup { id name type __typename }
          monthlyAmounts {
            month
            plannedCashFlowAmount
            plannedSetAsideAmount
            actualAmount
            remainingAmount
            previousMonthRolloverAmount
            rolloverType
            cumulativeActualAmount
            rolloverTargetAmount
            __typename
          }
          __typename
        }
        monthlyAmountsForFlexExpense {
          budgetVariability
          monthlyAmounts {
            month
            plannedCashFlowAmount
            plannedSetAsideAmount
            actualAmount
            remainingAmount
            previousMonthRolloverAmount
            rolloverType
            cumulativeActualAmount
            rolloverTargetAmount
            __typename
          }
          __typename
        }
        totalsByMonth {
          month
          totalIncome { actualAmount plannedAmount previousMonthRolloverAmount remainingAmount __typename }
          totalExpenses { actualAmount plannedAmount previousMonthRolloverAmount remainingAmount __typename }
          totalFixedExpenses { actualAmount plannedAmount previousMonthRolloverAmount remainingAmount __typename }
          totalNonMonthlyExpenses { actualAmount plannedAmount previousMonthRolloverAmount remainingAmount __typename }
          totalFlexibleExpenses { actualAmount plannedAmount previousMonthRolloverAmount remainingAmount __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_BudgetDataQuery", query_text, {"startDate": start, "endDate": end})


@read_tool()
async def get_budget_status() -> dict:
    """Get whether the household has an initialized budget."""
    query_text = """
    query Common_GetBudgetStatus {
      budgetStatus {
        hasBudget
        hasTransactions
        willCreateBudgetFromEmptyDefaultCategories
        __typename
      }
    }
    """
    return await query("Common_GetBudgetStatus", query_text)


@read_tool()
async def get_budget_settings() -> dict:
    """Get household budget system and apply-to-future defaults."""
    query_text = """
    query Common_GetBudgetSettings {
      budgetSystem
      budgetApplyToFutureMonthsDefault
      flexExpenseRolloverPeriod {
        id
        startMonth
        startingBalance
        __typename
      }
    }
    """
    return await query("Common_GetBudgetSettings", query_text)


@write_tool(idempotent=True)
async def update_budget_settings(
    budget_system: str | None = None,
    apply_to_future_months_default: bool | None = None,
    rollover_start_month: str | None = None,
    rollover_starting_balance: float | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Update household budget settings.

    Args:
        budget_system: Monarch budget system value.
        apply_to_future_months_default: Default for budget edits.
        rollover_start_month: Optional flex rollover start month as YYYY-MM-DD.
        rollover_starting_balance: Optional flex rollover starting balance.
        raw_input: Extra app-native UpdateBudgetSettingsMutationInput fields.
    """
    input_data = drop_none(
        {
            "budgetSystem": budget_system,
            "budgetApplyToFutureMonthsDefault": apply_to_future_months_default,
            "rolloverStartMonth": rollover_start_month,
            "rolloverStartingBalance": rollover_starting_balance,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = """
    mutation Common_UpdateBudgetSettings($input: UpdateBudgetSettingsMutationInput!) {
      updateBudgetSettings(input: $input) {
        budgetSystem
        budgetApplyToFutureMonthsDefault
        budgetRolloverPeriod {
          id
          startMonth
          startingBalance
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_UpdateBudgetSettings", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def update_budget_item(
    month: str,
    amount: float,
    category_id: str | None = None,
    category_group_id: str | None = None,
    apply_to_future: bool | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Update or create a category or category-group budget item.

    Args:
        month: Month as YYYY-MM or date as YYYY-MM-DD.
        amount: Planned budget amount.
        category_id: Category ID from get_categories.
        category_group_id: Category group ID from get_categories.
        apply_to_future: Whether Monarch should apply this amount to future months.
        raw_input: Extra app-native UpdateOrCreateBudgetItemMutationInput fields.
    """
    if category_id and category_group_id:
        raise ValueError("Only one of category_id or category_group_id can be provided")
    start_date = month if len(month) == 10 else f"{month}-01"
    input_data = drop_none(
        {
            "defaultAmount": None,
            "startDate": start_date,
            "timeframe": "month",
            "amount": amount,
            "applyToFuture": apply_to_future,
            "categoryId": category_id,
            "categoryGroupId": category_group_id,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = """
    mutation Common_UpdateBudgetItem($input: UpdateOrCreateBudgetItemMutationInput!) {
      updateOrCreateBudgetItem(input: $input) {
        budgetItem {
          id
          plannedCashFlowAmount
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_UpdateBudgetItem", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def update_flex_budget_item(
    month: str | None = None,
    amount: float | None = None,
    apply_to_future: bool | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Update or create a flex-budget item.

    Args:
        month: Month as YYYY-MM or date as YYYY-MM-DD. Sent to Monarch as
            `startDate`.
        amount: Flexible budget amount.
        apply_to_future: Whether Monarch should apply this amount to future months.
        raw_input: Extra app-native UpdateOrCreateFlexBudgetItemMutationInput.
    """
    input_data = dict(raw_input or {})
    if "month" in input_data and "startDate" not in input_data:
        input_data["startDate"] = month_start(str(input_data.pop("month")))
    if month and "startDate" not in input_data:
        input_data["startDate"] = month_start(month)
    if amount is not None:
        input_data["amount"] = amount
    if apply_to_future is not None:
        input_data["applyToFuture"] = apply_to_future

    query_text = """
    mutation Common_UpdateFlexBudgetMutation($input: UpdateOrCreateFlexBudgetItemMutationInput!) {
      updateOrCreateFlexBudgetItem(input: $input) {
        budgetItem {
          id
          budgetAmount
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_UpdateFlexBudgetMutation", query_text, {"input": input_data})


@write_tool()
async def move_money_between_budget_categories(
    amount: float | None = None,
    month: str | None = None,
    from_category_id: str | None = None,
    to_category_id: str | None = None,
    from_category_group_id: str | None = None,
    to_category_group_id: str | None = None,
    from_budget_target: str | None = None,
    to_budget_target: str | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Move budget money between categories or budget targets.

    Args:
        amount: Amount to move.
        month: Month as YYYY-MM or date as YYYY-MM-DD. Sent to Monarch as
            `startDate`.
        from_category_id: Source category ID.
        to_category_id: Destination category ID.
        from_category_group_id: Source category group ID.
        to_category_group_id: Destination category group ID.
        from_budget_target: Source aggregate budget target.
        to_budget_target: Destination aggregate budget target.
        raw_input: Extra app-native MoveMoneyMutationInput.
    """
    input_data = dict(raw_input or {})
    if "month" in input_data and "startDate" not in input_data:
        input_data["startDate"] = month_start(str(input_data.pop("month")))
    if month and "startDate" not in input_data:
        input_data["startDate"] = month_start(month)
    if amount is not None:
        input_data["amount"] = amount
    input_data.update(
        drop_none(
            {
                "fromCategoryId": from_category_id,
                "toCategoryId": to_category_id,
                "fromCategoryGroupId": from_category_group_id,
                "toCategoryGroupId": to_category_group_id,
                "fromBudgetTarget": from_budget_target,
                "toBudgetTarget": to_budget_target,
            }
        )
    )
    input_data.setdefault("timeframe", "month")

    query_text = """
    mutation Web_MoveMoneyMutation($input: MoveMoneyMutationInput!) {
      moveMoneyBetweenCategories(input: $input) {
        fromBudgetItem { id budgetAmount __typename }
        toBudgetItem { id budgetAmount __typename }
        __typename
      }
    }
    """
    return await query("Web_MoveMoneyMutation", query_text, {"input": input_data})


@write_tool(destructive=True)
async def reset_budget(
    month: str | None = None,
    category_type: str | None = None,
    budget_variability: str | None = None,
    category_ids: list[str] | None = None,
    overwrite_existing: bool | None = False,
    raw_input: dict | None = None,
) -> dict:
    """Recalculate/reset budget data.

    Args:
        month: Month as YYYY-MM or date as YYYY-MM-DD. Sent to Monarch as
            `startDate`.
        category_type: Optional category type, usually `income` or `expense`.
        budget_variability: Optional budget variability such as `fixed`.
        category_ids: Optional category IDs to recalculate.
        overwrite_existing: Whether to overwrite existing budget rows.
        raw_input: Extra app-native ResetBudgetMutationInput.
    """
    input_data = dict(raw_input or {})
    if "month" in input_data and "startDate" not in input_data:
        input_data["startDate"] = month_start(str(input_data.pop("month")))
    if month and "startDate" not in input_data:
        input_data["startDate"] = month_start(month)
    if overwrite_existing is not None:
        input_data.setdefault("overwriteExisting", overwrite_existing)
    if any(value is not None for value in (category_type, budget_variability, category_ids)):
        input_data["filters"] = drop_none(
            {
                "categoryType": category_type,
                "budgetVariability": budget_variability,
                "categoryIds": category_ids,
            }
        )

    query_text = """
    mutation Web_RecalculateBudgetMutation($input: ResetBudgetMutationInput!) {
      resetBudget(input: $input) {
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
    return await query("Web_RecalculateBudgetMutation", query_text, {"input": input_data})


@write_tool(destructive=True)
async def reset_budget_rollover(
    category_id: str | None = None,
    category_group_id: str | None = None,
    month: str | None = None,
    starting_balance: float | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Reset a budget rollover.

    Args:
        category_id: Category ID whose rollover should be reset.
        category_group_id: Category group ID whose rollover should be reset.
        month: Month as YYYY-MM or date as YYYY-MM-DD. Sent to Monarch as
            `startMonth`.
        starting_balance: Optional rollover starting balance.
        raw_input: Extra app-native ResetBudgetRolloverInput.
    """
    input_data = dict(raw_input or {})
    if "month" in input_data and "startMonth" not in input_data:
        input_data["startMonth"] = month_start(str(input_data.pop("month")))
    if "startDate" in input_data and "startMonth" not in input_data:
        input_data["startMonth"] = month_start(str(input_data.pop("startDate")))
    if month and "startMonth" not in input_data:
        input_data["startMonth"] = month_start(month)
    input_data.update(
        drop_none(
            {
                "categoryId": category_id,
                "categoryGroupId": category_group_id,
                "startingBalance": starting_balance,
            }
        )
    )
    input_data.pop("timeframe", None)

    if input_data.get("categoryId"):
        preflight_query = """
        query Common_CategoryRolloverPreflight($id: UUID!) {
          category(id: $id) {
            id
            name
            rolloverPeriod { id __typename }
            __typename
          }
        }
        """
        preflight = await query(
            "Common_CategoryRolloverPreflight",
            preflight_query,
            {"id": input_data["categoryId"]},
        )
        category = preflight.get("data", {}).get("category")
        if category and not category.get("rolloverPeriod"):
            return {
                "skipped": True,
                "reason": "category_has_no_rollover_period",
                "category": {"id": category.get("id"), "name": category.get("name")},
                "input": input_data,
            }
    elif input_data.get("categoryGroupId"):
        preflight_query = """
        query Common_CategoryGroupRolloverPreflight($id: UUID!) {
          categoryGroup(id: $id) {
            id
            name
            rolloverPeriod { id __typename }
            __typename
          }
        }
        """
        preflight = await query(
            "Common_CategoryGroupRolloverPreflight",
            preflight_query,
            {"id": input_data["categoryGroupId"]},
        )
        category_group = preflight.get("data", {}).get("categoryGroup")
        if category_group and not category_group.get("rolloverPeriod"):
            return {
                "skipped": True,
                "reason": "category_group_has_no_rollover_period",
                "categoryGroup": {"id": category_group.get("id"), "name": category_group.get("name")},
                "input": input_data,
            }
    else:
        preflight_query = """
        query Common_FlexRolloverPreflight {
          flexExpenseRolloverPeriod { id __typename }
        }
        """
        preflight = await query("Common_FlexRolloverPreflight", preflight_query)
        if not preflight.get("data", {}).get("flexExpenseRolloverPeriod"):
            return {
                "skipped": True,
                "reason": "flex_budget_has_no_rollover_period",
                "input": input_data,
            }

    query_text = """
    mutation Web_ResetRolloverMutation($input: ResetBudgetRolloverInput!) {
      resetBudgetRollover(input: $input) {
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
    return await query("Web_ResetRolloverMutation", query_text, {"input": input_data})


@read_tool()
async def get_categories() -> dict:
    """Get all transaction categories and their groups."""
    query_text = """
    query GetCategories {
      categories {
        id order name icon systemCategory isSystemCategory isDisabled
        group { id name type __typename }
        __typename
      }
    }
    """
    return await query("GetCategories", query_text)


@read_tool()
async def get_recurring(month: str | None = None) -> dict:
    """Get recurring transactions/bills for a given month.

    Args:
        month: Month in YYYY-MM format. Defaults to current month.
    """
    start, end = month_range(month)

    query_text = """
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
    return await query(
        "Common_GetAggregatedRecurringItems",
        query_text,
        {"startDate": start, "endDate": end, "filters": {}},
    )


@read_tool()
async def get_net_worth_snapshots(timeframe: str = "1M") -> dict:
    """Get historical net worth data points.

    Args:
        timeframe: One of 1M, 3M, 6M, 1Y, ALL.
    """
    start_date, _ = _date_range_for_timeframe(timeframe)
    monarch_timeframe = _net_worth_timeframe(timeframe)
    query_text = """
    query Common_GetSnapshotsByAccountType($startDate: Date!, $timeframe: Timeframe!, $filters: AccountFilters) {
      snapshotsByAccountType(startDate: $startDate, timeframe: $timeframe, filters: $filters) {
        accountType
        month
        balance
      }
      accountTypes {
        name
        group
      }
    }
    """
    result = await query(
        "Common_GetSnapshotsByAccountType",
        query_text,
        {"startDate": start_date, "timeframe": monarch_timeframe, "filters": {}},
    )
    result["requestedTimeframe"] = timeframe
    result["startDate"] = start_date
    result["monarchTimeframe"] = monarch_timeframe
    return result


@read_tool()
async def get_investments(
    timeframe: str = "3M",
    limit: int = 25,
    offset: int = 0,
    include_details: bool = False,
    save_full_response: bool = False,
) -> dict:
    """Get investment holdings and portfolio performance.

    Args:
        timeframe: One of 1M, 3M, 6M, 1Y, ALL. Defaults to 3M.
        limit: Max aggregate holdings to return. Clamped to 100.
        offset: Pagination offset.
        include_details: Return full Monarch holding objects for the page.
        save_full_response: Save the full raw Monarch response to a JSON file.
    """
    start_date, end_date = _date_range_for_timeframe(timeframe)
    query_text = """
    query Web_GetPortfolio($portfolioInput: PortfolioInput) {
      portfolio(input: $portfolioInput) {
        performance {
          totalValue
          totalChangePercent
          totalChangeDollars
          oneDayChangePercent
          historicalChart {
            date
            returnPercent
            __typename
          }
          benchmarks {
            security {
              id
              ticker
              name
              oneDayChangePercent
              __typename
            }
            historicalChart {
              date
              returnPercent
              __typename
            }
            __typename
          }
          __typename
        }
        aggregateHoldings {
          edges {
            node {
              id
              quantity
              costBasis
              totalValue
              securityPriceChangeDollars
              securityPriceChangePercent
              lastSyncedAt
              holdings {
                id
                type
                typeDisplay
                name
                ticker
                closingPrice
                closingPriceUpdatedAt
                quantity
                value
                costBasis
                userCostBasis
                account {
                  id
                  mask
                  icon
                  logoUrl
                  institution { id name __typename }
                  type { name display __typename }
                  subtype { name display __typename }
                  displayName
                  order
                  currentBalance
                  __typename
                }
                taxLots {
                  id
                  createdAt
                  acquisitionDate
                  acquisitionQuantity
                  costBasisPerUnit
                  __typename
                }
                __typename
              }
              security {
                id
                name
                ticker
                currentPrice
                currentPriceUpdatedAt
                closingPrice
                type
                typeDisplay
                categoryGroup
                __typename
              }
              __typename
            }
            __typename
          }
          __typename
        }
        __typename
      }
    }
    """
    raw = await query(
        "Web_GetPortfolio",
        query_text,
        {"portfolioInput": {"startDate": start_date, "endDate": end_date}},
    )
    portfolio = (raw.get("data") or {}).get("portfolio") or {}
    performance = portfolio.get("performance") or {}
    edges = ((portfolio.get("aggregateHoldings") or {}).get("edges")) or []
    paged_edges, page = page_items(edges, limit=limit, offset=offset)

    performance_summary = {
        "totalValue": performance.get("totalValue"),
        "totalChangePercent": performance.get("totalChangePercent"),
        "totalChangeDollars": performance.get("totalChangeDollars"),
        "oneDayChangePercent": performance.get("oneDayChangePercent"),
        "historicalChart": performance.get("historicalChart") or [],
        "benchmarkCount": len(performance.get("benchmarks") or []),
    }
    compact_result = {
        "timeframe": timeframe,
        "startDate": start_date,
        "endDate": end_date,
        "performance": performance_summary,
        "aggregateHoldings": [_holding_summary(edge) for edge in paged_edges],
        "page": page,
        "compact": True,
    }
    result = dict(compact_result)
    if include_details:
        result["aggregateHoldings"] = paged_edges
        result["compact"] = False
    if save_full_response:
        result["full_response_path"] = save_json_response(raw, prefix="monarch-get-investments")
    return ensure_context_safe_response(result, fallback=compact_result, prefix="monarch-get-investments")
