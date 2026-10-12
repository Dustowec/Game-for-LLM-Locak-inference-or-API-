"""Тесты для burt/world.py — граф локаций (§17).

Покрывает:
  - константы DIRECTIONS, OPPOSITE, START_NODE_ID, LOCATION_TYPES
  - roll_location_type — расклад типов локаций (1d6 + уточняющий)
  - roll_exit_count — количество выходов (2/3/4)
  - roll_exit_directions — какие направления получают выход
  - link — установка симметричных рёбер
  - create_start_graph — стартовый граф из §37
  - enter_node — генерация содержимого узла при входе

Решения, зафиксированные с пользователем (11.10.2026):
  В1: спереди=north, сзади=south, слева=west, справа=east
  В2: "кустарник" — только восточный сосед старта
  В3: node = {type, entered, exits: {north, east, south, west}}
  В4: граф неориентированный (симметрия рёбер)
  В5: тип/описание — при входе, соседи — при входе
  В6: 2-4 выхода у обычного, 4 у стартовой
  В7: расклад типов по 1d6, вынести в конфиг (пока константа)
  В8: "30 шагов" — ориентир, не инвариант
  В9: A — граф живёт в state.hidden.location_graph
"""
import pytest
from burt import world


# =====================================================================
# Константы
# =====================================================================

class TestConstants:

    def test_directions_order(self):
        assert world.DIRECTIONS == ("north", "east", "south", "west")

    def test_opposite_north_south(self):
        assert world.OPPOSITE["north"] == "south"
        assert world.OPPOSITE["south"] == "north"

    def test_opposite_east_west(self):
        assert world.OPPOSITE["east"] == "west"
        assert world.OPPOSITE["west"] == "east"

    def test_opposite_is_involution(self):
        for d in world.DIRECTIONS:
            assert world.OPPOSITE[world.OPPOSITE[d]] == d

    def test_start_node_id(self):
        assert world.START_NODE_ID == "start"

    def test_location_types_contains_standard(self):
        for t in ("лес", "поле", "степь", "болото", "река",
                  "дорога", "деревня"):
            assert t in world.LOCATION_TYPES

    def test_location_types_contains_rare(self):
        assert "храм" in world.LOCATION_TYPES
        assert "подземелье" in world.LOCATION_TYPES

    def test_location_types_contains_special(self):
        assert "старт" in world.LOCATION_TYPES
        assert "кустарник" in world.LOCATION_TYPES


# =====================================================================
# roll_location_type
# =====================================================================

class TestRollLocationType:

    def test_roll_1_лес(self):
        assert world.roll_location_type(1) == "лес"

    def test_roll_2_лес(self):
        assert world.roll_location_type(2) == "лес"

    def test_roll_3_поле(self):
        assert world.roll_location_type(3) == "поле"

    def test_roll_4_степь(self):
        assert world.roll_location_type(4) == "степь"

    def test_roll_5_size_1_болото(self):
        assert world.roll_location_type(5, 1) == "болото"

    def test_roll_5_size_2_река(self):
        assert world.roll_location_type(5, 2) == "река"

    def test_roll_5_size_3_дорога(self):
        assert world.roll_location_type(5, 3) == "дорога"

    def test_roll_6_size_1_храм(self):
        assert world.roll_location_type(6, 1) == "храм"

    def test_roll_6_size_2_подземелье(self):
        assert world.roll_location_type(6, 2) == "подземелье"

    @pytest.mark.parametrize("roll_size", [3, 4, 5, 6])
    def test_roll_6_size_3_to_6_деревня(self, roll_size):
        assert world.roll_location_type(6, roll_size) == "деревня"

    def test_roll_0_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(0)

    def test_roll_7_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(7)

    def test_roll_5_without_size_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(5)

    def test_roll_6_without_size_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(6)

    def test_roll_5_size_0_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(5, 0)

    def test_roll_5_size_4_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(5, 4)

    def test_roll_6_size_0_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(6, 0)

    def test_roll_6_size_7_raises(self):
        with pytest.raises(ValueError):
            world.roll_location_type(6, 7)

    def test_never_returns_кустарник(self):
        for roll in range(1, 7):
            for size in range(1, 7):
                try:
                    t = world.roll_location_type(roll, size)
                except ValueError:
                    continue
                assert t != "кустарник"

    def test_never_returns_старт(self):
        for roll in range(1, 7):
            for size in range(1, 7):
                try:
                    t = world.roll_location_type(roll, size)
                except ValueError:
                    continue
                assert t != "старт"


