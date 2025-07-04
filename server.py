#!/usr/bin/env python3
"""MonarchMoney MCP Server - Provides access to Monarch Money financial data via MCP protocol."""

import os
import asyncio
import json
from typing import Any, Dict, Optional, List
from datetime import datetime, date
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities
from mcp.types import Tool, TextContent
from monarchmoney import MonarchMoney


def convert_dates_to_strings(obj: Any) -> Any:
    """
    Recursively convert all date/datetime objects to ISO format strings.
    
    This ensures that the data can be serialized by any JSON encoder,
    not just our custom one. This is necessary because the MCP framework
    may attempt to serialize the response before we can use our custom encoder.
    """
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_dates_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates_to_strings(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_dates_to_strings(item) for item in obj)
    else:
        return obj

# Initialize the MCP server
server = Server("monarch-money")

# Global variable to store the MonarchMoney client
mm_client: Optional[MonarchMoney] = None
session_file = Path.home() / ".monarchmoney_session"


async def initialize_client():
    """Initialize the MonarchMoney client with authentication."""
    global mm_client
    
    email = os.getenv("MONARCH_EMAIL")
    password = os.getenv("MONARCH_PASSWORD")
    mfa_secret = os.getenv("MONARCH_MFA_SECRET")
    
    if not email or not password:
        raise ValueError("MONARCH_EMAIL and MONARCH_PASSWORD environment variables are required")
    
    mm_client = MonarchMoney()
    
    # Try to load existing session first
    if session_file.exists() and not os.getenv("MONARCH_FORCE_LOGIN"):
        try:
            mm_client.load_session(str(session_file))
            # Test if session is still valid
            await mm_client.get_accounts()
            print("Loaded existing session successfully")
            return
        except Exception:
            print("Existing session invalid, logging in fresh")
    
    # Login with credentials
    if mfa_secret:
        await mm_client.login(email, password, mfa_secret_key=mfa_secret)
    else:
        await mm_client.login(email, password)
    
    # Save session for future use
    mm_client.save_session(str(session_file))
    print("Logged in and saved session")


