import os
import sys
import uuid
import json
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import openai
import asyncio
from typing import Dict, List, Any, Optional, Union
import argparse
import logging
import dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# Load environment variables from .env file
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to import functions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.middleware import TokenVerificationMiddleware
from functions.ats_functions import get_available_functions, execute_function

# Load OpenAI API key from environment variable
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    logger.warning("OPENAI_API_KEY environment variable is not set or empty")
    print("Error: OPENAI_API_KEY environment variable is not set or empty")

# Initialize OpenAI client
try:
    client = openai.AsyncClient(api_key=api_key)
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    print(f"Error initializing OpenAI client: {str(e)}")
    client = None

# Initialize rich console for better formatting
console = Console()

# Initialize FastAPI app
app = FastAPI(title="AI Recruiter API",)
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # or specify a list of allowed domains instead of ["*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    
@app.get("/health", response_model=MessageResponse)
def health_check():
    """Health check endpoint"""
    return MessageResponse(response="Hive is Alive")

app.add_middleware(TokenVerificationMiddleware)

class RecruiterAgent:
    def __init__(self, session_id: str, token: str = None, model: str = "gpt-4-turbo"):
        self.MODE = os.environ.get("MODE")
        self.model = model
        self.session_id = session_id
        self.token = token
        self.functions = get_available_functions()
        
        # Initialize conversation history
        self.messages = [
            {
                "role": "system",
                "content": """You are an AI recruiter assistant that helps hiring managers and recruiters manage 
                their applicant tracking system. You can help with:

                1. Creating and managing job postings
                2. Reviewing and managing candidates
                3. Setting up interview pipelines and assessments
                4. Tracking candidate progress through hiring stages
                5. Providing insights on hiring metrics
                6. Creating job pipelines and managing candidate applications

                You have access to the company's ATS through GraphQL API functions. Use these functions to help users
                accomplish their recruitment tasks. Be proactive in suggesting relevant actions but make sure to
                understand the user's needs first.

                When responding to the user:
                - Be professional, helpful, and concise
                - Explain any recommended actions clearly
                - Format information in an easy-to-read manner
                - Respect confidentiality of candidate information
                - When users request for information that requires an input use the relevant function to provide a list of possible options of the input they can select from i.e when they request for top candidate with a pipeline, automatically use getRecentPipeline function to list possible pipelines in the same response
                
                When asked to create a pipeline:
                    - Initiate Conversation and Gather Job Criteria:
                    •	Always engage the user professionally, asking clarifying questions to gather missing job details if not fully provided in the initial message.
                    •	Essential Fields to Collect:
                    •	pipeline_name (Required)
                    •	job_title (Required)
                    •	skills (Required)
                    •	Optional Fields to Collect:
                    •	min_experience (Years)
                    •	job_type
                    •	location
                    •	Ensure a conversational flow to dynamically capture missing information, adjusting language for clarity and professionalism.
                    prompt them if they want to provide optional details
                    •	Add the pipeline link to the response message for easy access. i.e https://gethivemind.ai/pipeline/{{pipeline_id}}. pipeline_id will be return after successful creation of the pipeline
                    
                When you need to access the ATS system, use the available functions to fetch or update the necessary data.
                """
            }
        ]

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history"""
        self.messages.append({"role": role, "content": content})

    async def call_function(self, function_name: str, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a function and get the result asynchronously"""
        # Use asyncio to run the potentially blocking function in a thread pool
        result = await execute_function(self.token, function_name, function_args)
        return result

    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the assistant's response asynchronously"""
        # Add user message to conversation history
        self.add_message("user", user_message)
        
        # Call the model with the updated conversation
        response = await client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=[{"type": "function", "function": f} for f in self.functions],
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls
        
        # If the model wants to call a function
        if tool_calls:
            # Add the assistant's message with function calls to conversation
            self.add_message("assistant", assistant_message.content or "")
            self.messages[-1]["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in tool_calls
            ]
            
            # Process function calls concurrently
            function_tasks = []
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Create a task for this function call
                task = asyncio.create_task(self.call_function(function_name, function_args))
                function_tasks.append((tool_call.id, function_name, task))
            
            # Process all function responses and add them to the conversation
            for tool_call_id, function_name, task in function_tasks:
                function_response = await task
                
                # Add the function response to conversation
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": function_name,
                    "content": json.dumps(function_response)
                })
            
            # Get a new response from the model with the function results
            second_response = await client.chat.completions.create(
                model=self.model,
                messages=self.messages
            )
            
            assistant_response = second_response.choices[0].message.content
            self.add_message("assistant", assistant_response)
            return assistant_response
        
        # If no function call is needed, return the response
        self.add_message("assistant", assistant_message.content)
        return assistant_message.content