# =====================================================================
# roll_exit_count
# =====================================================================

class TestRollExitCount:

    @pytest.mark.parametrize("roll,expected", [
        (1, 2), (2, 2),
        (3, 3), (4, 3),
        (5, 4), (6, 4),
    ])
    def test_count(self, roll, expected):
        assert world.roll_exit_count(roll) == expected

    def test_roll_0_raises(self):
        with pytest.raises(ValueError):
            world.roll_exit_count(0)

    def test_roll_7_raises(self):
        with pytest.raises(ValueError):
            world.roll_exit_count(7)


# =====================================================================
# roll_exit_directions
# =====================================================================

class TestRollExitDirections:

    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_count_4_returns_all_directions(self, roll):
        result = world.roll_exit_directions(4, roll)
        assert result == ("north", "east", "south", "west")

    @pytest.mark.parametrize("roll,expected", [
        (1, ("east", "south", "west")),   # исключён north
        (2, ("north", "south", "west")),  # исключён east
        (3, ("north", "east", "west")),   # исключён south
        (4, ("north", "east", "south")),  # исключён west
        (5, ("east", "south", "west")),   # повтор roll=1
        (6, ("north", "south", "west")),  # повтор roll=2
    ])
    def test_count_3_excludes_one(self, roll, expected):
        assert world.roll_exit_directions(3, roll) == expected

    @pytest.mark.parametrize("roll,expected", [
        (1, ("north", "east")),
        (2, ("north", "south")),
        (3, ("north", "west")),
        (4, ("east", "south")),
        (5, ("east", "west")),
        (6, ("south", "west")),
    ])
    def test_count_2_pairs(self, roll, expected):
        assert world.roll_exit_directions(2, roll) == expected

    def test_count_1_raises(self):
        with pytest.raises(ValueError):
            world.roll_exit_directions(1, 1)

    def test_count_5_raises(self):
        with pytest.raises(ValueError):
            world.roll_exit_directions(5, 1)

    def test_roll_0_raises(self):
        with pytest.raises(ValueError):
            world.roll_exit_directions(2, 0)

    def test_roll_7_raises(self):
        with pytest.raises(ValueError):
            world.roll_exit_directions(2, 7)


# =====================================================================
# link
# =====================================================================

def _empty_node(node_type=None, entered=False):
    return {
        "type": node_type,
        "entered": entered,
        "exits": {"north": None, "east": None,
                  "south": None, "west": None},
    }


class TestLink:

    def _make_graph(self):
        return {
            "a": _empty_node("лес", entered=True),
            "b": _empty_node("поле", entered=False),
            "c": _empty_node("степь", entered=False),
        }

    def test_forward_edge_set(self):
        g = self._make_graph()
        world.link(g, "a", "north", "b")
        assert g["a"]["exits"]["north"] == "b"

    def test_backward_edge_set(self):
        g = self._make_graph()
        world.link(g, "a", "north", "b")
        assert g["b"]["exits"]["south"] == "a"

    def test_east_west_symmetry(self):
        g = self._make_graph()
        world.link(g, "a", "east", "b")
        assert g["a"]["exits"]["east"] == "b"
        assert g["b"]["exits"]["west"] == "a"

    def test_south_north_symmetry(self):
        g = self._make_graph()
        world.link(g, "a", "south", "b")
        assert g["a"]["exits"]["south"] == "b"
        assert g["b"]["exits"]["north"] == "a"

    def test_forward_occupied_raises(self):
        g = self._make_graph()
        g["a"]["exits"]["north"] = "c"
        with pytest.raises(ValueError):
            world.link(g, "a", "north", "b")

    def test_backward_occupied_raises(self):
        g = self._make_graph()
        g["b"]["exits"]["south"] = "c"
        with pytest.raises(ValueError):
            world.link(g, "a", "north", "b")

    def test_invalid_direction_raises(self):
        g = self._make_graph()
        with pytest.raises(ValueError):
            world.link(g, "a", "up", "b")

    def test_unknown_node_raises(self):
        g = self._make_graph()
        with pytest.raises(KeyError):
            world.link(g, "a", "north", "zzz")


