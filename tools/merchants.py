from tools.decorators import read_tool, write_tool

from tools.client import query


@read_tool()
async def search_merchants(search: str | None = None, limit: int = 25, offset: int = 0) -> dict:
    """Search Monarch merchants.

    Args:
        search: Merchant search string.
        limit: Result limit.
        offset: Pagination offset.
    """
    query_text = """
    query GetMerchantsSearchWithLogo($search: String, $limit: Int, $offset: Int) {
      merchants(search: $search, limit: $limit, offset: $offset, orderBy: TRANSACTION_COUNT) {
        id
        name
        transactionCount
        logoUrl
        __typename
      }
    }
    """
    return await query("GetMerchantsSearchWithLogo", query_text, {"search": search, "limit": limit, "offset": offset})


@read_tool()
async def get_merchant(merchant_id: str) -> dict:
    """Get merchant details used by Monarch's edit merchant dialog.

    Args:
        merchant_id: Merchant ID from transactions or search_merchants.
    """
    query_text = """
    query Common_GetEditMerchant($merchantId: ID!) {
      merchant(id: $merchantId) {
        id
        name
        logoUrl
        transactionCount
        ruleCount
        canBeDeleted
        hasActiveRecurringStreams
        recurringTransactionStream {
          id
          frequency
          amount
          baseDate
          isActive
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_GetEditMerchant", query_text, {"merchantId": merchant_id})


@write_tool(idempotent=True)
async def update_merchant(merchant_id: str, name: str | None = None, raw_input: dict | None = None) -> dict:
    """Update a merchant.

    Args:
        merchant_id: Merchant ID from transactions or search_merchants.
        name: New merchant name.
        raw_input: Extra app-native UpdateMerchantInput fields.
    """
    input_data = {"id": merchant_id}
    if name is not None:
        input_data["name"] = name
    if raw_input:
        input_data.update(raw_input)

    query_text = """
    mutation Common_UpdateMerchant($input: UpdateMerchantInput!) {
      updateMerchant(input: $input) {
        merchant {
          id
          name
          recurringTransactionStream {
            id
            frequency
            amount
            baseDate
            isActive
            __typename
          }
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
    return await query("Common_UpdateMerchant", query_text, {"input": input_data})


@write_tool(destructive=True)
async def delete_merchant(merchant_id: str, move_to_merchant_id: str | None = None) -> dict:
    """Delete/merge a merchant.

    Args:
        merchant_id: Merchant ID to delete.
        move_to_merchant_id: Optional merchant ID to move relations to.
    """
    query_text = """
    mutation Common_DeleteMerchant($merchantId: ID!, $moveToId: ID) {
      deleteMerchant(id: $merchantId, moveRelationsToMerchantId: $moveToId) {
        success
        __typename
      }
    }
    """
    return await query(
        "Common_DeleteMerchant",
        query_text,
        {"merchantId": merchant_id, "moveToId": move_to_merchant_id},
    )
