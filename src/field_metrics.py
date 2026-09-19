"""Count-only field statistics; no invented detection precision/recall."""
from src.counting import counting_metrics
from src.field_cohort import KEYS


def validate_vector(vector):
    if len(vector) != 5 or any(type(n) is not int or n < 0 for n in vector):
        raise ValueError('Expected five nonnegative integer counts')


def summarize(rows):
    if not rows or len({r['image_id'] for r in rows}) != len(rows):
        raise ValueError('Expected nonempty unique image records')
    for row in rows:
        validate_vector(row['truth'])
        validate_vector(row['predicted'])
    truth, predicted = [r['truth'] for r in rows], [r['predicted'] for r in rows]
    common = counting_metrics(truth, predicted)
    errors = [[p-t for p,t in zip(r['predicted'],r['truth'])] for r in rows]
    return {'image_count': len(rows), 'scene_count': len({r['scene_id'] for r in rows}),
        'ground_truth_total': sum(map(sum,truth)), 'predicted_total': sum(map(sum,predicted)),
        'counting_mae': common['overall_cell_mae'], 'exact_five_class_accuracy': common['exact_five_class_accuracy'],
        'over_count': sum(max(e,0) for error in errors for e in error),
        'under_count': sum(max(-e,0) for error in errors for e in error),
        'per_class': {key: {'ground_truth_total':sum(r['truth'][c] for r in rows),
            'predicted_total':sum(r['predicted'][c] for r in rows),
            'absolute_count_error':sum(abs(e[c]) for e in errors), 'mae':common['per_class_mae'][c],
            'exact_image_accuracy':sum(e[c]==0 for e in errors)/len(rows)} for c,key in enumerate(KEYS)}}


def analyze(rows):
    rows = sorted(rows, key=lambda row: row['image_id'])
    overall = summarize(rows)
    per_scene = {scene:summarize([r for r in rows if r['scene_id']==scene]) for scene in sorted({r['scene_id'] for r in rows})}
    errors = []
    for row in rows:
        delta = [p-t for p,t in zip(row['predicted'],row['truth'])]
        over, under = sum(max(e,0) for e in delta), sum(max(-e,0) for e in delta)
        misses = [KEYS[c] for c in range(5) if row['truth'][c]>0 and row['predicted'][c]==0]
        zero_class_predictions = [KEYS[c] for c in range(5) if row['truth'][c]==0 and row['predicted'][c]>0]
        errors.append({'image_id':row['image_id'],'scene_id':row['scene_id'], 'absolute_error':over+under,
            'over_count':over, 'under_count':under, 'completely_missed_classes':misses,
            'zero_ground_truth_class_predictions':zero_class_predictions,
            'possible_confusion_needs_visual_review':bool(over and under),
            'preannotated_conditions_with_error':row.get('tags',[]) if over+under else []})
    choose = lambda values: [r['image_id'] for r in values[:3]]
    representatives = {
        'strongest_successes':choose(sorted([r for r in rows if r['truth']==r['predicted']],key=lambda r:(-sum(r['truth']),r['image_id']))),
        'largest_under_counts':choose(sorted([e for e in errors if e['under_count']],key=lambda e:(-e['under_count'],e['image_id']))),
        'largest_over_counts':choose(sorted([e for e in errors if e['over_count']],key=lambda e:(-e['over_count'],e['image_id']))),
        'complete_misses':choose([e for e in errors if e['completely_missed_classes']]),
        'confusion_review_candidates':choose([e for e in errors if e['possible_confusion_needs_visual_review']])}
    return {'overall':overall,'per_scene':per_scene,'image_errors':errors,'representatives':representatives}
