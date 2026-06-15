export type TermDefinition = {
  key: string;
  english: string;
  chinese: string;
  definition: string;
  shortDefinition: string;
};

export const termDefinitions: TermDefinition[] = [
  { key: 'KOM', english: 'Knee Osteoarthritis Manager', chinese: '膝骨关节炎智能管理系统', definition: '面向参与膝骨关节炎治疗决策医生的 AI 决策支持系统，用于在标准化病例任务中提供患者画像、治疗建议、安全审计和证据依据。', shortDefinition: '医生端 KOA 决策支持系统。' },
  { key: 'KOM-Assess', english: 'KOM assessment subsystem', chinese: 'KOM 评估子系统', definition: 'KOM 中负责患者评估的子系统，包括 KOM-Profile、KOM-Rad 和 KOM-Risk，为医生提供结构化患者画像、影像分级和纵向风险提示。', shortDefinition: '患者画像、影像分级和风险提示。' },
  { key: 'KOM-Treat', english: 'KOM treatment decision subsystem', chinese: 'KOM 治疗决策子系统', definition: 'KOM 中负责治疗建议生成的子系统，包括 KOM-KB、KOM-RAG、KOM-MDT、KOM-Rx 和 KOM-Safe，用于生成可追溯、可审计、可执行的治疗建议。', shortDefinition: '证据检索、多专科协商、处方和安全审计。' },
  { key: 'KOM-Profile', english: 'KOM patient profiling module', chinese: 'KOM 患者画像模块', definition: '将标准化病例资料转化为结构化临床画像的模块，包括症状、功能、影像、合并症、用药风险、治疗目标和复杂度象限。', shortDefinition: '标准化病例到结构化临床画像。' },
  { key: 'KOM-Rad', english: 'KOM radiographic assessment module', chinese: 'KOM 影像评估模块', definition: 'KOM-Assess 中处理膝关节 X 线结构信息的模块，其内部算法 OAK-Net 用于 KL 分级和影像征象识别。', shortDefinition: 'X 线结构分级支持。' },
  { key: 'OAK-Net', english: 'Osteoarthritis Knee X-ray Network', chinese: '膝骨关节炎 X 线结构分级网络', definition: 'KOM-Rad 内部用于膝关节 X 线结构分级的影像算法，输出 KL 分级、关节间隙狭窄、骨赘、软骨下硬化和不确定性信息。', shortDefinition: 'KOM-Rad 的 X 线分级算法。' },
  { key: 'KOM-Risk', english: 'KOM longitudinal risk module', chinese: 'KOM 纵向风险模块', definition: 'KOM-Assess 中用于估计 KL 结构进展、全膝置换或膝手术需求，以及症状/功能恶化风险的模块。', shortDefinition: '结构、手术和症状/功能风险提示。' },
  { key: 'KOM-KB', english: 'KOM evidence knowledge base', chinese: 'KOM 循证知识库', definition: '包含膝骨关节炎指南、系统综述、随机对照试验、观察性研究、安全性证据和实施资料的本地证据库。', shortDefinition: '本地 KOA 证据库。' },
  { key: 'KOM-RAG', english: 'KOM guideline-anchored retrieval module', chinese: 'KOM 指南锚定检索模块', definition: '从 KOM-KB 中检索与当前病例和治疗问题相关证据的模块。它不仅依赖语义相似度，还利用指南锚点、证据层级、专科标签和安全标签进行排序和筛选。', shortDefinition: '带指南锚点和安全标签的证据检索。' },
  { key: 'naive RAG baseline', english: 'naive RAG baseline', chinese: '朴素 RAG 基线', definition: '用于与 KOM-RAG 比较的简单检索增强生成流程。它使用同一批查询和同一证据库，但只执行单阶段向量相似度 top-k 检索；不使用指南锚点、不使用证据层级、不使用专科路由、不使用安全标签、不使用图结构关系、不使用证据仲裁。Naive RAG baseline = single-stage vector top-k retrieval over the same evidence library, without guideline anchors, evidence hierarchy, specialty routing, safety labels, graph links, or evidence arbitration.', shortDefinition: '同库同 query 的单阶段向量 top-k 检索。' },
  { key: 'KOM-MDT', english: 'KOM multidisciplinary team module', chinese: 'KOM 多专科协商模块', definition: '由运动医学、体重营养代谢、心理行为、骨科综合和证据仲裁智能体组成的多专科协商流程，用于生成并交叉审查治疗建议。', shortDefinition: '多专科智能体协商和交叉审查。' },
  { key: 'KOM-Rx', english: 'KOM prescription module', chinese: 'KOM 处方生成模块', definition: '将 KOM-MDT 的协商结果转化为医生可阅读、可修改、可执行的结构化治疗建议。', shortDefinition: '结构化治疗建议输出。' },
  { key: 'KOM-Safe', english: 'KOM safety audit module', chinese: 'KOM 安全审计模块', definition: '独立复核治疗建议中的安全风险，包括 NSAIDs 禁忌、胃肠道风险、心血管风险、肾功能风险、注射边界、运动风险、手术转诊边界和随访升级路径。', shortDefinition: '独立安全风险审计。' },
  { key: 'KOM-Score', english: 'KOM multi-source evaluation framework', chinese: 'KOM 多源评价框架', definition: '结合高年资医生评价、确定性规则评分和专科化评价者评分，用于评价处方质量、安全性、指南一致性、个体化、可执行性和错误类型。', shortDefinition: '处方质量和错误类型评价框架。' },
  { key: 'KOM-Sim', english: 'KOM clinician simulation framework', chinese: 'KOM 医生模拟交互框架', definition: '多中心、不同年资医生完成标准化病例处方任务的人机交互模拟框架。26 名医生每人完成 30 个任务，共形成 780 条医生–任务级处方记录。', shortDefinition: '26 名医生 × 30 个标准化任务。' },
  { key: 'Full KOM', english: 'Full KOM workflow', chinese: '完整 KOM 工作流', definition: '包含 KOM-Assess、KOM-RAG、KOM-MDT、KOM-Rx 和 KOM-Safe 的完整系统工作流。', shortDefinition: '完整系统流程。' },
  { key: 'KOM w/o RAG', english: 'KOM without RAG', chinese: '去除证据检索的 KOM', definition: '关闭 KOM-RAG，不使用外部证据检索，仅保留其余 KOM 工作流的消融组。', shortDefinition: '去除证据检索的消融组。' },
  { key: 'KOM w/o MDT', english: 'KOM without MDT', chinese: '去除多专科协商的 KOM', definition: '关闭 KOM-MDT，不执行多专科初稿、交叉质疑和证据仲裁的消融组。', shortDefinition: '去除多专科协商的消融组。' },
  { key: 'Direct LLM', english: 'Direct LLM baseline', chinese: '直接 LLM 基线', definition: '不启用 KOM 工作流，仅根据病例资料直接生成治疗建议的基线。', shortDefinition: '无 KOM 结构的直接生成基线。' },
  { key: 'Clinician alone', english: 'Clinician alone', chinese: '医生独立处方', definition: '医生仅查看标准化病例资料并独立书写处方。', shortDefinition: '无 KOM 支持的医生处方。' },
  { key: 'Clinician + KOM', english: 'Clinician with KOM recommendation', chinese: '医生使用 KOM 建议', definition: '医生查看标准化病例资料和 KOM 处方建议后书写处方。', shortDefinition: '医生查看 KOM 建议后书写处方。' },
  { key: 'Clinician + KOM-R', english: 'Clinician with KOM recommendation and rationale', chinese: '医生使用 KOM 建议及解释', definition: '医生查看标准化病例资料、KOM 处方建议和 KOM rationale 后书写处方。R 表示 rationale。', shortDefinition: '医生查看 KOM 建议和解释后书写处方。' },
  { key: 'KOM standalone', english: 'KOM standalone', chinese: 'KOM 独立处方', definition: '完整 KOM 在无医生修改条件下生成的系统基准处方，用于展示系统独立输出水平。', shortDefinition: '完整 KOM 独立输出。' },
  { key: 'physician–task prescription record', english: 'physician-task prescription record', chinese: '医生–任务级处方记录', definition: '一名医生在一个标准化处方任务中生成的一条处方记录。KOM-Sim 中 26 名医生每人完成 30 个任务，共 780 条记录。它不是 780 名医生，也不是 780 个独立病例。', shortDefinition: '一名医生在一个任务中生成的一条处方。' },
  { key: 'safety-critical error', english: 'safety-critical error', chinese: '安全关键错误', definition: '可能导致患者实质性伤害、违反明确禁忌证、错误建议或延误必要转诊、错误使用高风险药物，或遗漏关键安全门控的处方问题。', shortDefinition: '可能造成实质性伤害或遗漏关键安全门控。' },
  { key: 'clinically relevant error', english: 'clinically relevant error', chinese: '临床决策相关错误', definition: '可能改变治疗路径、降低治疗质量或造成重要管理遗漏，但通常不直接构成立即严重伤害的处方问题。', shortDefinition: '影响治疗路径或质量的重要错误。' },
  { key: 'minor error', english: 'minor error', chinese: '轻微错误', definition: '措辞、监测建议、细节完整性或非关键随访提示不足，不实质性改变主要治疗路径或安全性。', shortDefinition: '不改变主要路径的细节问题。' },
  { key: 'safety-critical error rate', english: 'safety-critical error rate', chinese: '安全关键错误率', definition: '每 100 条医生–任务级处方记录或每 100 个系统处方输出中的安全关键错误数。', shortDefinition: '安全关键错误数 / 处方记录数 × 100。' }
];

export function getTerm(key: string) {
  return termDefinitions.find((term) => term.key === key);
}
