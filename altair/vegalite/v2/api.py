# -*- coding: utf-8 -*-

import warnings

import jsonschema
import six
import pandas as pd

from .schema import core, channels, mixins, Undefined, SCHEMA_URL

from .data import data_transformers, pipe
from ... import utils, expr
from .display import renderers, VEGALITE_VERSION, VEGAEMBED_VERSION, VEGA_VERSION
from .theme import themes

# ------------------------------------------------------------------------
# Data Utilities
def _prepare_data(data):
    """Convert input data to data for use within schema"""
    if data is Undefined:
        return data
    elif isinstance(data, (dict, core.Data, core.InlineData,
                         core.UrlData, core.NamedData)):
        return data
    elif isinstance(data, pd.DataFrame):
        return pipe(data, data_transformers.get())
    elif isinstance(data, six.string_types):
        return core.UrlData(data)
    else:
        warnings.warn("data of type {0} not recognized".format(type(data)))
        return data


# ------------------------------------------------------------------------
# Aliases & specializations
Bin = core.BinParams

@utils.use_signature(core.LookupData)
class LookupData(core.LookupData):
    def to_dict(self, *args, **kwargs):
        """Convert the chart to a dictionary suitable for JSON export"""
        copy = self.copy(ignore=['data'])
        copy.data = _prepare_data(copy.data)
        return super(LookupData, copy).to_dict(*args, **kwargs)


@utils.use_signature(core.FacetMapping)
class FacetMapping(core.FacetMapping):
    _class_is_valid_at_instantiation = False

    def to_dict(self, *args, **kwargs):
        copy = self.copy()
        context = kwargs.get('context', {})
        data = context.get('data', None)
        if isinstance(self.row, six.string_types):
            copy.row = core.FacetFieldDef(**utils.parse_shorthand(self.row, data))
        if isinstance(self.column, six.string_types):
            copy.column = core.FacetFieldDef(**utils.parse_shorthand(self.column, data))
        return super(FacetMapping, copy).to_dict(*args, **kwargs)


# ------------------------------------------------------------------------
# Encoding will contain channel objects that aren't valid at instantiation
core.EncodingWithFacet._class_is_valid_at_instantiation = False

# ------------------------------------------------------------------------
# These are parameters that are valid at the top level, but are not valid
# for specs that are within a composite chart
# (layer, hconcat, vconcat, facet, repeat)
TOPLEVEL_ONLY_KEYS = {'background', 'config', 'autosize', 'padding', '$schema'}


def _get_channels_mapping():
    mapping = {}
    for attr in dir(channels):
        cls = getattr(channels, attr)
        if isinstance(cls, type) and issubclass(cls, core.SchemaBase):
            mapping[cls] = attr.replace('Value', '').lower()
    return mapping


# -------------------------------------------------------------------------
# Tools for working with selections
class SelectionMapping(core.VegaLiteSchema):
    """A mapping of selection names to selection definitions.

    This is designed to match the schema of the "selection" property of
    top-level objects.
    """
    _schema = {
        'type': 'object',
        'additionalPropeties': {'$ref': '#/definitions/SelectionDef'}
    }
    _rootschema = core.Root._schema

    def __add__(self, other):
        if isinstance(other, SelectionMapping):
            copy = self.copy()
            copy._kwds.update(other._kwds)
            return copy
        else:
            return NotImplemented

    def __iadd__(self, other):
        if isinstance(other, SelectionMapping):
            self._kwds.update(other._kwds)
            return self
        else:
            return NotImplemented


class NamedSelection(SelectionMapping):
    """A SelectionMapping with a single named selection item"""
    _schema = {
        'type': 'object',
        'additionalPropeties': {'$ref': '#/definitions/SelectionDef'},
        'minProperties': 1, 'maxProperties': 1
    }
    _rootschema = core.Root._schema

    def _get_name(self):
        if len(self._kwds) != 1:
            raise ValueError("NamedSelection has multiple properties")
        return next(iter(self._kwds))

    def ref(self):
        """Return a selection reference to this object

        Examples
        --------
        >>> import altair as alt
        >>> sel = alt.selection_interval(name='interval')
        >>> sel.ref()
        {'selection': 'interval'}
        """
        return {"selection": self._get_name()}

    def __invert__(self):
        return core.SelectionNot(**{'not': self._get_name()})

    def __and__(self, other):
        if isinstance(other, NamedSelection):
            other = other._get_name()
        return core.SelectionAnd(**{'and': [self._get_name(), other]})

    def __or__(self, other):
        if isinstance(other, NamedSelection):
            other = other._get_name()
        return core.SelectionOr(**{'or': [self._get_name(), other]})

    def __add__(self, other):
        copy = SelectionMapping(**self._kwds)
        copy += other
        return copy

    def __iadd__(self, other):
        # this will be delegated to SelectionMapping
        return NotImplemented

# ------------------------------------------------------------------------
# Top-Level Functions

def value(value, **kwargs):
    """Specify a value for use in an encoding"""
    return dict(value=value, **kwargs)


