import os
import sys
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
app = FastAPI(title="AI Recruiter API")

class RecruiterAgent:
    def __init__(self, model="gpt-4-turbo"):
        self.model = model
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

                You have access to the company's ATS through GraphQL API functions. Use these functions to help users
                accomplish their recruitment tasks. Be proactive in suggesting relevant actions but make sure to
                understand the user's needs first.

                When responding to the user:
                - Be professional, helpful, and concise
                - Explain any recommended actions clearly
                - Format information in an easy-to-read manner
                - Respect confidentiality of candidate information

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
        result = await asyncio.to_thread(execute_function, function_name, function_args)
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

async def async_main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AI Recruiter Agent CLI')
    parser.add_argument('--model', type=str, default='gpt-4-turbo', help='OpenAI model to use')
    args = parser.parse_args()
    
    # Create the agent
    agent = RecruiterAgent(model=args.model)
    
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
    user_id: str
    message: str
    session_id: Optional[str] = None

class MessageResponse(BaseModel):
    response: str
    session_id: str

# Dictionary to store agent instances by session_id
agent_sessions = {}

# API endpoints
@app.post("/", response_model=MessageResponse)
async def process_message(request: MessageRequest):
    """Process a message from the user and return the assistant's response"""
    try:
        # Get or create an agent for this session
        session_id = request.session_id or request.user_id
        if session_id not in agent_sessions:
            agent_sessions[session_id] = RecruiterAgent()
            
        # Process the message
        agent = agent_sessions[session_id]
        response = await agent.process_message(request.message)
        
        return MessageResponse(
            response=response,
            session_id=session_id
        )
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

def main():
    """Entry point for the application"""
    try:
        # Check if CLI mode or web server mode
        if len(sys.argv) > 1 and sys.argv[1] == "--web":
            # Start the FastAPI server with uvicorn
            import uvicorn
            port = int(os.environ.get("PORT", 8000))
            host = os.environ.get("HOST", "0.0.0.0")
            console.print(f"Starting web server on {host}:{port}...")
            uvicorn.run(app, host=host, port=port)
        else:
            # Run the async main function in CLI mode
            asyncio.run(async_main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        console.print("\n\n[bold]Program interrupted. Exiting...[/bold]")
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error: {str(e)}")
        console.print(f"\n\n[bold red]Error: {str(e)}[/bold red]")

if __name__ == "__main__":
    main()