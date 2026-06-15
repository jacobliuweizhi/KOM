const state = {
  content: null,
  profile: {},
  profileResult: null,
  page: "dashboard",
  level: "ALL",
  chain: "exercise_rehabilitation",
  manualChain: false,
  ragView: "case",
  evidenceDb: [],
  evidenceVisible: 80,
  evidencePageSize: 80,
  evidenceFilters: { q:"", level:"", domain:"", limit:600 },
  lastPatientFit: null,
  selectedEvidence: null,
  evidenceOverlay: null,
  agent: "exercise_rehab",
  selectedRisk: "structural",
  riskPrediction: null,
  riskEndpointStatus: "not requested",
  riskEndpointError: "",
  riskRequestSeq: 0,
  riskEndpointTimer: null,
  riskLastSignature: "",
  selectedCase: "surgical_referral",
  selectedFlow: "profile",
  selectedRadFinding: "left_knee",
  riskInputs: { bmi: 29.4, left_nrs: 8, right_nrs: 4, left_womac: 62, right_womac: 30, left_kl: 4, right_kl: 2 },
  savedProfile: null,
  profileSaveTimer: null,
  finalRx: null,
  rxFinalized: false,
  radRun: false,
  radAnnotated: false,
  useApi: false,
  negotiation: null,
  rxSelections: {
    medication: ["topical_diclofenac", "celecoxib"],
    injection: ["ia_corticosteroid"],
    exercise: ["aerobic_walking", "stationary_cycling", "resistance", "neuromotor_balance"],
    nutrition: ["leafy_vegetables", "legumes", "fish_poultry", "whole_grains"],
    psychology: ["risk_screen", "cbt_guided_self_help", "communication_script"],
    surgery: ["orthopedic_referral", "preoperative_warning"]
  },
  casePacks: {},
  packLoading: {}
};

const routes = [
  ["dashboard", "Overview"],
  ["settings", "Settings"],
  ["assess", "KOM-Profile"],
  ["rad", "KOM-Rad"],
  ["risk", "KOM-Risk"],
  ["rag", "KOM-RAG"],
  ["mdt", "KOM-MDT"],
  ["safe", "KOM-Safe"],
  ["rx", "KOM-Rx"],
  ["score", "KOM-Score"]
];

