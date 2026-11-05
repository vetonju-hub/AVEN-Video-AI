import ast
from pathlib import Path
import tempfile
import unittest
from aven.i18n import Locale, Text, message, ENGLISH


class LanguageTests(unittest.TestCase):
    def test_switch_and_persist_without_replacing_user_values(self):
        with tempfile.TemporaryDirectory() as d:
            preferences=Path(d)/'settings.json'
            language=Locale(preferences)
            self.assertEqual(language.code,'de')
            value=message('Szene {number} gespeichert.',number=3)
            self.assertEqual(language.render(value),'Szene 3 gespeichert.')
            language.select('en')
            self.assertEqual(language.render(value),'Scene 3 saved.')
            self.assertEqual(Locale(preferences).code,'en')
            language.select('de')
            self.assertEqual(language.render(value),'Szene 3 gespeichert.')

    def test_nested_errors_and_dynamic_content_use_current_language(self):
        with tempfile.TemporaryDirectory() as d:
            language=Locale(Path(d)/'prefs.json')
            text=message('{name}: Fehlercode {code}. {detail}',name='sd-cli.exe',code=7,
                         detail=message('Bitte engine.log im Szenenordner prüfen.'))
            error=RuntimeError(text)
            language.select('en')
            self.assertEqual(language.render(error),'sd-cli.exe: Error code 7. Please check engine.log in the scene folder.')
            self.assertEqual(language.render(message('Musik: {name} · {seconds:.3f} Sekunden',name='Lied ü.mp3',seconds=5.375)),
                             'Music: Lied ü.mp3 · 5.375 seconds')

    def test_bad_preferences_and_unsupported_locale(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'prefs.json'; path.write_text('not json')
            self.assertEqual(Locale(path).code,'de')
            path.write_text('{"language":"fr"}')
            locale=Locale(path); self.assertEqual(locale.code,'de')
            with self.assertRaises(ValueError): locale.select('xx')

    def test_templates_have_matching_fields(self):
        import string
        fmt=string.Formatter()
        for source,target in ENGLISH.items():
            with self.subTest(source=source):
                fields=lambda s:{k for _,k,_,_ in fmt.parse(s) if k is not None}
                self.assertEqual(fields(source),fields(target))

    def test_live_bindings_update_without_recreating_controls(self):
        from aven.i18n import Bindings
        with tempfile.TemporaryDirectory() as d:
            locale=Locale(Path(d)/'prefs.json'); bindings=Bindings(locale)
            visible=[]
            bindings.bind(lambda value:visible.append(value),'Musik hinzufügen')
            self.assertEqual(visible[-1],'Musik hinzufügen')
            locale.select('en'); bindings.refresh()
            self.assertEqual(visible[-1],'Add music')


if __name__=='__main__': unittest.main()
