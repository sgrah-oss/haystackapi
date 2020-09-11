#!/usr/bin/python
# -*- coding: utf-8 -*-
# Zinc Grid
# (C) 2016 VRT Systems
#
# vim: set ts=4 sts=4 et tw=78 sw=4 si:
import copy
import datetime
import logging
import numbers
from collections import Sequence

import six

from .datatypes import NA, Quantity, Coordinate
from .metadata import MetadataObject
from .sortabledict import SortableDict

log = logging.getLogger("ping.Provider")

try:
    import collections.abc as col
except ImportError:  # pragma: no cover
    import collections as col
from .version import Version, VER_3_0, VER_2_0


class Grid(col.MutableSequence):
    '''
    A grid is basically a series of tabular records.  The grid has a header
    which describes some metadata about the grid and its columns.  This is
    followed by zero or more rows.
    '''

    def __init__(self, version=None, metadata=None, columns=None):
        '''
        Create a new Grid.
        '''
        # Version
        version_given = version is not None
        if version_given:
            version = Version(version)
        else:
            version = VER_2_0
            # version = VER_3_0  # TODO: set default version to 3
        self._version = version
        self._version_given = version_given

        # Metadata
        self.metadata = MetadataObject(validate_fn=self._detect_or_validate)

        # The columns
        self.column = SortableDict()

        # Rows
        self._row = []

        # Internal index
        self._index = None

        if metadata is not None:
            self.metadata.update(metadata.items())

        if columns is not None:
            if isinstance(columns, dict) or isinstance(columns, SortableDict):
                columns = list(columns.items())
            elif isinstance(columns, Sequence):
                if len(columns) and not isinstance(columns[0], tuple):
                    columns = list(zip(columns, [{}] * len(columns)))

            for col_id, col_meta in columns:
                # Convert sorted lists and dicts back to a list of items.
                if isinstance(col_meta, dict) or \
                        isinstance(col_meta, SortableDict):
                    col_meta = list(col_meta.items())

                mo = MetadataObject(validate_fn=self._detect_or_validate)
                mo.extend(col_meta)
                self.column.add_item(col_id, mo)

    @staticmethod
    def _approx_check(v1, v2):
        # Check types match
        if isinstance(v1, numbers.Number) and isinstance(v2, numbers.Number):
            return abs(v1 - v2) < 0.000001
        if type(v1) != type(v2) and \
                not (isinstance(v1, six.string_types) and isinstance(v2, six.string_types)):
            return False
        if isinstance(v1, datetime.time):
            return v1.replace(microsecond=0) == v2.replace(microsecond=0)
        elif isinstance(v1, datetime.datetime):
            return v1.tzinfo == v2.tzinfo and \
                   v1.date() == v2.date() and \
                   Grid._approx_check(v1.time(), v2.time())
        elif isinstance(v1, Quantity):
            return v1.unit == v2.unit and \
                   Grid._approx_check(v1.value, v2.value)
        elif isinstance(v1, Coordinate):
            return Grid._approx_check(v1.latitude, v2.latitude) and \
                   Grid._approx_check(v1.longitude, v2.longitude)
        elif isinstance(v1, dict):
            for k, v in v1.items():
                if not Grid._approx_check(v, v2.get(k, None)):
                    return False
            for k, v in v2.items():
                if k not in v1 and not Grid._approx_check(v1.get(k, None), v):
                    return False
            return True
        else:
            return v1 == v2

    def __eq__(self, other):
        if not isinstance(other, Grid):
            return False
        if set(self.metadata.keys()) != set(other.metadata.keys()):
            return False
        for key in self.metadata.keys():
            if not Grid._approx_check(self.metadata[key], other.metadata[key]):
                return False
        # Check column matches
        if set(self.column.keys()) != set(other.column.keys()):
            return False

        for col in self.column.keys():
            if col not in other.column or \
                    len(self.column[col]) != len(other.column[col]):
                return False
            for key in self.column[col].keys():
                if not Grid._approx_check(self.column[col][key], other.column[col][key]):
                    return False
        # Check row matches
        if len(self) != len(other):
            return False

        pending_right_row = [id(row) for row in other if 'id' not in row]
        for left in self._row:
            # Search record in other with same values
            find = False
            if 'id' in left:
                if left['id'] in other:
                    if self._approx_check(left, other[left['id']]):
                        find = True
            else:
                for right in other._row:
                    if id(right) not in pending_right_row:
                        continue
                    if self._approx_check(left, right):
                        find = True
                        pending_right_row.remove(id(right))
                        break
            if not find:
                return False

        return True

    def __sub__(self, other):
        """
        Calculate the difference between two grid.
        The result is a grid with only the attributs to update (change value, delete, etc)
        If a row with id must be removed,
        - if the row has an id, the result add a row with this id, and a tag 'remove_'
        - if the row has not an id, the result add a row with all values of the original row, and a tag 'remove_'

        It's possible to update all metadatas, the order of columns, add, remove or update some rows

        It's possible to apply the result in a grid, with the add operator.
        At all time, with gridA and gridB, gridA + (gridB - gridA) == gridB
        """
        assert isinstance(other, Grid)
        from .grid_diff import grid_diff
        return grid_diff(self, other)

    def __add__(self, other):
        """
        Merge two grid.
        The metadata can be modified with the values from other.
        Some attributs can be removed if the other attributs is REMOVE.
        If a row have a 'remove_' tag, the corresponding row was removed.

        The result of __sub__() can be used to patch the current grid.
        At all time, with gridA and gridB, gridA + (gridB - gridA) == gridB
        """
        assert isinstance(other, Grid)
        from .grid_diff import grid_merge
        if 'diff_' in self:
            return grid_merge(other.copy(), self)
        return grid_merge(self.copy(), other)

    @property
    def version(self):  # pragma: no cover
        # Trivial function
        return self._version

    @property
    def nearest_version(self):  # pragma: no cover
        # Trivial function
        return Version.nearest(self._version)

    @property
    def ver_str(self):  # pragma: no cover
        # Trivial function
        return str(self.version)

    def __repr__(self):  # pragma: no cover
        # Not critical to the operation of the library.
        '''
        Return a representation of this grid.
        '''
        parts = [u'\tVersion: %s' % self.ver_str]
        if bool(self.metadata):
            parts.append(u'\tMetadata: %s' % self.metadata)

        column_meta = []
        for col, col_meta in self.column.items():
            if bool(col_meta):
                column_meta.append(u'\t\t%s: %s' % (col, col_meta))
            else:
                column_meta.append(u'\t\t%s' % col)

        if bool(column_meta):
            parts.append(u'\tColumns:\n%s' % '\n'.join(column_meta))
        elif len(self.column):
            parts.append(u'\tColumns: %s' % ', '.join(self.column.keys()))
        else:
            parts.append(u'\tNo columns')

        if bool(self):
            parts.extend([
                u'\tRow %4d:\n\t%s' % (row, u'\n\t'.join([
                    ((u'%s=%r' % (col, data[col])) \
                         if col in data else \
                         (u'%s absent' % col)) for col \
                    in self.column.keys()]))
                for (row, data) in enumerate(self)
            ])
        else:
            parts.append(u'\tNo rows')
        # Represent as pseudo-XML
        class_name = self.__class__.__name__
        return u'<%s>\n%s\n</%s>' % (
            class_name, u'\n'.join(parts), class_name
        )

    def __getitem__(self, key):
        '''
        Retrieve the row at index.
        '''
        if isinstance(key, slice):
            result = Grid(version=self.version, metadata=self.metadata, columns=self.column)
            result._row = self._row[key]
            result._index = None
            return result
        elif isinstance(key, numbers.Number):
            return self._row[key]
        else:
            if not self._index:
                self.reindex()
            return self._index[str(key)]

    def __contains__(self, key):
        if isinstance(key, numbers.Number):
            return key >= 0 and key < len(self._row)
        else:
            if not self._index:
                self.reindex()
            return key in self._index

    def get(self, index, default=None):
        if not self._index:
            self.reindex()
        return self._index.get(str(index), default)

    def keys(self):
        if not self._index:
            self.reindex()
        return self._index.keys()

    def __len__(self):
        '''
        Return the number of rows in the grid.
        '''
        return len(self._row)

    def __setitem__(self, index, value):
        '''
        Replace the row at index.
        '''
        if not isinstance(value, dict):
            raise TypeError('value must be a dict')
        for val in value.values():
            self._detect_or_validate(val)
        if isinstance(index, numbers.Number):
            if "id" in self._row[index]:
                self._index.pop(self._row[index]['id'], None)
            self._row[index] = value
            if "id" in value:
                self._index[str(value["id"])] = value  # FIXME: id must be a Ref, not a string
        else:
            if not self._index:
                self.reindex()
            idx = list.index(self._row, self._index[index])
            if "id" in self._row[idx]:
                self._index.pop(self._row[idx]['id'], None)
            self._row[idx] = value
            if "id" in value:
                self._index[str(value["id"])] = value

    def __delitem__(self, key):
        '''
        Delete the row at index.
        '''
        if isinstance(key, numbers.Number):
            if "id" in self._row[key] and self._index:
                del self._index[self._row[key]['id']]
            del self._row[key]
        else:
            if not self._index:
                self.reindex()
            self._row.remove(self._index[key])
            self._index.pop(key)

    def remove(self, key):
        self.__delitem__(key)

    def insert(self, index, value):
        '''
        Insert a new row before index.
        '''
        if not isinstance(value, dict):
            raise TypeError('value must be a dict')
        for val in value.values():
            self._detect_or_validate(val)
        self._row.insert(index, value)
        if "id" in value:
            if not self._index:
                self.reindex()
            self._index[str(value["id"])] = value

    def reindex(self):
        '''
        Reindex the grid if a user, update directly an id of a row
        '''
        self._index = {}
        for item in self._row:
            if "id" in item:
                self._index[str(item["id"])] = item

    # FIXME
    def extend(self, values):
        super(Grid, self).extend(values)  # Python 2 compatible :-(
        # super().extend(values)  # Python 3+ :-)
        for item in self._row:
            if "id" in item:
                self._index[str(item["id"])] = item

    def copy(self):
        cp = copy.deepcopy(self)
        cp._index = None

    def filter(self, filter, limit=0):
        '''
        Return a filter version of this grid.
        Warning, use a grid.filter(...).deepcopy() if you not whant to share metadata, columns and rows)
        '''
        assert isinstance(limit, numbers.Number)
        assert limit >=0
        from .grid_filter import filter_function
        if filter.strip() == '':
            if limit == 0:
                return self
            else:
                result = Grid(version=self.version, metadata=self.metadata, columns=self.column)
                result.extend(self.__getitem__(slice(0, limit)))
                return result

        result = Grid(version=self.version, metadata=self.metadata, columns=self.column)
        fn = filter_function(filter)
        for row in self._row:
            if fn(self, row):
                result.append(row)
            if limit and len(result) == limit:
                break
        return result

    def _detect_or_validate(self, val):
        '''
        Detect the version used from the row content, or validate against
        the version if given.
        '''
        if (val is NA) \
                or isinstance(val, list) \
                or isinstance(val, dict) \
                or isinstance(val, SortableDict) \
                or isinstance(val, Grid):
            # Project Haystack 3.0 type.
            self._assert_version(VER_3_0)

    def _assert_version(self, version):
        '''
        Assert that the grid version is equal to or above the given value.
        If no version is set, set the version.
        '''
        if self.nearest_version < version:
            if self._version_given:
                raise ValueError(
                    'Data type requires version %s' \
                    % version)
            else:
                self._version = version
