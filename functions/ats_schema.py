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
    },
    {
        "function": {
            "name": "createPipeline",
            "description": "Create a new recruiting pipeline with specified job details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline_name": {
                        "type": "string",
                        "description": "Name of the pipeline to be created."
                    },
                    "job_title": {
                        "type": "string",
                        "description": "Job title for the pipeline, e.g., Frontend Developer."
                    },
                    "job_description": {
                        "type": "string",
                        "description": "A detailed job description based on the job title and preferences."
                    },
                    "job_type": {
                        "type": "string",
                        "description": "Type of job recruitment. Possible values: Full-Time, Part-Time, Contract, Internship, Volunteer, Other. Ensure it is case-sensitive."
                    },
                    "skills": {
                        "type": "string",
                        "description": "skills required for the job role"
                    },
                    "experience": {
                        "type": "string",
                        "description": "experience level required for the job role"
                    },
                    "location": {
                        "type": "string",
                        "description": "Location for the recruitment."
                    },
                    "workplace_type": {
                        "type": "string",
                        "description": "Workplace type of the recruitment. Possible values: Remote, Hybrid, In-Office. Ensure it is case-sensitive."
                    }
                },
                "required": ["pipeline_name", "job_title", "job_type", "location", "workplace_type", "skills"]
            }
        },
        "graphQL": "mutation CreateCustomPipeline($object: Pipeline_insert_input!) { insert_Pipeline_one(object: $object) { id } }"
    }
]

insert_node_query = "mutation InsertNodes($objects: [PipelineNode_insert_input!]!) {insert_PipelineNode(objects: $objects) {affected_rows}}"
get_company_id = "query GetUserCompanyId($userId: uuid!) { User(where: {id: {_eq: $userId}}) { company_id } }"
