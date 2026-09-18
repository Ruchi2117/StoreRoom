"""Read-only independent-scene eligibility audit. Never loads a model."""
import json
from collections import Counter
from pathlib import Path
from src.nms_experiment import ROOT, save
from src.train_augmentation import verify_protected as prior_protect
from src.train_baseline import verify_dataset
from src.convert_smoke import digest

PREFIX='independent_validation_001'


def verify_protected():
    snapshot=json.loads((ROOT/f'reports/{PREFIX}_preservation.json').read_text())
    for path,expected in snapshot.items():
        assert digest(ROOT/path)==expected, f'Protected artifact changed: {path}'
    verify_dataset()
    return len(snapshot)


def main():
    target=ROOT/f'reports/{PREFIX}_audit.json'
    if target.exists():
        raise FileExistsError('Independent-scene audit already recorded')
    prior_protect()
    snapshot=json.loads((ROOT/'reports/augmentation_001_preservation.json').read_text())
    for folder in ['reports','src','configs','tests','runs']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and 'independent' not in p.name.lower():
                snapshot[p.relative_to(ROOT).as_posix()]=digest(p)
    raw=ROOT/'data/raw/holoselecta/FinalDataset'
    # Preserve source annotations as well as images; hashes do not evaluate test data.
    for p in raw.iterdir():
        if p.is_file():
            snapshot[p.relative_to(ROOT).as_posix()]=digest(p)
    save(ROOT/f'reports/{PREFIX}_preservation.json',snapshot)
    read=lambda p:json.loads((ROOT/p).read_text())
    manifest=read('reports/image_manifest.json')
    groups=read('reports/scene_groups.json')
    split=read('configs/splits.json')
    quarantine=read('reports/quarantine.json')
    exclusions=read('configs/exclusions.json')['images']
    classes=read('configs/class_map.json')['classes']
    names=[c['name'] if 'name' in c else c.get('display_name',c['source_label']) for c in classes]
    labels=[c['source_label'] for c in classes]
    images={r['image']:r for r in manifest}
    actual={p.name for p in raw.iterdir() if p.suffix.lower() in ['.jpg','.jpeg','.png']}
    archived={Path(r['name']).name for r in read('reports/archive_index.json') if Path(r['name']).suffix.lower() in ['.jpg','.jpeg','.png']}
    assert actual==set(images)==archived
    for name,row in images.items():
        assert digest(raw/name)==row['sha256']
    membership={name:g['scene_group'] for g in groups for name in g['images']}
    assert len(membership)==sum(len(g['images']) for g in groups)==len(images)
    assigned={g:s for s,gs in split['groups'].items() for g in gs}
    assert len(assigned)==sum(map(len,split['groups'].values()))
    used_images=set().union(*(set(v) for v in split['images'].values()))
    q_images={r['image'] for r in quarantine}
    assert used_images.isdisjoint(q_images) and used_images|q_images==set(images)
    for s,ims in split['images'].items():
        assert all(assigned[membership[n]]==s for n in ims)
    rows=[]
    for g in groups:
        counts=Counter(o['label'] for n in g['images'] for o in images[n]['objects'])
        rows.append({**g,'existing_split':assigned.get(g['scene_group']),
                     'annotation_count_all_classes':sum(counts.values()),
                     'selected_class_counts':[counts[label] for label in labels],
                     'quarantined_images':[n for n in g['images'] if n in q_images]})
    supported={g['scene_group'] for g in groups if g['status']=='sticker_supported'}
    unallocated=supported-set(assigned)
    assert supported==set(assigned), 'Unexpected verified unused groups: review before deciding'
    unused=set(images)-used_images
    unresolved=[g for g in groups if g['status']=='unresolved']
    unsupported_counts=Counter(o['label'] for n in unused for o in images[n]['objects'])
    frozen=read('reports/augmentation_001_setup.json')
    for tag,path in frozen['checkpoints'].items():
        assert digest(Path(path))==frozen['checkpoint_hashes'][tag]
    result={'status':'blocked_no_verified_independent_groups','inference_performed':False,
            'selection_frozen':False,'selected_group_ids':[],'selected_images':[],'selected_annotations':0,
            'selected_class_counts':[0]*5,'class_names':names,'source_images':len(images),
            'source_xml_files':len(list(raw.glob('*.xml'))),'archive_image_inventory_matches':True,
            'source_image_hashes_match':True,'verified_group_count':len(supported),
            'split_group_ids':split['groups'],'split_image_counts':{s:len(v) for s,v in split['images'].items()},
            'unused_verified_group_ids':sorted(unallocated),'unresolved_component_ids':[g['scene_group'] for g in unresolved],
            'unresolved_component_images':sum(len(g['images']) for g in unresolved),
            'quarantined_images':len(unused),'explicit_exclusions':exclusions,
            'unresolved_only_images':len(unused-set(exclusions)),
            'quarantine_annotation_count_all_classes':sum(unsupported_counts.values()),
            'quarantine_selected_class_counts':[unsupported_counts[label] for label in labels],
            'groups':rows,'models':frozen['checkpoints'],'model_hashes':frozen['checkpoint_hashes'],
            'common_arguments':frozen['common_arguments'],'class_thresholds':[.15,.25,.25,.25,.25],
            'protected_artifacts':len(snapshot),
            'reason':'All 33 supported groups are assigned to train/val/test. Remaining components lack verified cross-visit identity; test groups cannot be repurposed.'}
    save(target,result)
    verify_protected()
    print(json.dumps({k:v for k,v in result.items() if k!='groups'},indent=2))


if __name__=='__main__':
    main()
