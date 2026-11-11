"""Extensible structural rules. Algorithm names and comments are never inputs."""

from dataclasses import dataclass
from typing import Callable

from intelligence.evidence.function_purpose import DiscoveredFunction, PurposeConclusion


@dataclass(frozen=True)
class PatternRule:
    name: str
    observe: Callable
    conclusion: str


PATTERN_RULES: dict[str, PatternRule] = {}


def register_rule(rule: PatternRule):
    if rule.name in PATTERN_RULES:
        raise ValueError(f"Duplicate pattern rule: {rule.name}")
    PATTERN_RULES[rule.name] = rule


def facts(function, kind):
    return [e for e in function.evidence if e.kind == kind]


def traversal(function, removal):
    evidence = []
    sequences = {e.subject for e in facts(function, "collection_binding") if e.related == "sequence"}
    for take in facts(function, removal):
        if not take.related or take.subject not in sequences:
            continue
        adjacency = [e for e in facts(function, "adjacency_iteration") if e.related == take.related]
        append = [e for e in facts(function, "sequence_append") if e.subject == take.subject
                  and e.related and any(a.binding == e.related for a in adjacency)]
        loops = [e for e in facts(function, "while_loop") if e.subject == take.subject]
        if adjacency and append and loops:
            evidence.extend([take, *adjacency, *append, *loops,
                             *[e for e in facts(function, "collection_binding") if e.subject == take.subject]])
    return evidence


def visited(function):
    evidence = []
    for update in facts(function, "set_add"):
        guards = [e for e in facts(function, "membership_guard") if e.subject == update.subject]
        if guards:
            evidence.extend([update, *guards])
    return evidence


def memoized(function):
    if not facts(function, "direct_recursion"):
        return []
    result = []
    for write in facts(function, "indexed_write"):
        reads = [e for e in facts(function, "indexed_read") if e.subject == write.subject]
        guards = [e for e in facts(function, "membership_guard") if e.subject == write.subject]
        if reads and guards:
            result.extend([write, *reads, *guards, *facts(function, "direct_recursion")])
    return result


def recursive_exploration(function):
    result = []
    for adjacency in facts(function, "adjacency_iteration"):
        calls = [e for e in facts(function, "direct_recursion") if adjacency.binding and adjacency.binding in e.arguments]
        if calls:
            result.extend([adjacency, *calls])
    return result


for rule in [
    PatternRule("fifo_graph_traversal", lambda f: traversal(f, "fifo_remove"),
                "FIFO removal, re-enqueueing and indexed adjacency iteration share lexical bindings; BFS-like structure."),
    PatternRule("lifo_graph_exploration", lambda f: traversal(f, "lifo_remove"),
                "LIFO removal and indexed adjacency exploration share lexical bindings; DFS-like structure."),
    PatternRule("visited_set_tracking", visited, "A set-like receiver is checked for membership and updated."),
    PatternRule("recursion", lambda f: facts(f, "direct_recursion"), "The body contains a lexical self-call; runtime recursion is not established."),
    PatternRule("recursive_graph_exploration", recursive_exploration,
                "Indexed adjacency iteration occurs alongside a lexical self-call; recursive exploration is plausible."),
    PatternRule("priority_queue_operations", lambda f: facts(f, "heap_operation"), "Calls resolve syntactically through a heapq import; heap operations are indicated."),
    PatternRule("sorting_operations", lambda f: facts(f, "sorting_call"), "A sorted/sort call is present; runtime dispatch and ordering semantics remain unverified."),
    PatternRule("collection_filtering", lambda f: facts(f, "filtering_call") + facts(f, "filtering_comprehension"),
                "Filtering call or filtered comprehension syntax is present."),
    PatternRule("collection_search", lambda f: facts(f, "searching_call") + (
        facts(f, "conditional_return") if facts(f, "iteration") else []),
        "Search-like calls or conditional returns within an iterative function are present."),
    PatternRule("collection_accumulation", lambda f: facts(f, "aggregation_call") + (
        [e for e in facts(f, "accumulator_update") if any(r.subject == e.subject for r in facts(f, "return_value"))]
        if facts(f, "iteration") else []), "Reduction or accumulation syntax is present."),
    PatternRule("memoized_recursion", memoized,
                "Guarded table reads/writes accompany recursion; memoization is plausible, but DP subproblem semantics are unknown."),
]:
    register_rule(rule)


