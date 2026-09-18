# BASELINE_002 interpretation

### Was the ten-epoch baseline undertrained?

Yes, relative to this optimizer and scheduling policy: the larger budget improved
validation detection and counting, including every class's AP50, AP50-95 and
counting MAE. Overall cell counting MAE fell by about 35%, and four positive
validation images now have exactly correct five-class counts; BASELINE_001 had
none. The training curves show gains beyond epoch 10, with the highest recorded
validation fitness at epoch 23. Epochs 24–30 did not establish a higher peak.

This supports insufficient optimization budget as one bottleneck in BASELINE_001.
It does not establish that duration is the only bottleneck or that further epochs
will keep helping. The epoch-dependent learning-rate schedule was stretched by
the requested budget change, so the effect includes that scheduling consequence.
The first epoch reproduced the previous losses, and the effective settings differ
only in epochs and the experiment/output-directory names.

### What improved, and what did not?

The side-by-side review covered original failure images, crowded shelves,
multi-instance examples, and the largest image-level improvements and regressions.
Left panels are ground truth, middle panels BASELINE_001, right panels BASELINE_002.

- **Capri-Sun:** all 33 annotated validation instances were matched at confidence
  0.25 and diagnostic IoU 0.5, versus only two previously. There are now 12 false
  predictions, including three duplicate candidates. Recall improved strongly,
  while count bias changed from under-counting to over-counting.
- **Valser variants:** correct matches increased from 1 to 15 for Classic and
  from 9 to 23 for Still. However, Classic/Still confusion candidates increased
  from one to four. More training improved aggregate coverage without solving
  variant discrimination. The old `IMG_20181218_171607.jpg` confusion is fixed:
  its entire count vector is now correct. Other frames contain new wrong-class
  or overlapping water-bottle predictions.
- **Red Bull:** regular predictions overlapping excluded light-product annotations
  decreased from eight to six. This confusion persists. Regular Red Bull counting
  error remains the largest of the five classes. Its crowded-subset MAE actually
  worsened from 1.143 to 1.286, despite a small improvement over all validation
  images. Size accuracy remains unmeasurable because the source class merges sizes.
- **Crowded/multi-instance images:** crowded-image cell MAE improved from 1.029
  to 0.457 across 14 images. Across all 24 multi-instance images, cell MAE improved
  from 1.075 to 0.700. `IMG_20181218_171749.jpg` improves from six total predicted
  products to eleven, against twelve annotated products, recovering both water
  variants and Capri-Sun while still missing one Knoppers.
- **Duplicate predictions:** candidates increased from one to nine. They span
  Red Bull, both Valser classes and Capri-Sun. At `IMG_20181218_170247.jpg`, true
  `[4,0,1,1,0]` becomes `[0,0,4,3,0]`; extra overlapping water boxes accompany
  persistent Red Bull misses. More training alone did not produce better counts
  on this image.
- **Zero-output images:** positive images with no predictions decrease from four
  to zero, but this is not equivalent to finding the correct products. The hard
  mixed-size-can image `IMG_20181218_165652.jpg` still misses all twelve targets
  and adds a false Capri-Sun detection: `[0,0,0,0,0]` becomes `[0,0,0,0,1]`.
  Its count error worsens. Both actual zero-target images remain correctly empty.

Overall, 18 image-level count errors improved, four worsened and four stayed the
same. Detection is substantially better, and counting also improves, but exact
five-class accuracy is still only 6/26. More training reduced misses while exposing
additional duplicate and classification errors. These remain exploratory results
from 26 images across five validation machine groups and one random seed.

### The single most justified next experiment

Run one **validation-only NMS comparison using the frozen BASELINE_002 checkpoint**:
change class-aware NMS IoU from **0.70 to 0.50**, keeping confidence **0.25**, image
size **320**, the model weights, class mapping and all other inference settings
fixed. This is a proposed separate experiment; it has not been run here.

The evidence is specific: nine duplicate candidates remain, and eight overlap
another same-class prediction at IoUs between approximately 0.51 and 0.66, below
the current suppression threshold. Compare duplicate count, per-class counting
MAE, exact-vector accuracy, and crowded-scene recall against the stored 0.70
results. The hypothesis is that stronger duplicate suppression helps counts;
the tradeoff is possible suppression of genuine adjacent products. An IoU change
does not guarantee that all eight candidates disappear, and it does not address
cross-class or regular/light mistakes. This small comparison isolates a measured
failure mode without another training run or a new model technique.

### Reproducibility and verification

All 30 epochs completed in 1747.68 seconds (29 minutes 8 seconds). The same original
pretrained weights and frozen dataset were used. All 34 recorded BASELINE_001 and
shared frozen artifacts retained their original hashes. The raw training CSV was
copied byte-for-byte, and no reported metrics were edited. The full test suite
passed 27 tests, including configuration equality, effective settings, dataset
integrity, counting checks, preservation checks, and explicit rejection of a
BASELINE_002 test-evaluation request.

Commands used for this new experiment:

```powershell
.\.venv\Scripts\python.exe -m src.train_baseline_002
.\.venv\Scripts\python.exe -m src.evaluate_baseline_002 --split val
.\.venv\Scripts\python.exe -m src.review_baseline_002
.\.venv\Scripts\python.exe -m src.compare_baselines
.\.venv\Scripts\python.exe -m src.report_baseline_002
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Training and evaluation refuse to overwrite their completed experiment. The
review/comparison/report commands regenerate only BASELINE_002 analysis outputs.
