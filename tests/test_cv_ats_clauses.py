from __future__ import annotations

import unittest

from career.services.cv_content import _PORTUGUESE_ATS_CLAUSES


class PortugueseAtsClauseTests(unittest.TestCase):
    def test_lafinteca_top_keywords_have_defensible_canonical_clauses(self) -> None:
        expected = {
            "governanca operacional",
            "lideranca interfuncional",
            "automacao de processos",
            "escalabilidade operacional",
            "otimizacao de processos",
        }
        self.assertTrue(expected.issubset(_PORTUGUESE_ATS_CLAUSES))
        for keyword in expected:
            self.assertNotIn("R$", _PORTUGUESE_ATS_CLAUSES[keyword])

    def test_daki_top_keywords_have_defensible_canonical_clauses(self) -> None:
        expected = {
            "logistica de ultima milha",
            "last mile",
            "gestao de p&l",
            "otif",
            "tms",
            "gestao de multiplas unidades",
            "desenvolvimento de liderancas",
            "excelencia operacional",
        }
        self.assertTrue(expected.issubset(_PORTUGUESE_ATS_CLAUSES))
        for keyword in expected:
            self.assertNotIn("R$", _PORTUGUESE_ATS_CLAUSES[keyword])


if __name__ == "__main__":
    unittest.main()
