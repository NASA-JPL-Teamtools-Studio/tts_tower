#Standard Library Imports
from pathlib import Path
from enum import Enum, auto
from datetime import datetime

#Installed Dependency Imports
# None

#Teamtools Studio Imports
from tts_utilities.logger import create_logger

#This Library Imports
# None

logger = create_logger(__name__)

# ===================================================================
# :: Enum Extensions
# ===================================================================
class AccessEnum(Enum):
    """
    An enhanced Enum class that provides a flexible lookup method.

    This class adds a ``get`` method to retrieving enum members by instance, 
    value, or name (string). This is useful when processing inputs that might 
    be the Enum object itself, its database value, or its string representation.
    """
    @classmethod
    def get(cls, x, strict=True):
        """
        Retrieves an enum member by instance, value, or name.

        :param x: The key to look up. Can be an instance of the enum, a valid value, or a string name.
        :type x: Any
        :param strict: If True, raises a KeyError on failure. If False, returns None (implicit).
        :type strict: bool, optional
        :return: The matching Enum member.
        :rtype: AccessEnum
        :raises KeyError: If ``strict`` is True and no matching member is found.
        """
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

# ===================================================================
# :: General Utility Functions
# ===================================================================
def as_list(x):
    """
    Coerces a given input into a list.

    - Lists remain lists.
    - Strings and Dicts are wrapped in a single-element list (to prevent character/key iteration).
    - Iterables (other than str/dict) are converted to lists.
    - Scalars are wrapped in a single-element list.

    :param x: The input to coerce.
    :type x: Any
    :return: A list containing the input elements.
    :rtype: list
    """
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
    """
    Returns a new dictionary with the keys in reverse insertion order.

    :param d: The source dictionary.
    :type d: dict
    :return: A new dictionary with keys reversed.
    :rtype: dict
    """
    return {_k: _v for _k, _v in reversed(list(d.items()))}

def reverse_prio_dict_merge(d1, d2):
    """
    Merges two dictionaries while prioritizing the order of keys from the first dictionary.

    This is often used to ensure specific keys appear at the top of a dictionary 
    (e.g., for report ordering) by reversing, merging, and reversing back.

    :param d1: The dictionary whose key order takes priority (usually defaults/header info).
    :type d1: dict
    :param d2: The dictionary containing additional data.
    :type d2: dict
    :return: A merged dictionary with ``d1`` keys appearing first.
    :rtype: dict
    """
    return reverse_dict_order({**reverse_dict_order(d2), **reverse_dict_order(d1)})