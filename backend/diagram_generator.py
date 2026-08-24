import ast
import re
from collections import defaultdict
from typing import Dict, Any, Set
from indexer import get_all_chunks, get_file_content, DB_PATH


def categorize_file(file_path: str) -> str:
    """Assign a file to an architecture layer based on its name."""
    name = file_path.split("/")[-1].lower()
    if name in ("api.py", "__init__.py", "main.py", "applications.py", "routing.py"):
        return "Entry & API Layer"
    elif name in ("models.py", "cookies.py", "params.py", "datastructures.py"):
        return "Data Layer"
    elif name in ("_internal_utils.py", "_types.py", "compat.py", "help.py", "exceptions.py"):
        return "Utilities"
    else:
        return "Core Logic & Services"


# One palette per layer, matching the interface accent colours. Fills are
# translucent via 8-digit hex so the boxes float over the dark background
# instead of sitting on it as blocks of solid colour.
# (Do NOT use rgba() -- its commas break the Mermaid classDef parser.)
LAYER_STYLES = {
    "Entry & API Layer":     {"class": "entryLayer", "fill": "#38bdf826", "stroke": "#38bdf8", "text": "#bae6fd"},
    "Core Logic & Services": {"class": "coreLayer",  "fill": "#818cf826", "stroke": "#818cf8", "text": "#c7d2fe"},
    "Data Layer":            {"class": "dataLayer",  "fill": "#34d39926", "stroke": "#34d399", "text": "#a7f3d0"},
    "Utilities":             {"class": "utilLayer",  "fill": "#fbbf2426", "stroke": "#fbbf24", "text": "#fde68a"},
}
LAYER_ORDER = ["Entry & API Layer", "Core Logic & Services", "Data Layer", "Utilities"]


def extract_local_imports(raw_content: str, local_module_names: Set[str]) -> Set[str]:
    """
    Parse a file's real `import` statements with `ast` and return the ones
    pointing at other modules in the same repository.

    Uses actual import semantics rather than regex name-matching, which used to
    count every class's `__init__` method as a link to `__init__.py`.
    """
    referenced = set()
    try:
        tree = ast.parse(raw_content)
    except SyntaxError:
        return referenced

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_module = alias.name.split(".")[0]
                if top_module in local_module_names:
                    referenced.add(top_module)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_module = node.module.split(".")[0]
                if top_module in local_module_names:
                    referenced.add(top_module)
            if node.level and node.level > 0:
                for alias in node.names:
                    if alias.name in local_module_names:
                        referenced.add(alias.name)
    return referenced


