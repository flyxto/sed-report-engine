"""Placeholder for YOUR module's analysis output.

Replace this with your real results type — the `@dataclass` your analysis
engine already produces. The report views only read attributes off this object,
so there's nothing special to implement: your existing results just work.

Hold each utilisation as the float RATIO your analysis computed (1.0 == 100 %),
not as a formatted string or a status: the report builds every label, every
OK/FAIL and the overall pass from the ratios with reporting's util_* helpers.
"""

from dataclasses import dataclass, field


@dataclass
class CapacityCheck:
    name: str
    demand: str      # display string, with units
    capacity: str    # display string, with units
    util: float      # utilisation ratio, 1.0 == 100 %


@dataclass
class EdgeCheck:
    name: str
    m_star: str      # display string (kNm)
    phi_mn: str      # display string (kNm)
    util: float      # utilisation ratio, 1.0 == 100 %


@dataclass
class DemoResults:
    project: str
    reference: str
    system: str
    concrete: str
    checks: list[CapacityCheck] = field(default_factory=list)
    edges: list[EdgeCheck] = field(default_factory=list)

    def worst_edges(self, n: int) -> list[EdgeCheck]:
        return sorted(self.edges, key=lambda e: e.util, reverse=True)[:n]


# A sample instance so `python module_template/report.py` runs out of the box.
SAMPLE = DemoResults(
    project="Demo Dwelling",
    reference="DEMO-001",
    system="ExampleSystem750",
    concrete="25 MPa",
    checks=[
        CapacityCheck("Rib Flexure", "18.4 kNm", "24.1 kNm", 18.4 / 24.1),
        CapacityCheck("Rib Shear", "42.1 kN", "58.3 kN", 42.1 / 58.3),
        CapacityCheck("Deflection", "8.9 mm", "10.0 mm", 8.9 / 10.0),
    ],
    edges=[
        EdgeCheck("E1", "21.6", "21.8", 21.6 / 21.8),
        EdgeCheck("E3", "22.5", "21.8", 22.5 / 21.8),
        EdgeCheck("E7", "20.9", "21.8", 20.9 / 21.8),
        EdgeCheck("E2", "14.1", "21.8", 14.1 / 21.8),
    ],
)
