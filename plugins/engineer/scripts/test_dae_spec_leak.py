"""Tests for dae_spec_leak.py."""
import os
import tempfile
import unittest

import dae_spec_leak


class SpecLeakTests(unittest.TestCase):
    def test_clean_domain_spec_passes(self):
        text = """Feature: Number classification

Scenario: User sees a positive label
  Given a number is greater than zero
  When the number is classified
  Then the result is "positive"
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "spec.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(dae_spec_leak.main([path]), 0)

    def test_private_helper_and_endpoint_are_flagged(self):
        text = """Feature: Number classification

Scenario: Internal path leaks
  Given _normalize_input receives a value
  When POST /api/classify is called
  Then classify_number returns "positive"
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "spec.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(dae_spec_leak.main([path]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
