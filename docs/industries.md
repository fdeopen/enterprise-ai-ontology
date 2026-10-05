# 五个行业示例

所有示例为虚构业务模型，不含真实人员或企业数据。每个行业都有 6 个实体、3 个动作、4 个规则、3 个事件、2 个 AI 场景；JSON / YAML 两份定义语义一致。

| 行业 / CLI ID | 核心实体 | 业务动作 | AI 场景 |
|---|---|---|---|
| 电商 / ecommerce | 客户、商品、库存、订单、包裹、售后申请 | 批准发货、审核售后、调整库存 | 售后客服助手、履约异常分析 |
| 外贸 / foreign_trade | 海外客户、询盘、报价、合同、出运、贸易单据 | 发送已审报价、申请订舱、放行单据 | 多语言询盘助手、单证一致性助手 |
| 制造 / manufacturing | 销售订单、生产工单、设备、物料批次、检验、维护工单 | 批准工单启动、复核检验、安排维护 | 质量异常追溯、设备维护助手 |
| 医美 / medical_aesthetics | 客户、咨询、专业人员、服务计划、预约、随访 | 确认已审计划、确认预约、转交复核 | 咨询资料整理、随访任务分流 |
| 招聘 / recruitment | 岗位、候选人、申请、面试、能力评估、录用方案 | 推进申请、确认评估、发送已批方案 | 岗位能力证据助手、面试纪要助手 |

## 定义源文件

- [电商 YAML](../src/enterprise_ai_ontology/examples/ecommerce/ontology.yaml) / [JSON](../src/enterprise_ai_ontology/examples/ecommerce/ontology.json)
- [外贸 YAML](../src/enterprise_ai_ontology/examples/foreign_trade/ontology.yaml) / [JSON](../src/enterprise_ai_ontology/examples/foreign_trade/ontology.json)
- [制造 YAML](../src/enterprise_ai_ontology/examples/manufacturing/ontology.yaml) / [JSON](../src/enterprise_ai_ontology/examples/manufacturing/ontology.json)
- [医美 YAML](../src/enterprise_ai_ontology/examples/medical_aesthetics/ontology.yaml) / [JSON](../src/enterprise_ai_ontology/examples/medical_aesthetics/ontology.json)
- [招聘 YAML](../src/enterprise_ai_ontology/examples/recruitment/ontology.yaml) / [JSON](../src/enterprise_ai_ontology/examples/recruitment/ontology.json)

每个目录还有 `records.json`：指定 entity 及 valid / invalid 两条记录。CLI `init` 会将它们拆成 `record.valid.json`、`record.invalid.json`，便于直接运行检查。

## 一条可追溯业务链

电商示例：Customer → Order → ReturnRequest。SupportCopilot 场景读取客户问题、订单物流和政策证据，输出答复草稿与审核建议；ApproveReturn 动作引用 ReturnRequested 规则并声明 ReturnApproved 事件；客服保留审批责任。场景指标包括引用正确率、人工采纳率和错误退款建议率，后续可接入评估工具。

制造示例：SalesOrder → WorkOrder → MaterialLot / Inspection。QualityCopilot 整理异常证据，检验工程师复核后通过 ApproveInspection 声明 InspectionApproved。图谱表示各定义之间的关系，不推断缺陷因果，也不会直接控制设备。

医美聚焦资料整理与服务协同，招聘聚焦授权资料中的岗位证据。示例中的人工职责用于说明应用边界，不是自动化临床或录用决策功能。
