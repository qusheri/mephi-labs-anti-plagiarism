"""
Baseline evaluation: GraphCodeBERT + DFG_cpp on POJ-104 dataset.
No fine-tuning — zero-shot performance as a reference point.

Outputs (saved to ./baseline_results/):
  - sims_dfg.npy    : cosine similarities with DFG
  - sims_nodfc.npy  : cosine similarities without DFG (token-only)
  - labels.npy      : ground-truth pair labels (1=clone, 0=non-clone)
  - metrics.csv     : ROC-AUC, F1, Precision, Recall, Accuracy
  - baseline_plots.png : ROC curves + similarity histograms

These files can be reused to compare with classical algorithms
on the same pairs without recomputing embeddings.

Usage:
    python baseline_eval.py [--programs 400] [--pairs 800] [--seed 42]
"""

import sys
import os
import argparse
import random
import numpy as np
import torch
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm
import csv

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics import (roc_auc_score, roc_curve,
                             precision_recall_fscore_support,
                             accuracy_score)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from graphcodebert_dfg_encoder import get_embedding_with_dfg, get_embedding_no_dfg

# ── CLI args ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--programs", type=int, default=400,
                    help="Number of programs to sample (default: 400)")
parser.add_argument("--pairs",    type=int, default=800,
                    help="Total pairs to evaluate, ~50/50 (default: 800)")
parser.add_argument("--seed",     type=int, default=42)
parser.add_argument("--split",    type=str, default="validation",
                    choices=["train", "validation", "test"])
parser.add_argument("--out_dir",  type=str, default="baseline_results")
args = parser.parse_args()

OUT_DIR = Path(args.out_dir)
OUT_DIR.mkdir(exist_ok=True)

random.seed(args.seed)
np.random.seed(args.seed)

MODEL_NAME = "microsoft/graphcodebert-base"

# ── device ───────────────────────────────────────────────────────────────────
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")
if device.type == "cuda":
    props = torch.cuda.get_device_properties(0)
    print(f"GPU: {props.name}, VRAM: {props.total_memory/1024**3:.1f} GB")

