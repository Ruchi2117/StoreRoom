import json
import unittest
from src.nms_experiment import ROOT, protect, match_detections, summarize
from src.analyze_nms import compare_image


class NmsChecks(unittest.TestCase):
    def test_duplicate_and_wrong_class_do_not_become_true_positives(self):
        gt=[(0,0,0,10,10)]
        detections=[{'class_id':c,'confidence':s,'xyxy':[0,0,10,10]} for c,s in [(0,.9),(0,.8),(1,.7)]]
        result=match_detections(detections,gt)
        self.assertEqual([r['kind'] for r in result['predictions']],['tp','duplicate_candidate','wrong_class_candidate'])
        self.assertEqual(result['matched_gt_indices'],[0])
        self.assertEqual(result['missed_gt_indices'],[])

    def test_replacement_box_is_not_automatically_a_lost_neighbor(self):
        gt=[(0,0,0,10,10)]
        def row(box):
            ds=[{'class_id':0,'confidence':.9,'xyxy':box}]
            return {'image':'fixture','truth':[1,0,0,0,0],'predicted':[1,0,0,0,0],
                    'detections':ds,'matching':match_detections(ds,gt)}
        result=compare_image(row([0,0,10,10]),row([0,0,9,10]))
        self.assertEqual(len(result['removed']),1)
        self.assertEqual(result['added_b_indices'],[0])
        self.assertEqual(result['lost_gt_indices'],[])
        self.assertFalse(result['correct_vector_became_incorrect'])

    def test_real_runs_preserve_inputs_and_validation_only(self):
        self.assertGreater(protect(),50)
        setup=json.loads((ROOT/'reports/nms_001_setup.json').read_text())
        self.assertEqual(setup['runs'],{'A':.7,'B':.5})
        self.assertEqual(setup['common_arguments']['conf'],.25)
        self.assertFalse(setup['standard_ultralytics_validation_run'])
        splits=json.loads((ROOT/'configs/splits.json').read_text())['images']
        for tag in ['a','b']:
            report=json.loads((ROOT/f'reports/nms_001_{tag}.json').read_text())
            self.assertEqual(set(r['image'] for r in report['images']),set(splits['val']))
            self.assertEqual(len(report['images']),26)
            self.assertEqual(report['checkpoint_sha256'],setup['checkpoint_sha256'])
            measured=summarize(report['images'])
            for key,value in measured.items():
                self.assertEqual(value,report[key])
        comparison=json.loads((ROOT/'reports/nms_001_comparison.json').read_text())
        self.assertTrue(comparison['a_reproduces_baseline_002'])