# Tool definitions
@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="get_accounts",
            description="Retrieve all linked financial accounts",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_transactions",
            description="Fetch transactions with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of transactions to return",
                        "default": 100
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of transactions to skip",
                        "default": 0
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Filter by specific account ID"
                    },
                    "category_id": {
                        "type": "string",
                        "description": "Filter by specific category ID"
                    }
                },
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_budgets",
            description="Retrieve budget information",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_cashflow",
            description="Analyze cashflow data",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_transaction_categories",
            description="List all transaction categories",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        Tool(
            name="create_transaction",
            description="Create a new transaction",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Transaction amount (negative for expenses)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Transaction description"
                    },
                    "category_id": {
                        "type": "string",
                        "description": "Category ID for the transaction"
                    },
                    "account_id": {
                        "type": "string",
                        "description": "Account ID for the transaction"
                    },
                    "date": {
                        "type": "string",
                        "description": "Transaction date in YYYY-MM-DD format"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes for the transaction"
                    }
                },
                "required": ["amount", "description", "account_id", "date"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="update_transaction",
            description="Update an existing transaction",
            inputSchema={
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "ID of the transaction to update"
                    },
                    "amount": {
                        "type": "number",
                        "description": "New transaction amount"
                    },
                    "description": {
                        "type": "string",
                        "description": "New transaction description"
                    },
                    "category_id": {
                        "type": "string",
                        "description": "New category ID"
                    },
                    "date": {
                        "type": "string",
                        "description": "New transaction date in YYYY-MM-DD format"
                    },
                    "notes": {
                        "type": "string",
                        "description": "New notes for the transaction"
                    }
                },
                "required": ["transaction_id"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="refresh_accounts",
            description="Request a refresh of all account data from financial institutions",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute a tool and return the results."""
    if not mm_client:
        return [TextContent(type="text", text="Error: MonarchMoney client not initialized")]
    
    try:
        if name == "get_accounts":
            accounts = await mm_client.get_accounts()
            # Convert date objects to strings before serialization
            accounts = convert_dates_to_strings(accounts)
            return [TextContent(type="text", text=json.dumps(accounts, indent=2))]
        
        elif name == "get_transactions":
            # Build filter parameters
            filters = {}
            if "start_date" in arguments:
                filters["start_date"] = datetime.strptime(arguments["start_date"], "%Y-%m-%d").date()
            if "end_date" in arguments:
                filters["end_date"] = datetime.strptime(arguments["end_date"], "%Y-%m-%d").date()
            if "account_id" in arguments:
                filters["account_id"] = arguments["account_id"]
            if "category_id" in arguments:
                filters["category_id"] = arguments["category_id"]
            
            transactions = await mm_client.get_transactions(
                limit=arguments.get("limit", 100),
                offset=arguments.get("offset", 0),
                **filters
            )
            # Convert date objects to strings before serialization
            transactions = convert_dates_to_strings(transactions)
            return [TextContent(type="text", text=json.dumps(transactions, indent=2))]
        
        elif name == "get_budgets":
            kwargs = {}
            if "start_date" in arguments:
                kwargs["start_date"] = datetime.strptime(arguments["start_date"], "%Y-%m-%d").date()
            if "end_date" in arguments:
                kwargs["end_date"] = datetime.strptime(arguments["end_date"], "%Y-%m-%d").date()
            
            try:
                budgets = await mm_client.get_budgets(**kwargs)
                # Convert date objects to strings before serialization
                budgets = convert_dates_to_strings(budgets)
                return [TextContent(type="text", text=json.dumps(budgets, indent=2))]
            except Exception as e:
                # Handle the case where no budgets exist
                if "Something went wrong while processing: None" in str(e):
                    return [TextContent(type="text", text=json.dumps({
                        "budgets": [],
                        "message": "No budgets configured in your Monarch Money account"
                    }, indent=2))]
                else:
                    # Re-raise other errors
                    raise
        
        elif name == "get_cashflow":
            kwargs = {}
            if "start_date" in arguments:
                kwargs["start_date"] = datetime.strptime(arguments["start_date"], "%Y-%m-%d").date()
            if "end_date" in arguments:
                kwargs["end_date"] = datetime.strptime(arguments["end_date"], "%Y-%m-%d").date()
            
            cashflow = await mm_client.get_cashflow(**kwargs)
            # Convert date objects to strings before serialization
            cashflow = convert_dates_to_strings(cashflow)
            return [TextContent(type="text", text=json.dumps(cashflow, indent=2))]
        
        elif name == "get_transaction_categories":
            categories = await mm_client.get_transaction_categories()
            # Convert date objects to strings before serialization
            categories = convert_dates_to_strings(categories)
            return [TextContent(type="text", text=json.dumps(categories, indent=2))]
        
        elif name == "create_transaction":
            # Convert date string to date object
            transaction_date = datetime.strptime(arguments["date"], "%Y-%m-%d").date()
            
            result = await mm_client.create_transaction(
                amount=arguments["amount"],
                description=arguments["description"],
                category_id=arguments.get("category_id"),
                account_id=arguments["account_id"],
                date=transaction_date,
                notes=arguments.get("notes")
            )
            # Convert date objects to strings before serialization
            result = convert_dates_to_strings(result)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "update_transaction":
            # Build update parameters
            updates = {"transaction_id": arguments["transaction_id"]}
            if "amount" in arguments:
                updates["amount"] = arguments["amount"]
            if "description" in arguments:
                updates["description"] = arguments["description"]
            if "category_id" in arguments:
                updates["category_id"] = arguments["category_id"]
            if "date" in arguments:
                updates["date"] = datetime.strptime(arguments["date"], "%Y-%m-%d").date()
            if "notes" in arguments:
                updates["notes"] = arguments["notes"]
            
            result = await mm_client.update_transaction(**updates)
            # Convert date objects to strings before serialization
            result = convert_dates_to_strings(result)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "refresh_accounts":
            result = await mm_client.request_accounts_refresh()
            # Convert date objects to strings before serialization
            result = convert_dates_to_strings(result)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def main():
    """Main entry point for the server."""
    # Initialize the MonarchMoney client
    try:
        await initialize_client()
    except Exception as e:
        print(f"Failed to initialize MonarchMoney client: {e}")
        return
    
    # Run the MCP server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, 
            write_stream,
            InitializationOptions(
                server_name="monarch-money",
                server_version="1.0.0",
                capabilities=ServerCapabilities(
                    tools={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())