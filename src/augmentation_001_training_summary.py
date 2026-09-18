"""Extract completed training curves and checkpoint-selection evidence."""
import csv
import json
from src.nms_experiment import ROOT, save


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import torch
    summary={}
    fig,axes=plt.subplots(2,3,figsize=(15,8))
    keys=['train/box_loss','train/cls_loss','train/dfl_loss','val/box_loss','val/cls_loss','val/dfl_loss']
    for tag,name,record_name in [('A','baseline_002','baseline_002_experiment.json'),('B','augmentation_001','augmentation_001_training.json')]:
        record=json.loads((ROOT/'reports'/record_name).read_text())
        assert record['status']=='completed'
        with (ROOT/'runs'/name/'results.csv').open() as f:
            rows=[{k.strip():float(v) for k,v in r.items()} for r in csv.DictReader(f)]
        checkpoint=torch.load(record['checkpoint'],map_location='cpu',weights_only=False)
        fitness=checkpoint['train_metrics']['fitness']
        best=max(rows,key=lambda r:(r['metrics/mAP50-95(B)'],r['epoch']))
        assert abs(best['metrics/mAP50-95(B)']-fitness)<1e-4
        summary[tag]={'duration_seconds':record['duration_seconds'],'final_epoch':int(rows[-1]['epoch']),
                      'best_epoch':int(best['epoch']),'best':best,'final':rows[-1],
                      'checkpoint':record['checkpoint'],'checkpoint_sha256':record['checkpoint_sha256'],
                      'training_internal_checkpoint_metrics':checkpoint['train_metrics']}
        for ax,key in zip(axes.flat,keys):
            ax.plot([r['epoch'] for r in rows],[r[key] for r in rows],label=tag)
            ax.set_title(key); ax.set_xlabel('Epoch'); ax.legend()
    fig.tight_layout()
    fig.savefig(ROOT/'reports/visuals/augmentation_001_loss_curves.png',dpi=150)
    plt.close(fig)
    save(ROOT/'reports/augmentation_001_training_summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
