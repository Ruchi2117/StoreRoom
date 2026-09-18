"""Exactly two validation inference passes; reuse frozen NMS_001 evaluation."""
import json
import time
from pathlib import Path
from src.nms_experiment import ROOT, save, match_detections, summarize
from src.resolution_experiment import verify_protected as protect
from src.train_baseline import verify_dataset
from src.convert_smoke import digest
from src.counting import count_classes
from src.yolo_checks import read_yolo, decoded_boxes


def verify_protected():
    protect()
    snapshot = json.loads((ROOT/'reports/confidence_001_preservation.json').read_text())
    for name, expected in snapshot.items():
        assert digest(ROOT/name) == expected, f'Changed protected artifact: {name}'
    verify_dataset()
    return len(snapshot)


def main():
    setup_path = ROOT/'reports/confidence_001_setup.json'
    if setup_path.exists():
        raise FileExistsError('CONFIDENCE_001 already started; refusing to overwrite')
    protect()
    manifest_hash = verify_dataset()
    snapshot = json.loads((ROOT/'reports/nms_001_preservation.json').read_text())
    for folder in ['reports', 'src', 'configs', 'tests']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and 'confidence' not in p.name.lower():
                snapshot[p.relative_to(ROOT).as_posix()] = digest(p)
    save(ROOT/'reports/confidence_001_preservation.json', snapshot)
    from ultralytics import YOLO
    import ultralytics, torch
    setup = json.loads((ROOT/'reports/nms_001_setup.json').read_text())
    assert digest(Path(setup['checkpoint'])) == setup['checkpoint_sha256']
    assert manifest_hash == setup['dataset_manifest_sha256']
    setup['common_arguments'].pop('conf')
    setup['common_arguments']['iou'] = .50
    setup['runs'] = {'A':.25, 'B':.15}
    setup['metric_protocol'] = 'Unchanged NMS_001 same-class one-to-one matching at evaluation IoU >= 0.5; fixed operating points confidence 0.25 and 0.15. No AP pass.'
    setup['ultralytics'] = ultralytics.__version__
    setup['torch'] = torch.__version__
    setup['evaluation_source_sha256'] = {p:digest(ROOT/p) for p in ['src/nms_experiment.py','src/counting.py']}
    save(setup_path, setup)
    manifest = json.loads((ROOT/'reports/dataset_v01_manifest.json').read_text())
    rows = [r for r in manifest['images'] if r['split']=='val']
    assert [r['image'] for r in rows] == setup['images'] and len(rows)==26
    for tag,confidence in setup['runs'].items():
        started = time.perf_counter()
        model = YOLO(setup['checkpoint'])
        outputs = []
        for row in rows:
            path = ROOT/'data/yolo_v01/images/val'/row['image']
            pred = model.predict(str(path), conf=confidence, **setup['common_arguments'])[0]
            boxes = pred.boxes
            ds = [{'class_id':int(c),'confidence':float(s),'xyxy':b} for c,s,b in zip(boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist(),boxes.xyxy.cpu().tolist())]
            labels = ROOT/'data/yolo_v01/labels/val'/Path(row['image']).with_suffix('.txt')
            gt = decoded_boxes(read_yolo(labels),row['width'],row['height'])
            outputs.append({'image':row['image'],'scene_group':row['scene_group'],'truth':row['counts'],
                            'predicted':count_classes([d['class_id'] for d in ds]),'gt_boxes':gt,
                            'detections':ds,'matching':match_detections(ds,gt),'speed_ms':pred.speed})
        report = {'status':'completed','run':tag,'imgsz':320,'confidence':confidence,'nms_iou':.5,
                  'checkpoint_sha256':digest(Path(setup['checkpoint'])), 'duration_seconds':time.perf_counter()-started,
                  'images':outputs,**summarize(outputs)}
        save(ROOT/f'reports/confidence_001_{tag.lower()}.json',report)
        verify_protected()
        print(json.dumps({k:v for k,v in report.items() if k!='images'},indent=2),flush=True)


if __name__=='__main__':
    main()
