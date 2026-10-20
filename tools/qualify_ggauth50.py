"""Explicit native smoke test, never started by the server or unit-test suite.

The fixed answer is a real v584 IPC capture, not an invented successful answer.
This checks only the initial exchange, mutations and next-query generation.
It does NOT qualify required or all 501 cases.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gunbound.game.ggauth50 import Helper, Validator
from gunbound.game.ggauth50_helper import DLL_SHA256
from gunbound.game.ggauth50_codec import SERVER_SHA256

# Provenance: csauth2-live-ipc-vectors.json in gg-server-emu, real v584 IPC,
# not a TCP capture. No token, password, session cipher or transport key here.
INITIAL_QUERY = bytes.fromhex('4e95dd29ce3a55db20b6ad97a65cc01c')
INITIAL_ANSWER = bytes.fromhex('82d6df0180a8447df8b2aafa6d1d6c0b')


async def qualify(options, wait_timer=False):
    helper = Helper(options)
    validators = []
    results = dict(dll_sha256=DLL_SHA256, original_server_sha256=SERVER_SHA256,
                   fixture='v584 real IPC initial exchange', required_qualified=False)
    try:
        a, b = Validator(helper), Validator(helper)
        validators.extend((a, b))
        qa, qb = await a.query(None), await b.query(None)
        if qa.wire != INITIAL_QUERY or qb.wire != INITIAL_QUERY:
            raise RuntimeError('native initial query differs from reference')
        results['two_initial_queries_match'] = True
        results['session_b_initial_accepted'] = await b.check(None, qb.internal, INITIAL_ANSWER)
        results['session_a_initial_accepted'] = await a.check(None, qa.internal, INITIAL_ANSWER)
        results['session_a_replay_rejected'] = not await a.check(None, qa.internal, INITIAL_ANSWER)
        next_query = await a.query(None)
        results['following_query_generated'] = (len(next_query.internal) == 16 and
                                                next_query.internal[:4] != bytes(4))
        c = Validator(helper)
        validators.append(c)
        qc = await c.query(None)
        mutated = INITIAL_ANSWER[:-1] + bytes([INITIAL_ANSWER[-1] ^ 1])
        results['mutation_rejected'] = not await c.check(None, qc.internal, mutated)
        if wait_timer:
            await asyncio.sleep(301)
            hello = await helper.request('hello')
            results['native_300_second_timer_observed'] = hello.get('timer_updates', 0) >= 1
        results['all_checks_passed'] = all(value is True for key, value in results.items()
                                         if key.endswith(('_accepted', '_rejected', '_generated', '_match', '_observed')))
        return results
    finally:
        for validator in validators:
            await validator.close()
        await helper.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python-x86', required=True)
    parser.add_argument('--dll', required=True)
    parser.add_argument('--original-server', required=True)
    parser.add_argument('--wait-timer', action='store_true', help='also wait 301 seconds for a real native timer update')
    args = parser.parse_args()
    result = asyncio.run(qualify(dict(python_x86=args.python_x86, dll=args.dll,
                        original_server=args.original_server, minimum_version=2003010101, timeout=10), args.wait_timer))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['all_checks_passed'] else 1)


if __name__ == '__main__':
    main()
