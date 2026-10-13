from dataclasses import dataclass
@dataclass(frozen=True)
class InstrumentStatus:
 serial:str
 cycles:int
 def due(self): return self.cycles>=10000
