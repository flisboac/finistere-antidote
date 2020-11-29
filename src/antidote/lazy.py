import weakref
from typing import Callable, Union

from ._compatibility.typing import final
from ._internal import API
from ._internal.utils import debug_repr, FinalImmutable
from .core import Container, DependencyInstance
from .core.utils import DependencyDebug
from ._extension.providers import Lazy


@API.public
@final
class LazyCall(FinalImmutable, Lazy):
    """
    Dependency which is the result of the call of the given function with the
    given arguments.

    .. doctest:: helpers_lazy_func

        >>> from antidote import LazyCall, world
        >>> def f(x, y):
        ...     print("Computing {} + {}".format(x, y))
        ...     return x + y
        >>> A = LazyCall(f)(2, y=3)
        >>> world.get(A)
        Computing 2 + 3
        5
        >>> # You may also not provide any arguments
        ... def g():
        ...     print("I'm g")
        >>> B = LazyCall(g)
        >>> world.get(B)
        I'm g

    """
    __slots__ = ('func', 'singleton')
    func: Callable
    singleton: bool

    def __init__(self, func: Callable, *, singleton: bool = True):
        """
        Args:
            func: Function to lazily call, any (keyword-)arguments given by the returned
                :py:class:`~.LazyCall` itself will be propagated.
            singleton: Whether or not this is a singleton or not. If yes, the function
                will only be called once.
        """
        if not callable(func):
            raise TypeError("func is not callable")
        if not isinstance(singleton, bool):
            raise TypeError(f"singleton must be a boolean, not {type(singleton)!r}")
        super().__init__(func=func, singleton=singleton)

    def __call__(self, *args, **kwargs) -> 'LazyCallWithArgsKwargs':
        """
        All argument are passed on to the lazily called function.
        """
        return LazyCallWithArgsKwargs(self.func, self.singleton, args, kwargs)

    def __antidote_debug_repr__(self):
        return f"LazyCall(func={debug_repr(self.func)}, singleton={self.singleton})"

    def debug_info(self) -> DependencyDebug:
        return DependencyDebug(f"LazyCall {debug_repr(self.func)}",
                               singleton=self.singleton,
                               wired=[self.func])

    def lazy_get(self, container: Container) -> DependencyInstance:
        return DependencyInstance(self.func(), self.singleton)


