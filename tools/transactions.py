from datetime import date, timedelta

from fastmcp.tools import tool

from tools.client import drop_none, query, transaction_mutation_fields


@tool
async def get_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    category_ids: list[str] | None = None,
    account_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Search and list transactions with optional filters.

    Args:
        start_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        end_date: End date (YYYY-MM-DD). Defaults to today.
        search: Search term for merchant name or description.
        category_ids: Filter by category IDs (use get_categories to find IDs).
        account_ids: Filter by account IDs (use get_accounts to find IDs).
        tag_ids: Filter by tag IDs.
        limit: Max results to return (default 50).
        offset: Offset for pagination.
    """
    if not start_date:
        start_date = (date.today() - timedelta(days=30)).isoformat()
    if not end_date:
        end_date = date.today().isoformat()

    filters: dict = {
        "startDate": start_date,
        "endDate": end_date,
        "transactionVisibility": "non_hidden_transactions_only",
    }
    if search:
        filters["search"] = search
    if category_ids:
        filters["categories"] = category_ids
    if account_ids:
        filters["accounts"] = account_ids
    if tag_ids:
        filters["tags"] = tag_ids

    query_text = """
    query Web_GetTransactionsList($offset: Int, $limit: Int, $filters: TransactionFilterInput, $orderBy: TransactionOrdering) {
      allTransactions(filters: $filters) {
        totalCount
        results(offset: $offset, limit: $limit, orderBy: $orderBy) {
          id
          amount
          pending
          date
          hideFromReports
          notes
          isRecurring
          reviewStatus
          needsReview
          isSplitTransaction
          category {
            id name icon systemCategory
            group { id type __typename }
            __typename
          }
          merchant {
            name id transactionsCount logoUrl
            recurringTransactionStream { frequency isActive __typename }
            __typename
          }
          tags { id name color order __typename }
          account { id displayName icon logoUrl __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await query(
        "Web_GetTransactionsList",
        query_text,
        {"filters": filters, "limit": limit, "offset": offset, "orderBy": "date"},
    )


@tool
async def get_transaction(transaction_id: str) -> dict:
    """Get full details for a single transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
    """
    query_text = """
    query Common_TransactionDetailQuery($id: UUID!) {
      getTransaction(id: $id) {
        id
        amount
        pending
        date
        hideFromReports
        hiddenByAccount
        plaidName
        notes
        isRecurring
        reviewStatus
        needsReview
        isSplitTransaction
        dataProviderDescription
        deletedAt
        deletedByType
        attachments { id filename originalAssetUrl __typename }
        category { id name icon systemCategory group { id type __typename } __typename }
        merchant { id name transactionsCount logoUrl __typename }
        tags { id name color order __typename }
        account { id displayName icon logoUrl __typename }
        goal { id name __typename }
        savingsGoalEvent { id goal { id name __typename } __typename }
        ownedByUser { id displayName profilePictureUrl __typename }
        businessEntity { id name logoUrl color __typename }
        __typename
      }
    }
    """
    return await query("Common_TransactionDetailQuery", query_text, {"id": transaction_id})


@tool
async def get_transaction_split_details(transaction_id: str) -> dict:
    """Get the fields Monarch's split editor uses for one transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
    """
    query_text = """
    query Common_TransactionSplitQuery($id: UUID!) {
      getTransaction(id: $id) {
        id
        amount
        reviewedAt
        needsReview
        reviewStatus
        hideFromReports
        dataProviderDescription
        notes
        category { id name icon group { type __typename } __typename }
        merchant { id name logoUrl __typename }
        needsReviewByUser { id name __typename }
        tags { id name color __typename }
        savingsGoalEvent { id goal { id __typename } account { id __typename } __typename }
        ownedByUser { id displayName profilePictureUrl __typename }
        businessEntity { id name logoUrl color __typename }
        splitTransactions {
          id
          amount
          notes
          date
          hideFromReports
          reviewStatus
          needsReview
          merchant { id name logoUrl __typename }
          category { id icon name __typename }
          goal { id name imageStorageProvider imageStorageProviderId __typename }
          savingsGoalEvent { id goal { id __typename } account { id __typename } __typename }
          needsReviewByUser { id name __typename }
          tags { id name color __typename }
          ownedByUser { id displayName profilePictureUrl __typename }
          businessEntity { id name logoUrl color __typename }
          businessEntityOverriddenAt
          __typename
        }
        __typename
      }
    }
    """
    return await query("Common_TransactionSplitQuery", query_text, {"id": transaction_id})


@tool
async def split_transaction(transaction_id: str, split_data: list[dict]) -> dict:
    """Create, update, or clear transaction splits.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        split_data: List of Monarch split objects. Each split may include amount,
            categoryId, merchantName, notes, hideFromReports, reviewStatus, tags,
            needsReview, needsReviewByUserId, ownerUserId, businessEntityId, or id
            for existing split rows. Amounts must add up to the original
            transaction amount. Pass an empty list to remove all splits.
    """
    query_text = """
    mutation Common_SplitTransactionMutation($input: UpdateTransactionSplitMutationInput!) {
      updateTransactionSplit(input: $input) {
        errors {
          fieldErrors { field messages __typename }
          message
          code
          __typename
        }
        transaction {
          id
          hasSplitTransactions
          splitTransactions {
            id
            amount
            notes
            hideFromReports
            reviewStatus
            merchant { id name __typename }
            category { id icon name __typename }
            goal { id __typename }
            savingsGoalEvent { id goal { id __typename } account { id __typename } __typename }
            needsReviewByUser { id __typename }
            tags { id __typename }
            ownedByUser { id __typename }
            businessEntity { id name logoUrl color __typename }
            businessEntityOverriddenAt
            __typename
          }
          __typename
        }
        __typename
      }
    }
    """
    return await query(
        "Common_SplitTransactionMutation",
        query_text,
        {"input": {"transactionId": transaction_id, "splitData": split_data}},
    )


@tool
async def unsplit_transaction(transaction_id: str) -> dict:
    """Remove all splits from a transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
    """
    return await split_transaction(transaction_id, [])


@tool
async def update_transaction(
    transaction_id: str,
    category_id: str | None = None,
    merchant_name: str | None = None,
    notes: str | None = None,
    transaction_date: str | None = None,
    amount: float | None = None,
    hide_from_reports: bool | None = None,
    review_status: str | None = None,
    tag_ids: list[str] | None = None,
    is_recurring: bool | None = None,
    raw_updates: dict | None = None,
) -> dict:
    """Update a transaction's categorization/details.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        category_id: Category ID from get_categories. Sends Monarch's app-native
            `category` field.
        merchant_name: New merchant/display name.
        notes: Notes text. Use an empty string to clear notes.
        transaction_date: Transaction date as YYYY-MM-DD.
        amount: Transaction amount, using Monarch's sign convention.
        hide_from_reports: Whether to hide the transaction from reports.
        review_status: Monarch review status such as needs_review or approved.
        tag_ids: Replace tags with these tag IDs.
        is_recurring: Whether the transaction should be recurring.
        raw_updates: Extra app-native UpdateTransactionMutationInput fields.
    """
    input_data = drop_none(
        {
            "id": transaction_id,
            "category": category_id,
            "merchantName": merchant_name,
            "notes": notes,
            "date": transaction_date,
            "amount": amount,
            "hideFromReports": hide_from_reports,
            "reviewStatus": review_status,
            "isRecurring": is_recurring,
        }
    )
    if raw_updates:
        input_data.update(raw_updates)

    query_text = f"""
    mutation Web_UpdateTransactionOverview($input: UpdateTransactionMutationInput!) {{
      updateTransaction(input: $input) {{
        {transaction_mutation_fields()}
      }}
    }}
    """
    result = await query("Web_UpdateTransactionOverview", query_text, {"input": input_data})
    if tag_ids is not None:
        result["set_tags"] = await set_transaction_tags(transaction_id, tag_ids)
    return result


@tool
async def mark_transaction_reviewed(transaction_id: str, reviewed: bool = True) -> dict:
    """Mark a transaction reviewed or back to needs-review.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        reviewed: True marks approved; False marks needs_review.
    """
    return await update_transaction(
        transaction_id=transaction_id,
        review_status="approved" if reviewed else "needs_review",
    )


@tool
async def create_transaction(
    account_id: str,
    amount: float,
    transaction_date: str,
    merchant_name: str,
    category_id: str | None = None,
    notes: str | None = None,
    review_status: str | None = None,
    hide_from_reports: bool | None = None,
    should_update_balance: bool = True,
    tag_ids: list[str] | None = None,
    raw_input: dict | None = None,
) -> dict:
    """Create a manual transaction in Monarch.

    Args:
        account_id: Account ID from get_accounts.
        amount: Transaction amount, using Monarch's sign convention.
        transaction_date: Transaction date as YYYY-MM-DD.
        merchant_name: Merchant/display name.
        category_id: Category ID from get_categories.
        notes: Optional notes.
        review_status: Optional review status such as approved.
        hide_from_reports: Whether to hide from reports.
        should_update_balance: Whether to adjust the manual account balance.
        tag_ids: Optional tag IDs.
        raw_input: Extra app-native CreateTransactionMutationInput fields.
    """
    input_data = drop_none(
        {
            "accountId": account_id,
            "amount": amount,
            "date": transaction_date,
            "merchantName": merchant_name,
            "categoryId": category_id,
            "notes": notes,
            "reviewStatus": review_status,
            "hideFromReports": hide_from_reports,
            "shouldUpdateBalance": should_update_balance,
        }
    )
    if raw_input:
        input_data.update(raw_input)

    query_text = """
    mutation Common_CreateTransactionMutation($input: CreateTransactionMutationInput!) {
      createTransaction(input: $input) {
        transaction { id __typename }
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
    result = await query("Common_CreateTransactionMutation", query_text, {"input": input_data})
    create_payload = (result.get("data") or {}).get("createTransaction") or {}
    new_transaction_id = (create_payload.get("transaction") or {}).get("id")
    if new_transaction_id and tag_ids is not None:
        result["set_tags"] = await set_transaction_tags(new_transaction_id, tag_ids)
    return result


@tool
async def set_transaction_tags(transaction_id: str, tag_ids: list[str]) -> dict:
    """Replace a transaction's tags.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        tag_ids: Tag IDs to set. Use an empty list to clear tags.
    """
    query_text = """
    mutation Web_SetTransactionTags($input: SetTransactionTagsInput!) {
      setTransactionTags(input: $input) {
        errors {
          fieldErrors { field messages __typename }
          message
          code
          __typename
        }
        transaction {
          id
          tags { id name color order __typename }
          __typename
        }
        __typename
      }
    }
    """
    return await query(
        "Web_SetTransactionTags",
        query_text,
        {"input": {"transactionId": transaction_id, "tagIds": tag_ids}},
    )


@tool
async def delete_transaction(transaction_id: str) -> dict:
    """Delete one transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
    """
    query_text = """
    mutation Common_DeleteTransactionMutation($input: DeleteTransactionMutationInput!) {
      deleteTransaction(input: $input) {
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
    return await query("Common_DeleteTransactionMutation", query_text, {"input": {"transactionId": transaction_id}})


@tool
async def bulk_update_transactions(
    transaction_ids: list[str],
    updates: dict | None = None,
    category_id: str | None = None,
    merchant_name: str | None = None,
    notes: str | None = None,
    transaction_date: str | None = None,
    hide_from_reports: bool | None = None,
    review_status: str | None = None,
    tag_ids: list[str] | None = None,
) -> dict:
    """Bulk-update selected transactions.

    Args:
        transaction_ids: Transaction UUIDs from get_transactions.
        updates: App-native TransactionUpdateParams. Merged after convenience args.
        category_id: Category ID from get_categories.
        merchant_name: New merchant/display name.
        notes: Notes text. Use an empty string to clear notes.
        transaction_date: Transaction date as YYYY-MM-DD.
        hide_from_reports: Whether to hide from reports.
        review_status: Monarch review status such as needs_review or approved.
        tag_ids: Replace tags with these tag IDs.
    """
    update_data = drop_none(
        {
            "categoryId": category_id,
            "merchantName": merchant_name,
            "notes": notes,
            "date": transaction_date,
            "hideFromReports": hide_from_reports,
            "reviewStatus": review_status,
            "tags": tag_ids,
        }
    )
    if updates:
        update_data.update(updates)

    query_text = """
    mutation Common_BulkUpdateTransactionsMutation(
      $selectedTransactionIds: [ID!]
      $excludedTransactionIds: [ID!]
      $allSelected: Boolean!
      $expectedAffectedTransactionCount: Int!
      $updates: TransactionUpdateParams!
      $filters: TransactionFilterInput
    ) {
      bulkUpdateTransactions(
        selectedTransactionIds: $selectedTransactionIds
        excludedTransactionIds: $excludedTransactionIds
        updates: $updates
        allSelected: $allSelected
        expectedAffectedTransactionCount: $expectedAffectedTransactionCount
        filters: $filters
      ) {
        success
        affectedCount
        errors { message __typename }
        __typename
      }
    }
    """
    return await query(
        "Common_BulkUpdateTransactionsMutation",
        query_text,
        {
            "selectedTransactionIds": transaction_ids,
            "excludedTransactionIds": [],
            "allSelected": False,
            "expectedAffectedTransactionCount": len(transaction_ids),
            "updates": update_data,
            "filters": {},
        },
    )
