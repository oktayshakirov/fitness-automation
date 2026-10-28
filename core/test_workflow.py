"""Workflow regressions: version-bound approval and safe draft creation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.approvals import record_review, is_approved
import exercises

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ('catalog', 'motion/specs', 'motion/patterns'):
            (self.root / folder).mkdir(parents=True)
        self.cat = dict(id='demo', name='Demo', reviewed=False, source='original',
                        primary=['biceps'], secondary=[], equipment=[], steps=['Step'],
                        cues=['Cue'], mistakes=['Mistake'], breathing='Breathe')
        self.motion = dict(id='demo', approved=False, pattern='floor', tempo={'out':30,'back':30}, views=['front'])
        self.write('catalog/demo.json', self.cat)
        self.write('motion/specs/demo.json', self.motion)
        (self.root / 'motion/patterns/floor.py').touch()
        self.entry = dict(spec_sha256='spec1', pipeline_sha256='pipe1', media={'loop.mp4':{'sha256':'video1'}})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def test_approval_expires_for_changed_spec_pipeline_or_media(self):
        record_review('demo', True, self.entry, 'Explicit reviewer approval', self.root)
        self.assertTrue(is_approved('demo', self.entry, self.root))
        for key in ('spec_sha256', 'pipeline_sha256', 'media'):
            changed = copy.deepcopy(self.entry)
            changed[key] = 'changed' if key != 'media' else {'loop.mp4':{'sha256':'video2'}}
            self.assertFalse(is_approved('demo', changed, self.root), key)
        record_review('demo', False, None, 'Fix wrist', self.root)
        self.assertFalse(is_approved('demo', self.entry, self.root))
        self.assertFalse(json.loads((self.root/'catalog/demo.json').read_text())['reviewed'])
        self.assertEqual(len((self.root/'approvals/history.jsonl').read_text().splitlines()), 2)

    def test_model_approvals_are_independent_and_legacy_does_not_transfer(self):
        male={**self.entry,'model':'male'};female={**self.entry,'model':'female'}
        record_review('demo',True,self.entry,'Legacy reviewed',self.root)
        self.assertFalse(is_approved('demo',male,self.root))
        self.assertFalse(is_approved('demo',female,self.root))
        record_review('demo',True,male,'Male reviewed',self.root)
        self.assertTrue(is_approved('demo',male,self.root))
        self.assertFalse(is_approved('demo',female,self.root))
        record_review('demo',True,female,'Female reviewed',self.root)
        record_review('demo',False,male,'Male needs revision',self.root)
        self.assertFalse(is_approved('demo',male,self.root))
        self.assertTrue(is_approved('demo',female,self.root))
        self.assertTrue(is_approved('demo',self.entry,self.root))

    def test_legacy_flags_alone_are_not_a_review_record(self):
        self.cat['reviewed'] = self.motion['approved'] = True
        self.write('catalog/demo.json', self.cat)
        self.write('motion/specs/demo.json', self.motion)
        self.assertFalse(is_approved('demo', self.entry, self.root))

    def test_new_draft_does_not_copy_approval_or_claim_source(self):
        with patch.object(exercises, 'ROOT', self.root):
            exercises.create('new_demo', 'demo', 'New demo')
            cat, motion = exercises.pair('new_demo')
            self.assertFalse(cat['reviewed'] or motion['approved'])
            self.assertEqual(motion['id'], 'new_demo')
            self.assertIn('TODO:', cat['source'])
            with self.assertRaisesRegex(ValueError, 'TODO'):
                exercises.validate('new_demo')
            before = (self.root/'catalog/new_demo.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'already exists'):
                exercises.create('new_demo', 'demo', 'Overwrite')
            self.assertEqual(before, (self.root/'catalog/new_demo.json').read_bytes())

    def test_validator_rejects_mismatched_ids_and_duplicate_views(self):
        with patch.object(exercises, 'ROOT', self.root):
            exercises.validate('demo')
            self.motion['views'] = ['front','front']
            self.write('motion/specs/demo.json', self.motion)
            with self.assertRaisesRegex(ValueError, 'unique'):
                exercises.validate('demo')
            self.motion['id'] = 'wrong'
            self.write('motion/specs/demo.json', self.motion)
            with self.assertRaisesRegex(ValueError, 'IDs'):
                exercises.validate('demo')

if __name__ == '__main__':
    unittest.main()
