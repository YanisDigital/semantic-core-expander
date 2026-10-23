import unittest

from helpers import make_project
from common import load_project
from textutils import Filters, normalize, scripts_of, tokens


def filters(cfg):
    return Filters(load_project(make_project(cfg)))


# Russian forms of the root itself are project-specific, so they go to exclude.stems.
UK = {"gl": "ua", "hl": "uk", "seeds": ["житомир"], "roots": ["житомир"],
      "exclude_languages": ["ru"], "exclude": {"stems": ["житомире", "житомирск"]}}


class NormalizeTest(unittest.TestCase):
    def test_case_space_apostrophe(self):
        self.assertEqual(normalize("  Житомир   ПАМ’ЯТКИ "), "житомир пам'ятки")

    def test_lost_apostrophe_fix_uk(self):
        p = load_project(make_project(UK))["profile"]
        self.assertEqual(normalize("житомир пам ятки", p), "житомир пам'ятки")
        self.assertEqual(normalize("здоров я", p), "здоров'я")

    def test_tokens(self):
        self.assertEqual(tokens("пам'ятки ж/д, wi-fi 24"), ["пам'ятки", "ж", "д", "wi-fi", "24"])

    def test_scripts(self):
        self.assertEqual(scripts_of("kyiv київ 1"), {"LATIN", "CYRILLIC"})


class UkrainianFiltersTest(unittest.TestCase):
    def setUp(self):
        self.f = filters(UK)

    def test_keeps_ukrainian(self):
        for q in ["житомир новини", "погода у житомирі", "житомир пам'ятки",
                  "де в житомирі зробити паспорт"]:
            self.assertIsNone(self.f.reject_reason(q), q)

    def test_rejects_russian(self):
        for q in ["житомир новости", "что посмотреть житомир", "житомир объявления",
                  "житомир улица", "купить квартиру житомир"]:
            self.assertIsNotNone(self.f.foreign_reason(q), q)
        self.assertIn("foreign", self.f.reject_reason("житомирская область"))
        self.assertIn("project exclude", self.f.reject_reason("погода в житомире"))
        self.assertIsNone(self.f.reject_reason("житомирська область"))

    def test_latin_only_is_wrong_script(self):
        self.assertEqual(self.f.reject_reason("zhytomyr news"), "wrong script")
        self.assertIsNone(self.f.reject_reason("житомир wi-fi"))

    def test_trailing_letter_fragment(self):
        self.assertIn("truncated", self.f.reject_reason("житомир а"))
        self.assertIsNone(self.f.reject_reason("житомир вулиця 34 б"))

    def test_adult(self):
        self.assertIn("adult", self.f.reject_reason("житомир порно"))

    def test_relevance(self):
        self.assertTrue(self.f.relevant("у житомирі"))
        self.assertFalse(self.f.relevant("київ погода"))
        self.assertFalse(self.f.keep_expanding("погода в житомире"))

    def test_exclude_conflicts(self):
        f_cfg = load_project(make_project(dict(UK, seeds=["у львові"], roots=["льв"],
                                               exclude={"stems": ["львов", "львове"]})))
        self.assertEqual(Filters(f_cfg).exclude_conflicts(f_cfg), [("львов", ["львові"])])

    def test_allow_words(self):
        f = filters(dict(UK, allow_words=["новости"]))
        self.assertIsNone(f.foreign_reason("житомир новости"))


class EnglishFiltersTest(unittest.TestCase):
    def setUp(self):
        self.f = filters({"exclude": {"stems": ["toothless"], "regex": [r"\bmetro\b"]}})

    def test_trailing_letter_allowed_for_latin(self):
        self.assertIsNone(self.f.reject_reason("dentist vitamin c"))

    def test_cyrillic_is_wrong_script(self):
        self.assertEqual(self.f.reject_reason("дантист dentist".split()[0]), "wrong script")

    def test_project_excludes(self):
        self.assertIn("project exclude", self.f.reject_reason("toothless dentist"))
        self.assertIn("regex", self.f.reject_reason("dentist metro station"))

    def test_too_long_and_junk(self):
        self.assertIn("too long", self.f.reject_reason("dentist " + "a b c d e f g h i j"))
        self.assertIn("junk", self.f.reject_reason("dentist aaaaaa"))

    def test_excluding_spanish_marks(self):
        f = filters({"exclude_languages": ["es"]})
        self.assertIsNotNone(f.foreign_reason("dentist niño"))
        self.assertIsNotNone(f.foreign_reason("dentist para niños"))
        self.assertIsNone(f.foreign_reason("dentist for kids"))


if __name__ == "__main__":
    unittest.main()
