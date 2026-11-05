import math
import unittest
from aven.policy import Plan


class StoryTests(unittest.TestCase):
    def test_parse_sections_and_reject_ambiguous_timelines(self):
        from aven.story import parse_sections
        rows=parse_sections('0 | Intro | slow wide shot\n2,5 | Chorus | energetic close-up',5)
        self.assertEqual(rows[1],{'start':2.5,'title':'Chorus','prompt':'energetic close-up'})
        for text in ['1 | Intro | a','0 | Intro | a\n0 | Verse | b','0 | a | x\n5 | b | y','nan | a | b','0 | a |','-1 | a | b','0 | a']:
            with self.subTest(text=text), self.assertRaises(ValueError): parse_sections(text,5)

    def test_common_style_motif_and_per_section_prompt(self):
        from aven.story import scene_spec
        data={'plan':Plan.make(1,'16:9').__dict__,'prompt':'A dancer','seconds':5,'references':['one.png','two.png'],
              'story':{'style':'film grain','motif':'red jacket','reference_mode':'fixed','sections':[
                  {'start':0,'title':'Intro','prompt':'wide shot'},{'start':2,'title':'Chorus','prompt':'close-up'}]}}
        a=scene_spec(data,0); b=scene_spec(data,1)
        self.assertEqual(a['title'],'Intro'); self.assertEqual(b['title'],'Chorus')
        for prompt in (a['prompt'],b['prompt']):
            for anchor in ['A dancer','film grain','red jacket']: self.assertIn(anchor,prompt)
        self.assertIn('wide shot',a['prompt']); self.assertIn('close-up',b['prompt'])
        self.assertEqual((a['reference'],b['reference']),(0,0))
        data['story']['reference_mode']='alternate'
        self.assertEqual(scene_spec(data,1)['reference'],1)

    def test_suggestions_are_time_based_and_cover_short_tracks(self):
        from aven.story import suggested_sections, validate_story
        for seconds in [.2,2,5.375,180,86400]:
            sections=suggested_sections(seconds)
            self.assertEqual(sections[0]['start'],0)
            self.assertTrue(all(0<=x['start']<seconds for x in sections))
            validate_story({'style':'','motif':'','reference_mode':'fixed','sections':sections},seconds)

    def test_legacy_job_keeps_original_prompt_and_alternating_references(self):
        from aven.story import scene_spec
        data={'plan':Plan.make(1,'16:9').__dict__,'prompt':'original','seconds':3,'references':['a','b']}
        self.assertEqual(scene_spec(data,1)['prompt'],'original')
        self.assertEqual(scene_spec(data,1)['reference'],1)


if __name__=='__main__': unittest.main()


class PreviewLanguageTests(unittest.TestCase):
    def test_open_preview_captions_switch_language_without_changing_prompt(self):
        from pathlib import Path
        from aven.story import preview_text
        from aven.i18n import Locale, Bindings
        locale=Locale(Path('unused-settings.json')); rendered=[]
        bindings=Bindings(locale)
        source=preview_text([(1,{'start':0,'title':'Intro','prompt':'Musik hinzufügen {keep}'})])
        bindings.bind(rendered.append,source)
        self.assertIn('Szene 1',rendered[-1])
        locale.code='en'; bindings.refresh()
        self.assertIn('Scene 1',rendered[-1]); self.assertIn('Musik hinzufügen {keep}',rendered[-1])
        self.assertNotIn('Add music',rendered[-1])
