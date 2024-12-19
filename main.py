import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine, Iterable
from dataclasses import dataclass
from typing import (
    Concatenate,
    ParamSpec,
    Protocol,
    TypeVar,
)

T = TypeVar("T")
P = ParamSpec("P")
Returns = TypeVar("Returns")


@dataclass(frozen=True)
class PaginatedResponse(Protocol[T, Returns]):
    def _next_params(self) -> T | None: ...

    def _results(self) -> Iterable[Returns]: ...


@dataclass(slots=True, frozen=True)
class BasicResponse(PaginatedResponse[T, Returns]):
    next_params: T | None
    data: Iterable[Returns]

    def _next_params(self) -> T | None:
        return self.next_params

    def _results(self) -> Iterable[Returns]:
        return self.data


def async_generator():
    def decorator(func: Callable[Concatenate[T, P], Coroutine[None, None, Returns]]):
        async def wrapper(
            input: Iterable[T],
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> AsyncGenerator[Returns, None]:
            iterator = iter(input)
            async with asyncio.TaskGroup() as tasks:
                item = next(iterator)
                task = tasks.create_task(func(item, *args, **kwargs))
                result = await task

                for item in iterator:
                    task = tasks.create_task(func(item, *args, **kwargs))
                    yield result

                    result = await task

                yield result

        return wrapper

    return decorator


def async_generator_paginated():
    def decorator(
        func: Callable[Concatenate[T, P], Coroutine[None, None, PaginatedResponse[T, Returns]]],
    ):
        async def wrapper(
            input: T,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> AsyncGenerator[Returns, None]:
            async with asyncio.TaskGroup() as tasks:
                task = tasks.create_task(func(input, *args, **kwargs))
                result = await task

                next_params = result._next_params()
                while next_params is not None:
                    task = tasks.create_task(func(next_params, *args, **kwargs))

                    for data in result._results():
                        yield data

                    result = await task
                    next_params = result._next_params()

                for data in result._results():
                    yield data

        return wrapper

    return decorator


def retry(max_trys: int, delay: float = 0.1):
    def decorator(func: Callable[P, Coroutine[None, None, Returns]]):
        async def wrapper(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> Returns:
            for i in range(max_trys):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if i >= max_trys:
                        raise e
                    await asyncio.sleep(delay)

            raise Exception("Error in retrying the function.")

        return wrapper

    return decorator


@async_generator_paginated()
async def get_data(item: int) -> BasicResponse[int, int]:
    await asyncio.sleep(1)
    return BasicResponse(None, [item])


async def main():
    lista = [1, 2, 3, 4, 5]

    async for i in get_data(lista[0]):
        print(i)


if __name__ == "__main__":
    asyncio.run(main())
