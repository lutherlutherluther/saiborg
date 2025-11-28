import os
import logging
from typing import Optional, Dict, Any, List
import requests
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load .env so we can read MONDAY_API_KEY
load_dotenv()

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = os.getenv("MONDAY_API_URL", "https://api.monday.com/v2")
TIMEOUT = int(os.getenv("MONDAY_API_TIMEOUT", "30"))


def _call_monday(query: str, variables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Low-level helper: call Monday GraphQL API and return data['data'].
    
    Args:
        query: GraphQL query string
        variables: Optional variables dictionary for the query
        
    Returns:
        The 'data' field from the API response, or None on error
        
    Raises:
        RuntimeError: If API key is missing or API returns errors
        requests.RequestException: If the HTTP request fails
    """
    if not MONDAY_API_KEY:
        raise RuntimeError("MONDAY_API_KEY is missing in .env")

    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "variables": variables or {},
    }

    try:
        resp = requests.post(MONDAY_API_URL, json=payload, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            error_msg = f"Monday API error: {data['errors']}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return data.get("data")
    except requests.RequestException as e:
        logger.error("Request to Monday API failed: %s", e)
        raise


def get_all_items(board_id: int, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Fetch items from a given board.
    
    Args:
        board_id: The Monday.com board ID
        limit: Maximum number of items to fetch (default: 500)
        
    Returns:
        List of item dictionaries, each containing id, name, and column_values
        
    Raises:
        RuntimeError: If API call fails
    """
    query = """
    query($board_id: [ID!]!, $limit: Int!) {
      boards(ids: $board_id) {
        items_page(limit: $limit) {
          items {
            id
            name
            column_values {
              id
              text
            }
          }
        }
      }
    }
    """
    try:
        data = _call_monday(query, variables={"board_id": [board_id], "limit": limit})
        boards = (data or {}).get("boards") or []
        if not boards:
            logger.warning("No boards found for board_id: %d", board_id)
            return []

        items_page = boards[0].get("items_page") or {}
        items = items_page.get("items") or []
        logger.info("Fetched %d items from board %d", len(items), board_id)
        return items
    except Exception as e:
        logger.error("Failed to get items from board %d: %s", board_id, e)
        raise


def search_items_by_text(board_id: int, text: str) -> List[Dict[str, Any]]:
    """
    Search items by text: load items from the board and filter in Python
    by name or any column text containing the search string.
    
    Args:
        board_id: The Monday.com board ID
        text: Search term to match against item names and column values
        
    Returns:
        List of matching item dictionaries
        
    Note:
        This is a simple client-side search. For better performance with large
        datasets, consider using Monday.com's native search API.
    """
    term = (text or "").strip().lower()
    if not term:
        logger.warning("Empty search term provided")
        return []

    try:
        items = get_all_items(board_id)
        results = []

        for item in items:
            name = (item.get("name") or "").lower()
            cols = item.get("column_values") or []

            # Match on item name
            if term in name:
                results.append(item)
                continue

            # Or match on any column text
            for cv in cols:
                cv_text = (cv.get("text") or "").lower()
                if term in cv_text:
                    results.append(item)
                    break

        logger.info("Found %d matching items for search term '%s'", len(results), term)
        return results
    except Exception as e:
        logger.error("Failed to search items: %s", e)
        return []


# Optional: quick CLI test if you run `python3 monday_client.py`
if __name__ == "__main__":
    try:
        logger.info("Testing Monday connection...")
        me_query = "query { me { name email } }"
        data = _call_monday(me_query)
        me = (data or {}).get("me")
        if me:
            logger.info("✅ OK! Logged in as: %s (%s)", me.get("name"), me.get("email"))
        else:
            logger.error("❌ Failed to get user info")
    except Exception as e:
        logger.error("❌ Error testing Monday: %s", e)
