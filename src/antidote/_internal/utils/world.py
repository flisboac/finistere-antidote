"""
Utilities used by world, mostly for syntactic sugar.
"""
from typing import Any, Callable, cast, Hashable, List, Optional, Type, TypeVar

from .meta import FinalMeta
from .. import API
from ..._compatibility.typing import final
from ...core.container import (Container, DependencyInstance, RawContainer, RawProvider)
from ...core.utils import Dependency

T = TypeVar('T')


@API.private
@final
class WorldGet(metaclass=FinalMeta):
    def __call__(self, dependency: object) -> Any:
        from ..state import get_container
        return get_container().get(dependency)

    def __getitem__(self, tpe: Type[T]) -> Callable[[object], T]:
        def f(dependency=None) -> T:
            from ..state import get_container
            if dependency is None:
                dependency = tpe
            return cast(T, get_container().get(dependency))

        return f


@API.private
@final
class WorldLazy(metaclass=FinalMeta):
    def __call__(self, dependency: object) -> Dependency[Any]:
        return Dependency(dependency)

    def __getitem__(self, tpe: Type[T]) -> Callable[[object], Dependency[T]]:
        def f(dependency=None) -> Dependency[T]:
            if dependency is None:
                dependency = tpe
            return Dependency(dependency)

        return f


@API.private
def new_container():
    """ default new container in Antidote """

    from ..._extension.providers import (LazyProvider, ServiceProvider, TagProvider,
                                         IndirectProvider, FactoryProvider)

    container = RawContainer()
    container.add_provider(FactoryProvider)
    container.add_provider(ServiceProvider)
    container.add_provider(LazyProvider)
    container.add_provider(IndirectProvider)
    container.add_provider(TagProvider)

    return container


@API.private
@final
class OverridableProviderCollection(RawProvider, metaclass=FinalMeta):
    """ Utility class used for creating an overridable world """

    def __init__(self, providers: List[RawProvider] = None):
        super().__init__()
        self.__providers = providers or list()

    def exists(self, dependency: Hashable) -> bool:
        return False  # overridable as it'll never conflict.

    def maybe_provide(self,
                      dependency: Hashable,
                      container: Container) -> Optional[DependencyInstance]:
        for provider in self.__providers:
            dependency_instance = provider.maybe_provide(dependency, container)
            if dependency_instance is not None:
                return dependency_instance
        return None  # For Mypy

    def set_providers(self, providers: List[RawProvider]):
        self.__providers = providers

    def clone(self, keep_singletons_cache: bool) -> 'OverridableProviderCollection':
        return OverridableProviderCollection([p.clone(keep_singletons_cache)
                                              for p in self.__providers])