# =====================================================================
# create_start_graph
# =====================================================================

class TestCreateStartGraph:

    def test_returns_dict(self):
        g = world.create_start_graph()
        assert isinstance(g, dict)

    def test_has_5_nodes(self):
        g = world.create_start_graph()
        assert len(g) == 5

    def test_start_node_present(self):
        g = world.create_start_graph()
        assert world.START_NODE_ID in g

    def test_start_type(self):
        g = world.create_start_graph()
        assert g[world.START_NODE_ID]["type"] == "старт"

    def test_start_is_entered(self):
        g = world.create_start_graph()
        assert g[world.START_NODE_ID]["entered"] is True

    def test_start_has_4_exits(self):
        g = world.create_start_graph()
        exits = g[world.START_NODE_ID]["exits"]
        for d in world.DIRECTIONS:
            assert exits[d] is not None

    def test_north_is_дорога(self):
        g = world.create_start_graph()
        nid = g[world.START_NODE_ID]["exits"]["north"]
        assert g[nid]["type"] == "дорога"

    def test_east_is_кустарник(self):
        g = world.create_start_graph()
        nid = g[world.START_NODE_ID]["exits"]["east"]
        assert g[nid]["type"] == "кустарник"

    def test_south_is_лес(self):
        g = world.create_start_graph()
        nid = g[world.START_NODE_ID]["exits"]["south"]
        assert g[nid]["type"] == "лес"

    def test_west_is_река(self):
        g = world.create_start_graph()
        nid = g[world.START_NODE_ID]["exits"]["west"]
        assert g[nid]["type"] == "река"

    def test_neighbors_have_back_edge_to_start(self):
        g = world.create_start_graph()
        for d in world.DIRECTIONS:
            nid = g[world.START_NODE_ID]["exits"][d]
            opposite = world.OPPOSITE[d]
            assert g[nid]["exits"][opposite] == world.START_NODE_ID

    def test_neighbors_not_entered(self):
        g = world.create_start_graph()
        for d in world.DIRECTIONS:
            nid = g[world.START_NODE_ID]["exits"][d]
            assert g[nid]["entered"] is False

    def test_neighbors_have_only_back_edge(self):
        g = world.create_start_graph()
        for d in world.DIRECTIONS:
            nid = g[world.START_NODE_ID]["exits"][d]
            non_null = [k for k in world.DIRECTIONS
                        if g[nid]["exits"][k] is not None]
            assert non_null == [world.OPPOSITE[d]]

    def test_all_edges_symmetric(self):
        g = world.create_start_graph()
        for nid, node in g.items():
            for d, target in node["exits"].items():
                if target is not None:
                    assert g[target]["exits"][world.OPPOSITE[d]] == nid

    def test_node_keys(self):
        g = world.create_start_graph()
        for nid, node in g.items():
            assert set(node.keys()) == {"type", "entered", "exits"}

    def test_exits_keys(self):
        g = world.create_start_graph()
        for nid, node in g.items():
            assert set(node["exits"].keys()) == set(world.DIRECTIONS)


# =====================================================================
# enter_node
# =====================================================================

