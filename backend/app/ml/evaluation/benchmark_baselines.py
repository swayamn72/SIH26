import argparse
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
from tabulate import tabulate

from app.scoring.fusion import fuse_scores

def generate_synthetic_data(n_samples=5000, positive_rate=0.05):
    """
    Generates synthetic benchmark data simulating the outputs of the three models.
    Mules (label=1) typically trigger rules OR look highly anomalous OR fit supervised patterns.
    """
    np.random.seed(42)
    labels = np.random.binomial(1, positive_rate, n_samples)
    
    # Supervised ML is good but misses zero-day (some False Negatives) and has some False Positives
    sup_prob = np.where(labels == 1, np.random.beta(5, 2, n_samples), np.random.beta(1, 5, n_samples))
    
    # Rule engine is very precise but has low recall (misses subtle patterns)
    rule_score = np.where(labels == 1, np.random.choice([0, 100], p=[0.7, 0.3], size=n_samples), 0)
    
    # Anomaly is noisy but catches things the others miss
    anomaly_score = np.where(labels == 1, np.random.uniform(0.6, 1.0, n_samples), np.random.uniform(0.0, 0.7, n_samples))
    
    df = pd.DataFrame({
        "account_id": [f"ACCT_{i}" for i in range(n_samples)],
        "label": labels,
        "supervised_probability": sup_prob,
        "rule_score": rule_score,
        "anomaly_score": anomaly_score
    })
    return df

def calculate_metrics(y_true, y_pred, y_scores):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    
    # Prioritization: Lift at Top 5%
    top_5_percent_idx = np.argsort(y_scores)[::-1][:int(len(y_scores) * 0.05)]
    top_5_labels = y_true.iloc[top_5_percent_idx]
    precision_at_5 = top_5_labels.mean()
    base_rate = y_true.mean()
    lift_at_5 = precision_at_5 / base_rate if base_rate > 0 else 0
    
    return {
        "Precision": f"{precision:.3f}",
        "Recall": f"{recall:.3f}",
        "F1-Score": f"{f1:.3f}",
        "FPR": f"{fpr:.3f}",
        "Lift @ Top 5%": f"{lift_at_5:.1f}x"
    }

def main():
    parser = argparse.ArgumentParser(description="Evaluate MuleGuard vs Baselines")
    parser.add_argument("--csv", type=str, help="Path to evaluation dataset with scores", default=None)
    args = parser.parse_args()
    
    if args.csv:
        print(f"Loading data from {args.csv}")
        df = pd.read_csv(args.csv)
    else:
        print("No --csv provided. Generating synthetic benchmark dataset (N=5000)...")
        df = generate_synthetic_data()
        
    print(f"Dataset: {len(df)} accounts, {df['label'].sum()} positive (mules)")
    
    # 1. Baseline: Pure ML (Threshold = 0.5)
    df['ml_pred'] = (df['supervised_probability'] >= 0.5).astype(int)
    ml_metrics = calculate_metrics(df['label'], df['ml_pred'], df['supervised_probability'])
    
    # 2. Baseline: Pure Rules (Threshold > 0)
    df['rule_pred'] = (df['rule_score'] > 0).astype(int)
    rule_metrics = calculate_metrics(df['label'], df['rule_pred'], df['rule_score'])
    
    # 3. MuleGuard (Fused) (Threshold >= 75 for Confirmed Suspicious)
    fused_scores = []
    for _, row in df.iterrows():
        score, _ = fuse_scores(
            rule_score=row['rule_score'],
            anomaly_score=row['anomaly_score'],
            supervised_probability=row['supervised_probability']
        )
        fused_scores.append(score / 100.0) # normalized to 0-1
    
    df['muleguard_score'] = fused_scores
    df['muleguard_pred'] = (df['muleguard_score'] >= 0.75).astype(int)
    mg_metrics = calculate_metrics(df['label'], df['muleguard_pred'], df['muleguard_score'])
    
    # Report
    table = [
        ["Pure Rules (Baseline)"] + list(rule_metrics.values()),
        ["Pure ML (Baseline)"] + list(ml_metrics.values()),
        ["MuleGuard (Hybrid)"] + list(mg_metrics.values())
    ]
    
    headers = ["Model / Approach"] + list(rule_metrics.keys())
    print("\n" + tabulate(table, headers, tablefmt="github"))

if __name__ == "__main__":
    main()
