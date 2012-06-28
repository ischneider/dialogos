from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import PermissionDenied
try:
    from django.utils.importlib import import_module
except ImportError:
    from importlib import import_module
    
from functools import partial


def load_path_attr(path):
    i = path.rfind(".")
    module, attr = path[:i], path[i+1:]
    try:
        mod = import_module(module)
    except ImportError, e:
        raise ImproperlyConfigured("Error importing %s: '%s'" % (module, e))
    try:
        attr = getattr(mod, attr)
    except AttributeError:
        raise ImproperlyConfigured("Module '%s' does not define a '%s'" % (module, attr))
    return attr


def default_can_delete(user, comment):
    return user.is_superuser or user == comment.author


def default_can_edit(user, comment):
    return user == comment.author


def default_can_post(user, obj):
    '''Check whether the provided user can post a comment to the specified 
    object. The protocol is to raise an PermissionDenied exception if not
    allowed with the message set to the appropriate user facing explaination.
    
    This default simply disables anonymous comments.
    '''
    if not user.is_authenticated():
        raise PermissionDenied('Anonymous comments disabled')


def _load_callable(settings_key, default):
    import_path = getattr(settings, settings_key, None)
    return load_path_attr(import_path) if import_path else default


load_can_post = partial(_load_callable, 'COMMENTS_CAN_POST_CALLABLE',
                        default_can_post)
                               
load_can_delete = partial(_load_callable, 'COMMENTS_CAN_DELETE_CALLABLE',
                          default_can_delete)

load_can_edit = partial(_load_callable, 'COMMENTS_CAN_EDIT_CALLABLE',
                        default_can_edit)
