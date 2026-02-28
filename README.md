# Glycan Morphology ↔ Immune Function Prediction (E2E Demo)

端到端闭环系统：文献检索 → NER/RE → 证据融合 → 可追溯知识图谱 → 多跳推理（含简化双智能体 IRRL）→ 输出假设与证据链。

## 1. 项目结构

```text
.
├── api/                       # FastAPI /query
├── common/                    # 配置与核心数据结构
├── data/demo_data/            # 离线可跑最小样例数据
├── literature_retrieval/      # PubMed 检索 + 证据单元化
├── information_extraction/    # 形态敏感 NER + RE + 软约束
├── evidence_fusion/           # 对齐/消歧/冲突校准/置信融合
├── knowledge_graph/           # KG 节点边构建 + InMemory/Neo4j
├── reasoning/                 # 路径推理 + 简化 IRRL
├── scripts/run_demo.py        # 一键 demo：检索→抽取→入库→查询
├── tests/                     # 单元测试
├── docker-compose.yml         # app + Neo4j
└── config.json                # 可配置参数
```

## 2. 快速启动

### 本地
```bash
poetry install
poetry run python scripts/run_demo.py
poetry run uvicorn api.app:app --host 0.0.0.0 --port 8000
```

### Docker 一键启动
```bash
docker compose up --build
```

## 3. Demo Query

```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "L型糖 vs D型糖 是否具有免疫调节作用？给出证据链", "top_k": 5}'
```

返回每条 Top-K 假设包含：
- 结构形态槽位相关路径节点（如 L/D 构型）
- 多跳证据路径与 provenance
- 路径总分、分解项（edge mean / path length，可扩展为质量、多样性等）
- 可读解释（`explanation`）

## 4. 合规说明

- PubMed 仅调用 E-utilities 元数据/摘要接口。
- 不可访问全文时自动降级为摘要证据单元。
- Demo 默认离线数据（`project.demo_mode: true`）。

## 5. 可替换扩展点

- `information_extraction/ner_re.py`：已预留轻量基线，可替换为 Qwen 微调模型。
- `knowledge_graph/store.py`：可切换 Neo4j 入库。
- `reasoning/path_reasoner.py`：可将简化 IRRL 升级为真实层级策略网络。
