# coding=utf-8
"""
Source extract from
https://raw.githubusercontent.com/modlinltd/ModelAdmin-Utils/master/modeladmin_utils/mixins/search.py
"""

import logging
import operator
import warnings
from collections import defaultdict, Iterable
from functools import reduce

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q
from django.utils.functional import cached_property
from xadmin.util import lookup_needs_distinct

logger = logging.getLogger('xplugin_generic_search.search')


def _get_opts(model):
    """Return meta options from model"""
    return model._meta


def get_generic_field(model, field_name):
    """
    Find the given generic_field name in the given model and verify
    it is a GenericForeignKey, otherwise raise an Exeption.
    """
    for field in _get_opts(model).virtual_fields:
        if field.name == field_name:
            if not isinstance(field, GenericForeignKey):
                raise Exception(
                    'Given field %s is not an instance of '
                    'GenericForeignKey' % field_name)
            return field


class GenericSearchMixin(object):
    """
    Overrides the ModelAdmin.get_search_results method to allow searching
    through a generic relation fields.

    For quick set up, simply use a GenericForeignKey field name as the prefix
    in 'search_fields'.

    E.g: for a field named 'related_to' you can use the following:
    search_fields = ('related_to__fname', 'related_to__email', ...)

    Optionally, you may define 'related_search_mapping' in the ModelAdmin
    to explicitly define a generic field's object id and content types
    (this is useful to limit the content types).

    Notes:
    * Required Django > 1.6
    * Currently assumes id of related objects are unique across all models
    """

    def __init__(self, model, search_fields, related_search_mapping=None):
        if related_search_mapping is None:
            related_search_mapping = {}
        self.model = model
        self.search_fields = search_fields
        self.related_search_mapping = related_search_mapping

    @cached_property
    def opts(self):
        return _get_opts(self.model)

    @staticmethod
    def _generate_q_object(search_term, orm_lookups):
        """
        Generate Or'ed queries from orm_lookups (fields)
        and every bit of the search_term (query).
        """
        q = Q()
        for bit in search_term.split():
            or_queries = [Q(**{orm_lookup: bit})
                          for orm_lookup in orm_lookups]
            if or_queries:
                q = (q & reduce(operator.or_, or_queries))
        return q

    @staticmethod
    def _construct_search(field_name):
        """
        Parse field_name to allow advanced searches using the
        prefixes: '^', '=', '@' and no prefix (default)
        """

        # Apply keyword searches.
        if field_name.startswith('^'):
            return "%s__istartswith" % field_name[1:]
        elif field_name.startswith('='):
            return "%s__iexact" % field_name[1:]
        elif field_name.startswith('@'):
            return "%s__search" % field_name[1:]
        else:
            return "%s__icontains" % field_name

    @staticmethod
    def _get_object_id(model, generic_field):
        """
        Return the foreign key field for a given GenericForeignKey
        in a given model
        """
        logger.debug('related_search_mapping did not define object_id, '
                     'attempting to find using GenericForeignKey %s in '
                     'model %s', generic_field, model)
        field = get_generic_field(model, generic_field)
        if field:
            return field.fk_field
        raise Exception('Given field %s does not exist in registered model'
                        ' %s and no object_id provided' % (
                            generic_field, model))

    @staticmethod
    def _get_content_types(model, generic_field):
        """
        Return the content types allowed for a given GenericForeignKey
        in a given model
        """
        logger.debug('related_search_mapping did not define ctypes, '
                     'attempting to find using GenericForeignKey %s in '
                     'model %s', generic_field, model)
        field = get_generic_field(model, generic_field)
        if field:
            return field.ct_field
        raise Exception('Given field %s does not exist in registered model'
                        ' %s and no object_id provided' % (
                            generic_field, model))

    @staticmethod
    def _get_ctype_models(ctypes):
        """
        Gets model classes from the passed argument, which can be:

        a. a dict which can be extrapolated into a query filter.
        b. a Q object which can be passed to a query filter.
        c. an iterable of 2 element tuples as (app_label, model)
        """

        def get_ctype_model(value):
            app_label, model = value.split('.', 1)
            return ContentType.objects.get(app_label=app_label, model=model).model_class()

        def is_ctype_string(value):
            return isinstance(value, str) and '.' in value

        if isinstance(ctypes, dict):
            if not ctypes:
                warnings.warn("""
This is a very inefficient query! Each search argument is going to query
all model classes. Please limit ContentType choices the FK if possible,
or define a 'related_search_mapping' argument which limits the ctypes.""")
            return [ct.model_class()
                    for ct in ContentType.objects.filter(**ctypes)]
        elif is_ctype_string(ctypes):
            return [get_ctype_model(ctypes)]
        elif isinstance(ctypes, Q):
            return [ct.model_class()
                    for ct in ContentType.objects.filter(ctypes)]
        elif isinstance(ctypes, Iterable):
            models = []
            for ctype in ctypes:
                if is_ctype_string(ctype):
                    models.append(get_ctype_model(ctype))
                else:
                    app_label, model = ctype
                    models.append(
                        ContentType.objects.get(app_label=app_label, model=model).model_class()
                    )
            return models
        raise Exception("Invalid argument passed, must be one of: "
                        "<dict>, <Q>, <iterable of 2 elem. tuples>")

    def get_related_items(self, search_term, fields_mapping):
        """
        Takes a dict of {generic_field_name: list_of_inner_Fields}, performs
        the query on the related object models (using defined or calculated
        content types) and returns the ids of the result objects.
        """
        related_items = []
        for rel_field, fields in fields_mapping.items():
            object_id_field = self._get_object_id(self.model, rel_field)
            content_type_field = self._get_content_types(self.model, rel_field)
            models = self._get_ctype_models(self.related_search_mapping[rel_field])
            for model in models:
                lookup_fields = []
                for lookup_field in fields:
                    # Checks if the model has the field before the filter.
                    field_name = lookup_field.split("__", 1)[0]
                    try:
                        _get_opts(model).get_field(field_name)
                        lookup_fields.append(lookup_field)
                    except FieldDoesNotExist:
                        continue
                query = self._generate_q_object(search_term, lookup_fields)
                if not query:
                    continue
                related_items.append({
                    'object_ids': {
                        'field': object_id_field,
                        'values': list(model.objects.filter(query).values_list('pk', flat=True)),
                    },
                    'content_type': {
                        'field': content_type_field,
                        'value': ContentType.objects.get_for_model(model).pk
                    }
                })
        return related_items

    def parse_related_fields(self):
        """
        Go over the search_fields to look for fields that exist in the
        related_search_mapping
        """
        normal_fields = []
        generic_search_fields = defaultdict(list)
        for field in self.search_fields:
            if self.related_search_mapping:
                for rfield in self.related_search_mapping:
                    if field.startswith(rfield):
                        inner_field = field[len(rfield) + 2:]
                        generic_search_fields[rfield].append(
                            # get the field name after 'rfield__'
                            self._construct_search(inner_field)
                        )
                    else:
                        normal_fields.append(field)
            else:
                normal_fields.append(field)
        return normal_fields, generic_search_fields

    def get_results(self, search_term, queryset):
        use_distinct = False
        if not search_term:
            return queryset, use_distinct

        non_generic_fields, generic_fields = self.parse_related_fields()
        related_items = self.get_related_items(search_term, generic_fields)

        # initial orm lookups (for normal fields)
        orm_lookups = [self._construct_search(str(search_field))
                       for search_field in non_generic_fields]
        for bit in search_term.split():
            or_queries = [Q(**{orm_lookup: bit})
                          for orm_lookup in orm_lookups]
            # append generic related filters to or_queries
            for item in related_items:
                object_ids = item['object_ids']
                ctype = item['content_type']
                for pk in object_ids['values']:
                    or_queries.append(
                        Q(**{object_ids['field']: pk}) &
                        Q(**{ctype['field']: ctype['value']})
                    )
            if or_queries:
                query = reduce(operator.or_, or_queries)
                queryset = queryset.filter(query)
        if not use_distinct:
            for search_spec in orm_lookups:
                if lookup_needs_distinct(self.opts, search_spec):
                    use_distinct = True
                    break
        return queryset, use_distinct
