# xadmin-generic-search
Plugin that adds the ability to search for generic content (with content-type).

## django model

```
class Directory(MPTTModel, FileCollectionChildMixin):
    name = models.CharField(max_length=300, verbose_name="Name")
    alias = models.CharField(max_length=255, verbose_name="Alias",
                             null=True, blank=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                     blank=True, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')
```

## adminx.py settings
```
class DirectoryAdmin:
    readonly_fields = ('name',)
    related_search_fields = (
        'name',
        'alias',
        'content_object__first_name'
    )
    related_search_mapping = {
         'content_object': {
             'ctypes': [settings.AUTH_USER_MODEL.split('.')]
         }
    }

site.register(Directory, DirectoryAdmin)
```

## adminx.py register
```
import xplugin_generic_search.sites
xplugin_generic_search.sites.register()
```