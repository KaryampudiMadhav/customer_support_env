``` python
"""
Inference Script Example
"""
import os
import re
import base64
import textwrap
from io import BytesIO
from typing import List, Optional, Dict

from openai import OpenAI
import numpy as np
from PIL import Image

from browsergym_env import BrowserGymAction, BrowserGymEnv

API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

MAX_STEPS = 8
MAX_DOM_CHARS = 3500
TEMPERATURE = 0.2
MAX_TOKENS = 200
FALLBACK_ACTION = "noop()"

DEBUG = True

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=API_KEY,
)

# =========================
# HELPER FUNCTIONS
# =========================

def encode_image(image: Image.Image) -> str:
    """Convert image to base64"""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def truncate_dom(dom: str) -> str:
    """Limit DOM size"""
    return dom[:MAX_DOM_CHARS]


def extract_action(text: str) -> str:
    """Extract action like click(), type(), etc."""
    match = re.search(r"\w+\(.*?\)", text)
    return match.group(0) if match else FALLBACK_ACTION


def build_prompt(observation: Dict) -> str:
    """Create prompt for LLM"""
    dom = truncate_dom(observation.get("dom", ""))
    url = observation.get("url", "")
    
    prompt = f"""
You are a browser automation agent.

Current URL:
{url}

DOM:
{dom}

Decide next action.
Only return a valid function call like:
click(selector)
type(selector, text)
scroll(x, y)
noop()

Answer:
"""
    return textwrap.dedent(prompt)


def get_llm_action(prompt: str) -> str:
    """Call LLM"""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        text = response.choices[0].message.content
        return extract_action(text)

    except Exception as e:
        print("LLM Error:", e)
        return FALLBACK_ACTION


def run_episode():
    env = BrowserGymEnv()
    observation = env.reset()

    for step in range(MAX_STEPS):
        if DEBUG:
            print(f"\n--- Step {step} ---")

        prompt = build_prompt(observation)
        action_str = get_llm_action(prompt)

        if DEBUG:
            print("Action:", action_str)

        action = BrowserGymAction.from_string(action_str)

        observation, reward, done, info = env.step(action)

        if done:
            break

    env.close()

if __name__ == "__main__":
    if not API_KEY or not MODEL_NAME:
        raise ValueError("Missing API_KEY or MODEL_NAME")

    run_episode()
```