async def async_main(session_id: str):
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AI Recruiter Agent CLI')
    parser.add_argument('--model', type=str, default='gpt-4-turbo', help='OpenAI model to use')
    args = parser.parse_args()
    
    # Create the agent
    agent = RecruiterAgent(session_id=session_id, model=args.model)
    
    # Print welcome message
    console.print(Panel.fit(
        "🤖 [bold blue]AI Recruiter Assistant[/bold blue] 🤖\n\n"
        "I can help you manage your recruitment process through the ATS system.\n"
        "Type 'exit' or 'quit' to end the conversation.",
        title="Welcome"
    ))
    
    # Main conversation loop
    while True:
        # Get user input
        user_input = Prompt.ask("\n[bold green]You[/bold green]")
        
        # Check if the user wants to exit
        if user_input.lower() in ['exit', 'quit']:
            console.print("\n[bold]Thank you for using the AI Recruiter Assistant. Goodbye![/bold]")
            break
        
        # Show a processing indicator
        with console.status("[bold blue]Processing your request...[/bold blue]", spinner="dots"):
            # Process the message asynchronously
            response = await agent.process_message(user_input)
        
        # Display the assistant's response with rich formatting
        console.print("\n[bold purple]AI Recruiter[/bold purple]:")
        console.print(Markdown(response))

# Pydantic models for API requests and responses
class MessageRequest(BaseModel):
    # user_id: str
    message: str
    session_id: Optional[str] = None

# Dictionary to store agent instances by session_id
agent_sessions = {}

# API endpoints
@app.post("/", response_model=MessageResponse)
async def process_message_endpoint(message: MessageRequest, req: Request):
    """Process a message from the user and return the assistant's response."""
    try:
        # Determine session_id from the message or the middleware-verified token.
        if message.session_id:
            session_id = message.session_id
        elif hasattr(req.state, "decoded_token") and req.state.decoded_token:
            session_id = req.state.decoded_token.get("id")
        else:
            # Neither session_id nor token provided.
            raise HTTPException(status_code=404, detail="Session not found; pass token")
        
        # Create a new RecruiterAgent for this session if it does not exist.
        # Only create an agent if the token is provided; otherwise, return 404.
        if session_id not in agent_sessions:
            if hasattr(req.state, "token") and req.state.token:
                token = req.state.token
                agent_sessions[session_id] = RecruiterAgent(session_id=session_id, token=token)
            else:
                raise HTTPException(status_code=404, detail="Session not found; pass token")
        
        # Retrieve the existing RecruiterAgent for this session.
        agent = agent_sessions[session_id]

        # Process the user's message.
        response_text = await agent.process_message(message.message)

        return MessageResponse(
            response=response_text,
            session_id=session_id
        )
    except Exception as e:
        logger.error("Error processing message: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@app.post("/reset/{session_id}")
async def reset_session(session_id: str):
    """Reset the session by removing it from the active sessions."""
    try:
        # Check if the session exists
        if session_id in agent_sessions:
            # Remove the session
            del agent_sessions[session_id]
            return JSONResponse(
                content={"message": "Session successfully reset."},
                status_code=200
            )
        else:
            # If the session doesn't exist
            raise HTTPException(status_code=404, detail="Session not found.")
    except Exception as e:
        logger.error("Error resetting session: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error resetting session: {str(e)}")
    
@app.get("/health", response_model=MessageResponse)
def health_check():
    """Health check endpoint"""
    return MessageResponse(response="Hive is Alive")
    

import os
import sys
import uuid
import asyncio
import signal
import logging
from rich.console import Console
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
console = Console()

def main():
    """Entry point for the application"""
    session_id = str(uuid.uuid4())
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--web":
            # Web mode: start the FastAPI server with uvicorn
            import uvicorn
            port = int(os.environ.get("PORT", 8000))
            host = os.environ.get("HOST", "0.0.0.0")
            console.print(f"Starting web server on {host}:{port}...")
            uvicorn.run(app, host=host, port=port)
        else:
            # CLI mode: run the async main function using asyncio.run()
            asyncio.run(async_main(session_id))
    except KeyboardInterrupt:
        console.print("\n\n[bold]Program interrupted. Exiting...[/bold]")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        console.print(f"\n\n[bold red]Error: {str(e)}[/bold red]")

if __name__ == "__main__":
    main()
    