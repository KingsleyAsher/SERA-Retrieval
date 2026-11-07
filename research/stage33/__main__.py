"""Public gate-one checks and explicit frozen-input availability reporting."""
import argparse
import json
import sys
import unittest
from pathlib import Path

from research.reuse_foundation.common import digest
from research.reuse_foundation.runtime import atomic_publish
from .diagnostics import input_availability


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromName('research.stage33.test_stage33')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    root=Path(__file__).resolve().parents[2]
    report=dict(format=1,tests=result.testsRun,passed=result.wasSuccessful(),
        prerequisite_groups=10,geometry_tests=2,input_location_tests=1,synthetic_only=True,
        stage33_status='mechanics_verified_replay_status_separate' if result.wasSuccessful() else 'gate1_failed',
        frozen_inputs=input_availability(root),online_pruning=False,expert_training=False,
        code_sha256={p.name:digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')})
    atomic_publish(args.output,report)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__': sys.exit(main())
