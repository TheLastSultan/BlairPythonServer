import os
import sys
import jwt
import uuid
import json
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
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Load environment variables from .env file
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to import functions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from middleware import TokenVerificationMiddleware
from functions.ats_functions import get_available_functions, execute_function
from utils.cache import connect_redis, set_redis_data_with_ex, get_redis_data, delete_redis_data, set_redis_data

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
app = FastAPI(title="AI Recruiter API")
app.add_middleware(TokenVerificationMiddleware)
class RecruiterAgent:
    def __init__(self, session_id: str, model="gpt-4-turbo"):
        self.model = model
        self.session_id = session_id
        self.functions = get_available_functions()
        
         # Load conversation history from Redis
        key = f"recruiter_agent:{self.session_id}"
        state = get_redis_data(key)
        if state:
            try:
                data = json.loads(state)
                self.messages = data.get("messages", [])
            except Exception as e:
                print(f"Error loading state from Redis: {e}")
                self.messages = []
        else:    
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
                    
                When you need to access the ATS system, use the available functions to fetch or update the necessary data.
                """
            }
        ]
            self._save_state()
            
    def _save_state(self) -> None:
        """Save the current conversation state to Redis."""
        key = f"recruiter_agent:{self.session_id}"
        data = {"messages": self.messages}
        set_redis_data(key, json.dumps(data))
        
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history"""
        self.messages.append({"role": role, "content": content})
        self._save_state()

    async def call_function(self, function_name: str, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a function and get the result asynchronously"""
        # Use asyncio to run the potentially blocking function in a thread pool
        result = await asyncio.to_thread(execute_function, self.session_id, function_name, function_args)
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
                self._save_state()
            
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
    agent = RecruiterAgent(model=args.model, session_id=session_id)
    
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

class MessageResponse(BaseModel):
    response: str
    session_id: str

# API endpoints
@app.post("/", response_model=MessageResponse)
async def process_message(message: MessageRequest, req: Request):
    """Process a message from the user and return the assistant's response"""
    try:
        # Determine session_id based on the middleware-verified token or fallback to request data
        if req.state.decoded_token:
            session_id = req.state.decoded_token.get("id")
            key = f"session:{session_id}"
            # Update Redis with the raw token from the middleware
            delete_redis_data(key)
            set_redis_data_with_ex(key, req.state.token, 3600)
        elif message.session_id:
            session_id = message.session_id
        else:
            raise HTTPException(status_code=400, detail="session_id or token is required")
        
        # Check if the session already exists
        session = get_redis_data(f"session:{session_id}")
        if not session:
            raise HTTPException(status_code=403, detail="Session not found or expired; pass token")
        
        # Create a new agent instance
        agent = RecruiterAgent(session_id=session_id)

        # Process the message
        response = await agent.process_message(message.message)
        
        return MessageResponse(
            response=response,
            session_id=session_id
        )
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

def main():
    """Entry point for the application"""
    session_id = str(uuid.uuid4())
    try:
        # Check if CLI mode or web server mode
        if len(sys.argv) > 1 and sys.argv[1] == "--web":
            # Start the FastAPI server with uvicorn
            import uvicorn
            port = int(os.environ.get("PORT", 8000))
            host = os.environ.get("HOST", "0.0.0.0")
            console.print(f"Starting web server on {host}:{port}...")
            redis_client = connect_redis()
            if not redis_client:
                console.print("Redis connection failed. Exiting application.", style="bold red")
                sys.exit(1)
            uvicorn.run(app, host=host, port=port)
        else:
            # Run the async main function in CLI mode
            asyncio.run(async_main(session_id))
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        delete_redis_data(f"session:{session_id}")
        console.print("\n\n[bold]Program interrupted. Exiting...[/bold]")
    except Exception as e:
        # Handle any unexpected errors
        delete_redis_data(f"session:{session_id}")
        logger.error(f"Unexpected error: {str(e)}")
        console.print(f"\n\n[bold red]Error: {str(e)}[/bold red]")

if __name__ == "__main__":
    main()