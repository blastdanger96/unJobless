import os
from dotenv import load_dotenv

load_dotenv()

AI_ENABLED = os.getenv("AI_ENABLED", "FALSE").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "8"))

_client = None

def _get_client ():
    gloabl = _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            api_key=os.getenv("KEY HERE"),
            timeout = AI_TIMEOUT

        )
    return _client

def ai_grade (role:str, questions: str, answer: str, meta:dict) -> dict | None:
#returns none if AI is not responding and goes back to rule-based grading
    '''
    Returns dict with keys: feedback, points, breakdown
    Returns None if AI disabled, no key, or any error (caled falls back to rule-based)
    '''

    if not AI_ENABLED:
        return None
    if not os.getenv ("KEY"):
        return None

    return None

