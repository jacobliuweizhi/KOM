# KOM Project Code Package

生成时间：2026-06-16

本文件夹用于集中提交 KOM/KOA 项目相关代码与必要配置。整理时保留项目自有代码、运行入口、验证脚本、构建脚本、论文图表与方法学生成脚本，并排除了第三方依赖、缓存、日志、旧版重复包、IDE 配置、临时锁文件和外部运行时主体。

## 目录说明

| 目录 | 内容标记 | 用途 |
|---|---|---|
| `01_final_workbench_code` | 最终工作台代码 | 本地临床工作台主代码，包括后端服务、前端静态文件、配置、证据数据、验证入口、部署配置和启动脚本。 |
| `02_reviewer_demo_source` | 审稿/展示界面源码 | React/Vite 展示界面源码、测试脚本、构建脚本和单文件展示版。已排除 `node_modules`、截图视频、测试结果和构建缓存。 |
| `03_reproducibility_scripts` | 可复现流程脚本 | 项目根目录、`C:\koa_project` 和投稿补丁包中的数据整理、审计、评估、工作台构建、结果补全和导出脚本。 |
| `04_figures_methods_generation` | 图表与方法学生成 | 图表生成脚本、图表源数据、表格、审计说明，以及补充方法学文档生成脚本。 |
| `05_model_pipeline_protocols` | 模型流程协议 | KOMRisk 训练冻结协议和最终锁定流程脚本索引，用于说明模型与特征管线。 |
| `06_review_ready_runtime_notes` | 运行说明与查看文件 | 外部运行时说明和可直接打开的单文件展示版。 |

## 清单文件

- `00_CODE_INVENTORY.csv`：逐文件清单，包含相对路径、类型、大小和修改时间。
- `00_PACKAGE_SUMMARY.json`：整理包摘要，包含文件数、总大小和生成路径。

## 整理规则

- 保留：项目自有 `.py`、`.ts`、`.tsx`、`.js`、`.mjs`、`.html`、`.css`、`.json`、`.jsonl`、`.csv`、`.svg`、`.bat`、`.sh`、`.yaml/.yml` 等代码与必要配置/轻量数据文件。
- 排除：`.git`、`.idea`、`.venv`、`.claude`、`node_modules`、`dist`、`artifacts`、`test-results`、`__pycache__`、运行日志、临时文件、外部 Python 运行时主体、旧版重复目录和大型压缩包。
- 处理：整理包副本中已将开发工具临时命名和报告标题改为中性项目命名；原始项目文件未被修改。

## 使用提示

若需运行前端源码，请在 `02_reviewer_demo_source` 内按 `package.json` 安装依赖后运行。若需运行最终工作台，请从 `01_final_workbench_code` 中的启动脚本或 `README_START_HERE.md` 开始；外部 Python 运行时未随本代码包复制，可按项目环境重新配置。
