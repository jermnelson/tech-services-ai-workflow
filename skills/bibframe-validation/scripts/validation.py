"""Validate BIBFRAME Work/Instance RDF against the BIBFRAME Interoperability SHACL shapes.

Port of https://github.com/bf-interop/bf-demo-validation-tool
(`src/bf_demo_validation_tool/validation.py` + `data.py`) from Pyodide/DOM to a CLI.
The pyshacl call and the shape-summary SPARQL are kept as they are upstream; the `js`
document manipulation is replaced with printing, and the shapes graph is built from this
skill's local `assets/*.ttl` instead of Sinopia JSON-LD URLs.

Usage:
    uv run python .claude/skills/bibframe-validation/scripts/validation.py a13616108
    uv run python .../validation.py a13616108 --summarize
"""

import argparse
import pathlib
import sys

import pyshacl
import rdflib

BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
BFLC = rdflib.Namespace("http://id.loc.gov/ontologies/bflc/")
SHACL = rdflib.Namespace("http://www.w3.org/ns/shacl#")

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"

# The BIG shapes select focus nodes by sh:targetClass, so every shape file for a given
# resource kind can be merged into one graph -- only the shapes whose target classes are
# actually present in the data will fire. Nothing has to be picked by mode of issuance.
# The record-level shapes target genre/carrier classes, not bf:Work / bf:Instance. If the
# graph carries none of these types, the top-level shape never fires and only the nested
# component shapes (Title, Agent, AdminMetadata...) are actually checked.
RECORD_TARGETS = {
    "work": [BF.Monograph, BF.Serial, BF.Text],
    "instance": [BF.Print, BF.Electronic],
}

SHAPE_SETS = {
    "work": ["work-monograph-text.ttl", "work-serial-text.ttl", "admin-metadata.ttl"],
    "instance": [
        "instance-monograph-text.ttl",
        "instance-serial-electronic.ttl",
        "admin-metadata.ttl",
    ],
}


def _bind_namespaces(graph: rdflib.Graph):
    graph.namespace_manager.bind("bf", BF)
    graph.namespace_manager.bind("bflc", BFLC)
    graph.namespace_manager.bind("sh", SHACL)


def init_shacl_graph(shacl_files: list) -> rdflib.Graph:
    """Initialize SHACL Graph from local turtle assets."""
    shacl_graph = rdflib.Graph()
    _bind_namespaces(shacl_graph)
    for name in shacl_files:
        shacl_graph.parse(ASSETS / name, format="turtle")
    return shacl_graph


def build_incoming_graph(rdf_path: pathlib.Path) -> rdflib.Graph:
    """Builds RDF from a local file, guessing the parser from the extension."""
    incoming_graph = rdflib.Graph()
    _bind_namespaces(incoming_graph)
    rdf_type = rdflib.util.guess_format(str(rdf_path))
    incoming_graph.parse(rdf_path, format=rdf_type)
    return incoming_graph


def _shape_properties(validation_graph: rdflib.Graph, shape_id) -> dict:
    """Port of _add_shape's property collection, minus the DOM building."""
    properties = {}
    for obj in validation_graph.objects(subject=shape_id, predicate=SHACL.property):
        path = validation_graph.value(subject=obj, predicate=SHACL.path)
        path_key = str(path)
        if path_key not in properties:
            properties[path_key] = [("path", str(path))]
        min_count = validation_graph.value(subject=obj, predicate=SHACL.minCount)
        if min_count:
            properties[path_key].append(("miniumum count", int(min_count)))
        pattern = validation_graph.value(subject=obj, predicate=SHACL.pattern)
        if pattern:
            properties[path_key].append(("regular expression pattern", str(pattern)))
    return properties


def summarize(current_shacl: rdflib.Graph) -> dict:
    """Node shapes in the shapes graph, keyed by shape IRI, with their target classes."""
    shapes = {}
    for row in current_shacl.query(
        """PREFIX sh: <http://www.w3.org/ns/shacl#>
    SELECT ?node_shape ?label ?target
    WHERE { ?node_shape a sh:NodeShape .
            ?node_shape rdfs:label ?label .
            ?node_shape sh:targetClass ?target .}
    ORDER BY ?label """
    ):
        key = str(row[0])
        if key not in shapes:
            shapes[key] = {"id": row[0], "label": str(row[1]), "targets": [row[2]]}
            continue
        shapes[key]["targets"].append(row[2])
    return shapes