def selection(name=None, type=Undefined, **kwds):
    """Create a named selection.

    Parameters
    ----------
    name : string (optional)
        The name of the selection. If not specified, a unique name will be
        created.
    type : string
        The type of the selection: one of ["interval", "single", or "multi"]
    **kwds :
        additional keywords will be used to construct a SelectionDef instance
        that controls the selection.

    Returns
    -------
    selection: NamedSelection
        The selection object that can be used in chart creation.
    """
    if name is None:
        name = "selector{0:03d}".format(selection.counter)
        selection.counter += 1
    return NamedSelection(**{name: core.SelectionDef(type=type, **kwds)})

selection.counter = 1

@utils.use_signature(core.IntervalSelection)
def selection_interval(**kwargs):
    """Create a selection with type='interval'"""
    return selection(type='interval', **kwargs)


@utils.use_signature(core.MultiSelection)
def selection_multi(**kwargs):
    """Create a selection with type='multi'"""
    return selection(type='multi', **kwargs)


@utils.use_signature(core.SingleSelection)
def selection_single(**kwargs):
    """Create a selection with type='single'"""
    return selection(type='single', **kwargs)


@utils.use_signature(core.VgBinding)
def binding(input, **kwargs):
    """A generic binding"""
    return core.VgBinding(input=input, **kwargs)


@utils.use_signature(core.VgCheckboxBinding)
def binding_checkbox(**kwargs):
    """A checkbox binding"""
    return core.VgCheckboxBinding(input='checkbox', **kwargs)


@utils.use_signature(core.VgRadioBinding)
def binding_radio(**kwargs):
    """A radio button binding"""
    return core.VgRadioBinding(input='radio', **kwargs)


@utils.use_signature(core.VgSelectBinding)
def binding_select(**kwargs):
    """A select binding"""
    return core.VgSelectBinding(input='select', **kwargs)


@utils.use_signature(core.VgRangeBinding)
def binding_range(**kwargs):
    """A range binding"""
    return core.VgRangeBinding(input='range', **kwargs)


def condition(predicate, if_true, if_false, **kwargs):
    """A conditional attribute or encoding

    Parameters
    ----------
    predicate: NamedSelection, LogicalOperandPredicate, expr.Expression, dict, or string
        the selection predicate or test predicate for the condition.
        if a string is passed, it will be treated as a test operand.
    if_true:
        the spec or object to use if the selection predicate is true
    if_false:
        the spec or object to use if the selection predicate is false
    **kwargs:
        additional keyword args are added to the resulting dict

    Returns
    -------
    spec: dict or VegaLiteSchema
        the spec that describes the condition
    """
    selection_predicates = (core.SelectionNot, core.SelectionOr,
                            core.SelectionAnd, core.SelectionOperand)
    test_predicates = (six.string_types, expr.Expression, core.Predicate,
                       core.LogicalOperandPredicate, core.LogicalNotPredicate,
                       core.LogicalOrPredicate, core.LogicalAndPredicate)

    if isinstance(predicate, NamedSelection):
        condition = {'selection': predicate._get_name()}
    elif isinstance(predicate, selection_predicates):
        condition = {'selection': predicate}
    elif isinstance(predicate, test_predicates):
        condition = {'test': predicate}
    elif isinstance(predicate, dict):
        condition = predicate
    else:
        raise NotImplementedError("condition predicate of type {0}"
                                  "".format(type(predicate)))

    if isinstance(if_true, core.SchemaBase):
        # convert to dict for now; the from_dict call below will wrap this
        # dict in the appropriate schema
        if_true = if_true.to_dict()
    elif isinstance(if_true, six.string_types):
        if_true = {'shorthand': if_true}
        if_true.update(kwargs)
    condition.update(if_true)

    if isinstance(if_false, core.SchemaBase):
        # For the selection, the channel definitions all allow selections
        # already. So use this SchemaBase wrapper if possible.
        selection = if_false.copy()
        selection.condition = condition
    elif isinstance(if_false, six.string_types):
        selection = {'condition': condition, 'shorthand': if_false}
        selection.update(kwargs)
    else:
        selection = dict(condition=condition, **if_false)

    return selection


# --------------------------------------------------------------------
# Top-level objects

