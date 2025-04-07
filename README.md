# ChatGPT Recruiter Agent

An AI-powered recruiter agent that helps manage your recruiting process through a mock Applicant Tracking System.

## Overview

This project implements a ChatGPT-based recruiting assistant that can help with:

1. Creating and managing job postings
2. Reviewing and managing candidates
3. Setting up interview pipelines and assessments
4. Tracking candidate progress through hiring stages
5. Providing insights on hiring metrics

The agent interacts with a mock GraphQL backend that simulates an Applicant Tracking System (ATS). The responses from the backend are generated by ChatGPT, which creates realistic mock data based on the queries.

## Project Structure

- `schema/` - Contains the GraphQL schema for the ATS
- `functions/` - Contains the mock functions that interact with the simulated GraphQL backend
- `agent/` - Contains the recruiter agent implementation

## Requirements

- Python 3.8+ (Python 3.10+ recommended for best asyncio support)
- OpenAI API key

## Dependencies

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file in the root directory with your API keys:

```
OPENAI_API_KEY=your-api-key-here
ADMIN_SECRET=your-admin-secret-here
USE_MOCK_DATA=true
```

Or export them as environment variables:

```bash
export OPENAI_API_KEY="your-api-key-here"
export ADMIN_SECRET="your-admin-secret-here"
export USE_MOCK_DATA="true"
```

Environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key
- `ADMIN_SECRET`: Hasura admin secret for GraphQL API access
- `USE_MOCK_DATA`: Set to "true" to use mock data instead of real API calls (default: "false")
- `PORT`: Port for the web server (default: 8000, web mode only)
- `JWT_SIGNING_KEY`: JWT secret for hivemind
-  `MODE`: Mode of interaction with hive, terminal or web

## Usage

### CLI Mode

Run the recruiter agent in interactive CLI mode:

```bash
python agent/recruiter_agent.py
```

Optional arguments:
- `--model` - Specify the OpenAI model to use (default: gpt-4-turbo)

### Web API Mode

Run the recruiter agent as a FastAPI web server:

```bash
python agent/recruiter_agent.py --web
```

This will start a web server on port 8000 (or the port specified in the PORT environment variable).

#### API Endpoints

- **POST /** - Process a user message
  - Request body:
    ```json
    {
      "message": "Show me all open job positions",
      "session_id": "optional-session-id"
    }
    ```
  - Response:
    ```json
    {
      "response": "Here are the open job positions...",
      "session_id": "session-id"
    }
    ```

## Example Interactions

- "Show me all open job positions"
- "Create a new software engineer job posting"
- "List candidates for the senior developer role" 
- "Move candidate John Smith to the technical interview stage"
- "Create a technical assessment for the frontend developer role"
- "Add a note about my interview with Sarah Williams"

## Project Components

### GraphQL Schema

The schema defines the structure of the ATS data model, including:
- Users (recruiters, hiring managers)
- Teams
- Jobs
- Pipelines and Stages
- Candidates
- Assessments and Grades

### Mock Functions

The functions module provides:
- Definition of ChatGPT functions that map to GraphQL operations
- Mock implementation that generates realistic responses using ChatGPT
- Logging and tracking of function calls

### Recruiter Agent

The agent provides:
- A command-line interface for interacting with the ATS
- A FastAPI web server for API access
- Integration with the OpenAI API for message processing
- Function calling capabilities to retrieve and update ATS data
- Rich text formatting for an improved user experience (CLI mode)
- Stateful conversation handling with session tracking (both CLI and web modes)

## Note

This is a demonstration project. The backend is simulated, and all data is generated by ChatGPT during the interaction.