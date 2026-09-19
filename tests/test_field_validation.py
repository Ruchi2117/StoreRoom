"""Synthetic unit fixtures only: these images are NOT independent field evidence."""
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from src.field_cohort import (KEYS, GroundTruth, Revision, freeze_cohort, load_frozen,
    validate_inputs, digest, object_hash, read_json, verify_protocol)
from src.field_metrics import analyze, summarize
from src.field_evaluation import evaluate
from src.field_cli import main
from src.inference.config import load_config
from src.inference.results import Prediction, Product, Detection


class SyntheticDetector:
    calls = 0

    def __init__(self, **kwargs):
        self.config = load_config()

    def predict(self, image, annotate=False):
        type(self).calls += 1
        assert annotate is False
        products = [Product(class_id=i,class_name=name,product_id=self.config.product_ids[i],count=1 if i==0 else 0,
            detections=[Detection(confidence=.75,bbox=(1,1,10,10))] if i==0 else []) for i,name in enumerate(self.config.names)]
        return Prediction(model_id=self.config.model_id,checkpoint_sha256=self.config.checkpoint_sha256,
            image_width=32,image_height=32,products=products,total_count=1)


class FieldValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root = self.temp/'cohort'
        (self.root/'images').mkdir(parents=True)
        self.collection = {'cohort_id':'synthetic_test_only','purpose':'independent_field_validation',
            'scenes':[{'scene_id':'scene_a','permission_obtained':True,'independent_from_holoselecta':True,'correlated_captures_grouped':True},
                      {'scene_id':'scene_b','permission_obtained':True,'independent_from_holoselecta':True,'correlated_captures_grouped':True}],
            'images':[]}
        self.truth = []
        for i in range(2):
            id = 'image_'+str(i)
            image = Image.frombytes('RGB',(32,32),random.Random(42+i).randbytes(32*32*3))
            image.save(self.root/'images'/f'{id}.png')
            self.collection['images'].append({'image_id':id,'path':f'images/{id}.png','scene_id':'scene_a' if i==0 else 'scene_b',
                'captured_on':'2026-09-19','privacy_reviewed':True,'original_field_capture':True,'tags':['small_products']})
            self.truth.append({'image_id':id,'revisions':[{'revision':1,'counts':dict(zip(KEYS,[i,0,0,0,0])),
                'annotator_id':'test_annotator','recorded_at':'2026-09-19T10:00:00Z','before_predictions':True,
                'reason':'Synthetic unit fixture, not a field collection','previous_revision_sha256':None}]})
        self.write()
        self.frozen = self.root/'frozen.json'

    def write(self):
        (self.root/'collection.json').write_text(json.dumps(self.collection))
        (self.root/'ground_truth.json').write_text(json.dumps(self.truth))

    def freeze(self):
        return freeze_cohort(self.root,self.frozen)['cohort_sha256']

    def test_manifest_creation_checksums_and_scene_assignments(self):
        result = validate_inputs(self.root)
        self.assertEqual(len(result['images']),2)
        self.assertEqual(len(result['scenes']),2)
        row = result['images'][0]
        self.assertEqual(row['sha256'],digest(self.root/row['path']))
        self.assertEqual(row['ground_truth_reference'],'ground_truth.json#image_0')
        frozen_hash = self.freeze()
        self.assertEqual(load_frozen(self.root,self.frozen,frozen_hash)['cohort_id'],'synthetic_test_only')
        with self.assertRaises(FileExistsError):
            freeze_cohort(self.root,self.frozen)

    def test_duplicate_bytes_and_reencoded_pixels_rejected(self):
        first, second = [self.root/r['path'] for r in self.collection['images']]
        second.write_bytes(first.read_bytes())
        with self.assertRaisesRegex(ValueError,'Duplicate image'):
            validate_inputs(self.root)
        with Image.open(first) as image:
            image.save(second,compress_level=0)
        self.assertNotEqual(digest(first),digest(second))
        with self.assertRaisesRegex(ValueError,'Duplicate image'):
            validate_inputs(self.root)

    def test_ground_truth_schema_rejects_invalid_counts_and_keys(self):
        for bad in (-1, 1.5, True, '2'):
            row = json.loads(json.dumps(self.truth[0]))
            row['revisions'][0]['counts'][KEYS[0]] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                GroundTruth.model_validate(row)
        for keys in ({}, {**self.truth[0]['revisions'][0]['counts'],'unknown':1}):
            row = json.loads(json.dumps(self.truth[0]))
            row['revisions'][0]['counts'] = keys
            with self.assertRaises(ValueError):
                GroundTruth.model_validate(row)

    def test_missing_image_and_missing_truth_rejected(self):
        self.truth.pop()
        self.write()
        with self.assertRaisesRegex(ValueError,'ground-truth'):
            validate_inputs(self.root)
        (self.root/'ground_truth.json').write_text(json.dumps([self.truth[0],{**self.truth[0],'image_id':'image_1'}]))
        (self.root/'images/image_1.png').unlink()
        with self.assertRaises(ValueError):
            validate_inputs(self.root)

    def test_frozen_membership_and_labels_cannot_change(self):
        expected = self.freeze()
        (self.root/'images/extra.png').write_bytes((self.root/'images/image_0.png').read_bytes())
        with self.assertRaisesRegex(ValueError,'membership'):
            load_frozen(self.root,self.frozen,expected)
        (self.root/'images/extra.png').unlink()
        self.truth[0]['revisions'][0]['counts'][KEYS[0]] = 9
        self.write()
        with self.assertRaisesRegex(ValueError,'changed'):
            load_frozen(self.root,self.frozen,expected)

    def test_frozen_image_bytes_and_manifest_hash_enforced(self):
        expected = self.freeze()
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            load_frozen(self.root,self.frozen,'0'*64)
        envelope = read_json(self.frozen)
        envelope['cohort']['cohort_id'] = 'altered'
        self.frozen.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            load_frozen(self.root,self.frozen,expected)

    def test_valid_pixel_change_after_freeze_is_rejected(self):
        expected = self.freeze()
        path = self.root/'images/image_0.png'
        with Image.open(path) as source:
            changed = source.copy()
        changed.putpixel((0,0),(1,2,3))
        changed.save(path)
        with self.assertRaisesRegex(ValueError,'changed'):
            load_frozen(self.root,self.frozen,expected)

    def test_near_duplicates_must_remain_in_same_scene(self):
        with Image.open(self.root/'images/image_0.png') as source:
            changed = source.copy()
        changed.putpixel((0,0),(1,2,3))
        changed.save(self.root/'images/image_1.png')
        with self.assertRaisesRegex(ValueError,'Near-duplicate'):
            validate_inputs(self.root)
        self.collection['images'][1]['scene_id'] = 'scene_a'
        self.collection['scenes'] = self.collection['scenes'][:1]
        self.write()
        result = validate_inputs(self.root)
        self.assertEqual(len(result['near_duplicate_candidates']),1)

    def test_metrics_and_per_class_values(self):
        rows = [{'image_id':'a','scene_id':'one','truth':[2,1,0,0,0],'predicted':[1,2,1,0,0]},
                {'image_id':'b','scene_id':'two','truth':[0,0,0,0,0],'predicted':[0,0,0,0,0]}]
        result = summarize(rows)
        self.assertEqual(result['counting_mae'], .3)
        self.assertEqual(result['exact_five_class_accuracy'], .5)
        self.assertEqual((result['over_count'],result['under_count']),(2,1))
        self.assertEqual((result['ground_truth_total'],result['predicted_total']),(3,4))
        self.assertEqual(result['per_class']['red_bull']['absolute_count_error'],1)
        self.assertEqual(result['per_class']['red_bull']['mae'],.5)
        self.assertEqual(result['per_class']['red_bull']['exact_image_accuracy'],.5)

    def test_per_scene_and_error_categories_are_count_only(self):
        rows = [{'image_id':'a','scene_id':'one','truth':[2,0,0,0,0],'predicted':[0,1,0,0,0],'tags':['crowded']},
                {'image_id':'b','scene_id':'two','truth':[0,0,0,0,0],'predicted':[0,0,0,0,0]}]
        result = analyze(rows)
        self.assertEqual(result['per_scene']['one']['counting_mae'],.6)
        self.assertEqual(result['per_scene']['two']['counting_mae'],0)
        error = result['image_errors'][0]
        self.assertEqual(error['completely_missed_classes'],['red_bull'])
        self.assertEqual(error['zero_ground_truth_class_predictions'],['knoppers'])
        self.assertTrue(error['possible_confusion_needs_visual_review'])
        self.assertEqual(error['preannotated_conditions_with_error'],['crowded'])
        self.assertNotIn('precision', result['overall'])
        self.assertEqual(analyze(list(reversed(rows))),result)

    def test_deterministic_pipeline_and_visuals_with_fake_detector(self):
        expected = self.freeze()
        SyntheticDetector.calls = 0
        with patch('src.field_evaluation.Detector',SyntheticDetector):
            a = evaluate(self.root,self.frozen,expected,self.temp/'run_a')
            b = evaluate(self.root,self.frozen,expected,self.temp/'run_b')
        self.assertEqual(SyntheticDetector.calls,4)
        self.assertEqual(a['rows'],b['rows'])
        self.assertEqual(a['analysis'],b['analysis'])
        self.assertIn('small pilot',a['sample_limit'])
        self.assertTrue((self.temp/'run_a/COMPLETE').exists())
        self.assertFalse((self.temp/'run_a/INCOMPLETE').exists())
        for image in a['visualizations'].values():
            with Image.open(self.temp/'run_a'/image) as saved:
                self.assertFalse(saved.getexif())
                saved.verify()

    def test_midrun_mutation_leaves_no_completed_report(self):
        expected = self.freeze()
        root = self.root
        class MutatingDetector(SyntheticDetector):
            def predict(self,*args,**kwargs):
                result = super().predict(*args,**kwargs)
                (root/'images/unlisted.png').write_bytes((root/'images/image_0.png').read_bytes())
                return result
        with patch('src.field_evaluation.Detector',MutatingDetector), self.assertRaises(ValueError):
            evaluate(self.root,self.frozen,expected,self.temp/'failed')
        self.assertTrue((self.temp/'failed/INCOMPLETE').exists())
        self.assertFalse((self.temp/'failed/REPORT.md').exists())

    def test_consent_privacy_and_invalid_scene_fail(self):
        for key in ('permission_obtained','independent_from_holoselecta','correlated_captures_grouped'):
            self.collection['scenes'][0][key] = False
            self.write()
            with self.assertRaises(ValueError):
                validate_inputs(self.root)
            self.collection['scenes'][0][key] = True
        self.collection['images'][0]['privacy_reviewed'] = False
        self.write()
        with self.assertRaises(ValueError):
            validate_inputs(self.root)
        self.collection['images'][0]['privacy_reviewed'] = True
        self.collection['images'][0]['scene_id'] = 'unknown'
        self.write()
        with self.assertRaisesRegex(ValueError,'scene'):
            validate_inputs(self.root)

    def test_unsafe_paths_and_malformed_json_fail(self):
        for name in ('../image.png','/private.png','images/../../private.png','images\\x.png'):
            self.collection['images'][0]['path'] = name
            self.write()
            with self.assertRaises(ValueError):
                validate_inputs(self.root)
        (self.root/'collection.json').write_text('{broken')
        self.assertEqual(main(['validate','--root',str(self.root)]),1)
        (self.root/'collection.json').write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError,'Duplicate JSON'):
            read_json(self.root/'collection.json')

    def test_holoselecta_hashes_rejected_without_reading_test_images(self):
        real_reader = read_json
        def known(path):
            if Path(path).name == 'image_manifest.json':
                return [{'sha256':digest(self.root/'images/image_0.png'),'pixel_sha256':'unused'}]
            return real_reader(path)
        with patch('src.field_cohort.read_json',side_effect=known), self.assertRaisesRegex(ValueError,'HoloSelecta'):
            validate_inputs(self.root)

    def test_revision_history_is_chained_and_posthoc_is_recorded(self):
        previous = Revision.model_validate(self.truth[0]['revisions'][0]).model_dump(mode='json')
        correction = {**previous,'revision':2,'before_predictions':False,'reason':'Later human correction after predictions',
            'previous_revision_sha256':object_hash(previous),'recorded_at':'2026-09-19T11:00:00Z'}
        self.truth[0]['revisions'].append(correction)
        self.write()
        expected = self.freeze()
        with patch('src.field_evaluation.Detector',SyntheticDetector):
            result = evaluate(self.root,self.frozen,expected,self.temp/'revised')
        self.assertEqual(result['post_prediction_truth_records'],1)
        self.truth[0]['revisions'][0]['counts'][KEYS[0]] = 55
        with self.assertRaisesRegex(ValueError,'hash chain'):
            GroundTruth.model_validate(self.truth[0])

    def test_empty_cohort_and_invalid_metric_vectors_fail(self):
        self.collection['images'] = []
        self.write()
        with self.assertRaises(ValueError):
            validate_inputs(self.root)
        for truth in ([1,2],[-1,0,0,0,0],[True,0,0,0,0],[1.5,0,0,0,0]):
            with self.assertRaises(ValueError):
                summarize([{'image_id':'x','scene_id':'s','truth':truth,'predicted':[0]*5}])
        with self.assertRaises(ValueError):
            summarize([])

    def test_cli_init_creates_empty_template_and_protocol_is_verified(self):
        self.assertEqual(main(['init','--root',str(self.temp/'new')]),0)
        self.assertEqual(read_json(self.temp/'new/collection.json')['images'],[])
        self.assertEqual(verify_protocol()['protocol_version'],'field-counts-v1')
