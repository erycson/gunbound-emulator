"""Diagnostic fixture checker, Windows x86 ONLY; not part of the IPC protocol.

Initializes pending state to the exact saved real-IPC fixtures to compare the
native check ABI with the previous offline reference. This is not session flow
or an answer generator. Production sessions cannot inject flags/query/version.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gunbound.game.ggauth50_helper import Block, DLL_SHA256, Native, Session, Version
from gunbound.game.ggauth50_codec import Codec

VECTORS = (
    ('initial', '00000000000000000000000050000100', '500001001ca6d7ecb50fbf7710d3ded1',
     '82d6df0180a8447df8b2aafa6d1d6c0b'),
    ('index346', '5a010000050199452c8ddd4278563412', '50000100a683d8f3238db36b3fda89f5',
     '2e8e36f51809edee710aaa165da2d10b'),
)


def run(dll, original_server):
    native = Native(dll)
    codec = Codec(original_server)
    native.update()  # actual native UpdateTimer; same thread as init/check
    result = dict(dll_sha256=DLL_SHA256, native_update_returned_zero=True, cases=[])
    for name, query, answer, wire in VECTORS:
        codes = []
        for mutate in ('none', 'internal_last_byte', 'wire_last_byte'):
            session = Session()
            session.version = Version(2009010101, 2009, 1, 1, 1)
            session.flags.value = 3
            session.query = Block.from_buffer_copy(bytes.fromhex(query))
            raw = bytearray.fromhex(answer)
            if mutate == 'internal_last_byte':
                raw[-1] ^= 1
            if mutate == 'wire_last_byte':
                mutated = bytearray.fromhex(wire)
                mutated[-1] ^= 1
                raw = codec.decode_answer(mutated)
            session.answer = Block.from_buffer_copy(raw)
            codes.append(native.check(session))
        result['cases'].append(dict(name=name, accepted_code=codes[0], internal_last_byte_mutated_code=codes[1],
                                   wire_last_byte_mutated_code=codes[2]))
    result['all_checks_passed'] = all(row['accepted_code'] == 0 and row['wire_last_byte_mutated_code'] != 0
                                      for row in result['cases'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dll', required=True)
    parser.add_argument('--original-server', required=True)
    args = parser.parse_args()
    result = run(args.dll, args.original_server)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['all_checks_passed'] else 1)
