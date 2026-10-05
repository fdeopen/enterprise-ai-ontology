# Ontology DSL 1.0

DSL 是一个 JSON 兼容的对象树，JSON 和 YAML 只是两种序列化形式。`schema_version` 描述 DSL 协议版本，`version` 是某个业务模型的版本；二者独立演进。ID 是稳定技术标识，label 是可修改的展示名称。

## 对象与引用

| 类型 | 定义位置 | 关键字段 | 语义 |
|---|---|---|---|
| Entity | `entities[]` | id / label / description / primary_key / properties | 具有独立身份的业务对象类型 |
| Property | 实体 properties、动作 parameters、事件 payload | id / type / required / nullable / sensitive | 值字段及其元数据；ID 在所在列表内唯一 |
| Relationship | `relationships[]` | source / target / cardinality | 实体间有方向的业务关联 |
| Action | `actions[]` | entity / parameters / requires_rules / emits / human_approval | 可由外部应用实现的业务操作契约 |
| Rule | `rules[]` | entity / conditions / match / severity / message | 作用于单个实体记录的条件断言 |
| Event | `events[]` | entity / payload | 与实体有关的业务事实通知契约 |
| AIScenario | `ai_scenarios[]` | task / entities / actions / inputs / outputs / success_metrics / human_oversight | AI 用例及其业务依赖、评估目标、人工职责 |

每个有名字的对象都有必填 `id`、`label`、`description`。ID 使用 `[A-Za-z][A-Za-z0-9_]{0,63}`。顶层 ID 在各自类型中唯一；不同类型允许同名，图谱用 `类型:ID` 区分。Property 是嵌入式定义，无全局属性表；复用同名属性不表示它们是同一个业务字段。

Entity 主键必须引用该实体的 required=true、nullable=false 的 string / integer 属性。关系基数可选 `one_to_one`、`one_to_many`、`many_to_one`、`many_to_many`，方向为 source → target。自关联和环形关系合法；本工具不把关系视为父子树，也不检查关系实例或数据库外键。

Action 的 requires_rules 必须属于同一 entity；emits 可关联其他实体的事件，例如订单操作也可以声明产生库存事件。AI 场景中的每个引用必须存在，各个引用列表是独立的显式依赖；不会自动补齐传递依赖。

## 最小可运行示例

保存为 `order.yaml`，运行 `enterprise-ontology validate order.yaml`：

```yaml
schema_version: '1.0'
id: Commerce
name: 订单业务模型
version: 0.1.0
industry: 电商
description: 用于说明订单发货审批的最小模型。
entities:
  - id: Order
    label: 订单
    description: 订单状态与金额。
    primary_key: id
    properties:
      - id: id
        label: 订单号
        description: 订单唯一标识。
        type: string
        required: true
      - id: status
        label: 状态
        description: 简化订单状态。
        type: enum
        required: true
        enum_values: [pending, paid, shipped]
rules:
  - id: PaidBeforeShipping
    label: 发货前检查支付
    description: 发货审批时使用的前置断言。
    entity: Order
    conditions:
      - property: status
        operator: eq
        value: paid
    message: 发货前应确认订单已支付。
actions:
  - id: ShipOrder
    label: 批准发货
    description: 由仓库人员确认并执行发货。
    entity: Order
    requires_rules: [PaidBeforeShipping]
    emits: [OrderShipped]
    human_approval: true
events:
  - id: OrderShipped
    label: 已发货
    description: 订单完成发货操作的业务事件。
    entity: Order
```

数组缺省值为空，schema_version 缺省 `1.0`，version 缺省 `0.1.0`。至少定义一个实体和一个属性。类型之外的字段会报错，以发现拼写错误；不要加入任意自定义字段后指望工具忽略。

## 属性类型

