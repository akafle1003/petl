from __future__ import absolute_import, print_function, division


# standard library dependencies
from itertools import islice, chain
from collections import deque
from petl.compat import izip, izip_longest, next, count, string_types


# internal dependencies
from petl.util.base import asindices, rowgetter, Record, Table


import logging
logger = logging.getLogger(__name__)
warning = logger.warning
info = logger.info
debug = logger.debug


def cut(table, *args, **kwargs):
    """
    Choose and/or re-order fields. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar', 'baz'],
        ...           ['A', 1, 2.7],
        ...           ['B', 2, 3.4],
        ...           ['B', 3, 7.8],
        ...           ['D', 42, 9.0],
        ...           ['E', 12]]
        >>> table2 = etl.cut(table1, 'foo', 'baz')
        >>> table2
        +-------+-------+
        | 0|foo | 1|baz |
        +=======+=======+
        | 'A'   |   2.7 |
        +-------+-------+
        | 'B'   |   3.4 |
        +-------+-------+
        | 'B'   |   7.8 |
        +-------+-------+
        | 'D'   |   9.0 |
        +-------+-------+
        | 'E'   | None  |
        +-------+-------+

        >>> # fields can also be specified by index, starting from zero
        ... table3 = etl.cut(table1, 0, 2)
        >>> table3
        +-------+-------+
        | 0|foo | 1|baz |
        +=======+=======+
        | 'A'   |   2.7 |
        +-------+-------+
        | 'B'   |   3.4 |
        +-------+-------+
        | 'B'   |   7.8 |
        +-------+-------+
        | 'D'   |   9.0 |
        +-------+-------+
        | 'E'   | None  |
        +-------+-------+

        >>> # field names and indices can be mixed
        ... table4 = etl.cut(table1, 'bar', 0)
        >>> table4
        +-------+-------+
        | 0|bar | 1|foo |
        +=======+=======+
        |     1 | 'A'   |
        +-------+-------+
        |     2 | 'B'   |
        +-------+-------+
        |     3 | 'B'   |
        +-------+-------+
        |    42 | 'D'   |
        +-------+-------+
        |    12 | 'E'   |
        +-------+-------+

        >>> # select a range of fields
        ... table5 = etl.cut(table1, *range(0, 2))
        >>> table5
        +-------+-------+
        | 0|foo | 1|bar |
        +=======+=======+
        | 'A'   |     1 |
        +-------+-------+
        | 'B'   |     2 |
        +-------+-------+
        | 'B'   |     3 |
        +-------+-------+
        | 'D'   |    42 |
        +-------+-------+
        | 'E'   |    12 |
        +-------+-------+

    Note that any short rows will be padded with `None` values (or whatever is
    provided via the `missing` keyword argument).
    
    See also :func:`petl.transform.basics.cutout`.
    
    """

    # support passing a single list or tuple of fields
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        args = args[0]
            
    return CutView(table, args, **kwargs)


Table.cut = cut


class CutView(Table):
    
    def __init__(self, source, spec, missing=None):
        self.source = source
        self.spec = spec
        self.missing = missing
        
    def __iter__(self):
        return itercut(self.source, self.spec, self.missing)
    
        
def itercut(source, spec, missing=None):
    it = iter(source)
    spec = tuple(spec)  # make sure no-one can change midstream
    
    # convert field selection into field indices
    flds = next(it)
    indices = asindices(flds, spec)

    # define a function to transform each row in the source data 
    # according to the field selection
    transform = rowgetter(*indices)
    
    # yield the transformed field names
    yield transform(flds)
    
    # construct the transformed data
    for row in it:
        try:
            yield transform(row) 
        except IndexError:
            # row is short, let's be kind and fill in any missing fields
            yield tuple(row[i] if i < len(row) else missing for i in indices)

    
def cutout(table, *args, **kwargs):
    """
    Remove fields. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar', 'baz'],
        ...           ['A', 1, 2.7],
        ...           ['B', 2, 3.4],
        ...           ['B', 3, 7.8],
        ...           ['D', 42, 9.0],
        ...           ['E', 12]]
        >>> table2 = etl.cutout(table1, 'bar')
        >>> table2
        +-------+-------+
        | 0|foo | 1|baz |
        +=======+=======+
        | 'A'   |   2.7 |
        +-------+-------+
        | 'B'   |   3.4 |
        +-------+-------+
        | 'B'   |   7.8 |
        +-------+-------+
        | 'D'   |   9.0 |
        +-------+-------+
        | 'E'   | None  |
        +-------+-------+
        
    See also :func:`petl.transform.basics.cut`.
    
    """

    return CutOutView(table, args, **kwargs)


