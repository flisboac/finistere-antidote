from typing import Callable, Hashable, Optional

import pytest

from antidote import world
from antidote.core import Dependency, DependencyContainer, DependencyInstance, \
    DependencyProvider, StatelessDependencyProvider
from antidote.core.exceptions import DuplicateDependencyError
from antidote.exceptions import DependencyNotFoundError, FrozenWorldError
from antidote.providers import ServiceProvider


@pytest.fixture(autouse=True)
def empty_world():
    with world.test.empty():
        yield


class DummyIntProvider(DependencyProvider):
    def __init__(self):
        super().__init__()
        self.original = None

    def provide(self, dependency: Hashable, container: DependencyContainer
                ) -> Optional[DependencyInstance]:
        if isinstance(dependency, int):
            return DependencyInstance(dependency * 2)

    def clone(self, keep_singletons_cache: bool):
        p = DummyIntProvider()
        p.original = self
        return p


class A:
    pass


def test_singletons():
    world.singletons.set("singleton", 12342)
    assert world.get("singleton") == 12342

    world.singletons.update({
        "singleton2": 89,
        "singleton3": 123
    })
    assert world.get("singleton2") == 89
    assert world.get("singleton3") == 123


def test_duplicate_singletons():
    world.singletons.set("singleton", 12342)

    with pytest.raises(DuplicateDependencyError, match=".*singleton.*12342.*"):
        world.singletons.set("singleton", 1)

    with pytest.raises(DuplicateDependencyError, match=".*singleton.*12342.*"):
        world.singletons.update({"singleton": 1})


def test_get():
    world.singletons.set("x", 1)
    assert 1 == world.get("x")

    with pytest.raises(DependencyNotFoundError):
        world.get("nothing")

    world.singletons.set(A, A())
    assert world.get[int]("x") == 1
    assert world.get[A]() is world.get(A)


def test_lazy():
    world.singletons.update({
        'x': object(),
        A: A()
    })

    l = world.lazy('x')
    assert isinstance(l, Dependency)
    assert l.value == 'x'
    assert l.get() == world.get('x')

    l = world.lazy[int]('x')
    assert isinstance(l, Dependency)
    assert l.value == 'x'
    assert l.get() == world.get('x')
    assert world.lazy[A]().get() is world.get(A)


def test_freeze():
    world.provider(ServiceProvider)
    factory = world.get(ServiceProvider)

    class Service:
        pass

    world.freeze()
    with pytest.raises(FrozenWorldError):
        world.singletons.set("test", "x")

    with pytest.raises(FrozenWorldError):
        factory.register(Service)


def test_add_provider():
    world.provider(DummyIntProvider)
    assert world.get(10) == 20


@pytest.mark.parametrize('p, expectation', [
    (1, pytest.raises(TypeError)),
    (A, pytest.raises(TypeError))
])
def test_invalid_add_provider(p, expectation):
    with expectation:
        world.provider(p)


@pytest.mark.parametrize('context,keeps_singletons,strategy', [
    pytest.param(lambda: world.test.empty(),
                 False,
                 'empty',
                 id='empty'),
    pytest.param(lambda: world.test.new(),
                 False,
                 'new',
                 id='new'),
    pytest.param(lambda: world.test.clone(),
                 False,
                 'clone',
                 id='clone'),
    pytest.param(lambda: world.test.clone(keep_singletons=True),
                 True,
                 'clone',
                 id='clone-with-singletons'),
    pytest.param(lambda: world.test.clone(overridable=True),
                 False,
                 'overridable',
                 id='clone-overridable'),
    pytest.param(lambda: world.test.clone(keep_singletons=True, overridable=True),
                 True,
                 'overridable',
                 id='clone-overridable-with-singletons')
])
def test_test_world(context: Callable, keeps_singletons: bool, strategy: str):
    class DummyFloatProvider(StatelessDependencyProvider):
        def provide(self, dependency: Hashable, container: DependencyContainer
                    ) -> Optional[DependencyInstance]:
            if isinstance(dependency, float):
                return DependencyInstance(dependency ** 2)

    x = object()
    y = object()
    world.singletons.set("x", x)
    world.provider(DummyIntProvider)
    provider = world.get(DummyIntProvider)

    with context():
        if keeps_singletons:
            assert world.get('x') == x
        else:
            with pytest.raises(DependencyNotFoundError):
                world.get('x')

        if strategy == 'new':
            with pytest.raises(DependencyNotFoundError):
                world.get(DummyIntProvider)
            assert isinstance(world.get(ServiceProvider), ServiceProvider)
        elif strategy in {'clone', 'overridable'}:
            assert isinstance(world.get(DummyIntProvider), DummyIntProvider)
            assert world.get(DummyIntProvider) is not provider
            if strategy == 'clone':
                assert world.get(DummyIntProvider).original is provider
            else:
                assert world.get(DummyIntProvider).original is None
        elif strategy == 'empty':
            with pytest.raises(DependencyNotFoundError):
                world.get(DummyIntProvider)
            with pytest.raises(DependencyNotFoundError):
                world.get(ServiceProvider)

        world.singletons.set("y", y)
        world.provider(DummyFloatProvider)

        assert world.get(1.2) == 1.2 ** 2

    with pytest.raises(DependencyNotFoundError):
        world.get('y')

    with pytest.raises(DependencyNotFoundError):
        world.get(1.2)

    with pytest.raises(DependencyNotFoundError):
        world.get(DummyFloatProvider)


def test_test_clone():
    world.singletons.set("singleton", 2)

    with world.test.clone(keep_singletons=True):
        world.singletons.set("a", 3)
        assert world.get("singleton") == 2
        assert world.get("a") == 3
        world.provider(DummyIntProvider)
        assert world.get(10) == 20

    with world.test.clone(keep_singletons=False):
        world.singletons.set("a", 3)
        assert world.get("a") == 3
        with pytest.raises(DependencyNotFoundError):
            world.get("singleton")
        world.provider(DummyIntProvider)
        assert world.get(10) == 20

    with pytest.raises(DependencyNotFoundError):
        world.get("a")

    with pytest.raises(DependencyNotFoundError):
        assert world.get(10)


def test_test_empty():
    world.singletons.set("singleton", 2)

    with world.test.empty():
        world.singletons.set("a", 3)
        assert world.get("a") == 3
        with pytest.raises(DependencyNotFoundError):
            world.get("singleton")
        world.provider(DummyIntProvider)
        assert world.get(10) == 20
        with pytest.raises(DependencyNotFoundError):
            world.get(ServiceProvider)

    with pytest.raises(DependencyNotFoundError):
        world.get("a")

    with pytest.raises(DependencyNotFoundError):
        assert world.get(10)


def test_test_new():
    world.singletons.set("singleton", 2)

    with world.test.new():
        world.singletons.set("a", 3)
        assert world.get("a") == 3
        with pytest.raises(DependencyNotFoundError):
            world.get("singleton")
        world.provider(DummyIntProvider)
        assert world.get(10) == 20
        assert world.get(ServiceProvider) is not None

    with pytest.raises(DependencyNotFoundError):
        world.get("a")

    with pytest.raises(DependencyNotFoundError):
        assert world.get(10)
