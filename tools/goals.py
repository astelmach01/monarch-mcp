from tools.decorators import read_tool, write_tool

from tools.client import drop_none, query


def _payload_error_fields() -> str:
    return """
      fieldErrors { field messages __typename }
      message
      code
      __typename
    """


def _account_fields() -> str:
    return """
      id
      displayName
      displayBalance
      icon
      logoUrl
      type { name display group __typename }
      subtype { name display __typename }
      institution { id name logo primaryColor __typename }
      __typename
    """


def _goal_fields() -> str:
    return f"""
      id
      name
      type
      objective
      defaultName
      archivedAt
      completedAt
      newGoalId
      imageStorageProvider
      imageStorageProviderId
      targetAmount
      startingAmount
      currentAmount
      completionPercent
      estimatedCompletionMonth
      estimatedMonthsUntilCompletion
      plannedMonthlyContribution
      plannedMonthlyPretaxContribution
      priority
      accountAllocations {{
        id
        amount
        currentAmount
        useEntireAccountBalance
        currentMonthChange {{ amount percent __typename }}
        account {{ {_account_fields()} }}
        __typename
      }}
      eligibleAccounts {{ {_account_fields()} }}
      suggestedAccounts {{ {_account_fields()} }}
      __typename
    """


def _savings_goal_fields() -> str:
    return """
      id
      type
      name
      createdAt
      archivedAt
      imageStorageProvider
      imageStorageProviderId
      status
      progress
      currentBalance
      targetDate
      targetAmount
      hasFutureBudgetDifferentFromCurrentMonth
      currentMonthActualBudgetAmount
      currentMonthPlannedContributionAmount
      plannedMonthlyContribution
      spendingTotal
      netContribution
      netContributionWithSpending
      netContributionWithoutSpending
      balanceThisMonth
      estimatedMonthsUntilCompletion
      forecastedCompletionDate
      isSinkingFund
      priority
      allocationAmountsByAccount {
        goalId
        adjustmentAmount
        totalAmount
        spendingAmount
        contributionsAmount
        withdrawalsAmount
        account {
          id
          icon
          displayName
          displayBalance
          logoUrl
          linkedGoal { id __typename }
          subtype { name display __typename }
          __typename
        }
        __typename
      }
      __typename
    """


@read_tool()
async def list_goals() -> dict:
    """List Monarch goals and accounts with unallocated goal balances."""
    query_text = f"""
    query Web_GoalsV2 {{
      goalsV2 {{
        {_goal_fields()}
      }}
      accountsWithUnallocatedBalancesForGoals {{
        {_account_fields()}
      }}
    }}
    """
    return await query("Web_GoalsV2", query_text)


@read_tool()
async def list_savings_goals() -> dict:
    """List Monarch's current savings goals experience goals."""
    query_text = f"""
    query Common_SavingsGoals {{
      savingsGoals {{
        {_savings_goal_fields()}
      }}
    }}
    """
    return await query("Common_SavingsGoals", query_text)


@read_tool()
async def get_savings_goal(goal_id: str) -> dict:
    """Get one savings goal.

    Args:
        goal_id: Goal ID from list_savings_goals.
    """
    query_text = f"""
    query Common_SavingsGoal($id: ID!) {{
      savingsGoal(id: $id) {{
        {_savings_goal_fields()}
      }}
    }}
    """
    return await query("Common_SavingsGoal", query_text, {"id": goal_id})


@read_tool()
async def get_goal_detail(goal_id: str) -> dict:
    """Get detail for one Monarch goal.

    Args:
        goal_id: Goal ID from list_goals.
    """
    query_text = f"""
    query Web_GoalDetailV2($goalId: ID!) {{
      goalV2(id: $goalId) {{
        {_goal_fields()}
      }}
    }}
    """
    return await query("Web_GoalDetailV2", query_text, {"goalId": goal_id})


@read_tool()
async def get_goal_options() -> dict:
    """Get Monarch's built-in goal creation options."""
    query_text = """
    query Common_GoalOptions {
      goalOptions {
        defaultName
        objective
        type
        allowMultiSelect
        defaultImageStorageProvider
        defaultImageStorageProviderId
        __typename
      }
    }
    """
    return await query("Common_GoalOptions", query_text)