def get_architecture_graph(db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Return the diagram's raw data: layers, the files inside them, and the real
    import relationships between those files.

    The client draws the diagram from this, so expanding or collapsing a layer
    redraws instantly without a server round trip, and collapsed layers can be
    merged into a single box to keep the arrows readable.
    """
    chunks = get_all_chunks(db_path)
    if not chunks:
        return {"layers": [], "file_edges": []}

    files = sorted(set(c["file_path"] for c in chunks))
    module_to_file = {f.split("/")[-1].replace(".py", ""): f for f in files}
    local_module_names = set(module_to_file.keys()) - {"__init__"}

    file_edges = []
    for f in files:
        raw_content = get_file_content(f, db_path)
        if not raw_content:
            continue
        for imported_module in extract_local_imports(raw_content, local_module_names):
            target_file = module_to_file[imported_module]
            if target_file != f:
                file_edges.append({"source": f, "target": target_file})

    layers = defaultdict(list)
    for f in files:
        layers[categorize_file(f)].append(f)

    ordered_names = [n for n in LAYER_ORDER if n in layers]
    ordered_names += [n for n in layers if n not in LAYER_ORDER]

    return {
        "layers": [
            {
                "name": name,
                "files": sorted(layers[name]),
                "style": LAYER_STYLES.get(name, LAYER_STYLES["Core Logic & Services"])
            }
            for name in ordered_names
        ],
        "file_edges": file_edges
    }


def generate_architecture_diagram(db_path: str = DB_PATH, max_edges_per_node: int = 4) -> Dict[str, Any]:
    """
    Build a layered Mermaid.js diagram from the real import relationships
    found in the indexed files. The output reflects whichever repository was
    analyzed -- there is no template or canned result.
    """
    chunks = get_all_chunks(db_path)

    if not chunks:
        return {
            "status": "error",
            "message": "Nothing indexed to build a diagram from.",
            "mermaid_code": ""
        }

    files = list(set([c["file_path"] for c in chunks]))
    file_ids = {f: f"Node_{idx}" for idx, f in enumerate(files)}

    # module name (no extension) -> full path. If two files share a basename
    # the last one wins, which is an acceptable limitation here.
    module_to_file = {f.split("/")[-1].replace(".py", ""): f for f in files}
    local_module_names = set(module_to_file.keys()) - {"__init__"}

    edges_by_source = defaultdict(set)
    for f in files:
        raw_content = get_file_content(f, db_path)
        if not raw_content:
            continue
        for imported_module in extract_local_imports(raw_content, local_module_names):
            target_file = module_to_file[imported_module]
            if target_file != f:
                edges_by_source[f].add(target_file)

    final_edges = []
    for source, targets in edges_by_source.items():
        for target in list(targets)[:max_edges_per_node]:
            final_edges.append((source, target))

    layers = defaultdict(list)
    for f in files:
        layers[categorize_file(f)].append(f)

    mermaid_lines = [
        "%%{init: {'flowchart': {'curve': 'basis', 'nodeSpacing': 35, 'rankSpacing': 70, 'htmlLabels': true}}}%%",
        "flowchart TB",
        "    %% Codetrace AI - Auto-Generated Architecture Diagram (from real code relationships)"
    ]

    ordered_layer_names = [name for name in LAYER_ORDER if name in layers]
    ordered_layer_names += [name for name in layers if name not in LAYER_ORDER]

    for layer_name in ordered_layer_names:
        layer_files = sorted(layers[layer_name])
        safe_layer_id = re.sub(r'\W+', '_', layer_name)
        mermaid_lines.append(f'    subgraph {safe_layer_id}["{layer_name}"]')
        mermaid_lines.append("        direction LR")
        for f in layer_files:
            short_name = f.split("/")[-1]
            mermaid_lines.append(f'        {file_ids[f]}("📄 {short_name}")')
        mermaid_lines.append("    end")

    for source, target in final_edges:
        mermaid_lines.append(f"    {file_ids[source]} --> {file_ids[target]}")

    mermaid_lines.append("")
    for layer_name in ordered_layer_names:
        style = LAYER_STYLES.get(layer_name)
        if not style:
            continue
        mermaid_lines.append(
            f"    classDef {style['class']} fill:{style['fill']},stroke:{style['stroke']},"
            f"stroke-width:2px,color:{style['text']},rx:8,ry:8"
        )
        node_list = ",".join(file_ids[f] for f in layers[layer_name])
        mermaid_lines.append(f"    class {node_list} {style['class']}")
        safe_layer_id = re.sub(r'\W+', '_', layer_name)
        mermaid_lines.append(
            f"    style {safe_layer_id} fill:{style['fill']}33,stroke:{style['stroke']},stroke-width:1.5px,color:{style['text']}"
        )

    mermaid_lines.append("    linkStyle default stroke:#64748b,stroke-width:1.5px")

    mermaid_code = "\n".join(mermaid_lines)

    return {
        "status": "success",
        "total_files": len(files),
        "total_relationships": len(final_edges),
        "mermaid_code": mermaid_code
    }


def get_diagram_node_details(db_path: str = DB_PATH, max_children_per_node: int = 8) -> dict:
    """
    Group the indexed chunks by architecture layer for the layer list panel.
    """
    chunks = get_all_chunks(db_path)
    if not chunks:
        return {}

    layers = defaultdict(list)
    for c in chunks:
        layer_name = categorize_file(c["file_path"])
        layers[layer_name].append({
            "name": c["name"],
            "type": c["type"],
            "lines": f"{c['start_line']}-{c['end_line']}",
            "file": c["file_path"]
        })

    result = {}
    for layer_name, items in layers.items():
        result[layer_name] = {
            "label": layer_name,
            "children": items[:max_children_per_node]
        }
    return result


if __name__ == "__main__":
    result = generate_architecture_diagram()
    print(result["mermaid_code"])
