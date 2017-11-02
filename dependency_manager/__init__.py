from .manager import DependencyManager
from .container import DependencyContainer, DependencyFactory
from .injector import DependencyInjector
from .exceptions import *


__version__ = '0.1'

__all__ = [
    'DependencyContainer',
    'DependencyFactory',
    'DependencyInjector',
    'DependencyManager',
    'DependencyNotFoundError',
    'DependencyDuplicateError',
    'DependencyInstantiationError'
]


manager = DependencyManager()

container = manager.container
builder = manager.injector
inject = manager.inject
factory = manager.factory
register = manager.register
wire = manager.wire

try:
    import attr
except ImportError:
    pass
else:
    attrib = manager.attrib