class TopLevelMixin(mixins.ConfigMethodMixin):
    """Mixin for top-level chart objects such as Chart, LayeredChart, etc."""
    _class_is_valid_at_instantiation = False

    def to_dict(self, *args, **kwargs):
        """Convert the chart to a dictionary suitable for JSON export"""
        copy = self.copy()
        original_data = getattr(copy, 'data', Undefined)
        copy.data = _prepare_data(original_data)

        # We make use of two context markers:
        # - 'data' points to the data that should be referenced for column type
        #   inference.
        # - 'top_level' is a boolean flag that is assumed to be true; if it's
        #   true then a "$schema" arg is added to the dict.
        context = kwargs.get('context', {}).copy()

        is_top_level = context.get('top_level', True)
        context['top_level'] = False

        if original_data is not Undefined:
            context['data'] = original_data
        kwargs['context'] = context

        try:
            dct = super(TopLevelMixin, copy).to_dict(*args, **kwargs)
        except jsonschema.ValidationError:
            dct = None

        # If we hit an error, then re-convert with validate='deep' to get
        # a more useful traceback. We don't do this by default because it's
        # much slower in the case that there are no errors.
        if dct is None:
            kwargs['validate'] = 'deep'
            dct = super(TopLevelMixin, copy).to_dict(*args, **kwargs)

        if is_top_level:
            # since this is top-level we add $schema if it's missing
            if '$schema' not in dct:
                dct['$schema'] = SCHEMA_URL

            # apply theme from theme registry
            dct = utils.update_nested(themes.get(), dct, copy=True)

        return dct

    def savechart(self, fp, format=None, **kwargs):
        """Save a chart to file in a variety of formats

        Supported formats are json, html, png, svg

        Parameters
        ----------
        fp : string filename or file-like object
            file in which to write the chart.
        format : string (optional)
            the format to write: one of ['json', 'html', 'png', 'svg'].
            If not specified, the format will be determined from the filename.
        **kwargs :
            Additional keyword arguments are passed to the output method
            associated with the specified format.
        """
        warnings.warn(
            "Chart.savechart is deprecated in favor of Chart.save",
            DeprecationWarning
        )
        return self.save(fp, format=None, **kwargs)

    def save(self, fp, format=None, **kwargs):
        """Save a chart to file in a variety of formats

        Supported formats are json, html, png, svg

        Parameters
        ----------
        fp : string filename or file-like object
            file in which to write the chart.
        format : string (optional)
            the format to write: one of ['json', 'html', 'png', 'svg'].
            If not specified, the format will be determined from the filename.
        **kwargs :
            Additional keyword arguments are passed to the output method
            associated with the specified format.
        """
        from ...utils.save import save
        return save(self, fp=fp, format=format,
                         vegalite_version=VEGALITE_VERSION,
                         vega_version=VEGA_VERSION,
                         vegaembed_version=VEGAEMBED_VERSION,
                         **kwargs)

    # Layering and stacking

    def __add__(self, other):
        return LayerChart(layer=[self, other])

    def __and__(self, other):
        return VConcatChart(vconcat=[self, other])

    def __or__(self, other):
        return HConcatChart(hconcat=[self, other])

    # Display-related methods

    def _repr_mimebundle_(self, include, exclude):
        """Return a MIME bundle for display in Jupyter frontends."""
        # Catch errors explicitly to get around issues in Jupyter frontend
        # see https://github.com/ipython/ipython/issues/11038
        try:
            dct = self.to_dict()
        except Exception:
            utils.display_traceback(in_ipython=True)
            return {}
        else:
            return renderers.get()(dct)

    def repeat(self, row=Undefined, column=Undefined, **kwargs):
        """Return a RepeatChart built from the chart

        Fields within the chart can be set to correspond to the row or
        column using `alt.repeat('row')` and `alt.repeat('column')`.

        Parameters
        ----------
        row : list
            a list of data column names to be mapped to the row facet
        column : list
            a list of data column names to be mapped to the column facet

        Returns
        -------
        chart : RepeatChart
            a repeated chart.
        """
        repeat = core.Repeat(row=row, column=column)
        return RepeatChart(spec=self, repeat=repeat, **kwargs)

    def properties(self, **kwargs):
        """Set top-level properties of the Chart.

        Argument names and types are the same as class initialization.
        """
        copy = self.copy(deep=True, ignore=['data'])
        for key, val in kwargs.items():
            setattr(copy, key, val)
        return copy

    def project(self, type='mercator', center=Undefined, clipAngle=Undefined, clipExtent=Undefined,
                coefficient=Undefined, distance=Undefined, fraction=Undefined, lobes=Undefined,
                parallel=Undefined, precision=Undefined, radius=Undefined, ratio=Undefined,
                rotate=Undefined, spacing=Undefined, tilt=Undefined, **kwds):
        """Add a geographic projection to the chartself.

        This is generally used either with ``mark_geoshape`` or with the
        ``latitude``/``longitude`` encodings.

        Available projection types are
        ['albers', 'albersUsa', 'azimuthalEqualArea', 'azimuthalEquidistant',
         'conicConformal', 'conicEqualArea', 'conicEquidistant', 'equirectangular',
         'gnomonic', 'mercator', 'orthographic', 'stereographic', 'transverseMercator']

        Attributes
        ----------
        type : ProjectionType
            The cartographic projection to use. This value is case-insensitive, for example
            `"albers"` and `"Albers"` indicate the same projection type. You can find all valid
            projection types [in the
            documentation](https://vega.github.io/vega-lite/docs/projection.html#projection-types).
              __Default value:__ `mercator`
        center : List(float)
            Sets the projection’s center to the specified center, a two-element array of
            longitude and latitude in degrees.  __Default value:__ `[0, 0]`
        clipAngle : float
            Sets the projection’s clipping circle radius to the specified angle in degrees. If
            `null`, switches to [antimeridian](http://bl.ocks.org/mbostock/3788999) cutting
            rather than small-circle clipping.
        clipExtent : List(List(float))
            Sets the projection’s viewport clip extent to the specified bounds in pixels. The
            extent bounds are specified as an array `[[x0, y0], [x1, y1]]`, where `x0` is the
            left-side of the viewport, `y0` is the top, `x1` is the right and `y1` is the
            bottom. If `null`, no viewport clipping is performed.
        coefficient : float

        distance : float

        fraction : float

        lobes : float

        parallel : float

        precision : Mapping(required=[length])
            Sets the threshold for the projection’s [adaptive
            resampling](http://bl.ocks.org/mbostock/3795544) to the specified value in pixels.
            This value corresponds to the [Douglas–Peucker
            distance](http://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm).
             If precision is not specified, returns the projection’s current resampling
            precision which defaults to `√0.5 ≅ 0.70710…`.
        radius : float

        ratio : float

        rotate : List(float)
            Sets the projection’s three-axis rotation to the specified angles, which must be a
            two- or three-element array of numbers [`lambda`, `phi`, `gamma`] specifying the
            rotation angles in degrees about each spherical axis. (These correspond to yaw,
            pitch and roll.)  __Default value:__ `[0, 0, 0]`
        spacing : float

        tilt : float
        """
        projection = core.Projection(center=center, clipAngle=clipAngle, clipExtent=clipExtent,
                                     coefficient=coefficient, distance=distance, fraction=fraction,
                                     lobes=lobes, parallel=parallel, precision=precision,
                                     radius=radius, ratio=ratio, rotate=rotate, spacing=spacing,
                                     tilt=tilt, type=type, **kwds)
        return self.properties(projection=projection)

    def _add_transform(self, *transforms):
        """Copy the chart and add specified transforms to chart.transform"""
        copy = self.copy()
        if copy.transform is Undefined:
            copy.transform = list(transforms)
        else:
            copy.transform.extend(transforms)
        return copy

    def transform_aggregate(self, aggregate=Undefined, groupby=Undefined, **kwds):
        """
        Add an AggregateTransform to the schema.

        Parameters
        ----------
        aggregate : List(AggregatedFieldDef)
            Array of objects that define fields to aggregate.
        groupby : List(string)
            The data fields to group by. If not specified, a single group
            containing all data objects will be used.
        **kwds :
            additional keywords are converted to aggregates using standard
            shorthand parsing.

        Returns
        -------
        self : Chart object
            returns chart to allow for chaining

        Examples
        --------
        The aggregate transform allows you to specify transforms directly using
        the same shorthand syntax as used in encodings:

        >>> import altair as alt
        >>> chart1 = alt.Chart().transform_aggregate(
        ...     mean_acc='mean(Acceleration)',
        ...     groupby=['Origin']
        ... )
        >>> print(chart1.transform[0].to_json())  # doctest: +NORMALIZE_WHITESPACE
        {
          "aggregate": [
            {
              "as": "mean_acc",
              "field": "Acceleration",
              "op": "mean"
            }
          ],
          "groupby": [
            "Origin"
          ]
        }

        It also supports including AggregatedFieldDef instances or dicts directly,
        so you can create the above transform like this:

        >>> chart2 = alt.Chart().transform_aggregate(
        ...     [alt.AggregatedFieldDef(field='Acceleration', op='mean',
        ...                             **{'as': 'mean_acc'})],
        ...     groupby=['Origin']
        ... )
        >>> chart2.transform == chart1.transform
        True

        See Also
        --------
        alt.AggregateTransform : underlying transform object
        """
        if aggregate is Undefined:
            aggregate = []
        for key, val in kwds.items():
            parsed = utils.parse_shorthand(val)
            dct = {'as': key,
                   'field': parsed.get('field', Undefined),
                   'op': parsed.get('aggregate', Undefined)}
            aggregate.append(core.AggregatedFieldDef(**dct))
        return self._add_transform(core.AggregateTransform(aggregate=aggregate,
                                                           groupby=groupby))

    def transform_bin(self, as_=Undefined, field=Undefined, bin=True, **kwargs):
        """
        Add a BinTransform to the schema.

        Attributes
        ----------
        as_ : string
            The output fields at which to write the start and end bin values.
        bin : anyOf(boolean, BinParams)
            An object indicating bin properties, or simply `true` for using
            default bin parameters.
        field : string
            The data field to bin.

        Returns
        -------
        self : Chart object
            returns chart to allow for chaining

        Examples
        --------
        >>> import altair as alt
        >>> chart = alt.Chart().transform_bin("x_binned", "x")
        >>> chart.transform[0]
        BinTransform({
          as: 'x_binned',
          bin: True,
          field: 'x'
        })

        >>> chart = alt.Chart().transform_bin("x_binned", "x",
        ...                                   bin=alt.Bin(maxbins=10))
        >>> chart.transform[0]
        BinTransform({
          as: 'x_binned',
          bin: BinParams({
            maxbins: 10
          }),
          field: 'x'
        })

        See Also
        --------
        alt.BinTransform : underlying transform object
        """
        if as_ is not Undefined:
            if 'as' in kwargs:
                raise ValueError("transform_bin: both 'as_' and 'as' passed as arguments.")
            kwargs['as'] = as_
        kwargs['bin'] = bin
        kwargs['field'] = field
        return self._add_transform(core.BinTransform(**kwargs))

    def transform_calculate(self, as_=Undefined, calculate=Undefined, **kwargs):
        """
        Add a CalculateTransform to the schema.

        Attributes
        ----------
        as_ : string
            The output fields at which to write the start and end bin values.
        calculate : string or alt.expr expression
            An expression string. Use the variable `datum` to refer to the
            current data object.
        **kwargs
            transforms can also be passed by keyword argument; see Examples

        Returns
        -------
        self : Chart object
            returns chart to allow for chaining

        Examples
        --------
        >>> import altair as alt
        >>> from altair import datum, expr

        >>> chart = alt.Chart().transform_calculate(y = 2 * expr.sin(datum.x))
        >>> chart.transform[0]
        CalculateTransform({
          as: 'y',
          calculate: (2 * sin(datum.x))
        })

        It's also possible to pass the ``CalculateTransform`` arguments directly:

        >>> kwds = {'as': 'y', 'calculate': '2 * sin(datum.x)'}
        >>> chart = alt.Chart().transform_calculate(**kwds)
        >>> chart.transform[0]
        CalculateTransform({
          as: 'y',
          calculate: '2 * sin(datum.x)'
        })

        As the first form is easier to write and understand, that is the
        recommended method.

        See Also
        --------
        alt.CalculateTransform : underlying transform object
        """
        if as_ is Undefined:
            as_ = kwargs.pop('as', Undefined)
        else:
            if 'as' in kwargs:
                raise ValueError("transform_calculate: both 'as_' and 'as' passed as arguments.")
        if as_ is not Undefined or calculate is not Undefined:
            dct = {'as': as_, 'calculate': calculate}
            self = self._add_transform(core.CalculateTransform(**dct))
        for as_, calculate in kwargs.items():
            dct = {'as': as_, 'calculate': calculate}
            self = self._add_transform(core.CalculateTransform(**dct))
        return self

    def transform_filter(self, filter, **kwargs):
        """
        Add a FilterTransform to the schema.

        Attributes
        ----------
        filter : a filter expression
            The `filter` property must be one of the predicate definitions:
            (1) a string or alt.expr expression
            (2) a range predicate
            (3) a selection predicate
            (4) a logical operand combining (1)-(3)
            (5) a NamedSelection object

        Returns
        -------
        self : Chart object
            returns chart to allow for chaining

        See Also
        --------
        alt.FilterTransform : underlying transform object
        """
        if isinstance(filter, NamedSelection):
            filter = filter.ref()
        return self._add_transform(core.FilterTransform(filter=filter, **kwargs))

    def transform_lookup(self, as_=Undefined, from_=Undefined, lookup=Undefined, default=Undefined, **kwargs):
        """Add a LookupTransform to the schema

        Attributes
        ----------
        as_ : string or List(string)
            The field or fields for storing the computed formula value.
            If `from.fields` is specified, the transform will use the same names for `as`.
            If `from.fields` is not specified, `as` has to be a string and we put
            the whole object into the data under the specified name.
        from_ : LookupData
            Secondary data reference.
        lookup : string
            Key in primary data source.
        default : string
            The default value to use if lookup fails

        Returns
        -------
        self : Chart object
            returns chart to allow for chaining

        See Also
        --------
        alt.LookupTransform : underlying transform object
        """
        if as_ is not Undefined:
            if 'as' in kwargs:
                raise ValueError("transform_lookup: both 'as_' and 'as' passed as arguments.")
            kwargs['as'] = as_
        if from_ is not Undefined:
            if 'from' in kwargs:
                raise ValueError("transform_lookup: both 'from_' and 'from' passed as arguments.")
            kwargs['from'] = from_
        kwargs['lookup'] = lookup
        kwargs['default'] = default
        return self._add_transform(core.LookupTransform(**kwargs))

    def transform_timeunit(self, as_=Undefined, field=Undefined, timeUnit=Undefined, **kwargs):
        """
        Add a TimeUnitTransform to the schema.

        Attributes
        ----------
        as_ : string
            The output fields at which to write the start and end bin values.
        field : string
            The data field to apply time unit.
        timeUnit : TimeUnit
            The timeUnit.

        Returns
        -------
        self : Chart object
            returns chart to allow for chaining

        See Also
        --------
        alt.TimeUnitTransform : underlying transform object
        """
        if as_ is not Undefined:
            if 'as' in kwargs:
                raise ValueError("transform_timeunit: both 'as_' and 'as' passed as arguments.")
            kwargs['as'] = as_
        kwargs['field'] = field
        kwargs['timeUnit'] = timeUnit
        return self._add_transform(core.TimeUnitTransform(**kwargs))

    @utils.use_signature(core.Resolve)
    def _set_resolve(self, **kwargs):
        """Copy the chart and update the resolve property with kwargs"""
        if not hasattr(self, 'resolve'):
            raise ValueError("{0} object has no attribute "
                             "'resolve'".format(self.__class__))
        copy = self.copy()
        if copy.resolve is Undefined:
            copy.resolve = core.Resolve()
        for key, val in kwargs.items():
            copy.resolve[key] = val
        return copy

    @utils.use_signature(core.AxisResolveMap)
    def resolve_axis(self, *args, **kwargs):
        return self._set_resolve(axis=core.AxisResolveMap(*args, **kwargs))

    @utils.use_signature(core.LegendResolveMap)
    def resolve_legend(self, *args, **kwargs):
        return self._set_resolve(legend=core.LegendResolveMap(*args, **kwargs))

    @utils.use_signature(core.ScaleResolveMap)
    def resolve_scale(self, *args, **kwargs):
        return self._set_resolve(scale=core.ScaleResolveMap(*args, **kwargs))


