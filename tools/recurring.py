from tools.decorators import read_tool, write_tool

from tools.client import query


@read_tool()
async def get_recurring_streams(include_liabilities: bool | None = None) -> dict:
    """List recurring streams, including pending review streams.

    Args:
        include_liabilities: Include credit/liability recurring streams.
    """
    query_text = """
    query Common_GetRecurringStreams($includeLiabilities: Boolean) {
      recurringTransactionStreams(includePending: true, includeLiabilities: $includeLiabilities) {
        stream {
          id
          reviewStatus
          frequency
          amount
          baseDate
          dayOfTheMonth
          isApproximate
          name
          logoUrl
          recurringType
          isActive
          merchant { id name logoUrl __typename }
          creditReportLiabilityAccount {
            id
            account { id displayName __typename }
            lastStatement { id dueDate __typename }
            __typename
          }
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_GetRecurringStreams", query_text, {"includeLiabilities": include_liabilities})


@write_tool()
async def create_recurring_stream(merchant_id: str, amount: float, base_date: str, frequency: str) -> dict:
    """Create a recurring transaction stream for a merchant.

    Args:
        merchant_id: Merchant ID.
        amount: Expected amount.
        base_date: Base date as YYYY-MM-DD.
        frequency: Monarch frequency string such as every_month.
    """
    query_text = """
    mutation CreateRecurringTransactionStreamMutation(
      $merchantId: ID!
      $amount: Float!
      $baseDate: Date!
      $frequency: String!
    ) {
      createRecurringTransactionStream(
        merchantId: $merchantId
        amount: $amount
        baseDate: $baseDate
        frequency: $frequency
      ) {
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
    return await query(
        "CreateRecurringTransactionStreamMutation",
        query_text,
        {"merchantId": merchant_id, "amount": amount, "baseDate": base_date, "frequency": frequency},
    )


@write_tool(destructive=True)
async def delete_recurring_stream(stream_id: str) -> dict:
    """Delete a recurring transaction stream.

    Args:
        stream_id: Recurring stream ID from get_recurring/get_merchant.
    """
    query_text = """
    mutation DeleteRecurringTransactionStreamMutation($id: ID!) {
      deleteRecurringTransactionStream(id: $id) {
        success
        __typename
      }
    }
    """
    return await query("DeleteRecurringTransactionStreamMutation", query_text, {"id": stream_id})


@write_tool(idempotent=True)
async def mark_stream_not_recurring(stream_id: str) -> dict:
    """Mark a stream as not recurring.

    Args:
        stream_id: Recurring stream ID from get_recurring/get_merchant.
    """
    query_text = """
    mutation Common_MarkAsNotRecurring($streamId: ID!) {
      markStreamAsNotRecurring(streamId: $streamId) {
        success
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
    return await query("Common_MarkAsNotRecurring", query_text, {"streamId": stream_id})


@write_tool()
async def trigger_recurring_merchant_search() -> dict:
    """Ask Monarch to rescan transactions for recurring merchants."""
    query_text = """
    mutation Common_TriggerRecurringMerchantSearch {
      triggerRecurringMerchantSearch {
        success
        __typename
      }
    }
    """
    return await query("Common_TriggerRecurringMerchantSearch", query_text)