def print_summary(current_shacl: rdflib.Graph):
    shapes = summarize(current_shacl)
    print(f"  {len(current_shacl)} triples from {len(shapes)} SHACL Resources")
    for shape in shapes.values():
        targets = ", ".join(current_shacl.qname(t) for t in shape["targets"])
        print(f"  - {shape['label']} -> {targets}")
        for values in _shape_properties(current_shacl, shape["id"]).values():
            print("      " + "; ".join(f"{k}: {v}" for k, v in values))


def focus_node_count(graph: rdflib.Graph, shacl_graph: rdflib.Graph) -> int:
    """How many nodes in `graph` any sh:targetClass in `shacl_graph` actually selects.

    pyshacl reports conforms=True when a shapes graph selects no focus nodes at all, so a
    zero here means the pass is vacuous rather than earned.
    """
    targets = set(shacl_graph.objects(predicate=SHACL.targetClass))
    return len({s for t in targets for s in graph.subjects(rdflib.RDF.type, t)})


def record_shape_fired(graph: rdflib.Graph, kind: str) -> bool:
    """Whether the record-level (Work/Instance) shape has a focus node to attach to."""
    return any(
        (None, rdflib.RDF.type, cls) in graph for cls in RECORD_TARGETS[kind]
    )


def validate(
    incoming_graph: rdflib.Graph, validation_graph: rdflib.Graph, label: str, kind: str
) -> bool:
    if len(incoming_graph) < 1:
        print(f"{label}: empty graph, nothing to validate")
        return False

    conforms, _results_graph, results_text = pyshacl.validate(
        incoming_graph, shacl_graph=validation_graph, allow_warnings=True
    )
    status = "Passed!!" if conforms else "Failed!"
    focus = focus_node_count(incoming_graph, validation_graph)
    print(f"{label} with {len(incoming_graph)} triples {status}")
    print(f"  {focus} focus node(s) selected by sh:targetClass")
    match focus:
        case 0:
            print("  WARNING: no focus nodes -- this is a vacuous pass, not a validated record")
        case _:
            if not record_shape_fired(incoming_graph, kind):
                wanted = ", ".join(incoming_graph.qname(c) for c in RECORD_TARGETS[kind])
                print(f"  WARNING: record-level {kind} shape did not fire -- the graph is typed only "
                      f"bf:{kind.title()} and carries none of {wanted}, so only nested component "
                      "shapes were checked")
    print(results_text.rstrip())
    return conforms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hrid", help="FOLIO HRID, or a path ending in one (output/a13616108)")
    parser.add_argument(
        "--output-dir", default="output", help="parent of the {hrid} directory (default: output)"
    )
    parser.add_argument(
        "--summarize", action="store_true", help="also print the loaded SHACL shape summary"
    )
    args = parser.parse_args()

    hrid = pathlib.PurePath(args.hrid).name
    record_dir = pathlib.Path(args.output_dir) / hrid
    if not record_dir.is_dir():
        sys.exit(f"No such directory: {record_dir}")

    all_conform = True
    for kind in ("work", "instance"):
        rdf_path = record_dir / f"bf_{kind}.ttl"
        if not rdf_path.exists():
            rdf_path = record_dir / f"bf_{kind}.jsonld"
        if not rdf_path.exists():
            sys.exit(f"No bf_{kind}.ttl or bf_{kind}.jsonld in {record_dir} -- "
                     "run the bibframe-transformation skill first")

        shacl_graph = init_shacl_graph(SHAPE_SETS[kind])
        if args.summarize:
            print(f"== {kind} shapes")
            print_summary(shacl_graph)
        print(f"== {rdf_path}")
        all_conform &= validate(
            build_incoming_graph(rdf_path), shacl_graph, rdf_path.name, kind
        )
        print()

    sys.exit(0 if all_conform else 1)


if __name__ == "__main__":
    main()
