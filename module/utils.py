import os
from typing import List, Dict, Any
import asyncio

def load_prompt_file(filename: str) -> str:
    """Loads prompt text from the prompts directory."""
    # Logic to find prompt file relative to this module
    # Assuming module/utils.py, prompts are in ../prompts
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    prompt_path = os.path.join(project_root, 'prompts', filename)
    
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Prompt file {filename} not found at {prompt_path}")
        return ""

def calculate_total_usage(usage_list: List[Any]) -> Dict[str, int]:
    """Calculates total token usage from a list of usage metadata objects."""
    total_prompt_tokens = 0
    total_candidates_tokens = 0
    total_tokens = 0
    
    for usage in usage_list:
        # Check attributes based on google.genai usage object structure
        # Usually has prompt_token_count, candidates_token_count, total_token_count
        if hasattr(usage, 'prompt_token_count'):
            total_prompt_tokens += usage.prompt_token_count
        if hasattr(usage, 'candidates_token_count'):
            total_candidates_tokens += usage.candidates_token_count
        if hasattr(usage, 'total_token_count'):
            total_tokens += usage.total_token_count
            
    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_candidates_tokens,
        "total_tokens": total_tokens
    }

def run_async(coro):
    """
    Helper to run async coroutines safely in Streamlit.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If loop is running, we can't use run_until_complete.
        # This happens if we are inside a callback in some environments.
        # However, Streamlit usually runs script in a thread without a running loop.
        # But if 'asyncio.run' was called before, it might have closed it.
        pass

    try:
        return loop.run_until_complete(coro)
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        raise e
