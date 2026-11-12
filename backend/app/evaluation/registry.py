"""Small explicit version dispatch; future categories supply separate policies/reducers."""
from collections.abc import Callable
from app.evaluation.commerce import evaluate
from app.evaluation.rubric import VERSION, policy

EVALUATORS: dict[str, Callable[[dict], dict]] = {VERSION: evaluate}
POLICIES: dict[str, Callable[[], dict]] = {VERSION: policy}
