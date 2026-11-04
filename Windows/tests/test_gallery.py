import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from aven.jobs import create_job
from aven.policy import Plan
from aven.runtime import Cancellation


class GalleryTests(unittest.TestCase):
    def test_broken_project_does_not_hide_good_project(self):
        from aven.gallery import list_projects
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            good=create_job(root,Plan.make(1,'16:9'),'cat','',42,2,[],None,Cancellation())
            bad=root/'broken'; bad.mkdir(); (bad/'job.json').write_text('{')
            rows=list_projects(root)
            self.assertEqual(len(rows),2)
            row=next(x for x in rows if x['folder']==good)
            self.assertTrue(row['valid']); self.assertFalse(row['output_exists'])
            self.assertFalse(next(x for x in rows if x['folder']==bad)['valid'])

    def test_non_object_manifest_json_is_flagged_without_crashing_browser(self):
        from aven.gallery import list_projects
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); job=root/'broken'; job.mkdir(); manifest=job/'job.json'
            for value in [None,[],42,'broken']:
                with self.subTest(value=value):
                    manifest.write_text(json.dumps(value))
                    rows=list_projects(root)
                    self.assertEqual(len(rows),1); self.assertFalse(rows[0]['valid'])

    def test_invalid_metadata_types_are_flagged_before_preview(self):
        from aven.gallery import list_projects
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            job=create_job(root,Plan.make(1,'16:9'),'cat','',42,2,[],None,Cancellation())
            path=job/'job.json'; data=json.loads(path.read_text())
            for refs in [None,42,{},['../outside.png']]:
                data['references']=refs; path.write_text(json.dumps(data))
                self.assertFalse(list_projects(root)[0]['valid'])

    def test_only_exact_original_paths_and_saved_references_are_selected(self):
        from aven.gallery import scene_frames, reference_path
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); scene=root/'scene_000001'; scene.mkdir()
            f=scene/'generated_000.png'; Image.new('RGB',(8,8)).save(f)
            Image.new('RGB',(8,8)).save(scene/'unrelated.png')
            self.assertEqual(scene_frames(root,1),[f])
            with self.assertRaises(ValueError): scene_frames(root,-1)
            with self.assertRaises(ValueError): reference_path(root,{'references':['../outside.png']},0)
            outside=root.parent/(root.name+'-outside.png'); Image.new('RGB',(8,8)).save(outside)
            try:
                (scene/'generated_001.png').symlink_to(outside)
                self.assertEqual(scene_frames(root,1),[f])
            finally: outside.unlink()

    def test_live_status_templates_translate_and_unknown_eta_stays_unknown(self):
        from aven.telemetry import status_text
        from aven.i18n import Locale
        l=Locale(Path('unused-settings.json')); l.code='en'
        event={'stage':'loading','scene':1,'scenes':2,'step':0,'steps':20,'elapsed_seconds':65,'sampling_eta_seconds':None,'gpu':None}
        text=l.render(status_text(event))
        self.assertIn('01:05',text); self.assertIn('unavailable',text); self.assertIn('unknown',text)
        event.update(stage='sampling',step=5,sampling_eta_seconds=30,gpu={'used_mb':4000,'total_mb':10240,'utilization_percent':92})
        text=l.render(status_text(event))
        self.assertIn('5/20',text); self.assertIn('00:30',text); self.assertIn('4000',text)


if __name__=='__main__': unittest.main()

class AssessmentTests(unittest.TestCase):
    def test_user_review_is_saved_without_changing_measurements(self):
        from aven.gallery import save_assessment
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); path=root/'benchmark.json'
            path.write_text(json.dumps({'elapsed_seconds':42,'visual_assessment':'pending_user_review'}))
            save_assessment(root,'needs_work','blurred face')
            data=json.loads(path.read_text())
            self.assertEqual(data['elapsed_seconds'],42)
            self.assertEqual(data['visual_assessment'],'needs_work')
            self.assertEqual(data['visual_notes'],'blurred face')
            with self.assertRaises(ValueError): save_assessment(root,'automatic_quality_pass','')


class ReportValidationTests(unittest.TestCase):
    def test_corrupt_report_metadata_has_safe_display_fallbacks(self):
        from aven.gallery import report_caption
        from aven.i18n import Locale
        language=Locale(Path('unused-settings.json'))
        for data in [{'hardware':None},{'plan':[]},{'elapsed_seconds':'bad'},{'elapsed_seconds':10**400},{'status':[]},
                     {'peak_sampled_vram_mb':float('nan')},{'visual_notes':[]}]:
            with self.subTest(data=data):
                rendered=language.render(report_caption(data))
                self.assertIsInstance(rendered,str)
                self.assertIn('Nicht gemessen',rendered)
        with self.assertRaises(ValueError): report_caption([])

    def test_corrupt_existing_report_shows_invalid_message_without_creating_window(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from aven.i18n import Locale
        from aven.studio_panels import show_report
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); (root/'benchmark.json').write_text('[]')
            studio=SimpleNamespace(root=object(),language=Locale(root/'settings.json'))
            with patch('aven.studio_panels.messagebox.showerror') as error, patch('aven.studio_panels.messagebox.showinfo'):
                show_report(studio,root)
                self.assertTrue(error.called)
                self.assertEqual(error.call_args.args[1],'Messbericht ist ungültig.')
