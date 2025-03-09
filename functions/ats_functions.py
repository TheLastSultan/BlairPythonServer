import json
import openai
import os
import requests
from typing import Dict, List, Any, Optional, Union
import uuid
from datetime import datetime
import logging
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# Function definitions as a list of dictionaries to be passed to OpenAI API
ats_function_schema = [
    {
  "function": {
    "name": "getRecentPipeline",
    "description": "Get a list of pipelines sorted by their recently used. Typically this will be used as a precursor function.",
  },
  "graphQL": "query GetPipelines{ Pipeline(order_by: {updated_at: desc}, limit: 10) { id name updated_at } }"
},
{
  "function": {
    "name": "getRecentlyFinishedCandidates",
    "description": "Get the most recently finished candidates in a specified pipeline.",
    "parameters": {
      "type": "object",
      "properties": {
        "pipeline_id": {
          "type": "string",
          "description": "The ID of the pipeline to query for finished candidates."
        }
      },
      "required": ["pipeline_id"]
    }
  },
  "graphQL": "query GetRecentlyFinishedCandidates($pipeline_id: uuid!, $limit: Int, $offset: Int) { Pipeline_by_pk(id: $pipeline_id) { Candidates(order_by: {created_at: desc}, limit:$limit, offset:$offset){ id name email created_at status resume_url total_score } } }"
},
{
  "function": {
    "name": "getTopCandidates",
    "description": "Get the top candidates in a specified pipeline, ordered by total score.",
    "parameters": {
      "type": "object",
      "properties": {
        "pipeline_id": {
          "type": "string",
          "description": "The ID of the pipeline to query for top candidates."
        },
        "limit": {
          "type": "integer",
          "description": "The maximum number of candidates to retrieve.",
          "default": 10
        },
        "offset": {
          "type": "integer",
          "description": "The number of candidates to skip before starting to collect the results.",
          "default": 0
        }
      },
      "required": ["pipeline_id"]
    }
  },
  "graphQL": "query GetTopCandidates($pipeline_id: uuid!, $limit: Int = 10, $offset: Int = 0) { Pipeline_by_pk(id: $pipeline_id) { Candidates(order_by: {total_score: desc}, limit:$limit, offset:$offset){ id name email created_at status resume_url total_score } } }"
},
{
  "function": {
    "name": "getCandidateByEmail",
    "description": "Retrieve candidate details using their email address.",
    "parameters": {
      "type": "object",
      "properties": {
        "email": {
          "type": "string",
          "description": "Email of the candidate to retrieve details for."
        }
      },
      "required": ["email"]
    }
  },
  "graphQL": "query GetCandidateByEmail($email: String!) { Candidate(where: {email: {_eq: $email}}) { id name email pipeline_id total_score status resume_url} }"
  
},
{
  "function": {
    "name": "getCandidateByName",
    "description": "Retrieve candidate details using a case-insensitive includes, such as matching a first name.",
    "parameters": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "Match the candidate's name, case-insensitive."
        }
      },
      "required": ["name"]
    }
  },
  "graphQL": "query GetCandidateByName($name: String!) { Candidate(where: {name: {_iregex: $name}}) { id name email pipeline_id total_score status resume_url } }"
},
{
  "function": {
    "name": "getCandidateScoresDetail",
    "description": "Retrieve detailed score information for a candidate using their email address.",
    "parameters": {
      "type": "object",
      "properties": {
        "email": {
          "type": "string",
          "description": "Email of the candidate to retrieve score details for."
        }
      },
      "required": ["email"]
    }
  },
  "graphQL": "query GetCandidateScoresDetail($email: String!) { Candidate(where: {email: {_eq: $email}}) { id name email application_metadata total_score NodeResponses { score result } } }"
}
]


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
            result_text = result_text.split("```json")[1].split("```")[0].strip()
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


# Function to query Hasura GraphQL API
def get_graphql_response(function_name: str, params: Dict[str, Any], use_mock: bool = False) -> Dict[str, Any]:
    """
    Query the Hasura GraphQL API with the GraphQL query associated with the function.
    Falls back to mock data if the API call fails or use_mock is True.
    
    Args:
        function_name: Name of the function/operation to execute
        params: Parameters for the GraphQL operation
        use_mock: If True, skips the real API call and uses mock data
        
    Returns:
        Dict containing the GraphQL API response
    """
    # Create a unique request ID for tracking
    request_id = str(uuid.uuid4())
    logger = logging.getLogger('graphql')
    
    # Find the function definition in schema
    function_def = next((item for item in ats_function_schema if 
                         "function" in item and 
                         item["function"]["name"] == function_name), None)
    
    if function_def is None or "graphQL" not in function_def:
        logger.error(f"Function {function_name} not found in schema or missing GraphQL query")
        return {
            "error": f"Function {function_name} not found in schema or missing GraphQL query",
            "request_id": request_id
        }
        
    if func_def == "create_pipeline_from_scratch":
        create_pipeline_from_scratch()
        
    
    # If using mock data, skip the API call
    if use_mock:
        logger.info(f"Using mock data for {function_name} (Request ID: {request_id})")
        return mock_graphql_response(function_name, params)
    
    # Get the GraphQL query from the function definition
    graphql_query = function_def["graphQL"]
    
    # Prepare the request
    hasura_endpoint = "https://talent1.app/hasura/v1/graphql"
    admin_secret = os.environ.get("ADMIN_SECRET")
    
    if not admin_secret:
        logger.error("ADMIN_SECRET environment variable is not set")
        return {
            "error": "ADMIN_SECRET environment variable is not set",
            "request_id": request_id
        }
    
    headers = {
        "Content-Type": "application/json",
        "x-hasura-admin-secret": admin_secret
    }
    
    # Prepare request payload
    # Note: This is a simple implementation and may need to be extended to handle variables properly
    payload = {
        "query": graphql_query,
        "variables": params
    }
    
    # Log the request
    logger.info(f"GraphQL request for {function_name} (Request ID: {request_id})")
    logger.debug(f"Query: {graphql_query}")
    logger.debug(f"Variables: {json.dumps(params, indent=2)}")
    
    try:
        # Make the request to Hasura GraphQL API
        response = requests.post(
            hasura_endpoint,
            headers=headers,
            json=payload,
            timeout=10  # 10 seconds timeout
        )
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        # Log the result
        logger.info(f"GraphQL response received for {function_name} (Request ID: {request_id})")
        logger.debug(f"Result: {json.dumps(result, indent=2)}")
        
        return result
    
    except requests.exceptions.RequestException as e:
        logger.error(f"GraphQL request failed: {str(e)}")
        return {"error": {str(e)}}

# Function implementation that will be used by the agent
def execute_function(function_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
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
    
    # Call the GraphQL API or mock backend
    result = get_graphql_response(function_name, params, use_mock)

    # Log the result
    print(f"[{datetime.now().isoformat()}] Response for request ID: {request_id}")
    print(f"Result: {json.dumps(result, indent=2)}")

    return result

def create_pipeline_from_scratch():
    pass
    

# Get the list of available functions for the agent
def get_available_functions():
    return [item["function"] for item in ats_function_schema if "function" in item]