| type | 值形态 | 备注 |
|---|---|---|
| string | 字符串 | 适合编码、标识和正文 |
| integer | 整数 | 不把 bool / 1.0 / '1' 转成整数 |
| number | 整数或有限浮点数 | 不接受 NaN / Infinity；精确货币可使用整数最小货币单位 |
| boolean | true / false | 不把 'true'、0、1 当作布尔 |
| date | `YYYY-MM-DD` | 严格检查日历日期；YAML 中保留为字符串 |
| datetime | 带时区的 ISO 8601 字符串 | 必须含 T，例如 `2026-01-01T09:00:00+08:00` |
| enum | 字符串 | enum_values 必须非空、唯一；其他类型不能配置它 |
| string_list | 字符串数组 | 元素不能隐式转换 |
| json | JSON 值 | 允许嵌套对象/数组；null 仍受 nullable 控制 |

`required` 控制字段是否必须出现；`nullable` 独立控制显式 null。可选字段不等于可填 null。`sensitive` 和 `unit` 为说明元数据，不自动实现脱敏、权限或单位换算。

文件读取及记录检查拒绝超过 ±(2^53−1) 的整数，以便定义在 Python 和浏览器间往返时不丢失精度。大数字标识使用 string。YAML 数值由 PyYAML SafeLoader 处理，金额和编码应显式使用合适类型及引号；本项目不宣称完整实现 YAML 1.2。

## 规则语义

Rule 是“必须满足的断言”，不是 `if ... then ...` 脚本。所有条件固定引用 rule.entity 的一个直接属性，不支持路径表达式、函数、外部读取或动态代码。

| operator | 语义 | 字面量限制 |
|---|---|---|
| eq / ne | 等于 / 不等于 | 与属性类型一致；nullable 属性可比较 null |
| gt / gte / lt / lte | 大于 / 不小于 / 小于 / 不大于 | number、integer、date、datetime；非空值 |
| in / not_in | 是 / 不是给定候选值之一 | 非空数组，每个候选值匹配属性类型 |
| contains | 包含子串或字符串元素 | string / string_list，value 必须为 string |
| exists / absent | 字段存在且非 null / 不存在或为 null | value 省略或为 null |

`match: all`（默认）要求所有条件为真；`any` 要求至少一个。`severity: error`（默认）失败使记录检查退出码为 2；warning 失败仍返回 valid=true，但保留逐条失败结果。

缺失字段不会让 ne / not_in 自动通过；除 absent 外，缺失字段的比较一律为 false。显式 null 可以参加 eq/ne/in/not_in，在排序和 contains 中返回 false。日期/时间排序先解析，datetime 按带时区的时间比较；eq/ne/in/not_in 按原始值比较，时间等价但字符串表示不同的值不相等。

`check` 先验证字段与类型；失败时不运行规则。字段通过后，检查**该实体的全部规则**，包括为动作审批设计的前置断言。例如 pending 订单不能通过“发货前已支付”规则，这说明它不满足该断言，不表示 pending 是非法生命周期状态。规则试验不模拟状态迁移，不检查其他实体或实际审批记录。

Action 的 requires_rules 和 human_approval 是交给业务系统的契约，本工具不会执行动作，也不会自动执行外部授权。接入业务服务时，应用须按当前动作选择相应前置规则，并落实权限、审批、幂等与事件发布。

## 结构与语义校验

导出的 [JSON Schema](../schema/ontology.schema.json) 基于 [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/schema)，可供编辑器校验字段、类型和枚举；`additionalProperties: false` 帮助发现未声明字段。[官方对象约束说明](https://json-schema.org/understanding-json-schema/reference/object)

跨对象引用、局部 ID 唯一、主键引用、规则字面量与属性类型一致性属于语义检查，必须调用 CLI `validate` 或 Python `Ontology.model_validate`。仅通过 JSON Schema 不代表模型语义有效。

JSON 与 YAML 都拒绝重复 key。[YAML 规范要求映射键唯一](https://yaml.org/spec/1.2.2/)。项目使用 SafeLoader，并进一步禁止 alias、merge key、非 JSON 值、非字符串键、多文档和自定义对象构造。yes/no/on/off、日期保留为字符串；只有小写 true/false 隐式解析为布尔。

单个输入最大 2 MiB、嵌套深度 40、节点数 50,000。实体最多 100，关系 200，其余顶层列表各 100；每个实体/动作/事件最多 100 个属性，每个规则最多 30 个条件。报错包含字段路径；不会自动纠正定义。
