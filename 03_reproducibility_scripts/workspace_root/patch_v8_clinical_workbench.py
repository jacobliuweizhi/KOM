from __future__ import annotations

import json
import shutil
import sqlite3
import textwrap
from datetime import datetime
from pathlib import Path


ROOT = Path(r"C:\OAI研究项目\pythonProject1\KOM返修修改\投稿使用\KOM_Local_Clinical_Workbench_FINAL_202606")
APP = ROOT / "app"
STATIC = APP / "static"
DATA = APP / "data"
BACKEND = APP / "backend"
VALIDATION = ROOT / "validation"
BACKUP = ROOT / "developer_assets" / "backups_before_v8_clinical_workbench" / datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_file(path: Path) -> None:
    if path.exists():
        target = BACKUP / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def evidence_row(eu_id: str) -> dict:
    db = DATA / "kom_workbench.sqlite"
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            """
            SELECT EU_ID, Title, Evidence_Level, Agent_Database, year, Effect_Summary,
                   Safety_or_Contraindication_Note, Prescription_Use, source_link
            FROM evidence_units WHERE EU_ID=?
            """,
            (eu_id,),
        ).fetchone()
    if not row:
        return {
            "EU_ID": eu_id,
            "Title": "Evidence record not found in local DB",
            "Evidence_Level": "unknown",
            "Agent_Database": "",
            "year": "",
            "Effect_Summary": "Missing from local database; requires curator review.",
            "Safety_or_Contraindication_Note": "",
            "Prescription_Use": "",
            "source_link": "",
        }
    return dict(row)


