from benchmarks.models import PluginRole
from benchmarks.topologies import (build, build_fanout_fanin, build_layered_diamond,
                                   build_linear)


def _by_key(topo):
    return {n.key: n for n in topo.nodes}


def test_linear_shape_and_chain():
    topo = build_linear(depth=3, file_count=5, file_size="1KiB")
    assert topo.kind == "linear"
    assert len(topo.nodes) == 4              # root + 3 ds
    assert topo.nodes[0].role is PluginRole.FS
    assert topo.nodes[0].parents == ()
    # each ds chains to the previous node
    assert topo.nodes[1].parents == ("root",)
    assert topo.nodes[2].parents == ("ds0",)
    assert topo.nodes[3].parents == ("ds1",)
    assert all(n.role is PluginRole.DS for n in topo.nodes[1:])


def test_linear_root_encodes_file_count():
    topo = build_linear(depth=1, file_count=10, file_size="1KiB")
    assert topo.nodes[0].params == {"total": "10240B", "size": "1024B"}


def test_fanout_fanin_shape():
    topo = build_fanout_fanin(branches=4, file_count=1, file_size="1KiB")
    nodes = _by_key(topo)
    assert len(topo.nodes) == 1 + 4 + 1      # root + 4 branches + 1 merge
    merge = nodes["merge0"]
    assert merge.role is PluginRole.TS
    assert set(merge.parents) == {"b0", "b1", "b2", "b3"}
    assert all(nodes[f"b{i}"].parents == ("root",) for i in range(4))


def test_sleep_length_emits_integer_string_for_integral_values():
    # simpledsapp does time.sleep(int(v)) — "60.0" would crash the plugin
    topo = build_linear(depth=1, file_count=1, file_size="1KiB", sleep_length=60.0)
    assert topo.nodes[1].params["sleepLength"] == "60"
    topo = build_linear(depth=1, file_count=1, file_size="1KiB", sleep_length=0.0)
    assert "sleepLength" not in topo.nodes[1].params


def test_merge_runs_with_group_by_instance():
    # the usual way pl-topologicalcopy is run; also keeps same-named files from
    # sibling branches from colliding in the merged output
    topo = build_fanout_fanin(branches=2, file_count=1, file_size="1KiB")
    merge = _by_key(topo)["merge0"]
    assert merge.params == {"filter": ".*", "groupByInstance": True}


def test_fanout_multiple_merges():
    topo = build_fanout_fanin(branches=2, file_count=1, file_size="1KiB", merges=3)
    merges = [n for n in topo.nodes if n.role is PluginRole.TS]
    assert len(merges) == 3
    assert all(set(m.parents) == {"b0", "b1"} for m in merges)


def test_diamond_layers_linkage():
    topo = build_layered_diamond(branches=2, layers=2, file_count=1, file_size="1KiB")
    nodes = _by_key(topo)
    # root + layers * (branches + 1 merge)
    assert len(topo.nodes) == 1 + 2 * (2 + 1)
    # layer 0 branches hang off root; layer 1 branches hang off merge0
    assert nodes["l0b0"].parents == ("root",)
    assert nodes["l1b0"].parents == ("merge0",)
    assert set(nodes["merge1"].parents) == {"l1b0", "l1b1"}


def test_topological_order_parents_precede_children():
    topo = build_layered_diamond(branches=3, layers=2, file_count=2, file_size="1KiB")
    seen: set[str] = set()
    for node in topo.nodes:
        assert all(p in seen for p in node.parents), f"{node.key} before its parents"
        seen.add(node.key)


def test_build_dispatch():
    class P:
        depth = branches = layers = merges = 2
        file_count = 1
        file_size = "1KiB"
        sleep_length = 0
    assert build("linear", P()).kind == "linear"
    assert build("fanout_fanin", P()).kind == "fanout_fanin"
    assert build("diamond", P()).kind == "diamond"
