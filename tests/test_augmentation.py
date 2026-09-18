import json
import unittest
import yaml
from src.nms_experiment import ROOT, summarize
from src.train_augmentation import AUGMENTATION, verify_protected


class AugmentationChecks(unittest.TestCase):
    def test_only_augmentation_training_changes(self):
        a=yaml.safe_load((ROOT/'configs/baseline_002.yaml').read_text())
        b=yaml.safe_load((ROOT/'configs/augmentation_001.yaml').read_text())
        self.assertEqual({k:b[k] for k in b if a.get(k)!=b[k]},AUGMENTATION)
        training=json.loads((ROOT/'reports/augmentation_001_training.json').read_text())
        old=json.loads((ROOT/'reports/baseline_002_experiment.json').read_text())
        self.assertEqual(training['status'],'completed')
        self.assertEqual(training['initial_weights_sha256'],old['initial_weights_sha256'])
        actual={k:[old['actual_settings'].get(k),v] for k,v in training['actual_settings'].items() if old['actual_settings'].get(k)!=v}
        self.assertFalse(set(actual)-set(AUGMENTATION)-{'name','save_dir'})

    def test_fixed_validation_and_protected_artifacts(self):
        self.assertGreater(verify_protected(),256)
        setup=json.loads((ROOT/'reports/augmentation_001_setup.json').read_text())
        self.assertEqual(setup['runs']['A'],setup['runs']['B'])
        self.assertEqual(setup['runs']['A'],[.15,.25,.25,.25,.25])
        old=json.loads((ROOT/'reports/class_confidence_001_setup.json').read_text())
        self.assertEqual(setup['common_arguments'],old['common_arguments'])
        split=json.loads((ROOT/'configs/splits.json').read_text())['images']
        for tag in ['a','b']:
            run=json.loads((ROOT/f'reports/augmentation_001_{tag}.json').read_text())
            self.assertEqual(set(r['image'] for r in run['images']),set(split['val']))
            self.assertEqual(len(run['images']),26)
            for k,v in summarize(run['images']).items():
                self.assertEqual(run[k],v)
        comp=json.loads((ROOT/'reports/augmentation_001_comparison.json').read_text())
        self.assertTrue(comp['a_reproduces_class_confidence_001_b'])