Table.cutout = cutout


class CutOutView(Table):
    
    def __init__(self, source, spec, missing=None):
        self.source = source
        self.spec = spec
        self.missing = missing
        
    def __iter__(self):
        return itercutout(self.source, self.spec, self.missing)
    
        
def itercutout(source, spec, missing=None):
    it = iter(source)
    spec = tuple(spec)  # make sure no-one can change midstream
    
    # convert field selection into field indices
    flds = next(it)
    indicesout = asindices(flds, spec)
    indices = [i for i in range(len(flds)) if i not in indicesout]
    
    # define a function to transform each row in the source data 
    # according to the field selection
    transform = rowgetter(*indices)
    
    # yield the transformed field names
    yield transform(flds)
    
    # construct the transformed data
    for row in it:
        try:
            yield transform(row) 
        except IndexError:
            # row is short, let's be kind and fill in any missing fields
            yield tuple(row[i] if i < len(row) else missing for i in indices)

    
def cat(*tables, **kwargs):
    """
    Concatenate data from two or more tables. E.g.::
    
        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           [1, 'A'],
        ...           [2, 'B']]
        >>> table2 = [['bar', 'baz'],
        ...           ['C', True],
        ...           ['D', False]]
        >>> table3 = etl.cat(table1, table2)
        >>> table3
        +-------+-------+-------+
        | 0|foo | 1|bar | 2|baz |
        +=======+=======+=======+
        |     1 | 'A'   | None  |
        +-------+-------+-------+
        |     2 | 'B'   | None  |
        +-------+-------+-------+
        | None  | 'C'   | True  |
        +-------+-------+-------+
        | None  | 'D'   | False |
        +-------+-------+-------+

        >>> # can also be used to square up a single table with uneven rows
        ... table4 = [['foo', 'bar', 'baz'],
        ...           ['A', 1, 2],
        ...           ['B', '2', '3.4'],
        ...           [u'B', u'3', u'7.8', True],
        ...           ['D', 'xyz', 9.0],
        ...           ['E', None]]
        >>> table5 = etl.cat(table4)
        >>> table5
        +-------+-------+-------+
        | 0|foo | 1|bar | 2|baz |
        +=======+=======+=======+
        | 'A'   |     1 |     2 |
        +-------+-------+-------+
        | 'B'   | '2'   | '3.4' |
        +-------+-------+-------+
        | 'B'   | '3'   | '7.8' |
        +-------+-------+-------+
        | 'D'   | 'xyz' |   9.0 |
        +-------+-------+-------+
        | 'E'   | None  | None  |
        +-------+-------+-------+

        >>> # use the header keyword argument to specify a fixed set of fields
        ... table6 = [['bar', 'foo'],
        ...           ['A', 1],
        ...           ['B', 2]]
        >>> table7 = etl.cat(table6, header=['A', 'foo', 'B', 'bar', 'C'])
        >>> table7
        +------+-------+------+-------+------+
        | 0|A  | 1|foo | 2|B  | 3|bar | 4|C  |
        +======+=======+======+=======+======+
        | None |     1 | None | 'A'   | None |
        +------+-------+------+-------+------+
        | None |     2 | None | 'B'   | None |
        +------+-------+------+-------+------+

        >>> # using the header keyword argument with two input tables
        ... table8 = [['bar', 'foo'],
        ...           ['A', 1],
        ...           ['B', 2]]
        >>> table9 = [['bar', 'baz'],
        ...           ['C', True],
        ...           ['D', False]]
        >>> table10 = etl.cat(table8, table9, header=['A', 'foo', 'B', 'bar', 'C'])
        >>> table10
        +------+-------+------+-------+------+
        | 0|A  | 1|foo | 2|B  | 3|bar | 4|C  |
        +======+=======+======+=======+======+
        | None |     1 | None | 'A'   | None |
        +------+-------+------+-------+------+
        | None |     2 | None | 'B'   | None |
        +------+-------+------+-------+------+
        | None | None  | None | 'C'   | None |
        +------+-------+------+-------+------+
        | None | None  | None | 'D'   | None |
        +------+-------+------+-------+------+
    
    Note that the tables do not need to share exactly the same fields, any 
    missing fields will be padded with `None` or whatever is provided via the 
    `missing` keyword argument.

    Note that this function can be used with a single table argument, in which
    case it has the effect of ensuring all data rows are the same length as
    the header row, truncating any long rows and padding any short rows with
    the value of the `missing` keyword argument.

    By default, the fields for the output table will be determined as the
    union of all fields found in the input tables. Use the `header` keyword 
    argument to override this behaviour and specify a fixed set of fields for 
    the output table. 
    
    """
    
    return CatView(tables, **kwargs)


