from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata. Import future domain models here for Alembic discovery."""

from app.models.agent import Agent  # noqa: E402,F401 - populate migration metadata
from app.models.environment import Environment, EnvironmentTemplate  # noqa: E402,F401
from app.models.assessment import Assessment, RunEvent  # noqa: E402,F401
from app.models.rai import RaiProposal, RaiProposalEvent  # noqa: E402,F401
from app.models.payment import Payment  # noqa: E402,F401
from app.models.evaluation import ScoringBinding, Evaluation, EvaluationJob  # noqa: E402,F401
