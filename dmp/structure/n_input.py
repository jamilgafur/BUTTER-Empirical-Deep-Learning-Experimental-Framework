from dataclasses import dataclass

from dmp.structure.network_module import NetworkModule


@dataclass(frozen=False, eq=False, unsafe_hash=False)
class NInput(NetworkModule):
    
    @property
    def dimension(self) -> int:
        return len(self.shape)