Table.cat = cat

    
class CatView(Table):
    
    def __init__(self, sources, missing=None, header=None):
        self.sources = sources
        self.missing = missing
        if header is not None:
            header = tuple(header)  # ensure hashable
        self.header = header

    def __iter__(self):
        return itercat(self.sources, self.missing, self.header)
    

def itercat(sources, missing, header):
    its = [iter(t) for t in sources]
    source_flds_lists = [next(it) for it in its]

    if header is None:
        # determine output fields by gathering all fields found in the sources
        outflds = list()
        for flds in source_flds_lists:
            for f in flds:
                if f not in outflds:
                    # add any new fields as we find them
                    outflds.append(f)
    else:
        # predetermined output fields
        outflds = header
    yield tuple(outflds)

    # output data rows
    for source_index, it in enumerate(its):

        flds = source_flds_lists[source_index]
        
        # now construct and yield the data rows
        for row in it:
            try:
                # should be quickest to do this way
                yield tuple(row[flds.index(f)] if f in flds else missing
                            for f in outflds)
            except IndexError:
                # handle short rows
                outrow = [missing] * len(outflds)
                for i, f in enumerate(flds):
                    try:
                        outrow[outflds.index(f)] = row[i]
                    except IndexError:
                        pass  # be relaxed about short rows
                yield tuple(outrow)


def addfield(table, field, value=None, index=None, missing=None):
    """
    Add a field with a fixed or calculated value. E.g.::
    
        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['M', 12],
        ...           ['F', 34],
        ...           ['-', 56]]
        >>> # using a fixed value
        ... table2 = etl.addfield(table1, 'baz', 42)
        >>> table2
        +-------+-------+-------+
        | 0|foo | 1|bar | 2|baz |
        +=======+=======+=======+
        | 'M'   |    12 |    42 |
        +-------+-------+-------+
        | 'F'   |    34 |    42 |
        +-------+-------+-------+
        | '-'   |    56 |    42 |
        +-------+-------+-------+

        >>> # calculating the value
        ... table2 = etl.addfield(table1, 'baz', lambda rec: rec['bar'] * 2)
        >>> table2
        +-------+-------+-------+
        | 0|foo | 1|bar | 2|baz |
        +=======+=======+=======+
        | 'M'   |    12 |    24 |
        +-------+-------+-------+
        | 'F'   |    34 |    68 |
        +-------+-------+-------+
        | '-'   |    56 |   112 |
        +-------+-------+-------+

    Use the `index` parameter to control the position of the inserted field.

    """

    return AddFieldView(table, field, value=value, index=index,
                        missing=missing)


Table.addfield = addfield


class AddFieldView(Table):
    
    def __init__(self, source, field, value=None, index=None, missing=None):
        # ensure rows are all the same length
        self.source = cat(source, missing=missing)
        self.field = field
        self.value = value
        self.index = index
        
    def __iter__(self):
        return iteraddfield(self.source, self.field, self.value, self.index)
    

def iteraddfield(source, field, value, index):
    it = iter(source)
    flds = next(it)
    
    # determine index of new field
    if index is None:
        index = len(flds)
        
    # construct output fields
    outflds = list(flds)    
    outflds.insert(index, field)
    yield tuple(outflds)

    if callable(value):
        # wrap rows as records if using calculated value
        it = (Record(row, flds) for row in it)
        for row in it:
            outrow = list(row)
            v = value(row)
            outrow.insert(index, v)
            yield tuple(outrow)
    else:
        for row in it:
            outrow = list(row)
            outrow.insert(index, value)
            yield tuple(outrow)
        
    
