"""Analyze saved resolution runs without further inference."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from src.nms_experiment import ROOT, save
from src.train_augmentation import verify_protected
from src.analyze_nms import compare_image, same_prediction
from src.review_baseline_002 import iou
from src.counting import counting_metrics
from src.preview_yolo import panel


def main():
    verify_protected()
    a,b=[json.loads((ROOT/f'reports/augmentation_001_{t}.json').read_text()) for t in ['a','b']]
    old=json.loads((ROOT/'reports/class_confidence_001_b.json').read_text())
    assert [r['image'] for r in a['images']]==[r['image'] for r in old['images']]
    replay=all(x['predicted']==y['predicted'] and len(x['detections'])==len(y['detections']) and all(same_prediction(p,q) for p,q in zip(x['detections'],y['detections'])) for x,y in zip(a['images'],old['images']))
    assert replay, 'A must reproduce CLASS_CONFIDENCE_001 B'
    comparisons=[compare_image(x,y) for x,y in zip(a['images'],b['images'])]
    source={r['image']:r for r in json.loads((ROOT/'reports/image_manifest.json').read_text())}
    manifest={r['image']:r for r in json.loads((ROOT/'reports/dataset_v01_manifest.json').read_text())['images'] if r['split']=='val'}
    cohorts={
        'crowded_30plus_source_objects':[i for i,r in enumerate(a['images']) if len(source[r['image']]['objects'])>=30],
        'multi_instance_2plus':[i for i,r in enumerate(a['images']) if max(r['truth'])>=2],
        'zero_predictions_with_targets_at_320':[i for i,r in enumerate(a['images']) if sum(r['truth'])>0 and sum(r['predicted'])==0],
        'zero_true_positives_with_targets_at_320':[i for i,r in enumerate(a['images']) if sum(r['truth'])>0 and not r['matching']['matched_gt_indices']]}
    cohort_results={}
    for key,indices in cohorts.items():
        cohort_results[key]={'images':[a['images'][i]['image'] for i in indices]}
        if indices:
            for tag,run in [('A',a),('B',b)]:
                cohort_results[key][tag]=counting_metrics([run['images'][i]['truth'] for i in indices],[run['images'][i]['predicted'] for i in indices])
    identities={}
    small={}
    for tag,run in [('A',a),('B',b)]:
        wrong=valser=light=small_n=small_tp=0
        for r in run['images']:
            for dec in r['matching']['predictions']:
                p=r['detections'][dec['prediction_index']]
                if dec['kind']=='wrong_class_candidate':
                    wrong+=1
                    valser+= {p['class_id'],r['gt_boxes'][dec['gt_index']][0]}=={2,3}
                if dec['kind']!='tp' and p['class_id']==0:
                    light+=any(o['label']=='redbull_light__33__90162800' and iou(p['xyxy'],[v-1 for v in o['box']])>=.5 for o in source[r['image']]['objects'])
            scale=320/max(manifest[r['image']]['width'],manifest[r['image']]['height'])
            ids=[j for j,g in enumerate(r['gt_boxes']) if (g[3]-g[1])*(g[4]-g[2])*scale**2 < 32**2]
            small_n+=len(ids)
            small_tp+=len(set(ids)&set(r['matching']['matched_gt_indices']))
        identities[tag]={'wrong_class_candidates':wrong,'valser_confusions':valser,'regular_on_light':light}
        small[tag]={'targets':small_n,'matched':small_tp,'recall':small_tp/small_n if small_n else None}
    result={'a_reproduces_class_confidence_001_b':replay,'images':comparisons,'cohorts':cohort_results,'identity_errors':identities,'small_targets':small,
            'improved':sum(r['count_error_delta']<0 for r in comparisons),'unchanged':sum(r['count_error_delta']==0 for r in comparisons),'worsened':sum(r['count_error_delta']>0 for r in comparisons),
            'lost_gt_matches':sum(len(r['lost_gt_indices']) for r in comparisons),'gained_gt_matches':sum(len(r['gained_gt_indices']) for r in comparisons),
            'correct_vectors_became_incorrect':[r['image'] for r in comparisons if r['correct_vector_became_incorrect']]}
    save(ROOT/'reports/augmentation_001_comparison.json',result)
    # Save every validation comparison, allowing representative selection after review.
    for x,y in zip(a['images'],b['images']):
        path=ROOT/'data/yolo_v01/images/val'/x['image']
        canvas=Image.new('RGB',(1860,690),'#171c25')
        canvas.paste(panel(path,x['gt_boxes'],'Ground truth | '+x['image']),(0,0))
        for j,(title,r) in enumerate([('A: no augmentation',x),('B: augmentation',y)],1):
            canvas.paste(panel(path,[(d['class_id'],*d['xyxy']) for d in r['detections']],title+' | fixed class cutoffs'),(620*j,0))
        ImageDraw.Draw(canvas).text((10,640),f"Truth {x['truth']} | A {x['predicted']} | B {y['predicted']} | Red Bull / Knoppers / Classic / Still / Capri-Sun",fill='white',font=ImageFont.load_default(size=18))
        canvas.save(ROOT/'reports/visuals'/f"augmentation_001_{Path(x['image']).stem}.jpg",quality=92)
    verify_protected()
    print(json.dumps({k:v for k,v in result.items() if k!='images'},indent=2))
    for r in comparisons:
        print(r['image'],r['truth'],r['a_counts'],r['b_counts'],r['count_error_delta'])


if __name__=='__main__':
    main()
