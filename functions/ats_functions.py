import json
import openai
import os
import httpx
import uuid
from datetime import datetime
import logging
import dotenv
from typing import Dict, List, Any, Optional, Union
from functions.custom_pipeline import custom_pipeline
from functions.ats_schema import ats_function_schema, insert_node_query, get_company_id

# Load environment variables from .env file
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load OpenAI API key from environment variable
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    logger.warning("OPENAI_API_KEY environment variable is not set or empty")

# Initialize OpenAI client
try:
    client = openai.Client(api_key=api_key)
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    client = None

graphql_functions = ["getCandidateByName", "getCandidateByEmail", "getPipelineById",
                     "getRecentPipeline", "getTopCandidates", "getRecentlyFinishedCandidates"]

# Mock backend implementation - this simulates the GraphQL backend
def mock_graphql_response(function_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a mock response for a function call using ChatGPT"""
    # Prepare a prompt for ChatGPT to generate mock data
    prompt = f"""Generate a realistic mock JSON response for an ATS (Applicant Tracking System) GraphQL query.
    Function: {function_name}
    Parameters: {json.dumps(params, indent=2)}
    
    The response should be valid JSON and should represent what an actual ATS system would return.
    Include realistic data for all relevant fields.
    
    Response:"""

    # Call ChatGPT to generate mock data
    response = client.chat.completions.create(
        model="gpt-4-turbo",  # or whatever model is available to you
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that generates mock JSON responses for an ATS GraphQL API.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    # Extract the generated JSON from the response
    try:
        result_text = response.choices[0].message.content
        # Clean up the response to extract only the JSON part
        if "```json" in result_text:
            result_text = result_text.split(
                "```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)
        return result
    except Exception as e:
        return {
            "error": f"Failed to generate mock response: {str(e)}",
            "function": function_name,
            "params": params,
        }


def generate_job_description(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate job description for pipeline creation using ChatGPT"""
    # Prepare a prompt for ChatGPT to generate mock data
    prompt = f"""
        Generate a detailed job description based on the user's preferences (see 'Parameters' below). 
        - Integrate all necessary skills and requirements directly into the description.
        - Emphasize how this role will evaluate a candidate's qualifications (e.g., matching against their resume).
        - Omit any instructions about applying or references to the company.
        - The output must be valid JSON, containing only one field: "job_description".

        Parameters:
        {json.dumps(params, indent=2)}

        Example of valid response:
        {{
        "job_description": "AI-generated descriptive text goes here."
        }}
        """

    # Call ChatGPT to generate mock data
    response = client.chat.completions.create(
        model="gpt-4-turbo",  # or whatever model is available to you
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that generates job descriptions based on user parameters",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    # Extract the generated JSON from the response
    try:
        result_text = response.choices[0].message.content
        # Clean up the response to extract only the JSON part
        if "```json" in result_text:
            result_text = result_text.split(
                "```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)
        return result
    except Exception as e:
        return {
            "error": f"Failed to generate description: {str(e)}",
            "params": params,
        }


async def make_hasura_request(token: str, graphql_query: str, params: Dict[str, any], request_id: str):
    """
    Makes a request to the Hasura GraphQL API.

    Args:
        session_id (str): The session ID for the current user request.
        graphql_query (str): The GraphQL query to execute.
        params (Dict[str, Any]): The parameters for the GraphQL query.
        request_id (str): The unique request ID.

    Returns:
        Dict[str, Any]: The response from Hasura or error details.
    """
    logger = logging.getLogger('make_hasura_request')
    hasura_endpoint = os.environ.get("HASURA_ENDPOINT")
    admin_secret = os.environ.get("ADMIN_SECRET")
    mode = os.environ.get("MODE")

    # Determine headers based on mode of interaction
    if mode == "web":
      if not token:
            return {"error": "Token not found", "request_id": request_id}
      headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "x-hasura-role": "user"
        }
    else:
        if not admin_secret:
            logger.error("ADMIN_SECRET environment variable is not set")
            return {"error": "ADMIN_SECRET environment variable is not set", "request_id": request_id}
        headers = {
            "Content-Type": "application/json",
            "x-hasura-admin-secret": admin_secret
        }

    payload = {
        "query": graphql_query,
        "variables": params
    }

    # Log the request
    logger.debug(f"Query: {graphql_query}")
    logger.debug(f"Variables: {json.dumps(params, indent=2)}")

    try:
        async with httpx.AsyncClient(timeout=10) as request_client:
            response = await request_client.post(hasura_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Result: {json.dumps(result, indent=2)}")
            return result
    except httpx.RequestError as e:
        logger.error(f"GraphQL request failed: {str(e)}")
        return {"error": str(e), "request_id": request_id}

async def get_graphql_response(token: str, function_name: str, params: Dict[str, Any], use_mock: bool = False) -> Dict[str, Any]:
    """
    Executes a GraphQL query for a given function and parameters.

    Args:
        function_name (str): The name of the GraphQL function to execute.
        params (Dict[str, Any]): The parameters for the GraphQL query.
        use_mock (bool): Whether to use mock data instead of making a real API call (default is False).

    Returns:
        Dict[str, Any]: The GraphQL response or mock data.
    """
    request_id = str(uuid.uuid4())
    # Find the function definition in schema
    function_def = next((item for item in ats_function_schema if
                         "function" in item and
                         item["function"]["name"] == function_name), None)

    if function_def is None or "graphQL" not in function_def:
        logger.error(
            f"Function {function_name} not found in schema or missing GraphQL query")
        return {
            "error": f"Function {function_name} not found in schema or missing GraphQL query",
            "request_id": request_id
        }
    logger.info(
        f"GraphQL request for {function_name} (Request ID: {request_id})")

    # If using mock data, skip the API call
    if use_mock:
        logger.info(
            f"Using mock data for {function_name} (Request ID: {request_id})")
        return mock_graphql_response(function_name, params)

    # Get the GraphQL query from the function definition
    graphql_query = function_def["graphQL"]
    result = await make_hasura_request(token, graphql_query, params, request_id)

    logger.info(
        f"GraphQL response received for {function_name} (Request ID: {request_id})")

    return result

async def execute_function(token: str, function_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a function call to the GraphQL backend or fallback to mock"""
    # Create a unique request ID for tracking
    request_id = str(uuid.uuid4())

    # Log the function call
    print(
        f"[{datetime.now().isoformat()}] Function call: {function_name}, Request ID: {request_id}"
    )
    print(f"Parameters: {json.dumps(params, indent=2)}")

    # Use environment variable to determine if we should use mock data
    use_mock = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"

    if function_name in graphql_functions:
        # Call the GraphQL API or mock backend
        result = await get_graphql_response(token, function_name, params, use_mock)
    else:
        result = await run_functions(token, function_name, params)
    # Log the result
    print(f"[{datetime.now().isoformat()}] Response for request ID: {request_id}")
    print(f"Result: {json.dumps(result, indent=2)}")

    return result


async def create_pipeline(token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a pipeline and inserts the nodes into the database.

    Args:
        params (Dict[str, Any]): A dictionary containing parameters for pipeline creation.

    Returns:
        Dict[str, Any]: A dictionary indicating whether the operation was successful.
    """
    request_id = str(uuid.uuid4())  # Generate unique request ID for tracking
    # Generate the job description based on the params
    description = generate_job_description(params)
    logging.info(f"Generated job description: {description}")

    mode = os.environ.get("MODE")
    if mode != "web":
        company_id = "c207a04f-dd58-44bb-a8bb-f4e7bf4dbb18"
    else:
        #get company_id from user_id
        company = await make_hasura_request(token, get_company_id, {}, request_id)
        company_id = company['data']['User'][0]['company_id']
        
    # Build the pipeline object with the provided parameters
    pipeline = custom_pipeline(
        pipeline_name=params['pipeline_name'],
        job_title=params['job_title'],
        job_description=description['job_description'],
        job_type=params['job_type'],
        workplace_type=params['workplace_type'],
        location=params['location'],
        company_id=company_id,
    )

    # Iterate over the nodes in the pipeline and modify them based on their type
    for node in pipeline.get("node_flow", {}).get("nodes", []):
        # If it's a "resumatic" node with .configs.fields
        if node.get("type") == "resumatic":
            fields = node["data"].get("configs", {}).get("fields", [])
            for field in fields:
                if field.get("name") == "Job Description":
                    field["value"] = pipeline["job_description"]

        # If it's an "assessment" node with .configs generate and assign assessment
        # if node.get("type") == "assessment":
        #     node["data"]["configs"]["assessment_id"] = "assessment_id"

    data = await get_graphql_response(token, "createPipeline", {"object": pipeline})
    pipeline_id = data.get('data', {}).get('insert_Pipeline_one', {}).get('id')

    # Prepare and insert nodes associated with the pipeline
    if pipeline_id:
        pipeline_nodes = [
            {
                "type": node.get('type'),
                "node_flow_id": int(node.get('id')),
                "metadata": node.get('data'),
                "pipeline_id": pipeline_id,
            }
            for node in pipeline["node_flow"]["nodes"]
        ]
        await make_hasura_request(token, insert_node_query, {"objects": pipeline_nodes}, request_id)

        return {"success": True, pipeline_id: pipeline_id}
    else:
        logging.error("Pipeline ID not found in the response")
        return {"error": "Unable to create pipeline at this time"}


def get_available_functions():
    return [item["function"] for item in ats_function_schema if "function" in item]

async def run_functions(token: str, function_name, params):
    if function_name == "createPipeline":
        return await create_pipeline(token, params)
