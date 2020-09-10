from django import template
from xadmin.filters import SEARCH_VAR
from xadmin.plugins.utils import get_context_dict
from xadmin.views import BaseAdminPlugin
from xadmin.views import ListAdminView

from xplugin_generic_search.search import GenericSearchMixin


class GenericSearchPlugin(BaseAdminPlugin):
    """
    Search plugin similar to the standard but adds the ability to search generic content.
    """
    # Same as 'search_fields' but replace it with this one.
    related_search_fields = ()
    # Field map related to the columns of the generic field.
    related_search_mapping = {}

    def init_request(self, *args, **kwargs):
        return bool(not getattr(self.admin_view, 'search_fields', None) and
                    isinstance(self.admin_view, ListAdminView))

    def do_search(self, search_query, queryset):
        """Apply the search filter on standard fields and also on generic fields"""
        search_mixin = GenericSearchMixin(self.model,
                                          self.related_search_fields,
                                          self.related_search_mapping)
        queryset, use_distinct = search_mixin.get_results(search_query, queryset)
        if use_distinct:
            queryset = queryset.distinct()
        return queryset

    def get_list_queryset(self, queryset):
        """get_list_queryset::filter_hook"""
        search_query = self.request.GET.get(SEARCH_VAR, '')
        if search_query and self.related_search_fields:
            queryset = self.do_search(search_query, queryset)
            self.admin_view.search_query = search_query
        return queryset

    def block_nav_form(self, context, nodes):
        """block_nav_form::filter_hook"""
        if self.related_search_fields:
            context = get_context_dict(context or {})  # no error!
            self.admin_view.search_fields = self.related_search_fields
            context.update({
                'search_var': SEARCH_VAR,
                'remove_search_url': self.admin_view.get_query_string(remove=[SEARCH_VAR]),
                'search_form_params': self.admin_view.get_form_params(remove=[SEARCH_VAR])
            })
            nodes.append(
                template.loader.render_to_string(
                    'xadmin/blocks/model_list.nav_form.search_form.html',
                    context=context)
            )
