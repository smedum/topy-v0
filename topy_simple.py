# topy_simple.py - Complete Topy Kernel in One File
import copy
from typing import Dict, List, Tuple, Any, Optional
from abc import ABC, abstractmethod
import networkx as nx

# --- Kernel Core ---
class TopyContractViolation(Exception):
    pass

class Invariants:
    def __init__(self, betti: Optional[Dict[str, int]] = None):
        self.betti = betti or {"β0": 1, "β1": 0, "β2": 0}
    def copy(self):
        return Invariants(betti=copy.deepcopy(self.betti))
    def apply_deltas(self, deltas: Dict[str, Dict[str, int]]):
        out = self.copy()
        for inv_group, kv in deltas.items():
            if inv_group == "betti":
                for k, dv in kv.items():
                    out.betti[k] = out.betti.get(k, 0) + dv
        return out
    def __repr__(self):
        return f"Invariants(betti={self.betti})"

class Carrier(ABC):
    @abstractmethod
    def measure_invariants(self) -> Invariants: pass
    @abstractmethod
    def clone(self): pass

class GraphCarrier(Carrier):
    def __init__(self, G: Optional[nx.Graph] = None):
        self.G = G if G is not None else nx.Graph()
    def measure_invariants(self) -> Invariants:
        n, m = self.G.number_of_nodes(), self.G.number_of_edges()
        c = nx.number_connected_components(self.G)
        return Invariants(betti={"β0": c, "β1": m - n + c, "β2": 0})
    def clone(self):
        return GraphCarrier(G=self.G.copy())
    def __repr__(self):
        n, m, c = self.G.number_of_nodes(), self.G.number_of_edges(), nx.number_connected_components(self.G)
        return f"GraphCarrier(n={n}, m={m}, cc={c})"

class Operator(ABC):
    name: str = "Operator"
    requires_geometric_realization: bool = False
    force_measure: bool = False
    def __init__(self, parameters: Dict[str, Any]):
        self.parameters = parameters
    @abstractmethod
    def algebraic_effect(self, current: Invariants, carrier: Carrier) -> Dict[str, Dict[str, int]]: pass
    @abstractmethod
    def verify_contract(self, current: Invariants, deltas: Dict[str, Dict[str, int]], constraints: Dict[str, Any], carrier: Carrier) -> bool: pass
    @abstractmethod
    def realize_geometrically(self, carrier: Carrier) -> Carrier: pass

class I_AddCycleRedundancy(Operator):
    name = "I_AddCycleRedundancy"
    requires_geometric_realization = True
    force_measure = True
    def algebraic_effect(self, current: Invariants, carrier: GraphCarrier) -> Dict[str, Dict[str, int]]:
        edges, comp_index = self.parameters.get("edges", []), {}
        for i, comp in enumerate(nx.connected_components(carrier.G)):
            for v in comp: comp_index[v] = i
        delta_beta1, delta_beta0 = 0, 0
        for u, v in edges:
            cu, cv = comp_index.get(u), comp_index.get(v)
            if cu is not None and cv is not None:
                if cu == cv: delta_beta1 += 1
                else: delta_beta0 -= 1
        return {"betti": {"β1": delta_beta1, "β0": delta_beta0}}
    def verify_contract(self, current: Invariants, deltas: Dict[str, Dict[str, int]], constraints: Dict[str, Any], carrier: GraphCarrier) -> bool:
        if deltas["betti"]["β1"] < 0: return False
        max_b1 = constraints.get("max_betti1", float("inf"))
        return (current.betti["β1"] + deltas["betti"]["β1"]) <= max_b1
    def realize_geometrically(self, carrier: GraphCarrier) -> GraphCarrier:
        G = carrier.G
        for u, v in self.parameters.get("edges", []):
            if u not in G: G.add_node(u)
            if v not in G: G.add_node(v)
        G.add_edges_from(self.parameters.get("edges", []))
        return carrier

class I_CalculateH1Graph(Operator):
    name = "I_CalculateH1Graph"
    requires_geometric_realization = False
    force_measure = True
    def algebraic_effect(self, current: Invariants, carrier: Carrier) -> Dict[str, Dict[str, int]]:
        return {}
    def verify_contract(self, current: Invariants, deltas: Dict[str, Dict[str, int]], constraints: Dict[str, Any], carrier: Carrier) -> bool:
        return True
    def realize_geometrically(self, carrier: Carrier) -> Carrier:
        return carrier

class TopyKernel:
    def __init__(self, carrier: Carrier):
        self.carrier = carrier
        self.invariants = self.carrier.measure_invariants()
        self.log: List[Tuple[str, Dict[str, Any]]] = []
    def execute(self, operator_spec: List[Operator], constraints: Dict[str, Any]):
        for op in operator_spec:
            deltas = op.algebraic_effect(self.invariants, self.carrier)
            if not op.verify_contract(self.invariants, deltas, constraints, self.carrier):
                raise TopyContractViolation(f"Operator {op.name} violated constraints with deltas {deltas}")
            self.invariants = self.invariants.apply_deltas(deltas)
            if op.requires_geometric_realization:
                self.carrier = op.realize_geometrically(self.carrier)
            if op.force_measure:
                measured = self.carrier.measure_invariants()
                if measured.betti != self.invariants.betti:
                    self.invariants = measured
            self.log.append((op.name, {"parameters": op.parameters, "deltas": deltas}))

# --- Demo & Test ---
if __name__ == "__main__":
    # This part runs the demo
    G0 = nx.path_graph(4)
    kernel = TopyKernel(GraphCarrier(G0))
    print("Initial state:", kernel.carrier)
    print("Initial invariants:", kernel.invariants)
    ops = [I_AddCycleRedundancy({"edges": [(0, 3)]}), I_CalculateH1Graph({})]
    try:
        kernel.execute(ops, {"max_betti1": 3})
        print("\n✅ Success! Final invariants:", kernel.invariants)
        print("Log:", kernel.log)
    except TopyContractViolation as e:
        print("\n❌ Design failed:", e)
