"""Apply per-class confidence to raw best-class scores BEFORE NMS."""
from src.train_baseline import ROOT  # configure existing local runtime settings first
import torch
from ultralytics.models.yolo.detect.predict import DetectionPredictor
from ultralytics.utils.nms import non_max_suppression


def gate_candidates(prediction, thresholds):
    if prediction.ndim != 3 or prediction.shape[1] != 9:
        raise ValueError('Expected frozen five-class YOLO BCN output')
    scores, classes = prediction[:,4:9].max(dim=1)
    cutoffs = prediction.new_tensor(thresholds)
    if cutoffs.shape != (5,):
        raise ValueError('Expected five class cutoffs')
    accepted = scores > cutoffs[classes]  # match Ultralytics strict > semantics
    gated = prediction.clone()
    # Reject the whole candidate; never relabel to a second-best class.
    gated[:,4:9] *= accepted.unsqueeze(1)
    return gated


class ClassConfidencePredictor(DetectionPredictor):
    thresholds = (.25, .25, .25, .25, .25)

    def postprocess(self, preds, img, orig_imgs, **kwargs):
        if getattr(self.model, 'end2end', False):
            raise ValueError('This adapter requires the frozen YOLO11 detection head')
        raw = preds[0] if isinstance(preds,(tuple,list)) else preds
        gated = gate_candidates(raw, self.thresholds)
        # Global floor only passes already-gated candidates to unchanged stock NMS.
        assert self.args.conf == min(self.thresholds)
        return super().postprocess(gated, img, orig_imgs, **kwargs)


def sanity_check():
    raw=torch.zeros((1,9,8))
    for j in range(8):
        raw[0,:4,j]=torch.tensor([20+30*j,20,10,10])
    raw[0,4,0]=.20  # only alternative accepts Red Bull
    raw[0,5,1]=.20  # neither accepts low Knoppers
    raw[0,4,2]=.19; raw[0,5,2]=.20  # no fallback to runner-up Red Bull
    raw[0,5,3]=.30
    raw[0,4,4]=.15  # strict boundary rejected
    raw[0,5,5]=.25  # strict boundary rejected
    raw[0,4,6]=.40
    raw[0,:4,7]=raw[0,:4,6]; raw[0,4,7]=.18  # suppressed duplicate
    def nms(p,conf):
        return non_max_suppression(p.clone(),conf,.50,agnostic=False,max_det=300)[0]
    a=nms(gate_candidates(raw,[.25]*5),.25)
    stock=nms(raw,.25)
    b=nms(gate_candidates(raw,[.15,.25,.25,.25,.25]),.15)
    assert torch.equal(a,stock)
    assert len(a)==2 and len(b)==3
    assert sorted(b[:,4].tolist())==sorted([raw[0,4,0].item(),raw[0,5,3].item(),raw[0,4,6].item()])
    assert torch.equal(raw[0,5,1],torch.tensor(.20))
    return {'passed':True,'baseline_matches_stock':True,'baseline_boxes':len(a),'alternative_boxes':len(b),
            'checks':['Red Bull-only admission','other classes rejected before NMS','no runner-up relabeling','strict threshold boundaries','same-class duplicate suppression','input unchanged']}