def rowslice(table, *sliceargs):
    """
    Choose a subsequence of data rows. E.g.::
    
        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['a', 1],
        ...           ['b', 2],
        ...           ['c', 5],
        ...           ['d', 7],
        ...           ['f', 42]]
        >>> table2 = etl.rowslice(table1, 2)
        >>> table2
        +-------+-------+
        | 0|foo | 1|bar |
        +=======+=======+
        | 'a'   |     1 |
        +-------+-------+
        | 'b'   |     2 |
        +-------+-------+

        >>> table3 = etl.rowslice(table1, 1, 4)
        >>> table3
        +-------+-------+
        | 0|foo | 1|bar |
        +=======+=======+
        | 'b'   |     2 |
        +-------+-------+
        | 'c'   |     5 |
        +-------+-------+
        | 'd'   |     7 |
        +-------+-------+

        >>> table4 = etl.rowslice(table1, 0, 5, 2)
        >>> table4
        +-------+-------+
        | 0|foo | 1|bar |
        +=======+=======+
        | 'a'   |     1 |
        +-------+-------+
        | 'c'   |     5 |
        +-------+-------+
        | 'f'   |    42 |
        +-------+-------+
        
    Positional arguments are used to slice the data rows. The `sliceargs` are
    passed through to :func:`itertools.islice`.

    See also :func:`head`, :func:`tail`.

    """

    return RowSliceView(table, *sliceargs)


Table.rowslice = rowslice


class RowSliceView(Table):
    
    def __init__(self, source, *sliceargs):
        self.source = source
        if not sliceargs:
            self.sliceargs = (None,)
        else:
            self.sliceargs = sliceargs
        
    def __iter__(self):
        return iterrowslice(self.source, self.sliceargs)


def iterrowslice(source, sliceargs):    
    it = iter(source)
    yield tuple(next(it))  # fields
    for row in islice(it, *sliceargs):
        yield tuple(row)


def head(table, n=5):
    """
    Select the first n data rows. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['a', 1],
        ...           ['b', 2],
        ...           ['c', 5],
        ...           ['d', 7],
        ...           ['f', 42],
        ...           ['f', 3],
        ...           ['h', 90]]
        >>> table2 = etl.head(table1, 4)
        >>> table2
        +-------+-------+
        | 0|foo | 1|bar |
        +=======+=======+
        | 'a'   |     1 |
        +-------+-------+
        | 'b'   |     2 |
        +-------+-------+
        | 'c'   |     5 |
        +-------+-------+
        | 'd'   |     7 |
        +-------+-------+

    See also :func:`petl.transform.basics.tail`,
    :func:`petl.transform.basics.rowslice`.
    
    """

    return rowslice(table, n)


Table.head = head

        
def tail(table, n=5):
    """
    Select the last n data rows. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['a', 1],
        ...           ['b', 2],
        ...           ['c', 5],
        ...           ['d', 7],
        ...           ['f', 42],
        ...           ['f', 3],
        ...           ['h', 90],
        ...           ['k', 12],
        ...           ['l', 77],
        ...           ['q', 2]]
        >>> table2 = etl.tail(table1, 4)
        >>> table2
        +-------+-------+
        | 0|foo | 1|bar |
        +=======+=======+
        | 'h'   |    90 |
        +-------+-------+
        | 'k'   |    12 |
        +-------+-------+
        | 'l'   |    77 |
        +-------+-------+
        | 'q'   |     2 |
        +-------+-------+
        
    See also :func:`petl.transform.basics.head`,
    :func:`petl.transform.basics.rowslice`.

    """

    return TailView(table, n)


Table.tail = tail


class TailView(Table):
    
    def __init__(self, source, n):
        self.source = source
        self.n = n
        
    def __iter__(self):
        return itertail(self.source, self.n)


def itertail(source, n):
    it = iter(source)
    yield tuple(next(it))  # fields
    cache = deque()
    for row in it:
        cache.append(row)
        if len(cache) > n:
            cache.popleft()
    for row in cache:
        yield tuple(row)


