from dataclasses import dataclass

from dmp.experiment.structure.network_module import NetworkModule


@dataclass(frozen=False, eq=False, unsafe_hash=False)
class NInput(NetworkModule):
    pass
