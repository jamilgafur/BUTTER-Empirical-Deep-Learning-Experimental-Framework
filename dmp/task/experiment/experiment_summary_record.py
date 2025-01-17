from dataclasses import dataclass
from typing import Optional
import pandas


@dataclass
class ExperimentSummaryRecord():
    by_epoch: Optional[pandas.DataFrame]
    by_loss: Optional[pandas.DataFrame]
    by_progress: Optional[pandas.DataFrame]
    epoch_subset: Optional[pandas.DataFrame]
