"""Compare stored NMS runs, including lost ground-truth matches and count regressions."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from src.nms_experiment import ROOT, protect, save
from src.review_baseline_002 import iou
from src.preview_yolo import panel


def same_prediction(a,b):
    return a["class_id"]==b["class_id"] and abs(a["confidence"]-b["confidence"])<=1e-6 and max(abs(x-y) for x,y in zip(a["xyxy"],b["xyxy"]))<=1e-3


def compare_image(a,b):
    available=set(range(len(b["detections"])))
    kept=[]
    removed=[]
    for i,p in enumerate(a["detections"]):
        hits=[j for j in available if same_prediction(p,b["detections"][j])]
        if hits:
            j=hits[0]
            available.remove(j)
            kept.append([i,j])
        else:
            removed.append(i)
    ma={d["prediction_index"]:d for d in a["matching"]["predictions"]}
    mb={d["prediction_index"]:d for d in b["matching"]["predictions"]}
    lost=set(a["matching"]["matched_gt_indices"])-set(b["matching"]["matched_gt_indices"])
    gained=set(b["matching"]["matched_gt_indices"])-set(a["matching"]["matched_gt_indices"])
    details=[]
    for i in removed:
        p=a["detections"][i]
        candidates=[(j,iou(p["xyxy"],q["xyxy"])) for j,q in enumerate(b["detections"])
                    if q["class_id"]==p["class_id"] and q["confidence"]>=p["confidence"]]
        candidate=max(candidates,key=lambda pair:pair[1]) if candidates else None
        details.append({"a_index":i,"prediction":p,"a_match":ma[i],
                        "overlapping_b_index":candidate[0] if candidate else None,
                        "prediction_pair_iou":candidate[1] if candidate else None,
                        "b_match":mb[candidate[0]] if candidate else None,
                        "lost_previously_matched_gt":ma[i]["kind"]=="tp" and ma[i]["gt_index"] in lost})
    ta=np.array(a["truth"])
    ea=np.array(a["predicted"])-ta
    eb=np.array(b["predicted"])-ta
    return {"image":a["image"],"truth":a["truth"],"a_counts":a["predicted"],"b_counts":b["predicted"],
            "a_sum_absolute_error":int(abs(ea).sum()),"b_sum_absolute_error":int(abs(eb).sum()),
            "count_error_delta":int(abs(eb).sum()-abs(ea).sum()),"kept_indices":kept,
            "removed":details,"added_b_indices":sorted(available),"lost_gt_indices":sorted(lost),"gained_gt_indices":sorted(gained),
            "correct_vector_became_incorrect":bool(np.all(ea==0) and not np.all(eb==0)),
            "correct_class_counts_became_incorrect":[i for i in range(5) if ea[i]==0 and eb[i]!=0],
            "raw_predictions_unchanged":len(removed)==0 and not available}


def main():
    protect()
    a=json.loads((ROOT/"reports/nms_001_a.json").read_text())
    b=json.loads((ROOT/"reports/nms_001_b.json").read_text())
    old=json.loads((ROOT/"reports/baseline_002_val.json").read_text())
    lookup_a={r["image"]:r for r in a["images"]}
    lookup_b={r["image"]:r for r in b["images"]}
    assert lookup_a.keys()==lookup_b.keys()
    replay=all(r["predicted"]==lookup_a[r["image"]]["predicted"] and
               len(r["detections"])==len(lookup_a[r["image"]]["detections"]) and
               all(same_prediction(x,y) for x,y in zip(r["detections"],lookup_a[r["image"]]["detections"])) for r in old["images"])
    rows=[compare_image(r,lookup_b[r["image"]]) for r in a["images"]]
    categories={
        "duplicate_removed_without_lost_gt":[r["image"] for r in rows if any(d["a_match"]["kind"]=="duplicate_candidate" for d in r["removed"]) and not r["lost_gt_indices"]],
        "lost_gt_matches":[r["image"] for r in rows if r["lost_gt_indices"]],
        "unchanged_predictions":[r["image"] for r in rows if r["raw_predictions_unchanged"]],
        "wrong_class_removed":[r["image"] for r in rows if any(d["a_match"]["kind"]=="wrong_class_candidate" for d in r["removed"])],
        "correct_vector_became_incorrect":[r["image"] for r in rows if r["correct_vector_became_incorrect"]],
        "correct_class_count_became_incorrect":[r["image"] for r in rows if r["correct_class_counts_became_incorrect"]]}
    source={r["image"]:r for r in json.loads((ROOT/"reports/image_manifest.json").read_text())}
    identity_errors={}
    for tag,lookup in [("A",lookup_a),("B",lookup_b)]:
        wrong=valser=light=0
        for name,row in lookup.items():
            for decision in row["matching"]["predictions"]:
                pred=row["detections"][decision["prediction_index"]]
                if decision["kind"]=="wrong_class_candidate":
                    wrong+=1
                    valser += {pred["class_id"],row["gt_boxes"][decision["gt_index"]][0]}=={2,3}
                if decision["kind"]!='tp' and pred["class_id"]==0:
                    light += any(o['label']=='redbull_light__33__90162800' and iou(pred['xyxy'],[v-1 for v in o['box']])>=.5 for o in source[name]['objects'])
        identity_errors[tag]={"wrong_class_candidates":wrong,"valser_classic_still_candidates":valser,"regular_on_light_candidates":light}
    from src.counting import counting_metrics
    cohorts={"crowded_30plus_source_objects":[n for n in lookup_a if len(source[n]["objects"])>=30],
             "multi_instance_2plus":[n for n,r in lookup_a.items() if max(r["truth"])>=2]}
    cohort_results={}
    for label,names in cohorts.items():
        cohort_results[label]={"images":names,"A":counting_metrics([lookup_a[n]["truth"] for n in names],[lookup_a[n]["predicted"] for n in names]),
                              "B":counting_metrics([lookup_b[n]["truth"] for n in names],[lookup_b[n]["predicted"] for n in names])}
    result={"a_reproduces_baseline_002":replay,"categories":categories,"images":rows,"cohorts":cohort_results,"identity_errors":identity_errors,
            "removed_boxes":sum(len(r["removed"]) for r in rows),"added_boxes":sum(len(r["added_b_indices"]) for r in rows),
            "improved_images":sum(r["count_error_delta"]<0 for r in rows),"worsened_images":sum(r["count_error_delta"]>0 for r in rows)}
    save(ROOT/"reports/nms_001_comparison.json",result)
    names=[]
    for values in categories.values():
        names.extend(values[:2])
    names.extend(["IMG_20181218_170247.jpg","IMG_20181218_171755.jpg","DSC01658.png","IMG_20181218_165652.jpg"])
    names.extend(r['image'] for r in rows if r['added_b_indices'])
    names=list(dict.fromkeys(names))
    pages=[]
    for name in names:
        row_a,row_b=lookup_a[name],lookup_b[name]
        source_path=ROOT/"data/yolo_v01/images/val"/name
        canvas=Image.new("RGB",(1860,690),"#171c25")
        canvas.paste(panel(source_path,row_a["gt_boxes"],"Ground truth | "+name),(0,0))
        for i,(tag,row) in enumerate([("A: IoU 0.70",row_a),("B: IoU 0.50",row_b)],1):
            boxes=[(d["class_id"],*d["xyxy"]) for d in row["detections"]]
            canvas.paste(panel(source_path,boxes,tag+" | confidence 0.25"),(620*i,0))
        ImageDraw.Draw(canvas).text((12,641),f"Truth {row_a['truth']}    A {row_a['predicted']}    B {row_b['predicted']}    Class order: Red Bull / Knoppers / Classic / Still / Capri-Sun",fill="white",font=ImageFont.load_default(size=18))
        canvas.save(ROOT/"reports/visuals"/f"nms_001_{Path(name).stem}.jpg",quality=92)
        pages.append(ImageOps.contain(canvas,(1395,518)))
    for page in range(0,len(pages),3):
        sheet=Image.new("RGB",(1395,518*len(pages[page:page+3])),"#171c25")
        for j,img in enumerate(pages[page:page+3]):
            sheet.paste(img,(0,518*j))
        sheet.save(ROOT/"reports/visuals"/f"nms_001_page_{page//3+1}.jpg",quality=92)
    protect()
    print(json.dumps({k:v for k,v in result.items() if k not in ['images','cohorts']},indent=2))


if __name__=="__main__":
    main()