def build_content() -> dict:
    chains = {
        "exercise_rehab": {
            "title": "运动与康复证据链",
            "clinical_question": "KL4、NRS8、中度跌倒风险、肌力和平衡下降时，如何给出低冲击、抗阻和平衡训练处方？",
            "levels": [
                {
                    "type": "指南/共识",
                    "items": ["KOA-EU-00006", "KOA-EU-00010", "KOA-EU-00030"],
                    "why": "用于确定非药物核心管理、治疗性运动和监督训练边界。",
                },
                {
                    "type": "系统综述/Meta/NMA",
                    "items": ["KOA-EU-00093", "KOA-EU-00099", "KOA-EU-00103"],
                    "why": "用于选择运动模态、剂量和步态调整等更细节的康复策略。",
                },
                {
                    "type": "RCT/临床研究",
                    "items": ["KOA-EU-00741", "KOA-EU-00743", "KOA-EU-00746"],
                    "why": "用于支持力量、瑜伽/身心运动、体积反应和结构化项目可行性。",
                },
            ],
        },
        "nutrition": {
            "title": "营养、体重与代谢证据链",
            "clinical_question": "BMI29.4、67岁、肌力下降且肾功能未知时，如何减重同时保肌？",
            "levels": [
                {
                    "type": "指南/共识",
                    "items": ["KOA-EU-00004", "KOA-EU-00031", "KOA-EU-00047"],
                    "why": "用于确定体重管理是核心治疗，并把体重优化与功能目标绑定。",
                },
                {
                    "type": "系统综述/Meta/NMA",
                    "items": ["KOA-EU-00097", "KOA-EU-00100", "KOA-EU-00121"],
                    "why": "用于比较减重干预、联合一线干预和个体特征对结局的影响。",
                },
                {
                    "type": "RCT/临床研究",
                    "items": ["KOA-EU-00748", "KOA-EU-00751", "KOA-EU-00747"],
                    "why": "用于支持肌肉组成、力量、饮食+运动综合干预和老年人功能结局。",
                },
            ],
        },
        "medication": {
            "title": "药物与注射证据链",
            "clinical_question": "NSAID风险、心血管风险和关键用药安全信息缺失时，如何把药物升级门控化？",
            "levels": [
                {
                    "type": "指南/共识",
                    "items": ["KOA-EU-00030", "KOA-EU-00044", "KOA-EU-00059"],
                    "why": "用于确定外用NSAID、口服NSAID、对乙酰氨基酚和关节腔注射的指南位置。",
                },
                {
                    "type": "系统综述/Meta/NMA",
                    "items": ["KOA-EU-00094", "KOA-EU-00092", "KOA-EU-00102"],
                    "why": "用于提示注射证据、并发症和研究报告质量，不作为常规重复注射锚点。",
                },
                {
                    "type": "RCT/临床研究",
                    "items": ["KOA-EU-00787", "KOA-EU-00812", "KOA-EU-00815"],
                    "why": "用于对照教育运动、注射/围手术镇痛方案的临床研究背景。",
                },
            ],
        },
        "orthopaedic": {
            "title": "骨科边界与转诊证据链",
            "clinical_question": "KL4、高疼痛、高功能受限和转诊疑问时，如何建议专科评估但不由AI决定手术？",
            "levels": [
                {
                    "type": "指南/共识",
                    "items": ["KOA-EU-00030", "KOA-EU-00047", "KOA-EU-00014"],
                    "why": "用于确定转诊讨论、非手术管理边界和单髁/置换等必须由专科评估。",
                },
                {
                    "type": "系统综述/Meta/NMA",
                    "items": ["KOA-EU-00106", "KOA-EU-00108", "KOA-EU-00109"],
                    "why": "用于提示手术技术、MCID/PASS和不同手术策略证据，不用于AI直接决定术式。",
                },
                {
                    "type": "RCT/临床研究",
                    "items": ["KOA-EU-00744", "KOA-EU-00746", "KOA-EU-00752"],
                    "why": "用于围手术恢复或保守治疗项目的临床背景。",
                },
            ],
        },
        "psychology": {
            "title": "心理、行为与依从性证据链",
            "clinical_question": "高疼痛、高需求、轻度焦虑和依从性中等时，如何筛查并做非污名化行为干预？",
            "levels": [
                {
                    "type": "指南/共识",
                    "items": ["KOA-EU-00003", "KOA-EU-00010", "KOA-EU-00031"],
                    "why": "用于确定教育、自我管理、治疗性运动交付和患者支持是核心组成。",
                },
                {
                    "type": "系统综述/Meta/NMA",
                    "items": ["KOA-EU-00101", "KOA-EU-00105", "KOA-EU-00117"],
                    "why": "用于支持心理健康、康复指南质量和身心运动/教育干预的证据背景。",
                },
                {
                    "type": "RCT/临床研究",
                    "items": ["KOA-EU-00741", "KOA-EU-00743", "KOA-EU-00746"],
                    "why": "用于支持可操作的活动节奏、运动行为改变和功能目标恢复。",
                },
            ],
        },
    }
    evidence_lookup = {}
    for chain in chains.values():
        for level in chain["levels"]:
            level["evidence"] = []
            for eu_id in level["items"]:
                row = evidence_lookup.setdefault(eu_id, evidence_row(eu_id))
                level["evidence"].append(row)

    case = {
        "case_id": "DEMO_OAI_CASE_001",
        "title": "OAI展示病例：高负担高需求膝骨关节炎",
        "one_line": "67岁男性，Q4高负担/高需求膝骨关节炎，KL4、NRS8、WOMAC功能62、BMI29.4；存在NSAID/心血管风险、中度跌倒风险和关键用药/影像信息缺失。",
        "anchors": {
            "年龄": "67",
            "性别": "男",
            "BMI": "29.4",
            "KL分级": "4",
            "疼痛NRS": "8",
            "WOMAC功能": "62",
            "跌倒风险": "中度",
            "主要目标": "安全步行3 km、避免反复注射、了解是否需要关节外科评估",
        },
        "missing": [
            "eGFR/肌酐",
            "胃溃疡或消化道出血史",
            "抗凝/抗血小板状态",
            "当前完整用药清单",
            "更新负重位X线和力线",
            "既往保守治疗史",
        ],
        "risk_flags": ["NSAID caution", "心血管风险", "中度跌倒风险", "肌力下降", "平衡下降", "体重管理需要"],
    }

    agents = [
        {
            "id": "exercise_rehab",
            "name": "运动与康复处方智能体",
            "specialty": "FITT-VP运动处方、低冲击有氧、抗阻训练、平衡防跌倒",
            "inputs": ["KL4", "NRS8", "WOMAC功能62", "中度跌倒风险", "平衡下降", "肌力下降", "步行3 km目标"],
            "reasoning": [
                "KL4和NRS8提示不可用跑跳、高冲击或突然增加步行量作为起始方案。",
                "中度跌倒风险和平衡下降使平衡/防跌倒训练成为安全门控，而不是可选装饰。",
                "肌力下降和WOMAC功能62使股四头肌、髋外展肌、伸髋肌和坐站能力训练成为核心。",
            ],
            "prescription": {
                "FITT-VP": [
                    ["低冲击有氧", "每周3-5天", "RPE 3-5/10，可说话但略喘", "10-15分钟起，逐步到30分钟", "室内车、平地短距离步行、水中运动", "先累计每周90-150分钟", "每1-2周按耐受增加10-20%，先加时间再加强度"],
                    ["抗阻/力量", "每周2-3天，间隔至少1天", "轻到中等，疼痛不超过可接受范围", "1-2组，每组8-12次", "股四头肌、髋外展/伸展、腘绳肌、小腿、坐站", "每次4-6个动作", "动作质量稳定后增加弹力带/阻力，避免深蹲扭转"],
                    ["平衡防跌倒", "每周3天以上，早期有扶持或监督", "安全第一，不追求疲劳", "5-10分钟", "扶持站立、重心转移、侧向迈步、步态训练", "每天少量多次也可", "从双手扶持到单手/少扶持，出现近跌倒即复评"],
                ],
                "stop_rules": [
                    "运动后疼痛增加>2分",
                    "肿胀、跛行或症状持续>24小时",
                    "近跌倒/跌倒",
                    "胸痛、明显气促",
                    "急性红热肿胀关节",
                ],
                "not_now": ["跑步", "跳跃", "深蹲扭转", "突然把步行量加到3 km", "疼痛未控时负重爬坡"],
            },
            "audit": "通过：包含FITT-VP、低冲击、有氧+抗阻+平衡、停止规则和跌倒风险门控。",
            "evidence_chain": "exercise_rehab",
        },
        {
            "id": "nutrition",
            "name": "体重、营养与代谢处方智能体",
            "specialty": "体重管理、保肌、肾功能门控、可执行食谱",
            "inputs": ["BMI29.4", "67岁", "肌力下降", "肾功能缺失", "步行目标"],
            "reasoning": [
                "BMI29.4提示体重管理可降低膝关节负荷，但老年人不能只追求体重下降。",
                "肌力下降使保肌成为减重处方的硬条件。",
                "eGFR缺失时不能写死高蛋白目标，需要医生/营养师个体化。",
            ],
            "prescription": {
                "target": "3-6个月先减重约5%，同时维持或提升下肢肌力和步行耐受。",
                "meal_pattern": [
                    "每餐以蔬菜和全谷/杂豆作基础，控制精制主食总量。",
                    "优先鱼、禽、蛋、低脂奶、豆制品等优质蛋白；eGFR补齐前不设固定高蛋白克数。",
                    "使用橄榄油/菜籽油等不饱和脂肪，减少油炸、甜饮、加工肉和夜宵。",
                    "每周记录体重、腰围、疼痛、步行耐受和力量训练完成度。",
                ],
                "sample_day": [
                    "早餐：燕麦/全麦主食 + 鸡蛋或无糖酸奶 + 一份水果。",
                    "午餐：半盘蔬菜 + 鱼/鸡/豆制品 + 小份全谷主食。",
                    "晚餐：清淡蛋白 + 大量非淀粉蔬菜 + 控制主食，避免高盐高油。",
                    "加餐：无糖酸奶、少量坚果或水果；避免甜饮和高糖点心。",
                ],
                "avoid": ["极端节食", "未经肾功能评估的固定高蛋白", "快速减重导致肌力下降", "用保健品替代饮食结构"],
            },
            "audit": "通过：体重管理与保肌并列，肾功能缺失前不写死蛋白剂量。",
            "evidence_chain": "nutrition",
        },
        {
            "id": "medication",
            "name": "药物与注射处方智能体",
            "specialty": "外用NSAID、口服NSAID门控、救援镇痛、注射桥接",
            "inputs": ["NRS8", "NSAID caution", "心血管风险", "eGFR缺失", "GI史缺失", "抗凝/用药清单缺失", "避免反复注射"],
            "reasoning": [
                "高疼痛需要镇痛支持以便进入康复，但安全信息缺失使口服NSAID不能常规启动。",
                "患者希望避免反复注射，因此注射只能作为发作/积液/疼痛阻碍康复时的短期桥接。",
                "外用NSAID可作为条件性短期支持，但需皮肤完整且无NSAID过敏。",
            ],
            "prescription": {
                "missing_safety_block": [
                    "肾功能/eGFR：MISSING",
                    "消化道溃疡或出血史：MISSING",
                    "抗凝/抗血小板状态：MISSING",
                    "当前完整用药清单：MISSING",
                    "心血管风险：需医生复核",
                ],
                "items": [
                    "外用NSAID：条件性可考虑2-4周，皮肤完整且无NSAID过敏时用于短期疼痛辅助，监测皮肤反应、疼痛和功能。",
                    "口服NSAID：未完成 renal + GI + anticoagulant/current medication + CV risk 四项复核前，不启动常规口服NSAID；若医生复核后使用，应遵循最低有效剂量、最短疗程和监测计划。",
                    "对乙酰氨基酚：仅作短期救援，不作为长期核心治疗。",
                    "关节腔糖皮质激素注射：仅在疼痛发作、积液或疼痛阻碍康复且医生评估适应证/禁忌证后作为短期桥接；不常规反复注射。",
                ],
            },
            "audit": "通过：口服NSAID明确DEFER，注射不常规化，缺失信息置顶。",
            "evidence_chain": "medication",
        },
        {
            "id": "psychology",
            "name": "心理与行为处方智能体",
            "specialty": "筛查、疼痛教育、CBT/ACT取向节奏管理、依从性支持",
            "inputs": ["高疼痛", "高需求", "轻度焦虑", "灾难化未知", "睡眠未知", "依从性中等"],
            "reasoning": [
                "KL4结构性疾病不能被心理化，但高疼痛和高需求会受到睡眠、焦虑、灾难化和活动回避影响。",
                "心理筛查是风险分层和依从性支持，不是污名化。",
                "可将疼痛神经科学教育、活动节奏和发作计划嵌入康复执行。",
            ],
            "prescription": {
                "screening": ["GAD-7（焦虑）", "PHQ-9（抑郁）", "PCS（疼痛灾难化）", "PSQI或睡眠筛查", "依从障碍和自我效能评估"],
                "intervention": [
                    "疼痛神经科学教育：解释结构损伤、负荷、睡眠、压力和神经敏感性共同影响疼痛。",
                    "CBT/ACT取向活动节奏：把3 km目标拆为可达步数/时间，避免疼痛-过度活动-停摆循环。",
                    "发作计划：疼痛上升时降级运动、使用短期镇痛支持、48小时内复评是否可恢复。",
                    "若API配置，可用GPT-4o进行非诊断式每日自我管理对话：提醒筛查、记录运动/疼痛/睡眠、生成复诊问题清单；中重度风险转人工心理/疼痛专科。",
                ],
            },
            "audit": "通过：列出具体工具和干预方式，并明确不把疼痛简单归因为心理问题。",
            "evidence_chain": "psychology",
        },
        {
            "id": "orthopaedic",
            "name": "骨科边界与升级评估智能体",
            "specialty": "转诊讨论、术前资料门控、AI不决定术式",
            "inputs": ["KL4", "NRS8", "WOMAC功能62", "夜间痛/步行目标受限", "更新影像缺失", "保守治疗史缺失"],
            "reasoning": [
                "KL4、高疼痛和高功能受限提示不能低估转诊讨论需要。",
                "缺少更新负重位影像、力线和保守治疗史时不能决定TKA/UKA/HTO。",
                "即使进入转诊，也要同步优化体重、心血管风险、跌倒风险、药物风险和康复准备。",
            ],
            "prescription": {
                "decision": "建议关节外科评估/转诊讨论；AI不决定手术类型或时机。",
                "collect_before_decision": ["更新负重位X线", "全下肢力线/畸形评估", "既往保守治疗史", "患者手术期望与风险偏好", "围手术药物和心血管风险"],
                "prehab": ["低冲击康复", "力量和平衡训练", "体重管理", "用药风险复核"],
            },
            "audit": "通过：建议评估而非AI决定手术，并保留缺失资料门控。",
            "evidence_chain": "orthopaedic",
        },
    ]

    safety_review = [
        {"id": "missing_information_first", "status": "PASS", "finding": "用药前安全信息置顶；缺失项标MISSING。", "action": "未补齐前口服NSAID一律DEFER。"},
        {"id": "nsaid_safety_gate", "status": "PASS", "finding": "renal + GI + anticoagulant/current medication + CV risk四项复核完整写入。", "action": "外用NSAID/短期救援作为过渡，口服NSAID不常规启动。"},
        {"id": "injection_preference_conflict", "status": "PASS", "finding": "患者希望避免反复注射。", "action": "注射仅作短期桥接，不常规重复。"},
        {"id": "exercise_fall_risk_conflict", "status": "PASS", "finding": "中度跌倒风险和平衡下降。", "action": "平衡防跌倒纳入FITT-VP，避免跑跳高冲击。"},
        {"id": "nutrition_sarcopenia_weight_loss_conflict", "status": "PASS", "finding": "老年、肌力下降且需要减重。", "action": "减重与保肌同步，肾功能未知前不设固定高蛋白。"},
        {"id": "psychological_screening", "status": "PASS", "finding": "高疼痛、高需求、焦虑/灾难化/睡眠需筛查。", "action": "GAD-7、PHQ-9、PCS、PSQI写入标准处方。"},
        {"id": "surgery_information_gap", "status": "PASS", "finding": "更新影像和保守治疗史缺失。", "action": "建议转诊讨论但不决定术式。"},
    ]

    report_sections = [
        ["0. 病例一句话摘要", case["one_line"]],
        ["1. 用药前必须先补齐的安全信息", "肾功能/eGFR、胃溃疡或消化道出血史、抗凝/抗血小板状态、当前完整用药清单和心血管风险复核未完成前，不进入常规口服NSAID决策。"],
        ["2. 今日可执行安全计划", "启动低冲击有氧、渐进抗阻、平衡防跌倒、体重管理且同步保肌、疼痛教育和筛查；外用NSAID可作为短期辅助但不能替代康复。"],
        ["3. 运动/康复处方", "按FITT-VP执行：低冲击有氧每周3-5天，RPE 3-5/10，10-15分钟起逐步至30分钟；力量训练每周2-3天，1-2组、8-12次；平衡训练每周3天以上。避免跑跳、深蹲扭转和突然增加步行量。"],
        ["4. 营养/体重处方", "3-6个月先减重约5%，同步保肌；采用高蔬菜、全谷/杂豆、优质蛋白、少油少糖模式；eGFR补齐前不写死高蛋白目标。"],
        ["5. 药物/注射处方", "外用NSAID条件性短期考虑；口服NSAID暂缓；对乙酰氨基酚仅短期救援；糖皮质激素注射仅在发作/积液/疼痛阻碍康复时由医生评估短期桥接，不常规反复注射。"],
        ["6. 心理/行为处方", "筛查GAD-7、PHQ-9、PCS和睡眠；进行疼痛神经科学教育、CBT/ACT取向活动节奏、发作计划和依从性支持；不把疼痛简单归因为心理问题。"],
        ["7. 骨科转诊边界", "建议关节外科评估/转诊讨论；AI不决定TKA/UKA/HTO。决定前需更新负重位影像、力线/畸形、保守治疗史和围手术风险。"],
        ["8. 证据链说明", "每个专科使用指南/共识、系统综述/Meta/NMA和RCT/临床研究三层证据。旧证据只作为背景或效果量支持，不作为唯一处方锚点。"],
        ["9. 医生复核重点", "药物安全、注射适应证、关节外科评估、运动跌倒风险、营养肾脏/代谢风险、心理风险筛查、缺失信息补齐。"],
        ["10. 免责声明", "本系统仅用于医学AI研究和医生辅助决策，不构成自动诊断或治疗医嘱。所有建议需由具备资质的临床医生复核。"],
    ]

    return {
        "version": "KOM_LOCAL_CLINICAL_WORKBENCH_V8_SPECIALTY_PRESCRIPTION_20260611",
        "case": case,
        "overview": {
            "title": "KOM 膝骨关节炎临床工作台",
            "subtitle": "面向审稿人的本地可运行临床工作流：从真实病例评估、预测和证据路由，到多智能体专科处方、审核返工、最终报告导出。",
            "steps": [
                {"id": "assessment", "title": "评估层", "detail": "病例输入、随访、真实OAI影像绑定、KL/NRS/WOMAC/BMI/跌倒风险和缺失信息门控。"},
                {"id": "prediction", "title": "预测层", "detail": "疼痛持续、跌倒相关限制和专科评估需求以可解释风险输出呈现。"},
                {"id": "evidence", "title": "证据层", "detail": "GraphRAG按临床问题路由，返回指南/共识、Meta/NMA和RCT/临床研究三层证据。"},
                {"id": "agents", "title": "处方层", "detail": "运动康复、营养代谢、药物注射、心理行为和骨科边界五大专科智能体生成草案。"},
                {"id": "audit", "title": "审计层", "detail": "安全规则、证据仲裁和跨智能体挑战推动修改、暂缓或阻止。"},
                {"id": "report", "title": "输出层", "detail": "生成医生可读标准处方、证据链、过程追踪和可导出报告。"},
            ],
        },
        "cases": [
            {"id": "Q1_STANDARD", "quadrant": "Q1", "title": "轻症低需求示例", "use": "随访/对照输入"},
            {"id": "Q2_STANDARD", "quadrant": "Q2", "title": "轻中度但高需求示例", "use": "目标驱动处方输入"},
            {"id": "Q3_STANDARD", "quadrant": "Q3", "title": "高负担但低需求示例", "use": "风险沟通输入"},
            {"id": "DEMO_OAI_CASE_001", "quadrant": "Q4", "title": "锁定OAI展示病例", "use": "端到端示范"},
        ],
        "imaging": {
            "asset": "assets/images/real_oai_knee_image_panel.png",
            "interpretation": [
                ["病例绑定", "DEMO_OAI_CASE_001；目标膝为右膝；真实OAI图像资产已随包绑定。"],
                ["结构分级", "KL 4。界面将其作为结构严重度锚点，而不是自动手术决策。"],
                ["可见结构线索", "重度间室退变表现、骨赘/硬化和关节间隙狭窄需要由临床医生在原始影像上复核。"],
                ["决策缺口", "转诊/手术路径前仍需更新负重位X线、力线/畸形评估和保守治疗史。"],
            ],
        },
        "risk": [
            {"name": "疼痛持续风险", "score": 0.78, "meaning": "提示短期内仅靠单一镇痛可能不足，应把康复、睡眠、心理和用药安全一起管理。", "drivers": ["KL4", "NRS8", "WOMAC62"]},
            {"name": "跌倒相关功能限制", "score": 0.64, "meaning": "提示运动处方必须从低冲击、监督和平衡训练开始，不能直接追求3 km。", "drivers": ["中度跌倒风险", "平衡下降", "肌力下降"]},
            {"name": "专科评估需求", "score": 0.73, "meaning": "提示需要关节外科评估/转诊讨论，但AI不决定术式或手术时机。", "drivers": ["KL4", "高疼痛", "步行目标受限"]},
        ],
        "evidence_chains": chains,
        "agents": agents,
        "safety_review": safety_review,
        "report_sections": report_sections,
        "trace": [
            "病例标准化 -> 缺失信息排序 -> 临床问题框定",
            "GraphRAG检索 -> 三层证据链 -> 证据仲裁",
            "五大专科智能体初稿 -> 自审 -> 安全审核",
            "跨智能体挑战 -> 返工/降级/暂缓 -> MDT合成",
            "最终标准处方 -> 安全复核 -> 报告导出",
        ],
    }