class EncodingMixin(object):
    @utils.use_signature(core.EncodingWithFacet)
    def encode(self, *args, **kwargs):
        # First convert args to kwargs by inferring the class from the argument
        if args:
            mapping = _get_channels_mapping()
            for arg in args:
                encoding = mapping.get(type(arg), None)
                if encoding is None:
                    raise NotImplementedError("non-keyword arg of type {0}"
                                              "".format(type(arg)))
                if encoding in kwargs:
                    raise ValueError("encode: encoding {0} specified twice"
                                     "".format(encoding))
                kwargs[encoding] = arg

        def _wrap_in_channel_class(obj, prop):
            clsname = prop.title()

            if isinstance(obj, core.SchemaBase):
                return obj

            if isinstance(obj, six.string_types):
                obj = {'shorthand': obj}

            if 'value' in obj:
                clsname += 'Value'

            try:
                cls = getattr(channels, clsname)
            except AttributeError:
                raise ValueError("Unrecognized encoding channel '{0}'".format(prop))

            try:
                # Don't force validation here; some objects won't be valid until
                # they're created in the context of a chart.
                return cls.from_dict(obj, validate=False)
            except jsonschema.ValidationError:
                # our attempts at finding the correct class have failed
                return obj

        for prop, obj in list(kwargs.items()):
            try:
                condition = obj['condition']
            except (KeyError, TypeError):
                pass
            else:
                if condition is not Undefined:
                    obj['condition'] = _wrap_in_channel_class(condition, prop)
            kwargs[prop] = _wrap_in_channel_class(obj, prop)


        copy = self.copy(deep=True, ignore=['data'])

        # get a copy of the dict representation of the previous encoding
        encoding = copy.encoding
        if encoding is Undefined:
            encoding = {}
        elif isinstance(encoding, dict):
            pass
        else:
            encoding = {k: v for k, v in encoding._kwds.items()
                        if v is not Undefined}

        # update with the new encodings, and apply them to the copy
        encoding.update(kwargs)
        copy.encoding = core.EncodingWithFacet(**encoding)
        return copy


