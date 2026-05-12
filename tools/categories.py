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


def _category_group_fields() -> str:
    return """
      id
      name
      order
      type
      color
      groupLevelBudgetingEnabled
      budgetVariability
      rolloverPeriod {
        id
        startMonth
        endMonth
        startingBalance
        __typename
      }
      __typename
    """


def _payload_errors() -> str:
    return """
      errors {
        fieldErrors { field messages __typename }
        message
        code
        __typename
      }
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
async def get_category_groups(include_categories: bool = False) -> dict:
    """Get category groups, optionally with their child categories.

    Args:
        include_categories: Include child category IDs/names/order/icons.
    """
    categories_selection = """
        categories {
          id
          name
          order
          icon
          __typename
        }
    """ if include_categories else ""
    query_text = f"""
    query GetCategoryGroups {{
      categoryGroups {{
        {_category_group_fields()}
        {categories_selection}
      }}
    }}
    """
    return await query("GetCategoryGroups", query_text)


@tool
async def get_category_group(category_group_id: str, include_disabled_system_categories: bool | None = None) -> dict:
    """Get one category group and its categories.

    Args:
        category_group_id: Category group UUID.
        include_disabled_system_categories: Include disabled system categories.
    """
    query_text = f"""
    query GetCategoryGroup($id: UUID!, $includeDisabledSystemCategories: Boolean) {{
      categoryGroup(id: $id) {{
        {_category_group_fields()}
        categories(includeDisabledSystemCategories: $includeDisabledSystemCategories) {{
          id
          name
          order
          icon
          __typename
        }}
      }}
    }}
    """
    return await query(
        "GetCategoryGroup",
        query_text,
        {"id": category_group_id, "includeDisabledSystemCategories": include_disabled_system_categories},
    )


@tool
async def create_category_group(
    name: str,
    group_type: str,
    group_level_budgeting_enabled: bool | None = False,
    budget_variability: str | None = None,
    rollover_enabled: bool | None = False,
    rollover_start_month: str | None = None,
    rollover_type: str | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Create a category group.

    Args:
        name: Group name.
        group_type: Monarch group type such as income, expense, or transfer.
        group_level_budgeting_enabled: Whether the group budgets as a group.
        budget_variability: Optional budget variability value.
        rollover_enabled: Whether rollover is enabled.
        rollover_start_month: Optional rollover start month as YYYY-MM-DD.
        rollover_type: Optional Monarch rollover type.
        raw_input: Extra app-native CreateCategoryGroupInput fields.
    """
    input_data = drop_none(
        {
            "name": name,
            "type": group_type,
            "groupLevelBudgetingEnabled": group_level_budgeting_enabled,
            "budgetVariability": budget_variability,
            "rolloverEnabled": rollover_enabled,
            "rolloverStartMonth": rollover_start_month,
            "rolloverType": rollover_type,
        }
    )
    if raw_input:
        input_data.update(raw_input)
    query_text = f"""
    mutation Common_CreateCategoryGroup($input: CreateCategoryGroupInput!) {{
      createCategoryGroup(input: $input) {{
        categoryGroup {{ {_category_group_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Common_CreateCategoryGroup", query_text, {"input": input_data})


@tool
async def update_category_group(
    category_group_id: str,
    name: str | None = None,
    group_type: str | None = None,
    group_level_budgeting_enabled: bool | None = None,
    budget_variability: str | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Update a category group.

    Args:
        category_group_id: Category group UUID.
        name: New group name.
        group_type: Monarch group type such as income, expense, or transfer.
        group_level_budgeting_enabled: Whether the group budgets as a group.
        budget_variability: Optional budget variability value.
        raw_input: Extra app-native UpdateCategoryGroupInput fields.
    """
    input_data = drop_none(
        {
            "id": category_group_id,
            "name": name,
            "type": group_type,
            "groupLevelBudgetingEnabled": group_level_budgeting_enabled,
            "budgetVariability": budget_variability,
        }
    )
    if raw_input:
        input_data.update(raw_input)
    query_text = f"""
    mutation Common_UpdateCategoryGroup($input: UpdateCategoryGroupInput!) {{
      updateCategoryGroup(input: $input) {{
        categoryGroup {{ {_category_group_fields()} }}
        __typename
      }}
    }}
    """
    return await query("Common_UpdateCategoryGroup", query_text, {"input": input_data})


@tool
async def delete_category_group(category_group_id: str, move_to_group_id: str | None = None) -> dict:
    """Delete a category group and optionally move categories to another group.

    Args:
        category_group_id: Category group UUID.
        move_to_group_id: Optional destination category group UUID.
    """
    query_text = f"""
    mutation Common_DeleteCategoryGroup($id: UUID!, $moveToGroupId: UUID) {{
      deleteCategoryGroup(id: $id, moveToGroupId: $moveToGroupId) {{
        deleted
        {_payload_errors()}
        __typename
      }}
    }}
    """
    return await query(
        "Common_DeleteCategoryGroup",
        query_text,
        {"id": category_group_id, "moveToGroupId": move_to_group_id},
    )


@tool
async def update_category_group_order(category_group_id: str, order: int) -> dict:
    """Move a category group to a new order position.

    Args:
        category_group_id: Category group UUID.
        order: New integer order.
    """
    query_text = """
    mutation Web_UpdateCategoryGroupOrder($id: UUID!, $order: Int!) {
      updateCategoryGroupOrder(id: $id, order: $order) {
        categoryGroups { id __typename }
        __typename
      }
    }
    """
    return await query("Web_UpdateCategoryGroupOrder", query_text, {"id": category_group_id, "order": order})


@tool
async def update_category_order(category_id: str, category_group_id: str, order: int) -> dict:
    """Move a category within a category group.

    Args:
        category_id: Category UUID.
        category_group_id: Destination/current category group UUID.
        order: New integer order.
    """
    query_text = """
    mutation Web_UpdateCategoryOrder($id: UUID!, $categoryGroupId: UUID!, $order: Int!) {
      updateCategoryOrderInCategoryGroup(id: $id, categoryGroupId: $categoryGroupId, order: $order) {
        category { id __typename }
        __typename
      }
    }
    """
    return await query(
        "Web_UpdateCategoryOrder",
        query_text,
        {"id": category_id, "categoryGroupId": category_group_id, "order": order},
    )


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
