from datetime import date

from tools.decorators import read_tool, write_tool

from tools.client import drop_none, month_range, query


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
async def update_flex_budget_item(raw_input: dict) -> dict:
    """Update or create a flex-budget item using Monarch's app-native input.

    Args:
        raw_input: UpdateOrCreateFlexBudgetItemMutationInput.
    """
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
    return await query("Common_UpdateFlexBudgetMutation", query_text, {"input": raw_input})


@write_tool()
async def move_money_between_budget_categories(raw_input: dict) -> dict:
    """Move budget money between categories using Monarch's app-native input.

    Args:
        raw_input: MoveMoneyMutationInput.
    """
    query_text = """
    mutation Web_MoveMoneyMutation($input: MoveMoneyMutationInput!) {
      moveMoneyBetweenCategories(input: $input) {
        fromBudgetItem { id budgetAmount __typename }
        toBudgetItem { id budgetAmount __typename }
        __typename
      }
    }
    """
    return await query("Web_MoveMoneyMutation", query_text, {"input": raw_input})


@write_tool(destructive=True)
async def reset_budget(raw_input: dict) -> dict:
    """Recalculate/reset budget data using Monarch's app-native input.

    Args:
        raw_input: ResetBudgetMutationInput.
    """
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
    return await query("Web_RecalculateBudgetMutation", query_text, {"input": raw_input})


@write_tool(destructive=True)
async def reset_budget_rollover(raw_input: dict) -> dict:
    """Reset a budget rollover using Monarch's app-native input.

    Args:
        raw_input: ResetBudgetRolloverInput.
    """
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
    return await query("Web_ResetRolloverMutation", query_text, {"input": raw_input})


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
    query_text = """
    query GetNetWorthSnapshots($timeframe: String!) {
      accountChartData(chartType: "performance", dateRange: $timeframe) {
        date
        balance
      }
    }
    """
    return await query("GetNetWorthSnapshots", query_text, {"timeframe": timeframe})


@read_tool()
async def get_investments() -> dict:
    """Get investment holdings and performance."""
    query_text = """
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
    return await query("GetInvestments", query_text)