def skipcomments(table, prefix):
    """
    Skip any row where the first value is a string and starts with
    `prefix`. E.g.::
    
        >>> import petl as etl
        >>> table1 = [['##aaa', 'bbb', 'ccc'],
        ...           ['##mmm',],
        ...           ['#foo', 'bar'],
        ...           ['##nnn', 1],
        ...           ['a', 1],
        ...           ['b', 2]]
        >>> table2 = etl.skipcomments(table1, '##')
        >>> table2
        +--------+-------+
        | 0|#foo | 1|bar |
        +========+=======+
        | 'a'    |     1 |
        +--------+-------+
        | 'b'    |     2 |
        +--------+-------+

    Use the `prefix` parameter to determine which string to consider as
    indicating a comment.

    """

    return SkipCommentsView(table, prefix)


Table.skipcomments = skipcomments


class SkipCommentsView(Table):
    
    def __init__(self, source, prefix):
        self.source = source
        self.prefix = prefix
        
    def __iter__(self):
        return iterskipcomments(self.source, self.prefix)   


def iterskipcomments(source, prefix):
    return (row for row in source
            if (len(row) > 0
                and not(isinstance(row[0], string_types)
                and row[0].startswith(prefix))))


def movefield(table, field, index):
    """
    Move a field to a new position.

    """

    return MoveFieldView(table, field, index)


Table.movefield = movefield


class MoveFieldView(Table):

    def __init__(self, table, field, index, missing=None):
        self.table = table
        self.field = field
        self.index = index
        self.missing = missing

    def __iter__(self):
        it = iter(self.table)

        # determine output fields
        fields = list(next(it))
        newfields = [f for f in fields if f != self.field]
        newfields.insert(self.index, self.field)
        yield tuple(newfields)

        # define a function to transform each row in the source data
        # according to the field selection
        indices = asindices(fields, newfields)
        transform = rowgetter(*indices)

        # construct the transformed data
        for row in it:
            try:
                yield transform(row)
            except IndexError:
                # row is short, let's be kind and fill in any missing fields
                yield tuple(row[i] if i < len(row) else self.missing
                            for i in indices)


def annex(*tables, **kwargs):
    """
    Join two or more tables by row order. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['A', 9],
        ...           ['C', 2],
        ...           ['F', 1]]
        >>> table2 = [['foo', 'baz'],
        ...           ['B', 3],
        ...           ['D', 10]]
        >>> table3 = etl.annex(table1, table2)
        >>> table3
        +-------+-------+-------+-------+
        | 0|foo | 1|bar | 2|foo | 3|baz |
        +=======+=======+=======+=======+
        | 'A'   |     9 | 'B'   |     3 |
        +-------+-------+-------+-------+
        | 'C'   |     2 | 'D'   |    10 |
        +-------+-------+-------+-------+
        | 'F'   |     1 | None  | None  |
        +-------+-------+-------+-------+

    See also :func:`petl.transform.joins.join`.

    """
    
    return AnnexView(tables, **kwargs)


Table.annex = annex


class AnnexView(Table):
    
    def __init__(self, tables, missing=None):
        self.tables = tables
        self.missing = missing
        
    def __iter__(self):
        return iterannex(self.tables, self.missing)
    

def iterannex(tables, missing):
    iters = [iter(t) for t in tables]
    headers = [next(it) for it in iters]
    outfields = tuple(chain(*headers))  
    yield outfields
    for rows in izip_longest(*iters):
        outrow = list()
        for i, row in enumerate(rows):
            lh = len(headers[i])
            if row is None:  # handle uneven length tables
                row = [missing] * len(headers[i])
            else:
                lr = len(row)
                if lr < lh:  # handle short rows
                    row = list(row)
                    row.extend([missing] * (lh-lr))
                elif lr > lh:  # handle long rows
                    row = row[:lh]
            outrow.extend(row)
        yield tuple(outrow)
          
    
def addrownumbers(table, start=1, step=1):
    """
    Add a field of row numbers. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['A', 9],
        ...           ['C', 2],
        ...           ['F', 1]]
        >>> table2 = etl.addrownumbers(table1)
        >>> table2
        +-------+-------+-------+
        | 0|row | 1|foo | 2|bar |
        +=======+=======+=======+
        |     1 | 'A'   |     9 |
        +-------+-------+-------+
        |     2 | 'C'   |     2 |
        +-------+-------+-------+
        |     3 | 'F'   |     1 |
        +-------+-------+-------+

    Parameters `start` and `step` control the numbering.

    """
    
    return AddRowNumbersView(table, start, step)


Table.addrownumbers = addrownumbers


