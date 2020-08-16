#!/usr/bin/env python3
# vim: set ts=4 sw=4 ts=4 et :

import argparse
import contextlib
import enum
import logging
import time

from typing import List, Dict, Union, Optional, Any

import asyncio
import aiohttp

# type: ignore
import throttler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


class MatchFetcher:
    """
    a simple async riot api client
    """

    __rate_limits: List[Dict[str, int]] = [
        {"rate_limit": 20, "period": 1},
        {"rate_limit": 100, "period": 120},
    ]

    __base_url: str = "https://na1.api.riotgames.com/lol"

    api_key: str = str()
    limiters: List[throttler.Throttler] = list()

    class Endpoint(enum.Enum):
        MATCHES = "match/v4/matchlists/by-account"
        SUMMONER = "summoner/v4/summoners/by-name"
        MATCH = "match/v4/matches"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.limiters = self.__init_rate_limits()

    def __init_rate_limits(self) -> List[throttler.Throttler]:
        limiters = list()
        for limit in self.__rate_limits:
            limiters.append(throttler.Throttler(**limit))
        return limiters

    async def call_api(self, client: aiohttp.ClientSession, endpoint: Endpoint, query: str) -> Any:
        url = f"{self.__base_url}/{endpoint.value}/{query}"
        data = None
        async with contextlib.AsyncExitStack() as stack:
            for limit in self.limiters:
                await stack.enter_async_context(limit)
            data = await self._request(client, url)
        return data

    async def _request(self, client: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
        log.debug(url)
        async with client.get(url) as response:
            return await response.json()

    async def get_match_history(self, username: str) -> None:
        headers = {"X-Riot-Token": self.api_key}
        async with aiohttp.ClientSession(headers=headers) as client:
            summoner_info = await self.call_api(
                client, self.Endpoint.SUMMONER, username
            )
            if summoner_info is None:
                log.error("Failed to get info for summoner: {username}")
                return None

            account_id = summoner_info.get("accountId")
            if account_id is None:
                return None

            match_history = await self.call_api(
                client, self.Endpoint.MATCHES, str(account_id)
            )
            if match_history is None:
                return None

            tasks = list()
            for match in match_history.get("matches", []):
                summoner_id = summoner_info.get("id")
                game_id = match.get("gameId")
                coro = self.get_normalize_match(client, summoner_id, game_id)
                tasks.append(asyncio.ensure_future(coro))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            matches = filter(lambda i: not(isinstance(i, Exception)), results)


    async def get_normalize_match(self, client, summoner_id, game_id):
        match = await self.call_api(client, self.Endpoint.MATCH, game_id)
        # TODO: correlate win in match with summoner_id
        return match


def parse_args():
    parser = argparse.ArgumentParser(description="Default")
    parser.add_argument("--debug", help="debug", action="store_true")
    parser.add_argument("-k", "--api_key", help="api key")
    parser.add_argument("-s", "--summoner", help="summoner name")
    return parser.parse_args()


def main():
    args = parse_args()

    log.info("Running {}".format(__file__))
    if args.debug:
        log.setLevel(logging.DEBUG)
        log.debug("Debug mode enabled")

    # profiling
    s = time.perf_counter()

    r = MatchFetcher(args.api_key)
    asyncio.run(r.get_match_history(args.summoner))

    elapsed = time.perf_counter() - s
    log.info(f"{__file__} executed in {elapsed:0.5f} seconds.")


if __name__ == "__main__":
    main()
