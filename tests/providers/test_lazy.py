import pytest

from antidote.core import DependencyContainer
from antidote.providers.lazy import LazyCall, LazyCallProvider, LazyMethodCall
from antidote.providers.service import ServiceProvider


@pytest.fixture
def container():
    return DependencyContainer()


@pytest.fixture
def service_provider(container):
    provider = ServiceProvider(container=container)
    container.register_provider(provider)
    return provider


@pytest.fixture
def lazy_provider(container):
    provider = LazyCallProvider(container=container)
    container.register_provider(provider)
    return provider


def test_lazy(lazy_provider: LazyCallProvider, service_provider: ServiceProvider):
    def func(x):
        return x

    obj = object()
    test = LazyCall(func)(obj)

    assert obj is lazy_provider.provide(test).instance


def test_lazy_singleton(lazy_provider: LazyCallProvider,
                        service_provider: ServiceProvider):
    def func(x):
        return x

    test = LazyCall(func, singleton=False)(1)
    assert False is lazy_provider.provide(test).singleton

    test2 = LazyCall(func, singleton=True)(1)
    assert True is lazy_provider.provide(test2).singleton


@pytest.mark.parametrize(
    'args,kwargs',
    [
        ((1,), dict(test=2)),
        ((), dict(x=32)),
        ((4,), {})
    ]
)
def test_args_kwargs(lazy_provider: LazyCallProvider,
                     service_provider: ServiceProvider,
                     args, kwargs):
    def func(*args_, **kwargs_):
        return args_, kwargs_

    test = LazyCall(func)(*args, **kwargs)

    assert (args, kwargs) == lazy_provider.provide(test).instance


def test_method_call(lazy_provider: LazyCallProvider,
                     service_provider: ServiceProvider):
    x = object()

    class Test:
        def get(self, s):
            return id(s)

        A = LazyMethodCall(get)(x)
        B = LazyMethodCall('get')(x)

    service_provider.register(Test)

    assert id(x) == lazy_provider.provide(Test.A).instance
    assert id(x) == lazy_provider.provide(Test.B).instance


def test_method_same_instance(lazy_provider: LazyCallProvider,
                              service_provider: ServiceProvider):
    class Test:
        def get(self):
            return self

        A = LazyMethodCall(get, singleton=True)
        B = LazyMethodCall(get, singleton=False)

    service_provider.register(Test)

    x = lazy_provider.provide(Test.A).instance
    assert x is lazy_provider.provide(Test.A).instance
    assert x is lazy_provider.provide(Test.B).instance


def test_method_singleton(lazy_provider: LazyCallProvider,
                          service_provider: ServiceProvider):
    class Test:
        def get(self):
            return self

        A = LazyMethodCall(get, singleton=True)
        B = LazyMethodCall(get, singleton=False)

    service_provider.register(Test)

    assert Test.A is Test.A
    assert True is lazy_provider.provide(Test.A).singleton
    assert Test.B is not Test.B
    assert False is lazy_provider.provide(Test.B).singleton


def test_method_direct_call(lazy_provider: LazyCallProvider,
                            service_provider: ServiceProvider):
    class Test:
        def get(self):
            return self

        A = LazyMethodCall(get)

    service_provider.register(Test)

    t = Test()
    assert t is t.A

    t2 = Test()
    assert t2 is t2.A


@pytest.mark.parametrize(
    'args,kwargs',
    [
        ((1,), dict(test=2)),
        ((), dict(x=32)),
        ((4,), {})
    ]
)
def test_method_args_kwargs(lazy_provider: LazyCallProvider,
                            service_provider: ServiceProvider,
                            args, kwargs):
    class Test:
        def get(self, *args_, **kwargs_):
            return args_, kwargs_

        A = LazyMethodCall(get)(*args, **kwargs)

    service_provider.register(Test)

    assert (args, kwargs) == Test().A
    assert (args, kwargs) == lazy_provider.provide(Test.A).instance