@write_tool()
async def create_savings_goals(goals: list[dict]) -> dict:
    """Create one or more savings goals using Monarch's app-native goal objects.

    Args:
        goals: List of goal dicts such as name/type/imageStorageProvider/
            imageStorageProviderId from get_goal_options.
    """
    query_text = """
    mutation Common_CreateSavingsGoals($input: CreateSavingsGoalsInput!) {
      createSavingsGoals(input: $input) {
        savingsGoals {
          id
          type
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_CreateSavingsGoals", query_text, {"input": {"goals": goals}})


@write_tool(idempotent=True)
async def update_goal(
    goal_id: str,
    name: str | None = None,
    image_storage_provider: str | None = None,
    image_storage_provider_id: str | None = None,
    target_amount: float | None = None,
    starting_amount: float | None = None,
    planned_monthly_contribution: float | None = None,
    planned_monthly_pretax_contribution: float | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Update a Monarch goal.

    Args:
        goal_id: Goal ID from list_goals.
        name: New goal name.
        image_storage_provider: Monarch image provider string.
        image_storage_provider_id: Monarch image provider ID/path.
        target_amount: New target amount.
        starting_amount: New starting amount.
        planned_monthly_contribution: Planned monthly post-tax contribution.
        planned_monthly_pretax_contribution: Planned monthly pre-tax contribution.
        raw_input: Extra app-native UpdateGoalInput fields.
    """
    input_data = drop_none(
        {
            "id": goal_id,
            "name": name,
            "imageStorageProvider": image_storage_provider,
            "imageStorageProviderId": image_storage_provider_id,
            "targetAmount": target_amount,
            "startingAmount": starting_amount,
            "plannedMonthlyContribution": planned_monthly_contribution,
            "plannedMonthlyPretaxContribution": planned_monthly_pretax_contribution,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Mobile_UpdateGoalV2($input: UpdateGoalInput!) {{
      updateGoalV2(input: $input) {{
        goal {{
          {_goal_fields()}
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Mobile_UpdateGoalV2", query_text, {"input": input_data})


@write_tool(destructive=True)
async def delete_goal(goal_id: str, raw_input: dict | None = None) -> dict:
    """Delete a Monarch goal.

    Args:
        goal_id: Goal ID from list_goals.
        raw_input: Extra app-native DeleteGoalInput fields.
    """
    input_data = {"id": goal_id}
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Common_DeleteGoalV2($input: DeleteGoalInput!) {{
      deleteGoalV2(input: $input) {{
        success
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Common_DeleteGoalV2", query_text, {"input": input_data})


@write_tool(destructive=True)
async def delete_savings_goal(goal_id: str, raw_input: dict | None = None) -> dict:
    """Delete a savings goal.

    Args:
        goal_id: Goal ID from list_savings_goals.
        raw_input: Extra app-native DeleteSavingsGoalInput fields.
    """
    input_data = {"id": goal_id}
    if raw_input:
        input_data.update(raw_input)
    query_text = """
    mutation Common_DeleteSavingsGoal($input: DeleteSavingsGoalInput!) {
      deleteSavingsGoal(input: $input) {
        success
        errors { message __typename }
        __typename
      }
    }
    """
    return await query("Common_DeleteSavingsGoal", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def archive_savings_goal(goal_id: str, raw_input: dict | None = None) -> dict:
    """Archive a savings goal.

    Args:
        goal_id: Goal ID from list_savings_goals.
        raw_input: Extra app-native ArchiveSavingsGoalInput fields.
    """
    input_data = {"id": goal_id}
    if raw_input:
        input_data.update(raw_input)
    query_text = """
    mutation Common_ArchiveSavingsGoal($input: ArchiveSavingsGoalInput!) {
      archiveSavingsGoal(input: $input) {
        savingsGoal { id archivedAt status __typename }
        errors { message __typename }
        __typename
      }
    }
    """
    return await query("Common_ArchiveSavingsGoal", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def unarchive_savings_goal(goal_id: str, raw_input: dict | None = None) -> dict:
    """Unarchive a savings goal.

    Args:
        goal_id: Goal ID from list_savings_goals.
        raw_input: Extra app-native UnarchiveSavingsGoalInput fields.
    """
    input_data = {"id": goal_id}
    if raw_input:
        input_data.update(raw_input)
    query_text = """
    mutation Common_UnarchiveSavingsGoal($input: UnarchiveSavingsGoalInput!) {
      unarchiveSavingsGoal(input: $input) {
        savingsGoal { id archivedAt status __typename }
        errors { message __typename }
        __typename
      }
    }
    """
    return await query("Common_UnarchiveSavingsGoal", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def mark_goal_complete(goal_id: str, raw_input: dict | None = None) -> dict:
    """Mark a Monarch goal complete.

    Args:
        goal_id: Goal ID from list_goals.
        raw_input: Extra app-native MarkGoalCompleteInput fields.
    """
    input_data = {"id": goal_id}
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Common_MarkGoalComplete($input: MarkGoalCompleteInput!) {{
      markGoalComplete(input: $input) {{
        goal {{
          id
          completedAt
          __typename
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Common_MarkGoalComplete", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def mark_goal_incomplete(goal_id: str, raw_input: dict | None = None) -> dict:
    """Mark a completed Monarch goal incomplete.

    Args:
        goal_id: Goal ID from list_goals.
        raw_input: Extra app-native MarkGoalIncompleteInput fields.
    """
    input_data = {"id": goal_id}
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Common_MarkGoalIncomplete($input: MarkGoalIncompleteInput!) {{
      markGoalIncomplete(input: $input) {{
        goal {{
          id
          completedAt
          __typename
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Common_MarkGoalIncomplete", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def link_transaction_to_goal(
    transaction_id: str,
    goal_id: str | None = None,
    account_id: str | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Link or unlink a transaction to a goal.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        goal_id: Goal ID from list_goals. Use None to unlink the transaction.
        account_id: Optional account ID to disambiguate goal allocation.
        raw_input: Extra app-native LinkTransactionToGoalInput fields.
    """
    input_data = drop_none(
        {
            "transactionId": transaction_id,
            "goalId": goal_id,
            "accountId": account_id,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = """
    mutation Common_LinkTransactionToGoal($input: LinkTransactionToGoalInput!) {
      linkTransactionToGoal(input: $input) {
        goalEvent {
          id
          transaction {
            id
            savingsGoalEvent {
              id
              goal { id __typename }
              __typename
            }
            __typename
          }
          __typename
        }
        errors { message __typename }
        __typename
      }
    }
    """
    return await query("Common_LinkTransactionToGoal", query_text, {"input": input_data})


@write_tool()
async def spend_from_goal(
    transaction_id: str,
    goal_id: str | None = None,
    account_id: str | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Legacy Monarch mutation for spending from a goal.

    Args:
        transaction_id: Expense transaction UUID from get_transactions.
        goal_id: Goal ID from list_goals.
        account_id: Optional account ID to disambiguate goal allocation.
        raw_input: Extra app-native SpendFromGoalInput fields.
    """
    input_data = drop_none(
        {
            "transactionId": transaction_id,
            "goalId": goal_id,
            "accountId": account_id,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = """
    mutation Common_SpendFromGoal($input: SpendFromGoalInput!) {
      spendFromGoal(input: $input) {
        goalEvent { id __typename }
        errors { message __typename }
        __typename
      }
    }
    """
    return await query("Common_SpendFromGoal", query_text, {"input": input_data})


@write_tool()
async def contribute_to_savings_goal(raw_input: dict) -> dict:
    """Create a savings-goal contribution using Monarch's app-native input.

    Args:
        raw_input: CreateSavingsGoalContributionInput.
    """
    query_text = """
    mutation Common_ContributeToSavingsGoal($input: CreateSavingsGoalContributionInput!) {
      createSavingsGoalContribution(input: $input) {
        userNotice
        goalEvent {
          id
          goal { id currentBalance progress status __typename }
          account { id availableBalanceForGoalsUnmemoized includeInGoalContributions __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_ContributeToSavingsGoal", query_text, {"input": raw_input})


@write_tool()
async def withdraw_from_savings_goal(raw_input: dict) -> dict:
    """Create a savings-goal withdrawal using Monarch's app-native input.

    Args:
        raw_input: CreateSavingsGoalWithdrawalInput.
    """
    query_text = """
    mutation Common_WithdrawFromSavingsGoal($input: CreateSavingsGoalWithdrawalInput!) {
      createSavingsGoalWithdrawal(input: $input) {
        goalEvent {
          id
          goal { id currentBalance progress status __typename }
          account { id availableBalanceForGoalsUnmemoized includeInGoalContributions __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_WithdrawFromSavingsGoal", query_text, {"input": raw_input})


@write_tool(idempotent=True)
async def update_savings_goal_event(raw_input: dict) -> dict:
    """Update a savings-goal event using Monarch's app-native input.

    Args:
        raw_input: UpdateGoalEventInput.
    """
    query_text = """
    mutation Common_UpdateSavingsGoalEvent($input: UpdateGoalEventInput!) {
      updateGoalEvent(input: $input) {
        goalEvent {
          id
          amount
          type
          createdAt
          canDelete
          includeInBudget
          notes
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_UpdateSavingsGoalEvent", query_text, {"input": raw_input})


@write_tool(destructive=True)
async def delete_savings_goal_event(raw_input: dict) -> dict:
    """Delete a savings-goal event using Monarch's app-native input.

    Args:
        raw_input: DeleteGoalEventInput.
    """
    query_text = """
    mutation Common_DeleteSavingsGoalEvent($input: DeleteGoalEventInput!) {
      deleteGoalEvent(input: $input) {
        success
        __typename
      }
    }
    """
    return await query("Common_DeleteSavingsGoalEvent", query_text, {"input": raw_input})


@write_tool(idempotent=True)
async def update_goal_priorities(
    goals: list[dict] | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Update goal priorities.

    Args:
        goals: App-native list of {"id": goal_id, "priority": int} objects.
        raw_input: Full app-native UpdateGoalPrioritiesInput. Merged after goals.
    """
    input_data = {}
    if goals is not None:
        input_data["goals"] = goals
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Mobile_UpdateGoalsPriorities($input: UpdateGoalPrioritiesInput!) {{
      updateGoalPriorities(input: $input) {{
        goals {{
          id
          priority
          __typename
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Mobile_UpdateGoalsPriorities", query_text, {"input": input_data})


@write_tool(idempotent=True)
async def set_goal_planned_contribution(
    goal_id: str,
    amount: float,
    month: str,
    raw_input: dict | None = None,
) -> dict:
    """Create or update a goal's planned monthly contribution.

    Args:
        goal_id: Goal ID from list_goals.
        amount: Planned contribution amount.
        month: Month/date as Monarch Date, usually YYYY-MM-01.
        raw_input: Extra app-native CreateOrUpdateGoalPlannedContributionInput fields.
    """
    input_data = {"goalId": goal_id, "amount": amount, "month": month}
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Common_CreateOrUpdateGoalV2PlannedContributionMutation(
      $input: CreateOrUpdateGoalPlannedContributionInput!
    ) {{
      createOrUpdateGoalPlannedContribution(input: $input) {{
        goalPlannedContribution {{
          id
          amount
          month
          __typename
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    return await query(
        "Common_CreateOrUpdateGoalV2PlannedContributionMutation",
        query_text,
        {"input": input_data},
    )


@write_tool(idempotent=True)
async def set_savings_goal_budget_amount(raw_input: dict) -> dict:
    """Set a savings-goal budget amount using Monarch's app-native input.

    Args:
        raw_input: SetSavingsGoalBudgetAmountInput.
    """
    query_text = f"""
    mutation Common_SetSavingsGoalBudgetAmount($input: SetSavingsGoalBudgetAmountInput!) {{
      setSavingsGoalBudgetAmount(input: $input) {{
        success
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Common_SetSavingsGoalBudgetAmount", query_text, {"input": raw_input})
