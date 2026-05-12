# Monarch Money MCP Server

An MCP (Model Context Protocol) server that connects AI assistants to [Monarch Money](https://www.monarchmoney.com/) for personal finance tracking.

## Features

- **Accounts**: View all financial accounts, balances, and connection status
- **Transactions**: Search and filter transactions by date, category, account, or keyword
- **Transaction CRUD**: View, create, update, bulk-update, mark reviewed, and delete transactions
- **Cash Flow**: Monthly income/expense breakdown with savings rate
- **Budgets**: Budget tracking with actual vs planned spending
- **Recurring**: Track bills and recurring transactions
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
| `update_transaction` | Update category, merchant, notes, date, amount, review status, tags, etc. |
| `mark_transaction_reviewed` | Mark a transaction reviewed or needs-review |
| `create_transaction` | Create a manual transaction |
| `set_transaction_tags` | Replace tags on one transaction |
| `delete_transaction` | Delete one transaction |
| `bulk_update_transactions` | Update a set of transactions |
| `get_cash_flow` | Monthly income/expense breakdown |
| `get_budgets` | Budget vs actual spending |
| `get_recurring` | Bills and recurring charges |
| `get_net_worth_snapshots` | Historical net worth data |
| `get_investments` | Portfolio holdings and performance |
| `get_account_history` | Balance history for one account |
| `login` | Authenticate and save credentials |

## Code Layout

`server.py` only configures the FastMCP server. Tools are loaded from `tools/`
with FastMCP's filesystem provider:

- `tools/accounts.py`: account and balance tools
- `tools/transactions.py`: transaction read, create, update, tag, bulk update, and delete tools
- `tools/planning.py`: cash flow, budget, recurring, net worth, and investment tools
- `tools/auth.py`: login tool
- `tools/client.py`: shared Monarch GraphQL/auth helpers

## Auto-Authentication

If your token expires, the server automatically re-authenticates using `MONARCH_EMAIL` and `MONARCH_PASSWORD` from your `.env`. For accounts with MFA, set `MONARCH_TOTP_SECRET` to your TOTP seed.
