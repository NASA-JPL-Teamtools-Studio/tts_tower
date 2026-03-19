import pytest
from enum import Enum, auto

# ===================================================================
# :: Import or Mock the Code Under Test
# ===================================================================
# NOTE: If your code is in 'tower/utils.py', import it here normally:
# from tts_tower.utils import AccessEnum, as_list, reverse_dict_order, reverse_prio_dict_merge

# FOR THIS EXAMPLE: I am pasting the code logic here (mocked) to ensure 
# the tests run standalone for you immediately. 
# -------------------------------------------------------------------

class AccessEnum(Enum):
    @classmethod
    def get(cls, x, strict=True):
        if isinstance(x, cls):
            return x
        try:
            return cls(x)
        except ValueError:
            try:
                return cls[x]
            except KeyError:
                if strict:
                    raise KeyError(f'Enum {cls} does not have matching name or value: {x}')
                # Implicitly returns None if not strict

def as_list(x):
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [x]
    if hasattr(x, '__iter__'):
        return list(x)
    return [x]

def reverse_dict_order(d):
    return {_k: _v for _k, _v in reversed(list(d.items()))}

def reverse_prio_dict_merge(d1, d2):
    return reverse_dict_order({**reverse_dict_order(d2), **reverse_dict_order(d1)})

# ===================================================================
# :: Unit Tests
# ===================================================================

# --- Setup for AccessEnum Tests ---
class Color(AccessEnum):
    RED = 1
    BLUE = 2
    GREEN = "green_val"

class TestAccessEnum:
    def test_get_existing_instance(self):
        """Should return the instance if an instance is passed."""
        assert Color.get(Color.RED) == Color.RED

    def test_get_by_value_int(self):
        """Should return the instance if the integer value is passed."""
        assert Color.get(1) == Color.RED

    def test_get_by_value_str(self):
        """Should return the instance if the string value is passed."""
        assert Color.get("green_val") == Color.GREEN

    def test_get_by_name_str(self):
        """Should return the instance if the Key Name is passed."""
        assert Color.get("BLUE") == Color.BLUE
        assert Color.get("RED") == Color.RED

    def test_get_missing_strict(self):
        """Should raise KeyError if strict=True and value/name not found."""
        with pytest.raises(KeyError) as excinfo:
            Color.get("PURPLE", strict=True)
        assert "does not have matching name or value" in str(excinfo.value)

    def test_get_missing_non_strict(self):
        """Should return None if strict=False and value/name not found."""
        result = Color.get("PURPLE", strict=False)
        assert result is None


class TestAsList:
    def test_list_remains_list(self):
        """If input is already a list, return it as is."""
        x = [1, 2, 3]
        assert as_list(x) == x

    def test_string_becomes_list(self):
        """String should be wrapped in a list, not exploded into chars."""
        assert as_list("hello") == ["hello"]

    def test_dict_becomes_list_of_dict(self):
        """Dict should be wrapped in a list, not converted to list of keys."""
        x = {'a': 1}
        assert as_list(x) == [{'a': 1}]

    def test_tuple_becomes_list(self):
        """Tuples (iterables) should be converted to lists."""
        x = (1, 2)
        assert as_list(x) == [1, 2]
    
    def test_set_becomes_list(self):
        """Sets (iterables) should be converted to lists."""
        x = {1, 2}
        # Sorting because set order is not guaranteed
        assert sorted(as_list(x)) == [1, 2]

    def test_scalar_becomes_list(self):
        """Integers/Floats/None should be wrapped in a list."""
        assert as_list(100) == [100]
        assert as_list(None) == [None]


class TestDictUtils:
    def test_reverse_dict_order(self):
        """Should reverse the insertion order of keys."""
        # Python 3.7+ guarantees insertion order
        d = {'a': 1, 'b': 2, 'c': 3}
        reversed_d = reverse_dict_order(d)
        
        # Verify order by converting keys to list
        assert list(reversed_d.keys()) == ['c', 'b', 'a']
        assert reversed_d['a'] == 1

    def test_reverse_prio_dict_merge_disjoint(self):
        """
        Merging disjoint dicts.
        Logic implies d1 items should end up BEFORE d2 items in the final dict.
        """
        d1 = {'a': 1}
        d2 = {'b': 2}
        
        # Logic trace:
        # rev(d1) -> {a:1}
        # rev(d2) -> {b:2}
        # merge {**rev_d2, **rev_d1} -> {b:2, a:1} (d1 adds to end)
        # reverse result -> {a:1, b:2}
        
        result = reverse_prio_dict_merge(d1, d2)
        assert list(result.keys()) == ['a', 'b']
        assert result == {'a': 1, 'b': 2}

    def test_reverse_prio_dict_merge_overlap(self):
        """
        Merging overlapping dicts.
        d1 is the 'priority' dict, so its values should overwrite d2.
        """
        d1 = {'key': 'priority', 'unique_1': 1}
        d2 = {'key': 'original', 'unique_2': 2}

        result = reverse_prio_dict_merge(d1, d2)

        # 1. Check Value Priority (d1 should win)
        assert result['key'] == 'priority'
        
        # 2. Check Order (d1 keys should come first)
        expected_order = ['unique_1', 'key', 'unique_2']
        # Note: 'key' position depends on the specific reversing logic.
        # rev(d2) = {unique_2, key:orig}
        # rev(d1) = {unique_1, key:prio}
        # merge = {unique_2, key:prio, unique_1} (d1 updates key, adds unique_1 to end)
        # reverse = {unique_1, key:prio, unique_2}
        
        assert list(result.keys()) == expected_order