class Chart(TopLevelMixin, EncodingMixin, mixins.MarkMethodMixin,
            core.TopLevelFacetedUnitSpec):
    """Create a basic Altair/Vega-Lite chart.

    Although it is possible to set all Chart properties as constructor attributes,
    it is more idiomatic to use methods such as ``mark_point()``, ``encode()``,
    ``transform_filter()``, ``properties()``, etc. See Altair's documentation
    for details and examples: http://altair-viz.github.io/.

    Attributes
    ----------
    data : Data
        An object describing the data source
    mark : AnyMark
        A string describing the mark type (one of `"bar"`, `"circle"`, `"square"`, `"tick"`,
         `"line"`, * `"area"`, `"point"`, `"rule"`, `"geoshape"`, and `"text"`) or a
         MarkDef object.
    encoding : EncodingWithFacet
        A key-value mapping between encoding channels and definition of fields.
    autosize : anyOf(AutosizeType, AutoSizeParams)
        Sets how the visualization size should be determined. If a string, should be one of
        `"pad"`, `"fit"` or `"none"`. Object values can additionally specify parameters for
        content sizing and automatic resizing. `"fit"` is only supported for single and
        layered views that don't use `rangeStep`.  __Default value__: `pad`
    background : string
        CSS color property to use as the background of visualization.  __Default value:__
        none (transparent)
    config : Config
        Vega-Lite configuration object.  This property can only be defined at the top-level
        of a specification.
    description : string
        Description of this mark for commenting purpose.
    height : float
        The height of a visualization.
    name : string
        Name of the visualization for later reference.
    padding : Padding
        The default visualization padding, in pixels, from the edge of the visualization
        canvas to the data rectangle.  If a number, specifies padding for all sides. If an
        object, the value should have the format `{"left": 5, "top": 5, "right": 5,
        "bottom": 5}` to specify padding for each side of the visualization.  __Default
        value__: `5`
    projection : Projection
        An object defining properties of geographic projection.  Works with `"geoshape"`
        marks and `"point"` or `"line"` marks that have a channel (one or more of `"X"`,
        `"X2"`, `"Y"`, `"Y2"`) with type `"latitude"`, or `"longitude"`.
    selection : Mapping(required=[])
        A key-value mapping between selection names and definitions.
    title : anyOf(string, TitleParams)
        Title for the plot.
    transform : List(Transform)
        An array of data transformations such as filter and new field calculation.
    width : float
        The width of a visualization.
    """
    def __init__(self, data=Undefined, encoding=Undefined, mark=Undefined,
                 width=Undefined, height=Undefined, **kwargs):
        super(Chart, self).__init__(data=data, encoding=encoding, mark=mark,
                                    width=width, height=height, **kwargs)

    @classmethod
    def from_dict(cls, dct, validate=True):
        # First try from_dict for the Chart type
        try:
            return super(Chart, cls).from_dict(dct, validate=validate)
        except jsonschema.ValidationError:
            pass

        # If this fails, try with all other top level types
        for class_ in TopLevelMixin.__subclasses__():
            if class_ is Chart:
                continue
            try:
                return class_.from_dict(dct, validate=validate)
            except jsonschema.ValidationError:
                pass

        # As a last resort, try using the Root vegalite object
        return core.Root.from_dict(dct, validate)

    def interactive(self, name=None, bind_x=True, bind_y=True):
        """Make chart axes scales interactive

        Parameters
        ----------
        name : string
            The selection name to use for the axes scales. This name should be
            unique among all selections within the chart.
        bind_x : boolean, default True
            If true, then bind the interactive scales to the x-axis
        bind_y : boolean, default True
            If true, then bind the interactive scales to the y-axis

        Returns
        -------
        chart :
            copy of self, with interactive axes added
        """
        encodings = []
        if bind_x:
            encodings.append('x')
        if bind_y:
            encodings.append('y')
        copy = self.copy(deep=True, ignore=['data'])

        if copy.selection is Undefined:
            copy.selection = SelectionMapping()
        if isinstance(copy.selection, dict):
            copy.selection = SelectionMapping(**copy.selection)
        copy.selection += selection(type='interval', bind='scales',
                                    encodings=encodings)
        return copy

    def facet(self, row=Undefined, column=Undefined, data=Undefined, **kwargs):
        """Create a facet chart from the current chart.

        Faceted charts require data to be specified at the top level; if data
        is not specified, the data from the current chart will be used at the
        top level.
        """
        if data is Undefined:
            data = self.data
            self = self.copy()
            self.data = Undefined
        return FacetChart(spec=self, facet=FacetMapping(row=row, column=column),
                          data=data, **kwargs)


