"""
Tools for the Alex Researcher agent
"""
import os
from typing import Dict, Any, Optional
from datetime import datetime, UTC
import boto3
import httpx
from agents import function_tool
from tenacity import retry, stop_after_attempt, wait_exponential

HTTP_API_URL_PARAM = os.getenv("HTTP_API_URL_PARAM", "/alex/http_api_url")
ALEX_API_KEY = os.getenv("ALEX_API_KEY")


def alex_ingest_endpoint() -> Optional[str]:
    """Ingest URL from env (local) or SSM /alex/http_api_url (deploy). Avoids a CFN cycle."""
    endpoint = os.getenv("ALEX_API_ENDPOINT")
    if endpoint:
        return endpoint
    try:
        base = (
            boto3.client("ssm")
            .get_parameter(Name=HTTP_API_URL_PARAM)["Parameter"]["Value"]
            .rstrip("/")
        )
        return f"{base}/ingest"
    except Exception:
        return None


def _ingest(document: Dict[str, Any]) -> Dict[str, Any]:
    """Internal function to make the actual API call."""
    endpoint = alex_ingest_endpoint()
    if not endpoint:
        raise RuntimeError("Alex ingest endpoint is not configured")
    with httpx.Client() as client:
        response = client.post(
            endpoint,
            json=document,
            headers={"x-api-key": ALEX_API_KEY},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def ingest_with_retries(document: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest with retry logic for SageMaker cold starts."""
    return _ingest(document)


@function_tool
def ingest_financial_document(topic: str, analysis: str) -> Dict[str, Any]:
    """
    Ingest a financial document into the Alex knowledge base.
    
    Args:
        topic: The topic or subject of the analysis (e.g., "AAPL Stock Analysis", "Retirement Planning Guide")
        analysis: Detailed analysis or advice with specific data and insights
    
    Returns:
        Dictionary with success status and document ID
    """
    if not alex_ingest_endpoint() or not ALEX_API_KEY:
        return {
            "success": False,
            "error": "Alex API not configured. Running in local mode."
        }
    
    document = {
        "text": analysis,
        "metadata": {
            "topic": topic,
            "timestamp": datetime.now(UTC).isoformat()
        }
    }
    
    try:
        result = ingest_with_retries(document)
        return {
            "success": True,
            "document_id": result.get("document_id"),  # Changed from documentId
            "message": f"Successfully ingested analysis for {topic}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
