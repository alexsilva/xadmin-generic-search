# coding=utf-8
import xadmin.sites
from xadmin.views import ListAdminView


def register(site=None):
    """Register the plugin in the ListAdminView class"""
    if site is None:
        site = xadmin.sites.site

    from xplugin_generic_search.plugin import GenericSearchPlugin
    site.register_plugin(GenericSearchPlugin, ListAdminView)