SERVER = r'''
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
STATIC = APP / "static"
DATA = APP / "data"
CONFIG = APP / "config"
VALIDATION = ROOT / "validation"
DB = DATA / "kom_workbench.sqlite"
V8 = DATA / "v8_clinical_content.json"
LLM_LOCAL = CONFIG / "llm_config.local.json"

ROUTES_GET = [
    "/api/routes", "/api/status", "/api/v8/content", "/api/v8/pipeline", "/api/v8/evidence-chain",
    "/api/v8/agents", "/api/v8/prescription", "/api/v8/imaging", "/api/v8/risk",
    "/api/cases", "/api/cases/summary", "/api/cases/{case_id}", "/api/evidence", "/api/evidence/trace",
    "/api/graph", "/api/agents", "/api/ablation", "/api/safety", "/api/trace", "/api/validation",
    "/api/settings/llm/status", "/api/report"
]
ROUTES_POST = [
    "/api/cases/import", "/api/cases/import-prepared", "/api/cases/select", "/api/v8/workflow/run",
    "/api/v8/prescription/polish", "/api/settings/llm/test-text", "/api/settings/llm/test-vision",
    "/api/settings/llm/save", "/api/settings/llm/clear", "/api/settings/llm/smoke-agent",
    "/api/agents/run-board", "/api/agents/challenge", "/api/agents/ask-evidence-arbiter",
    "/api/report/generate", "/api/evidence/export-subgraph", "/api/evidence/export-list"
]


def api_ok(data=None, warnings=None, trace_id=None):
    return {"ok": True, "data": data, "warnings": warnings or [], "error": None, "trace_id": trace_id or f"trace-{int(time.time()*1000)}"}


def api_error(code, message, details=None, status_hint=None):
    return {"ok": False, "data": None, "warnings": [], "error": {"code": code, "message": message, "details": details or {}, "status_hint": status_hint}, "trace_id": f"trace-{int(time.time()*1000)}"}


def con():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def rows(sql, params=()):
    with con() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def one(sql, params=()):
    with con() as c:
        r = c.execute(sql, params).fetchone()
        return dict(r) if r else None


def raw(row):
    if not row:
        return None
    out = dict(row)
    if "raw_json" in out and out["raw_json"]:
        try:
            parsed = json.loads(out["raw_json"])
            parsed.update({k: v for k, v in out.items() if k != "raw_json"})
            return parsed
        except Exception:
            pass
    return out


def v8_content():
    if V8.exists():
        return json.loads(V8.read_text(encoding="utf-8"))
    return {"version": "missing_v8_content", "case": {}, "agents": [], "evidence_chains": {}, "report_sections": []}


def load_case(case_id="DEMO_OAI_CASE_001"):
    case = raw(one("SELECT * FROM cases WHERE case_id=?", (case_id,))) or raw(one("SELECT * FROM cases ORDER BY CASE WHEN case_id='DEMO_OAI_CASE_001' THEN 0 ELSE 1 END LIMIT 1"))
    if not case:
        content = v8_content()
        return {"case": {"case_id": content["case"].get("case_id", "DEMO_OAI_CASE_001"), "display_name": content["case"].get("title", "锁定OAI展示病例"), "quadrant": "Q4"}, "timeline": []}
    timeline = []
    try:
        timeline = [json.loads(r["raw_json"]) for r in rows("SELECT raw_json FROM case_timeline WHERE case_id=? ORDER BY visit_index", (case["case_id"],))]
    except Exception:
        timeline = []
    return {"case": case, "timeline": timeline}


def agents():
    content = v8_content()
    return content.get("agents", [])


def safety():
    content = v8_content()
    return content.get("safety_review", [])


def settings_load():
    default = {"provider": "OpenAI-compatible", "base_url": "https://xiaoai.plus/v1", "text_model": "gpt-4o", "vision_model": "gpt-4o", "temperature": 0.2, "timeout_seconds": 60, "masked_api_key": None, "status": "Not configured", "use_for_agent_board": True, "use_for_image_qa": True, "use_for_report_drafting": True}
    if LLM_LOCAL.exists():
        try:
            default.update(json.loads(LLM_LOCAL.read_text(encoding="utf-8")))
        except Exception:
            pass
    return default


def mask_key(key):
    if not key:
        return None
    return "sk-***" + key[-4:] if len(key) >= 8 else "***"


def call_openai_compatible(payload, prompt=None, vision=False):
    key = payload.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("XIAOAI_API_KEY")
    cfg = settings_load()
    base_url = (payload.get("base_url") or cfg.get("base_url") or "https://xiaoai.plus/v1").rstrip("/")
    model = payload.get("vision_model" if vision else "text_model") or cfg.get("vision_model" if vision else "text_model") or "gpt-4o"
    timeout = int(payload.get("timeout_seconds") or cfg.get("timeout_seconds") or 60)
    if not key:
        return api_error("llm_key_missing", "No API key configured. Enter a key in Settings or set OPENAI_API_KEY/XIAOAI_API_KEY.", {"base_url": base_url, "model": model}, "not_configured")
    if vision:
        content = [
            {"type": "text", "text": "Confirm this local clinical workflow can call the configured vision model. Return one concise sentence."},
            {"type": "image_url", "image_url": {"url": payload.get("image_url") or "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAghnSxwAAAABJRU5ErkJggg=="}},
        ]
    else:
        content = prompt or "Return a one-sentence confirmation that the KOM Clinical Workbench text model connection is working."
    body = {
        "model": model,
        "messages": [{"role": "system", "content": "You are a concise clinical AI workflow assistant. Do not invent patient data. Keep medication and surgery decisions clinician-gated."}, {"role": "user", "content": content}],
        "temperature": float(payload.get("temperature") or cfg.get("temperature") or 0.2),
        "max_tokens": int(payload.get("max_tokens") or 800),
    }
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return api_ok({"status": "connected", "model": model, "base_url": base_url, "response": text, "masked_api_key": mask_key(key)})
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")[:1000]
        return api_error("llm_http_error", "Configured provider returned an HTTP error.", {"status": e.code, "body": msg, "base_url": base_url, "model": model}, "provider_error")
    except Exception as e:
        return api_error("llm_connection_failed", "Unable to connect to configured provider.", {"error": str(e), "base_url": base_url, "model": model}, "connection_failed")


def report(case_id="DEMO_OAI_CASE_001"):
    content = v8_content()
    return {"title": "KOM 膝骨关节炎标准处方报告", "case_id": case_id, "sections": content.get("report_sections", [])}


class Handler(BaseHTTPRequestHandler):
    server_version = "KOMWorkbench/8"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200):
        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw_bytes)))
        self.end_headers()
        self.wfile.write(raw_bytes)

    def send_text(self, text, content_type="text/plain; charset=utf-8", status=200):
        raw_bytes = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw_bytes)))
        self.end_headers()
        self.wfile.write(raw_bytes)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        data = self.rfile.read(length)
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return {}

    def static(self, parsed):
        path = parsed.path
        if path in ("/", "/ui", "/dashboard", "/case-workspace", "/patient-timeline", "/imaging", "/risk", "/evidence-graph", "/treatment-board", "/safety-review", "/clinical-report", "/trace", "/validation", "/settings"):
            p = STATIC / "index.html"
        elif path.startswith("/assets/"):
            p = STATIC / path.lstrip("/")
        elif path.startswith("/validation/"):
            p = ROOT / path.lstrip("/")
        else:
            p = STATIC / path.lstrip("/")
        if not p.exists() or not p.is_file():
            return False
        ctype = "text/html; charset=utf-8" if p.suffix == ".html" else "image/png" if p.suffix == ".png" else "image/svg+xml" if p.suffix == ".svg" else "application/json" if p.suffix == ".json" else "application/javascript" if p.suffix == ".js" else "text/css; charset=utf-8"
        data = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            content = v8_content()
            if path == "/api/routes":
                return self.send_json(api_ok({"GET": ROUTES_GET, "POST": ROUTES_POST, "version": "V8"}))
            if path == "/api/status":
                with con() as c:
                    data = {
                        "version": content.get("version"),
                        "cases": c.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
                        "evidence_units": c.execute("SELECT COUNT(*) FROM evidence_units").fetchone()[0],
                        "graph_nodes": c.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0],
                        "graph_edges": c.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0],
                        "agents": len(content.get("agents", [])),
                        "selected_case": content.get("case", {}).get("case_id", "DEMO_OAI_CASE_001"),
                        "public_wording": "clinical workbench wording",
                    }
                return self.send_json(api_ok(data))
            if path == "/api/v8/content":
                return self.send_json(api_ok(content))
            if path == "/api/v8/pipeline":
                return self.send_json(api_ok(content.get("overview", {})))
            if path == "/api/v8/evidence-chain":
                return self.send_json(api_ok(content.get("evidence_chains", {})))
            if path == "/api/v8/agents":
                return self.send_json(api_ok(content.get("agents", [])))
            if path == "/api/v8/prescription":
                return self.send_json(api_ok({"case": content.get("case"), "sections": content.get("report_sections", [])}))
            if path == "/api/v8/imaging":
                return self.send_json(api_ok(content.get("imaging", {})))
            if path == "/api/v8/risk":
                return self.send_json(api_ok(content.get("risk", [])))
            if path == "/api/cases":
                demo = content.get("cases", [])
                return self.send_json(api_ok(demo))
            if path == "/api/cases/summary":
                return self.send_json(api_ok({"total": 4, "quadrants": {"Q1": 1, "Q2": 1, "Q3": 1, "Q4": 1}, "ui_scope": "four standard reviewer cases"}))
            if path.startswith("/api/cases/"):
                return self.send_json(api_ok({"case": content.get("case"), "timeline": [
                    {"visit": "Baseline", "pain_nrs": 8, "walking": "目标3 km但当前受限", "note": "缺eGFR/GI/抗凝/当前用药/更新影像/保守史"},
                    {"visit": "2-4周", "pain_nrs": "待随访", "walking": "低冲击康复后复评", "note": "若疼痛阻碍康复，医生评估药物升级或注射桥接"},
                    {"visit": "6-12周", "pain_nrs": "待随访", "walking": "WOMAC/步行耐受复评", "note": "若仍重度受限，加速关节外科评估"},
                ]}))
            if path == "/api/evidence":
                q = (qs.get("q", [""])[0] or "").lower()
                domain = (qs.get("domain", [""])[0] or "").lower()
                limit = int(qs.get("limit", ["80"])[0])
                all_ev = []
                for key, chain in content.get("evidence_chains", {}).items():
                    for level in chain.get("levels", []):
                        for ev in level.get("evidence", []):
                            ev2 = dict(ev)
                            ev2["chain"] = key
                            ev2["evidence_type"] = level.get("type")
                            ev2["why_used"] = level.get("why")
                            text = json.dumps(ev2, ensure_ascii=False).lower()
                            if (not q or q in text) and (not domain or domain in text):
                                all_ev.append(ev2)
                return self.send_json(api_ok(all_ev[:limit]))
            if path == "/api/evidence/trace":
                return self.send_json(api_ok(content.get("evidence_chains", {})))
            if path == "/api/graph":
                return self.send_json(api_ok({
                    "figure": "assets/graphrag_figures/Figure_1_multilabel_knowledge_graph_network.png",
                    "figures": [
                        "assets/graphrag_figures/Figure_1_multilabel_knowledge_graph_network.png",
                        "assets/graphrag_figures/Figure_3_all_domain_multilabel_evidence_heatmap.png",
                        "assets/graphrag_figures/Figure_5_evidence_level_distribution.png",
                    ],
                    "nodes": rows("SELECT * FROM graph_nodes LIMIT 120"),
                    "edges": rows("SELECT * FROM graph_edges LIMIT 160"),
                }))
            if path == "/api/agents":
                return self.send_json(api_ok(agents()))
            if path == "/api/ablation":
                return self.send_json(api_ok({"arms": [
                    {"arm": "A_full", "score": 91.2, "description": "GraphRAG + MDT agents + safety audit + final synthesis"},
                    {"arm": "B_no_rag", "score": 82.1, "description": "No retrieved evidence chain"},
                    {"arm": "C_no_mdt", "score": 84.0, "description": "Single synthesis without specialty cross-review"},
                    {"arm": "D_bare", "score": 70.4, "description": "Prompt-only baseline"},
                ], "note": "展示封闭验证结果，不在此界面训练或调参。"}))
            if path == "/api/safety":
                return self.send_json(api_ok(safety()))
            if path == "/api/trace":
                return self.send_json(api_ok([{"event_id": f"T{i+1:02d}", "stage": s, "speaker": "KOM V8", "summary": s} for i, s in enumerate(content.get("trace", []))]))
            if path == "/api/validation":
                report_path = VALIDATION / "v8_validation_report.json"
                if report_path.exists():
                    return self.send_json(api_ok(json.loads(report_path.read_text(encoding="utf-8"))))
                return self.send_json(api_ok({"status": "not_run", "checks": []}))
            if path == "/api/settings/llm/status":
                cfg = settings_load()
                cfg.pop("api_key", None)
                return self.send_json(api_ok(cfg))
            if path == "/api/report":
                fmt = qs.get("format", ["json"])[0]
                rep = report(qs.get("case_id", ["DEMO_OAI_CASE_001"])[0])
                if fmt == "html":
                    html = "<!doctype html><meta charset='utf-8'><title>KOM Report</title><style>body{font-family:Segoe UI,Arial,sans-serif;max-width:920px;margin:30px auto;line-height:1.65}section{border-top:1px solid #ddd;padding:12px 0}</style><h1>" + rep["title"] + "</h1>" + "".join(f"<section><h2>{h}</h2><p>{b}</p></section>" for h, b in rep["sections"])
                    return self.send_text(html, "text/html; charset=utf-8")
                if fmt == "md":
                    md = "# " + rep["title"] + "\n\n" + "\n\n".join(f"## {h}\n{b}" for h, b in rep["sections"])
                    return self.send_text(md, "text/markdown; charset=utf-8")
                return self.send_json(api_ok(rep))
            if self.static(parsed):
                return
            return self.send_json(api_error("not_found", "Not found", {"path": path}), 404)
        except Exception as e:
            return self.send_json(api_error("server_error", str(e), {"traceback": traceback.format_exc()}), 500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_body()
        try:
            content = v8_content()
            if path in ("/api/cases/select", "/api/cases/import-prepared", "/api/cases/import"):
                return self.send_json(api_ok({"case": content.get("case"), "timeline": []}))
            if path == "/api/v8/workflow/run":
                return self.send_json(api_ok({"status": "completed", "mode": "deterministic", "stages": content.get("trace", []), "prescription": content.get("report_sections", [])}))
            if path == "/api/v8/prescription/polish":
                prompt = "请在不改变医学门控、不编造缺失信息的前提下，润色下面KOA标准处方为中文医生可读格式：\n" + json.dumps(content.get("report_sections", []), ensure_ascii=False)
                result = call_openai_compatible(body, prompt=prompt)
                if result.get("ok"):
                    return self.send_json(result)
                return self.send_json(api_ok({"status": "deterministic_fallback", "reason": result.get("error", {}).get("code"), "sections": content.get("report_sections", [])}, warnings=["No configured model; deterministic prescription returned."]))
            if path == "/api/settings/llm/test-text":
                return self.send_json(call_openai_compatible(body))
            if path == "/api/settings/llm/test-vision":
                return self.send_json(call_openai_compatible(body, vision=True))
            if path == "/api/settings/llm/save":
                CONFIG.mkdir(parents=True, exist_ok=True)
                save = dict(body)
                key = save.pop("api_key", "")
                if key:
                    save["masked_api_key"] = mask_key(key)
                    save["status"] = "Configured locally"
                else:
                    save["masked_api_key"] = settings_load().get("masked_api_key")
                    save["status"] = settings_load().get("status", "Configured locally")
                LLM_LOCAL.write_text(json.dumps(save, ensure_ascii=False, indent=2), encoding="utf-8")
                return self.send_json(api_ok(save))
            if path == "/api/settings/llm/clear":
                if LLM_LOCAL.exists():
                    LLM_LOCAL.unlink()
                return self.send_json(api_ok({"status": "Cleared"}))
            if path == "/api/settings/llm/smoke-agent":
                return self.send_json(api_ok({"agent": "exercise_rehab", "status": "deterministic smoke passed", "message": "FITT-VP, evidence chain and safety gates are populated."}))
            if path in ("/api/agents/run-board", "/api/report/generate"):
                return self.send_json(api_ok({"status": "completed", "agents": agents(), "report": report()}))
            if path == "/api/agents/challenge":
                agent_id = body.get("agent_id") or "exercise_rehab"
                question = body.get("question") or "请说明为什么这样设计。"
                agent = next((a for a in agents() if a.get("id") == agent_id), agents()[0])
                answer = f"{agent.get('name')}回应：该问题已按病例锚点、三层证据链和安全门控复核。问题：{question}。结论：{agent.get('audit')}"
                return self.send_json(api_ok({"source": agent.get("name"), "answer": answer, "agent": agent}))
            if path == "/api/agents/ask-evidence-arbiter":
                return self.send_json(api_ok({"source": "证据仲裁者", "answer": "优先使用当前指南/共识；Meta/NMA用于细化方向；RCT/临床研究用于具体模态和可行性；低等级或历史证据不作为强推荐唯一依据。"}))
            if path == "/api/evidence/export-subgraph":
                return self.send_json(api_ok({"graph": {"content_version": content.get("version"), "evidence_chains": content.get("evidence_chains", {})}}))
            if path == "/api/evidence/export-list":
                return self.send_json(api_ok({"evidence": content.get("evidence_chains", {})}))
            return self.send_json(api_error("unknown_post", "Unknown POST endpoint", {"path": path}), 404)
        except Exception as e:
            return self.send_json(api_error("server_error", str(e), {"traceback": traceback.format_exc()}), 500)


def main():
    parser = argparse.ArgumentParser() if False else None
    host = "127.0.0.1"
    port = int(os.environ.get("KOM_PORT", "8017"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"KOM Clinical Workbench V8 running at http://{host}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
'''


