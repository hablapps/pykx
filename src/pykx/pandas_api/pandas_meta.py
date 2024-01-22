from . import api_return
from ..exceptions import QError


def _init(_q):
    global q
    q = _q


def _type_num_is_numeric(typenum):
    if typenum >= 4 and typenum <= 9:
        return True
    return False


def _type_num_is_numeric_or_bool(typenum):
    if typenum >= 4 and typenum <= 9 or typenum == 1:
        return True
    return False


def _get_numeric_only_subtable(tab):
    t = q('0#0!', tab)
    cols = q.cols(t).py()
    numeric_cols = []
    for c in cols:
        if _type_num_is_numeric(t[c].t):
            numeric_cols.append(c)
    return tab[numeric_cols]


def _get_numeric_only_subtable_with_bools(tab):
    t = q('0#0!', tab)
    cols = q.cols(t).py()
    numeric_cols = []
    for c in cols:
        if _type_num_is_numeric_or_bool(t[c].t):
            numeric_cols.append(c)
    return (tab[numeric_cols], numeric_cols)


def _get_bool_only_subtable(tab):
    t = q('0#0!', tab)
    cols = q.cols(t).py()
    bool_cols = []
    for c in cols:
        if t[c].t == 1 or t[c].t == -1:
            bool_cols.append(c)
    return (tab[bool_cols], bool_cols)


def preparse_computations(tab, axis=0, skipna=True, numeric_only=False, bool_only=False):
    cols = q('cols', tab)
    if 'Keyed' in str(type(tab)):
        tab = q('{(keys x) _ 0!x}', tab)
    if numeric_only:
        (tab, cols) = _get_numeric_only_subtable_with_bools(tab)
    if bool_only:
        (tab, cols) = _get_bool_only_subtable(tab)
    res = q(
        '{[tab;skipna;axis]'
        'r:value flip tab;'
        'if[not axis~0;r:flip r];'
        'if[skipna;r:{x where not null x} each r];'
        'r}',
        tab,
        skipna,
        axis
    )
    return (res, cols if axis == 0 else q.til(len(res)))


# The simple computation functions all return a tuple of the results and the col names the results
# were created from, this decorator is used to remove some code duplication to convert all of those
# back into a dictionary
def convert_result(func):
    @api_return
    def inner(*args, **kwargs):
        res, cols = func(*args, **kwargs)
        return q('{[x; y] y!x}', res, cols)
    return inner


# Define the mapping between returns of kx.q.meta and associated data type
_type_mapping = {'c': b'kx.Char',
                 's': b'kx.Symbol',
                 'g': b'kx.GUID',
                 'c': b'kx.Char',
                 'b': b'kx.Boolean',
                 'x': b'kx.Byte',
                 'h': b'kx.Short',
                 'i': b'kx.Int',
                 'j': b'kx.Long',
                 'e': b'kx.Real',
                 'f': b'kx.Float',
                 'p': b'kx.Timestamp',
                 'd': b'kx.Date',
                 'z': b'kx.Datetime',
                 'n': b'kx.Timespan',
                 'u': b'kx.Minute',
                 'v': b'kx.Second',
                 't': b'kx.Time',
                 'm': b'kx.Month',
                 '': b'kx.List'}


