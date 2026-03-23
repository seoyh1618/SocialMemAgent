import logging
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _make_request(url: str, headers: dict, params: dict) -> dict:
    """Make an HTTP GET request and return parsed JSON response.

    Returns a dict with 'status' key set to 'Error' on failure.
    """
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error from Twitter API: status=%s url=%s", e.response.status_code, url)
        return {"status": "Error", "message": f"HTTP {e.response.status_code} from Twitter API"}
    except requests.exceptions.RequestException as e:
        logger.error("Network error calling Twitter API: %s", type(e).__name__)
        return {"status": "Error", "message": "Network error calling Twitter API"}

    try:
        return response.json()
    except json.JSONDecodeError:
        logger.error("Invalid JSON response from Twitter API url=%s", url)
        return {"status": "Error", "message": "Invalid JSON response from Twitter API"}


def advanced_search(query: str, queryType: str, cursor: str) -> dict:
    """Search for related tweets.

    Args:
        query (str): The query to search for example, "AI" OR "Twitter".
        queryType (enum<str>): The query type to search for. "Latest" OR "Top"
        cursor (str): The cursor to paginate through the results. First page is "".

    Returns:
        tweets object[]: The content of the tweet.
        has_next_page boolean: Whether there is a next page. (Every page has 20 tweets)
        cursor str: Cursor for fetching the next page of results.
    """
    logger.info("Tool: advanced_search | query=%s", query)

    x_api_key = os.getenv("X_API_KEY")
    if not x_api_key:
        return {"status": "skipped", "message": "X API key not configured. Skipping Twitter search.", "tweets": []}

    try:
        url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
        headers = {"X-API-Key": x_api_key}
        querystring = {"query": query, "queryType": queryType, "cursor": cursor}
        result = _make_request(url, headers, querystring)
        if result.get("status") == "Error":
            logger.warning("Twitter advanced_search failed: %s", result.get("message"))
            return {"status": "skipped", "message": f"Twitter API unavailable: {result.get('message', 'unknown error')}. Skipping.", "tweets": []}
        return result
    except Exception as e:
        logger.warning("Twitter advanced_search exception: %s", e)
        return {"status": "skipped", "message": f"Twitter API error: {e}. Skipping.", "tweets": []}


def get_trends():
    """
    Retrieve the current hot topics/trends on X (Twitter).

    Args:
        None.

    Returns:
        The list of trends (sorted from most popular to less popular).
    """
    logger.info("Tool: get_trends")

    x_api_key = os.getenv("X_API_KEY")
    if not x_api_key:
        return {"status": "skipped", "message": "X API key not configured. Skipping trends.", "trends": []}

    try:
        url = "https://api.twitterapi.io/twitter/trends"
        querystring = {"woeid": "23424977"}
        headers = {"X-API-Key": x_api_key}

        data = _make_request(url, headers, querystring)
        if data.get("status") == "Error":
            logger.warning("Twitter get_trends failed: %s", data.get("message"))
            return {"status": "skipped", "message": f"Twitter API unavailable: {data.get('message', 'unknown error')}. Skipping.", "trends": []}

        trends = data.get("trends", [])[:20]
        trend_names = []
        for item in trends:
            trend = item.get("trend", {})
            name = trend.get("name")
            if name is not None:
                trend_names.append(name)

        logger.debug("get_trends result: %s", trend_names)
        return trend_names
    except Exception as e:
        logger.warning("Twitter get_trends exception: %s", e)
        return {"status": "skipped", "message": f"Twitter API error: {e}. Skipping.", "trends": []}


def get_user_posts(userId: str, cursor: str):
    """
    Given a userId of a X (Twitter), retrieve their historical posts.

    Args:
        userId (str): The user id that we want to retrieve the posts from.
        cursor (str): The cursor to paginate through the results. Default is "".

    Returns:
        tweets object[]: The content of the tweet.
        has_next_page boolean: Whether there is a next page. (Every page has 20 tweets)
        cursor str: Cursor for fetching the next page of results.
    """
    logger.info("Tool: get_user_posts | userId=%s", userId)
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"

    x_api_key = os.getenv("X_API_KEY")
    if not x_api_key:
        return {"status": "Error", "message": "X_API_KEY not specified"}
    headers = {"X-API-Key": x_api_key}

    querystring = {
        "query": f"from:{userId}",
        "queryType": "Latest",
        "cursor": cursor
    }

    return _make_request(url, headers, querystring)