def _check_if_valid_subspec(spec, classname):
    """Check if the spec is a valid sub-spec.

    If it is not, then raise a ValueError
    """
    err = ('Objects with "{0}" attribute cannot be used within {1}. '
           'Consider defining the {0} attribute in the {1} object instead.')

    for attr in TOPLEVEL_ONLY_KEYS:
        if isinstance(spec, core.SchemaBase):
            val = getattr(spec, attr, Undefined)
        else:
            val = spec.get(attr, Undefined)
        if val is not Undefined:
            raise ValueError(err.format(attr, classname))


@utils.use_signature(core.TopLevelRepeatSpec)
class RepeatChart(TopLevelMixin, core.TopLevelRepeatSpec):
    """A chart repeated across rows and columns with small changes"""
    def __init__(self, spec=Undefined, data=Undefined, repeat=Undefined, **kwargs):
        _check_if_valid_subspec(spec, 'RepeatChart')
        super(RepeatChart, self).__init__(spec=spec, data=data, repeat=repeat, **kwargs)

    def interactive(self, name=None, bind_x=True, bind_y=True):
        """Make chart axes scales interactive

        Parameters
        ----------
        name : string
            The selection name to use for the axes scales. This name should be
            unique among all selections within the chart.
        bind_x : boolean, default True
            If true, then bind the interactive scales to the x-axis
        bind_y : boolean, default True
            If true, then bind the interactive scales to the y-axis

        Returns
        -------
        chart :
            copy of self, with interactive axes added
        """
        copy = self.copy()
        copy.spec = copy.spec.interactive(name=name, bind_x=bind_x, bind_y=bind_y)
        return copy


