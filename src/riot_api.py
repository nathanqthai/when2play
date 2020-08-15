#!/usr/bin/env python3
# vim: set ts=4 sw=4 ts=4 et :

import argparse
import contextlib
import logging
import time

from typing import List, Dict

import asyncio
import throttler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


class RiotAPI:
    """
    a simple async riot api client
    """

    __rate_limits: List[Dict[str, int]] = [
        {"rate_limit": 20, "period": 1},
        {"rate_limit": 100, "period": 120},
    ]

    api_key: str = str()
    limiters: List[throttler.Throttler] = list()


    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.limiters = self.__init_rate_limits()

    def __init_rate_limits(self) -> List[throttler.Throttler]:
        limiters = list()
        for limit in self.__rate_limits:
            limiters.append(throttler.Throttler(**limit))
        return limiters

    async def _throttled_request(self, *args, **kwargs):
        async with contextlib.AsyncExitStack() as stack:
            for limit in self.limiters:
                await stack.enter_async_context(limit)
            await self._request(*args, **kwargs)

    async def _request(self, *args, **kwargs):
        print(f"{args[0]:>2d}: Drip! {time.time() - args[1]:>5.2f}")


def parse_args():
    parser = argparse.ArgumentParser(description="Default")
    parser.add_argument("--debug", help="debug", action="store_true")
    parser.add_argument("-k", "--api_key", help="api key")
    return parser.parse_args()


def main():
    args = parse_args()

    log.info("Running {}".format(__file__))
    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("Debug mode enabled")

    # profiling
    s = time.perf_counter()

    r = RiotAPI(args.api_key)

    ref = time.time()
    tasks = [r._throttled_request(i, ref) for i in range(200)]
    asyncio.run(asyncio.wait(tasks))

    elapsed = time.perf_counter() - s
    log.info(f"{__file__} executed in {elapsed:0.5f} seconds.")


if __name__ == "__main__":
    main()
