# Development Guidelines for ChatGPT Recruiter Agent

## Build Commands
- Run the agent: `python agent/recruiter_agent.py [--model gpt-4-turbo]`
- Install dependencies: `pip install -r requirements.txt`

## Project Structure
- `schema/` - GraphQL schema definitions
- `functions/` - ChatGPT function definitions and mock backend
- `agent/` - Main agent implementation with CLI

## Code Style
- Follow PEP 8 guidelines for Python code
- Use type hints for all function parameters and return values
- Organize imports: stdlib first, then third-party, then local
- Class names: PascalCase; Functions/variables: snake_case
- Use async/await consistently throughout the codebase
- Add docstrings to all classes and functions

## Error Handling
- Use try/except blocks for API calls and external operations
- Log errors with timestamps using ISO format
- Gracefully handle keyboard interrupts with proper cleanup

## Concurrency Patterns
- Use asyncio.create_task for parallel operations
- Use asyncio.to_thread for CPU-bound blocking operations
- Await all async operations properly

## Testing
- Currently no formal testing framework