class TestEnterNode:

    def _start_and_north(self):
        g = world.create_start_graph()
        nid = g[world.START_NODE_ID]["exits"]["north"]
        return g, nid

    def test_preserves_preset_type(self):
        g, nid = self._start_and_north()
        world.enter_node(g, nid, roll_count=1, roll_dirs=1)
        assert g[nid]["type"] == "дорога"

    def test_generates_type_if_none(self):
        g = world.create_start_graph()
        # Изолированный пустой узел (без рёбер к старту)
        g["skeleton"] = _empty_node()
        world.enter_node(g, "skeleton", roll_count=1, roll_dirs=1,
                         roll_type=3)
        assert g["skeleton"]["type"] == "поле"

    def test_marks_entered(self):
        g, nid = self._start_and_north()
        assert g[nid]["entered"] is False
        world.enter_node(g, nid, roll_count=1, roll_dirs=1)
        assert g[nid]["entered"] is True

    def test_already_entered_raises(self):
        g = world.create_start_graph()
        with pytest.raises(ValueError):
            world.enter_node(g, world.START_NODE_ID,
                             roll_count=1, roll_dirs=1)

    def test_type_none_without_roll_type_raises(self):
        g = world.create_start_graph()
        g["skeleton"] = _empty_node()
        with pytest.raises(ValueError):
            world.enter_node(g, "skeleton", roll_count=1, roll_dirs=1)

    def test_generates_exits_for_fixed_node(self):
        # north имеет back-ребро south→start.
        # roll_count=1 → n=2, roll_dirs=1 → (north, east).
        # north: свободно → новый сосед.
        # east:  свободно → новый сосед.
        # south: занято start → пропуск.
        g, nid = self._start_and_north()
        world.enter_node(g, nid, roll_count=1, roll_dirs=1)
        exits = g[nid]["exits"]
        assert exits["north"] is not None
        assert exits["east"] is not None
        assert exits["south"] == world.START_NODE_ID
        assert exits["west"] is None

    def test_new_neighbors_are_skeletons(self):
        g, nid = self._start_and_north()
        world.enter_node(g, nid, roll_count=1, roll_dirs=1)
        new_id = g[nid]["exits"]["north"]
        assert g[new_id]["type"] is None
        assert g[new_id]["entered"] is False
        assert g[new_id]["exits"]["south"] == nid

    def test_back_direction_overlap_is_skipped(self):
        # roll_count=3 → n=3, roll_dirs=2 → (N, S, W).
        # N: свободно → новый.
        # S: занято start → пропуск.
        # W: свободно → новый.
        g, nid = self._start_and_north()
        world.enter_node(g, nid, roll_count=3, roll_dirs=2)
        exits = g[nid]["exits"]
        assert exits["south"] == world.START_NODE_ID
        assert exits["north"] is not None
        assert exits["west"] is not None
        assert exits["east"] is None

    def test_symmetry_after_generation(self):
        g, nid = self._start_and_north()
        world.enter_node(g, nid, roll_count=5, roll_dirs=1)
        for node_id, node in g.items():
            for d, target in node["exits"].items():
                if target is not None:
                    assert g[target]["exits"][world.OPPOSITE[d]] == node_id

    @pytest.mark.parametrize("roll_count", [1, 2, 3, 4, 5, 6])
    @pytest.mark.parametrize("roll_dirs", [1, 2, 3, 4, 5, 6])
    def test_total_exits_between_2_and_4(self, roll_count, roll_dirs):
        g, nid = self._start_and_north()
        world.enter_node(g, nid, roll_count=roll_count, roll_dirs=roll_dirs)
        count = sum(1 for k in world.DIRECTIONS
                    if g[nid]["exits"][k] is not None)
        assert 2 <= count <= 4

    def test_walk_two_steps(self):
        g = world.create_start_graph()
        n1 = g[world.START_NODE_ID]["exits"]["north"]
        world.enter_node(g, n1, roll_count=5, roll_dirs=1)  # n=4, все
        assert g[n1]["entered"] is True
        n2 = g[n1]["exits"]["north"]
        assert n2 in g
        assert g[n2]["entered"] is False
        world.enter_node(g, n2, roll_count=3, roll_dirs=1, roll_type=3)
        assert g[n2]["type"] == "поле"
        assert g[n2]["entered"] is True

    def test_node_count_grows(self):
        g, nid = self._start_and_north()
        before = len(g)
        world.enter_node(g, nid, roll_count=5, roll_dirs=1)  # все 4
        after = len(g)
        # back-ребро уже было, добавляем 3 новых соседа
        assert after == before + 3