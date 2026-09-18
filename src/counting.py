"""Count post-NMS detections, then compare image-by-class count vectors."""
import numpy as np


def count_classes(class_ids, class_count=5):
    values = np.asarray(class_ids)
    if values.size == 0:
        return [0] * class_count
    if not np.all(np.isfinite(values)) or not np.all(values == values.astype(int)):
        raise ValueError("Class IDs must be finite integers")
    if np.any(values < 0) or np.any(values >= class_count):
        raise ValueError("Class ID outside frozen mapping")
    return np.bincount(values.astype(int), minlength=class_count).tolist()


def counting_metrics(truth, predictions):
    truth, predictions = np.asarray(truth), np.asarray(predictions)
    if truth.shape != predictions.shape or truth.ndim != 2 or truth.shape[1] != 5 or len(truth) == 0:
        raise ValueError("Expected matching non-empty N x 5 count arrays")
    if not np.all(np.isfinite(truth)) or not np.all(np.isfinite(predictions)) or np.any(truth < 0) or np.any(predictions < 0):
        raise ValueError("Counts must be finite and nonnegative")
    error = predictions - truth
    return {"per_class_mae": np.abs(error).mean(axis=0).tolist(),
            "overall_cell_mae": float(np.abs(error).mean()),
            "total_count_mae": float(np.abs(error.sum(axis=1)).mean()),
            "mean_sum_absolute_class_errors": float(np.abs(error).sum(axis=1).mean()),
            "exact_five_class_accuracy": float(np.all(error == 0, axis=1).mean()),
            "per_class_bias": error.mean(axis=0).tolist()}
