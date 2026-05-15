from tools.client import drop_none, query
from tools.decorators import write_tool


def _payload_error_fields() -> str:
    return """
      fieldErrors { field messages __typename }
      message
      code
      __typename
    """


def _goal_account_allocation_fields() -> str:
    return """
      id
      amount
      currentAmount
      useEntireAccountBalance
      account {
        id
        displayName
        availableBalanceForGoals
        __typename
      }
      __typename
    """


def _verified_goal_fields() -> str:
    return """
      id
      name
      type
      objective
      targetAmount
      currentAmount
      completionPercent
      plannedMonthlyContribution
      priority
      accountAllocations {
        id
        amount
        currentAmount
        useEntireAccountBalance
        account {
          id
          displayName
          displayBalance
          type { display __typename }
          subtype { display __typename }
          __typename
        }
        __typename
      }
      __typename
    """


def _account_summary(account: dict | None) -> dict | None:
    if not account:
        return None
    return {
        "id": account.get("id"),
        "displayName": account.get("displayName"),
        "displayBalance": account.get("displayBalance"),
        "type": (account.get("type") or {}).get("display"),
        "subtype": (account.get("subtype") or {}).get("display"),
    }


def _verified_goal_summary(goal: dict | None) -> dict | None:
    if not goal:
        return None
    allocations = goal.get("accountAllocations") or []
    return {
        "id": goal.get("id"),
        "name": goal.get("name"),
        "type": goal.get("type"),
        "objective": goal.get("objective"),
        "targetAmount": goal.get("targetAmount"),
        "currentAmount": goal.get("currentAmount"),
        "completionPercent": goal.get("completionPercent"),
        "plannedMonthlyContribution": goal.get("plannedMonthlyContribution"),
        "priority": goal.get("priority"),
        "accountAllocationCount": len(allocations),
        "accountAllocations": [
            {
                "id": allocation.get("id"),
                "amount": allocation.get("amount"),
                "currentAmount": allocation.get("currentAmount"),
                "useEntireAccountBalance": allocation.get("useEntireAccountBalance"),
                "account": _account_summary(allocation.get("account")),
            }
            for allocation in allocations
        ],
    }


async def _verified_goal(goal_id: str) -> dict | None:
    query_text = f"""
    query VerifyGoalAccountAllocations($goalId: ID!) {{
      goalV2(id: $goalId) {{
        {_verified_goal_fields()}
      }}
    }}
    """
    raw = await query("VerifyGoalAccountAllocations", query_text, {"goalId": goal_id})
    return _verified_goal_summary((raw.get("data") or {}).get("goalV2"))


@write_tool()
async def link_goal_to_account(
    goal_id: str,
    account_id: str,
    use_entire_account_balance: bool = True,
    amount: float | None = None,
    verify: bool = True,
    raw_input: dict | None = None,
) -> dict:
    """Allocate an account balance to a goals-v2 goal.

    Args:
        goal_id: Goal ID from list_goals.
        account_id: Account ID from get_accounts or a goal's eligibleAccounts.
        use_entire_account_balance: Whether Monarch should allocate the full account balance.
        amount: Explicit allocation amount. Usually None when use_entire_account_balance is true.
        verify: Fetch and return the refreshed goal after the write.
        raw_input: Extra app-native CreateGoalAccountAllocationInput fields.
    """
    input_data = drop_none(
        {
            "goalId": goal_id,
            "accountId": account_id,
            "useEntireAccountBalance": use_entire_account_balance,
            "amount": amount,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Common_CreateGoalAccountAllocation($input: CreateGoalAccountAllocationInput!) {{
      createGoalAccountAllocation(input: $input) {{
        goalAccountAllocation {{
          {_goal_account_allocation_fields()}
        }}
        goal {{
          id
          name
          currentAmount
          completionPercent
          __typename
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    result = await query("Common_CreateGoalAccountAllocation", query_text, {"input": input_data})
    if verify:
        result["verifiedGoal"] = await _verified_goal(goal_id)
    return result


@write_tool(destructive=True)
async def unlink_goal_from_account(
    goal_id: str,
    account_id: str,
    verify: bool = True,
    raw_input: dict | None = None,
) -> dict:
    """Remove a goals-v2 account allocation.

    Args:
        goal_id: Goal ID from list_goals.
        account_id: Account ID currently allocated to the goal.
        verify: Fetch and return the refreshed goal after the write.
        raw_input: Extra app-native DeleteGoalAccountAllocationInput fields.
    """
    input_data = {"goalId": goal_id, "accountId": account_id}
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Common_DeleteGoalAccountAllocation($input: DeleteGoalAccountAllocationInput!) {{
      deleteGoalAccountAllocation(input: $input) {{
        goal {{
          id
          name
          currentAmount
          completionPercent
          __typename
        }}
        account {{
          id
          displayName
          availableBalanceForGoals
          __typename
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    result = await query("Common_DeleteGoalAccountAllocation", query_text, {"input": input_data})
    if verify:
        result["verifiedGoal"] = await _verified_goal(goal_id)
    return result


@write_tool(idempotent=True)
async def update_goal_account_allocation(
    allocation_id: str,
    goal_id: str,
    account_id: str,
    amount: float | None = None,
    use_entire_account_balance: bool | None = None,
    verify: bool = True,
    raw_input: dict | None = None,
) -> dict:
    """Update an existing goals-v2 account allocation amount/settings.

    Args:
        allocation_id: Goal account allocation ID from a goal's accountAllocations.
        goal_id: Goal ID from list_goals.
        account_id: Account ID for the allocation.
        amount: Explicit allocation amount.
        use_entire_account_balance: Whether Monarch should allocate the full account balance.
        verify: Fetch and return the refreshed goal after the write.
        raw_input: Extra app-native UpdateGoalAccountAllocationInput fields.
    """
    input_data = drop_none(
        {
            "id": allocation_id,
            "goalId": goal_id,
            "accountId": account_id,
            "amount": amount,
            "useEntireAccountBalance": use_entire_account_balance,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Common_UpdateGoalAccountAllocation($input: UpdateGoalAccountAllocationInput!) {{
      updateGoalAccountAllocation(input: $input) {{
        goalAccountAllocation {{
          {_goal_account_allocation_fields()}
        }}
        goal {{
          id
          name
          currentAmount
          completionPercent
          __typename
        }}
        errors {{ {_payload_error_fields()} }}
        __typename
      }}
    }}
    """
    result = await query("Common_UpdateGoalAccountAllocation", query_text, {"input": input_data})
    if verify:
        result["verifiedGoal"] = await _verified_goal(goal_id)
    return result
