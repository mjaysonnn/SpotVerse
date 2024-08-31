from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class FileType(Enum):
    """
    Enum for the file type. -> Complete or Interruption (from bucket)
    """
    COMPLETE = 'complete'
    INTERRUPTION = 'interruption'


@dataclass
class Instance:
    """
    Dataclass for the instance.
    """
    start_time: datetime
    end_time: datetime
    availability_zone: str
    cost_per_hour: float
    completion_hours: float
    total_cost: float
