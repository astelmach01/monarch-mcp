from fastmcp.tools import tool

from tools.client import drop_none, query


def _category_fields() -> str:
    return """
      id
      order
      name
      icon
      systemCategory
      systemCategoryDisplayName
      budgetVariability
      excludeFromBudget
      isSystemCategory
      isDisabled
      group { id type groupLevelBudgetingEnabled __typename }
      rolloverPeriod {
        id
        startMonth
        startingBalance
        type
        frequency
        targetAmount
        __typename
      }
      __typename
    """


@tool
async def get_category_deletion_info(category_id: str) -> dict:
    """Preview what deleting/disabling a category would affect.

    Args:
        category_id: Category ID from get_categories.
    """
    query_text = """
    query Mobile_GetCategoryDeletionInfo($id: UUID!) {
      categoryDeletionInfo(id: $id) {
        category { id name icon isSystemCategory __typename }
        transactionsCount
        rulesCount
        __typename
      }
    }
    """
    return await query("Mobile_GetCategoryDeletionInfo", query_text, {"id": category_id})


@tool
async def create_category(
    name: str,
    group_id: str,
    icon: str,
    category_type: str | None = None,
    exclude_from_budget: bool | None = None,
    budget_variability: str | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Create a Monarch category.

    Args:
        name: Category name.
        group_id: Category group ID from get_categories.
        icon: Category emoji/icon.
        category_type: Optional Monarch type string.
        exclude_from_budget: Whether to exclude from budget.
        budget_variability: Optional Monarch budget variability string.
        raw_input: Extra app-native CreateCategoryInput fields.
    """
    input_data = drop_none(
        {
            "name": name,
            "group": group_id,
            "icon": icon,
            "type": category_type,
            "excludeFromBudget": exclude_from_budget,
            "budgetVariability": budget_variability,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Mobile_CreateCategoryMutation($input: CreateCategoryInput!) {{
      createCategory(input: $input) {{
        errors {{
          fieldErrors {{ field messages __typename }}
          message
          code
          __typename
        }}
        category {{ {_category_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Mobile_CreateCategoryMutation", query_text, {"input": input_data})


@tool
async def update_category(
    category_id: str,
    name: str | None = None,
    group_id: str | None = None,
    icon: str | None = None,
    category_type: str | None = None,
    exclude_from_budget: bool | None = None,
    budget_variability: str | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Update a Monarch category.

    Args:
        category_id: Category ID from get_categories.
        name: New name.
        group_id: New group ID.
        icon: New emoji/icon.
        category_type: Optional Monarch type string.
        exclude_from_budget: Whether to exclude from budget.
        budget_variability: Optional Monarch budget variability string.
        raw_input: Extra app-native UpdateCategoryInput fields.
    """
    input_data = drop_none(
        {
            "id": category_id,
            "name": name,
            "group": group_id,
            "icon": icon,
            "type": category_type,
            "excludeFromBudget": exclude_from_budget,
            "budgetVariability": budget_variability,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = f"""
    mutation Mobile_UpdateCategoryMutation($input: UpdateCategoryInput!) {{
      updateCategory(input: $input) {{
        errors {{
          fieldErrors {{ field messages __typename }}
          message
          code
          __typename
        }}
        category {{ {_category_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Mobile_UpdateCategoryMutation", query_text, {"input": input_data})


@tool
async def delete_category(category_id: str, move_to_category_id: str | None = None) -> dict:
    """Delete/disable a category and move transactions/rules elsewhere.

    Args:
        category_id: Category ID from get_categories.
        move_to_category_id: Optional destination category. Defaults to Monarch's
            uncategorized behavior.
    """
    query_text = """
    mutation Mobile_DeleteCategoryMutation($id: UUID!, $moveToCategoryId: UUID) {
      deleteCategory(id: $id, moveToCategoryId: $moveToCategoryId) {
        errors {
          fieldErrors { field messages __typename }
          message
          code
          __typename
        }
        deleted
        __typename
      }
    }
    """
    return await query(
        "Mobile_DeleteCategoryMutation",
        query_text,
        {"id": category_id, "moveToCategoryId": move_to_category_id},
    )