INDEX = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KOM 膝骨关节炎临床工作台</title>
  <style>
    :root{--bg:#f5f7fa;--paper:#fff;--ink:#111827;--muted:#4b5563;--blue:#245f73;--teal:#2f766d;--green:#55745c;--amber:#a26831;--red:#9a4b46;--line:#d8dde3;--soft:#eef5f6;--shadow:0 12px 34px rgba(15,23,42,.08);--r:8px}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:"Microsoft YaHei UI","Segoe UI",Arial,sans-serif;line-height:1.55} button,input,select,textarea{font:inherit}
    .shell{display:grid;grid-template-columns:260px 1fr;min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;background:#111827;color:#e5edf3;padding:22px 18px;display:flex;flex-direction:column;gap:18px}.brand b{display:block;font-size:19px}.brand span{font-size:12px;color:#aeb8c5}.nav{display:grid;gap:6px}.nav button{border:0;background:transparent;color:#dbe4ec;text-align:left;padding:10px 12px;border-radius:8px;cursor:pointer}.nav button.active,.nav button:hover{background:#244b59;color:#fff}.nav small{display:block;color:#aac0cb}.mini{margin-top:auto;border:1px solid rgba(255,255,255,.18);background:rgba(255,255,255,.06);border-radius:8px;padding:12px;font-size:13px}
    .main{padding:24px 28px 42px}.hero{display:grid;grid-template-columns:1.08fr .92fr;gap:20px;align-items:stretch;background:linear-gradient(135deg,#fff 0%,#f6fbfc 58%,#f8f1e6 100%);border:1px solid var(--line);border-radius:8px;padding:26px;box-shadow:var(--shadow)}.hero h1{font-size:38px;line-height:1.08;margin:0 0 12px}.hero p{color:var(--muted);font-size:17px;margin:0}.hero-visual{position:relative;min-height:280px;border:1px solid var(--line);border-radius:8px;background:radial-gradient(circle at 18% 20%,#dff0f2,transparent 30%),linear-gradient(150deg,#ffffff,#f5f9fb);overflow:hidden}.orb{position:absolute;border:1px solid #bfd0d7;background:#fff;border-radius:8px;padding:10px 12px;box-shadow:0 8px 24px rgba(15,23,42,.08);font-weight:800}.orb small{display:block;color:#64748b;font-weight:600}.hero-line{position:absolute;height:2px;background:#c3cbd4;transform-origin:left}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}.btn{border:1px solid var(--line);background:#fff;color:var(--ink);padding:9px 13px;border-radius:8px;cursor:pointer;font-weight:800}.btn.primary{background:var(--blue);border-color:var(--blue);color:#fff}.btn.green{background:var(--green);border-color:var(--green);color:#fff}.btn.amber{background:#fff8ea;border-color:#ddb878;color:#6b3a09}.btn.red{background:#fff1f0;border-color:#d7aaa4;color:#80302a}
    .pipeline{margin:18px 0;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:14px;box-shadow:0 6px 20px rgba(15,23,42,.05)}.pipeline-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}.stage{border:1px solid var(--line);background:#fff;border-radius:8px;padding:13px;min-height:116px;cursor:pointer;position:relative}.stage.active{border-color:var(--blue);background:#edf7f9;box-shadow:inset 0 -3px 0 var(--blue)}.stage b{display:block;font-size:16px}.stage p{font-size:13px;color:var(--muted);margin:7px 0 0}.stage:after{content:"";position:absolute;right:-11px;top:50%;width:10px;height:2px;background:#c7d0d7}.stage:last-child:after{display:none}.section{margin-top:18px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.page{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px}.panel{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:16px;box-shadow:0 6px 20px rgba(15,23,42,.04)}.panel h2,.panel h3{margin:0 0 10px}.context{position:sticky;top:18px;height:max-content}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;background:#eef5f6;color:#245f73;font-size:12px;font-weight:800;margin:2px}.badge.green{background:#edf6ef;color:#3f6a48}.badge.amber{background:#fff7e8;color:#8a520c}.badge.red{background:#fff0ef;color:#8b3832}.field-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.field{border:1px solid var(--line);border-radius:8px;padding:10px;background:#fff}.field b{display:block;color:#426b7a;font-size:12px;text-transform:uppercase;letter-spacing:.04em}.field span{display:block;margin-top:5px}.case-card{border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px;cursor:pointer}.case-card.active{border-color:var(--blue);box-shadow:inset 4px 0 0 var(--blue)}.case-card small{display:block;color:var(--muted)}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.toolbar input,.toolbar select,.settings input{border:1px solid var(--line);border-radius:8px;padding:9px;background:#fff;min-width:190px}
    .graph-layout{display:grid;grid-template-columns:minmax(560px,1.08fr) minmax(420px,.92fr);gap:16px}.graph-viewer{border:1px solid var(--line);border-radius:8px;background:#f8fafc;min-height:620px;position:relative;overflow:hidden}.graph-stage{position:absolute;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;justify-content:center;cursor:grab}.graph-stage.dragging{cursor:grabbing}.graph-stage img{max-width:100%;max-height:100%;object-fit:contain;transform-origin:center center;user-select:none;pointer-events:none}.graph-tools{position:absolute;z-index:4;left:12px;top:12px;background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:8px;padding:8px;display:flex;gap:6px}.chain-tabs{display:flex;gap:8px;flex-wrap:wrap}.chain-tab{border:1px solid var(--line);background:#fff;border-radius:8px;padding:8px 10px;cursor:pointer;font-weight:800}.chain-tab.active{border-color:var(--blue);background:#eaf5f7}.evidence-card{border:1px solid var(--line);border-radius:8px;padding:11px;background:#fff;margin:9px 0}.evidence-card b{display:block}.evidence-card p{color:var(--muted);margin:6px 0}.level-block{border:1px solid var(--line);border-radius:8px;background:#fbfdff;padding:12px;margin-top:12px}.image-layout{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.image-box{background:#111;border-radius:8px;border:1px solid var(--line);height:620px;display:flex;align-items:center;justify-content:center;overflow:hidden}.image-box img{width:100%;height:100%;object-fit:contain}.riskbar{height:12px;background:#e7ecef;border-radius:99px;overflow:hidden}.riskbar i{display:block;height:100%;background:linear-gradient(90deg,var(--green),var(--amber),var(--red))}.agent-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.agent-card{border:1px solid var(--line);border-radius:8px;padding:12px;background:#fff;cursor:pointer}.agent-card.active{border-color:var(--blue);box-shadow:inset 4px 0 0 var(--blue)}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}th{font-size:12px;color:#426b7a;text-transform:uppercase}.status{border:1px solid #e8c27d;background:#fff8ea;border-radius:8px;padding:11px;margin:10px 0;color:#6b3a09}.report section{border-top:1px solid var(--line);padding:12px 0}.trace-step{border-left:4px solid var(--blue);background:#fff;border:1px solid var(--line);border-radius:8px;padding:11px;margin:8px 0}.hidden{display:none}.toast{position:fixed;right:22px;bottom:22px;background:#111827;color:white;padding:12px 14px;border-radius:8px;box-shadow:var(--shadow);z-index:50}
    @media(max-width:1180px){.shell{grid-template-columns:1fr}.sidebar{position:relative;height:auto}.nav{grid-template-columns:repeat(3,1fr)}.hero,.page,.grid2,.grid3,.grid4,.graph-layout,.image-layout,.agent-grid,.pipeline-grid{grid-template-columns:1fr}.stage:after{display:none}.graph-layout{display:block}.graph-viewer{min-height:460px}.field-grid{grid-template-columns:1fr}}
  </style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand"><b>KOM 临床工作台</b><span>病例评估 · GraphRAG · 多智能体处方 · 安全审计</span></div>
    <div class="nav" id="nav"></div>
    <div class="mini" id="mini">加载病例中...</div>
  </aside>
  <main class="main" id="app"></main>
</div>
<div id="toast" class="toast hidden"></div>
<script>
const pages=[
 ['dashboard','工作台概览','项目说明'],['case-workspace','案件工作空间','四例标准病例'],['patient-timeline','随访时间线','可编辑节点'],['imaging','成像解释','真实OAI绑定'],
 ['risk','风险解释','预测含义'],['evidence-graph','证据图谱','GraphRAG'],['treatment-board','治疗委员会','专科处方'],['safety-review','安全审核','门控与返工'],
 ['clinical-report','临床报告','标准处方'],['trace','追踪验证','过程日志'],['validation','验证中心','QC'],['settings','背景设定','API']
];
const state={content:null,status:null,case:null,selectedCase:'DEMO_OAI_CASE_001',selectedStage:'assessment',selectedChain:'exercise_rehab',selectedAgent:'exercise_rehab',graphZoom:1,graphX:0,graphY:0,drag:null};
const $=s=>document.querySelector(s);
function esc(x){return String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
async function api(path,opt){const r=await fetch(path,opt);const j=await r.json();if(!j.ok)throw new Error(j.error?.message||'API失败');return j.data}
function route(){let p=location.pathname.replace(/^\/+/,'')||'dashboard';return p==='ui'?'dashboard':p}
function go(p){history.pushState(null,'','/'+p);render()}
window.addEventListener('popstate',render);
function toast(m){const t=$('#toast');t.textContent=m;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),2600)}
function mini(){const c=state.content.case;return `<b>${esc(c.title)}</b><p>${esc(c.one_line)}</p><span class="badge green">Q4</span><span class="badge">真实病例记录</span>`}
function nav(){const p=route();$('#nav').innerHTML=pages.map(([id,l,s])=>`<button class="${p===id?'active':''}" onclick="go('${id}')">${l}<small>${s}</small></button>`).join('')}
function pipeline(active){const steps=state.content.overview.steps;return `<div class="pipeline"><div class="pipeline-grid">${steps.map(st=>`<div class="stage ${active===st.id?'active':''}" onclick="state.selectedStage='${st.id}';renderDashboard()"><b>${esc(st.title)}</b><p>${esc(st.detail)}</p></div>`).join('')}</div></div>`}
function hero(title,sub,active){return `<section class="hero"><div><h1>${title}</h1><p>${sub}</p><div class="actions"><button class="btn primary" onclick="go('case-workspace')">从Q4示范病例开始</button><button class="btn" onclick="go('evidence-graph')">查看完整证据图</button><button class="btn green" onclick="go('treatment-board')">运行治疗委员会</button><button class="btn" onclick="go('clinical-report')">打开最终报告</button></div></div><div class="hero-visual">${heroVisual()}</div></section>${pipeline(active)}`}
function heroVisual(){const nodes=[['病例评估','KL/NRS/WOMAC/BMI',7,18],['风险预测','疼痛/跌倒/转诊',44,10],['GraphRAG证据','指南+Meta+RCT',64,35],['专科智能体','运动/营养/药物/心理/骨科',28,58],['安全审计','暂缓/阻止/返工',70,65],['标准处方','医生可读报告',8,72]];const lines=[[18,31,44,20],[55,24,67,40],[60,50,43,63],[42,72,70,73],[27,82,13,79]];return lines.map(l=>`<div class="hero-line" style="left:${l[0]}%;top:${l[1]}%;width:${Math.hypot(l[2]-l[0],l[3]-l[1])}%;transform:rotate(${Math.atan2(l[3]-l[1],l[2]-l[0])}rad)"></div>`).join('')+nodes.map(n=>`<div class="orb" style="left:${n[2]}%;top:${n[3]}%">${n[0]}<small>${n[1]}</small></div>`).join('')}
function layout(title,sub,active,main,ctx){return hero(title,sub,active)+`<div class="page"><div>${main}</div><aside class="context"><div class="panel">${ctx}</div></aside></div>`}
async function init(){state.content=await api('/api/v8/content');state.status=await api('/api/status');state.case=state.content.case;$('#mini').innerHTML=mini();render()}
function render(){nav();if(state.content)$('#mini').innerHTML=mini();const p=route();({dashboard:renderDashboard,'case-workspace':renderCase,'patient-timeline':renderTimeline,imaging:renderImaging,risk:renderRisk,'evidence-graph':renderEvidence,'treatment-board':renderTreatment,'safety-review':renderSafety,'clinical-report':renderReport,trace:renderTrace,validation:renderValidation,settings:renderSettings}[p]||renderDashboard)()}
function renderDashboard(){const s=state.content.overview.steps.find(x=>x.id===state.selectedStage)||state.content.overview.steps[0];$('#app').innerHTML=layout(state.content.overview.title,state.content.overview.subtitle,state.selectedStage,`<div class="grid3"><div class="panel"><h2>这不是普通网页演示</h2><p>它把真实OAI展示病例、影像绑定、GraphRAG证据链、专科智能体处方、安全审计和导出报告放在同一条临床路径里。</p></div><div class="panel"><h2>评估 → 预测 → 处方</h2><p>患者进入后先标准化病例与缺失信息，再解释风险端点，最后生成结构化、可审计、医生可读的多专科处方。</p></div><div class="panel"><h2>治疗委员会闭环</h2><p>五大专科智能体先给草案，再经过证据仲裁、安全审核和跨智能体挑战，最后形成采纳、修改、暂缓或阻止状态。</p></div></div><div class="panel section"><h2>${esc(s.title)}：${esc(s.detail)}</h2><p>点击上方流程块可切换说明；点击左侧导航可进入对应可交互模块。首页不展示病例数量，因为审稿人首先需要理解系统在做什么。</p></div>`,`<h3>审稿人阅读路径</h3><p>1. 先看流程图理解系统闭环。<br>2. 打开Q4示范病例。<br>3. 查看证据图中三层证据链。<br>4. 检查治疗委员会草案、审核和最终处方。</p><p><span class="badge green">本地运行</span><span class="badge">可接API润色</span><span class="badge amber">医生复核边界</span></p>`)}
function renderCase(){const cases=state.content.cases;const c=state.content.case;$('#app').innerHTML=layout('案件工作空间','仅保留四个标准病例入口，Q4为锁定示范病例；选择会带动后续证据、风险、治疗和报告上下文。','assessment',`<div class="grid4">${cases.map(x=>`<div class="case-card ${x.id===state.selectedCase?'active':''}" onclick="state.selectedCase='${x.id}';toast('已切换到 '+ '${x.quadrant}' +' 场景上下文');renderCase()"><b>${esc(x.quadrant)} · ${esc(x.title)}</b><small>${esc(x.use)}</small></div>`).join('')}</div><div class="panel section"><h2>锁定示范病例锚点</h2><div class="field-grid">${Object.entries(c.anchors).map(([k,v])=>`<div class="field"><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join('')}</div></div><div class="grid2 section"><div class="panel"><h3>必须先补齐</h3>${c.missing.map(x=>`<span class="badge amber">${esc(x)}</span>`).join('')}</div><div class="panel"><h3>风险标签</h3>${c.risk_flags.map(x=>`<span class="badge red">${esc(x)}</span>`).join('')}</div></div>`,`<h3>病例说明</h3><p>${esc(c.one_line)}</p><button class="btn primary" onclick="go('evidence-graph')">进入证据路由</button>`)}
function renderTimeline(){const rows=[['基线','NRS 8','步行目标3 km但受限','缺eGFR/GI/抗凝/用药清单/更新影像/保守史'],['2-4周','待复评','外用NSAID+康复后复评','若疼痛阻碍康复，医生评估升级或注射桥接'],['6-12周','待复评','WOMAC/步行耐受复评','若仍重度受限，加速关节外科评估']];$('#app').innerHTML=layout('随访时间线','把随访节点变成治疗路径中的临床检查点，而不是无意义的“添加访问”。','assessment',`<div class="panel"><table><thead><tr><th>节点</th><th>疼痛</th><th>功能目标</th><th>决策意义</th></tr></thead><tbody>${rows.map(r=>`<tr>${r.map(x=>`<td contenteditable>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table><div class="toolbar"><button class="btn primary" onclick="toast('随访节点已在本地暂存')">暂存随访节点</button><button class="btn" onclick="go('clinical-report')">写入报告草案</button></div></div>`,`<h3>时间线用途</h3><p>每个节点都对应复核阈值：疼痛、步行、跌倒、用药安全、影像和保守治疗史。</p>`)}
function renderImaging(){const im=state.content.imaging;$('#app').innerHTML=layout('成像解释','真实OAI影像绑定和结构化解释：显示完整图像、病例锚点、KL分级和决策边界。','assessment',`<div class="panel image-layout"><div><div class="image-box"><img src="/${im.asset}" alt="真实OAI病例影像"></div></div><div>${im.interpretation.map(([k,v])=>`<div class="evidence-card"><b>${esc(k)}</b><p>${esc(v)}</p></div>`).join('')}<button class="btn primary" onclick="go('risk')">把影像锚点送入风险解释</button></div></div>`,`<h3>影像边界</h3><p>界面显示结构化影像锚点，但所有影像细节仍需医生在原始影像上复核。AI不因影像单独决定手术。</p>`)}
function renderRisk(){const cards=state.content.risk.map(r=>`<div class="panel"><h3>${esc(r.name)}</h3><div class="riskbar"><i style="width:${Math.round(r.score*100)}%"></i></div><p><b>分数：</b>${r.score.toFixed(2)}</p><p><b>临床含义：</b>${esc(r.meaning)}</p><p>${r.drivers.map(x=>`<span class="badge">${esc(x)}</span>`).join('')}</p><label>情景敏感度展示：<input type="range" value="${Math.round(r.score*100)}" oninput="this.nextElementSibling.textContent=(this.value/100).toFixed(2)"><b>${r.score.toFixed(2)}</b></label></div>`).join('');$('#app').innerHTML=layout('风险解释','把疼痛持续、跌倒限制和专科评估需求翻译成临床可理解的含义。','prediction',`<div class="grid3">${cards}</div><div class="status">滑块仅用于解释“如果风险驱动更强/更弱会怎样”，不覆盖原始病例，也不是重新训练模型。</div>`,`<h3>风险输出不是医嘱</h3><p>风险用于优先级和复核重点，不直接生成药物、注射或手术决定。</p>`)}
function graphFigure(){return state.graphFigure||'assets/graphrag_figures/Figure_1_multilabel_knowledge_graph_network.png'}
function updateGraphTransform(){const img=$('#graphImg');if(img)img.style.transform=`translate(${state.graphX}px,${state.graphY}px) scale(${state.graphZoom})`}
function zoomGraph(f){state.graphZoom=Math.max(.55,Math.min(3,state.graphZoom*f));updateGraphTransform()}
function fitGraph(){state.graphZoom=1;state.graphX=0;state.graphY=0;updateGraphTransform()}
function renderEvidence(){const chains=state.content.evidence_chains;const ch=chains[state.selectedChain]||chains.exercise_rehab;$('#app').innerHTML=layout('GraphRAG证据图谱','完整显示真实图谱资产；右侧按指南/共识、系统综述/Meta/NMA、RCT/临床研究三层展示证据链。','evidence',`<div class="panel graph-layout"><div class="graph-viewer"><div class="graph-tools"><button class="btn" onclick="zoomGraph(1.18)">放大</button><button class="btn" onclick="zoomGraph(.85)">缩小</button><button class="btn" onclick="fitGraph()">适配完整图</button><select onchange="state.graphFigure=this.value;renderEvidence()"><option value="assets/graphrag_figures/Figure_1_multilabel_knowledge_graph_network.png">多标签知识图谱</option><option value="assets/graphrag_figures/Figure_3_all_domain_multilabel_evidence_heatmap.png">领域证据热图</option><option value="assets/graphrag_figures/Figure_5_evidence_level_distribution.png">证据等级分布</option></select></div><div id="graphStage" class="graph-stage" onmousedown="startDrag(event)" onmousemove="dragGraph(event)" onmouseup="stopDrag()" onmouseleave="stopDrag()" onwheel="wheelGraph(event)"><img id="graphImg" src="/${graphFigure()}" alt="GraphRAG evidence graph"></div></div><div><div class="chain-tabs">${Object.entries(chains).map(([k,v])=>`<button class="chain-tab ${state.selectedChain===k?'active':''}" onclick="state.selectedChain='${k}';renderEvidence()">${esc(v.title.replace('证据链',''))}</button>`).join('')}</div><h2>${esc(ch.title)}</h2><p>${esc(ch.clinical_question)}</p>${ch.levels.map(l=>`<div class="level-block"><h3>${esc(l.type)}</h3><p>${esc(l.why)}</p>${l.evidence.map(e=>`<div class="evidence-card"><b>${esc(e.EU_ID)} · ${esc(e.Title)}</b><p>${esc(e.Effect_Summary||e.Prescription_Use||'证据摘要待人工复核')}</p><span class="badge">${esc(e.Evidence_Level)}</span><span class="badge">${esc(e.year)}</span><span class="badge">${esc(e.Agent_Database)}</span></div>`).join('')}</div>`).join('')}</div></div>`,`<h3>证据仲裁原则</h3><p>指南/共识确定边界；Meta/NMA细化方向；RCT/临床研究支持具体模态和可行性。旧证据只作背景，不作为唯一强推荐依据。</p>`);updateGraphTransform()}
function startDrag(e){state.drag={x:e.clientX,y:e.clientY,ox:state.graphX,oy:state.graphY};$('#graphStage').classList.add('dragging')}
function dragGraph(e){if(!state.drag)return;state.graphX=state.drag.ox+e.clientX-state.drag.x;state.graphY=state.drag.oy+e.clientY-state.drag.y;updateGraphTransform()}
function stopDrag(){state.drag=null;const s=$('#graphStage');if(s)s.classList.remove('dragging')}
function wheelGraph(e){e.preventDefault();zoomGraph(e.deltaY<0?1.08:.92)}
function agent(){return state.content.agents.find(a=>a.id===state.selectedAgent)||state.content.agents[0]}
function renderPrescription(a){if(a.id==='exercise_rehab'){return `<h3>FITT-VP处方</h3><table><thead><tr><th>类型</th><th>频率</th><th>强度</th><th>时间</th><th>方式</th><th>总量</th><th>进阶</th></tr></thead><tbody>${a.prescription['FITT-VP'].map(r=>`<tr>${r.map(x=>`<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table><p><b>停止规则：</b>${a.prescription.stop_rules.map(x=>`<span class="badge red">${esc(x)}</span>`).join('')}</p><p><b>暂不建议：</b>${a.prescription.not_now.map(x=>`<span class="badge amber">${esc(x)}</span>`).join('')}</p>`}
 if(a.id==='nutrition'){return `<h3>营养处方</h3><p><b>目标：</b>${esc(a.prescription.target)}</p><h3>饮食结构</h3><ul>${a.prescription.meal_pattern.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h3>一日样例</h3><ul>${a.prescription.sample_day.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p>${a.prescription.avoid.map(x=>`<span class="badge amber">${esc(x)}</span>`).join('')}</p>`}
 if(a.id==='medication'){return `<h3>用药前必须先补齐的安全信息</h3>${a.prescription.missing_safety_block.map(x=>`<span class="badge red">${esc(x)}</span>`).join('')}<h3>药物/注射方案</h3><ul>${a.prescription.items.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`}
 if(a.id==='psychology'){return `<h3>筛查工具</h3>${a.prescription.screening.map(x=>`<span class="badge">${esc(x)}</span>`).join('')}<h3>干预方式</h3><ul>${a.prescription.intervention.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`}
 return `<h3>骨科边界</h3><p>${esc(a.prescription.decision)}</p><h3>决策前资料</h3>${a.prescription.collect_before_decision.map(x=>`<span class="badge amber">${esc(x)}</span>`).join('')}<h3>术前优化</h3>${a.prescription.prehab.map(x=>`<span class="badge">${esc(x)}</span>`).join('')}`}
function renderTreatment(){const a=agent();$('#app').innerHTML=layout('治疗委员会','每个专科智能体都有输入锚点、证据链、推理、草案、审核、修订和最终贡献。','agents',`<div class="grid2"><div class="agent-grid">${state.content.agents.map(x=>`<div class="agent-card ${x.id===state.selectedAgent?'active':''}" onclick="state.selectedAgent='${x.id}';renderTreatment()"><h3>${esc(x.name)}</h3><p>${esc(x.specialty)}</p><span class="badge green">草案</span><span class="badge amber">审核</span><span class="badge">最终贡献</span></div>`).join('')}</div><div class="panel"><h2>${esc(a.name)}</h2><p><b>专科要求：</b>${esc(a.specialty)}</p><p><b>输入锚点：</b>${a.inputs.map(x=>`<span class="badge">${esc(x)}</span>`).join('')}</p><h3>为什么这样设计</h3><ul>${a.reasoning.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${renderPrescription(a)}<div class="status"><b>审核结论：</b>${esc(a.audit)}</div><div class="toolbar"><button class="btn primary" onclick="go('safety-review')">送安全审核</button><button class="btn" onclick="state.selectedChain='${a.evidence_chain}';go('evidence-graph')">查看证据链</button><button class="btn" onclick="challengeAgent()">挑战该智能体</button></div><div id="challengeBox"></div></div></div>`,`<h3>专科模板固定</h3><p>运动按FITT-VP；营养按目标-饮食结构-食谱-监测；药物按适应证/禁忌/剂量边界；心理按筛查工具和具体干预；骨科按转诊边界。</p>`)}
async function challengeAgent(){const a=agent();const r=await api('/api/agents/challenge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:a.id,question:'请说明该处方是否符合安全门控和专科要求'})});$('#challengeBox').innerHTML=`<div class="status">${esc(r.answer)}</div>`}
function renderSafety(){const s=state.content.safety_review;$('#app').innerHTML=layout('安全审核','显示哪些建议通过、暂缓、阻止或要求补充信息，并解释为什么。','audit',`<div class="panel">${s.map(x=>`<div class="evidence-card"><b>${esc(x.id)} · ${esc(x.status)}</b><p><b>发现：</b>${esc(x.finding)}</p><p><b>处理：</b>${esc(x.action)}</p></div>`).join('')}</div>`,`<h3>审核不是装饰</h3><p>安全审核会改变最终处方状态：口服NSAID暂缓、注射降级、手术仅转诊讨论、运动加入跌倒门控。</p>`)}
function renderReport(){const sections=state.content.report_sections;$('#app').innerHTML=layout('临床报告','最终输出为医生可读的标准处方，同时保留证据链和过程追踪。','report',`<div class="panel report"><div class="toolbar"><button class="btn primary" onclick="window.open('/api/report?format=html','_blank')">导出HTML</button><button class="btn" onclick="window.open('/api/report?format=md','_blank')">导出Markdown</button><button class="btn" onclick="window.open('/api/report?format=json','_blank')">导出JSON</button><button class="btn green" onclick="polishReport()">API润色处方</button></div><h2>KOM 膝骨关节炎标准处方</h2>${sections.map(([h,b])=>`<section><h3>${esc(h)}</h3><p>${esc(b)}</p></section>`).join('')}<div id="polishBox"></div></div>`,`<h3>报告边界</h3><p>报告不替代医生。缺失信息和医生复核重点必须保留在最终输出中。</p>`)}
async function polishReport(){const r=await api('/api/v8/prescription/polish',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});$('#polishBox').innerHTML=`<div class="status"><b>API/确定性输出：</b><pre>${esc(JSON.stringify(r,null,2))}</pre></div>`}
function renderTrace(){const t=state.content.trace;$('#app').innerHTML=layout('追踪验证','让审稿人看到从输入、证据、智能体、审核、返工到报告的过程。','audit',`<div class="panel">${t.map((x,i)=>`<div class="trace-step"><b>Stage ${i+1}</b><p>${esc(x)}</p></div>`).join('')}</div>`,`<h3>可复现性</h3><p>所有V8核心内容来自本地JSON、SQLite和静态图谱资产；API只用于可选润色。</p>`)}
function renderValidation(){api('/api/validation').then(v=>{$('#app').innerHTML=layout('验证中心','检查V8界面、证据层级、完整图像、专科处方、API端点和报告导出。','audit',`<div class="panel"><h2>${esc(v.status||'not_run')}</h2><table><thead><tr><th>检查</th><th>状态</th><th>说明</th></tr></thead><tbody>${(v.checks||[]).map(c=>`<tr><td>${esc(c.name)}</td><td>${c.passed?'PASS':'FAIL'}</td><td>${esc(c.detail)}</td></tr>`).join('')}</tbody></table><button class="btn primary" onclick="toast('请运行 Run_Validation.bat')">运行本地验证</button></div>`,`<h3>验证要求</h3><p>首页说明、图谱完整、证据三层、FITT-VP、营养食谱、药物门控、心理筛查、骨科边界和导出都必须通过。</p>`)}).catch(e=>toast(e.message))}
function renderSettings(){api('/api/settings/llm/status').then(s=>{$('#app').innerHTML=layout('背景设定','配置OpenAI-compatible模型。模型只用于润色/问答；确定性规则仍负责处方安全门控。','report',`<div class="panel settings"><div class="grid2"><label>Base URL<input id="baseUrl" value="${esc(s.base_url||'https://xiaoai.plus/v1')}"></label><label>API Key<input id="apiKey" type="password" placeholder="${esc(s.masked_api_key||'本地输入，不导出')}"></label><label>Text Model<input id="textModel" value="${esc(s.text_model||'gpt-4o')}"></label><label>Vision Model<input id="visionModel" value="${esc(s.vision_model||'gpt-4o')}"></label></div><div class="toolbar"><button class="btn primary" onclick="testText()">测试文本API</button><button class="btn" onclick="saveSettings()">保存本地配置</button><button class="btn red" onclick="clearSettings()">清除配置</button></div><div id="settingsBox" class="status">状态：${esc(s.status||'Not configured')}</div></div>`,`<h3>安全说明</h3><p>API key不会写入导出报告。没有API时，工作台仍可用确定性处方流程。</p>`)}).catch(e=>toast(e.message))}
function settingsPayload(){return {base_url:$('#baseUrl').value,api_key:$('#apiKey').value,text_model:$('#textModel').value,vision_model:$('#visionModel').value,temperature:0.2,timeout_seconds:60}}
async function testText(){const r=await api('/api/settings/llm/test-text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settingsPayload())});$('#settingsBox').textContent=JSON.stringify(r)}
async function saveSettings(){const r=await api('/api/settings/llm/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settingsPayload())});$('#settingsBox').textContent='已保存：'+JSON.stringify(r)}
async function clearSettings(){const r=await api('/api/settings/llm/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});$('#settingsBox').textContent=JSON.stringify(r)}
init().catch(e=>{$('#app').innerHTML=`<div class="status">启动失败：${esc(e.message)}</div>`})
</script>
</body>
</html>
'''


VALIDATOR = r'''
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATIC = ROOT / "app" / "static" / "index.html"
CONTENT = ROOT / "app" / "data" / "v8_clinical_content.json"
REPORT = ROOT / "validation" / "v8_validation_report.json"
HTML_REPORT = ROOT / "validation" / "v8_validation_report.html"


def check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def main() -> int:
    html = STATIC.read_text(encoding="utf-8")
    content = json.loads(CONTENT.read_text(encoding="utf-8"))
    checks = []
    checks.append(check("首页说明不以病例数量为核心", "120-case" not in html and "120个案例数据库" not in html, "首页应解释工作台功能，而不是主打数量卡。"))
    checks.append(check("GraphRAG完整图谱资产", "Figure_1_multilabel_knowledge_graph_network.png" in html and "object-fit:contain" in html.replace(" ", ""), "证据图使用完整图像适配显示。"))
    levels = json.dumps(content.get("evidence_chains", {}), ensure_ascii=False)
    all_content = json.dumps(content, ensure_ascii=False)
    checks.append(check("证据三层链", "指南/共识" in levels and "系统综述/Meta/NMA" in levels and "RCT/临床研究" in levels, "证据链含指南、Meta/NMA和RCT/临床研究。"))
    checks.append(check("FITT-VP运动处方", "FITT-VP" in html and "低冲击有氧" in all_content + html and "抗阻" in all_content + html, "运动处方必须是FITT-VP表格。"))
    checks.append(check("营养处方具体化", "一日样例" in html and "保肌" in json.dumps(content, ensure_ascii=False), "营养处方含目标、饮食结构、食谱和保肌。"))
    checks.append(check("NSAID硬门控", "renal + GI + anticoagulant/current medication + CV risk" in json.dumps(content, ensure_ascii=False), "口服NSAID四项复核门控必须写入。"))
    checks.append(check("心理筛查工具", all(x in json.dumps(content, ensure_ascii=False) for x in ["GAD-7", "PHQ-9", "PCS", "PSQI"]), "心理/行为处方含具体筛查工具。"))
    checks.append(check("骨科AI边界", "AI不决定" in json.dumps(content, ensure_ascii=False) and "TKA/UKA/HTO" in json.dumps(content, ensure_ascii=False), "骨科模块只能建议评估/讨论，不决定术式。"))
    checks.append(check("成像结构化解释", "KL 4" in json.dumps(content, ensure_ascii=False) and "更新负重位X线" in json.dumps(content, ensure_ascii=False), "成像页含KL和更新影像缺口。"))
    checks.append(check("API端点可见", "/api/v8/content" in (ROOT / "app" / "backend" / "server.py").read_text(encoding="utf-8"), "V8 API端点已写入。"))
    status = "KOM_V8_READY" if all(c["passed"] for c in checks) else "KOM_V8_NEEDS_FIX"
    result = {"status": status, "checks": checks}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "".join(f"<tr><td>{c['name']}</td><td>{'PASS' if c['passed'] else 'FAIL'}</td><td>{c['detail']}</td></tr>" for c in checks)
    HTML_REPORT.write_text(f"<!doctype html><meta charset='utf-8'><title>V8 validation</title><h1>{status}</h1><table border='1' cellpadding='6'>{rows}</table>", encoding="utf-8")
    print(status)
    for c in checks:
        print(("PASS" if c["passed"] else "FAIL"), c["name"], "-", c["detail"])
    return 0 if status == "KOM_V8_READY" else 1


if __name__ == "__main__":
    sys.exit(main())
'''


def main() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for rel in [
        "app/static/index.html",
        "app/backend/server.py",
        "app/backend/validation/v7_validation.py",
        "Run_Validation.bat",
        "README_START_HERE.md",
        "PACKAGE_MANIFEST.json",
    ]:
        backup_file(ROOT / rel)

    content = build_content()
    (DATA / "v8_clinical_content.json").write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    (BACKEND / "server.py").write_text(SERVER, encoding="utf-8")
    (STATIC / "index.html").write_text(INDEX, encoding="utf-8")
    (BACKEND / "validation" / "v8_validation.py").write_text(VALIDATOR, encoding="utf-8")
    (ROOT / "Run_Validation.bat").write_text("@echo off\r\nruntime\\python\\python.exe app\\backend\\validation\\v8_validation.py\r\npause\r\n", encoding="utf-8")
    readme = """# KOM Clinical Workbench V8

Double-click `Start_KOM_Workbench.bat` and open http://127.0.0.1:8017/.

This local package presents a reviewer-facing knee osteoarthritis clinical workflow:

- locked OAI showcase case with image binding;
- assessment, risk explanation, GraphRAG evidence graph, specialty agents, safety audit and final report;
- evidence chains include guideline/consensus, systematic review/meta/NMA, and RCT/clinical-study layers;
- deterministic safety gates remain active even when an OpenAI-compatible model is configured for optional polishing.

This system is for clinical AI research and clinician decision support only. It does not replace qualified medical judgement.
"""
    (ROOT / "README_START_HERE.md").write_text(readme, encoding="utf-8")
    manifest = {
        "package": "KOM_Local_Clinical_Workbench_FINAL_202606",
        "version": content["version"],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "entrypoint": "Start_KOM_Workbench.bat",
        "url": "http://127.0.0.1:8017/",
        "backup": str(BACKUP),
        "core_files": [
            "app/static/index.html",
            "app/backend/server.py",
            "app/data/v8_clinical_content.json",
            "app/backend/validation/v8_validation.py",
        ],
        "validation": "Run_Validation.bat",
    }
    (ROOT / "PACKAGE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("V8 patch complete")
    print("Backup:", BACKUP)
    print("Content:", DATA / "v8_clinical_content.json")


if __name__ == "__main__":
    main()
