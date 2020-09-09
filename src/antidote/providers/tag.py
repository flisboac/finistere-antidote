import threading
from typing import (Any, Callable, Dict, Hashable, Iterable, Iterator, List, Optional,
                    Union)

from .._internal.utils import SlotsReprMixin, API
from ..core import DependencyContainer, DependencyInstance, DependencyProvider
from ..exceptions import DuplicateTagError, FrozenWorldError


@API.public
class Tag(SlotsReprMixin):
    """
    Tags are a way to expose a dependency indirectly. Instead of explicitly
    defining a list of dependencies to retrieve, one can just mark those with
    tags and retrieve them. This helps decoupling dependencies, and may be used
    to add extensions to another service typically.

    The tag itself has a name (string) attribute, with which it is identified.
    One may add others attributes to pass additional information to the services
    retrieving it.

    .. doctest::

        >>> from antidote import Tag
        >>> t = Tag('dep', info=1)
        >>> t.info
        1

    """
    __slots__ = ('name', '_attrs')

    def __init__(self, name: str, **attrs):
        """
        Args:
            name: Name which identifies the tag.
            **attrs: Any other parameters will be accessible as an attribute.
        """
        if not isinstance(name, str):
            raise TypeError("name must be a string")

        if len(name) == 0:
            raise ValueError("name must be a non empty string")

        self.name = name
        self._attrs = attrs

    def __str__(self):
        if not self._attrs:
            return f"{type(self).__name__}({self.name!r})"
        return repr(self)

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self._attrs.items())
        return f"{type(self).__name__}(name={self.name!r}, {attrs})"

    def __getattr__(self, item):
        return self._attrs.get(item)


@API.public
class Tagged(SlotsReprMixin):
    """
    Custom dependency used to retrieve all dependencies tagged with by with the
    name.
    """
    __slots__ = ('name',)

    def __init__(self, name: str):
        """
        Args:
            name: Name of the tags which shall be retrieved.
        """
        if not isinstance(name, str):
            raise TypeError("name must be a string")

        if len(name) == 0:
            raise ValueError("name must be a non empty string")

        self.name = name

    __str__: Callable[['Tagged'], str] = SlotsReprMixin.__repr__

    def __hash__(self):
        return object.__hash__(self)

    def __eq__(self, other):
        return object.__eq__(self, other)


@API.private
class TagProvider(DependencyProvider):
    """
    Provider managing string tag. Tags allows one to retrieve a collection of
    dependencies marked by their creator.
    """

    def __init__(self):
        super().__init__()
        self.__dependency_to_tag_by_tag_name: Dict[str, Dict[Hashable, Tag]] = {}
        self.__freeze_lock = threading.RLock()
        self.__frozen = False

    def freeze(self):
        with self.__freeze_lock:
            self.__frozen = True

    def __repr__(self):
        return f"{type(self).__name__}(tagged_dependencies={self.__dependency_to_tag_by_tag_name!r})"

    def clone(self) -> DependencyProvider:
        p = TagProvider()
        p.__dependency_to_tag_by_tag_name = self.__dependency_to_tag_by_tag_name.copy()
        return p

    def provide(self, dependency: Hashable, container: DependencyContainer
                ) -> Optional[DependencyInstance]:
        """
        Returns all dependencies matching the tag name specified with a
        :py:class:`~.dependency.Tagged`. For every other case, :obj:`None` is
        returned.

        Args:
            dependency: Only :py:class:`~.dependency.Tagged` is supported, all
                others are ignored.

        Returns:
            :py:class:`~.TaggedDependencies` wrapped in a
            :py:class:`~..core.Instance`.
        """
        if isinstance(dependency, Tagged):
            dependencies = []
            tags = []
            dependency_to_tag = self.__dependency_to_tag_by_tag_name.get(dependency.name,
                                                                         {})

            for dependency_, tag in dependency_to_tag.items():
                dependencies.append(dependency_)
                tags.append(tag)

            return DependencyInstance(
                TaggedDependencies(
                    container=container,
                    dependencies=dependencies,
                    tags=tags
                ),
                # Whether the returned dependencies are singletons or not is
                # their decision to take.
                singleton=False
            )

        return None

    def register(self, dependency: Hashable, tags: Iterable[Union[str, Tag]]):
        """
        Mark a dependency with all the supplied tags. Raises
        :py:exc:`~.exceptions.DuplicateTagError` if the tag has already been
        used for this dependency.

        Args:
            dependency: dependency to register.
            tags: Iterable of tags which should be associated with the
                dependency
        """
        tags = [Tag(t) if isinstance(t, str) else t for t in tags]
        for tag in tags:
            if not isinstance(tag, Tag):
                raise ValueError(f"Expecting tag of type Tag, not {type(tag)}")

        with self.__freeze_lock:
            if self.__frozen:
                raise FrozenWorldError(f"Cannot add tags {tags} to {dependency} "
                                       f"in a frozen world.")
            for tag in tags:
                if tag.name not in self.__dependency_to_tag_by_tag_name:
                    self.__dependency_to_tag_by_tag_name[tag.name] = {dependency: tag}
                elif dependency not in self.__dependency_to_tag_by_tag_name[tag.name]:
                    self.__dependency_to_tag_by_tag_name[tag.name][dependency] = tag
                else:
                    raise DuplicateTagError(tag.name)


@API.public
class TaggedDependencies:
    """
    Collection containing dependencies and their tags. Dependencies are lazily
    instantiated. This is thread-safe.

    Used by :py:class:`~.TagProvider` to return the dependencies matching a tag.
    """

    @API.private  # You're not supposed to create it yourself
    def __init__(self,
                 container: DependencyContainer,
                 dependencies: List[Hashable],
                 tags: List[Tag]):
        self._lock = threading.Lock()
        self._container = container
        self._dependencies = dependencies
        self._tags = tags
        self._instances: List[Any] = []

    def __len__(self):
        return len(self._tags)

    def dependencies(self) -> Iterable[Hashable]:
        """
        Returns all the dependencies retrieved. This does not instantiate them.
        """
        return iter(self._dependencies)

    def tags(self) -> Iterable[Tag]:
        """
        Returns all the tags retrieved. This does not instantiate the
        dependencies.
        """
        return iter(self._tags)

    def instances(self) -> Iterator:
        """
        Returns the dependencies, in a stable order for multi-threaded
        environments.
        """
        i = -1
        for i, instance in enumerate(self._instances):
            yield instance

        i += 1
        while i < len(self):
            try:
                yield self._instances[i]
            except IndexError:
                with self._lock:
                    # If not other thread has already added the instance.
                    if i == len(self._instances):
                        self._instances.append(
                            self._container.get(self._dependencies[i])
                        )
                yield self._instances[i]
            i += 1
