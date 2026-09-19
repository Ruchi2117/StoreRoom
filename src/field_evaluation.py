"""Run the frozen detector once per field image, then create a count-only report."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import platform
import ast
from src.inference import Detector
from src.inference.annotation import save_annotation
from src.inference.images import decode_image
from src.field_cohort import KEYS, ROOT, PROTOCOL, digest, load_frozen, local_image, private_location, runtime, write_new
from src.field_metrics import analyze


def report_markdown(result):
    metrics = result['analysis']['overall']
    lines = ['# Independent field validation results', '',
        'Evaluation only: the frozen provisional model/configuration was not tuned.', '',
        f"Cohort hash: `{result['cohort_sha256']}`", f"Model hash: `{result['checkpoint_sha256']}`",
        f"Protocol hash: `{result['protocol_sha256']}`", f"Evaluation: {result['evaluated_at']}", '',
        '## Cohort and interpretation', '',
        f"Images: {metrics['image_count']}; independent scene groups (collector attested): {metrics['scene_count']}.",
        result['sample_limit'],
        f"Ground-truth records with post-prediction revisions: {result['post_prediction_truth_records']}.",
        'Hash checks detect exact copies; collection provenance and scene independence still require human verification.', '',
        '## Overall count results', '', '| Metric | Value |', '| --- | --- |']
    for key in ('ground_truth_total','predicted_total','counting_mae','exact_five_class_accuracy','over_count','under_count'):
        lines.append(f'| {key} | {metrics[key]} |')
    lines += ['', 'MAE is absolute error averaged over images × five classes. Over/under-counts do not cancel across classes.',
        'No detection precision/recall or mAP: no bounding-box ground truth.', '', '## Per class', '',
        '| Class | Truth | Predicted | Absolute error | MAE | Exact image accuracy |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for key, row in metrics['per_class'].items():
        lines.append(f"| {key} | {row['ground_truth_total']} | {row['predicted_total']} | {row['absolute_count_error']} | {row['mae']:.6f} | {row['exact_image_accuracy']:.6f} |")
    lines += ['', '## Per scene', '', '| Scene | Images | Truth | Predicted | MAE | Exact five-class accuracy | Over | Under |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for key, row in result['analysis']['per_scene'].items():
        lines.append(f"| {key} | {row['image_count']} | {row['ground_truth_total']} | {row['predicted_total']} | {row['counting_mae']:.6f} | {row['exact_five_class_accuracy']:.6f} | {row['over_count']} | {row['under_count']} |")
    lines += ['', '## Error analysis and representative examples', '',
        'See metrics.json for per-image errors. A predicted class with zero ground truth is a class-level false-positive count.',
        'Simultaneous over/under-counts are review candidates, not proven class confusion. Scene tags describe conditions, not error causes.',
        'Count-only labels cannot establish duplicate boxes, object-level matching, or whether small size/occlusion caused a miss.', '']
    rows = {r['image_id']:r for r in result['rows']}
    for category, ids in result['analysis']['representatives'].items():
        lines += [f'### {category}', '']
        for id in ids:
            row = rows[id]
            lines += [f"{id}: truth {row['truth']}; predicted {row['predicted']} (fixed class order).",
                f"![{id} saved detections]({result['visualizations'][id]})", '']
        if not ids:
            lines += ['No qualifying examples.', '']
    lines += ['## Comparison and limitations', '',
        'The HoloSelecta validation cohort and the field cohort are different populations and should not be treated as directly equivalent benchmarks.',
        'Do not pool scores or infer production readiness. Even 30 images / 5 groups is only a descriptive initial field baseline;',
        'correlated images do not become independent observations. Report class support and per-scene differences.',
        'All-zero classes measure false-positive behavior only, not recall for that product.', '',
        '## Reproducibility', '', f"Runtime: `{result['runtime']}`", f"Platform: {result['platform']}",
        f"Test definitions: {result['test_definition_count']} (static count, not a claim that this run executed tests).",
        'Frozen protocol/cohort and saved per-image predictions accompany this local report. Run the complete suite separately.', '',
        '## Conclusion and next milestone', '', result['sample_limit'],
        'These results describe this cohort only. Retain the frozen configuration; do not optimize it using these observations.',
        'Next milestone: collect a second prospectively specified independent cohort to check whether the observed scene/class patterns repeat.', '']
    return '\n'.join(lines)


def evaluate(root, manifest, expected_hash, output):
    root = private_location(root)
    output = private_location(output, 'output')
    cohort = load_frozen(root, manifest, expected_hash)
    output.mkdir(parents=True, exist_ok=False)
    incomplete = output/'INCOMPLETE'
    incomplete.write_text('Do not interpret partial outputs as a completed evaluation.\n')
    # Real CLI has no model/threshold/config override. Tests patch this constructor only.
    detector = Detector(output_dir=output/'visuals')
    rows, predictions = [], {}
    for record in cohort['images']:
        source = local_image(root, record['path']).read_bytes()
        if hashlib.sha256(source).hexdigest() != record['sha256']:
            raise ValueError('Image changed during inference')
        result = detector.predict(source, annotate=False)
        if [p.class_id for p in result.products] != list(range(5)):
            raise ValueError('Prediction class order differs from frozen mapping')
        predictions[record['image_id']] = result
        rows.append({'image_id':record['image_id'],'scene_id':record['scene_id'], 'tags':record['tags'],
            'truth':[record['ground_truth']['revisions'][-1]['counts'][key] for key in KEYS],
            'predicted':[p.count for p in result.products]})
    load_frozen(root, manifest, expected_hash)  # Fail if membership/labels/files changed mid-run.
    analysis = analyze(rows)
    selected = set().union(*map(set,analysis['representatives'].values()))
    visuals = {}
    for record in cohort['images']:
        if record['image_id'] in selected:
            bgr = decode_image(local_image(root, record['path']))
            generated = save_annotation(bgr, predictions[record['image_id']], output/'visuals')
            stable = record['image_id']+'.jpg'
            (output/'visuals'/generated).rename(output/'visuals'/stable)
            visuals[record['image_id']] = 'visuals/'+stable
    load_frozen(root, manifest, expected_hash)
    n, groups = len(rows), analysis['overall']['scene_count']
    sample_limit = ('Below the initial target of 30 images and 5 groups: this is a small pilot and cannot support broad generalization.'
        if n < 30 or groups < 5 else 'The initial size target is met, but this convenience cohort supports descriptive results for sampled scenes only, not population-wide or production claims.')
    tests = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
        for path in (ROOT/'tests').glob('test_*.py') for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))))
    record = {'evaluated_at':datetime.now(timezone.utc).isoformat(), 'cohort_sha256':expected_hash,
        'protocol_sha256':digest(PROTOCOL), 'checkpoint_sha256':detector.config.checkpoint_sha256,
        'model_id':detector.config.model_id, 'inference_config_sha256':digest(ROOT/'configs/inference_v01.json'),
        'runtime':runtime(),'platform':platform.platform(), 'test_definition_count':tests,
        'post_prediction_truth_records':sum(any(not r['before_predictions'] for r in i['ground_truth']['revisions']) for i in cohort['images']),
        'sample_limit':sample_limit,'rows':rows,'analysis':analysis,'visualizations':visuals}
    write_new(output/'metrics.json', record)
    write_new(output/'predictions.json',{id:p.model_dump(mode='json') for id,p in predictions.items()})
    write_new(output/'frozen_cohort.json', {'cohort':cohort,'cohort_sha256':expected_hash})
    (output/'REPORT.md').write_text(report_markdown(record),encoding='utf-8')
    incomplete.unlink()
    (output/'COMPLETE').write_text(expected_hash+'\n')
    return record
