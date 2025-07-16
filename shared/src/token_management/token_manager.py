# Token Management System for Portfolio Application
# Adapted from ~/projects/token_mng/open_ai_token_manager.py

import json
import time
import logging
from pathlib import Path
from datetime import datetime
import tiktoken
import openai
from openai import OpenAIError, RateLimitError

# Configurable constants
MODEL_TIERS = [
    {"name": "gpt-4o", "max_tokens": 250_000, "stop_at": 240_000},
    {"name": "gpt-4o-mini", "max_tokens": 2_500_000, "stop_at": 2_450_000}
]
DEFAULT_MODEL = MODEL_TIERS[1]["name"]
ENCODING = "cl100k_base"
DRY_RUN = False  # set True to test without API calls

# Global path references
_path_refs = {}

def setup_paths(project_dir: Path):
    """Setup project-specific paths for token management"""
    state_dir = project_dir / "state"
    logs_dir = project_dir / "logs"
    output_dir = project_dir / "output"

    state_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    return {
        "TOKEN_STATE_FILE": state_dir / "token_usage.json",
        "LOG_FILE": logs_dir / "token_manager.log",
        "OUTPUT_DIR": output_dir
    }

def get_model_info(model_name):
    """Get model information by name"""
    return next((m for m in MODEL_TIERS if m["name"] == model_name), None)

def switch_to_next_model(state):
    """Switch to next model tier when current tier is exhausted"""
    current_index = next((i for i, m in enumerate(MODEL_TIERS) if m["name"] == state["current_model"]), None)
    if current_index is not None and current_index + 1 < len(MODEL_TIERS):
        new_model = MODEL_TIERS[current_index + 1]["name"]
        print(f"[INFO] Switching from {state['current_model']} to {new_model}")
        logging.info(f"Switching from {state['current_model']} to {new_model}")
        state["used_tokens_by_model"][new_model] = 0
        state["current_model"] = new_model
        save_token_state(state)
        return True
    else:
        print(f"[INFO] No more model tiers to switch to. Ending program.")
        return False

def init_token_manager(project_dir: Path):
    """Initialize token manager with project directory"""
    global _path_refs
    _path_refs = setup_paths(project_dir)

    # Initialize logging
    logging.basicConfig(
        filename=_path_refs["LOG_FILE"],
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

def load_token_state():
    """Load current token state or initialize new one"""
    token_file = _path_refs["TOKEN_STATE_FILE"]

    if token_file.exists():
        with open(token_file, "r") as f:
            state = json.load(f)

        today = datetime.now().strftime("%Y-%m-%d")
        if state.get("date") != today:
            logging.info("New day detected. Resetting token usage.")
            return {
                "used_tokens_by_model": {},
                "current_model": DEFAULT_MODEL,
                "last_completed_row": -1,
                "date": today
            }
        if "used_tokens_by_model" not in state:
            state["used_tokens_by_model"] = {}
        return state
    else:
        return {
            "used_tokens_by_model": {},
            "current_model": DEFAULT_MODEL,
            "last_completed_row": -1,
            "date": datetime.now().strftime("%Y-%m-%d")
        }

def save_token_state(state):
    """Save token state to file"""
    token_file = _path_refs["TOKEN_STATE_FILE"]
    try:
        with open(token_file, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save token state: {e}")

def estimate_tokens(messages, model=DEFAULT_MODEL):
    """Estimate token usage for messages"""
    encoding = tiktoken.get_encoding(ENCODING)
    total_tokens = 0
    for msg in messages:
        total_tokens += len(encoding.encode(msg.get("content", ""))) + 4
    return total_tokens + 2

def call_openai_chat(system_prompt, user_prompt, response_format=None, timeout=45, force_model=None):
    """
    Call OpenAI chat completions with token management
    
    Args:
        system_prompt: System message content
        user_prompt: User message content
        response_format: Optional response format ("json" or None)
        timeout: Request timeout in seconds
        force_model: Force specific model (bypasses automatic switching)
    
    Returns:
        Response content or None if failed
    """
    state = load_token_state()
    current_model = force_model if force_model else state["current_model"]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    estimated = estimate_tokens(messages, model=current_model)

    if force_model is None:
        # Automatic switching logic
        while True:
            model_info = next((m for m in MODEL_TIERS if m["name"] == current_model), None)
            if not model_info:
                logging.error(f"Missing model info for {current_model}.")
                return None

            used = state["used_tokens_by_model"].get(current_model, 0)
            if used + estimated < model_info["stop_at"]:
                break

            switched = switch_to_next_model(state)
            if not switched:
                logging.warning("All model tiers exhausted. Ending execution.")
                return None
            current_model = state["current_model"]
            estimated = estimate_tokens(messages, model=current_model)
    else:
        # Forced model: check if tokens are available
        model_info = next((m for m in MODEL_TIERS if m["name"] == current_model), None)
        if not model_info:
            logging.error(f"Missing model info for forced model {current_model}.")
            return None

        if current_model not in state["used_tokens_by_model"]:
            state["used_tokens_by_model"][current_model] = 0

        used = state["used_tokens_by_model"][current_model]
        if used + estimated >= model_info["stop_at"]:
            logging.warning(f"Token limit reached for forced model {current_model}.")
            return None

    # Update state only if not using forced model
    if force_model is None:
        state["current_model"] = current_model

    model_tokens_used = state["used_tokens_by_model"].get(current_model, 0)

    if DRY_RUN:
        logging.info(f"Dry-run: Estimated ~{estimated} tokens for model {current_model}. Skipping call.")
        return "{}"

    for attempt in range(3):
        try:
            response = openai.chat.completions.create(
                model=current_model,
                messages=messages,
                response_format={"type": "json_object"} if response_format == "json" else None,
                timeout=timeout
            )

            actual_tokens = response.usage.total_tokens
            state["used_tokens_by_model"][current_model] = model_tokens_used + actual_tokens
            save_token_state(state)

            logging.info(f"Model: {current_model} | Tokens used: {actual_tokens} | Total: {state['used_tokens_by_model'][current_model]}")
            print(f"Model: {current_model} | Tokens used: {actual_tokens}")

            return response.choices[0].message.content

        except RateLimitError:
            logging.warning(f"Rate limit on {current_model}. Retrying in 10 seconds...")
            time.sleep(10)
        except OpenAIError as e:
            logging.error(f"OpenAI error on {current_model}: {e}")
            return None

    logging.error(f"Failed all retries for model {current_model}.")
    return None

def update_last_completed_row(row_index: int):
    """Update last completed row index"""
    state = load_token_state()
    state["last_completed_row"] = row_index
    save_token_state(state)

def get_last_completed_row():
    """Get last completed row index"""
    state = load_token_state()
    return state.get("last_completed_row", -1)

def get_token_usage_summary():
    """Get summary of token usage"""
    state = load_token_state()
    return {
        "current_model": state["current_model"],
        "date": state["date"],
        "usage_by_model": state["used_tokens_by_model"],
        "last_completed_row": state.get("last_completed_row", -1)
    }