class AddRowNumbersView(Table):
    
    def __init__(self, table, start=1, step=1):
        self.table = table
        self.start = start
        self.step = step

    def __iter__(self):
        return iteraddrownumbers(self.table, self.start, self.step)
    

def iteraddrownumbers(table, start, step):
    it = iter(table)
    flds = next(it)
    outflds = ['row']
    outflds.extend(flds)
    yield tuple(outflds)
    for row, n in izip(it, count(start, step)):
        outrow = [n]
        outrow.extend(row)
        yield tuple(outrow)
        

def addcolumn(table, field, col, index=None, missing=None):
    """
    Add a column of data to the table. E.g.::
    
        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['A', 1],
        ...           ['B', 2]]
        >>> col = [True, False]
        >>> table2 = etl.addcolumn(table1, 'baz', col)
        >>> table2
        +-------+-------+-------+
        | 0|foo | 1|bar | 2|baz |
        +=======+=======+=======+
        | 'A'   |     1 | True  |
        +-------+-------+-------+
        | 'B'   |     2 | False |
        +-------+-------+-------+

    Use the `index` parameter to control the position of the new column.

    """
    
    return AddColumnView(table, field, col, index=index, missing=missing)


Table.addcolumn = addcolumn


class AddColumnView(Table):
    
    def __init__(self, table, field, col, index=None, missing=None):
        self._table = table
        self._field = field
        self._col = col
        self._index = index
        self._missing = missing
        
    def __iter__(self):
        return iteraddcolumn(self._table, self._field, self._col, 
                             self._index, self._missing)
    
    
def iteraddcolumn(table, field, col, index, missing):
    it = iter(table)
    fields = [str(f) for f in next(it)]
    
    # determine position of new column
    if index is None:
        index = len(fields)
    
    # construct output header
    outflds = list(fields)
    outflds.insert(index, field)
    yield tuple(outflds)
    
    # construct output data
    for row, val in izip_longest(it, col, fillvalue=missing):
        # run out of rows?
        if row == missing:
            row = [missing] * len(fields)
        outrow = list(row)
        outrow.insert(index, val)
        yield tuple(outrow)
        
        
class TransformError(Exception):
    pass


def addfieldusingcontext(table, field, query):
    """
    Like :func:`addfield` but the `query` function is passed the previous,
    current and next rows, so values may be calculated based on data in adjacent
    rows. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['A', 1],
        ...           ['B', 4],
        ...           ['C', 5],
        ...           ['D', 9]]
        >>> def upstream(prv, cur, nxt):
        ...     if prv is None:
        ...         return None
        ...     else:
        ...         return cur.bar - prv.bar
        ...
        >>> def downstream(prv, cur, nxt):
        ...     if nxt is None:
        ...         return None
        ...     else:
        ...         return nxt.bar - cur.bar
        ...
        >>> table2 = etl.addfieldusingcontext(table1, 'baz', upstream)
        >>> table3 = etl.addfieldusingcontext(table2, 'quux', downstream)
        >>> table3
        +-------+-------+-------+--------+
        | 0|foo | 1|bar | 2|baz | 3|quux |
        +=======+=======+=======+========+
        | 'A'   |     1 | None  |      3 |
        +-------+-------+-------+--------+
        | 'B'   |     4 |     3 |      1 |
        +-------+-------+-------+--------+
        | 'C'   |     5 |     1 |      4 |
        +-------+-------+-------+--------+
        | 'D'   |     9 |     4 | None   |
        +-------+-------+-------+--------+

    The `field` parameter is the name of the field to be added. The `query`
    parameter is a function operating on the curent, previous and next rows
    and returning the value.

    """

    return AddFieldUsingContextView(table, field, query)


Table.addfieldusingcontext = addfieldusingcontext


class AddFieldUsingContextView(Table):

    def __init__(self, table, field, query):
        self.table = table
        self.field = field
        self.query = query

    def __iter__(self):
        return iteraddfieldusingcontext(self.table, self.field, self.query)


def iteraddfieldusingcontext(table, field, query):
    it = iter(table)
    fields = tuple(next(it))
    yield fields + (field,)
    it = (Record(row, fields) for row in it)
    prv = None
    cur = next(it)
    for nxt in it:
        v = query(prv, cur, nxt)
        yield tuple(cur) + (v,)
        prv = cur
        cur = nxt
    # handle last row
    v = query(prv, cur, None)
    yield tuple(cur) + (v,)
