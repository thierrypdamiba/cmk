from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field


class Gate(str, Enum):
    behavioral = "behavioral"
    relational = "relational"
    epistemic = "epistemic"
    promissory = "promissory"
    correction = "correction"
    checkpoint = "checkpoint"  # journal-only: session snapshots
    digest = "digest"          # journal-only: consolidated weekly digests
    observation = "observation"  # journal-only: compressed tool output from flow mode

    @classmethod
    def from_str(cls, s: str) -> "Gate | None":
        try:
            return cls(s.lower())
        except ValueError:
            return None


class DecayClass(str, Enum):
    never = "never"        # commitments, 0 decay
    slow = "slow"          # people, 180d half-life
    moderate = "moderate"  # learnings, 90d half-life
    fast = "fast"          # context decisions, 30d half-life

    def half_life_days(self) -> float | None:
        return {
            DecayClass.never: None,
            DecayClass.slow: 180.0,
            DecayClass.moderate: 90.0,
            DecayClass.fast: 30.0,
        }[self]

    @classmethod
    def from_gate(cls, gate: Gate) -> "DecayClass":
        return {
            Gate.promissory: cls.never,
            Gate.relational: cls.slow,
            Gate.epistemic: cls.moderate,
            Gate.behavioral: cls.fast,
            Gate.correction: cls.moderate,
            Gate.checkpoint: cls.fast,
            Gate.digest: cls.moderate,
            Gate.observation: cls.fast,
        }[gate]


class Visibility(str, Enum):
    private = "private"
    team = "team"


class Memory(BaseModel):
    id: str
    created: datetime
    gate: Gate
    person: str | None = None
    project: str | None = None
    confidence: float = 0.9
    last_accessed: datetime
    access_count: int = 1
    decay_class: DecayClass
    content: str
    pinned: bool = False
    sensitivity: str | None = None
    sensitivity_reason: str | None = None
    visibility: Visibility = Visibility.private
    team_id: str | None = None
    created_by: str | None = None


class JournalEntry(BaseModel):
    timestamp: datetime
    gate: Gate
    content: str
    person: str | None = None
    project: str | None = None


class IdentityCard(BaseModel):
    person: str | None = None
    project: str | None = None
    content: str
    last_updated: datetime


class SearchResult(BaseModel):
    memory: Memory
    score: float
    source: str


class ExtractedMemory(BaseModel):
    gate: str
    content: str
    person: str | None = None
    project: str | None = None
