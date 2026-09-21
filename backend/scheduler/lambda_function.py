"""
Lambda function to trigger the researcher HttpApi /research endpoint.
Called by EventBridge on a schedule.
"""
import os
import urllib.request
import json

import boto3


def _research_base_url() -> str:
    base_url = os.environ.get("RESEARCH_URL") or os.environ.get("APP_RUNNER_URL")
    if base_url:
        return base_url
    param = os.environ.get("HTTP_API_URL_PARAM", "/alex/http_api_url")
    return boto3.client("ssm").get_parameter(Name=param)["Parameter"]["Value"]


def handler(event, context):
    """Trigger the researcher HttpApi /research endpoint."""

    base_url = _research_base_url()
    if not base_url:
        raise ValueError("RESEARCH_URL / SSM /alex/http_api_url not set")

    if base_url.startswith("https://"):
        host = base_url.replace("https://", "").rstrip("/")
    elif base_url.startswith("http://"):
        host = base_url.replace("http://", "").rstrip("/")
    else:
        host = base_url.rstrip("/")

    url = f"https://{host}/research"
    api_key = os.environ.get("ALEX_API_KEY", "")

    try:
        data = json.dumps({}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["x-api-key"] = api_key
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers=headers,
        )
        
        with urllib.request.urlopen(req, timeout=180) as response:
            result = response.read().decode('utf-8')
            print(f"Research triggered successfully: {result}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Research triggered successfully',
                    'result': result
                })
            }
    except Exception as e:
        print(f"Error triggering research: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
