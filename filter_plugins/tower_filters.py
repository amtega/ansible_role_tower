# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.filter.core import combine


def reverse_combine(a, b):
    """Apply ansible combine in a reverse way

    Args:
        a (dict): the dict with the values to merge
        b (dict): the dict to merge in

    Returns:
        dict: dict b with the values of dict a merged
    """
    return combine(b, a, recursive=True)


class FilterModule(object):
    """Ansible users filters."""

    def filters(self):
        return {
            "reverse_combine": reverse_combine
        }
