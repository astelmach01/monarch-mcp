from fastmcp.tools import tool

from tools.client import query


def tag_fields(transaction_count: str = "") -> str:
    return f"""
      id
      name
      color
      order
      {transaction_count}
      __typename
    """


@tool
async def get_transaction_tags(
    search: str | None = None,
    limit: int | None = None,
    include_transaction_count: bool = False,
    bulk_params: dict | None = None,
) -> dict:
    """List/search household transaction tags.

    Args:
        search: Optional tag name search.
        limit: Optional result limit.
        include_transaction_count: Include transaction counts.
        bulk_params: Optional Monarch BulkTransactionDataParams.
    """
    query_text = f"""
    query Common_GetHouseholdTransactionTags(
      $search: String
      $limit: Int
      $bulkParams: BulkTransactionDataParams
      $includeTransactionCount: Boolean = false
    ) {{
      householdTransactionTags(
        search: $search
        limit: $limit
        bulkParams: $bulkParams
      ) {{
        {tag_fields("transactionCount @include(if: $includeTransactionCount)")}
      }}
    }}
    """
    return await query(
        "Common_GetHouseholdTransactionTags",
        query_text,
        {
            "search": search,
            "limit": limit,
            "bulkParams": bulk_params,
            "includeTransactionCount": include_transaction_count,
        },
    )


@tool
async def search_transaction_tags(search: str, limit: int = 20) -> dict:
    """Search household transaction tags by name.

    Args:
        search: Tag name search term.
        limit: Max results to return.
    """
    return await get_transaction_tags(search=search, limit=limit)


@tool
async def create_transaction_tag(name: str, color: str) -> dict:
    """Create a transaction tag.

    Args:
        name: Tag name.
        color: Tag color string used by Monarch, such as #ff6600.
    """
    query_text = f"""
    mutation Common_CreateTransactionTag($input: CreateTransactionTagInput!) {{
      createTransactionTag(input: $input) {{
        tag {{
          {tag_fields("transactionCount")}
        }}
        errors {{
          fieldErrors {{ field messages __typename }}
          message
          code
          __typename
        }}
        __typename
      }}
    }}
    """
    return await query(
        "Common_CreateTransactionTag",
        query_text,
        {"input": {"name": name, "color": color}},
    )


async def _get_transaction_tag_by_id(tag_id: str) -> dict:
    result = await get_transaction_tags(include_transaction_count=False)
    tags = (result.get("data") or {}).get("householdTransactionTags") or []
    for tag in tags:
        if tag.get("id") == tag_id:
            return tag
    raise ValueError(f"Tag not found: {tag_id}")


@tool
async def update_transaction_tag(
    tag_id: str,
    name: str | None = None,
    color: str | None = None,
) -> dict:
    """Update a transaction tag's name/color.

    Args:
        tag_id: Tag ID from get_transaction_tags.
        name: New tag name. Defaults to the current name.
        color: New tag color string. Defaults to the current color.
    """
    if name is None and color is None:
        raise ValueError("Provide name, color, or both.")
    if name is None or color is None:
        current_tag = await _get_transaction_tag_by_id(tag_id)
        name = name if name is not None else current_tag["name"]
        color = color if color is not None else current_tag["color"]

    query_text = f"""
    mutation Common_UpdateTransactionTag($input: UpdateTransactionTagInput!) {{
      updateTransactionTag(input: $input) {{
        tag {{
          {tag_fields()}
        }}
        errors {{
          fieldErrors {{ field messages __typename }}
          message
          code
          __typename
        }}
        __typename
      }}
    }}
    """
    return await query(
        "Common_UpdateTransactionTag",
        query_text,
        {"input": {"id": tag_id, "name": name, "color": color}},
    )


@tool
async def delete_transaction_tag(tag_id: str) -> dict:
    """Delete a household transaction tag.

    Args:
        tag_id: Tag ID from get_transaction_tags.
    """
    query_text = """
    mutation Common_DeleteHouseholdTransactionTag($tagId: ID!) {
      deleteTransactionTag(tagId: $tagId) {
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
    return await query(
        "Common_DeleteHouseholdTransactionTag",
        query_text,
        {"tagId": tag_id},
    )


@tool
async def update_transaction_tag_order(tag_id: str, order: int) -> dict:
    """Move a transaction tag to a new order position.

    Args:
        tag_id: Tag ID from get_transaction_tags.
        order: New integer sort order.
    """
    query_text = """
    mutation Common_UpdateTransactionTagOrder($tagId: ID!, $order: Int!) {
      updateTransactionTagOrder(tagId: $tagId, order: $order) {
        householdTransactionTags {
          id
          order
          __typename
        }
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
    return await query(
        "Common_UpdateTransactionTagOrder",
        query_text,
        {"tagId": tag_id, "order": order},
    )
