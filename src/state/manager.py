"""State management with SQLAlchemy."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Enum as SQLEnum, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings

Base = declarative_base()


class TaskStatus(str, Enum):
    """Task status enum."""

    PLANNED = "planned"
    DISPATCHED = "dispatched"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class WorkflowState(Base):
    """Workflow state table."""

    __tablename__ = "workflow_states"

    id = Column(Integer, primary_key=True)
    workflow_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PLANNED)
    original_task = Column(Text, nullable=False)
    current_iteration = Column(Integer, default=0)
    max_iterations = Column(Integer, default=100)
    context = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SubtaskState(Base):
    """Subtask state table."""

    __tablename__ = "subtask_states"

    id = Column(Integer, primary_key=True)
    workflow_id = Column(String(100), nullable=False, index=True)
    subtask_id = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PLANNED)
    result = Column(Text)
    error = Column(Text)
    retry_count = Column(Integer, default=0)
    executor = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckpointState(Base):
    """Checkpoint state table."""

    __tablename__ = "checkpoint_states"

    id = Column(Integer, primary_key=True)
    workflow_id = Column(String(100), nullable=False, index=True)
    checkpoint_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class StateManager:
    """Manage workflow and task state."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self):
        """Get database session."""
        return self.SessionLocal()

    def create_workflow(self, workflow_id: str, original_task: str, max_iterations: int = 100):
        """Create a new workflow."""
        with self.get_session() as session:
            workflow = WorkflowState(
                workflow_id=workflow_id,
                original_task=original_task,
                max_iterations=max_iterations,
                status=TaskStatus.PLANNED,
            )
            session.add(workflow)
            session.commit()
            return workflow

    def update_workflow_status(self, workflow_id: str, status: TaskStatus):
        """Update workflow status."""
        with self.get_session() as session:
            workflow = (
                session.query(WorkflowState).filter_by(workflow_id=workflow_id).first()
            )
            if workflow:
                workflow.status = status
                workflow.updated_at = datetime.utcnow()
                session.commit()

    def increment_iteration(self, workflow_id: str):
        """Increment workflow iteration count."""
        with self.get_session() as session:
            workflow = (
                session.query(WorkflowState).filter_by(workflow_id=workflow_id).first()
            )
            if workflow:
                workflow.current_iteration += 1
                workflow.updated_at = datetime.utcnow()
                session.commit()
                return workflow.current_iteration
            return 0

    def create_subtask(
        self, workflow_id: str, subtask_id: str, description: str
    ):
        """Create a new subtask."""
        with self.get_session() as session:
            subtask = SubtaskState(
                workflow_id=workflow_id,
                subtask_id=subtask_id,
                description=description,
                status=TaskStatus.PLANNED,
            )
            session.add(subtask)
            session.commit()
            return subtask

    def update_subtask_status(
        self,
        workflow_id: str,
        subtask_id: str,
        status: TaskStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
        executor: Optional[str] = None,
    ):
        """Update subtask status."""
        with self.get_session() as session:
            subtask = (
                session.query(SubtaskState)
                .filter_by(workflow_id=workflow_id, subtask_id=subtask_id)
                .first()
            )
            if subtask:
                subtask.status = status
                if result:
                    subtask.result = result
                if error:
                    subtask.error = error
                if executor:
                    subtask.executor = executor
                subtask.updated_at = datetime.utcnow()
                session.commit()

    def get_workflow(self, workflow_id: str):
        """Get workflow state."""
        with self.get_session() as session:
            return session.query(WorkflowState).filter_by(workflow_id=workflow_id).first()

    def get_subtasks(self, workflow_id: str):
        """Get all subtasks for a workflow."""
        with self.get_session() as session:
            return session.query(SubtaskState).filter_by(workflow_id=workflow_id).all()

    def create_checkpoint(self, workflow_id: str, checkpoint_data: dict):
        """Create a checkpoint."""
        with self.get_session() as session:
            checkpoint = CheckpointState(
                workflow_id=workflow_id,
                checkpoint_data=checkpoint_data,
            )
            session.add(checkpoint)
            session.commit()

    def get_latest_checkpoint(self, workflow_id: str):
        """Get the latest checkpoint."""
        with self.get_session() as session:
            return (
                session.query(CheckpointState)
                .filter_by(workflow_id=workflow_id)
                .order_by(CheckpointState.created_at.desc())
                .first()
            )
