const sections = [
  ['Study design and physician-facing validation framework', 'The study used standardized KOA cases to evaluate assessment support, treatment-planning support, clinician interaction, and scoring reliability.'],
  ['Standardized case set', 'Cases were organized across burden-demand quadrants and used for structured prescription tasks and system evaluation.'],
  ['KOM-Assess validation', 'Profile extraction, staging, phenotype explanation, radiographic support, and risk outputs were evaluated using predefined metrics.'],
  ['KOM-Treat development and validation', 'Evidence retrieval, specialty routing, MDT synthesis, prescription curation, and safety audit were evaluated through complete and ablated workflows.'],
  ['KOM-Sim clinician-in-the-loop simulation', 'Physicians completed standardized prescription tasks under different assistance conditions, generating physician-task prescription records.'],
  ['KOM-Score multi-source evaluation', 'Rule scoring, evaluator anchors, ICC reliability, and error taxonomy were used to quantify prescription quality and safety.'],
  ['Statistical analysis', 'Comparisons used paired designs where appropriate, reliability statistics, rule-score summaries, and retrieval metrics.'],
  ['Key metric definitions', 'Overall quality, safety, guideline alignment, personalization, actionability, evidence traceability, safety-critical error, clinically relevant error, safety-critical error rate, and naive RAG baseline were defined before evaluation.']
];

export default function MethodsPage() {
  return (
    <div className="space-y-6">
      <section>
        <p className="section-title">Methods</p>
        <h2 className="mt-2 text-3xl font-black text-ink">Concise manuscript-facing methods map</h2>
      </section>
      <section className="grid gap-4 lg:grid-cols-2">
        {sections.map(([title, text]) => (
          <article className="panel p-5" key={title}>
            <h3 className="text-lg font-black text-ink">{title}</h3>
            <p className="mt-3 small-note">{text}</p>
          </article>
        ))}
      </section>
      <section className="panel p-5">
        <h3 className="text-xl font-black text-ink">Key metric definitions</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {[
            ['overall quality', 'Overall usefulness as a physician-facing prescription.'],
            ['safety', 'Contraindications, safety gates, and escalation boundaries.'],
            ['guideline alignment', 'Consistency with current KOA guideline anchors.'],
            ['personalization', 'Use of patient-specific symptoms, KL grade, BMI, risks, and goals.'],
            ['actionability', 'Specific frequency, intensity, duration, progression, and stopping rules.'],
            ['evidence traceability', 'Recommendation-specific evidence or explicit rule rationale.'],
            ['safety-critical error', 'A prescription problem that may cause material harm or omit essential risk gating.'],
            ['clinically relevant error', 'A quality-changing error that usually does not directly create immediate severe harm.'],
            ['safety-critical error rate', 'Number of safety-critical errors / number of prescription records × 100.'],
            ['naive RAG baseline', 'Single-stage vector top-k retrieval without guideline anchors, hierarchy, specialty routing, safety labels, graph links, or arbitration.']
          ].map(([k, v]) => <div key={k} className="rounded-md border border-slate-200 bg-slate-50 p-3"><b>{k}</b><p className="mt-1 text-sm text-muted">{v}</p></div>)}
        </div>
      </section>
    </div>
  );
}