def resolve(function: DiscoveredFunction) -> DiscoveredFunction:
    function.detected_patterns = []
    for rule in PATTERN_RULES.values():
        evidence = rule.observe(function)
        if evidence:
            function.detected_patterns.append(PurposeConclusion(
                kind=rule.name, status="INFERRED", evidence_refs=list(dict.fromkeys(e.id for e in evidence)),
                supported_conclusion=rule.conclusion, source_revision=function.source_revision,
                missing_information=["Runtime value types and dispatch are not proven by syntax."],
            ))
    patterns = {p.kind: p for p in function.detected_patterns}
    hypotheses = []

    def hypothesis(kind, names, explanation, extra=()):
        refs = [ref for name in names if name in patterns for ref in patterns[name].evidence_refs]
        refs += [e.id for e in extra]
        hypotheses.append(PurposeConclusion(
            kind=kind, status="INFERRED", evidence_refs=list(dict.fromkeys(refs)),
            source_revision=function.source_revision, supported_conclusion=explanation,
            missing_information=["No authoritative function contract has been verified.",
                                 "Behavior on uninspected inputs and external call targets is unknown."],
        ))

    graph_patterns = [name for name in ("fifo_graph_traversal", "lifo_graph_exploration", "recursive_graph_exploration") if name in patterns]
    if graph_patterns:
        neighbors = {e.binding for e in facts(function, "adjacency_iteration") if e.binding}
        tracked = {e.subject for e in facts(function, "set_add") if e.related in neighbors
                   and any(g.subject == e.subject and g.related == e.related for g in facts(function, "membership_guard"))}
        if "recursive_graph_exploration" in graph_patterns:
            for update in facts(function, "set_add"):
                for adjacency in facts(function, "adjacency_iteration"):
                    if update.related == adjacency.related and any(
                        g.subject == update.subject and g.related == adjacency.binding
                        for g in facts(function, "membership_guard")
                    ) and any(update.subject in call.arguments and adjacency.binding in call.arguments
                              for call in facts(function, "direct_recursion")):
                        tracked.add(update.subject)
        returned = [e for e in facts(function, "return_value") if e.subject in tracked]
        if "visited_set_tracking" in patterns and returned:
            hypothesis("graph_reachability", graph_patterns + ["visited_set_tracking"],
                       "Exploration returns the tracked membership collection; reachable-node collection is a plausible purpose.", returned)
        else:
            hypothesis("graph_traversal", graph_patterns, "The function appears to explore indexed adjacency data; its required output is not established.")
    if "sorting_operations" in patterns:
        hypothesis("collection_ordering", ["sorting_operations"], "Ordering a collection appears to be one operation; required ordering and task scope remain unknown.")
    if "collection_filtering" in patterns:
        hypothesis("collection_filtering", ["collection_filtering"], "Selecting a subset by a predicate is a plausible operation.")
    if "collection_search" in patterns and not graph_patterns:
        hypothesis("collection_search_or_selection", ["collection_search"], "Searching, testing or selecting matching values are plausible interpretations.")
    if "collection_accumulation" in patterns:
        hypothesis("collection_aggregation", ["collection_accumulation"], "Combining values into an accumulated result is a plausible purpose.")
    function.task_hypotheses = hypotheses
    function.task_status = "AMBIGUOUS" if len(hypotheses) > 1 else "INFERRED" if hypotheses else "UNKNOWN"
    function.possible_task = hypotheses[0].kind if len(hypotheses) == 1 else None
    function.uncertainty = [
        "No authoritative contract is bound to this source hash; inferred purpose is not a functional requirement.",
        "Names, comments and type annotations do not prove behavior; dynamic calls, aliases and rebinding remain unresolved.",
    ]
    if not hypotheses:
        function.uncertainty.append("Structural metadata is available, but supported rules do not establish a computational task.")
    if len(hypotheses) > 1:
        function.uncertainty.append("Several operations are plausible; their role in the function's overall task is not established.")
    if not function.source_revision:
        function.uncertainty.append("Commit revision was not supplied; only the source-content hash is established.")
    if not function.callers:
        function.uncertainty.append("No caller was linked in the inspected snapshot; external callers may exist.")
    if not function.requirement_evidence_refs:
        function.uncertainty.append("No matching static test expectation was linked in the inspected snapshot.")
    return function
