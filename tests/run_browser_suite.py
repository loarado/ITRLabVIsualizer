"""Run each distinct browser test once (shared inherited fixtures are common)."""
import importlib
from pathlib import Path
import unittest


def suite():
    result, seen = unittest.TestSuite(), set()

    def add(tests):
        for test in tests:
            if isinstance(test, unittest.TestSuite):
                add(test)
            else:
                method = getattr(type(test), test._testMethodName)
                if method not in seen:
                    seen.add(method)
                    result.addTest(test)

    for path in sorted(Path(__file__).parent.glob('browser_*.py')):
        if path.stem != 'browser_smoke':  # Standalone script, run separately.
            add(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(path.stem)))
    return result


if __name__ == '__main__':
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite()).wasSuccessful())
