"""Simple test script for Monday.com API connection."""
import logging
from monday_client import _call_monday

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Very simple query: get your Monday account name
query = """
{
  me {
    name
    id
    email
  }
}
"""

if __name__ == "__main__":
    try:
        logger.info("Testing Monday.com API connection...")
        data = _call_monday(query)
        
        if data and "me" in data:
            me = data["me"]
            logger.info("✅ SUCCESS! Connected to Monday as: %s (ID: %s)", 
                       me.get("name"), me.get("id"))
            if me.get("email"):
                logger.info("   Email: %s", me.get("email"))
        else:
            logger.error("❌ FAILED: No user data returned")
    except Exception as e:
        logger.error("❌ FAILED: %s", e)
