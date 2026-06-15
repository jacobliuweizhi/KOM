# Reviewer Guide: 3-5 minute KOM demo script

## 1. Overview

Open the Overview page. Explain that **KOM** is a physician-facing AI decision-support workflow for knee osteoarthritis treatment planning in standardized case tasks.

Point out the four evidence chains:

1. KOM-Assess: physician-side patient portrait.
2. KOM-Treat: treatment recommendation generation and component ablation.
3. KOM-Sim: clinician-in-the-loop simulation.
4. KOM-Score: multi-source evaluation and error definitions.

Clarify that **780** means 26 physicians x 30 standardized tasks = 780 physician-task prescription records.

## 2. Select a Q4 high-complexity case

Go to Case workspace and select `Q4-01-9304021` or `Q4-04-9222596`. These cases show medication safety gates, high BMI, severe structural burden, and referral boundaries.

## 3. Run KOM workflow

Click **Run full KOM workflow**. Walk through:

Case input -> KOM-Profile -> KOM-Rad -> KOM-Risk -> KOM-RAG -> KOM-MDT -> KOM-Rx -> KOM-Safe -> Export report.

## 4. Show KOM-RAG and naive RAG baseline

Open KOM-Treat. Show the card **What is the naive RAG baseline?**

Key line: the naive RAG baseline uses the same evidence library and query but retrieves by vector similarity only, without guideline anchors, evidence hierarchy, specialty routing, safety labels, graph links, or evidence arbitration.

## 5. Show KOM-Safe

Use the selected Q4 case to show how NSAID safety, renal/GI/CV gates, exercise intensity, injection boundary, and surgery referral boundary are displayed.

## 6. Open KOM-Sim

Switch between:

- Clinician alone
- Clinician + KOM
- Clinician + KOM-R
- KOM standalone

Explain that KOM-R means KOM recommendation plus rationale.

## 7. Open Results

Show:

- Full KOM overall 8.46 and safety 9.11.
- KOM w/o RAG and KOM w/o MDT performance decline.
- Clinician + KOM overall 7.34.
- KOM-RAG Precision@10 0.676 vs naive baseline 0.303.

## 8. Export report

Return to Case workspace and click **Download report** to export a local markdown report.