class PandasMeta:
    # Dataframe properties
    @property
    def columns(self):
        return q('{if[99h~type x; x:value x]; cols x}', self)

    @property
    def dtypes(self):
        return q('''
                 {a:0!x;
                  flip `columns`type!(
                    a[`c];
                    {$[x~"kx.List";x;x,$[y in .Q.a;"Atom";"Vector"]]}'[y `$/:lower a`t;a`t])}
                 ''', q.meta(self), _type_mapping)

    @property
    def empty(self):
        return q('{0~count x}', self)

    @property
    def ndim(self):
        return q('2')

    @property
    def shape(self):
        return tuple(q('{if[99h~type x; x:value x]; (count x; count cols x)}', self))

    @property
    def size(self):
        return q('{count[x] * count[cols x]}', self)

    @api_return
    def mean(self, axis: int = 0, numeric_only: bool = False):
        tab = self
        if 'Keyed' in str(type(tab)):
            tab = q('{(keys x) _ 0!x}', tab)
        if numeric_only:
            tab = _get_numeric_only_subtable(tab)

        key_str = '' if axis == 0 else '`$string '
        val_str = '' if axis == 0 else '"f"$value '
        query_str = 'cols tab' if axis == 0 else 'til count tab'
        where_str = ' where not (::)~/:r[;1]'
        return q(
            '{[tab]'
            f'r:{{[tab; x] ({key_str}x; avg {val_str}tab[x])}}[tab;] each {query_str};'
            f'(,/) {{(enlist x 0)!(enlist x 1)}} each r{where_str}}}',
            tab
        )

    @api_return
    def median(self, axis: int = 0, numeric_only: bool = False):
        tab = self
        if 'Keyed' in str(type(tab)):
            tab = q('{(keys x) _ 0!x}', tab)
        if numeric_only:
            tab = _get_numeric_only_subtable(tab)

        key_str = '' if axis == 0 else '`$string '
        val_str = '' if axis == 0 else '"f"$value '
        query_str = 'cols tab' if axis == 0 else 'til count tab'
        where_str = ' where not (::)~/:r[;1]'
        return q(
            '{[tab]'
            f'r:{{[tab; x] ({key_str}x; med {val_str}tab[x])}}[tab;] each {query_str};'
            f'(,/) {{(enlist x 0)!(enlist x 1)}} each r{where_str}}}',
            tab
        )

    @api_return
    def mode(self, axis: int = 0, numeric_only: bool = False, dropna: bool = True):
        tab = self
        if 'Keyed' in str(type(tab)):
            tab = q('{(keys x) _ 0!x}', tab)
        if numeric_only:
            tab = _get_numeric_only_subtable(tab)
        x_str = 'x: x where not null x; ' if dropna else ''
        query_str = 'cols tab' if axis == 0 else 'til count tab'
        cols_str = 'tab[x]' if axis == 0 else 'value tab[x]'
        maxc_str = 'x[1]' if axis ==0 else 'raze x _ 0'
        cs_str = 'cols tab' if axis == 0 else '`idx,`$string each til count r[0][1]'
        m_str = '{1 _ raze x}' if axis == 0 else '{x: raze x; x iasc null x}'
        flip_m = 'flip ' if axis == 0 else ''
        mode_query = f'{{{x_str}(x l) where d=max d:1_deltas (l:where differ x),count x:asc x}}' \
            if numeric_only else f'{{{x_str}x where f=max f:@[0*i;i:x?x;+;1]}}'
        return q(
            '{[tab]'
            f'r:{{[tab; x] (x; {mode_query}'
            f'[{cols_str}])}}[tab;] each {query_str};'
            f'maxc: max {{count {maxc_str}}} each r;'
            'r:{[x; y] $[not y=t:count x 1;'
            '[qq: x 1; (x 0;(y - t){[z; t]z,z[t]}[;t]/qq)];'
            '(x 0; x 1)]}[;maxc] each r;'
            f'cs: {cs_str};'
            f'm: {m_str} each r;'
            f'cs !/: {flip_m}m}}',
            tab
        )

    @api_return
    def abs(self, numeric_only=False):
        tab = self
        if numeric_only:
            tab = _get_numeric_only_subtable(self)
        return q.abs(tab)

    @api_return
    def isin(self, values):
        tab = self
        key_table = 'KeyedTable' in str(type(tab))
        key_value = 'KeyedTable' in str(type(values))
        n_rows = 0
        false_dataframe_f = q("""{u:(cols x); 
                            v:(count[u],count[x])#0b; 
                            flip u!v}""")
        if key_value and not key_table:
            return false_dataframe_f(tab)
        if key_table:
            kcols = q.key(tab)
            if key_value:
                n_rows, tab = q("""{n_rows:max 0, count[x]-
                                            count rows:(key y) inter key x; 
                                            (n_rows;
                                               x each rows)}""", tab, values)
                values = q.value(values)
            else:
                tab = q.value(tab)
        dic_value, is_tab = q("""{$[98h = type x;
                                    (flip x; 1b);
                                    (x; 0b)]}""", values)
        if key_table and not key_value and is_tab:
            ftable = false_dataframe_f(tab)
        else:
            ftable = q("""{ [table; values; is_tab; n_rows]
                        flip (cols table)!
                        {[col_name; tab; values; v_is_tab; n_rows]
                            col: tab col_name;
                            ltype: .Q.ty col;
                            values: $[99h~type values; values col_name; values];
                            $[v_is_tab or ltype=" "; ;
                                    values@:where (lower ltype) = .Q.t abs type each values];
                            $[0 = count values;
                                        (n_rows + count[col])#0b;
                                        $[v_is_tab;
                                            $[any ltype = (" ";"C"); ~'; =]
                                            [mlen#col;mlen#values],
                                                (n_rows + max 0,count[col]-
                                                    mlen: min count[values],
                                                        count[col])#0b;
                                            any $[any ltype = (" ";"C"); ~/:\:; =\:][values;col]
                                            ]
                                ]}[; table; values; is_tab; n_rows]
                        each cols table}""", tab, dic_value, is_tab, n_rows)
        return ftable.set_index(kcols) if key_table else ftable

    @convert_result
    def all(self, axis=0, bool_only=False, skipna=True):
        res, cols = preparse_computations(self, axis, skipna, bool_only=bool_only)
        return (q('{"b"$x}', [all(x) for x in res]), cols)

    @convert_result
    def any(self, axis=0, bool_only=False, skipna=True):
        res, cols = preparse_computations(self, axis, skipna, bool_only=bool_only)
        return (q('{"b"$x}', [any(x) for x in res]), cols)

    @convert_result
    def max(self, axis=0, skipna=True, numeric_only=False):
        res, cols = preparse_computations(self, axis, skipna, numeric_only)
        return (q(
            '{[row] {$[11h=type x; {[x1; y1] $[x1 > y1; x1; y1]} over x; max x]} each row}',
            res
        ), cols)

    @convert_result
    def min(self, axis=0, skipna=True, numeric_only=False):
        res, cols = preparse_computations(self, axis, skipna, numeric_only)
        return (q(
            '{[row] {$[11h=type x; {[x1; y1] $[x1 < y1; x1; y1]} over x; min x]} each row}',
            res
        ), cols)

    @convert_result
    def prod(self, axis=0, skipna=True, numeric_only=False, min_count=0):
        res, cols = preparse_computations(self, axis, skipna, numeric_only)
        return (q(
            '{[row; minc] {$[y > 0; $[y>count[x]; 0N; prd x]; prd x]}[;minc] each row}',
            res,
            min_count
        ), cols)

    @convert_result
    def sum(self, axis=0, skipna=True, numeric_only=False, min_count=0):
        res, cols = preparse_computations(self, axis, skipna, numeric_only)
        return (q(
            '{[row; minc]'
            '{$[y > 0;'
            '$[y>count[x]; 0N; $[11h=type x; `$"" sv string x;sum x]];'
            '$[11h=type x; `$"" sv string x;sum x]]}[;minc] each row}',
            res,
            min_count
        ), cols)

    def agg(self, func, axis=0, *args, **kwargs): # noqa: C901
        if 'KeyedTable' in str(type(self)):
            raise NotImplementedError("'agg' method not presently supported for KeyedTable")
        if 'GroupbyTable' not in str(type(self)):
            if 0 == len(self):
                raise QError("Application of 'agg' method not supported for on tabular data with 0 rows") # noqa: E501
        keyname = q('()')
        data = q('()')
        if axis != 0:
            raise NotImplementedError('axis parameter only presently supported for axis=0')
        if isinstance(func, str):
            return getattr(self, func)()
        elif callable(func):
            return self.apply(func, *args, **kwargs)
        elif isinstance(func, list):
            for i in func:
                if isinstance(i, str):
                    keyname = q('{x,y}', keyname, i)
                    data = q('{x, enlist y}', data, getattr(self, i)())
                elif callable(i):
                    keyname = q('{x,y}', keyname, i.__name__)
                    data = q('{x, enlist y}', data, self.apply(i, *args, **kwargs))
            if 'GroupbyTable' in str(type(self)):
                return q('{x!y}', keyname, data)
        elif isinstance(func, dict):
            if 'GroupbyTable' in str(type(self)):
                raise NotImplementedError('Dictionary input func not presently supported for GroupbyTable') # noqa: E501
            data = q('{(flip enlist[`function]!enlist ())!'
                     'flip ($[1~count x;enlist;]x)!'
                     '$[1~count x;enlist;]count[x]#()}', self.keys())
            for key, value in func.items():
                data_name = [key]
                if isinstance(value, str):
                    valname = value
                    keyname = q('{x, y}', keyname, value)
                    exec_data = getattr(self[data_name], value)()
                elif callable(value):
                    valname = value.__name__
                    keyname = q('{x, y}', keyname, valname)
                    exec_data = self[data_name].apply(value, *args, **kwargs)
                else:
                    raise NotImplementedError(f"Unsupported type '{type(value)}' supplied as dictionary value") # noqa: E501
                data = q('{[x;y;z;k]x upsert(enlist enlist[`function]!enlist[k])!enlist z}',
                         data,
                         self.keys(),
                         exec_data,
                         valname)
            return data
        else:
            raise NotImplementedError(f"func type: {type(func)} unsupported")
        if 'GroupbyTable' in str(type(self)):
            return data
        else:
            return (q('{(flip enlist[`function]!enlist x)!y}', keyname, data))