def repeat(repeater):
    """Tie a channel to the row or column within a repeated chart

    The output of this should be passed to the ``field`` attribute of
    a channel.

    Parameters
    ----------
    repeater : {'row'|'column'}
        The repeater to tie the field to.

    Returns
    -------
    repeat : RepeatRef object
    """
    assert repeater in ['row', 'column']
    return core.RepeatRef(repeat=repeater)


@utils.use_signature(core.TopLevelHConcatSpec)
class HConcatChart(TopLevelMixin, core.TopLevelHConcatSpec):
    """A chart with horizontally-concatenated facets"""
    def __init__(self, hconcat=(), **kwargs):
        # TODO: move common data to top level?
        for spec in hconcat:
            _check_if_valid_subspec(spec, 'HConcatChart')
        super(HConcatChart, self).__init__(hconcat=list(hconcat), **kwargs)

    def __ior__(self, other):
        _check_if_valid_subspec(other, 'HConcatChart')
        self.hconcat.append(other)
        return self

    def __or__(self, other):
        _check_if_valid_subspec(other, 'HConcatChart')
        copy = self.copy()
        copy.hconcat.append(other)
        return copy

    # TODO: think about the most useful class API here


def hconcat(*charts, **kwargs):
    """Concatenate charts horizontally"""
    return HConcatChart(hconcat=charts, **kwargs)


