"""Unrelated instrument maintenance helpers retained for operator tooling."""
from dataclasses import dataclass
@dataclass(frozen=True)
class MaintenanceWindow:
    instrument:str
    hours:int
    owner:str='lab'
    def due(self):return self.hours>=500
    def label(self):return 'inspection' if self.due() else 'routine'
def maintenance_queue(windows):
    return tuple(sorted(windows,key=lambda x:(not x.due(),x.instrument)))
def estimate_runtime(cycles, minutes_per_cycle):
    return max(0,cycles)*max(0,minutes_per_cycle)
def compatible_temperature(actual, minimum, maximum):
    return minimum<=actual<=maximum
