import json
import logging
from typing import Optional
from app.llm.ollama_client import OllamaClient
from app.config_loader import load_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert bank transaction categorizer.
Your goal is to deduce the category and merchant name from a list of raw banking narrations.

Rules:
1. 'category' MUST be a very short, generic label (e.g., "Food", "Shopping", "Transport", "Utilities", "Transfer", "Salary", "Investment").
2. 'merchant_name' MUST be the cleaned up name of the business or person (e.g., "Zomato", "Amazon", "Rahul"). If unknown, output "UNKNOWN".
3. Return your response STRICTLY as a JSON array of objects. Do not include markdown blocks, explanations, or any other text.
4. Each object in the array MUST have the exact keys: "narration", "category", and "merchant_name".
"""

def batch_categorize(narrations: list[str]) -> dict[str, dict]:
    """
    Takes a list of narrations and queries the Ollama LLM to categorize them in a single batch.
    Returns a dictionary mapping the original narration to a dict with 'category' and 'merchant_name'.
    """
    if not narrations:
        return {}
        
    client = OllamaClient()
    if not client.is_available():
        logger.warning("Ollama client is not available. Skipping AI categorization.")
        return {}
        
    # Construct prompt
    prompt = "Categorize the following narrations:\n"
    for idx, narr in enumerate(narrations):
        prompt += f"{idx + 1}. {narr}\n"
        
    logger.info(f"Sending {len(narrations)} narrations to Ollama for categorization...")
    
    try:
        # Give it a higher max_tokens since it's generating a JSON array for multiple items
        response = client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=1500
        )
        
        # Cleanup potential markdown block wrapping (e.g., ```json ... ```)
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
            
        parsed_list = json.loads(response.strip())
        
        result_map = {}
        for item in parsed_list:
            if isinstance(item, dict) and "narration" in item:
                result_map[item["narration"]] = {
                    "category": item.get("category", "uncategorized"),
                    "merchant_name": item.get("merchant_name", "UNKNOWN")
                }
                
        logger.info(f"Successfully AI-categorized {len(result_map)} narrations.")
        return result_map
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Ollama JSON response: {e}\nResponse was: {response}")
        return {}
    except Exception as e:
        logger.error(f"Error during AI categorization: {e}")
        return {}