@utils.use_signature(core.TopLevelVConcatSpec)
class VConcatChart(TopLevelMixin, core.TopLevelVConcatSpec):
    """A chart with vertically-concatenated facets"""
    def __init__(self, vconcat=(), **kwargs):
        # TODO: move common data to top level?
        for spec in vconcat:
            _check_if_valid_subspec(spec, 'VConcatChart')
        super(VConcatChart, self).__init__(vconcat=list(vconcat), **kwargs)

    def __iand__(self, other):
        _check_if_valid_subspec(other, 'VConcatChart')
        self.vconcat.append(other)
        return self

    def __and__(self, other):
        _check_if_valid_subspec(other, 'VConcatChart')
        copy = self.copy()
        copy.vconcat.append(other)
        return copy

    # TODO: think about the most useful class API here


def vconcat(*charts, **kwargs):
    """Concatenate charts vertically"""
    return VConcatChart(vconcat=charts, **kwargs)


@utils.use_signature(core.TopLevelLayerSpec)
class LayerChart(TopLevelMixin, EncodingMixin, core.TopLevelLayerSpec):
    """A Chart with layers within a single panel"""
    def __init__(self, data=Undefined, layer=(), **kwargs):
        # TODO: move common data to top level?
        # TODO: check for conflicting interaction
        for spec in layer:
            _check_if_valid_subspec(spec, 'LayerChart')
        super(LayerChart, self).__init__(data=data, layer=list(layer), **kwargs)

    def __iadd__(self, other):
        _check_if_valid_subspec(other, 'LayerChart')
        self.layer.append(other)
        return self

    def __add__(self, other):
        copy = self.copy()
        copy.layer.append(other)
        return copy

    def add_layers(self, *layers):
        copy = self.copy()
        for layer in layers:
            copy += layer
        return copy

    def interactive(self, name=None, bind_x=True, bind_y=True):
        """Make chart axes scales interactive

        Parameters
        ----------
        name : string
            The selection name to use for the axes scales. This name should be
            unique among all selections within the chart.
        bind_x : boolean, default True
            If true, then bind the interactive scales to the x-axis
        bind_y : boolean, default True
            If true, then bind the interactive scales to the y-axis

        Returns
        -------
        chart :
            copy of self, with interactive axes added
        """
        if not self.layer:
            raise ValueError("LayerChart: cannot call interactive() until a "
                             "layer is defined")
        copy = self.copy()
        copy.layer[0] = copy.layer[0].interactive(name=name, bind_x=bind_x, bind_y=bind_y)
        return copy

    def facet(self, row=Undefined, column=Undefined, data=Undefined, **kwargs):
        """Create a facet chart from the current chart.

        Faceted charts require data to be specified at the top level; if data
        is not specified, the data from the current chart will be used at the
        top level.
        """
        if data is Undefined:
            data = self.data
            self = self.copy()
            self.data = Undefined
        return FacetChart(spec=self, facet=FacetMapping(row=row, column=column),
                          data=data, **kwargs)


def layer(*charts, **kwargs):
    """layer multiple charts"""
    return LayerChart(layer=charts, **kwargs)


@utils.use_signature(core.TopLevelFacetSpec)
class FacetChart(TopLevelMixin, core.TopLevelFacetSpec):
    """A Chart with layers within a single panel"""
    def __init__(self, spec, facet=Undefined, **kwargs):
        _check_if_valid_subspec(spec, 'FacetChart')
        super(FacetChart, self).__init__(spec=spec, facet=facet, **kwargs)

    def interactive(self, name=None, bind_x=True, bind_y=True):
        """Make chart axes scales interactive

        Parameters
        ----------
        name : string
            The selection name to use for the axes scales. This name should be
            unique among all selections within the chart.
        bind_x : boolean, default True
            If true, then bind the interactive scales to the x-axis
        bind_y : boolean, default True
            If true, then bind the interactive scales to the y-axis

        Returns
        -------
        chart :
            copy of self, with interactive axes added
        """
        copy = self.copy()
        copy.spec = copy.spec.interactive(name=name, bind_x=bind_x, bind_y=bind_y)
        return copy


def topo_feature(url, feature, **kwargs):
    """A convenience function for extracting features from a topojson url

    Parameters
    ----------
    url : string
        An URL from which to load the data set.

    feature : string
        The name of the TopoJSON object set to convert to a GeoJSON feature collection. For
        example, in a map of the world, there may be an object set named `"countries"`.
        Using the feature property, we can extract this set and generate a GeoJSON feature
        object for each country.

    **kwargs :
        additional keywords passed to TopoDataFormat
    """
    return core.UrlData(url=url, format=core.TopoDataFormat(type='topojson',
                                                         feature=feature, **kwargs))
