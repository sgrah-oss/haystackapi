#!/usr/bin/python
# -*- coding: utf-8 -*-
# Zinc Grid Metadata
# (C) 2016 VRT Systems
#
# vim: set ts=4 sts=4 et tw=78 sw=4 si:
"""
A support of metadata of a grid or column.
"""
import copy

from .datatypes import MARKER
from .sortabledict import SortableDict


class MetadataObject(SortableDict):  # pylint: disable=too-many-ancestors
    """
    An object that contains some metadata fields.  Used as a convenience
    base-class for grids and columns, both of which have metadata.
    """

    def append(self, key, value=MARKER, replace=True):
        """
        Append the item to the metadata.
        """
        return self.add_item(key, value, replace=replace)

    def extend(self, items, replace=True):
        """
        Append the items to the metadata.
        """
        if isinstance(items, (dict, SortableDict)):
            items = list(items.items())

        for (key, value) in items:
            self.append(key, value, replace=replace)

    def copy(self):
        return copy.deepcopy(self)