@API.public
@final
class LazyMethodCall(FinalImmutable, copy=False):
    """
    Similar to :py:class:`~.LazyCall` but adapted to methods within a class definition.
    The class has to be a registered service, as the class instantiation itself is also
    lazy.

    :py:class:`~.LazyMethodCall` has two different behaviors:

    - if retrieved as a class attribute it returns a dependency which can be retrieved
      from Antidote.
    - if retrieved as a instance attribute it returns the result for this
      instance. This makes testing a lot easier as it does not pass through Antidote.

    .. doctest:: helpers_lazy_method

        >>> from antidote import LazyMethodCall, Service, world
        >>> class Api(Service):
        ...     # Name of the method
        ...     conf = LazyMethodCall('query')('/conf')
        ...
        ...     def query(self, url: str = '/status'):
        ...         return f"requested {url}"
        ...
        ...     # or the method itself
        ...     status = LazyMethodCall(query, singleton=False)
        >>> world.get(Api.conf)
        'requested /conf'
        >>> # For ease of use, accessing the dependency through a instance will simply
        ... # call the method without passing through Antidote. Useful for tests typically
        ... Api().status
        'requested /status'

    .. note::

        Check out :py:class:`~.extension.constants.Constants` for simple way
        to declare multiple constants.

    """
    __slots__ = ('method_name', 'singleton', '_cache_attr')
    method_name: str
    singleton: bool
    _cache_attr: str

    def __init__(self, method: Union[Callable, str], singleton: bool = True):
        """
        Args:
            method: Method name or the method itself that must be called.
            singleton: Whether or not this is a singleton or not. If yes, the method
                will only be called once.
        """
        if not (callable(method) or isinstance(method, str)):
            raise TypeError("method must be a method or its name")
        if not isinstance(singleton, bool):
            raise TypeError(f"singleton must be a boolean, not {type(singleton)!r}")
        super().__init__(
            method_name=method if isinstance(method, str) else method.__name__,
            singleton=singleton,
            _cache_attr=f"__antidote_dependency_{hex(id(self))}"
        )

    def __call__(self, *args, **kwargs) -> 'LazyMethodCallWithArgsKwargs':
        """
        All argument are passed on to the lazily called method.
        """
        return LazyMethodCallWithArgsKwargs(self.method_name,
                                            self.singleton,
                                            self._cache_attr,
                                            args, kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            try:
                return getattr(owner, self._cache_attr)
            except AttributeError:
                dependency = LazyMethodCallDependency(self,
                                                      weakref.ref(owner),
                                                      self.singleton)
                setattr(owner, self._cache_attr, dependency)
                return dependency
        return getattr(instance, self.method_name)()


@API.private
@final
class LazyCallWithArgsKwargs(FinalImmutable, Lazy):
    """
    :meta private:
    """
    __slots__ = ('func', 'singleton', 'args', 'kwargs')
    func: Callable
    singleton: bool
    args: tuple
    kwargs: dict

    def __antidote_debug_repr__(self):
        return f"LazyCall(func={debug_repr(self.func)}, " \
               f"args={self.args}, kwargs={self.kwargs}" \
               f"singleton={self.singleton})"

    def debug_info(self) -> DependencyDebug:
        return DependencyDebug(
            f"Lazy '{debug_repr(self.func)}' "
            f"with args={self.args!r} and kwargs={self.kwargs!r}",
            singleton=self.singleton,
            wired=[self.func])

    def lazy_get(self, container: Container) -> DependencyInstance:
        return DependencyInstance(self.func(*self.args, **self.kwargs), self.singleton)


@API.private
@final
class LazyMethodCallWithArgsKwargs(FinalImmutable, copy=False):
    """
    :meta private:
    """
    __slots__ = ('method_name', 'singleton', '_cache_attr', 'args', 'kwargs')
    method_name: str
    singleton: bool
    args: tuple
    kwargs: dict
    _cache_attr: str

    def __get__(self, instance, owner):
        if instance is None:
            try:
                return getattr(owner, self._cache_attr)
            except AttributeError:
                dependency = LazyMethodCallDependency(self,
                                                      weakref.ref(owner),
                                                      self.singleton)
                setattr(owner, self._cache_attr, dependency)
                return dependency
        return getattr(instance, self.method_name)(*self.args, **self.kwargs)


@API.private
@final
class LazyMethodCallDependency(FinalImmutable, Lazy):
    """
    :meta private:
    """
    __slots__ = ('descriptor', 'owner_ref', 'singleton')
    descriptor: Union[LazyMethodCall, LazyMethodCallWithArgsKwargs]
    owner_ref: weakref.ReferenceType
    singleton: bool

    def debug_info(self) -> DependencyDebug:
        owner = self.owner_ref()
        assert owner is not None
        method = self.descriptor.method_name
        if isinstance(self.descriptor, LazyMethodCall):
            info = f"Lazy Method '{method}'"
        else:
            info = f"Lazy Method '{method}' " \
                   f"with args={self.descriptor.args} and kwargs={self.descriptor.kwargs}"
        return DependencyDebug(info,
                               singleton=self.descriptor.singleton,
                               wired=[getattr(owner, method)],
                               dependencies=[owner])

    def lazy_get(self, container: Container) -> DependencyInstance:
        owner = self.owner_ref()
        assert owner is not None
        return DependencyInstance(
            self.descriptor.__get__(container.get(owner), owner),
            self.singleton
        )