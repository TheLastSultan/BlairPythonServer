import json
import openai
import os
from typing import Dict, List, Any, Optional, Union
import uuid
from datetime import datetime

# Load OpenAI API key from environment variable
client = openai.Client(api_key=os.environ.get("OPENAI_API_KEY"))

# Set this to True to simulate a delay for more realistic API behavior
SIMULATE_DELAY = True

# Function definitions as a list of dictionaries to be passed to OpenAI API
ats_functions = [
    # User functions
    {
        "name": "getUser",
        "description": "Get user details by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "User ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "getUsers",
        "description": "Get users by role",
        "parameters": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ["ADMIN", "RECRUITER", "HIRING_MANAGER", "INTERVIEWER"], "description": "User role filter"},
            },
        },
    },
    {
        "name": "createUser",
        "description": "Create a new user",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User's full name"},
                "email": {"type": "string", "description": "User's email"},
                "role": {"type": "string", "enum": ["ADMIN", "RECRUITER", "HIRING_MANAGER", "INTERVIEWER"], "description": "User role"},
            },
            "required": ["name", "email", "role"],
        },
    },
    
    # Team functions
    {
        "name": "getTeam",
        "description": "Get team details by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Team ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "getTeams",
        "description": "Get all teams",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "createTeam",
        "description": "Create a new team",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Team name"},
                "description": {"type": "string", "description": "Team description"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "addUserToTeam",
        "description": "Add a user to a team",
        "parameters": {
            "type": "object",
            "properties": {
                "userId": {"type": "string", "description": "User ID"},
                "teamId": {"type": "string", "description": "Team ID"},
            },
            "required": ["userId", "teamId"],
        },
    },
    
    # Job functions
    {
        "name": "getJob",
        "description": "Get job details by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Job ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "getJobs",
        "description": "Get jobs filtered by status",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["DRAFT", "OPEN", "PAUSED", "CLOSED", "FILLED"], "description": "Job status filter"},
            },
        },
    },
    {
        "name": "createJob",
        "description": "Create a new job",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Job title"},
                "description": {"type": "string", "description": "Job description"},
                "hiringManagerId": {"type": "string", "description": "Hiring manager user ID"},
                "location": {"type": "string", "description": "Job location"},
                "salaryMin": {"type": "number", "description": "Minimum salary"},
                "salaryMax": {"type": "number", "description": "Maximum salary"},
                "salaryCurrency": {"type": "string", "description": "Salary currency"},
                "requirements": {"type": "array", "items": {"type": "string"}, "description": "Job requirements"},
            },
            "required": ["title", "description", "hiringManagerId"],
        },
    },
    {
        "name": "assignRecruiterToJob",
        "description": "Assign a recruiter to a job",
        "parameters": {
            "type": "object",
            "properties": {
                "jobId": {"type": "string", "description": "Job ID"},
                "recruiterId": {"type": "string", "description": "Recruiter user ID"},
            },
            "required": ["jobId", "recruiterId"],
        },
    },
    
    # Pipeline and Stage functions
    {
        "name": "getPipeline",
        "description": "Get pipeline details by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Pipeline ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "createPipeline",
        "description": "Create a new pipeline for a job",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Pipeline name"},
                "jobId": {"type": "string", "description": "Job ID"},
            },
            "required": ["name", "jobId"],
        },
    },
    {
        "name": "createStage",
        "description": "Create a new stage in a pipeline",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Stage name"},
                "pipelineId": {"type": "string", "description": "Pipeline ID"},
                "order": {"type": "integer", "description": "Stage order in the pipeline"},
            },
            "required": ["name", "pipelineId", "order"],
        },
    },
    
    # Candidate functions
    {
        "name": "getCandidate",
        "description": "Get candidate details by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Candidate ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "getCandidates",
        "description": "Get candidates filtered by job, stage, or status",
        "parameters": {
            "type": "object",
            "properties": {
                "jobId": {"type": "string", "description": "Job ID filter"},
                "stageId": {"type": "string", "description": "Stage ID filter"},
                "status": {"type": "string", "enum": ["NEW", "IN_PROGRESS", "ON_HOLD", "REJECTED", "OFFERED", "ACCEPTED", "DECLINED", "WITHDRAWN"], "description": "Candidate status filter"},
            },
        },
    },
    {
        "name": "createCandidate",
        "description": "Create a new candidate for a job",
        "parameters": {
            "type": "object",
            "properties": {
                "firstName": {"type": "string", "description": "Candidate's first name"},
                "lastName": {"type": "string", "description": "Candidate's last name"},
                "email": {"type": "string", "description": "Candidate's email"},
                "phone": {"type": "string", "description": "Candidate's phone number"},
                "resume": {"type": "string", "description": "URL to candidate's resume"},
                "source": {"type": "string", "description": "Where the candidate was sourced from"},
                "jobId": {"type": "string", "description": "Job ID"},
            },
            "required": ["firstName", "lastName", "email", "jobId"],
        },
    },
    {
        "name": "moveCandidate",
        "description": "Move a candidate to a different stage in the pipeline",
        "parameters": {
            "type": "object",
            "properties": {
                "candidateId": {"type": "string", "description": "Candidate ID"},
                "stageId": {"type": "string", "description": "Stage ID to move candidate to"},
            },
            "required": ["candidateId", "stageId"],
        },
    },
    {
        "name": "updateCandidateStatus",
        "description": "Update a candidate's status",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Candidate ID"},
                "status": {"type": "string", "enum": ["NEW", "IN_PROGRESS", "ON_HOLD", "REJECTED", "OFFERED", "ACCEPTED", "DECLINED", "WITHDRAWN"], "description": "New candidate status"},
            },
            "required": ["id", "status"],
        },
    },
    {
        "name": "searchCandidates",
        "description": "Search for candidates with structured criteria",
        "parameters": {
            "type": "object",
            "properties": {
                "skills": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "List of skills to search for"
                },
                "experienceYearsMin": {
                    "type": "integer", 
                    "description": "Minimum years of experience"
                },
                "experienceYearsMax": {
                    "type": "integer", 
                    "description": "Maximum years of experience"
                },
                "locations": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "List of locations to search for"
                },
                "education": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "List of education institutions to search for"
                },
                "educationLevel": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "List of education levels to search for (e.g., Bachelor's, Master's, PhD)"
                },
                "availabilityDate": {
                    "type": "string", 
                    "description": "Date when candidate is available to start"
                },
                "salaryMin": {
                    "type": "number", 
                    "description": "Minimum salary expectation"
                },
                "salaryMax": {
                    "type": "number", 
                    "description": "Maximum salary expectation"
                },
                "salaryCurrency": {
                    "type": "string", 
                    "description": "Currency for salary range"
                },
                "jobTitles": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "List of job titles to search for"
                },
                "industries": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "List of industries to search for"
                },
                "keywordSearch": {
                    "type": "string", 
                    "description": "Keyword(s) to search across all text fields"
                },
                "tags": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "List of tags to search for"
                },
                "appliedDateStart": {
                    "type": "string", 
                    "description": "Start date for when candidate applied"
                },
                "appliedDateEnd": {
                    "type": "string", 
                    "description": "End date for when candidate applied"
                },
                "lastContactDateStart": {
                    "type": "string", 
                    "description": "Start date for when candidate was last contacted"
                },
                "lastContactDateEnd": {
                    "type": "string", 
                    "description": "End date for when candidate was last contacted"
                }
            }
        },
    },
    
    # Note functions
    {
        "name": "createNote",
        "description": "Create a note for a candidate",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Note content"},
                "candidateId": {"type": "string", "description": "Candidate ID"},
                "authorId": {"type": "string", "description": "Author user ID"},
            },
            "required": ["content", "candidateId", "authorId"],
        },
    },
    
    # Assessment functions
    {
        "name": "getAssessment",
        "description": "Get assessment details by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Assessment ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "createAssessment",
        "description": "Create a new assessment for a stage",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Assessment name"},
                "description": {"type": "string", "description": "Assessment description"},
                "type": {"type": "string", "enum": ["TECHNICAL", "BEHAVIORAL", "CULTURAL", "CASE_STUDY", "ASSIGNMENT"], "description": "Assessment type"},
                "stageId": {"type": "string", "description": "Stage ID"},
            },
            "required": ["name", "description", "type", "stageId"],
        },
    },
    {
        "name": "getAssessmentGrade",
        "description": "Get assessment grade details by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Assessment grade ID"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "getCandidateAssessments",
        "description": "Get all assessment grades for a candidate",
        "parameters": {
            "type": "object",
            "properties": {
                "candidateId": {"type": "string", "description": "Candidate ID"},
            },
            "required": ["candidateId"],
        },
    },
    {
        "name": "createAssessmentGrade",
        "description": "Create an assessment grade for a candidate",
        "parameters": {
            "type": "object",
            "properties": {
                "assessmentId": {"type": "string", "description": "Assessment ID"},
                "candidateId": {"type": "string", "description": "Candidate ID"},
                "interviewerId": {"type": "string", "description": "Interviewer user ID"},
                "score": {"type": "number", "description": "Assessment score"},
                "feedback": {"type": "string", "description": "Assessment feedback"},
                "strengths": {"type": "array", "items": {"type": "string"}, "description": "Candidate strengths identified"},
                "weaknesses": {"type": "array", "items": {"type": "string"}, "description": "Candidate weaknesses identified"},
                "recommendation": {"type": "string", "enum": ["STRONG_YES", "YES", "NEUTRAL", "NO", "STRONG_NO"], "description": "Overall recommendation"},
            },
            "required": ["assessmentId", "candidateId", "interviewerId", "feedback", "recommendation"],
        },
    },
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
            {"role": "system", "content": "You are a helpful assistant that generates mock JSON responses for an ATS GraphQL API."},
            {"role": "user", "content": prompt}
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
            "params": params
        }

# Function implementation that will be used by the agent
def execute_function(function_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a function call to the mock GraphQL backend"""
    # Create a unique request ID for tracking
    request_id = str(uuid.uuid4())
    
    # Log the function call
    print(f"[{datetime.now().isoformat()}] Function call: {function_name}, Request ID: {request_id}")
    print(f"Parameters: {json.dumps(params, indent=2)}")
    
    # Simulate network delay for more realistic behavior
    if SIMULATE_DELAY:
        import random
        import time
        # Random delay between 0.5 and 2 seconds
        delay = random.uniform(0.5, 2.0)
        time.sleep(delay)
    
    # Call the mock backend
    result = mock_graphql_response(function_name, params)
    
    # Log the result
    print(f"[{datetime.now().isoformat()}] Response for request ID: {request_id}")
    print(f"Result: {json.dumps(result, indent=2)}")
    
    return result

# Get the list of available functions for the agent
def get_available_functions():
    return ats_functions