function $(s){ return document.querySelector(s); }
function $all(s){ return Array.from(document.querySelectorAll(s)); }
function esc(x){ return String(x ?? "").replace(/[&<>"']/g, m => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[m])); }
async function api(path,opt){ const r = await fetch(path,opt); const j = await r.json(); if(!j.ok) throw new Error(j.error?.message || "API call failed"); return j.data; }
function toast(msg){ const t=$("#toast"); t.textContent=msg; t.classList.remove("hidden"); setTimeout(()=>t.classList.add("hidden"),2600); }
function route(){ const p=location.pathname.replace(/^\/+/,"") || "dashboard"; const map={"ui":"dashboard","case-workspace":"assess","imaging":"rad","evidence-graph":"rag","treatment-board":"mdt","safety-review":"safe","clinical-report":"rx","validation":"score","trace":"score"}; return map[p] || p; }
function go(p){ history.pushState(null,"","/"+p); render(); }
window.addEventListener("popstate", render);

async function init(){ state.content = await api("/api/v9/content"); initProfile(); await loadPersistentState(); render(); }
function initProfile(){
  (state.content.profile_form?.fields || []).forEach(f=>state.profile[f.id]=f.value);
  syncProfileDerived("init");
}
async function loadPersistentState(){
  try{
    const saved=await api("/api/v16/profile/current");
    if(saved?.profile && Object.keys(saved.profile).length){
      state.profile={...state.profile,...saved.profile};
      if(saved.selectedCase) state.selectedCase=saved.selectedCase;
      if(saved.rxSelections) state.rxSelections=saved.rxSelections;
      if(saved.chain) state.chain=saved.chain;
      state.savedProfile=saved;
    }
  }catch(e){}
  try{
    const final=await api("/api/v16/rx/final");
    if(final?.prescription){
      state.finalRx=final.prescription;
      state.rxFinalized=true;
    }
  }catch(e){}
  syncProfileDerived("load-persistent");
}

function num(v,d=0){ const n=Number(v); return Number.isFinite(n)?n:d; }
function normalized(v){ return String(v ?? "").trim().toLowerCase(); }
function hasValue(v){ const s=normalized(v); return !!s && !["missing","unknown","not recorded","needs review","uncertain"].includes(s); }
function isNormalRenal(){ return /normal|egfr\s*(>=?\s*60|[6-9]\d|1\d{2})/i.test(String(state.profile.egfr||"")); }
function hasNoGiRisk(){ return /no ulcer|no history|none/i.test(String(state.profile.gi_history||"")); }
function hasNoAnticoag(){ return /none|no anticoagulant|no antiplatelet/i.test(String(state.profile.anticoag||"")); }
function hasNoRiskMeds(){ return /no (key|high-risk).*medication|none/i.test(String(state.profile.current_meds||"")); }
function medicationGateComplete(){ return isNormalRenal() && hasNoGiRisk() && hasNoAnticoag() && hasNoRiskMeds() && /low|reviewed|controlled/i.test(String(state.profile.cv_risk||"")); }
function missingInfo(){
  const items=[];
  if(!hasValue(state.profile.egfr) || !isNormalRenal()) items.push("eGFR / creatinine result");
  if(!hasValue(state.profile.gi_history)) items.push("GI ulcer or bleeding history");
  if(!hasValue(state.profile.anticoag)) items.push("Anticoagulant / antiplatelet status");
  if(!hasValue(state.profile.current_meds)) items.push("Current medication reconciliation");
  if(!hasValue(state.profile.conservative_history)) items.push("Conservative-treatment history");
  return items;
}
function targetSideId(){
  const side=String(state.profile.target_side||"Both knees").toLowerCase();
  if(side.includes("right")) return "right";
  if(side.includes("both")) return "both";
  return "left";
}
function primaryKnee(){
  const left=num(state.profile.left_kl,4), right=num(state.profile.right_kl,2);
  const target=targetSideId();
  if(target==="right") return "right";
  if(target==="both") return left>=right?"left":"right";
  return "left";
}
function kneeLabel(side){ return side==="left" ? "Left knee" : "Right knee"; }
function kneeKl(side){ return num(state.profile[side+"_kl"], side==="left"?4:2); }
function sidePain(side){ return num(state.profile[side+"_nrs"], num(state.profile.nrs, side==="left"?8:4)); }
function sideWomac(side){ return num(state.profile[side+"_womac_function"], num(state.profile.womac_function, side==="left"?62:30)); }
function kneeStrength(side){ return state.profile[side+"_strength"] || "Not recorded"; }
function primaryKl(){ return kneeKl(primaryKnee()); }
function kneePriority(side){
  const kl=kneeKl(side), pain=sidePain(side), womac=sideWomac(side);
  if(kl>=4 || pain>=7 || womac>=50) return "treatment-priority knee";
  if(kl>=2 || pain>=4 || womac>=25) return "active monitoring knee";
  return "prevention and maintenance knee";
}
function kneeDescriptor(side){
  const kl=kneeKl(side);
  return `${kneeLabel(side)} KL ${kl}, NRS ${sidePain(side)}, WOMAC function ${sideWomac(side)} (${kneePriority(side)})`;
}
function bilateralSummary(){ return `${kneeDescriptor("left")}; ${kneeDescriptor("right")}`; }
function caseFromProfile(){
  const kl=Math.max(num(state.profile.left_kl,4),num(state.profile.right_kl,2)), nrs=Math.max(sidePain("left"),sidePain("right")), womac=Math.max(sideWomac("left"),sideWomac("right"));
  const highBurden = kl>=3 || nrs>=7 || womac>=50;
  const goal = String(state.profile.quality_goal||"").toLowerCase();
  const surgeryQuestion = String(state.profile.surgery_question||"").toLowerCase();
  const injectionPreference = String(state.profile.avoid_injection||"").toLowerCase();
  const highDemand = /3 km|return|sport|referral|surgery|arthroplasty/.test(goal) || /yes|referral|surgery/.test(surgeryQuestion) || /yes|avoid repeated|avoid injection/.test(injectionPreference);
  const id = highBurden && highDemand ? "surgical_referral" : highBurden ? "medical_complex" : highDemand ? "active_rehab" : "early_education";
  return {id, highBurden, highDemand};
}
function syncProfileDerived(reason="profile"){
  state.riskInputs = {
    bmi: num(state.profile.bmi,29.4),
    left_nrs: sidePain("left"),
    right_nrs: sidePain("right"),
    left_womac: sideWomac("left"),
    right_womac: sideWomac("right"),
    left_kl: num(state.profile.left_kl,4),
    right_kl: num(state.profile.right_kl,2)
  };
  const q=caseFromProfile();
  state.selectedCase=state.profile.case_id || q.id;
  if(!state.manualChain){
    if(missingInfo().length || !medicationGateComplete()) state.chain="pharmacologic_or_injection";
    else if(q.highBurden && primaryKl()>=3) state.chain="surgery_or_escalation";
    else if(num(state.profile.bmi,0)>=27) state.chain="nutrition_weight_management";
    else state.chain="exercise_rehabilitation";
  }
  if(reason !== "risk-slider") state.negotiation=null;
}
function profileContext(){
  return {
    case_profile: state.selectedCase,
    case_label: currentCaseTitle(),
    target_side: state.profile.target_side,
    primary_knee: kneeLabel(primaryKnee()),
    targetKl: primaryKl(),
    left_kl: num(state.profile.left_kl,4),
    right_kl: num(state.profile.right_kl,2),
    left_nrs: sidePain("left"),
    right_nrs: sidePain("right"),
    left_womac_function: sideWomac("left"),
    right_womac_function: sideWomac("right"),
    left_strength: state.profile.left_strength,
    right_strength: state.profile.right_strength,
    bilateral_summary: bilateralSummary(),
    nrs: Math.max(sidePain("left"), sidePain("right")),
    bmi: num(state.profile.bmi,29.4),
    womac: Math.max(sideWomac("left"), sideWomac("right")),
    egfr: state.profile.egfr,
    gi: state.profile.gi_history,
    anticoag: state.profile.anticoag,
    currentMeds: state.profile.current_meds,
    conservativeHistory: state.profile.conservative_history,
    qualityGoal: state.profile.quality_goal,
    medicationGateComplete: medicationGateComplete()
  };
}

function topbar(){
  const c = state.content.case;
  return `<div class="topbar"><div class="topbar-inner"><div class="brand"><b>KOM Clinical Workbench</b><span>West China Hospital Sports Medicine</span></div><nav class="nav">${routes.map(([id,label])=>`<button class="${route()===id?'active':''}" onclick="go('${id}')">${label}</button>`).join("")}</nav><div class="selected-case"><b>${esc(c.title)}</b><span>${esc(c.one_line)}</span></div></div></div>`;
}
function shell(body){ $("#app").innerHTML = `<div class="app">${topbar()}<main class="screen">${body}</main></div>`; }
function pageLayout(title, subtitle, main, side){
  const r=route();
  const inlineSide=["assess","rag"].includes(r);
  const sideBlock=side?`<div class="panel ${inlineSide?'inline-side-panel':'side-panel'}">${side}</div>`:"";
  shell(`<div class="hero-card page-head page-head-${r}"><h1>${title}</h1><p>${subtitle}</p></div><div class="layout layout-${r} ${inlineSide?'inline-side-layout':''}"><div class="main-col">${main}${inlineSide?sideBlock:""}</div>${(!inlineSide&&side)?`<aside class="side">${sideBlock}</aside>`:""}</div>${moduleNextDock(r)}`);
}
function moduleRoute(name){ if(name==="KOM-Profile")return"assess"; if(name==="KOM-Rad")return"rad"; if(name==="KOM-Risk")return"risk"; if(name==="KOM-RAG")return"rag"; if(name==="KOM-MDT")return"mdt"; if(name==="KOM-Safe")return"safe"; if(name==="KOM-Rx")return"rx"; return"score"; }
function moduleNextInfo(r){
  return {
    assess:["risk","Next: KOM-Risk"],
    rad:["risk","Next: KOM-Risk"],
    risk:["rag","Next: KOM-RAG"],
    rag:["mdt","Next: KOM-MDT"],
    mdt:["safe","Next: KOM-Safe"],
    safe:["rx","Next: KOM-Rx"],
    rx:["score","Next: KOM-Score"]
  }[r] || null;
}
function moduleNextDock(r){
  if(r==="assess") return "";
  const info=moduleNextInfo(r);
  if(!info) return "";
  return `<div class="module-next-dock"><button class="btn primary" onclick="go('${info[0]}')">${esc(info[1])}</button></div>`;
}

function dashboard(){
  const a=state.content.architecture;
  shell(`<section class="hero hero-release"><div class="hero-card"><div class="eyebrow">West China Hospital Sports Medicine</div><h1>Knee osteoarthritis assessment and MDT prescription workbench</h1><p>KOM-Assess builds the patient profile, structured imaging interpretation and longitudinal risk estimates. KOM-Treat then performs evidence retrieval, specialty-agent prescription, safety negotiation and structured clinical reporting.</p><div class="actions"><button class="btn primary" onclick="go('settings')">Configure API key</button><button class="btn" onclick="go('assess')">Start KOM-Profile</button><button class="btn" onclick="go('risk')">Inspect risk endpoint</button><button class="btn green" onclick="go('mdt')">Open MDT board</button></div></div>${heroVisual()}</section>${flowOverview()}<section class="architecture architecture-release">${a.map((sys,i)=>`<div class="system-block ${i===0?'assess-block':'treat-block'}"><h2>${esc(sys.title)}</h2><p>${esc(sys.summary)}</p><div class="module-grid">${sys.modules.map(m=>`<div class="module" onclick="go('${moduleRoute(m.name)}')"><b>${esc(m.name)}</b><small>${esc(m.role)}</small><p>${esc(m.detail)}</p></div>`).join("")}</div></div>`).join("")}</section><section class="grid3 dashboard-bottom"><div class="panel"><h2>Locked showcase case</h2>${anchorList(state.content.case.anchors)}</div><div class="panel"><h2>Assessment gate meaning</h2><p>Medication and injection decisions use renal function, GI bleeding history, anticoagulant or antiplatelet exposure, cardiovascular risk and current medication reconciliation as explicit gates.</p></div><div class="panel"><h2>Interactive pathway</h2><p>Configure the API endpoint, edit KOM-Profile, run KOM-Rad, inspect endpoint-backed risk prediction, retrieve evidence, ask specialty agents, run KOM-Safe negotiation and export the KOM-Rx report.</p></div></section>`);
}
function flowNodes(){
  return [
    { id:"settings", label:"Settings", small:"API endpoint", route:"settings", x:"6%", y:"10%", detail:"Stores the OpenAI-compatible endpoint locally, tests text/vision access, and keeps private keys out of the release package." },
    { id:"profile", label:"KOM-Profile", small:"patient assessment", route:"assess", x:"7%", y:"43%", detail:"Builds the structured bilateral knee profile. Left/right KL can be edited here and are read-only downstream in KOM-Risk and KOM-Rad." },
    { id:"rad", label:"KOM-Rad", small:"image evidence", route:"rad", x:"34%", y:"17%", detail:"Displays side-specific KL/JSN/osteophyte imaging evidence. It documents the image anchor but does not provide KL editing controls." },
    { id:"contract", label:"Patient-state contract", small:"profile KL + scenarios", route:"assess", x:"36%", y:"48%", detail:"This joins profile, imaging, risk and treatment: Profile-controlled KL plus editable pain, WOMAC, BMI, strength, safety fields and goals." },
    { id:"risk", label:"KOM-Risk", small:"POST /api/v9/risk/predict", route:"risk", x:"65%", y:"17%", detail:"Calls the backend risk prediction endpoint. Scenario variables are posted; the endpoint returns side-specific risk and coupling audit terms." },
    { id:"rag", label:"KOM-RAG", small:"patient-fit evidence", route:"rag", x:"78%", y:"43%", detail:"Retrieves a patient-fit evidence pack with guideline anchors, meta-analyses, clinical trials and contextual safety or implementation evidence." },
    { id:"mdt", label:"KOM-MDT", small:"specialty agents", route:"mdt", x:"30%", y:"74%", detail:"Routes the patient state and evidence pack to rehabilitation, medication, nutrition, psychology and orthopedic boundary agents for specialty prescriptions." },
    { id:"safe", label:"KOM-Safe", small:"audit negotiation", route:"safe", x:"58%", y:"74%", detail:"Runs safety gates and sends negotiation feedback back to specialty agents until unsafe or unclear recommendations are revised." },
    { id:"rx", label:"KOM-Rx", small:"clinical report", route:"rx", x:"80%", y:"74%", detail:"Curates the accepted agent outputs into a structured patient report, standard MDT prescription, evidence rationale and validation trace." }
  ];
}
function selectFlowNode(id){ state.selectedFlow=id; const node=flowNodes().find(n=>n.id===id); node?.route ? go(node.route) : dashboard(); }
function openFlowStep(id,path){ state.selectedFlow=id; go(path); }
function heroVisual(){
  const nodes=flowNodes();
  const selected=nodes.find(n=>n.id===state.selectedFlow)||nodes[0];
  const edges=[
    ["settings","contract"],
    ["profile","contract"],
    ["rad","contract"],
    ["contract","risk"],
    ["risk","rag"],
    ["contract","mdt"],
    ["rag","mdt"],
    ["mdt","safe"],
    ["safe","rx"]
  ];
  const nodeById=Object.fromEntries(nodes.map(n=>[n.id,n]));
  const point=n=>({x:parseFloat(n.x)+8,y:parseFloat(n.y)+5});
  const edgeSvg=edges.map(([a,b])=>{
    const A=point(nodeById[a]), B=point(nodeById[b]);
    return `<line x1="${A.x}" y1="${A.y}" x2="${B.x}" y2="${B.y}" class="workflow-edge-line"/>`;
  }).join("");
  const bg=state.content.imaging?.original_asset || "assets/images/real_oai_knee_image_panel.png";
  return `<div class="visual clinical-visual workflow-visual"><img class="workflow-bg" src="/${esc(bg)}" alt="Bilateral knee radiograph background"><svg class="workflow-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="workflowArrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#d9edf3"/></marker></defs>${edgeSvg}</svg><div class="flow-map workflow-map">${nodes.map(n=>`<button class="flow-node workflow-node ${selected.id===n.id?'active':''} ${n.id==='contract'?'contract-node':''}" data-flow="${n.id}" style="left:${n.x};top:${n.y}" onclick="selectFlowNode('${n.id}')" title="${esc(n.detail)}">${esc(n.label)}<small>${esc(n.small)}</small></button>`).join("")}</div></div>`;
}
function flowOverview(){
  const steps=[
    {id:"profile", route:"assess", title:"Assessment layer", desc:"Open KOM-Profile for bilateral knee history, outcomes, imaging anchors and progression inputs."},
    {id:"rag", route:"rag", title:"Evidence layer", desc:"Open KOM-RAG for patient-fit retrieval, L1-L7 evidence chains and the full evidence network."},
    {id:"mdt", route:"mdt", title:"MDT prescription layer", desc:"Open KOM-MDT for specialty-agent reasoning, eligibility checks and draft treatment modules."},
    {id:"safe", route:"safe", title:"Safety audit layer", desc:"Open KOM-Safe for medication, injection, surgery, nutrition, psychology and evidence-gate negotiation."},
    {id:"rx", route:"rx", title:"Verifiable output", desc:"Open KOM-Rx for the selectable clinician prescription, report export and validation trace."}
  ];
  const current=route();
  return `<section class="flow-overview">${steps.map((s,i)=>`<button class="flow-step ${current===s.route||state.selectedFlow===s.id?'active':''}" onclick="openFlowStep('${s.id}','${s.route}')"><b>${i+1}. ${esc(s.title)}</b><p>${esc(s.desc)}</p></button>`).join("")}</section>`;
}
function anchorList(obj){ return `<div class="anchor-list">${Object.entries(obj).map(([k,v])=>`<div><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join("")}</div>`; }
function profileCaseCardHtml(x){
  const active=state.selectedCase===x.id;
  const presets={
    early_education:{title:"Education", burden:"Low burden", demand:"Low demand", kl:"KL1 / KL1", plan:"Home strength"},
    active_rehab:{title:"Activity rehab", burden:"Low burden", demand:"High demand", kl:"KL2 / KL1", plan:"Cycling + walking"},
    medical_complex:{title:"Safety-gated", burden:"High burden", demand:"Low demand", kl:"KL3 / KL2", plan:"Conservative care"},
    surgical_referral:{title:"Referral screen", burden:"High burden", demand:"High demand", kl:"KL4 / KL2", plan:"Prehab bridge"}
  };
  const m=presets[x.id]||{title:x.title||"Case", burden:"Case", demand:"Demand", kl:"KL fixed", plan:"Clinician review"};
  return `<button class="case-card profile-example-card ${active?'active':''}" data-case="${esc(x.id)}" title="${esc(x.title)}" onclick="loadCase('${x.id}')"><span class="case-no">${esc(x.short_label||"Case")}</span><span class="case-main"><b>${esc(m.title)}</b><small>${esc(m.plan)}</small></span><span class="case-kl-pill">${esc(m.kl.replace(" / ","/"))}</span><span class="case-status-line"><small>${esc(m.burden)}</small><small>${esc(m.demand)}</small></span></button>`;
}
function profileLiveSnapshotHtml(){
  return `<div class="profile-snapshot"><h3>Live bilateral snapshot</h3><div class="snapshot-grid"><div><b>Left knee</b><span>KL ${state.riskInputs.left_kl}; pain ${state.riskInputs.left_nrs}; WOMAC ${state.riskInputs.left_womac}</span><small>${esc(kneePriority("left"))}</small></div><div><b>Right knee</b><span>KL ${state.riskInputs.right_kl}; pain ${state.riskInputs.right_nrs}; WOMAC ${state.riskInputs.right_womac}</span><small>${esc(kneePriority("right"))}</small></div><div><b>Medication gate</b><span>${medicationGateComplete()?"Complete":"Incomplete"}</span><small>${esc(missingInfo().slice(0,3).join("; ")||"No critical missing item")}</small></div><div><b>Evidence route</b><span>${esc(state.chain.replaceAll("_"," "))}</span><small>Updates downstream RAG and MDT focus</small></div></div></div>`;
}
function klOptions(value){
  return [0,1,2,3,4].map(v=>`<option value="${v}" ${String(value)===String(v)?'selected':''}>KL ${v}</option>`).join("");
}
function profileKlField(id,label,compact=false){
  const value=state.profile[id] ?? (id==="left_kl"?"4":"2");
  return `<label class="${compact?'quick-control':'field profile-kl-field'}"><b>${esc(label)}</b><select data-id="${id}" onchange="updateProfileField(this)">${klOptions(value)}</select>${compact?`<small>${id==="left_kl"?"Left":"Right"} radiographic grade</small>`:`<small>Editable only in KOM-Profile. KOM-Rad documents image evidence and KOM-Risk reads this value.</small>`}</label>`;
}
function profileQuickRange(id,label,min,max,step){
  const value=state.profile[id] ?? "";
  return `<label class="quick-control"><b>${esc(label)} <span id="profileQuickLabel_${id}">${esc(value)}</span></b><input data-id="${id}" type="range" min="${min}" max="${max}" step="${step}" value="${esc(value)}" oninput="updateProfileFieldFast(this)" onchange="commitProfileField(this)"></label>`;
}
function profileQuickEditorHtml(){
  return `<div class="profile-quick-editor"><div class="quick-editor-head"><h3>Bilateral anchors visible here</h3><span>Changes immediately update KOM-Risk inputs, RAG focus, MDT modules and final Rx logic.</span></div><div class="quick-control-grid">${profileKlField("left_kl","Left KL",true)}${profileKlField("right_kl","Right KL",true)}${profileQuickRange("left_nrs","Left NRS",0,10,1)}${profileQuickRange("right_nrs","Right NRS",0,10,1)}${profileQuickRange("left_womac_function","Left WOMAC",0,68,1)}${profileQuickRange("right_womac_function","Right WOMAC",0,68,1)}${profileQuickRange("bmi","BMI",18,45,.1)}</div>${downstreamPreview()}</div>`;
}
function profileNextFloating(){
  return `<div class="profile-next-floating case-panel-next"><button class="btn primary" onclick="go('risk')">Next: KOM-Risk</button></div>`;
}

function assess(){
  syncProfileDerived("render-assess");
  const form=state.content.profile_form, fields=form.fields;
  pageLayout("KOM-Profile patient assessment", "Use one of four compact patient examples, then edit left/right KL and modifiable profile variables only in this Profile layer. The downstream KOM-Risk endpoint, RAG focus, MDT modules and final Rx logic update from this patient state.",
  `<div class="profile-workspace-v26"><div class="profile-left-stack"><div class="panel case-panel compact-case-panel"><div class="section-head"><div><h2>Four selectable patient examples</h2><p>Each example starts with a different left/right KL profile and treatment pathway. KL can be adjusted below before moving to KOM-Risk.</p></div><span class="badge dark">${esc(currentCaseTitle())}</span></div><div class="case-grid case-example-grid">${state.content.standard_cases.map(profileCaseCardHtml).join("")}</div>${profileNextFloating()}${profileQuickEditorHtml()}</div><div class="panel profile-fields-panel"><h2>Full profile fields</h2><div class="field-grid profile-fields">${fields.map(fieldHtml).join("")}</div><div class="actions"><button class="btn primary" onclick="generateProfile()">Generate KOM-Profile</button><button class="btn green" onclick="saveProfileConfig(true)">Save profile configuration</button><button class="btn" onclick="openCalc('womac')">WOMAC assistant</button><button class="btn" onclick="openCalc('koos')">KOOS assistant</button><button class="btn" onclick="openCalc('oks')">Oxford Knee Score assistant</button><button class="btn" onclick="openCalc('performance')">Performance tests</button></div></div></div><div class="profile-right-stack"><div class="panel case-rule profile-rule-panel"><h2>Current patient summary</h2>${caseSummaryHtml(form)}${profileLiveSnapshotHtml()}</div><div class="panel profile-output"><h2>Current KOM-Profile</h2><div id="profileBox">${profileHtml(state.profileResult)}</div>${profileSaveStatusHtml()}</div></div></div>${outcomeMeasurePanel()}<div class="panel followup-panel"><h2>Embedded follow-up nodes</h2><table><thead><tr><th>Time point</th><th>Collect</th><th>Decision use</th></tr></thead><tbody>${state.content.followup.map(r=>`<tr><td>${esc(r.time)}</td><td contenteditable>${esc(r.collect)}</td><td contenteditable>${esc(r.decision)}</td></tr>`).join("")}</tbody></table></div>${calcModal()}`,
  `<h3>Current case</h3><p><span class="badge dark">${esc(currentCaseTitle())}</span></p><h3>Missing information</h3>${missingInfo().map(x=>`<span class="badge red">${esc(x)}</span>`).join("") || '<span class="badge green">No safety-critical missing item</span>'}<h3>Field help</h3><p>Hover over each question mark for clinical definitions and measurement guidance.</p>`);
}
function currentCaseTitle(){
  const selected=state.content.standard_cases.find(x=>x.id===state.selectedCase)||state.content.standard_cases[3];
  return selected?.title || "Current patient";
}
function caseSummaryHtml(form){
  const selected=state.content.standard_cases.find(x=>x.id===state.selectedCase)||state.content.standard_cases[3];
  const q=caseFromProfile();
  const burden=q.highBurden?"Higher clinical burden":"Lower clinical burden";
  const demand=q.highDemand?"Goal or referral demand present":"Lower goal demand";
  const defaultChain=state.chain;
  const ruleRows=[
    ["Bilateral disease focus", `${bilateralSummary()}, left strength ${kneeStrength("left")}, right strength ${kneeStrength("right")}.`],
    ["Functional burden", `${burden}: worst-side KL ${Math.max(num(state.profile.left_kl,4),num(state.profile.right_kl,2))}, pain ${Math.max(sidePain("left"),sidePain("right"))}, WOMAC ${Math.max(sideWomac("left"),sideWomac("right"))}.`],
    ["Goal and preference", `${demand}: ${state.profile.quality_goal}; avoid repeated injections: ${state.profile.avoid_injection}.`],
    ["Default evidence route", defaultChain.replaceAll("_"," ")]
  ];
  return `<div class="classification-hero"><span class="summary-case-badge">${esc(selected.short_label||"Case")}</span><div class="classification-copy"><h3>${esc(selected.title)}</h3><p>${esc(selected.purpose)}</p></div></div><div class="case-rule-list">${ruleRows.map(r=>`<p><b>${esc(r[0])}</b><span>${esc(r[1])}</span></p>`).join("")}</div>`;
}
function profileRangeSpec(id){
  if(["left_womac_function","right_womac_function","womac_function"].includes(id)) return {min:0,max:68,step:1,label:"WOMAC"};
  if(["left_nrs","right_nrs","nrs"].includes(id)) return {min:0,max:10,step:1,label:"NRS"};
  if(id==="bmi") return {min:18,max:45,step:.1,label:"BMI"};
  return null;
}
function fieldHtml(f){
  const help=`<span class="help-dot" tabindex="0">?</span><span class="hover-help">${esc(f.help||"")}</span>`;
  const calc=f.calc?`<button class="mini-btn" onclick="openCalc('${f.calc}')">Assessment assistant</button>`:"";
  if(["left_kl","right_kl"].includes(f.id)) return profileKlField(f.id,f.label,false);
  const range=profileRangeSpec(f.id);
  if(range){
    const v=String(state.profile[f.id] ?? "");
    return `<label class="field profile-range-field"><b>${esc(f.label)} ${help}</b><div class="profile-range-row"><input data-id="${f.id}" type="range" min="${range.min}" max="${range.max}" step="${range.step}" value="${esc(v)}" oninput="updateProfileFieldFast(this)" onchange="commitProfileField(this)"><input class="range-number" data-id="${f.id}" value="${esc(v)}" inputmode="decimal" oninput="updateProfileFieldFast(this)" onchange="commitProfileField(this)"></div><small><span id="profileRangeLabel_${f.id}">${esc(v)}</span> ${esc(range.label)}</small>${calc}</label>`;
  }
  if(f.type==="select") return `<label class="field"><b>${esc(f.label)} ${help}</b><select data-id="${f.id}" onchange="updateProfileField(this)">${f.options.map(o=>`<option ${String(state.profile[f.id])===String(o)?'selected':''}>${esc(o)}</option>`).join("")}</select>${calc}</label>`;
  return `<label class="field"><b>${esc(f.label)} ${help}</b><input data-id="${f.id}" value="${esc(state.profile[f.id])}" onchange="updateProfileField(this)">${calc}</label>`;
}
function setProfileValue(id,value){
  state.profile[id]=String(value);
  if(["left_nrs","right_nrs","nrs"].includes(id)) state.profile.nrs=String(Math.max(sidePain("left"),sidePain("right")));
  if(["left_womac_function","right_womac_function","womac_function"].includes(id)) state.profile.womac_function=String(Math.max(sideWomac("left"),sideWomac("right")));
}
function updateRangePeers(id,value){
  $all(`[data-id="${CSS.escape(id)}"]`).forEach(el=>{ if(el.value!==String(value)) el.value=String(value); });
  const lab=$("#profileRangeLabel_"+id); if(lab) lab.textContent=value;
  const quick=$("#profileQuickLabel_"+id); if(quick) quick.textContent=value;
}
function updateProfileFieldFast(el){
  const id=el.dataset.id;
  setProfileValue(id,el.value);
  state.profileResult=null;
  state.manualChain=false;
  state.rxFinalized=false;
  state.riskPrediction=null;
  state.riskLastSignature="";
  syncProfileDerived("profile-slider");
  updateRangePeers(id,el.value);
  updateProfileDerivedUI({full:false});
  scheduleProfileSave();
}
function commitProfileField(el){ updateProfileFieldFast(el); saveProfileConfig(false); }
function updateProfileField(el){
  setProfileValue(el.dataset.id,el.value);
  state.profileResult=null;
  state.manualChain=false;
  state.rxFinalized=false;
  state.riskPrediction=null;
  state.riskLastSignature="";
  syncProfileDerived("profile-edit");
  updateRangePeers(el.dataset.id,el.value);
  updateProfileDerivedUI({full:true});
  scheduleProfileSave();
}
function updateProfileDerivedUI(opts={full:true}){
  const box=$("#profileBox"); if(box && opts.full) box.innerHTML=profileHtml(state.profileResult);
  const live=$("#downstreamPreview"); if(live) live.innerHTML=downstreamPreviewInner();
  const snap=$(".profile-snapshot"); if(snap) snap.outerHTML=profileLiveSnapshotHtml();
  const status=$("#profileSaveStatus"); if(status) status.innerHTML=profileSaveStatusInner();
  $all(".case-grid .case-card").forEach(card=>card.classList.toggle("active", card.dataset.case===state.selectedCase));
}
function loadCase(id){
  initProfile();
  state.selectedCase=id;
  state.profile.case_id=id;
  state.manualChain=false;
  const safetyClear={target_side:"Both knees",egfr:"eGFR >=60 and creatinine normal",gi_history:"No history",anticoag:"None",cv_risk:"Low",current_meds:"No high-risk interacting medication recorded",conservative_history:"Education, home exercise and topical analgesic trial documented",gad7:"GAD-7 2, low anxiety signal",phq9:"PHQ-9 3, low depression signal",sleep_quality:"Sleep acceptable",pain_catastrophizing:"No high catastrophizing signal",exercise_preference:"Walking and home strengthening",nutrition_risk:"No renal or malnutrition warning",surgical_cv_screen:"No self-reported cardiovascular red flag",surgical_resp_screen:"No respiratory red flag",skin_dental_infection_screen:"No skin wound or dental infection signal",weightbearing_alignment_xray:"Weight-bearing AP/lateral radiographs available",knee_rom:"Left 0-125, right 0-130"};
  const presets={
    early_education:{...safetyClear,age:"56",sex:"Female",bmi:"23.8",left_kl:"1",right_kl:"1",left_nrs:"2",right_nrs:"1",left_womac_function:"14",right_womac_function:"10",left_progression_status:"Early OA / no radiographic progression",right_progression_status:"Early OA / no radiographic progression",nrs:"2",womac_function:"14",left_strength:"MRC 5/5; no dynamometer deficit recorded",right_strength:"MRC 5/5; no dynamometer deficit recorded",balance:"Single-leg stance >=20 s without support",quality_goal:"Maintain daily mobility and prevent flare during work travel",avoid_injection:"No injection requested",surgery_question:"No",exercise_preference:"Brisk walking, stair pacing and home resistance band",nutrition_risk:"No weight-loss target; maintain balanced diet"},
    active_rehab:{...safetyClear,age:"62",sex:"Male",bmi:"26.2",left_kl:"2",right_kl:"1",left_nrs:"5",right_nrs:"2",left_womac_function:"34",right_womac_function:"18",left_progression_status:"Mild medial compartment progression",right_progression_status:"Stable monitoring",nrs:"5",womac_function:"34",left_strength:"MRC 4+/5; mild quadriceps endurance deficit",right_strength:"MRC 5/5",balance:"Single-leg stance 12-15 s, no fall",quality_goal:"Return to 5 km recreational walking and stationary cycling",avoid_injection:"Prefers non-injection options",surgery_question:"No",exercise_preference:"Stationary cycling plus progressive walking",gad7:"GAD-7 4, performance worry only",phq9:"PHQ-9 2, no depression signal",sleep_quality:"Sleep disrupted only after long walks",pain_catastrophizing:"Low catastrophizing; high activity expectation"},
    medical_complex:{...safetyClear,age:"72",sex:"Female",bmi:"31.8",target_side:"Both knees",left_kl:"3",right_kl:"2",left_nrs:"7",right_nrs:"5",left_womac_function:"56",right_womac_function:"38",left_progression_status:"Progressive symptomatic OA",right_progression_status:"Active monitoring",nrs:"7",womac_function:"56",left_strength:"MRC 4-/5; sit-to-stand pain inhibition",right_strength:"MRC 4/5",balance:"Single-leg stance <10 s or needs support",egfr:"eGFR 52, CKD stage 3a self-reported",gi_history:"Prior peptic ulcer bleeding",anticoag:"Apixaban for atrial fibrillation",cv_risk:"Moderate cardiovascular risk after review",current_meds:"Apixaban, amlodipine, metformin; medication reconciliation incomplete",conservative_history:"Education and intermittent home exercise; topical NSAID trial partial response",quality_goal:"Walk safely indoors and reduce night pain without oral NSAID escalation",avoid_injection:"No strong preference but asks about injection alternatives",surgery_question:"Uncertain",exercise_preference:"Supervised low-impact cycling or aquatic exercise; fear of falling",nutrition_risk:"Obesity with CKD stage 3a; protein target requires renal review",gad7:"GAD-7 8, mild anxiety around falling",phq9:"PHQ-9 7, mild depressive symptoms",sleep_quality:"Sleep fragmented by pain 3 nights per week",pain_catastrophizing:"Moderate pain catastrophizing signal",surgical_cv_screen:"Atrial fibrillation on anticoagulant; cardiology clearance not collected",surgical_resp_screen:"No respiratory red flag reported",skin_dental_infection_screen:"Dental status not checked",weightbearing_alignment_xray:"Weight-bearing alignment radiograph not yet updated",knee_rom:"Left 5-105 with effusion, right 0-120"},
    surgical_referral:{...safetyClear,age:"67",sex:"Male",bmi:"29.4",target_side:"Both knees",left_kl:"4",right_kl:"2",left_nrs:"8",right_nrs:"4",left_womac_function:"62",right_womac_function:"30",left_progression_status:"Advanced OA / progressed",right_progression_status:"Stable monitoring",nrs:"8",womac_function:"62",left_strength:"MRC 4-/5; isometric knee-extension peak force not measured",right_strength:"MRC 4+/5; isometric knee-extension peak force not measured",balance:"Single-leg stance <10 s or needs support",egfr:"MISSING",gi_history:"MISSING",anticoag:"MISSING",cv_risk:"Needs review",current_meds:"MISSING",conservative_history:"Structured rehabilitation duration and response not documented",quality_goal:"Walk 3 km safely, avoid repeated injections, and discuss orthopedic referral",avoid_injection:"Yes",surgery_question:"Yes",exercise_preference:"Walking goal with supervised prehabilitation; cycling acceptable",nutrition_risk:"BMI elevated; weight-loss target must preserve muscle",gad7:"GAD-7 10, moderate anxiety about surgery",phq9:"PHQ-9 6, mild depressive symptoms",sleep_quality:"Pain-related insomnia most nights",pain_catastrophizing:"High worry about irreversible disability",surgical_cv_screen:"Self-reported exertional dyspnea not yet characterized",surgical_resp_screen:"Former smoker; no spirometry report collected",skin_dental_infection_screen:"Skin intact; dental status not recorded",weightbearing_alignment_xray:"Weight-bearing AP/lateral radiographs present; long-leg alignment not collected",knee_rom:"Left 8-100, right 0-125"}
  }[id] || {};
  Object.assign(state.profile,presets);
  const rxByCase={
    early_education:{medication:["topical_diclofenac"],injection:[],exercise:["aerobic_walking","quadriceps_isometric"],nutrition:["leafy_vegetables","whole_grains"],psychology:["risk_screen","communication_script"],surgery:[]},
    active_rehab:{medication:["topical_diclofenac","acetaminophen"],injection:[],exercise:["aerobic_walking","stationary_cycling","resistance","hip_abductor_chain","tai_chi_yoga"],nutrition:["leafy_vegetables","legumes","fish_poultry"],psychology:["risk_screen","relaxation_pacing","communication_script"],surgery:[]},
    medical_complex:{medication:["topical_diclofenac","acetaminophen","semaglutide_obesity","duloxetine"],injection:["ia_corticosteroid","lp_prp"],exercise:["stationary_cycling","aquatic","quadriceps_isometric","neuromotor_balance"],nutrition:["weight_target","leafy_vegetables","legumes","obesity_pharmacotherapy_review"],psychology:["risk_screen","cbt_guided_self_help","behavioral_activation","relaxation_pacing"],surgery:["preoperative_warning"]},
    surgical_referral:{medication:["topical_diclofenac"],injection:["genicular_rfa"],exercise:["stationary_cycling","sit_to_stand_step","neuromotor_balance"],nutrition:["weight_target","leafy_vegetables","fish_poultry"],psychology:["risk_screen","cbt_guided_self_help","communication_script"],surgery:["orthopedic_referral","preoperative_warning","prehab"]}
  };
  if(rxByCase[id]) state.rxSelections=JSON.parse(JSON.stringify(rxByCase[id]));
  syncProfileDerived("case-load");
  state.profileResult=null;
  state.finalRx=null;
  state.rxFinalized=false;
  saveProfileConfig(false);
  toast(`${currentCaseTitle()} loaded. Downstream risk, evidence and MDT focus updated.`);
  assess();
}
async function generateProfile(){ state.manualChain=false; syncProfileDerived("generate"); const result=await api("/api/v10/profile/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(state.profile)}); state.profileResult=result; if(result.case_profile && !state.profile.case_id) state.selectedCase=result.case_profile; $("#profileBox").innerHTML=profileHtml(result); updateProfileDerivedUI(); await saveProfileConfig(false); toast("KOM-Profile generated for " + currentCaseTitle()); }
function profileHtml(p){ if(!p) return `<p>No profile has been generated yet. Click <b>Generate KOM-Profile</b> to display the selected case, missing information, safety gates and the next clinical step.</p>`; const kneeRows=p.knees?Object.values(p.knees).map(k=>`<tr><td>${esc(k.side)}</td><td>${esc(k.kl)}</td><td>${esc(k.pain_nrs)}</td><td>${esc(k.womac_function)}</td><td>${esc(k.progression_state)}</td><td>${esc(k.clinical_priority)}</td></tr>`).join(""):""; return `<div class="profile-summary"><span class="badge dark">${esc(currentCaseTitle())}</span><span class="badge">${esc(p.burden)}</span><span class="badge">${esc(p.demand)}</span></div><h3>One-line profile</h3><p>${esc(p.one_line)}</p>${kneeRows?`<h3>Side-specific knees</h3><table class="compact"><thead><tr><th>Knee</th><th>KL</th><th>NRS</th><th>WOMAC</th><th>Progression</th><th>Priority</th></tr></thead><tbody>${kneeRows}</tbody></table>`:""}<h3>Missing information</h3>${p.missing.map(x=>`<span class="badge red">${esc(x)}</span>`).join("") || '<span class="badge green">None recorded</span>'}<h3>Safety gates</h3><ul>${p.gates.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`; }
function downstreamPreview(){ return `<div id="downstreamPreview">${downstreamPreviewInner()}</div>`; }
function downstreamPreviewInner(){ return `<h3>Live downstream effect</h3><p><b>Risk inputs:</b> BMI ${state.riskInputs.bmi}; profile left KL ${state.riskInputs.left_kl}, NRS ${state.riskInputs.left_nrs}, WOMAC ${state.riskInputs.left_womac}; profile right KL ${state.riskInputs.right_kl}, NRS ${state.riskInputs.right_nrs}, WOMAC ${state.riskInputs.right_womac}.</p><p><b>Bilateral decision frame:</b> ${esc(bilateralSummary())}.</p><p><b>Primary evidence focus:</b> ${esc(state.chain.replaceAll("_"," "))}</p><p><b>Medication gate:</b> ${medicationGateComplete()?'<span class="badge green">complete</span>':'<span class="badge red">requires review</span>'}</p><p><b>Selected case:</b> <span class="badge dark">${esc(currentCaseTitle())}</span></p>`; }
function profileSavePayload(){
  return {profile:{...state.profile}, selectedCase:state.selectedCase, riskInputs:{...state.riskInputs}, rxSelections:state.rxSelections, chain:state.chain, saved_at:new Date().toISOString()};
}
function profileSaveStatusInner(){
  const saved=state.savedProfile?.saved_at || state.savedProfile?.savedAt;
  return saved ? `<span class="badge green">Saved profile configuration</span><small>${esc(saved)}</small>` : `<span class="badge amber">Profile not saved yet</span><small>Save once to embed the current patient state for KOM-Risk, KOM-RAG, KOM-MDT and KOM-Rx.</small>`;
}
function profileSaveStatusHtml(){ return `<div id="profileSaveStatus" class="profile-save-status">${profileSaveStatusInner()}</div>`; }
function scheduleProfileSave(){ clearTimeout(state.profileSaveTimer); state.profileSaveTimer=setTimeout(()=>saveProfileConfig(false),700); }
async function saveProfileConfig(showToast=true){
  syncProfileDerived("profile-save");
  const payload=profileSavePayload();
  try{
    const saved=await api("/api/v16/profile/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    state.savedProfile=saved;
    const status=$("#profileSaveStatus"); if(status) status.innerHTML=profileSaveStatusInner();
    if(showToast) toast("Profile configuration saved and embedded for downstream modules.");
    return saved;
  }catch(e){
    if(showToast) toast("Profile save failed: " + e.message);
    return null;
  }
}
function outcomeMeasurePanel(){ const measures=[["WOMAC","Pain, stiffness and physical function in hip or knee OA."],["KOOS","Symptoms, pain, ADL, sport/recreation and quality of life."],["Oxford Knee Score","12-item knee pain and function measure, often used around arthroplasty evaluation."],["NRS pain","0-10 pain intensity anchor."],["MRC strength","Manual muscle testing from 0 to 5; can be paired with dynamometer peak-force values."],["TUG / Chair stand / 6-minute walk","Performance tests for mobility, lower-limb function and fall-risk context."]]; return `<div class="panel measures-panel"><h2>Clinical score and function set</h2><div class="measure-grid">${measures.map(m=>`<div><b>${esc(m[0])}</b><span>${esc(m[1])}</span></div>`).join("")}</div></div>`; }
function calcModal(){ return `<div id="calcModal" class="modal hidden"><div class="modal-card"><button class="modal-close" onclick="closeCalc()">x</button><h2 id="calcTitle">Assessment assistant</h2><div id="calcBody"></div><div class="actions"><button class="btn primary" onclick="applyCalc()">Write result to profile</button><button class="btn" onclick="closeCalc()">Cancel</button></div></div></div>`; }
function openCalc(kind){
  state.activeCalc=kind; const m=$("#calcModal"); m.classList.remove("hidden");
  const data={
    womac:["WOMAC assistant","Score each item 0 to 4. WOMAC covers pain, stiffness and function in knee or hip OA.",["Walking on flat ground pain","Stairs pain","Night pain","Sitting/lying pain","Standing pain","Morning stiffness","Stiffness after activity","Descending stairs","Ascending stairs","Rising from sitting","Standing","Bending","Walking","Getting in/out of car","Shopping","Putting on socks","Rising from bed","Taking off socks","Lying in bed","Getting in/out of bath","Sitting","Getting on/off toilet","Heavy domestic duties","Light domestic duties"]],
    koos:["KOOS-ADL assistant","Score each item 0 to 4; the assistant converts responses into a 0-100 ADL score where higher is better.",["Stairs","Rising from sitting","Standing","Bending to floor","Walking on flat ground","Getting in/out of car","Shopping","Putting on socks","Rising from bed","Light domestic duties","Heavy domestic duties"]],
    oks:["Oxford Knee Score assistant","Twelve patient-reported knee pain and function items; lower function or severe pain strengthens referral discussion.",["Night pain","Washing/drying","Transport","Walking time","Pain while walking","Limping","Kneeling","Work or housework","Confidence in knee","Shopping","Stairs","Sudden severe pain"]],
    performance:["Performance tests","Add objective mobility tests when available.",["Timed Up and Go >12 seconds","30-second chair stand below age expectation","6-minute walk distance limited","Single-leg stance reduced","Gait speed below 1.0 m/s"]],
    mrc:["Quadriceps strength assistant","Quadriceps are the anterior thigh muscles that extend the knee. Record both side and method. MRC grade 0=no contraction, 1=flicker, 2=movement with gravity eliminated, 3=against gravity, 4=against resistance but weak, 5=normal.",["Left quadriceps MRC 4-/5","Left quadriceps MRC 5/5","Right quadriceps MRC 4+/5","Right quadriceps MRC 5/5","Left isometric knee-extension peak force recorded","Right isometric knee-extension peak force recorded"]],
    cv:["Cardiovascular risk assistant","Use this to identify NSAID and perioperative risk. Mark moderate/high risk for ASCVD, heart failure, CKD, uncontrolled hypertension or multiple risk factors.",["Prior myocardial infarction / stroke / stent","Heart failure or CKD","Uncontrolled hypertension","Diabetes","Smoking","High LDL or unknown lipids"]],
    meds:["Key medication screening","Mark current medication classes that affect NSAID, injection or surgical safety. If none apply, select the explicit none option.",["No key risk medication","Warfarin","DOAC","Aspirin or clopidogrel","Current oral NSAID","ACEI/ARB or diuretic","Systemic corticosteroid","SSRI/SNRI","Opioid analgesic"]],
    conservative:["Conservative-treatment history","Record what has already been tried, duration and response.",["OA education / self-management completed","Structured rehabilitation >=6 weeks","Weight-management attempt","Topical NSAID trial","Oral medication after clinician review","Physical therapy","Prior corticosteroid injection","Prior hyaluronic-acid injection","Prior PRP injection","Brace or cane"]],
    egfr:["eGFR / creatinine guidance","eGFR requires a blood creatinine test. Record the actual result category; do not infer it by interview alone.",["eGFR >=60 and creatinine normal","eGFR 30-59 or CKD risk","eGFR <30 or advanced CKD","Blood creatinine/eGFR ordered","Needs nephrology/internal medicine review"]],
    gi:["GI history assistant","Ask about gastric/duodenal ulcer, GI bleeding, melena, anemia, endoscopy and PPI use.",["No ulcer or GI bleeding history","Prior ulcer","Prior GI bleeding or melena","Unexplained anemia","Positive endoscopy history"]]
  }[kind];
  $("#calcTitle").textContent=data[0];
  $("#calcBody").innerHTML=`<p class="muted">${esc(data[1])}</p><div class="scale-grid ${kind}">${data[2].map((it,i)=> ["womac","koos","oks"].includes(kind) ? `<label><span>${esc(it)}</span><select class="scale-item">${[0,1,2,3,4].map(v=>`<option ${i%5===0&&v===3?'selected':''}>${v}</option>`).join("")}</select></label>` : `<label><span>${esc(it)}</span><input class="scale-check" type="checkbox"></label>`).join("")}</div>`;
}
function closeCalc(){ $("#calcModal").classList.add("hidden"); }
function applyCalc(){
  const kind=state.activeCalc;
  if(["womac","koos","oks"].includes(kind)){
    const vals=$all(".scale-item").map(x=>Number(x.value));
    const sum=vals.reduce((a,b)=>a+b,0);
    if(kind==="womac"){ const fn=String(vals.slice(7).reduce((a,b)=>a+b,0)); state.profile.womac_pain=String(vals.slice(0,5).reduce((a,b)=>a+b,0)); state.profile.womac_stiffness=String(vals.slice(5,7).reduce((a,b)=>a+b,0)); state.profile.womac_function=fn; state.profile.left_womac_function=fn; if(!hasValue(state.profile.right_womac_function)) state.profile.right_womac_function=fn; }
    if(kind==="koos") state.profile.koos_adl=String(Math.max(0,Math.round(100-(sum/(vals.length*4))*100)));
    if(kind==="oks") state.profile.quality_goal=`Oxford Knee Score item burden ${sum}/48; align treatment with patient-reported limitation.`;
  } else {
    const selected=$all(".scale-check").map(x=>x.checked?x.closest("label").querySelector("span").textContent:null).filter(Boolean);
    if(kind==="mrc") state.profile.left_strength=selected.join("; ")||"MRC 5/5; no numeric deficit recorded";
    if(kind==="performance") state.profile.balance=selected.join("; ")||"No abnormal performance test recorded";
    if(kind==="cv") state.profile.cv_risk=selected.length>=3||selected.some(x=>/myocardial|heart|CKD/i.test(x))?"High":selected.length?"Moderate":"Low";
    if(kind==="meds") state.profile.current_meds=selected.join("; ")||"No key risk medication";
    if(kind==="conservative") state.profile.conservative_history=selected.join("; ")||"No structured conservative treatment recorded";
    if(kind==="egfr") state.profile.egfr=selected.join("; ")||"MISSING";
    if(kind==="gi") state.profile.gi_history=selected.join("; ")||"No ulcer or GI bleeding history";
  }
  closeCalc(); syncProfileDerived("calc"); assess(); toast("Assessment result written to KOM-Profile");
}

function radFindings(){
  return [
    { id:"right_knee", label:"Right knee: KL2", x:"18%", y:"34%", title:"Right knee side-specific finding", detail:"The right knee shows milder medial joint-space narrowing and osteophytes, consistent with KL grade 2 in this showcase.", use:"Receives its own risk prediction, strengthening, load advice and follow-up monitoring; do not copy left-knee escalation to the right knee." },
    { id:"left_knee", label:"Left knee: KL4", x:"57%", y:"38%", title:"Left knee side-specific KL grade", detail:"The left knee has severe medial compartment narrowing with osteophyte and sclerosis, supporting KL grade 4 structural burden.", use:"Supports orthopedic specialist evaluation, preoperative warning review, load management and low-impact rehabilitation for the left knee." },
    { id:"left_medial_jsn", label:"Left severe medial JSN", x:"58%", y:"54%", title:"Left medial joint-space narrowing", detail:"Marked left medial joint-space narrowing indicates compartment-dominant structural disease and explains why high-impact loading is avoided.", use:"Strength, balance and gait plans should protect the left medial compartment while also training the right knee." },
    { id:"left_osteophyte", label:"Left osteophyte / sclerosis", x:"60%", y:"63%", title:"Left osteophyte and subchondral sclerosis", detail:"Marginal osteophyte formation and medial subchondral sclerosis reinforce advanced osteoarthritic change on the left side.", use:"Supports advanced OA phenotype; it is not a standalone surgical decision." }
  ];
}
function selectRadFinding(id){ state.selectedRadFinding=id; state.radRun=true; state.radAnnotated=true; rad(); }
function radFindingPanel(){
  const f=radFindings().find(x=>x.id===state.selectedRadFinding)||radFindings()[1];
  return `<div class="rad-finding-panel"><h3>${esc(f.title)}</h3><p>${esc(f.detail)}</p><p><b>How this changes care:</b> ${esc(f.use)}</p><div class="rad-finding-list">${radFindings().map(x=>`<button class="${x.id===f.id?'active':''}" data-rad-finding="${x.id}" onclick="selectRadFinding('${x.id}')">${esc(x.label)}</button>`).join("")}</div></div>`;
}
function radImageHtml(){
  const im=state.content.imaging;
  const overlay=state.radRun && state.radAnnotated ? `<div class="rad-overlay">${radFindings().map(f=>`<button class="rad-hotspot ${state.selectedRadFinding===f.id?'active':''}" data-rad-finding="${f.id}" style="left:${f.x};top:${f.y}" onclick="selectRadFinding('${f.id}')">${esc(f.label)}</button>`).join("")}</div>` : "";
  return `<div class="image-view full-image"><img id="radImage" src="/${im.original_asset}" alt="Original OAI knee radiograph">${overlay}</div>`;
}
function rad(){
  const im=state.content.imaging;
  const result = state.radRun ? `<h2>Structured interpretation</h2>${radFindingPanel()}<table class="compact"><thead><tr><th>Side</th><th>KL</th><th>Joint space</th><th>Osteophyte / sclerosis</th><th>Review</th></tr></thead><tbody>${im.examples.map(r=>`<tr><td>${esc(r.side)}</td><td>${esc(r.kl)}</td><td>${esc(r.medial_jsn)}<br>${esc(r.lateral_jsn)}</td><td>${esc(r.osteophyte)}<br>${esc(r.sclerosis)}</td><td>${esc(r.review)}</td></tr>`).join("")}</tbody></table><div class="model-strip"><b>Embedded model</b><span>${esc(im.model_note)}</span></div><div class="thumbs two-knee">${im.examples.map((r,i)=>`<figure><img src="/${i===0?im.left_crop:im.right_crop}" alt="${esc(r.side)}"><figcaption>${esc(r.side)}: KL ${esc(r.kl)}</figcaption></figure>`).join("")}</div>` : `<div class="rad-pending"><h2>Structured interpretation has not been run</h2><p>The initial view shows the original OAI radiograph. Click <b>Run structural interpretation</b> to reveal English annotations and target-knee findings.</p></div>`;
  pageLayout("KOM-Rad structured imaging interpretation", "The radiology module starts from the original OAI X-ray and reveals annotation plus structured KL, joint-space narrowing, osteophyte and sclerosis findings only after the run action. KL is documented here but changed only through KOM-Profile.",
  `<div class="panel image-layout aligned-rad"><div>${radImageHtml()}<div class="actions rad-actions"><button class="btn" onclick="state.radAnnotated=false;rad()">Original image</button><button class="btn" onclick="state.radAnnotated=true;state.radRun=true;rad()">Annotated image</button><label class="btn">Upload image<input type="file" accept="image/*" style="display:none" onchange="previewUpload(event)"></label><button class="btn primary" onclick="runRad()">Run structural interpretation</button></div></div><div id="radResult">${result}</div></div>`,
  `<h3>Clinical meaning</h3><p>KOM-Rad stores both knees separately and does not expose KL editing controls. Left knee: ${esc(kneeDescriptor("left"))}. Right knee: ${esc(kneeDescriptor("right"))}.</p><button class="btn primary next-cta" onclick="go('risk')">Next: KOM-Risk</button>`);
}
function previewUpload(e){ const f=e.target.files[0]; if(!f)return; $("#radImage").src=URL.createObjectURL(f); toast("Local image preview loaded. Structured interpretation still requires model or clinician review."); }
async function runRad(){ await api("/api/v9/rad/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}); state.radRun=true; state.radAnnotated=true; rad(); toast("KOM-Rad interpretation completed"); }

function riskInputSignature(){
  const x=state.riskInputs;
  return JSON.stringify({bmi:x.bmi,left_kl:x.left_kl,right_kl:x.right_kl,left_nrs:x.left_nrs,right_nrs:x.right_nrs,left_womac:x.left_womac,right_womac:x.right_womac,target_side:state.profile.target_side||"Both knees"});
}
function riskPayload(){
  syncProfileDerived("risk-payload");
  const x=state.riskInputs;
  return {
    endpoint_requested: "/api/v9/risk/predict",
    bmi: x.bmi,
    left_kl: x.left_kl,
    right_kl: x.right_kl,
    left_nrs: x.left_nrs,
    right_nrs: x.right_nrs,
    left_womac: x.left_womac,
    right_womac: x.right_womac,
    left_womac_function: x.left_womac,
    right_womac_function: x.right_womac,
    target_side: state.profile.target_side||"Both knees",
    profile: profileContext(),
    risk_inputs: {...x,left_womac_function:x.left_womac,right_womac_function:x.right_womac}
  };
}
function emptyRiskPrediction(){
  const x=state.riskInputs;
  const side=(name)=>({kl:name==="left"?x.left_kl:x.right_kl,pain_nrs:name==="left"?x.left_nrs:x.right_nrs,womac_function:name==="left"?x.left_womac:x.right_womac,structural:0,surgery:0,symptom:0,structural_event_applicable:true,surgery_rule_floor:0,coupling:{contralateral_knee:name==="left"?"right":"left",coefficient_version:"BILATERAL_WEIGHT_V4_KL4_CEILING_20260615",bilateral_load_term:0,compensation_load_term:0,shared_burden_term:0}});
  return {endpoint:"POST /api/v9/risk/predict",request_id:"pending endpoint response",model_source:"waiting_for_backend_endpoint",not_frontend_simulation:true,input_echo:{bmi:x.bmi,left:side("left"),right:side("right")},left:side("left"),right:side("right"),max:{structural:0,surgery:0,symptom:0},side_specific:true,bilateral_coupled:true};
}
function currentRiskPrediction(){
  if(state.riskPrediction && state.riskLastSignature===riskInputSignature()) return state.riskPrediction;
  return emptyRiskPrediction();
}
function riskVal(sim,side,id){
  const n=Number(sim?.[side]?.[id]);
  return Number.isFinite(n) ? n : 0;
}
function riskPct(v){ const n=Number(v); return Number.isFinite(n) ? Math.round(n*100) : 0; }
function endpointMax(sim,id){
  const m=Number(sim?.max?.[id]);
  if(Number.isFinite(m)) return m;
  return Math.max(riskVal(sim,"left",id), riskVal(sim,"right",id));
}
function riskCouplingLabel(c,side){
  const other=c.contralateral_knee || c.other || (side==="left"?"right":"left");
  const label=String(other).toLowerCase().includes("left") ? "Left knee" : String(other).toLowerCase().includes("right") ? "Right knee" : other;
  return label || "Contralateral knee";
}
function riskEventMessage(sim,side,id){
  const s=sim?.[side]||{};
  if(id==="structural" && s.structural_event_applicable===false){
    return s.structural_probability_note || "KL4 structural ceiling: no KL+1 event is possible; this displays end-stage status rather than further KL progression.";
  }
  if(id==="surgery" && Number(s.surgery_rule_floor)>0){
    const floor=riskPct(s.surgery_rule_floor);
    return `${s.surgery_rule_label || "Escalation gate"} applied: 96-month TKA-event estimate is floored at ${floor}% before bilateral coupling display.`;
  }
  if(id==="symptom" && Number(s.symptom_rule_floor)>0){
    return `End-stage symptom/function floor applied at ${riskPct(s.symptom_rule_floor)}% because KL4 plus symptoms should not be treated as a low-burden scenario.`;
  }
  return "";
}
function riskCardSemanticNote(sim,id){
  const messages=["left","right"].map(side=>riskEventMessage(sim,side,id)).filter(Boolean);
  if(!messages.length) return "";
  const unique=[...new Set(messages)];
  return `<p class="risk-card-semantic">${unique.map(esc).join(" ")}</p>`;
}
function riskSideTable(sim,id){
  return `<div class="risk-side-table">${["left","right"].map(side=>{ const s=sim[side]||{}, c=s.coupling||{}; const pct=riskPct(riskVal(sim,side,id)); const eventNote=riskEventMessage(sim,side,id); return `<div class="risk-detail-knee ${side===primaryKnee()?'primary-knee':''}"><h3>${esc(kneeLabel(side))} <span class="badge">${esc(kneePriority(side))}</span></h3><div class="risk-big">${pct}%</div><p>KL ${esc(s.kl ?? (side==="left"?state.riskInputs.left_kl:state.riskInputs.right_kl))}; NRS ${esc(s.pain_nrs ?? (side==="left"?state.riskInputs.left_nrs:state.riskInputs.right_nrs))}; WOMAC ${esc(s.womac_function ?? (side==="left"?state.riskInputs.left_womac:state.riskInputs.right_womac))}. ${side===primaryKnee()?'Highest current treatment priority':'Active side-specific monitoring'}.</p>${eventNote?`<p class="risk-event-note">${esc(eventNote)}</p>`:""}<p class="coupling-note"><b>Cross-knee coupling:</b> ${esc(riskCouplingLabel(c,side))} contributes KL ${esc(c.contralateral_kl ?? c.other_kl ?? "-")}, NRS ${esc(c.contralateral_pain_nrs ?? c.other_nrs ?? "-")}, WOMAC ${esc(c.contralateral_womac_function ?? c.other_womac ?? "-")} through shared activity load and compensation.</p><div class="riskbar"><i style="width:${pct}%"></i></div></div>`; }).join("")}</div>`;
}
function riskWeightAuditHtml(sim){
  const rows=["left","right"].map(side=>{ const c=(sim[side]||{}).coupling||{}; const b=Number(c.bilateral_load_term ?? c.bilateral_load ?? 0), comp=Number(c.compensation_load_term ?? c.compensation_load ?? 0), sh=Number(c.shared_burden_term ?? c.shared_burden ?? 0); return `<tr><td>${esc(kneeLabel(side))}</td><td>${esc(c.coefficient_version||c.version||"BILATERAL_WEIGHT_V4_KL4_CEILING_20260615")}</td><td>${esc(b.toFixed(3))}</td><td>${esc(comp.toFixed(3))}</td><td>${esc(sh.toFixed(3))}</td></tr>`; }).join("");
  return `<div class="risk-weight-audit" id="riskWeightAudit"><h3>Bilateral endpoint weight audit</h3><p>Contralateral pain, WOMAC and KL are returned by <b>POST /api/v9/risk/predict</b>, not calculated for display in the browser. The retraining data strategy is paired-knee longitudinal data: baseline left/right KL, pain, WOMAC, BMI, strength, gait/fall and treatment exposure mapped to side-specific 24-96 month outcomes.</p><table class="compact"><thead><tr><th>Knee</th><th>Version</th><th>Contralateral load</th><th>Compensation load</th><th>Shared burden</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function riskEndpointBanner(sim){
  const status=state.riskEndpointStatus;
  const cls=status==="connected"?"green":status==="failed"?"red":"amber";
  const msg=status==="failed" ? state.riskEndpointError : status==="connected" ? "Endpoint response applied to the displayed risks." : "Waiting for backend endpoint response.";
  return `<div class="endpoint-status endpoint-${cls}" id="riskEndpointBanner"><div><b>Risk endpoint</b><span>${esc(sim.endpoint||"POST /api/v9/risk/predict")}</span></div><div><b>Status</b><span>${esc(status)}</span></div><div><b>Model source</b><span>${esc(sim.model_source||"backend endpoint pending")}</span></div><div><b>Request ID</b><span>${esc(sim.request_id||"pending")}</span></div><p>${esc(msg)}</p></div>`;
}
function lockedKlPanel(){
  return `<div class="locked-kl-panel"><h3>KL grade locked from KOM-Profile</h3><p>KL grade is an observed radiographic input. It is changed only by the KOM-Profile patient example/configuration. KOM-Rad documents image evidence, and KOM-Risk treats KL as read-only endpoint input.</p><div><span class="badge dark">Left KL ${state.riskInputs.left_kl}</span><span class="badge dark">Right KL ${state.riskInputs.right_kl}</span></div></div>`;
}
function risk(){ syncProfileDerived("risk-render"); const rs=state.content.risk, sim=currentRiskPrediction(); const current=rs.find(x=>x.id===state.selectedRisk)||rs[0]; pageLayout("KOM-Risk bilateral longitudinal risk prediction", "Risk is estimated by the backend endpoint for each knee with cross-knee coupling: pain, WOMAC and KL burden from one knee can change the other knee through activity reduction, load compensation and shared systemic factors. KL remains locked from KOM-Profile.", `${riskEndpointBanner(sim)}<div class="grid3 risk-cards">${rs.map(r=>`<div class="panel risk-card ${r.id===state.selectedRisk?'active':''}" data-risk="${r.id}" onclick="state.selectedRisk='${r.id}';risk()"><h3>${esc(r.name)}</h3><div class="riskbar"><i style="width:${riskPct(endpointMax(sim,r.id))}%"></i></div><p><b class="risk-value">${riskPct(endpointMax(sim,r.id))}%</b> max knee risk - ${esc(r.horizon)}</p><div class="bilateral-risk-grid"><span>Left ${riskPct(riskVal(sim,"left",r.id))}%</span><span>Right ${riskPct(riskVal(sim,"right",r.id))}%</span></div><p>${esc(r.definition)}</p><div class="risk-card-note-slot">${riskCardSemanticNote(sim,r.id)}</div>${r.drivers.map(x=>`<span class="badge">${esc(x)}</span>`).join("")}</div>`).join("")}</div><div class="grid2 stable-risk"><div class="panel"><h2>Scenario controls</h2><p class="muted">Each slider posts a new left/right scenario to the backend endpoint. Ipsilateral variables remain dominant, while contralateral pain/function contributes through endpoint-returned bilateral coupling terms.</p>${lockedKlPanel()}${riskSlider("bmi","BMI scenario",20,38,0.1)}${riskSlider("left_nrs","Left pain NRS scenario",0,10,1)}${riskSlider("right_nrs","Right pain NRS scenario",0,10,1)}${riskSlider("left_womac","Left WOMAC function scenario",0,68,1)}${riskSlider("right_womac","Right WOMAC function scenario",0,68,1)}</div><div class="panel"><h2 id="selectedRiskName">${esc(current.name)}</h2><p><b>Horizon:</b> ${esc(current.horizon)}<br><b>Event definition:</b> ${esc(current.definition)}</p><p id="riskModelNote"><b>Model:</b> ${esc(sim.model_source||"backend endpoint pending")}; endpoint ${esc(sim.endpoint||"POST /api/v9/risk/predict")}. The returned weight table is auditable; KL4 structural ceiling and severe-KL4 TKA floors are returned by the backend before retraining with paired-knee OAI labels.</p>${riskSideTable(sim,current.id)}${riskWeightAuditHtml(sim)}<p>${esc(current.meaning)}</p><div class="figure"><img src="/${current.figure}" alt="${esc(current.name)}"></div></div></div>`, `<h3>Interpretation boundary</h3><p>Risk output supports follow-up intensity, counseling and evidence retrieval. KL grade remains fixed unless the KOM-Profile patient configuration is changed.</p><button class="btn primary next-cta" onclick="go('rag')">Next: KOM-RAG</button>`); requestRiskPrediction("render"); }
function riskSlider(id,label,min,max,step){ return `<label class="risk-slider"><b>${esc(label)} <span id="riskLabel_${id}">${state.riskInputs[id]}</span></b><input type="range" min="${min}" max="${max}" step="${step}" value="${state.riskInputs[id]}" oninput="updateRiskInput('${id}', this.value)"></label>`; }
function updateRiskInput(id,value){
  state.riskInputs[id]=Number(value);
  if(id==="bmi") state.profile.bmi=String(value);
  if(id==="left_nrs") state.profile.left_nrs=String(value);
  if(id==="right_nrs") state.profile.right_nrs=String(value);
  if(id==="left_womac") state.profile.left_womac_function=String(value);
  if(id==="right_womac") state.profile.right_womac_function=String(value);
  state.profile.nrs=String(Math.max(sidePain("left"),sidePain("right")));
  state.profile.womac_function=String(Math.max(sideWomac("left"),sideWomac("right")));
  state.profileResult=null;
  state.rxFinalized=false;
  syncProfileDerived("risk-slider");
  state.riskPrediction=null;
  state.riskLastSignature="";
  state.riskEndpointStatus="pending";
  const lab=$("#riskLabel_"+id); if(lab) lab.textContent=value;
  updateRiskDisplay();
  scheduleRiskPrediction();
  scheduleProfileSave();
}
function scheduleRiskPrediction(){
  clearTimeout(state.riskEndpointTimer);
  state.riskEndpointTimer=setTimeout(()=>requestRiskPrediction("scenario"),140);
}
async function requestRiskPrediction(reason="render", force=false){
  const sig=riskInputSignature();
  if(!force && state.riskPrediction && state.riskLastSignature===sig && state.riskEndpointStatus==="connected"){
    if(state.page==="risk") updateRiskDisplay(state.riskPrediction);
    return state.riskPrediction;
  }
  const seq=++state.riskRequestSeq;
  state.riskEndpointStatus="pending";
  state.riskEndpointError="";
  if(state.page==="risk") updateRiskDisplay(currentRiskPrediction());
  try{
    const data=await api("/api/v9/risk/predict",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(riskPayload())});
    if(seq!==state.riskRequestSeq) return data;
    state.riskPrediction=data;
    state.riskLastSignature=sig;
    state.riskEndpointStatus="connected";
    state.riskEndpointError="";
    if(state.page==="risk") updateRiskDisplay(data);
    return data;
  }catch(e){
    if(seq!==state.riskRequestSeq) return null;
    state.riskEndpointStatus="failed";
    state.riskEndpointError=e.message || String(e);
    if(state.page==="risk") updateRiskDisplay(currentRiskPrediction());
    return null;
  }
}
function updateRiskDisplay(data=null){
  const sim=data || currentRiskPrediction();
  const banner=$("#riskEndpointBanner");
  if(banner) banner.outerHTML=riskEndpointBanner(sim);
  state.content.risk.forEach(r=>{
    const card=document.querySelector(`.risk-card[data-risk="${r.id}"]`);
    if(card){
      const max=endpointMax(sim,r.id);
      card.querySelector(".riskbar i").style.width=riskPct(max)+"%";
      card.querySelector(".risk-value").textContent=riskPct(max)+"%";
      const bilateral=card.querySelector(".bilateral-risk-grid");
      if(bilateral) bilateral.innerHTML=`<span>Left ${riskPct(riskVal(sim,"left",r.id))}%</span><span>Right ${riskPct(riskVal(sim,"right",r.id))}%</span>`;
      const noteSlot=card.querySelector(".risk-card-note-slot");
      if(noteSlot) noteSlot.innerHTML=riskCardSemanticNote(sim,r.id);
    }
  });
  const table=$(".risk-side-table");
  if(table) table.outerHTML=riskSideTable(sim,state.selectedRisk);
  const audit=$("#riskWeightAudit");
  if(audit) audit.outerHTML=riskWeightAuditHtml(sim);
  const note=$("#riskModelNote");
  if(note) note.innerHTML=`<b>Model:</b> ${esc(sim.model_source||"backend endpoint pending")}; endpoint ${esc(sim.endpoint||"POST /api/v9/risk/predict")}. The returned weight table is auditable; KL4 structural ceiling and severe-KL4 TKA floors are returned by the backend before retraining with paired-knee OAI labels.`;
}

function levelCode(e){ return String(e.level||e.Evidence_Level||e.full_evidence_level||"L7").match(/L[1-7]/)?.[0] || "L7"; }
function layerNameFor(level){
  return ({L1:"Guideline anchor",L2:"Meta-analysis / synthesis",L3:"RCT / clinical study",L4:"Observational patient-fit context",L5:"Implementation and clinical context",L6:"Protocol or mechanism support",L7:"Background context only"})[level]||"Evidence unit";
}
function directnessFor(level){ return ["L1","L2","L3"].includes(level) ? "Direct or direct-support evidence" : level==="L4" ? "Risk / patient-fit context" : "Context / support only"; }
function prescriptionUseFor(row, level){
  return row.Prescription_Use || row.prescription_use || (["L1","L2","L3"].includes(level) ? "Can support prescription decisions after patient-fit and safety checks." : "Shown for context, implementation or background; not used as the sole direct prescription anchor.");
}
function extractSampleSize(text){
  const s=String(text||"");
  const patterns=[/sample size:\s*([0-9,]+)/i,/\b(?:n|N)\s*=\s*([0-9,]+)/,/([0-9,]+)\s+participants/i,/([0-9,]+)\s+adults/i,/([0-9,]+)\s+patients/i,/([0-9,]+)\s+randomi[sz]ed controlled trials/i,/([0-9,]+)\s+RCTs/i,/([0-9,]+)\s+studies/i];
  const m=patterns.map(p=>s.match(p)).find(Boolean);
  return m ? m[1].replace(/,/g,"") : "not reported in local metadata";
}
function extractPopulationFingerprint(pop){
  const s=String(pop||"");
  const age=s.match(/age:\s*([^;]+)/i)?.[1]||"age not reported";
  const sex=s.match(/sex:\s*([^;]+)/i)?.[1]||"sex not reported";
  const bmi=s.match(/BMI:\s*([^;]+)/i)?.[1]||"BMI not reported";
  if(/participants|adults|patients|randomi[sz]ed|RCTs|studies/i.test(s) && !/age:\s*/i.test(s)) return `${s}; sample size ${extractSampleSize(s)}`;
  return `${age}; ${sex}; ${bmi}; sample size ${extractSampleSize(s)}`;
}
function resultDirectionText(e){
  const s=`${e?.outcomes||e?.O_Outcomes||""} ${e?.effect||e?.Effect_Summary||""} ${e?.summary||""}`.toLowerCase();
  const positive=/positive|improv|reduce|benefit|superior|effective/.test(s);
  const mixed=/mixed|null|no superiority|no difference|inconsistent|no clear/.test(s);
  if(/negative|harm|worse|adverse/.test(s)) return "negative or safety-limited signal";
  if(positive && mixed) return "positive primary signal with mixed or safety-limited secondary findings";
  if(mixed) return "mixed or neutral signal";
  if(positive) return "positive signal";
  return "direction not explicit in local metadata";
}
function numericEffectStatus(e){
  const s=`${e?.effect||e?.Effect_Summary||""} ${e?.outcomes||e?.O_Outcomes||""}`;
  if(/Quantitative effect status:/i.test(s)) return s;
  const hasEffect=/\b(MD|SMD|RR|OR|HR|CI|%|p\s*[<=>]|WOMAC|VAS|KOOS)\b/i.test(s) && /\d/.test(s);
  if(hasEffect) return s;
  return "Exact effect size is not present in this local metadata row; do not claim magnitude without source-level verification.";
}
function evidenceQuantHtml(e){
  const items=[
    ["Population fingerprint", e.population_fingerprint||extractPopulationFingerprint(e.population)],
    ["Sample size", extractSampleSize(e.population)],
    ["Result direction", e.result_direction||resultDirectionText(e)],
    ["Quantitative effect status", e.quantitative_effect_status||numericEffectStatus(e)],
    ["Extraction QA", e.extraction_qa||"not recorded"],
    ["Evidence rank score", e.rank_score||"not ranked"],
    ["Direct prescription use", e.prescription_use||"not specified"]
  ];
  return `<div class="evidence-quant-grid">${items.map(r=>`<div><b>${esc(r[0])}</b><span>${esc(r[1])}</span></div>`).join("")}</div>`;
}
function normalizeEvidenceRow(row, rank=1){
  const level=levelCode(row);
  const year=row.year||row.publication_year||row.Year||"year pending";
  const effect=row.Effect_Summary||row.effect||row.summary||"Exact effect size is not present in this local metadata row; inspect the source before quantitative citation.";
  const outcomes=row.O_Outcomes||row.outcomes||"Pain, function, walking tolerance, treatment adherence, adverse events or implementation outcomes as recorded by the source.";
  const summary=row.summary||row.Effect_Summary||row.O_Outcomes||row.Prescription_Use||"Evidence summary is available in the source-linked Evidence Unit.";
  const levelWeight={L1:1,L2:.9,L3:.82,L4:.62,L5:.5,L6:.4,L7:.32}[level]||.3;
  const recencyWeight=Number(year)>=2022?.12:Number(year)>=2019?.07:0;
  const rankScore=Math.max(.1,Math.min(.99,levelWeight+recencyWeight-rank*.012));
  return {
    EU_ID: row.EU_ID,
    title: row.Title||row.title||row.EU_ID,
    level,
    layer: row.layer||layerNameFor(level),
    year,
    summary,
    fit: row.patient_fit||row.why_selected||ragEvidenceReason({level,title:row.Title||row.title||"",Prescription_Use:row.Prescription_Use}),
    validation: row.validation||`Patient-fit check recorded; ranked within ${state.chain.replaceAll("_"," ")} using evidence level, recency, domain fit and safety relevance.`,
    directness: row.directness||directnessFor(level),
    source_link: row.source_link||row.Source_Link||"",
    database_domain: row.Agent_Database||row.database_domain||state.chain,
    full_evidence_level: row.full_evidence_level||row.Evidence_Level||level,
    population: row.Population_Fingerprint||row.P_Population||row.population||"Adults with knee osteoarthritis or mixed hip/knee osteoarthritis including knee OA where recorded.",
    population_fingerprint: row.Population_Fingerprint||row.population_fingerprint||row.P_Population||row.population,
    intervention: row.Intervention_Detail||row.I_Intervention||row.intervention||"Intervention, exposure or management strategy described in the title/source.",
    intervention_detail: row.Intervention_Detail||row.intervention_detail||row.I_Intervention||row.intervention,
    comparator: row.Comparator_Detail||row.C_Comparator||row.comparator||"Comparator or usual-care context not separately recorded in this local unit.",
    comparator_detail: row.Comparator_Detail||row.comparator_detail||row.C_Comparator||row.comparator,
    outcomes,
    effect: row.Quantitative_Effect_Status||numericEffectStatus({effect,outcomes,summary}),
    result_direction: row.Result_Direction||row.result_direction||resultDirectionText({outcomes,effect,summary}),
    quantitative_effect_status: row.Quantitative_Effect_Status||row.quantitative_effect_status||numericEffectStatus({effect,outcomes,summary}),
    extraction_qa: row.Evidence_Extraction_QA||row.extraction_qa||row.source_status,
    source_pmid: row.Source_PMID||row.source_pmid||"",
    source_abstract: row.Source_Abstract||row.source_abstract||"",
    safety: row.Safety_or_Contraindication_Note||row.safety||"No additional safety note recorded in this local unit; clinician review still applies.",
    prescription_use: prescriptionUseFor(row, level),
    traceability: row.Traceability_Status||row.traceability||"source-linked",
    rank_score: rankScore.toFixed(2)
  };
}
function staticEvidenceCards(ch){ const cards=[]; ch.layers.forEach(layer=>layer.items.forEach((item,i)=>{ cards.push(normalizeEvidenceRow({layer:layer.name,...item},i+1)); })); return cards; }
function packKey(){ return [state.chain,state.selectedCase,state.riskInputs.left_kl,state.riskInputs.right_kl,state.riskInputs.left_nrs,state.riskInputs.right_nrs,state.riskInputs.left_womac,state.riskInputs.right_womac,state.riskInputs.bmi,medicationGateComplete()?"gate-complete":"gate-open"].join("|"); }
function selectRankedPack(rows, fallbackCards){
  const targets={L1:3,L2:3,L3:3,L4:2,L5:2,L6:1,L7:1};
  const seen=new Set(), out=[];
  const all=[...fallbackCards,...rows].filter(x=>x&&x.EU_ID).map((x,i)=>normalizeEvidenceRow(x,i+1));
  ["L1","L2","L3","L4","L5","L6","L7"].forEach(level=>{
    const group=all.filter(x=>levelCode(x)===level && !seen.has(x.EU_ID))
      .sort((a,b)=>Number(b.rank_score||0)-Number(a.rank_score||0)||String(b.year).localeCompare(String(a.year)));
    let taken=0;
    for(const x of group){
      if(seen.has(x.EU_ID)) continue;
      seen.add(x.EU_ID);
      out.push(x);
      taken++;
      if(taken>=targets[level]) break;
    }
  });
  return out.slice(0,15);
}
async function ensureCasePack(ch){
  const key=packKey();
  if(state.casePacks[key]||state.packLoading[key]) return;
  state.packLoading[key]=true;
  try{
    const data=await api("/api/v10/evidence/patient-fit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q:caseQueryText(),domain:state.chain,profile:profileContext(),limit:42})});
    const rows=data.rows||[];
    state.casePacks[key]=selectRankedPack(rows, staticEvidenceCards(ch));
    if(route()==="rag" && state.ragView==="case") rag();
  }catch(e){
    state.casePacks[key]=staticEvidenceCards(ch);
  }finally{
    state.packLoading[key]=false;
  }
}
function evidenceCards(ch){
  const key=packKey();
  const cards=state.casePacks[key]||staticEvidenceCards(ch);
  const filtered=cards.filter(item=>state.level==="ALL"||levelCode(item)===state.level);
  return filtered;
}
function ragEvidenceReason(item){ const q=caseFromProfile(); if(String(item.level).startsWith("L1")) return "Current guideline anchor for boundary and safety."; if(state.chain==="pharmacologic_or_injection" && !medicationGateComplete()) return "Medication safety gate is active, so safety evidence is prioritized."; if(state.chain==="nutrition_weight_management" && num(state.profile.bmi,0)>=27) return "BMI and muscle-preservation needs prioritize nutrition evidence."; if(state.chain==="exercise_rehabilitation" && /resistance|balance|exercise|fall|cycling|aerobic/i.test(item.title||"")) return "Strength, aerobic modality, balance, fall-risk or function signals prioritize rehabilitation detail."; if(state.chain==="surgery_or_escalation" && q.highBurden) return "High burden and locked KL grade support referral-boundary evidence."; return "Selected for domain fit, evidence level and patient relevance."; }
function caseQueryText(){
  const p=state.profile;
  const terms=[state.chain.replaceAll("_"," "),`left knee KL ${state.riskInputs.left_kl} pain NRS ${state.riskInputs.left_nrs} WOMAC ${state.riskInputs.left_womac}`,`right knee KL ${state.riskInputs.right_kl} pain NRS ${state.riskInputs.right_nrs} WOMAC ${state.riskInputs.right_womac}`,`BMI ${state.riskInputs.bmi}`];
  if(!medicationGateComplete()) terms.push("renal GI anticoagulant cardiovascular medication safety");
  if(/fall|balance|tug|stance/i.test(String(p.balance||""))) terms.push("fall prevention balance training");
  if(num(p.bmi,0)>=27) terms.push("weight management muscle preservation");
  if(num(p.bmi,0)>=30) terms.push("semaglutide obesity knee osteoarthritis STEP 9");
  return terms.join(" ");
}
async function runCaseQuery(){
  const box=$("#ragQuery");
  const query=box?.value||caseQueryText();
  const data=await api("/api/v10/evidence/patient-fit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q:query,domain:state.chain,profile:profileContext(),limit:40})});
  state.evidenceDb=data.rows||[];
  state.evidenceVisible=state.evidencePageSize;
  state.lastPatientFit=data;
  state.ragView="db";
  rag();
  toast(`${data.success?'Patient-fit retrieval passed':'Patient-fit retrieval needs review'}: ${state.evidenceDb.length} units, ${data.retrieval_rounds?.length||0} retrieval rounds`);
}
function rag(){
  syncProfileDerived("rag-render");
  const ev=state.content.evidence;
  const ch=ev.chains[state.chain]||Object.values(ev.chains)[0];
  const cards=evidenceCards(ch);
  ensureCasePack(ch);
  const selected=cards.find(x=>x.EU_ID===state.selectedEvidence)||cards[0];
  const specialtyTabs=Object.entries(ev.chains).map(([k,v])=>`<button class="${state.chain===k?'active':''}" onclick="state.manualChain=true;state.chain='${k}';state.level='ALL';state.ragView='case';rag()">${esc(v.title.replace(' evidence chain',''))}</button>`).join("");
  const levelTabs=`<button class="${state.level==='ALL'?'active':''}" onclick="state.level='ALL';rag()">ALL</button>${ev.level_definitions.map(l=>`<button class="${state.level===l[0]?'active':''}" onclick="state.level='${l[0]}';state.ragView='case';rag()">${l[0]}</button>`).join("")}`;
  const cardList=cards.map(x=>`<div class="evidence-card ${selected&&selected.EU_ID===x.EU_ID?'active':''}" data-evidence="${esc(x.EU_ID)}" onclick="selectEvidence('${esc(x.EU_ID)}')"><b>${esc(x.EU_ID)} - ${esc(x.title)}</b><p>${esc(x.summary)}</p><p><b>Why selected:</b> ${esc(x.fit)}</p><span class="badge">${esc(x.layer)}</span><span class="badge">${esc(x.level)}</span><span class="badge amber">${esc(x.year)}</span></div>`).join("");
  pageLayout("KOM-RAG evidence graph and evidence chain", "The patient node and evidence nodes are interactive. Changing KOM-Profile changes specialty routing, patient-fit reasons and catalog retrieval results.",
  `<div class="graph-layout"><div class="panel rag-main-panel"><div class="graph-toolbar"><button class="btn ${state.ragView==='case'?'primary':''}" onclick="state.ragView='case';rag()">Case evidence chain</button><button class="btn ${state.ragView==='db'?'primary':''}" onclick="showCatalog()">Evidence catalog</button><button class="btn ${state.ragView==='figure'?'primary':''}" onclick="state.ragView='figure';rag()">Full graph figure</button></div><div class="rag-query-strip"><input id="ragQuery" value="${esc(caseQueryText())}" aria-label="Patient-fit evidence query"><button class="btn primary" onclick="runCaseQuery()">Run patient-fit retrieval</button><span class="badge">Case pack ${cards.length} ranked nodes across ${[...new Set(cards.map(x=>x.level))].join(', ')}</span></div><div id="evidenceGraphBox" class="dynamic-graph">${state.ragView==='db'?renderEvidenceDb():state.ragView==='figure'?staticGraphFigure():renderEvidenceSvg(cards,ch)}</div></div><div class="panel evidence-chain-panel"><div class="evidence-chain-sticky"><h2>Specialty evidence chain</h2><div class="tabs">${specialtyTabs}</div><p>${esc(ch.clinical_question)}</p><div class="filter-row">${levelTabs}</div></div><div class="evidence-card-list">${cardList}</div></div></div><div class="panel evidence-detail-panel">${evidenceDetailHtml(selected)}</div><div class="panel hierarchy-panel"><h2>L1-L7 evidence hierarchy</h2><table><thead><tr><th>Level</th><th>Meaning</th><th>Prescription use</th></tr></thead><tbody>${ev.level_definitions.map(r=>`<tr><td><b>${esc(r[0])}</b></td><td>${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join("")}</tbody></table></div>${evidenceOverlayHtml()}`,
  `<h3>Evidence database</h3><p><span class="badge">Evidence Units ${ev.count}</span><span class="badge">Graph nodes 40</span><span class="badge">Edges 68</span></p><h3>Profile-driven focus</h3><p>${esc(state.chain.replaceAll("_"," "))}</p><h3>Level distribution</h3><p>${Object.entries(ev.distribution.levels).sort().map(([k,v])=>`<span class="badge">${esc(k)} ${v}</span>`).join("")}</p>`);
}
function selectEvidence(id){ state.selectedEvidence=id; state.evidenceOverlay=id; rag(); }
function closeEvidenceOverlay(){ state.evidenceOverlay=null; rag(); }
function normalizeEvidenceDetailRow(e){
  if(!e) return null;
  return {
    EU_ID:e.EU_ID,
    title:e.title||e.Title,
    summary:e.summary||e.Effect_Summary,
    layer:e.layer||e.Agent_Database,
    level:e.level||e.Evidence_Level,
    year:e.year,
    rank_score:e.rank_score,
    directness:e.directness||e.KOA_Relevance_Grade,
    fit:e.fit||ragEvidenceReason({level:e.Evidence_Level,title:e.Title}),
    population:e.population||e.Population_Fingerprint||e.P_Population,
    population_fingerprint:e.population_fingerprint||e.Population_Fingerprint||e.P_Population,
    intervention:e.intervention||e.Intervention_Detail||e.I_Intervention,
    intervention_detail:e.intervention_detail||e.Intervention_Detail||e.I_Intervention,
    comparator:e.comparator||e.Comparator_Detail||e.C_Comparator,
    comparator_detail:e.comparator_detail||e.Comparator_Detail||e.C_Comparator,
    outcomes:e.outcomes||e.O_Outcomes,
    effect:e.effect||e.Quantitative_Effect_Status||e.Effect_Summary,
    result_direction:e.result_direction||e.Result_Direction,
    quantitative_effect_status:e.quantitative_effect_status||e.Quantitative_Effect_Status,
    extraction_qa:e.extraction_qa||e.Evidence_Extraction_QA,
    source_pmid:e.source_pmid||e.Source_PMID,
    source_abstract:e.source_abstract||e.Source_Abstract,
    safety:e.safety||e.Safety_or_Contraindication_Note,
    prescription_use:e.prescription_use||e.Prescription_Use,
    traceability:e.traceability||e.Traceability_Status||e.trace_id,
    validation:e.validation||e.Evidence_Extraction_QA||e.source_status||"Local evidence unit retained in the package.",
    source_link:e.source_link
  };
}
function evidenceById(id){
  if(!id) return null;
  const ev=state.content.evidence;
  for(const [key,ch] of Object.entries(ev.chains||{})){
    const cards=key===state.chain ? (state.casePacks[packKey()]||staticEvidenceCards(ch)) : staticEvidenceCards(ch);
    const found=(cards||[]).find(x=>x.EU_ID===id);
    if(found) return normalizeEvidenceDetailRow(found);
  }
  const db=(state.evidenceDb||[]).find(x=>x.EU_ID===id);
  return normalizeEvidenceDetailRow(db);
}
function evidenceOverlayHtml(){
  const e=evidenceById(state.evidenceOverlay);
  if(!e) return "";
  return `<div class="evidence-float" role="dialog" aria-modal="true" onclick="if(event.target===this)closeEvidenceOverlay()"><div class="evidence-float-card"><button class="modal-close" onclick="closeEvidenceOverlay()" aria-label="Close evidence detail">x</button>${evidenceDetailHtml(e)}</div></div>`;
}
function evidenceDetailHtml(e){
  e=normalizeEvidenceDetailRow(e);
  if(!e) return "<h2>Selected evidence</h2><p>Select an evidence node to inspect why it was retrieved.</p>";
  const rows=[
    ["Population", e.population],
    ["Intervention / exposure", e.intervention_detail||e.intervention],
    ["Comparator / context", e.comparator_detail||e.comparator],
    ["Observed outcomes", e.outcomes],
    ["Quantitative result / effect", e.quantitative_effect_status||e.effect],
    ["Source abstract excerpt", e.source_abstract ? e.source_abstract.slice(0,900) : "Abstract not available in this local Evidence Unit."],
    ["Safety note", e.safety],
    ["Prescription use", e.prescription_use],
    ["Traceability", [e.traceability, e.source_pmid?`PMID ${e.source_pmid}`:""].filter(Boolean).join("; ")]
  ];
  return `<h2>Selected evidence</h2><p><b>${esc(e.EU_ID)}</b> - ${esc(e.title)}</p><p><b>Layer:</b> ${esc(e.layer)} <span class="badge">${esc(e.level)}</span> <span class="badge amber">${esc(e.year)}</span> <span class="badge ${String(e.directness||'').includes('Direct')?'green':'amber'}">${esc(e.directness||'Use recorded')}</span> <span class="badge">rank score ${esc(e.rank_score||'not recorded')}</span></p><p><b>Why this evidence fits this patient:</b> ${esc(e.fit)}</p><h3>Population and quantified result extraction</h3>${evidenceQuantHtml(e)}<div class="evidence-pico-grid">${rows.map(r=>`<div><b>${esc(r[0])}</b><span>${esc(r[1]||'Not recorded in this local Evidence Unit.')}</span></div>`).join("")}</div><p><b>Validation note:</b> ${esc(e.validation)}</p>${e.source_link?`<p><b>Source:</b> <a href="${esc(e.source_link)}" target="_blank">${esc(e.source_link)}</a></p>`:""}`;
}
function renderEvidenceSvg(cards,ch){
  const levels=["L1","L2","L3","L4","L5","L6","L7"];
  const grouped=Object.fromEntries(levels.map(level=>[level,cards.filter(c=>levelCode(c)===level)]));
  return `<div class="evidence-pack-board"><div class="pack-intro"><div><h2>${esc(ch.title)}</h2><p>L1-L3 are direct anchors or direct-support evidence. L4-L7 are retained for patient-fit context, implementation limits, mechanism or background.</p></div><div class="patient-token"><b>Patient</b><span>${esc(currentCaseTitle())}</span><span>Left KL ${state.riskInputs.left_kl}, NRS ${state.riskInputs.left_nrs}, WOMAC ${state.riskInputs.left_womac}</span><span>Right KL ${state.riskInputs.right_kl}, NRS ${state.riskInputs.right_nrs}, WOMAC ${state.riskInputs.right_womac}</span></div></div><div class="level-lanes">${levels.map(level=>`<section class="level-lane level-${level.toLowerCase()}"><h3>${level}<span>${grouped[level].length}</span></h3>${grouped[level].map((e,i)=>`<button class="evidence-node ${state.selectedEvidence===e.EU_ID?'active':''}" data-evidence="${esc(e.EU_ID)}" onclick="selectEvidence('${esc(e.EU_ID)}')"><b>${esc(e.EU_ID)}</b><strong>${esc(e.title).slice(0,88)}</strong><small>${esc(e.year)} | score ${esc(e.rank_score||'--')}</small><em>${esc(e.directness)}</em></button>`).join("")||'<p class="empty-level">No matching unit in this level for the current domain.</p>'}</section>`).join("")}</div></div>`;
}
function staticGraphFigure(){
  const ev=state.content.evidence;
  const ch=ev.chains[state.chain]||Object.values(ev.chains)[0];
  const fallback=staticEvidenceCards(ch);
  const source=(state.evidenceDb||[]).length ? selectRankedPack(state.evidenceDb, fallback) : evidenceCards(ch);
  const cards=selectRankedPack(source, fallback);
  const levels=["L1","L2","L3","L4","L5","L6","L7"];
  const currentCounts=Object.fromEntries(levels.map(l=>[l,cards.filter(x=>levelCode(x)===l).length]));
  const domainLabels={
    exercise_rehabilitation:"Exercise",
    nutrition_weight_management:"Nutrition",
    pharmacologic_or_injection:"Medication / injection",
    psychology_behavior_selfmanagement:"Psychology",
    surgery_or_escalation:"Orthopedics"
  };
  const visibleNodes=cards.slice(0,8);
  const nodes=visibleNodes.map((e,i)=>{
    const top=18+i*88;
    return `<button class="network-node network-evidence level-${levelCode(e).toLowerCase()}" style="right:22px;top:${top}px" data-evidence="${esc(e.EU_ID)}"><span>${esc(levelCode(e))}</span><b>${esc(e.EU_ID)}</b><small>${esc(e.title).slice(0,72)}</small></button>`;
  }).join("");
  const edgeLines=visibleNodes.map((e,i)=>{
    const x2=855, y2=55+i*88;
    const color=levelCode(e)==="L1"?"#426a47":levelCode(e)==="L2"?"#245f73":levelCode(e)==="L3"?"#8b5f27":"#7890a2";
    return `<path d="M600 310 C660 250,690 ${y2},${x2} ${y2}" stroke="${color}" stroke-width="${Math.max(2,5-i*.25)}" opacity=".42" fill="none"/>`;
  }).join("");
  const sourceLabel=(state.evidenceDb||[]).length ? `Current catalog/query result: ${state.evidenceDb.length} loaded units${state.evidenceFilters.q?` for "${state.evidenceFilters.q}"`:""}.` : `Current profile-ranked case pack: ${cards.length} visible units.`;
  return `<div class="interactive-network"><div class="network-top"><div><h2>KOM-RAG interactive evidence network</h2><p>${esc(sourceLabel)} The graph now samples by L1-L7 level, so guidelines do not hide meta-analysis, trial, implementation or background units.</p></div><div class="network-counts">${levels.map(l=>`<span>${l}<b>${currentCounts[l]||0}</b></span>`).join("")}</div></div><div class="network-stage"><svg class="network-lines" viewBox="0 0 1120 780" aria-hidden="true"><defs><linearGradient id="networkFlow" x1="0" x2="1"><stop offset="0" stop-color="#245f73"/><stop offset="1" stop-color="#4f7b55"/></linearGradient></defs><path d="M155 310 C255 180,340 170,450 210" stroke="url(#networkFlow)" stroke-width="6" opacity=".35" fill="none"/><path d="M155 310 C255 435,340 455,450 410" stroke="url(#networkFlow)" stroke-width="6" opacity=".35" fill="none"/><path d="M500 210 C540 235,560 270,600 310" stroke="#245f73" stroke-width="4" opacity=".3" fill="none"/><path d="M500 410 C540 385,560 350,600 310" stroke="#245f73" stroke-width="4" opacity=".3" fill="none"/><path d="M600 310 C650 290,690 300,760 310" stroke="#172033" stroke-width="4" opacity=".16" fill="none"/>${edgeLines}</svg><div class="network-node network-patient" style="left:3%;top:38%"><span>Patient</span><b>${esc(currentCaseTitle())}</b><small>BMI ${esc(state.riskInputs.bmi)}; ${esc(primaryKnee()==='left'?'left':'right')} priority</small></div><div class="network-node network-knee" style="left:24%;top:19%"><span>Left knee</span><b>KL ${state.riskInputs.left_kl} / NRS ${state.riskInputs.left_nrs}</b><small>WOMAC ${state.riskInputs.left_womac}</small></div><div class="network-node network-knee" style="left:24%;top:61%"><span>Right knee</span><b>KL ${state.riskInputs.right_kl} / NRS ${state.riskInputs.right_nrs}</b><small>WOMAC ${state.riskInputs.right_womac}</small></div><div class="network-node network-router" style="left:42%;top:38%"><span>Evidence router</span><b>${esc(domainLabels[state.chain]||state.chain.replaceAll("_"," "))}</b><small>${esc(medicationGateComplete()?"medication gate complete":"safety gates active")}</small></div>${nodes}</div><div class="network-footer"><div><b>Catalog scale</b><span>${esc(ev.count)} local Evidence Units, loaded in pages to avoid browser freezes.</span></div><div><b>Interaction</b><span>Click any evidence node to open the same detailed unit card used by the evidence catalog.</span></div><div><b>Audit boundary</b><span>Level color shows the current evidence tier; it is not an automatic prescription claim.</span></div></div></div>`;
}
async function showCatalog(){ state.ragView='db'; if(!state.evidenceDb.length) await loadEvidenceDbFromControls(false); rag(); }
async function loadEvidenceDbFromControls(renderAfter=true){ const rawQ=$("#evidenceSearch")?.value||state.evidenceFilters.q||""; const rawLevel=$("#evidenceLevel")?.value||state.evidenceFilters.level||""; const rawDomain=$("#evidenceDomain")?.value||state.evidenceFilters.domain||""; const limit=Number($("#evidenceLimit")?.value||state.evidenceFilters.limit||600); state.evidenceFilters={q:rawQ,level:rawLevel,domain:rawDomain,limit}; const q=encodeURIComponent(rawQ); const level=encodeURIComponent(rawLevel); const domain=encodeURIComponent(rawDomain); const data=await api(`/api/v10/evidence/units?limit=${limit}&q=${q}&level=${level}&domain=${domain}`); state.evidenceDb=data.rows||[]; state.evidenceVisible=state.evidencePageSize; state.lastPatientFit=null; state.evidenceDbMeta=data; if(renderAfter) rag(); }
function increaseEvidenceVisible(){ state.evidenceVisible=Math.min((state.evidenceDb||[]).length,state.evidenceVisible+state.evidencePageSize); rag(); }
function patientFitSummary(){ const r=state.lastPatientFit; if(!r) return ""; return `<div class="patient-fit-summary ${r.success?'pass':'hold'}"><b>Patient-fit retrieval ${r.success?'passed':'needs review'}</b><p>${esc(r.success_rule)}</p><div class="retrieval-rounds">${(r.retrieval_rounds||[]).map(x=>`<span class="badge">${esc('Round '+x.round+': '+x.strategy+' -> '+x.retrieved+' new')}</span>`).join("")}</div><p><b>Levels found:</b> ${esc((r.levels_found||[]).join(', '))}</p></div>`; }
function renderEvidenceDb(){
  const rows=(state.evidenceDb||[]).slice(0,state.evidenceVisible);
  const meta=state.evidenceDbMeta||{};
  const f=state.evidenceFilters;
  const exportHref=`/api/v10/evidence/units?limit=5000&q=${encodeURIComponent(f.q||"")}&level=${encodeURIComponent(f.level||"")}&domain=${encodeURIComponent(f.domain||"")}`;
  return `<div class="evidence-db"><div class="db-controls"><input id="evidenceSearch" value="${esc(f.q||"")}" placeholder="Search OA, semaglutide, PRP, cycling, CBT, surgery..." onkeydown="if(event.key==='Enter')loadEvidenceDbFromControls()"><select id="evidenceLevel"><option value="">All levels</option>${["L1","L2","L3","L4","L5","L6","L7"].map(l=>`<option ${f.level===l?'selected':''}>${l}</option>`).join("")}</select><select id="evidenceDomain"><option value="">All domains</option>${["exercise_rehabilitation","nutrition_weight_management","pharmacologic_or_injection","psychology_behavior_selfmanagement","surgery_or_escalation"].map(d=>`<option ${f.domain===d?'selected':''}>${d}</option>`).join("")}</select><select id="evidenceLimit"><option value="600" ${Number(f.limit)===600?'selected':''}>Load 600</option><option value="1200" ${Number(f.limit)===1200?'selected':''}>Load 1200</option><option value="5000" ${Number(f.limit)===5000?'selected':''}>Load all metadata</option></select><button class="btn primary" onclick="loadEvidenceDbFromControls()">Search catalog</button><a class="btn" href="${esc(exportHref)}" target="_blank">Export JSON</a></div>${patientFitSummary()}<p class="muted">Rendering ${rows.length} of ${state.evidenceDb.length} loaded Evidence Units${meta.total_matches?` (${meta.total_matches} matching in database)`:''}. Use Show more to avoid browser freezing; Export JSON returns the full metadata without adding every row to the page.</p><div class="db-list">${rows.map(e=>`<details class="db-row"><summary><b>${esc(e.EU_ID)}</b> - ${esc(e.Title).slice(0,120)} <span class="badge">${esc(e.Evidence_Level)}</span><span class="badge amber">${esc(e.year||'year pending')}</span></summary><div class="db-detail"><p><b>Domain:</b> ${esc(e.Agent_Database)}</p><p><b>Population fingerprint:</b> ${esc(e.Population_Fingerprint||e.P_Population)}</p><p><b>Intervention detail:</b> ${esc(e.Intervention_Detail||e.I_Intervention)}</p><p><b>Comparator/context:</b> ${esc(e.Comparator_Detail||e.C_Comparator)}</p><p><b>Result direction:</b> ${esc(e.Result_Direction||"not recorded")}</p><p><b>Outcomes:</b> ${esc(e.O_Outcomes)}</p><p><b>Quantitative effect status:</b> ${esc(e.Quantitative_Effect_Status||e.Effect_Summary||"not recorded")}</p><p><b>Extraction QA:</b> ${esc(e.Evidence_Extraction_QA||e.source_status||"not recorded")}</p><p><b>Safety:</b> ${esc(e.Safety_or_Contraindication_Note)}</p><p><b>Prescription use:</b> ${esc(e.Prescription_Use)}</p><p><b>PMID:</b> ${esc(e.Source_PMID||"not resolved")} <b>Source:</b> ${e.source_link?`<a href="${esc(e.source_link)}" target="_blank">${esc(e.source_link)}</a>`:'not recorded'}</p><button class="btn" data-evidence="${esc(e.EU_ID)}">Open floating detail</button></div></details>`).join("")}</div>${state.evidenceVisible<state.evidenceDb.length?`<div class="db-more"><button class="btn primary" onclick="increaseEvidenceVisible()">Show ${Math.min(state.evidencePageSize,state.evidenceDb.length-state.evidenceVisible)} more</button></div>`:""}</div>`;
}

function eligibilityHtml(agent){ const eligible = num(state.profile.left_kl,0)>0 && num(state.profile.right_kl,0)>0 && Math.max(sidePain("left"),sidePain("right"))>=0 && /knee/i.test(String(state.profile.target_side||"Both knees")); return `<div class="eligibility ${eligible?'pass':'hold'}"><b>Bilateral knee OA information check:</b> ${eligible?'Eligible for specialty processing':'Insufficient bilateral knee OA context'}<br><span>${eligible?'Left and right KL grades plus side-specific symptom/function anchors are present before this specialty prescription is shown.':'Complete left/right KL grade and symptom/function anchors before specialty prescription.'}</span></div>`; }
function mdt(){ syncProfileDerived("mdt-render"); const agents=state.content.agents; const current=agents.find(a=>a.id===state.agent)||agents[0]; pageLayout("KOM-MDT specialty treatment board", "Each specialty agent first checks whether the input is an eligible knee OA profile, then uses the domain-specific evidence chain to produce a prescription, reasoning and safety boundaries.", `<div class="grid5">${agents.map(a=>`<div class="agent-card ${state.agent===a.id?'active':''}" onclick="state.agent='${a.id}';mdt()"><h3>${esc(a.name)}</h3><p>${esc(a.specialty_rule)}</p></div>`).join("")}</div><div class="panel mdt-live-panel"><h2>${esc(current.name)}</h2>${eligibilityHtml(current)}<p><b>Specialty rule:</b> ${esc(current.specialty_rule)}</p><h3>Inputs</h3>${current.inputs.map(x=>`<span class="badge">${esc(x)}</span>`).join("")}<h3>Reasoning</h3><ul>${current.reasoning.map(x=>`<li>${esc(x)}</li>`).join("")}</ul><h3>Prescription</h3>${prescriptionHtml(current)}${agentChat(current)}</div>`, `<h3>Evidence alignment</h3><p>Guidelines define boundaries; meta-analysis and clinical studies add dose, delivery and patient-fit detail. Current focus: <b>${esc(state.chain.replaceAll("_"," "))}</b>.</p><button class="btn primary next-cta" onclick="go('safe')">Next: KOM-Safe</button>`); }
function dynamicMedicationItems(base){ const items=[...base.prescription.items]; if(num(state.profile.bmi,0)>=30) items.splice(5,0,"Semaglutide 2.4 mg once weekly is a special-population obesity-treatment option after clinician/endocrine review and label contraindication screening; STEP 9 supports weight and WOMAC pain improvement in adults with obesity and moderate knee OA, but it is not an autonomous OA analgesic."); if(medicationGateComplete()) items.unshift("Oral NSAID gate complete: named oral options below still require clinician selection, lowest effective dose, shortest duration and adverse-effect monitoring."); else items.unshift("Oral NSAID status: DEFER until renal function, GI bleeding risk, anticoagulant/antiplatelet status, current medications and cardiovascular risk are reviewed."); return items; }
function resultTierHtml(p){ if(!p.result_tiers) return ""; return `<div class="result-tier-grid">${p.result_tiers.map(x=>`<div><b>${esc(x.tier)}</b><span>${esc(x.message)}</span></div>`).join("")}</div>`; }
function exerciseActionLibrary(){
  const fall=/fall|stance|support|balance/i.test(String(state.profile.balance||""));
  return [
    {name:"Walking interval dose", tier:"L1 + L2", evidence:"KOA-EU-00019; KOA-EU-00099", dose:"3-5 days/week; 10-30 min split into 3-10 min intervals; RPE 3-5/10.", actions:"Flat indoor route or treadmill, shorter stride, comfortable cadence; progress total minutes before speed.", stop:"Stop or reduce for swelling, limp, night-pain increase or next-day function loss."},
    {name:"Stationary cycling protocol", tier:"L2 + L3", evidence:"KOA-EU-00477; KOA-EU-01039", dose:"2-4 days/week; 15-30 min; low-to-moderate resistance; saddle high enough to avoid deep-flexion pain.", actions:"Start with 5 min warm-up, steady cadence, then 2-4 short moderate blocks if tolerated.", stop:"Stop for effusion, sharp patellofemoral pain, increasing night pain or cycling through swelling."},
    {name:"Quadriceps isometric start", tier:"L1 + L3", evidence:"KOA-EU-00019; KOA-EU-01039", dose:"5-6 days/week; 2-3 sets of 8-12 reps; 5-10 second holds.", actions:"Quad sets, straight-leg raise, short-arc terminal knee extension; pain <=3/10 during and after.", stop:"Avoid breath-holding, resisted terminal extension through sharp pain, or next-day swelling."},
    {name:"Sit-to-stand and low step control", tier:"L1 + L3", evidence:"KOA-EU-00019; KOA-EU-00849", dose:"2-3 days/week; 1-3 sets of 6-10 reps; raised chair or 10-15 cm step.", actions:"Slow sit-to-stand, low step-up, controlled step-down; hand support if balance is limited.", stop:"Avoid deep flexion, knee collapse, fast stair volume increase or unsupported drills with fall risk."},
    {name:"Hip abductor and posterior-chain support", tier:"L1", evidence:"KOA-EU-00019", dose:"2-3 days/week; 1-3 sets of 8-12 reps.", actions:"Side-lying hip abduction, bridges, calf raises, hamstring curls, band walks when tolerated.", stop:"Avoid gait-changing resistance, lateral hip pain or worsening knee torque."},
    {name:"Balance and gait safety block", tier:fall?"Required safety module":"Conditional safety module", evidence:"KOA-EU-00019", dose:"3-5 days/week; 8-15 min/session; supervise if single-leg stance <10 s.", actions:"Tandem stance, supported single-leg stance, step touch, turning practice, gait aid check.", stop:"No unstable-surface drills without support; stop after near-fall, dizziness or fear escalation."},
    {name:"Aquatic bridge", tier:"L2", evidence:"KOA-EU-00156", dose:"1-3 sessions/week if available; 20-40 min.", actions:"Water walking, supported ROM, cycling-like movements when land walking flares.", stop:"Avoid with open wound, infection risk, unsafe pool access or uncontrolled cardiopulmonary symptoms."}
  ];
}
function exerciseActionHtml(){
  return `<div class="exercise-action-board"><h4>Specific exercise action menu</h4><p class="muted">Select and tailor these actions by preference, current flare state, fall risk and next-day response.</p><div class="exercise-action-grid">${exerciseActionLibrary().map(x=>`<article><div><b>${esc(x.name)}</b><span>${esc(x.tier)}</span></div><p><strong>Dose:</strong> ${esc(x.dose)}</p><p><strong>Actions:</strong> ${esc(x.actions)}</p><p><strong>Stop rule:</strong> ${esc(x.stop)}</p><small>Evidence: ${esc(x.evidence)}</small></article>`).join("")}</div></div>`;
}
function prescriptionHtml(a){ const p=a.prescription; if(a.id==="exercise_rehab") return `${resultTierHtml(p)}${exerciseActionHtml()}<table><thead><tr><th>Type</th><th>Frequency</th><th>Intensity</th><th>Time</th><th>Mode</th><th>Volume</th><th>Progression</th></tr></thead><tbody>${p.content.map(r=>`<tr>${r.map(x=>`<td>${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table><p><b>Stop rules:</b> ${p.stop_rules.map(x=>`<span class="badge red">${esc(x)}</span>`).join("")}</p><p><b>Avoid:</b> ${p.avoid.map(x=>`<span class="badge amber">${esc(x)}</span>`).join("")}</p>`; if(a.id==="nutrition") return `${resultTierHtml(p)}<p><b>Target:</b> ${num(state.profile.bmi,0)>=27?esc(p.target):"Weight maintenance with muscle preservation; avoid unnecessary weight-loss emphasis."}</p><p><b>Monitoring:</b> ${esc(p.monitoring||"Track weight, symptoms and strength.")}</p><p><b>Protein boundary:</b> ${esc(p.protein_boundary||"Avoid fixed high-protein dosing until renal function is known.")}</p><p><b>Plate structure:</b> ${esc(p.plate)}</p><h4>Encourage</h4>${p.eat_more.map(x=>`<span class="badge green">${esc(x)}</span>`).join("")}<h4>Reduce or avoid</h4>${p.eat_less.map(x=>`<span class="badge amber">${esc(x)}</span>`).join("")}<h4>Example day</h4><ul>${p.sample_day.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`; if(a.id==="medication") return `${resultTierHtml(p)}<h4>Safety information required before oral NSAID</h4>${missingInfo().map(x=>`<span class="badge red">${esc(x)}</span>`).join("") || '<span class="badge green">Medication safety gate complete</span>'}<div class="med-grid">${dynamicMedicationItems(a).map(x=>`<div class="med-item">${esc(x)}</div>`).join("")}</div>`; if(a.id==="psychology") return `${resultTierHtml(p)}<h4>Current screen signals</h4><p><span class="badge ${psychRiskStatus().includes('high')||psychRiskStatus().includes('Positive')?'red':'amber'}">${esc(psychRiskStatus())}</span></p><h4>Screening</h4>${p.screening.map(x=>`<span class="badge">${esc(x)}</span>`).join("")}<h4>Actionable intervention</h4><ul>${p.intervention.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`; const sx=surgeryDecisionStatus(); return `${resultTierHtml(p)}<div class="ortho-decision ${sx.status.startsWith('Recommend')?'recommend':sx.status.startsWith('Not appropriate')?'hold':'not-needed'}"><b>${esc(sx.status)}</b><p>${esc(sx.detail)}</p><p><strong>Reason:</strong> ${esc(sx.why)}</p></div><h4>Mandatory pre-referral screen</h4><ul>${(p.preoperative_warning||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ul><h4>Missing or unresolved screen items</h4>${sx.missing.map(x=>`<span class="badge red">${esc(x)}</span>`).join("") || '<span class="badge green">No basic pre-referral screen gap recorded</span>'}<h4>Collect before decision</h4>${p.collect_before_decision.map(x=>`<span class="badge amber">${esc(x)}</span>`).join("")}<h4>Pre-referral safety review</h4>${p.prehab.map(x=>`<span class="badge">${esc(x)}</span>`).join("")}`; }
function agentChat(agent){ return `<div class="chat-box ${agent.id==='psychology'?'psych-chat':''}"><h3>Ask this specialty agent</h3><div class="agent-quick-prompts"><button class="btn" onclick="quickAgentPrompt('Who are you and what can you do for knee osteoarthritis care?')">Who are you?</button><button class="btn" onclick="quickAgentPrompt('Use the current patient profile and draft your specialty prescription with evidence support and safety boundaries.')">Use current patient</button><button class="btn" onclick="quickAgentPrompt('What safety gates or missing data would stop this specialty recommendation?')">Safety gates</button></div><textarea id="agentQuestion" placeholder="Example: How should I explain this plan to a worried patient?"></textarea><label><input type="checkbox" onchange="state.useApi=this.checked"> Use configured model API if available</label><div class="actions"><button class="btn primary" onclick="askAgent('${agent.id}')">Ask agent</button></div><div id="agentAnswer" class="reason-box hidden"></div></div>`; }
function quickAgentPrompt(text){ const box=$("#agentQuestion"); if(box){ box.value=text; box.focus(); } }
async function askAgent(id){ const q=$("#agentQuestion").value||"Explain this specialty prescription."; const data=await api("/api/v9/agent/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({agent_id:id,question:q,profile:profileContext(),use_llm:state.useApi,selected_modules:selectedRxOptions(),safety_checks:dynamicSafetyChecks()})}); const box=$("#agentAnswer"); box.classList.remove("hidden"); box.textContent=`Source: ${data.source||'local'}\n\n${data.answer}`; }

function fieldMissing(v){ return !hasValue(v) || /missing|not recorded|not checked|needs review|not yet|incomplete/i.test(String(v||"")); }
function dynamicSafetyChecks(){
  const checks=[];
  const severeSides=["left","right"].filter(s=>kneeKl(s)>=3 || sidePain(s)>=7 || sideWomac(s)>=50);
  const oralUnsafe=!medicationGateComplete();
  const renalRisk=/egfr\s*(5[0-9]|4[0-9]|3[0-9])|ckd|renal/i.test(String(state.profile.egfr||""));
  const giRisk=/ulcer|bleed/i.test(String(state.profile.gi_history||""));
  const anticoagRisk=/warfarin|apixaban|rivaroxaban|dabigatran|anticoag|antiplatelet|aspirin/i.test(String(state.profile.anticoag||""));
  const fallRisk=/fall|balance|tug|stance|support/i.test(String(state.profile.balance||""));
  const psychRisk=/moderate|severe|high|insomnia|catastroph/i.test(`${state.profile.gad7||""} ${state.profile.phq9||""} ${state.profile.sleep_quality||""} ${state.profile.pain_catastrophizing||""}`);
  const preopMissing=["weightbearing_alignment_xray","knee_rom","surgical_cv_screen","surgical_resp_screen","skin_dental_infection_screen","conservative_history"].filter(k=>fieldMissing(state.profile[k]));
  checks.push({gate:"Specialty compatibility gate",status:(oralUnsafe||fallRisk||preopMissing.length)?"ACTION_REQUIRED":"PASS",finding:`Medication, injection, exercise, nutrition, psychology and orthopedic modules are cross-checked. Oral NSAID risk: ${oralUnsafe?"active":"controlled"}; fall-risk conflict: ${fallRisk?"active":"not active"}; pre-referral data gaps: ${preopMissing.length}.`,decision:"Block combinations that conflict: oral NSAID with renal/GI/anticoagulant risk, unsupervised exercise with fall risk, injection plans that ignore patient preference, or surgical referral without basic screening data."});
  checks.push({gate:"Patient data completeness gate",status:missingInfo().length||preopMissing.length?"ACTION_REQUIRED":"PASS",finding:`Missing medication/safety fields: ${missingInfo().join(", ")||"none"}. Pre-referral screening gaps: ${preopMissing.join(", ")||"none"}.`,decision:"Return to KOM-Profile for missing safety data before final Rx; if surgery is only being screened, collect self-reported CV/respiratory/infection/ROM/radiograph status rather than full specialist reports."});
  checks.push({gate:"Bilateral knee identity gate",status:"PASS_WITH_RULES",finding:`${bilateralSummary()}.`,decision:"Every prediction, imaging interpretation and treatment recommendation must state the knee side; KL grade is locked from profile in KOM-Risk."});
  checks.push({gate:"Medication safety gate",status:oralUnsafe?"ACTION_REQUIRED":"PASS",finding:oralUnsafe?`Red flags: ${[renalRisk&&"renal/eGFR",giRisk&&"GI ulcer/bleeding",anticoagRisk&&"anticoagulant/antiplatelet",fieldMissing(state.profile.current_meds)&&"medication reconciliation"].filter(Boolean).join(", ")||"incomplete review"}.`:"Renal, GI, medication and cardiovascular review are recorded.",decision:oralUnsafe?"Oral NSAID modules remain deferred; prefer topical diclofenac, acetaminophen rescue or injection bridge only after clinician assessment.":"Permit clinician-reviewed short-course named oral NSAID consideration if otherwise appropriate."});
  checks.push({gate:"Exercise FITT-VP and fall gate",status:fallRisk?"ACTION_REQUIRED":"CONDITIONAL_PASS",finding:fallRisk?`Fall/balance signal: ${state.profile.balance}. Preference: ${state.profile.exercise_preference||"not recorded"}.`:`No major fall-risk signal recorded. Preference: ${state.profile.exercise_preference||"not recorded"}.`,decision:"Exercise prescription must include frequency, intensity, time, type, volume, progression, preferred modality, supervision level and stop rules; cycling/aquatic options can be prioritized when walking flares symptoms."});
  checks.push({gate:"Nutrition and metabolic safety gate",status:/ckd|egfr\s*5|renal|malnutrition/i.test(String(state.profile.nutrition_risk||state.profile.egfr||""))?"ACTION_REQUIRED":num(state.profile.bmi,0)>=27?"CONDITIONAL_PASS":"PASS",finding:`Nutrition risk: ${state.profile.nutrition_risk||"not recorded"}; BMI ${state.profile.bmi}.`,decision:"Use explicit 5-10% weight target only when BMI is elevated, preserve muscle, and avoid fixed protein targets until renal/metabolic risk is reviewed."});
  checks.push({gate:"Psychology signal and communication gate",status:psychRisk?"ACTION_REQUIRED":"CONDITIONAL_PASS",finding:`${state.profile.gad7||"GAD-7 not recorded"}; ${state.profile.phq9||"PHQ-9 not recorded"}; ${state.profile.sleep_quality||"sleep not recorded"}; ${state.profile.pain_catastrophizing||"catastrophizing not recorded"}.`,decision:psychRisk?"Use CBT-informed explanation, behavioral activation, pacing, relaxation and referral thresholds before asking for adherence-heavy plans.":"If no screen is recorded, report the data gap and use neutral low-risk education until screening is completed."});
  checks.push({gate:"Orthopedic referral and preoperative screening gate",status:severeSides.length?(preopMissing.length?"ACTION_REQUIRED":"CONDITIONAL_PASS"):"PASS",finding:severeSides.length?`${severeSides.map(kneeLabel).join(", ")} meets referral-screen profile; missing: ${preopMissing.join(", ")||"none"}.`:"Referral discussion is not the primary driver under the current bilateral profile.",decision:"For referral screening, require weight-bearing radiographs/alignment status, ROM, conservative-treatment response, self-reported cardiovascular and respiratory risk, skin/dental infection signal and anticoagulant/diabetes flags; do not choose TKA/UKA/HTO inside the AI module."});
  return checks;
}
function loadSafetyScenario(kind){
  if(kind==="medication_missing") Object.assign(state.profile,{target_side:"Both knees",egfr:"MISSING",gi_history:"MISSING",anticoag:"Warfarin",current_meds:"Warfarin; antihypertensive therapy; medication reconciliation incomplete",cv_risk:"High",left_nrs:"8",right_nrs:"4"});
  if(kind==="injection_preference") Object.assign(state.profile,{target_side:"Both knees",avoid_injection:"Yes",left_nrs:"8",right_nrs:"4",left_kl:"4",right_kl:"2",quality_goal:"Maintain community mobility while avoiding repeated injections"});
  if(kind==="fall_exercise") Object.assign(state.profile,{target_side:"Both knees",balance:"Single-leg stance <10 s or needs support",left_strength:"MRC 4-/5; isometric knee-extension peak force not measured",right_strength:"MRC 4+/5; monitor endurance",left_nrs:"8",right_nrs:"4",left_kl:"4",right_kl:"2"});
  state.manualChain=false; state.negotiation=null; syncProfileDerived("safety-scenario"); safe(); toast("Problem-case profile loaded for Safe-MDT negotiation.");
}
function safe(){ const s=dynamicSafetyChecks(); pageLayout("KOM-Safe audit and MDT negotiation", "Safety is not a static checklist. Non-pass gates are routed back to the responsible specialty agent, revised, re-audited and recorded.", `<div class="panel scenario-panel"><h2>Problem-case runners</h2><p>Use these profiles to inspect how KOM-Safe returns unsafe or unclear recommendations to the responsible specialty agent.</p><div class="actions"><button class="btn" onclick="loadSafetyScenario('medication_missing')">Medication safety problem</button><button class="btn" onclick="loadSafetyScenario('injection_preference')">Injection preference conflict</button><button class="btn" onclick="loadSafetyScenario('fall_exercise')">Fall-risk exercise conflict</button></div></div><div class="grid3">${s.map(x=>`<div class="panel safety-card"><h3>${esc(x.gate)} <span class="badge ${x.status==='ACTION_REQUIRED'?'red':'green'}">${esc(x.status)}</span></h3><p><b>Finding:</b> ${esc(x.finding)}</p><p><b>Decision:</b> ${esc(x.decision)}</p></div>`).join("")}</div><div class="panel negotiation-board"><div class="negotiation-head"><div><h2>Safe-MDT negotiation and revision trace</h2><p>Run the negotiation loop to show how audit findings are returned to specialty agents.</p></div><button class="btn primary" onclick="runNegotiation()">Run Safe-MDT negotiation</button></div><div class="negotiation-flow"><span>KOM-Safe audit</span><i></i><span>Specialty revision</span><i></i><span>Re-audit</span><i></i><span>Adoption / clinician review</span></div><div id="negotiationBox">${negotiationHtml()}</div></div>`, `<h3>Completion rule</h3><p>A recommendation can proceed only after gate status, specialty response, re-audit and clinician-review boundary are recorded.</p><button class="btn primary next-cta" onclick="go('rx')">Next: KOM-Rx</button>`); }
function negotiationHtml(){ const n=state.negotiation; if(!n) return `<p class="muted">No negotiation run yet.</p>`; return `<p><b>Status:</b> ${esc(n.status)} <span class="badge">${esc(n.source)}</span><span class="badge">${esc(n.audit_id||'audit pending')}</span></p><div class="negotiation-events">${n.events.map(e=>`<div class="negotiation-event"><div class="event-meta"><span class="badge">${esc(e.event_id||('Round '+e.round))}</span><span class="badge">Round ${e.round}</span><span class="badge">${esc(e.target)}</span><span class="badge green">${esc(e.status)}</span></div><p><b>Gate:</b> ${esc(e.gate)} <span class="badge amber">${esc(e.input_gate_status||'not supplied')}</span></p><p><b>Audit message:</b> ${esc(e.message)}</p><p><b>Agent response:</b> ${esc(e.agent_response)}</p><p><b>Re-audit:</b> ${esc(e.reaudit)}</p><p><b>Adoption rule:</b> ${esc(e.adoption_rule||'Recorded clinician-review boundary required.')}</p></div>`).join("")}</div>${n.llm_feedback?`<div class="reason-box"><b>Model feedback:</b> ${esc(n.llm_feedback)}</div>`:""}`; }
async function runNegotiation(){ const data=await api("/api/v15/safe/negotiate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({checks:dynamicSafetyChecks(),profile:profileContext(),use_llm:state.useApi})}); state.negotiation=data; $("#negotiationBox").innerHTML=negotiationHtml(); toast("Safe-MDT negotiation completed"); }

function rxSections(){
  const c=state.content;
  const medicationStatus = medicationGateComplete()
    ? "Medication safety gate is complete; oral NSAID may be considered only as clinician-reviewed short-course therapy."
    : "Oral NSAID remains deferred until renal, GI, anticoagulant/current medication and cardiovascular review is complete.";
  return [
    ["Case summary", c.case.one_line],
    ["Patient assessment report", `Current case: ${currentCaseTitle()}; left knee profile-derived KL ${state.riskInputs.left_kl}, NRS ${state.riskInputs.left_nrs}, WOMAC ${state.riskInputs.left_womac}; right knee profile-derived KL ${state.riskInputs.right_kl}, NRS ${state.riskInputs.right_nrs}, WOMAC ${state.riskInputs.right_womac}; BMI ${state.riskInputs.bmi}.`],
    ["Medication safety priority", medicationStatus],
    ["Final clinician-selected modules", selectedRxOptions().map(x=>x.label).join("; ") || "No final modules selected yet."],
    ["Evidence and MDT routing", `Current GraphRAG focus is ${state.chain.replaceAll("_"," ")} with guideline anchors plus meta-analysis and clinical-study detail.`],
    ["Follow-up and escalation", "Reassess pain, function, walking tolerance, adverse effects, fall events and patient goals at structured follow-up. Escalate referral discussion if conservative treatment remains insufficient."]
  ];
}
function psychRiskStatus(){
  const text=`${state.profile.gad7||""} ${state.profile.phq9||""} ${state.profile.sleep_quality||""} ${state.profile.pain_catastrophizing||""}`.toLowerCase();
  if(/moderate|severe|positive|high|self-harm|suicid/.test(text)) return "Positive or high-risk signal recorded";
  if(/mild|watch|insomnia|worry|low mood/.test(text)) return "Mild or watch signal recorded";
  return "Screening required before final communication plan";
}
function rxRiskFactors(){
  const risks=[];
  if(num(state.profile.bmi,0)>=27) risks.push(`BMI ${state.profile.bmi}: weight target with muscle preservation`);
  if(kneeKl("left")>=3 || sidePain("left")>=7 || sideWomac("left")>=50) risks.push(`Left knee priority: KL ${kneeKl("left")}, NRS ${sidePain("left")}, WOMAC ${sideWomac("left")}`);
  if(kneeKl("right")>=3 || sidePain("right")>=7 || sideWomac("right")>=50) risks.push(`Right knee priority: KL ${kneeKl("right")}, NRS ${sidePain("right")}, WOMAC ${sideWomac("right")}`);
  if(!medicationGateComplete()) risks.push(`Medication gate incomplete: ${missingInfo().join(", ")}`);
  if(/stance|support|fall|balance/i.test(String(state.profile.balance||""))) risks.push(`Balance and fall signal: ${state.profile.balance}`);
  risks.push(`Psychology status: ${psychRiskStatus()}`);
  return risks;
}
function semaglutideRecommendation(){
  const bmi=num(state.profile.bmi,0);
  if(bmi>=30) return "Special-population obesity option";
  if(bmi>=27) return "Obesity-comorbidity review only";
  return "Not indicated from current BMI";
}
function rxEvidenceLibrary(){
  return {
    topical_diclofenac:[{level:"L1",eu:"KOA-EU-00011",label:"Guideline/consensus anchor for topical NSAID before systemic escalation"}],
    celecoxib:[{level:"L1",eu:"KOA-EU-00012",label:"Oral NSAID only after safety-gate review"},{level:"L3",eu:"KOA-EU-02073",label:"Celecoxib comparator trial evidence in symptomatic knee OA"}],
    naproxen:[{level:"L1",eu:"KOA-EU-00012",label:"Named oral NSAID boundary: shortest course and risk review"},{level:"L3",eu:"KOA-EU-01554",label:"Naproxen comparator study recorded in local evidence unit"}],
    ibuprofen:[{level:"L1",eu:"KOA-EU-00012",label:"Oral NSAID class boundary, patient safety gate required"}],
    acetaminophen:[{level:"L1",eu:"KOA-EU-00011",label:"Analgesic rescue boundary; not a disease-modifying plan"}],
    duloxetine:[{level:"L1",eu:"KOA-EU-00012",label:"Conditionally used centrally acting analgesic boundary"},{level:"L3",eu:"KOA-EU-01307",label:"Duloxetine perioperative chronic pain trial evidence; not routine OA-only proof"}],
    semaglutide_obesity:[{level:"L3",eu:"KOA-EU-STEP9-2024",label:"STEP 9 randomized evidence for obesity plus knee OA"}],
    frontier_rna_trials:[{level:"L6",eu:"FRONTIER-RNA-2026",label:"Frontier/preclinical or early translational RNA/mRNA OA therapy; trial-only boundary"}],
    ia_corticosteroid:[{level:"L1",eu:"KOA-EU-00023",label:"Guideline boundary for conditional injection bridge"},{level:"L2",eu:"KOA-EU-00094",label:"Injection safety comparison synthesis"}],
    sodium_hyaluronate:[{level:"L1",eu:"KOA-EU-00011",label:"Guideline conflict: HA is not routine/default therapy"}],
    prp:[{level:"L2",eu:"KOA-EU-00094",label:"PRP safety synthesis"},{level:"L2",eu:"KOA-EU-00136",label:"PRP RCT fragility/synthesis boundary"}],
    lp_prp:[{level:"L2",eu:"KOA-EU-00094",label:"PRP safety synthesis; preparation must be specified"},{level:"L3",eu:"PRP-LP-LR-2024",label:"LP-PRP versus LR-PRP RCT signal; comparable outcomes, shared decision"}],
    lr_prp:[{level:"L2",eu:"KOA-EU-00136",label:"PRP evidence fragility boundary"},{level:"L3",eu:"PRP-LP-LR-2024",label:"Leukocyte status comparison; not a universal superiority claim"}],
    genicular_rfa:[{level:"L3",eu:"KOA-EU-00824",label:"Genicular nerve radiofrequency randomized/interventional evidence"}],
    gae:[{level:"L2",eu:"KOA-EU-00209",label:"Genicular artery embolization systematic review/meta-analysis"}],
    aerobic_walking:[{level:"L1",eu:"KOA-EU-00019",label:"Guideline core exercise anchor"},{level:"L2",eu:"KOA-EU-00099",label:"Exercise modality NMA favors accessible aerobic modes"}],
    stationary_cycling:[{level:"L2",eu:"KOA-EU-00477",label:"Stationary cycling meta-analysis"},{level:"L3",eu:"KOA-EU-01039",label:"Power cycling plus quadriceps training RCT"}],
    resistance:[{level:"L1",eu:"KOA-EU-00019",label:"Guideline strengthening anchor"},{level:"L3",eu:"KOA-EU-00849",label:"Resistance-training interventional signal"}],
    quadriceps_isometric:[{level:"L1",eu:"KOA-EU-00019",label:"Guideline strengthening anchor"},{level:"L3",eu:"KOA-EU-01039",label:"Quadriceps training trial evidence"}],
    sit_to_stand_step:[{level:"L1",eu:"KOA-EU-00019",label:"Functional strengthening guideline anchor"},{level:"L3",eu:"KOA-EU-00849",label:"Progressive resistance/interventional support"}],
    hip_abductor_chain:[{level:"L1",eu:"KOA-EU-00019",label:"Strength and neuromuscular control guideline anchor"}],
    neuromotor_balance:[{level:"L1",eu:"KOA-EU-00019",label:"Exercise/fall-safety boundary"},{level:"L2",eu:"KOA-EU-00721",label:"Brace/support synthesis informs balance and support decisions"}],
    aquatic:[{level:"L2",eu:"KOA-EU-00156",label:"Aquatic exercise systematic review/meta-analysis"}],
    tai_chi_yoga:[{level:"L2",eu:"KOA-EU-00154",label:"Tai chi overview of systematic reviews"},{level:"L2",eu:"KOA-EU-00429",label:"Tai chi meta-analysis signal"}],
    weight_target:[{level:"L1",eu:"KOA-EU-00011",label:"Weight-management guideline anchor"}],
    leafy_vegetables:[{level:"L1",eu:"KOA-EU-00011",label:"Diet quality within weight/self-management guideline boundary"}],
    legumes:[{level:"L1",eu:"KOA-EU-00011",label:"Diet quality and muscle-preservation boundary"}],
    fish_poultry:[{level:"L1",eu:"KOA-EU-00011",label:"Protein-quality boundary, renal review when needed"}],
    whole_grains:[{level:"L1",eu:"KOA-EU-00011",label:"Diet quality and energy-control boundary"}],
    obesity_pharmacotherapy_review:[{level:"L3",eu:"KOA-EU-STEP9-2024",label:"Obesity pharmacotherapy RCT evidence in knee OA phenotype"}],
    risk_screen:[{level:"L1",eu:"KOA-EU-00011",label:"Self-management and psychosocial screening boundary"}],
    cbt_guided_self_help:[{level:"L3",eu:"KOA-EU-01297",label:"Exercise/education plus CBT trial evidence"},{level:"L3",eu:"KOA-EU-01422",label:"CBT-related trial record"}],
    behavioral_activation:[{level:"L3",eu:"KOA-EU-01297",label:"CBT-informed activity and education trial support"}],
    relaxation_pacing:[{level:"L1",eu:"KOA-EU-00011",label:"Self-management guideline boundary"}],
    communication_script:[{level:"L1",eu:"KOA-EU-00011",label:"Patient education and shared-decision boundary"}],
    orthopedic_referral:[{level:"L1",eu:"KOA-EU-00023",label:"Referral/escalation guideline boundary"}],
    preoperative_warning:[{level:"L1",eu:"KOA-EU-00025",label:"Prehabilitation/postoperative rehabilitation clinical practice recommendation"}],
    prehab:[{level:"L1",eu:"KOA-EU-00025",label:"Prehabilitation clinical practice recommendation"},{level:"L2",eu:"KOA-EU-00330",label:"Prehabilitation systematic review evidence"}]
  };
}
function evidenceForRxOption(cat,id){
  return rxEvidenceLibrary()[id] || [{level:"L7",eu:"LOCAL-RX-GATE",label:`${cat} module requires clinician review and local evidence audit`}];
}
function rxEvidenceHtml(list){
  return `<div class="rx-evidence-support">${(list||[]).map(e=>`<span class="rx-evidence-badge ${esc(String(e.level||'L7').toLowerCase())}" title="${esc(e.label)}"><b>${esc(e.level)}</b>${esc(e.eu)}</span>`).join("")}</div>`;
}
function rxEvidenceText(list){
  return (list||[]).map(e=>`${e.level} ${e.eu}: ${e.label}`).join("; ");
}
function surgeryDecisionStatus(){
  const severeSides=["left","right"].filter(s=>kneeKl(s)>=3 || sidePain(s)>=7 || sideWomac(s)>=50);
  const hasSevere=severeSides.length>0;
  const preopMissing=["weightbearing_alignment_xray","knee_rom","surgical_cv_screen","surgical_resp_screen","skin_dental_infection_screen","conservative_history"].filter(k=>fieldMissing(state.profile[k]));
  if(!hasSevere) return {status:"Not needed now", detail:"No side currently combines KL3-4 disease or severe pain/function loss; continue conservative care and side-specific monitoring.", why:"Referral is not the primary treatment driver for this profile.", missing:preopMissing};
  if(/severe|unstable|active infection|uncontrolled/i.test(`${state.profile.surgical_cv_screen||""} ${state.profile.surgical_resp_screen||""} ${state.profile.skin_dental_infection_screen||""}`)) return {status:"Not appropriate until risk optimized", detail:`${severeSides.map(kneeLabel).join(", ")} may need specialist review, but current pre-referral screen contains unresolved safety concerns.`, why:"Unresolved cardiopulmonary or infection signals should be optimized before elective surgical pathway planning.", missing:preopMissing};
  return {status:"Recommend orthopedic evaluation", detail:`${severeSides.map(kneeLabel).join(", ")} meets referral-screen profile because structural/symptom/function burden is high.`, why:"Advanced side-specific burden plus patient goal or failed/uncertain conservative response supports specialist evaluation.", missing:preopMissing};
}
function rxOptionDefinitions(){
  const oralGate=medicationGateComplete();
  const oralGateNote=oralGate?"Safety gate currently complete; still use lowest effective dose for the shortest duration.":"Select only as a deferred option until renal, GI, anticoagulant/current-medication and cardiovascular review is complete.";
  const surgeryStatus=surgeryDecisionStatus();
  return {
    medication:{title:"Medication modules", note:"Choose named medicines rather than broad drug classes.", options:[
      {id:"topical_diclofenac", label:"Diclofenac 1% gel", rec:"Recommended first-line topical NSAID", detail:"Apply 4 g to the symptomatic knee up to four times daily for 2-4 weeks; avoid broken skin and monitor dermatitis.", why:"Knee OA with localized pain; topical NSAID gives a lower systemic exposure path before oral NSAIDs.", avoid:"Avoid combining multiple topical NSAIDs or applying under occlusion."},
      {id:"celecoxib", label:"Celecoxib oral NSAID", rec:oralGate?"Conditional oral option":"Deferred oral option", detail:"Celecoxib 100 mg twice daily or 200 mg once daily after clinician review; consider gastroprotection where risk requires it.", why:"Oral NSAID can be considered when topical therapy is ineffective or unsuitable and safety gates are acceptable.", avoid:oralGateNote},
      {id:"naproxen", label:"Naproxen oral NSAID", rec:oralGate?"Alternative oral option":"Deferred oral option", detail:"Naproxen 250 mg twice daily; clinician-supervised adjustment only if needed and tolerated.", why:"Alternative oral NSAID when celecoxib is unsuitable or local formulary favors naproxen.", avoid:"Do not combine with another oral NSAID; review GI, renal, anticoagulant and CV risk."},
      {id:"ibuprofen", label:"Ibuprofen short-course option", rec:oralGate?"Short-course option":"Deferred oral option", detail:"Ibuprofen 400 mg every 6-8 hours as needed for a short course after safety review.", why:"Useful for episodic pain flares when clinician judges risk acceptable.", avoid:"Avoid unsupervised use with aspirin, anticoagulants, renal impairment, active ulcer disease or uncontrolled CV risk."},
      {id:"acetaminophen", label:"Acetaminophen rescue analgesic", rec:"Infrequent rescue only", detail:"Acetaminophen/paracetamol 500-1000 mg every 6-8 hours as needed; keep within local daily dose limits.", why:"May support short-term episodic pain when NSAID options are unsuitable.", avoid:"Avoid routine long-term reliance; lower dose limits with liver disease, alcohol misuse or frailty."},
      {id:"duloxetine", label:"Duloxetine pain-modulation option", rec:"Selected chronic pain option", detail:"Duloxetine 30 mg once daily for 1 week, then 60 mg once daily if tolerated and clinically appropriate; review interactions and mood/suicide risk.", why:"Consider when central sensitization, sleep/mood burden or NSAID limitations make a pain-modulation approach relevant.", avoid:"Avoid in uncontrolled liver disease, high-risk drug interactions, severe renal impairment, bipolar/mania risk or abrupt discontinuation."},
      {id:"semaglutide_obesity", label:"Semaglutide 2.4 mg once weekly", rec:semaglutideRecommendation(), detail:"For BMI >=30 or an obesity-treatment indication, consider referral/clinician review for semaglutide titrated to 2.4 mg subcutaneous weekly with lifestyle therapy, label contraindication review and adverse-effect monitoring.", why:"STEP 9 showed weight loss and WOMAC pain improvement in adults with obesity and moderate knee OA; use as obesity therapy, not as an autonomous OA analgesic.", avoid:"Avoid without obesity indication or prescribing authority; review pregnancy, pancreatitis/gallbladder history, MEN2/MTC contraindication, GI intolerance, cost and long-term continuation plan."},
      {id:"frontier_rna_trials", label:"RNA/mRNA frontier therapy", rec:"Research-only / trial screen", detail:"Do not prescribe as routine OA care. If a patient asks about disease-modifying RNA or mRNA approaches, route to trial eligibility or research discussion only.", why:"Early translational OA literature is active, but routine clinical prescribing is not supported by the current local clinical evidence chain.", avoid:"Avoid presenting frontier molecular therapy as an available clinical prescription or structural-regeneration guarantee."}
    ]},
    injection:{title:"Injection modules", note:"Injection choices are explicitly separated from oral/topical medicine.", options:[
      {id:"ia_corticosteroid", label:"Intra-articular corticosteroid", rec:"Conditional short-term option", detail:"Triamcinolone acetonide 40 mg intra-articular injection to the symptomatic knee after clinician assessment.", why:"Can provide a short relief window when pain or effusion blocks exercise participation.", avoid:"Avoid routine repeated injections; avoid active infection and review diabetes, anticoagulation and upcoming surgery timing."},
      {id:"sodium_hyaluronate", label:"Sodium hyaluronate", rec:"Not routine; shared-decision only", detail:"Product-specific intra-articular sodium hyaluronate regimen, commonly weekly injection series or approved single-injection product per local label.", why:"Use only if clinician and patient explicitly accept uncertainty, cost and guideline conflict after standard options are unsuitable.", avoid:"NICE does not offer hyaluronan and AAOS does not recommend routine HA use; do not present as default therapy."},
      {id:"prp", label:"Platelet-rich plasma (PRP)", rec:"Not routine; evidence-conflict option", detail:"If offered locally, document PRP preparation, leukocyte status if known, number of injections, interval, cost and uncertainty before consent.", why:"AAOS reports limited evidence that PRP may improve pain/function, while ACR recommends against routine PRP for knee OA.", avoid:"Avoid as an automatic recommendation; avoid active infection, unreviewed anticoagulation, unrealistic structural-regeneration claims and opaque protocols."},
      {id:"lp_prp", label:"Leukocyte-poor PRP", rec:"Protocol-specific option", detail:"Document leukocyte-poor preparation, platelet concentration if available, activation, number of injections and interval before consent.", why:"Preparation heterogeneity matters; LP-PRP can be discussed only when the local protocol is transparent and patient accepts uncertainty.", avoid:"Avoid implying superiority unless the evidence unit and local protocol match the patient and product."},
      {id:"lr_prp", label:"Leukocyte-rich PRP", rec:"Protocol-specific option", detail:"Document leukocyte-rich preparation and inflammation-risk discussion; consider whether local evidence supports the chosen product.", why:"Some trials compare leukocyte status, but this is not a default superiority signal for routine care.", avoid:"Avoid in uncontrolled inflammatory flare, infection risk or when leukocyte status cannot be reported."},
      {id:"genicular_rfa", label:"Genicular nerve radiofrequency", rec:"Refractory pain bridge", detail:"Consider interventional-pain referral for genicular nerve RFA when pain remains high despite conservative care and surgery is deferred or unsuitable.", why:"May reduce pain in selected refractory patients while preserving the orthopedic decision boundary.", avoid:"Avoid if diagnostic block/pathway is unavailable or if it delays urgent orthopedic review."},
      {id:"gae", label:"Genicular artery embolization", rec:"Emerging IR option", detail:"For refractory symptomatic mild-to-moderate OA, discuss interventional radiology evaluation only in centers with protocolized selection and follow-up.", why:"Systematic reviews support an emerging signal, but patient selection, durability and adverse-event monitoring remain essential.", avoid:"Avoid as routine first-line therapy or for advanced mechanical deformity requiring orthopedic assessment."}
    ]},
    exercise:{title:"Exercise prescription modules", note:"Modules are grouped by guideline core, synthesis/RCT signal and patient-fit safety.", options:[
      {id:"aerobic_walking", label:"Walking or treadmill intervals", rec:"L1 guideline core", detail:"3-5 days/week, 20-30 minutes/session or interval blocks, moderate perceived exertion, progress by symptoms.", why:"Guidelines consistently support aerobic exercise; useful when the patient goal is walking tolerance.", avoid:"Avoid large jumps in distance; reduce load for 24-48 hours after flare."},
      {id:"stationary_cycling", label:"Stationary cycling", rec:"L2/L3 low-impact signal", detail:"2-4 days/week, 15-30 minutes/session, low-to-moderate resistance; progress duration before resistance.", why:"Low joint-impact aerobic modality is useful for patients who flare with walking but can tolerate cycling.", avoid:"Avoid high saddle resistance, deep-flexion pain, or cycling through swelling."},
      {id:"resistance", label:"Progressive resistance training", rec:"L1 core plus synthesis support", detail:"2-3 days/week; quadriceps, hip abductors, hamstrings and calf; 1-3 sets of 8-12 reps, slow progression.", why:"Weakness and functional burden make strength a central modifiable target across guideline and synthesis evidence.", avoid:"Avoid high-load painful deep flexion, swelling escalation or next-day function loss."},
      {id:"quadriceps_isometric", label:"Quadriceps isometrics", rec:"Pain-safe strength start", detail:"5-6 days/week; quad sets or straight-leg raises, 2-3 sets of 8-12 reps, 5-10 second holds, pain <=3/10 during and after.", why:"Useful when the priority knee has pain inhibition or cannot tolerate loaded knee flexion yet.", avoid:"Avoid breath-holding, resisted terminal extension through sharp pain or next-day swelling."},
      {id:"sit_to_stand_step", label:"Sit-to-stand and step control", rec:"Functional resistance", detail:"2-3 days/week; sit-to-stand from raised chair, low step-up/step-down, 1-3 sets of 6-10 reps with hand support if needed.", why:"Links quadriceps and hip strength to daily function and fall prevention.", avoid:"Avoid deep knee flexion, valgus collapse, rapid stair volume increase or unsupported drills with fall risk."},
      {id:"hip_abductor_chain", label:"Hip abductor chain", rec:"Load-control module", detail:"2-3 days/week; side-lying hip abduction, bridges, band walks and calf/hamstring support work, 1-3 sets of 8-12 reps.", why:"Hip and posterior-chain control can reduce symptomatic load during gait and stairs.", avoid:"Avoid high-resistance band work that changes gait or causes lateral hip pain."},
      {id:"neuromotor_balance", label:"Neuromotor and balance training", rec:"Patient-fit safety module", detail:"3-5 days/week; supported single-leg stance, tandem stance, sit-to-stand control, step-down control and gait practice.", why:"Balance or fall signals should change the exercise prescription, not simply add generic advice.", avoid:"Avoid unsupervised unstable-surface drills if the patient needs support."},
      {id:"aquatic", label:"Aquatic exercise", rec:"L2/L3 symptom-limited option", detail:"1-3 sessions/week if available; water walking, cycling-like movements and range-of-motion work when land exercise flares symptoms.", why:"Useful when body weight, pain, fear or severe symptoms limit land-based training.", avoid:"Avoid if wound, infection risk or pool access/safety is unsuitable."},
      {id:"tai_chi_yoga", label:"Tai chi or yoga-informed movement", rec:"Conditional adherence option", detail:"1-2 supervised sessions/week or home sequence after instruction; emphasize slow control, breathing and pain-safe range.", why:"Can support balance, confidence, anxiety and adherence in selected patients.", avoid:"Avoid positions that provoke knee torque, deep flexion pain or fall risk."}
    ]},
    nutrition:{title:"Nutrition modules", note:"Give concrete food examples and a measurable target.", options:[
      {id:"weight_target", label:"5-10% weight target", rec:"Recommended when BMI elevated", detail:"Aim for 5% weight reduction over 3-6 months; consider 10% only if strength and function are preserved.", why:"BMI elevation increases load; target is paired with resistance training to protect muscle.", avoid:"Avoid crash dieting and unmonitored rapid weight loss."},
      {id:"leafy_vegetables", label:"Non-starchy vegetables", rec:"Plate anchor", detail:"Leafy greens, broccoli, peppers, tomatoes, mushrooms, cucumber, carrots and other non-starchy vegetables at most meals.", why:"Improves meal volume, micronutrients and energy control without adding joint load.", avoid:"Avoid turning vegetable advice into a restrictive diet."},
      {id:"legumes", label:"Legumes and soy foods", rec:"Plant-protein option", detail:"Beans, lentils, chickpeas, tofu or edamame several times weekly if tolerated.", why:"Supports satiety and protein distribution, especially when meat intake is reduced.", avoid:"Adjust for gastrointestinal tolerance and renal/dietary restrictions."},
      {id:"fish_poultry", label:"Fish or lean poultry", rec:"Protein option", detail:"Fish, skinless poultry, eggs or low-fat dairy as tolerated; distribute protein across meals after renal review.", why:"Pairs nutrition with resistance training and muscle preservation.", avoid:"Avoid fixed high-protein dosing until eGFR is reviewed."},
      {id:"whole_grains", label:"Whole grains or starchy vegetables", rec:"Carbohydrate quality", detail:"Oats, brown rice, whole-wheat noodles, corn, potato or sweet potato in controlled portions.", why:"Keeps meals practical while reducing energy excess.", avoid:"Avoid sugary drinks and large late-night refined-carbohydrate meals."},
      {id:"obesity_pharmacotherapy_review", label:"Obesity pharmacotherapy review", rec:num(state.profile.bmi,0)>=30?"Review GLP-1 option":"Not routine", detail:"When BMI and local indication fit, discuss anti-obesity pharmacotherapy as a metabolic adjunct while retaining resistance training and nutrition monitoring.", why:"Evidence now includes semaglutide STEP 9 for obesity plus knee OA; this changes management for selected obese patients.", avoid:"Do not replace exercise, diet quality, renal review or clinician prescribing boundaries."}
    ]},
    psychology:{title:"Psychology and communication modules", note:`Risk status: ${psychRiskStatus()}.`, options:[
      {id:"risk_screen", label:"Screen anxiety, depression and sleep", rec:"Required before final plan", detail:"Use GAD-7, PHQ-9, pain catastrophizing and sleep screen; ask self-harm question when clinically indicated.", why:"The system should surface risk before the clinician conversation, not discover it after the visit.", avoid:"Avoid dismissing distress as merely emotional or unrelated to pain."},
      {id:"cbt_guided_self_help", label:"CBT-guided self-help", rec:"Mild or stepped-care option", detail:"4-6 weeks of guided CBT principles: pain education, thought reframing, activity scheduling, pacing and weekly symptom tracking.", why:"Guideline-consistent low-intensity psychological support can improve coping and adherence.", avoid:"Escalate rather than delay if moderate/severe symptoms, self-harm signal or inability to adhere safely is present."},
      {id:"behavioral_activation", label:"Behavioral activation", rec:"Depression-adherence support", detail:"Schedule one meaningful low-load activity daily and track mood, sleep, pain interference and completion.", why:"Links mood management to rehabilitation adherence.", avoid:"Avoid unrealistic daily goals that trigger flare or failure."},
      {id:"relaxation_pacing", label:"Relaxation and pacing script", rec:"Flare-management tool", detail:"Teach 5 minutes diaphragmatic breathing, 10 minutes progressive relaxation, load reduction for 24-48 hours, then graded return.", why:"Gives the patient an action script for anxiety-pain flare cycles.", avoid:"Avoid complete rest beyond the short flare window unless red flags exist."},
      {id:"communication_script", label:"Clinician conversation cue", rec:"Use during visit", detail:"Acknowledge pain, explain that structure, load, sleep, stress and nervous-system sensitivity interact, then invite one shared goal for the next 2 weeks.", why:"Pre-assessed anxiety/depression risk changes how the clinician frames expectations.", avoid:"Avoid blame, fear language or promises that imaging changes will fully reverse."}
    ]},
    surgery:{title:"Orthopedic boundary modules", note:"Surgery is a referral recommendation with preoperative warnings, not an automatic procedure choice.", options:[
      {id:"orthopedic_referral", label:"Orthopedic specialist evaluation", rec:surgeryStatus.status, detail:surgeryStatus.detail, why:surgeryStatus.why, avoid:"Do not choose TKA, UKA or HTO inside the AI module; do not refer as final surgery if basic risk and conservative-response data are missing."},
      {id:"preoperative_warning", label:"Preoperative warning checklist", rec:"Required before surgical decision", detail:"Collect updated weight-bearing radiographs, alignment, ROM, infection risk, diabetes control, dental/skin status, anticoagulation plan and rehab capacity.", why:"Preoperative risk must be surfaced before the patient is steered toward surgery.", avoid:"Avoid referral without documenting modifiable risks and conservative-treatment response."},
      {id:"prehab", label:"Prehabilitation bridge", rec:"Bridge while awaiting review", detail:"Continue low-irritability strength, range of motion, gait aid optimization and weight/nutrition plan.", why:"Improves readiness whether the final path is surgery or continued conservative care.", avoid:"Avoid painful overload that worsens effusion or sleep."}
    ]}
  };
}
function isRxSelected(cat,id){ return (state.rxSelections[cat]||[]).includes(id); }
function toggleRxOption(cat,id){
  const current=state.rxSelections[cat]||[];
  state.rxSelections[cat]=current.includes(id)?current.filter(x=>x!==id):[...current,id];
  state.rxFinalized=false;
  scheduleProfileSave();
  rx();
}
function rxCategoryHtml(cat,group){
  return `<section class="rx-builder-category"><div class="rx-builder-category-head"><h3>${esc(group.title)}</h3><p>${esc(group.note)}</p></div><div class="rx-option-stack">${group.options.map(o=>{ const ev=evidenceForRxOption(cat,o.id); return `<button class="rx-option ${isRxSelected(cat,o.id)?'selected':''}" data-rx-cat="${esc(cat)}" data-rx-id="${esc(o.id)}" onclick="toggleRxOption('${cat}','${o.id}')"><span>${esc(o.rec)}</span><b>${esc(o.label)}</b>${rxEvidenceHtml(ev)}<p>${esc(o.detail)}</p><small><b>Why:</b> ${esc(o.why)}</small><small><b>Avoid:</b> ${esc(o.avoid)}</small></button>`; }).join("")}</div></section>`;
}
function selectedRxOptions(){
  const defs=rxOptionDefinitions();
  const rows=[];
  Object.entries(defs).forEach(([cat,group])=>{
    group.options.filter(o=>isRxSelected(cat,o.id)).forEach(o=>rows.push({cat,title:group.title,evidence_support:evidenceForRxOption(cat,o.id),...o}));
  });
  return rows;
}
function selectedRxPlanHtml(){
  const rows=selectedRxOptions();
  if(!rows.length) return `<p class="muted">No modules selected yet. Click treatment modules above to build the clinician prescription.</p>`;
  return rows.map(o=>`<div class="selected-rx-row"><span>${esc(o.title)}</span><b>${esc(o.label)}</b>${rxEvidenceHtml(o.evidence_support)}<p>${esc(o.detail)}</p><p><strong>Rationale:</strong> ${esc(o.why)} <strong>Avoided:</strong> ${esc(o.avoid)}</p><p><strong>Evidence support:</strong> ${esc(rxEvidenceText(o.evidence_support))}</p></div>`).join("");
}
function finalRxPayload(){
  return {
    finalized_at:new Date().toISOString(),
    patient:{...profileContext(), age:state.profile.age, sex:state.profile.sex},
    selected_case:currentCaseTitle(),
    selected_modules:selectedRxOptions(),
    rx_selections:state.rxSelections,
    risk_factors:rxRiskFactors(),
    safety_checks:dynamicSafetyChecks(),
    surgery_status:surgeryDecisionStatus(),
    evidence_focus:state.chain,
    medication_gate_complete:medicationGateComplete(),
    clinician_boundary:"Final KOM-Rx records clinician-selected modules and safety gates; it is not an autonomous medical order."
  };
}
async function confirmFinalRx(){
  const payload=finalRxPayload();
  await saveProfileConfig(false);
  const saved=await api("/api/v16/rx/finalize",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  state.finalRx=saved.prescription||payload;
  state.rxFinalized=true;
  toast("Final KOM-Rx confirmed and saved locally.");
  rx();
}
function finalRxHtml(){
  const p=state.finalRx;
  if(!p) return `<section class="final-rx-panel draft"><h3>Final prescription status</h3><p>No final KOM-Rx has been confirmed yet. Select modules above, then click <b>Confirm final KOM-Rx</b>.</p></section>`;
  const stale=!state.rxFinalized;
  const rows=p.selected_modules||[];
  return `<section class="final-rx-panel ${stale?'stale':'confirmed'}"><div class="final-rx-head"><div><h3>${stale?'Draft changed after last confirmation':'Final confirmed KOM-Rx'}</h3><p>${esc(p.finalized_at||"time not recorded")} - ${esc(p.selected_case||currentCaseTitle())}</p></div><span class="badge ${stale?'amber':'green'}">${stale?'Needs reconfirmation':'Saved'}</span></div><div class="final-rx-grid">${rows.map(o=>`<div><span>${esc(o.cat)}</span><b>${esc(o.label)}</b>${rxEvidenceHtml(o.evidence_support)}<p>${esc(o.detail)}</p><p><strong>Evidence:</strong> ${esc(rxEvidenceText(o.evidence_support))}</p></div>`).join("")||'<p>No selected modules recorded.</p>'}</div><h4>Safety gates carried into final prescription</h4><div class="final-safety-list">${(p.safety_checks||[]).map(x=>`<p><b>${esc(x.gate)}</b><span class="badge ${x.status==='ACTION_REQUIRED'?'red':'green'}">${esc(x.status)}</span><br>${esc(x.decision)}</p>`).join("")}</div></section>`;
}
function rxBuilderHtml(){
  const defs=rxOptionDefinitions();
  return `<section class="rx-builder"><div class="rx-builder-head"><div><div class="eyebrow">Clinician selectable modules</div><h2>Build the final KOM-Rx by clicking treatment options</h2><p>The AI proposes concrete modules, but the clinician selects the final combination. Every click edits the draft prescription; confirmation below generates the saved final prescription.</p></div><div class="rx-risk-box"><b>High-risk factors considered</b>${rxRiskFactors().map(x=>`<span>${esc(x)}</span>`).join("")}</div></div><div class="rx-builder-grid">${Object.entries(defs).map(([cat,group])=>rxCategoryHtml(cat,group)).join("")}</div><section class="selected-rx-plan"><h3>Selected clinician prescription draft</h3>${selectedRxPlanHtml()}<div class="rx-builder-actions"><button class="btn primary" onclick="confirmFinalRx()">Confirm final KOM-Rx</button><button class="btn" onclick="saveProfileConfig(true)">Save profile and draft</button><span class="badge ${state.rxFinalized?'green':'amber'}">${state.rxFinalized?'Final prescription matches current selections':'Draft not finalized'}</span></div></section>${finalRxHtml()}</section>`;
}
function rxReviewPills(){
  const items=missingInfo();
  if(!items.length) return '<span class="rx-pill ok">Medication safety gate complete</span>';
  return items.map(x=>`<span class="rx-pill alert">${esc(x)}</span>`).join("");
}
function rxStatusTiles(){
  const checks=dynamicSafetyChecks();
  const statusClass=s=>s==="PASS"?"ok":s==="ACTION_REQUIRED"?"alert":"watch";
  return checks.slice(0,5).map(x=>`<div class="rx-status ${statusClass(x.status)}"><b>${esc(x.gate)}</b><span>${esc(x.status.replaceAll("_"," "))}</span><p>${esc(x.decision)}</p></div>`).join("");
}
function rxMiniSections(){
  return rxSections().map((r,i)=>`<article class="rx-brief"><span>${String(i).padStart(2,"0")}</span><h3>${esc(r[0])}</h3><p>${esc(r[1])}</p></article>`).join("");
}
function rxSpecialtyCard(agent,title,kind="standard"){
  return `<section class="rx-card ${kind}"><div class="rx-card-head"><span>${esc(agent.specialty||title)}</span><h3>${esc(title)}</h3></div><div class="rx-card-body">${prescriptionHtml(agent)}</div></section>`;
}
function rx(){
  const c=state.content;
  const meds=c.agents.find(a=>a.id==="medication"), ex=c.agents.find(a=>a.id==="exercise_rehab"), nu=c.agents.find(a=>a.id==="nutrition"), psy=c.agents.find(a=>a.id==="psychology"), surg=c.agents.find(a=>a.id==="surgery");
  const body = `
    <div class="rx-report-shell">
      <section class="rx-command">
        <div>
          <div class="eyebrow">Structured MDT prescription</div>
          <h2>Clinician-facing KOM-Rx report</h2>
          <p>Patient assessment, specialty prescriptions, safety negotiation and evidence routing are curated into a single auditable clinical report.</p>
        </div>
        <div class="rx-export-actions">
          <a class="btn primary" href="/api/report?format=md" target="_blank">Export Markdown</a>
          <a class="btn" href="/api/report?format=html" target="_blank">Export HTML</a>
        </div>
      </section>
      <section class="rx-priority-band">
        <div>
          <h2>Review priorities</h2>
          <p>This report supports clinician review and shared decision-making; it is not an autonomous medical order.</p>
        </div>
        <div class="rx-pill-row">${rxReviewPills()}</div>
      </section>
      ${rxBuilderHtml()}
      <section class="rx-status-board">${rxStatusTiles()}</section>
      <section class="rx-brief-grid">${rxMiniSections()}</section>
      <section class="rx-prescription-board">
        ${rxSpecialtyCard(meds,"Detailed medication and injection plan","wide")}
        ${rxSpecialtyCard(ex,"Exercise prescription","wide")}
        ${rxSpecialtyCard(nu,"Nutrition prescription")}
        ${rxSpecialtyCard(psy,"Psychology and behavior prescription")}
        ${rxSpecialtyCard(surg,"Orthopedic boundary and referral")}
      </section>
      <section class="rx-boundary-strip">
        <b>Report boundary</b>
        <span>Medication, injection, surgery, exercise, nutrition and psychology recommendations require clinician review.</span>
      </section>
    </div>`;
  pageLayout("KOM-Rx structured clinical report", "The report separates the patient assessment report, MDT treatment prescription, reasoning trail and clinician-review priorities. It is structured for clinical review rather than raw agent text.", body, "");
}

function score(){ const c=state.content; pageLayout("KOM-Score validation center", "Validation is separated into rule/model performance, expert prescription quality review and safety-event auditing.", `<div class="grid3">${c.score.map(s=>`<div class="panel"><h2>${esc(s.domain)}</h2>${s.metrics.map(x=>`<span class="badge">${esc(x)}</span>`).join("")}</div>`).join("")}</div><div class="panel process-trace"><h2>Process trace</h2><table><thead><tr><th>Stage</th><th>Artifact</th></tr></thead><tbody>${c.trace.map(t=>`<tr><td>${esc(t.stage)}</td><td>${esc(t.artifact)}</td></tr>`).join("")}</tbody></table><div class="actions"><button class="btn primary" onclick="runValidation()">Run local validation</button></div><pre id="validationOut" class="reason-box hidden"></pre></div>`, `<h3>Evidence</h3><p>The local validation endpoint checks route availability, English wording, profile controls, RAG views, MDT prescriptions, Safe-MDT negotiation and report export.</p>`); }
async function runValidation(){ const data=await api("/api/v9/validate"); const out=$("#validationOut"); out.classList.remove("hidden"); out.textContent=JSON.stringify(data,null,2); }

function settings(){ pageLayout("Settings", "Configure a model endpoint if model-based refinement is needed. The deterministic local pathway remains available without a key.", `<div class="panel"><h2>Model connection</h2><div class="field-grid"><label class="field"><b>Base URL</b><input id="baseUrl" value="https://xiaoai.plus/v1"></label><label class="field"><b>API key</b><input id="apiKey" type="password" placeholder="Paste local key"></label><label class="field"><b>Text model</b><input id="textModel" value="gpt-4o"></label><label class="field"><b>Vision model</b><input id="visionModel" value="gpt-4o"></label></div><div class="actions"><button class="btn primary" onclick="saveSettings()">Save locally</button><button class="btn" onclick="testText()">Test text model</button><button class="btn" onclick="clearSettings()">Clear local key</button></div><pre id="settingsOut" class="reason-box"></pre></div>`, `<h3>Privacy</h3><p>No private API key is bundled in the release package. Saved keys remain local to this folder.</p>`); loadSettingsStatus(); }
function payload(){ return {base_url:$("#baseUrl")?.value, api_key:$("#apiKey")?.value, text_model:$("#textModel")?.value, vision_model:$("#visionModel")?.value, temperature:0.2}; }
async function loadSettingsStatus(){ try{ const s=await api("/api/settings/llm/status"); const o=$("#settingsOut"); if(o)o.textContent=JSON.stringify(s,null,2); }catch(e){} }
async function saveSettings(){ const data=await api("/api/settings/llm/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload())}); $("#settingsOut").textContent=JSON.stringify(data,null,2); }
async function testText(){ const data=await api("/api/settings/llm/test-text",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload())}); $("#settingsOut").textContent=JSON.stringify(data,null,2); }
async function clearSettings(){ const data=await api("/api/settings/llm/clear",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}); $("#settingsOut").textContent=JSON.stringify(data,null,2); }

function bindInteractiveDelegates(){
  document.addEventListener("click", ev => {
    const flow = ev.target.closest("[data-flow]");
    if(flow){ ev.preventDefault(); selectFlowNode(flow.dataset.flow); return; }
    const q = ev.target.closest(".case-grid [data-case]");
    if(q){ ev.preventDefault(); loadCase(q.dataset.case); return; }
    const finding = ev.target.closest("[data-rad-finding]");
    if(finding){ ev.preventDefault(); selectRadFinding(finding.dataset.radFinding); return; }
    const evidence = ev.target.closest("[data-evidence]");
    if(evidence){ ev.preventDefault(); selectEvidence(evidence.dataset.evidence); return; }
  });
  Object.assign(window,{go,openFlowStep,loadCase,selectFlowNode,selectRadFinding,selectEvidence,closeEvidenceOverlay,toggleRxOption,confirmFinalRx,rag,rad,dashboard,rx,runRad,showCatalog,runCaseQuery,loadEvidenceDbFromControls,increaseEvidenceVisible,updateProfileField,updateProfileFieldFast,commitProfileField,saveProfileConfig,generateProfile,openCalc,closeCalc,applyCalc,runValidation,runNegotiation,loadSafetyScenario,askAgent,quickAgentPrompt});
}
function render(){ const r=route(); state.page=r; ({dashboard,assess,rad,risk,rag,mdt,safe,rx,score,settings}[r]||dashboard)(); }
bindInteractiveDelegates();
init().catch(e=>{ $("#app").innerHTML=`<div class="screen"><div class="panel"><h1>Unable to load KOM workbench</h1><p>${esc(e.message)}</p></div></div>`; });

