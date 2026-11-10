"""Tests of routing2.net_rules that need no SUMO or data files. Success prints NET_RULES_TESTS_OK."""

from __future__ import annotations

from .net_rules import active, axis_groups, clusters, largest_scc, split_bans, two_axis_phases


def test_active() -> None:
    w = "06:00-09:00,16:00-19:00"
    assert active(None, "03:00")
    assert active(w, "06:00") and active(w, "08:59") and active(w, "16:30")
    assert not active(w, "09:00") and not active(w, "12:00") and not active(w, "19:00")


def ban(osm, f, t, when=None, moto=True, car=True) -> dict:
    return {"osm": osm, "kind": "no_left_turn", "when": when, "binds": {"motorcycle": moto, "car": car}, "from": f, "to": t}


def test_split() -> None:
    succ = {"a": {"b"}, "b": {"c"}, "x": {"y"}, "p": {"q"}}
    bans = [
        ban(1, ["a"], ["b"]),  # binds all: physically removed
        ban(2, ["x"], ["y"], moto=False),  # cars only: route level
        ban(3, ["a", "b"], ["b", "c"], moto=False),  # a -> b -> c, listed as in via-way records
        ban(4, ["p"], ["q"], when="17:00-19:00"),  # not in force at 08:00
        ban(5, ["p"], ["z"]),  # no such connection
    ]
    s = split_bans(bans, "08:00", succ)
    assert s["delete"] == {("a", "b")}
    assert s["car_pairs"] == {("x", "y")}
    assert s["chains"][0]["links"] == ["a", "b", "c"]
    assert s["inactive"] == [4] and s["no_link"] == [5] and not s["unhandled"]
    assert ("p", "q") in split_bans(bans, "17:30", succ)["delete"]


def test_axes() -> None:
    g = axis_groups({"n": 2.0, "s": 183.0, "e": 91.0, "w": 268.0})
    assert g["n"] == g["s"] != g["e"] == g["w"]
    assert len(set(axis_groups({"a": 10.0, "b": 190.0}).values())) == 1


def test_phases() -> None:
    links = [{"from": "n", "dir": "s"}, {"from": "n", "dir": "l"}, {"from": "e", "dir": "s"}, {"from": "inside", "dir": "s"}]
    p = two_axis_phases(links, {"n": 0, "e": 1}, 83)
    assert sum(d for d, _ in p) == 83
    assert [s for _, s in p] == ["GgrG", "yyrG", "rrGG", "rryG"]
    assert abs(p[0][0] - p[2][0]) <= 1
    assert sum(d for d, _ in two_axis_phases(links, {"n": 0, "e": 1}, 183.5)) == round(183.5)
    try:
        two_axis_phases(links, {}, 5)
    except ValueError:
        return
    raise AssertionError("too short a cycle must be rejected")


def test_clusters() -> None:
    c = clusters({"a": (106.7, 10.75), "b": (106.7001, 10.75), "z": (106.71, 10.75)}, 40.0)
    assert c["a"] == c["b"] != c["z"]


def test_scc() -> None:
    assert largest_scc({"a": {"b"}, "b": {"a", "c"}}) == 2


def main() -> None:
    test_active()
    test_split()
    test_axes()
    test_phases()
    test_clusters()
    test_scc()
    print("NET_RULES_TESTS_OK")


if __name__ == "__main__":
    main()
