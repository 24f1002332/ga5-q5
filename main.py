from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List
import json
import re

app = FastAPI()


class Step(BaseModel):
    step_number: int
    tool: str
    args: Dict[str, Any] = {}
    tokens_used: int


class RequestData(BaseModel):
    budget_tokens: int
    steps: List[Step]


def normalize(value):
    """Normalize values for loop comparison."""
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            # Ignore IDs
            if k == "id":
                continue
            result[k] = normalize(v)
        return result

    if isinstance(value, list):
        return [normalize(v) for v in value]

    if isinstance(value, str):
        # Collapse whitespace
        return re.sub(r"\s+", " ", value).strip()

    return value


def make_key(step: Step):
    args = normalize(step.args)
    return (
        step.tool,
        json.dumps(args, sort_keys=True, separators=(",", ":"))
    )


def detect_loop(steps: List[Step], n=3):
    if len(steps) < n:
        return False

    last = steps[-n:]
    first_key = make_key(last[0])

    for s in last[1:]:
        if make_key(s) != first_key:
            return False

    return True


@app.post("/")
@app.post("/check")
def check(req: RequestData):

    cumulative = sum(s.tokens_used for s in req.steps)

    # Rule 1: Budget
    if cumulative >= req.budget_tokens:
        return {
            "decision": "halt",
            "reason": f"Cumulative tokens_used ({cumulative}) has reached the budget ({req.budget_tokens})."
        }

    # Rule 2: Loop
    if detect_loop(req.steps):
        return {
            "decision": "halt",
            "reason": "Detected an infinite loop: the same tool was called three consecutive times with identical arguments."
        }

    return {
        "decision": "continue",
        "reason": "Run is under budget and no infinite loop detected."
    }