# ── model ────────────────────────────────────────────────────────────────────
print(f"\nLoading {MODEL_NAME}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model     = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()
print("Model ready.\n")

# ── dataset ──────────────────────────────────────────────────────────────────
print(f"Loading POJ-104 ({args.split} split)...")
ds = load_dataset("google/code_x_glue_cc_clone_detection_poj104",
                  split=args.split)
print(f"Total: {len(ds)} programs, {len(set(ds['label']))} problem classes\n")

# ── stratified subsample ─────────────────────────────────────────────────────
by_label = defaultdict(list)
for idx, item in enumerate(ds):
    by_label[item["label"]].append(idx)

per_class = max(1, args.programs // len(by_label))
selected  = []
for lbl in sorted(by_label.keys()):
    pool = by_label[lbl]
    selected.extend(random.sample(pool, min(per_class, len(pool))))

random.shuffle(selected)
selected = selected[:args.programs]
programs = [(ds[i]["id"], ds[i]["code"], ds[i]["label"]) for i in selected]
print(f"Sampled {len(programs)} programs from "
      f"{len(set(p[2] for p in programs))} classes.\n")

# ── pair generation ──────────────────────────────────────────────────────────
by_label_local = defaultdict(list)
for pid, code, lbl in programs:
    by_label_local[lbl].append((pid, code))

pos_pairs, neg_pairs = [], []
lbl_keys = list(by_label_local.keys())

for lbl, items in by_label_local.items():
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            pos_pairs.append((items[i], items[j], 1))

while len(neg_pairs) < len(pos_pairs) * 2:
    l1, l2 = random.sample(lbl_keys, 2)
    a = random.choice(by_label_local[l1])
    b = random.choice(by_label_local[l2])
    neg_pairs.append((a, b, 0))

half      = min(len(pos_pairs), len(neg_pairs), args.pairs // 2)
pos_pairs = random.sample(pos_pairs, half)
neg_pairs = random.sample(neg_pairs, half)
all_pairs = pos_pairs + neg_pairs
random.shuffle(all_pairs)
print(f"Pairs: {len(all_pairs)} ({half} positive + {half} negative)\n")

# save pair metadata for reuse by classical algorithms
with open(OUT_DIR / "pairs.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id_a", "id_b", "label"])
    for (pid_a, _), (pid_b, _), lbl in all_pairs:
        w.writerow([pid_a, pid_b, lbl])

with open(OUT_DIR / "programs.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "label", "code"])
    for pid, code, lbl in programs:
        w.writerow([pid, lbl, code])

print(f"Pair list saved → {OUT_DIR/'pairs.csv'}")
print(f"Program list saved → {OUT_DIR/'programs.csv'}\n")

# ── embeddings (cached) ──────────────────────────────────────────────────────
unique_codes: dict = {}
for (pid_a, code_a), (pid_b, code_b), _ in all_pairs:
    unique_codes[pid_a] = code_a
    unique_codes[pid_b] = code_b

print(f"Computing embeddings for {len(unique_codes)} unique programs...")
emb_dfg  = {}
emb_ndfg = {}

for pid, code in tqdm(unique_codes.items(), desc="Embeddings"):
    try:
        emb_dfg[pid]  = get_embedding_with_dfg(code, model, tokenizer, device)
    except Exception as e:
        emb_dfg[pid] = None

    try:
        emb_ndfg[pid] = get_embedding_no_dfg(code, model, tokenizer, device)
    except Exception as e:
        emb_ndfg[pid] = None

# ── cosine similarity for each pair ──────────────────────────────────────────
sims_dfg, sims_ndfg, labels_list = [], [], []

for (pid_a, _), (pid_b, _), lbl in all_pairs:
    ea_d, eb_d = emb_dfg.get(pid_a),  emb_dfg.get(pid_b)
    ea_n, eb_n = emb_ndfg.get(pid_a), emb_ndfg.get(pid_b)
    if None in (ea_d, eb_d, ea_n, eb_n):
        continue
    sims_dfg.append(float(np.dot(ea_d, eb_d)))
    sims_ndfg.append(float(np.dot(ea_n, eb_n)))
    labels_list.append(lbl)

sims_dfg   = np.array(sims_dfg)
sims_ndfg  = np.array(sims_ndfg)
labels_arr = np.array(labels_list)

np.save(OUT_DIR / "sims_dfg.npy",   sims_dfg)
np.save(OUT_DIR / "sims_ndfg.npy",  sims_ndfg)
np.save(OUT_DIR / "labels.npy",     labels_arr)

print(f"\nPairs evaluated: {len(labels_arr)}")

# ── metrics ──────────────────────────────────────────────────────────────────

def compute_metrics(sims, labels, name):
    auc      = roc_auc_score(labels, sims)
    fpr, tpr, thresholds = roc_curve(labels, sims)
    best_idx = np.argmax(tpr - fpr)          # Youden's J
    best_thr = thresholds[best_idx]
    preds    = (sims >= best_thr).astype(int)
    prec, rec, f1, _ = precision_recall_fscore_support(
        labels, preds, average="binary", zero_division=0)
    acc = accuracy_score(labels, preds)
    print(f"\n  [{name}]")
    print(f"  ROC-AUC:   {auc:.4f}  |  threshold: {best_thr:.4f}")
    print(f"  Precision: {prec:.4f}  Recall: {rec:.4f}  F1: {f1:.4f}  Acc: {acc:.4f}")
    return dict(name=name, auc=auc, threshold=best_thr,
                precision=prec, recall=rec, f1=f1, accuracy=acc,
                fpr=fpr, tpr=tpr)

print("\n" + "="*55)
print("  BASELINE RESULTS (zero-shot, no fine-tuning)")
print("="*55)
res_nd  = compute_metrics(sims_ndfg, labels_arr, "Token-only (no DFG)")
res_dfg = compute_metrics(sims_dfg,  labels_arr, "GraphCodeBERT + DFG")

# ── summary table ─────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  {'Metric':<12} {'No DFG':>12} {'With DFG':>12} {'Delta':>8}")
print(f"  {'─'*51}")
for key, label in [("auc","ROC-AUC"), ("f1","F1"),
                   ("precision","Precision"), ("recall","Recall"),
                   ("accuracy","Accuracy")]:
    nd  = res_nd[key]
    dfg = res_dfg[key]
    print(f"  {label:<12} {nd:>12.4f} {dfg:>12.4f} {dfg-nd:>+8.4f}")
print(f"{'='*55}\n")

# ── save metrics CSV ─────────────────────────────────────────────────────────
with open(OUT_DIR / "metrics.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["metric", "no_dfg", "with_dfg"])
    for key in ["auc","f1","precision","recall","accuracy"]:
        w.writerow([key, f"{res_nd[key]:.4f}", f"{res_dfg[key]:.4f}"])

# ── plots ────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

ax = axes[0]
ax.plot(res_nd["fpr"],  res_nd["tpr"],
        label=f"No DFG  (AUC={res_nd['auc']:.3f})",   color="steelblue")
ax.plot(res_dfg["fpr"], res_dfg["tpr"],
        label=f"With DFG (AUC={res_dfg['auc']:.3f})", color="darkorange")
ax.plot([0, 1], [0, 1], "k--", lw=0.8)
ax.set_xlabel("FPR"); ax.set_ylabel("TPR")
ax.set_title("ROC Curves (baseline, zero-shot)")
ax.legend(); ax.grid(alpha=0.3)

ax = axes[1]
for sims, label, colors in [
        (sims_dfg,  "DFG",     ("darkorange", "gold")),
        (sims_ndfg, "No DFG",  ("steelblue",  "lightblue"))]:
    kw = dict(bins=40, alpha=0.55, density=True)
    ax.hist(sims[labels_arr == 1], **kw, color=colors[0], label=f"{label}: clones")
    ax.hist(sims[labels_arr == 0], **kw, color=colors[1], label=f"{label}: non-clones")
ax.set_xlabel("Cosine similarity"); ax.set_ylabel("Density")
ax.set_title("Similarity Distribution (baseline)")
ax.legend(fontsize=7); ax.grid(alpha=0.3)

plt.tight_layout()
fig.savefig(OUT_DIR / "baseline_plots.png", dpi=150)

print(f"Saved to {OUT_DIR}/")
print("  metrics.csv, pairs.csv, programs.csv")
print("  sims_dfg.npy, sims_ndfg.npy, labels.npy")
print("  baseline_plots.png")
