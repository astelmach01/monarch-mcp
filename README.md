# Monarch Money MCP Server

An MCP (Model Context Protocol) server that connects AI assistants to [Monarch Money](https://www.monarchmoney.com/) for personal finance tracking.

## Features

- **Accounts**: View all financial accounts, balances, and connection status
- **Transactions**: Search and filter transactions by date, category, account, or keyword
- **Transaction CRUD**: View, create, update, bulk-update, mark reviewed, and delete transactions
- **Transaction Splits**: Inspect, split, and unsplit transactions
- **Tags**: List, search, create, update, delete, and reorder transaction tags
- **Categories**: Create, update, preview delete impact, and delete/move categories
- **Category Groups**: Create, update, delete, inspect, and reorder category groups/categories
- **Merchants**: Search, inspect, rename, and merge/delete merchants
- **Rules**: List, preview, create, update, reorder, and delete transaction rules
- **Attachments**: Upload, inspect, and delete transaction attachments
- **Cash Flow**: Monthly income/expense breakdown with savings rate
- **Budgets**: Budget tracking plus budget item/settings/rollover edits
- **Goals**: List, create, update, delete, prioritize, link transactions, and manage goal events
- **Recurring**: Track bills and recurring transactions, list streams, rescan, and manage streams
- **Net Worth**: Historical net worth snapshots
- **Investments**: Portfolio holdings and performance
- **Auto-auth**: Automatic token refresh with optional MFA/TOTP support

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp env.template .env
```

Get your Monarch Money token:
1. Log into [app.monarchmoney.com](https://app.monarchmoney.com)
2. Open browser DevTools → Network tab
3. Find any request to `api.monarch.com` and copy the `authorization` header value (after "Token ")

### 3. Add to Claude Code

Add to your `~/.claude.json` under `mcpServers`:

```json
{
  "monarch-money": {
    "type": "stdio",
    "command": "uv",
    "args": ["run", "--directory", "/path/to/monarch-mcp", "python", "server.py"],
    "env": {
      "MONARCH_TOKEN": "your_token_here"
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `get_accounts` | All accounts with balances and status |
| `get_account_balances_summary` | Quick net worth overview |
| `get_transactions` | Search/filter transactions |
| `get_transaction` | Details for one transaction |
| `explain_transaction` | Monarch's explanation for one transaction |
| `get_transaction_split_details` | Split-editor detail for one transaction |
| `split_transaction` | Create or update split rows |
| `unsplit_transaction` | Remove all split rows |
| `update_transaction` | Update category, merchant, notes, date, amount, review status, tags, etc. |
| `mark_transaction_reviewed` | Mark a transaction reviewed or needs-review |
| `create_transaction` | Create a manual transaction |
| `set_transaction_tags` | Replace tags on one transaction |
| `delete_transaction` | Delete one transaction |
| `bulk_delete_transactions` | Delete a set of transactions |
| `bulk_update_transactions` | Update a set of transactions |
| `start_transactions_download` | Start a CSV transaction export |
| `get_transactions_download_session` | Check a transaction export session |
| `move_transactions` | Move transactions using Monarch's app-native input |
| `get_transaction_attachment_upload_info` | Get signed upload fields for an attachment |
| `upload_transaction_attachment` | Upload and attach a local file |
| `add_transaction_attachment_metadata` | Attach an already-uploaded asset |
| `get_transaction_attachment` | Get attachment detail/download URL |
| `delete_transaction_attachment` | Delete a transaction attachment |
| `get_transaction_tags` | List transaction tags |
| `search_transaction_tags` | Search transaction tags by name |
| `create_transaction_tag` | Create a transaction tag |
| `update_transaction_tag` | Update a transaction tag |
| `delete_transaction_tag` | Delete a transaction tag |
| `update_transaction_tag_order` | Reorder transaction tags |
| `get_category_deletion_info` | Preview category delete/move impact |
| `get_category_groups` | List category groups |
| `get_category_group` | Inspect one category group |
| `create_category_group` | Create a category group |
| `update_category_group` | Update a category group |
| `delete_category_group` | Delete/move a category group |
| `update_category_group_order` | Reorder a category group |
| `update_category_order` | Reorder a category within a group |
| `create_category` | Create a transaction category |
| `update_category` | Update a transaction category |
| `delete_category` | Delete/disable a category and move relations |
| `search_merchants` | Search merchants |
| `get_merchant` | Merchant edit details |
| `update_merchant` | Rename/update a merchant |
| `delete_merchant` | Delete/merge a merchant |
| `get_transaction_rules` | List transaction rules |
| `preview_transaction_rule` | Preview a transaction rule |
| `create_transaction_rule` | Create a transaction rule |
| `update_transaction_rule` | Update a transaction rule |
| `delete_transaction_rule` | Delete a transaction rule |
| `update_transaction_rule_order` | Reorder a transaction rule |
| `delete_all_transaction_rules` | Delete all transaction rules |
| `get_cash_flow` | Monthly income/expense breakdown |
| `get_budgets` | Budget vs actual spending |
| `get_budget_status` | Budget initialization status |
| `get_budget_settings` | Household budget settings |
| `update_budget_settings` | Update household budget settings |
| `update_budget_item` | Update/create category or group budget amount |
| `update_flex_budget_item` | Update/create flex budget amount |
| `move_money_between_budget_categories` | Move budget money between categories |
| `reset_budget` | Recalculate/reset budget data |
| `reset_budget_rollover` | Reset a budget rollover |
| `list_goals` | List legacy/goals-v2 goals |
| `list_savings_goals` | List savings goals |
| `get_goal_detail` | Get one goals-v2 goal |
| `get_savings_goal` | Get one savings goal |
| `get_goal_options` | Get built-in goal creation options |
| `create_savings_goals` | Create savings goals |
| `update_goal` | Update a goal |
| `delete_goal` | Delete a goals-v2 goal |
| `delete_savings_goal` | Delete a savings goal |
| `archive_savings_goal` | Archive a savings goal |
| `unarchive_savings_goal` | Unarchive a savings goal |
| `mark_goal_complete` | Mark a goal complete |
| `mark_goal_incomplete` | Mark a goal incomplete |
| `link_transaction_to_goal` | Link or unlink a transaction to a goal |
| `spend_from_goal` | Spend from a goal |
| `contribute_to_savings_goal` | Add a savings-goal contribution |
| `withdraw_from_savings_goal` | Add a savings-goal withdrawal |
| `update_savings_goal_event` | Update a savings-goal event |
| `delete_savings_goal_event` | Delete a savings-goal event |
| `update_goal_priorities` | Reorder/prioritize goals |
| `set_goal_planned_contribution` | Set planned monthly goal contribution |
| `set_savings_goal_budget_amount` | Set savings-goal budget amount |
| `get_recurring` | Bills and recurring charges |
| `get_recurring_streams` | List recurring streams |
| `create_recurring_stream` | Create a recurring stream |
| `delete_recurring_stream` | Delete a recurring stream |
| `mark_stream_not_recurring` | Mark a stream as not recurring |
| `trigger_recurring_merchant_search` | Trigger Monarch's recurring merchant scan |
| `get_net_worth_snapshots` | Historical net worth data |
| `get_investments` | Portfolio holdings and performance |
| `get_account_history` | Balance history for one account |
| `login` | Authenticate and save credentials |

## Code Layout

`server.py` only configures the FastMCP server. Tools are loaded from `tools/`
with FastMCP's filesystem provider:

- `tools/accounts.py`: account and balance tools
- `tools/transactions.py`: transaction read, create, update, tag, bulk update, and delete tools
- `tools/attachments.py`: transaction attachment upload/read/delete tools
- `tools/categories.py`: category and category-group create, update, delete, reorder, and delete-preview tools
- `tools/merchants.py`: merchant search, edit, and merge/delete tools
- `tools/recurring.py`: recurring stream list/create/delete/scan tools
- `tools/rules.py`: transaction rule list, preview, create, update, and delete tools
- `tools/tags.py`: transaction tag list, search, create, update, delete, and order tools
- `tools/goals.py`: goal/savings-goal read/write/event tools
- `tools/planning.py`: cash flow, budget, recurring, net worth, and investment tools
- `tools/auth.py`: login tool
- `tools/client.py`: shared Monarch GraphQL/auth helpers

## Auto-Authentication

If your token expires, the server automatically re-authenticates using `MONARCH_EMAIL` and `MONARCH_PASSWORD` from your `.env`. For accounts with MFA, set `MONARCH_TOTP_SECRET` to your TOTP seed.
