"""One preregistered augmentation training run, preserving all earlier artifacts."""
import json
import platform
import time
from pathlib import Path
from src.nms_experiment import ROOT, save
from src.class_confidence_experiment import verify_protected as previous_protect
from src.train_baseline import verify_dataset
from src.convert_smoke import digest

AUGMENTATION={'hsv_s':.10,'hsv_v':.15,'translate':.03,'scale':.10,'degrees':3.0}


def verify_protected():
    snapshot=json.loads((ROOT/'reports/augmentation_001_preservation.json').read_text())
    for path,expected in snapshot.items():
        assert digest(ROOT/path)==expected, f'Protected artifact changed: {path}'
    verify_dataset()
    return len(snapshot)


def main():
    import yaml, torch, ultralytics
    from ultralytics import YOLO
    record_path=ROOT/'reports/augmentation_001_training.json'
    run=ROOT/'runs/augmentation_001'
    if record_path.exists() or run.exists():
        raise FileExistsError('Refusing to overwrite AUGMENTATION_001')
    previous_protect()
    snapshot=json.loads((ROOT/'reports/class_confidence_001_preservation.json').read_text())
    for folder in ['reports','src','configs','tests','runs']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and not any('augmentation_001' in part.lower() for part in p.parts) and p.name not in ['train_augmentation.py','evaluate_augmentation.py','analyze_augmentation.py','report_augmentation.py','test_augmentation.py']:
                snapshot[p.relative_to(ROOT).as_posix()]=digest(p)
    save(ROOT/'reports/augmentation_001_preservation.json',snapshot)
    old=json.loads((ROOT/'reports/baseline_002_experiment.json').read_text())
    assert platform.python_version()==old['python'] and torch.__version__==old['torch'] and ultralytics.__version__==old['ultralytics']
    assert digest(ROOT/'data/models/yolo11n.pt')==old['initial_weights_sha256']
    assert verify_dataset()==old['dataset_manifest_sha256']
    args=yaml.safe_load((ROOT/'configs/baseline_002.yaml').read_text())
    args.update(AUGMENTATION)
    (ROOT/'configs/augmentation_001.yaml').write_text(yaml.safe_dump(args,sort_keys=False))
    args.update(data=str(ROOT/'configs/yolo_v01.yaml'),project=str(ROOT/'runs'),name='augmentation_001')
    changes={k:[old['requested_settings'].get(k),v] for k,v in args.items() if old['requested_settings'].get(k)!=v}
    assert set(changes)==set(AUGMENTATION)|{'name'}
    record={'status':'running','initial_weights_sha256':old['initial_weights_sha256'],'dataset_manifest_sha256':old['dataset_manifest_sha256'],
            'configuration_sha256':digest(ROOT/'configs/augmentation_001.yaml'),'requested_settings':args,'controlled_changes':changes,
            'python':platform.python_version(),'torch':torch.__version__,'ultralytics':ultralytics.__version__}
    save(record_path,record)
    (ROOT/'reports/AUGMENTATION_001_RESULTS.md').write_text('# AUGMENTATION_001 (preregistered; training pending)\n\nA is the completed frozen BASELINE_002 30-epoch no-augmentation run. B starts from the identical pretrained yolo11n.pt.\n\nOnly training augmentation changes; output name is separate. Fixed seed 42, CPU, epochs 30, batch 4, 320px, AdamW lr0 .001.\n\nExact requested B training parameters, recorded before training:\n\n```json\n'+json.dumps(args,indent=2)+'\n```\n\nFixed final evaluation: both models use Red Bull .15, other classes .25, 320px, NMS .50 and unchanged class-score gate/counting evaluator. Training-internal validation retains BASELINE_002 conf .001 / NMS .70 for checkpoint selection; these metrics are separate. No test evaluation. One configuration only; no tuning.\n')
    started=time.perf_counter()
    try:
        model=YOLO(str(ROOT/'data/models/yolo11n.pt'))
        model.train(**args)
        record.update(status='completed',duration_seconds=time.perf_counter()-started,
                      actual_settings=yaml.safe_load((run/'args.yaml').read_text()),checkpoint=str(run/'weights/best.pt'),
                      checkpoint_sha256=digest(run/'weights/best.pt'),cpu_threads=torch.get_num_threads())
    except Exception as e:
        record.update(status='failed',error=repr(e),duration_seconds=time.perf_counter()-started)
        raise
    finally:
        save(record_path,record)
        verify_protected()


if __name__=='__main__':
    main()
