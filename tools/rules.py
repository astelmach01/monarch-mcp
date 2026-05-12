from fastmcp.tools import tool

from tools.client import query


def _rule_error_fields() -> str:
    return """
      errors {
        fieldErrors { field messages __typename }
        message
        code
        __typename
      }
      __typename
    """


def _rule_fields() -> str:
    return """
      id
      order
      merchantCriteriaUseOriginalStatement
      merchantCriteria { operator value __typename }
      originalStatementCriteria { operator value __typename }
      merchantNameCriteria { operator value __typename }
      amountCriteria {
        operator
        isExpense
        value
        valueRange { lower upper __typename }
        __typename
      }
      categoryIds
      accountIds
      categories { id name icon __typename }
      accounts { id displayName icon logoUrl __typename }
      criteriaOwnerIsJoint
      criteriaOwnerUserIds
      criteriaBusinessEntityIds
      criteriaBusinessEntityIsUnassigned
      setMerchantAction { id name __typename }
      setCategoryAction { id name icon __typename }
      addTagsAction { id name color __typename }
      needsReviewByUserAction { id displayName __typename }
      unassignNeedsReviewByUserAction
      sendNotificationAction
      setHideFromReportsAction
      setLinkToPaydownBudgetAction
      reviewStatusAction
      actionSetOwnerIsJoint
      actionSetBusinessEntityIsUnassigned
      recentApplicationCount
      lastAppliedAt
      splitTransactionsAction {
        amountType
        splitsInfo {
          categoryId
          merchantName
          amount
          tags
          hideFromReports
          reviewStatus
          needsReviewByUserId
          ownerUserId
          ownerIsJoint
          businessEntityId
          businessEntityIsUnassigned
          __typename
        }
        __typename
      }
      __typename
    """


@tool
async def get_transaction_rules() -> dict:
    """List transaction rules."""
    query_text = f"""
    query GetTransactionRules {{
      transactionRules {{
        {_rule_fields()}
      }}
    }}
    """
    return await query("GetTransactionRules", query_text)


@tool
async def preview_transaction_rule(rule: dict, offset: int = 0) -> dict:
    """Preview which transactions a rule would change.

    Args:
        rule: App-native TransactionRulePreviewInput.
        offset: Preview pagination offset.
    """
    query_text = """
    query Common_PreviewTransactionRule($rule: TransactionRulePreviewInput!, $offset: Int) {
      transactionRulePreview(input: $rule) {
        totalCount
        results(offset: $offset, limit: 30) {
          newName
          newSplitTransactions
          newCategory { id icon name __typename }
          newHideFromReports
          newTags { id name color order __typename }
          transaction {
            id
            date
            amount
            merchant { id name __typename }
            category { id name icon __typename }
            __typename
          }
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_PreviewTransactionRule", query_text, {"rule": rule, "offset": offset})


@tool
async def create_transaction_rule(rule_input: dict) -> dict:
    """Create a transaction rule.

    Args:
        rule_input: App-native CreateTransactionRuleInput. Set
            applyToExistingTransactions false unless intentionally backfilling.
    """
    query_text = f"""
    mutation Common_CreateTransactionRuleMutationV2($input: CreateTransactionRuleInput!) {{
      createTransactionRuleV2(input: $input) {{
        transactionRule {{ {_rule_fields()} }}
        {_rule_error_fields()}
      }}
    }}
    """
    return await query("Common_CreateTransactionRuleMutationV2", query_text, {"input": rule_input})


@tool
async def update_transaction_rule(rule_id: str, rule_input: dict) -> dict:
    """Update a transaction rule.

    Args:
        rule_id: Rule ID from get_transaction_rules.
        rule_input: App-native UpdateTransactionRuleInput fields, without or
            with id. The id argument wins if both are supplied.
    """
    input_data = {**rule_input, "id": rule_id}
    query_text = f"""
    mutation Common_UpdateTransactionRuleMutationV2($input: UpdateTransactionRuleInput!) {{
      updateTransactionRuleV2(input: $input) {{
        transactionRule {{ {_rule_fields()} }}
        {_rule_error_fields()}
      }}
    }}
    """
    return await query("Common_UpdateTransactionRuleMutationV2", query_text, {"input": input_data})


@tool
async def delete_transaction_rule(rule_id: str) -> dict:
    """Delete a transaction rule.

    Args:
        rule_id: Rule ID from get_transaction_rules.
    """
    query_text = """
    mutation Common_DeleteTransactionRule($id: ID!) {
      deleteTransactionRule(id: $id) {
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
    return await query("Common_DeleteTransactionRule", query_text, {"id": rule_id})


@tool
async def update_transaction_rule_order(rule_id: str, order: int) -> dict:
    """Move a transaction rule to a new order position.

    Args:
        rule_id: Rule ID from get_transaction_rules.
        order: New integer order.
    """
    query_text = """
    mutation Web_UpdateRuleOrderMutation($id: ID!, $order: Int!) {
      updateTransactionRuleOrderV2(id: $id, order: $order) {
        transactionRules { id order __typename }
        __typename
      }
    }
    """
    return await query("Web_UpdateRuleOrderMutation", query_text, {"id": rule_id, "order": order})


@tool
async def delete_all_transaction_rules() -> dict:
    """Delete all transaction rules. This is destructive."""
    query_text = """
    mutation Web_DeleteAllTransactionRulesMutation {
      deleteAllTransactionRules {
        deleted
        __typename
      }
    }
    """
    return await query("Web_DeleteAllTransactionRulesMutation", query_text)
