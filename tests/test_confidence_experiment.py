import json
import unittest
from src.nms_experiment import ROOT, match_detections, summarize
from src.confidence_experiment import verify_protected


class ConfidenceChecks(unittest.TestCase):
    def test_frozen_validation_protocol_and_metrics(self):
        self.assertGreater(verify_protected(),72)
        setup=json.loads((ROOT/'reports/confidence_001_setup.json').read_text())
        previous=json.loads((ROOT/'reports/nms_001_setup.json').read_text())
        args=previous['common_arguments'].copy()
        args.pop('conf')
        args['iou']=.5
        self.assertEqual(setup['common_arguments'],args)
        self.assertEqual(setup['runs'],{'A':.25,'B':.15})
        split=json.loads((ROOT/'configs/splits.json').read_text())['images']
        for tag,confidence in [('a',.25),('b',.15)]:
            run=json.loads((ROOT/f'reports/confidence_001_{tag}.json').read_text())
            self.assertEqual(run['imgsz'],320)
            self.assertEqual(run['confidence'],confidence)
            self.assertEqual(run['nms_iou'],.5)
            self.assertEqual(run['checkpoint_sha256'],previous['checkpoint_sha256'])
            self.assertEqual(set(r['image'] for r in run['images']),set(split['val']))
            self.assertEqual(len(run['images']),26)
            self.assertFalse(set(r['image'] for r in run['images']) & set(split['test']))
            for row in run['images']:
                self.assertEqual(row['matching'],match_detections(row['detections'],row['gt_boxes']))
            for key,value in summarize(run['images']).items():
                self.assertEqual(run[key],value)
        comparison=json.loads((ROOT/'reports/confidence_001_comparison.json').read_text())
        self.assertTrue(comparison['a_reproduces_resolution_001_a'])
        self.assertEqual(sum(comparison[k] for k in ['improved','unchanged','worsened']),26)
