"""Evaluate A and B once with the unchanged class-confidence pipeline."""
import json
import time
from pathlib import Path
from src.nms_experiment import ROOT, save, match_detections, summarize
from src.train_augmentation import verify_protected
from src.convert_smoke import digest
from src.counting import count_classes
from src.yolo_checks import read_yolo, decoded_boxes


def main():
    setup_path=ROOT/'reports/augmentation_001_setup.json'
    if setup_path.exists():
        raise FileExistsError('AUGMENTATION_001 inference already started')
    verify_protected()
    trained=json.loads((ROOT/'reports/augmentation_001_training.json').read_text())
    assert trained['status']=='completed'
    setup=json.loads((ROOT/'reports/class_confidence_001_setup.json').read_text())
    setup['checkpoints']={'A':setup.pop('checkpoint'),'B':trained['checkpoint']}
    setup['checkpoint_hashes']={'A':setup.pop('checkpoint_sha256'),'B':trained['checkpoint_sha256']}
    setup['runs']={'A':[.15,.25,.25,.25,.25],'B':[.15,.25,.25,.25,.25]}
    setup['metric_protocol']='Unchanged class-specific inference at 320, NMS .50, Red Bull .15 / others .25; NMS_001 counting/matching.'
    save(setup_path,setup)
    from src.class_confidence_predictor import ClassConfidencePredictor
    from ultralytics import YOLO
    rows=[r for r in json.loads((ROOT/'reports/dataset_v01_manifest.json').read_text())['images'] if r['split']=='val']
    assert len(rows)==26 and [r['image'] for r in rows]==setup['images']
    for tag,thresholds in setup['runs'].items():
        checkpoint=Path(setup['checkpoints'][tag])
        assert digest(checkpoint)==setup['checkpoint_hashes'][tag]
        started=time.perf_counter()
        model=YOLO(str(checkpoint))
        predictor=type('ConfiguredPredictor',(ClassConfidencePredictor,),{'thresholds':tuple(thresholds)})
        outputs=[]
        for row in rows:
            pred=model.predict(str(ROOT/'data/yolo_v01/images/val'/row['image']),conf=min(thresholds),predictor=predictor,**setup['common_arguments'])[0]
            boxes=pred.boxes
            ds=[{'class_id':int(c),'confidence':float(s),'xyxy':b} for c,s,b in zip(boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist(),boxes.xyxy.cpu().tolist())]
            gt=decoded_boxes(read_yolo(ROOT/'data/yolo_v01/labels/val'/Path(row['image']).with_suffix('.txt')),row['width'],row['height'])
            outputs.append({'image':row['image'],'scene_group':row['scene_group'],'truth':row['counts'],'predicted':count_classes([d['class_id'] for d in ds]),'gt_boxes':gt,'detections':ds,'matching':match_detections(ds,gt)})
        save(ROOT/f'reports/augmentation_001_{tag.lower()}.json',{'status':'completed','run':tag,'checkpoint_sha256':digest(checkpoint),'class_thresholds':thresholds,'duration_seconds':time.perf_counter()-started,'images':outputs,**summarize(outputs)})
        verify_protected()


if __name__=='__main__':
    main()
