"""Script to generate the system architecture diagram for AI Revenue Recovery Agent."""

import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def generate_diagram(output_path: str = "docs/architecture.png") -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(16, 10), dpi=200)
    ax.set_facecolor('#0B0F19')
    fig.patch.set_facecolor('#0B0F19')

    # Title
    plt.text(8.0, 9.5, 'AI Revenue Recovery Agent — End-to-End System Architecture', 
             fontsize=18, fontweight='bold', color='#FFFFFF', ha='center', va='center')
    plt.text(8.0, 9.15, 'Track 03: AI Revenue Recovery | Razorpay AI Buildathon 2026', 
             fontsize=11, color='#94A3B8', ha='center', va='center')

    # Define stages: (x, y, width, height, title, subtitle, color, border_color)
    stages = [
        # Row 1: Ingestion & Integrity
        (0.8, 7.3, 2.8, 1.2, '1. RevenueEvent Ingestion', 'Streaming degraded txn\nUPI, Cards, NetBanking', '#1E293B', '#38BDF8'),
        (4.4, 7.3, 2.8, 1.2, '2. Transaction Truth', 'Strict state validation\nPending != Failed invariant', '#1E293B', '#38BDF8'),
        (8.0, 7.3, 2.8, 1.2, '3. Payment Integrity', 'Debit ambiguity detection\nZero double-charge gate', '#1E293B', '#F59E0B'),
        (11.6, 7.3, 2.8, 1.2, '4. Stopping Rules', 'Opt-out, duplicate debit,\nTerminal status evaluation', '#1E293B', '#EF4444'),
        
        # Row 2: Diagnosis & Economics
        (11.6, 5.0, 2.8, 1.2, '5. Root-Cause Diagnosis', 'Rule Baseline + LLM Client\nStrict JSON schema & cache', '#1E293B', '#818CF8'),
        (8.0, 5.0, 2.8, 1.2, '6. Action Catalog', '9 bounded recovery actions\nCost, risk, caps metadata', '#1E293B', '#34D399'),
        (4.4, 5.0, 2.8, 1.2, '7. Expected Value Ranking', 'Stratified empirical lift\nWilson score 95% CI', '#1E293B', '#10B981'),
        (0.8, 5.0, 2.8, 1.2, '8. Statutory Guardrails', 'TRAI DND, RBI Fair Practice\nDPDP PII safety boundaries', '#1E293B', '#F43F5E'),
        
        # Row 3: Decision & Execution
        (0.8, 2.7, 2.8, 1.2, '9. Decision Engine', 'Deterministic policy routing\nAUTO / HUMAN / BLOCK', '#1E293B', '#A855F7'),
        (4.4, 2.7, 2.8, 1.2, '10. Execution Adapter', 'Idempotent sandbox dispatch\nPTP commitment tracking', '#1E293B', '#06B6D4'),
        (8.0, 2.7, 2.8, 1.2, '11. Webhook Verification', 'Authoritative settlement\nNever treat dispatch as rec.', '#1E293B', '#3B82F6'),
        (11.6, 2.7, 2.8, 1.2, '12. Reconciliation Engine', 'Tripartite state matching\nHold inquiry on mismatch', '#1E293B', '#6366F1'),
        
        # Row 4: Audit & Benchmark
        (8.0, 0.6, 3.8, 1.3, '13. Append-Only SHA-256 Ledger', 'Cryptographic hash-chained audit trail\n100% events verifiable from genesis', '#1E1B4B', '#A78BFA'),
        (2.8, 0.6, 4.4, 1.3, '14. 4-Arm Evaluation Benchmark', 'CONTROL vs NAIVE vs RULES vs AGENT\nTrue Incremental Lift Attribution', '#064E3B', '#34D399'),
    ]

    for (x, y, w, h, title, sub, bg, border) in stages:
        box = patches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.1,rounding_size=0.15',
                                    facecolor=bg, edgecolor=border, linewidth=1.8, alpha=0.95)
        ax.add_patch(box)
        plt.text(x + w/2, y + h*0.68, title, fontsize=9.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')
        plt.text(x + w/2, y + h*0.32, sub, fontsize=8, color='#94A3B8', ha='center', va='center')

    # Arrows connecting the flow
    def draw_arrow(x1, y1, x2, y2):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#64748B', lw=1.8, mutation_scale=14))

    # Row 1 left to right
    draw_arrow(3.7, 7.9, 4.3, 7.9)
    draw_arrow(7.3, 7.9, 7.9, 7.9)
    draw_arrow(10.9, 7.9, 11.5, 7.9)

    # Row 1 to Row 2
    draw_arrow(13.0, 7.2, 13.0, 6.3)

    # Row 2 right to left
    draw_arrow(11.5, 5.6, 10.9, 5.6)
    draw_arrow(7.9, 5.6, 7.3, 5.6)
    draw_arrow(4.3, 5.6, 3.7, 5.6)

    # Row 2 to Row 3
    draw_arrow(2.2, 4.9, 2.2, 4.0)

    # Row 3 left to right
    draw_arrow(3.7, 3.3, 4.3, 3.3)
    draw_arrow(7.3, 3.3, 7.9, 3.3)
    draw_arrow(10.9, 3.3, 11.5, 3.3)

    # Row 3 to Row 4 (Reconciliation -> Ledger -> Benchmark)
    draw_arrow(13.0, 2.6, 10.5, 2.0)
    draw_arrow(7.9, 1.25, 7.3, 1.25)

    ax.set_xlim(0, 15.5)
    ax.set_ylim(0, 10)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close()


if __name__ == '__main__':
    generate_diagram()
