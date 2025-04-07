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
from contextlib import asynccontextmanager
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
from utils.middleware import TokenVerificationMiddleware
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
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to Redis
    redis_client = await connect_redis()
    if not redis_client:
        raise Exception("Redis connection failed.")
    app.state.redis_client = redis_client
    yield
    # Shutdown: close Redis connection
    await app.state.redis_client.close()
    
app = FastAPI(title="AI Recruiter API", lifespan=lifespan)
app.add_middleware(TokenVerificationMiddleware)

# --- RecruiterAgent Class using Async Redis ---
class RecruiterAgent:
    def __init__(self, session_id: str, model: str = "gpt-4-turbo"):
        self.MODE = os.environ.get("MODE")
        self.model = model
        self.session_id = session_id
        self.functions = get_available_functions()
        self.messages = []  # Will be populated via async load

    @classmethod
    async def create(cls, session_id: str, model: str = "gpt-4-turbo"):
        """
        Asynchronous factory method that initializes a RecruiterAgent
        and loads its conversation history from Redis.
        """
        agent = cls(session_id, model)
        await agent._load_state()
        return agent

    async def _load_state(self) -> None:
        """Load conversation history from Redis asynchronously."""
        if self.MODE == "web":
            key = f"recruiter_agent:{self.session_id}"
            state = await get_redis_data(key)
            if state:
                try:
                    data = json.loads(state)
                    self.messages = data.get("messages", [])
                except Exception as e:
                    logger.error("Error loading state from Redis: %s", e)
                self.messages = []
            else:
                # Initialize conversation history with a system message for web.
                self.messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are an AI recruiter assistant that helps hiring managers and recruiters manage "
                            "their applicant tracking system. You can help with:\n\n"
                            "1. Creating and managing job postings\n"
                            "2. Reviewing and managing candidates\n"
                            "3. Setting up interview pipelines and assessments\n"
                            "4. Tracking candidate progress through hiring stages\n"
                            "5. Providing insights on hiring metrics\n"
                            "6. Creating job pipelines and managing candidate applications\n\n"
                            "You have access to the company's ATS through GraphQL API functions. Use these functions to help users "
                            "accomplish their recruitment tasks. Be proactive in suggesting relevant actions but make sure to "
                            "understand the user's needs first.\n\n"
                            "When responding to the user:\n"
                            "- Be professional, helpful, and concise\n"
                            "- Explain any recommended actions clearly\n"
                            "- Format information in an easy-to-read manner\n"
                            "- Respect confidentiality of candidate information\n"
                            "- When users request information that requires input, use the relevant function to provide a list "
                            "of options they can select from.\n\n"
                            "When asked to create a pipeline:\n"
                            "- Initiate conversation and gather job criteria, prompting for required and optional details.\n\n"
                            "When you need to access the ATS system, use the available functions to fetch or update the necessary data."
                        )
                    }
                ]
                await self._save_state()
        else:
            # Initialize conversation history with a system message for CLI
            if not self.messages:
                self.messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an AI recruiter assistant that helps hiring managers and recruiters manage "
                        "their applicant tracking system. You can help with:\n\n"
                        "1. Creating and managing job postings\n"
                        "2. Reviewing and managing candidates\n"
                        "3. Setting up interview pipelines and assessments\n"
                        "4. Tracking candidate progress through hiring stages\n"
                        "5. Providing insights on hiring metrics\n"
                        "6. Creating job pipelines and managing candidate applications\n\n"
                        "You have access to the company's ATS through GraphQL API functions. Use these functions to help users "
                        "accomplish their recruitment tasks. Be proactive in suggesting relevant actions but make sure to "
                        "understand the user's needs first.\n\n"
                        "When responding to the user:\n"
                        "- Be professional, helpful, and concise\n"
                        "- Explain any recommended actions clearly\n"
                        "- Format information in an easy-to-read manner\n"
                        "- Respect confidentiality of candidate information\n"
                        "- When users request information that requires input, use the relevant function to provide a list "
                        "of options they can select from.\n\n"
                        "When asked to create a pipeline:\n"
                        "- Initiate conversation and gather job criteria, prompting for required and optional details.\n\n"
                        "When you need to access the ATS system, use the available functions to fetch or update the necessary data."
                    )
                }
            ]

    async def _save_state(self) -> None:
        """Save the current conversation state to Redis asynchronously."""
        key = f"recruiter_agent:{self.session_id}"
        data = {"messages": self.messages}
        await set_redis_data(key, json.dumps(data))

    async def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history and save state asynchronously."""
        self.messages.append({"role": role, "content": content})
        if self.MODE == "web":
            await self._save_state()

    async def call_function(self, function_name: str, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a function and get the result asynchronously"""
        result = await execute_function(self.session_id, function_name, function_args)
        return result

    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the assistant's response asynchronously"""
        # Add user message to conversation history
        await self.add_message("user", user_message)
        
        # Call the model with the updated conversation
        response = await client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=[{"type": "function", "function": f} for f in self.functions],
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        tool_calls = getattr(assistant_message, "tool_calls", [])
        
        # If the model wants to call a function
        if tool_calls:
            # Add the assistant's message with function calls to conversation
            await self.add_message("assistant", assistant_message.content or "")
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
                await self._save_state()  # Save the updated state to Redis
            
            # Get a new response from the model with the function results
            second_response = await client.chat.completions.create(
                model=self.model,
                messages=self.messages
            )
            
            assistant_response = second_response.choices[0].message.content
            await self.add_message("assistant", assistant_response)
            return assistant_response
        
        # If no function call is needed, return the response
        await self.add_message("assistant", assistant_message.content)
        return assistant_message.content

async def async_main(session_id: str):
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AI Recruiter Agent CLI')
    parser.add_argument('--model', type=str, default='gpt-4-turbo', help='OpenAI model to use')
    args = parser.parse_args()
    
    # Create the agent
    agent = await RecruiterAgent.create(model=args.model, session_id=session_id)
    
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
async def process_message_endpoint(message: MessageRequest, req: Request):
    """Process a message from the user and return the assistant's response."""
    try:
        # Determine session_id based on a middleware-verified token or request data.
        if hasattr(req.state, "decoded_token") and req.state.decoded_token:
            session_id = req.state.decoded_token.get("id")
            key = f"session:{session_id}"
            existing_session = await get_redis_data(key)
            if not existing_session:
                # Update Redis with the raw token from middleware (with expiration).
                await set_redis_data_with_ex(key, req.state.token, 3600)
        elif message.session_id:
            session_id = message.session_id
        else:
            raise HTTPException(status_code=400, detail="session_id or token is required")

        # Verify session exists
        session = await get_redis_data(f"session:{session_id}")
        if not session:
            raise HTTPException(status_code=403, detail="Session not found or expired; pass token")

        # Create a new RecruiterAgent instance using the async factory method.
        agent = await RecruiterAgent.create(session_id=session_id)

        # Process the user's message.
        response_text = await agent.process_message(message.message)

        return MessageResponse(
            response=response_text,
            session_id=session_id
        )
    except Exception as e:
        logger.error("Error processing message: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


import os
import sys
import uuid
import asyncio
import signal
import logging
from rich.console import Console
from dotenv import load_dotenv

# Assume these functions are defined elsewhere:
# async_main(session_id), connect_redis(), app (the FastAPI instance)

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
    