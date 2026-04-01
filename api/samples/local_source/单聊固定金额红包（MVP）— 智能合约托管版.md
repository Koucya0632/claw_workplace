# 单聊固定金额红包（MVP）— 智能合约托管版

## 1. 文档目标

在现有「单聊固定金额红包（MVP）」方案基础上，将资金托管方式正式收敛为**链上智能合约托管**，补齐可进入开发阶段所需的关键设计，包括：

- 合约最小模型
- 链上状态与业务状态边界
- 客户端 / 后端 / 合约职责划分
- 主链路与异常链路
- 幂等与一致性设计
- 接口与任务拆分建议

---

## 2. 设计结论

本方案采用：

- **单聊红包**
- **固定金额**
- **固定 24 小时有效期**
- **指定接收者领取**
- **单链**
- **多 ERC-20 代币**
- **链上智能合约托管资金**
- **后端负责业务编排、token 白名单控制与状态同步**
- **客户端负责交互、签名、展示与恢复**

其中，多 token 的边界定义如下：

- 红包合约支持在创建时传入 ERC-20 token 地址
- 合约层不负责 token 白名单治理
- 后端仅允许白名单内 token 创建业务单
- App 仅保证对白名单 token 红包的创建、展示、领取引导、状态同步与退款编排

这是一个**可落地、可控复杂度、适合 MVP 的多 token 方案**。

---

## 3. MVP 范围

### 3.1 包含

- 单聊红包入口
- 红包创建页
- 红包详情页
- 红包卡片消息
- 链上锁资
- 指定接收者领取
- 到期退款
- 红包状态同步
- 冷启动恢复
- 后端到期扫描与补偿任务

### 3.2 不包含

- 群红包
- 拼手气红包
- 口令红包
- 多接收者红包
- 多链红包
- 原生币红包
- 可升级合约
- Relay / Gas 代付
- 复杂运营玩法
- 跨链红包

---

## 4. 核心架构选择

### 4.1 资金真相

红包资金不保存在后端数据库余额中，也不由纯后端托管地址进行业务记账，而是：

**由链上红包智能合约进行托管。**

也就是说：

- 红包创建成功的前提，是链上锁资成功
- 红包可领取的前提，是合约中已存在有效红包记录
- 红包已领取 / 已退款，以链上最终结果为准

### 4.2 业务真相

后端仍然需要维护业务状态，用于：

- App 查询与展示
- XMTP 红包消息投递
- 冷启动恢复
- 状态聚合
- 补偿重试
- 审计与排障
- 到期任务触发

因此本方案采用：

- **链上状态：资金真相**
- **后端状态：业务编排真相**
- **客户端状态：展示与交互状态**

---

## 5. 职责分层

## 5.1 智能合约负责

- 红包创建与锁资
- 指定接收者约束
- 领取资格的链上最终校验
- 到期判断
- 到期退款
- 防重复领取
- 防重复退款

## 5.2 后端负责

- 创建业务单
- 生成 redPacketId
- 维护 redPacketId 与链上 packetId 映射
- 追踪创建 / 领取 / 退款交易结果
- 聚合红包详情状态
- 发送 XMTP 红包消息
- 进行状态补偿
- 到期扫描并触发退款
- 可观测、日志、告警、审计

## 5.3 客户端负责

- 单聊入口与页面展示
- 红包表单校验
- 支付密码校验
- 签名与发起交易
- 红包详情展示
- 红包卡片展示
- 聊天页状态刷新
- 冷启动后状态恢复

---

## 6. 合约模型设计

## 6.1 设计原则

MVP 合约不追求通用红包平台能力，只做单条红包记录的最小闭环。

目标是：

- 最少字段
- 最少状态
- 最少方法
- 最容易验证
- 最容易测试

## 6.2 合约核心结构

建议合约保存如下字段：

```solidity
struct Packet {
    address sender;
    address receiver;
    address token;
    uint256 amount;
    uint64 expiredAt;
    bool claimed;
    bool refunded;
}
```

说明：

- `sender`：红包发送者
- `receiver`：红包指定接收者
- `token`：ERC-20 代币地址
- `amount`：固定金额
- `expiredAt`：过期时间戳
- `claimed`：是否已领取
- `refunded`：是否已退款

## 6.3 多 Token 设计边界

本方案为单链、多 token 红包模型。

其含义是：

- 同一红包合约可支持多种 ERC-20 代币
- `token` 作为 `createPacket` 的入参传入
- 合约负责资金托管、领取、退款规则
- 合约不负责 token 白名单校验
- token 准入由后端业务层控制

因此，合约层的职责边界是“资金规则正确”，而不是“平台资产治理正确”。

## 6.4 合约最小接口

建议 MVP 仅提供以下方法：

```solidity
function createPacket(
    address receiver,
    address token,
    uint256 amount,
    uint64 expiredAt
) external returns (uint256 packetId);

function claim(uint256 packetId) external;

function refundExpired(uint256 packetId) external;

function getPacket(uint256 packetId) external view returns (Packet memory);
```

## 6.5 合约事件建议

为了支持后端状态同步、冷启动恢复、补偿任务与审计，合约建议至少提供以下事件：

```solidity
event PacketCreated(
    uint256 indexed packetId,
    address indexed sender,
    address indexed receiver,
    address token,
    uint256 amount,
    uint64 expiredAt
);

event PacketClaimed(
    uint256 indexed packetId,
    address indexed receiver,
    address token,
    uint256 amount
);

event PacketRefunded(
    uint256 indexed packetId,
    address indexed sender,
    address token,
    uint256 amount
);
```

要求：

- 事件中必须带 `token`
- 后端以事件 + 交易回执作为链上状态同步依据
- 客户端回写失败时，后端仍可通过事件恢复状态

## 6.6 创建逻辑

`createPacket` 内应完成：

1. 校验 `receiver != address(0)`
2. 校验 `amount > 0`
3. 校验 `expiredAt > block.timestamp`
4. 从发送者地址转入代币到合约
5. 创建 packet 记录
6. 返回 `packetId`

前提：

发送者需要先对红包合约执行 ERC-20 `approve`。

补充约定：

- MVP 阶段红包有效期固定为 24 小时
- `expiredAt` 由后端在创建业务单时生成，并由客户端在发起 `createPacket` 时原样带入
- 前端不提供“自定义过期时间”输入能力

## 6.7 领取逻辑

`claim(packetId)` 内应完成：

1. 校验红包存在
2. 校验未过期
3. 校验未领取
4. 校验未退款
5. 校验 `msg.sender == receiver`
6. 标记 `claimed = true`
7. 将代币转给接收者

## 6.8 退款逻辑

`refundExpired(packetId)` 内应完成：

1. 校验红包存在
2. 校验当前时间已过期
3. 校验未领取
4. 校验未退款
5. 标记 `refunded = true`
6. 将代币退还发送者

### 说明

- `refundExpired` 可以允许任何人触发，因为资产最终只会退回发送者
- 这样后端任务、发送者本人、甚至链上 keeper 都可以触发
- 规则由合约保证，而不是由后端保证

### ERC-20 兼容性约束

- 合约层支持多 token，但 MVP 不等于支持任意 ERC-20
- MVP 仅支持平台验证通过的标准 ERC-20
- 建议使用 OpenZeppelin `SafeERC20`
- 所有金额使用 token 最小单位存储和传输
- 前后端基于 token metadata 做展示换算，但链上只认最小单位金额

---

## 7. 状态设计

## 7.1 链上状态

合约层尽量只保留最少状态，不使用复杂枚举。

链上状态可由字段推导：

- **Funded**：已创建，且 `claimed = false` 且 `refunded = false`
- **Claimed**：`claimed = true`
- **Refunded**：`refunded = true`

是否过期由 `expiredAt` 与当前区块时间比较判断。

## 7.2 业务状态

后端业务状态建议使用：

- `created`
- `pending_deposit`
- `depositing`
- `claimable`
- `claiming`
- `claimed`
- `expired`
- `refunding`
- `refunded`
- `failed`

## 7.3 状态语义

### `created`
已创建业务单，但还未开始链上锁资。

### `pending_deposit`
已完成客户端表单与密码校验，准备发起链上锁资。

### `depositing`
创建红包交易已发出，等待链上确认。

### `claimable`
链上锁资成功，红包已成立，可发送聊天卡片，可进入领取。

### `claiming`
领取交易已发出，等待链上确认。

### `claimed`
领取成功，资产已到接收者地址。

### `expired`
当前已过期，且尚未退款完成。

### `refunding`
退款交易已发出，等待链上确认。

### `refunded`
退款成功，资产已回到发送者地址。

### `failed`
创建 / 领取 / 退款过程中出现不可恢复失败。

---

## 8. 状态迁移规则

建议明确成“状态机表”：

| 当前状态 | 触发条件 | 下一个状态 | 说明 |
|---|---|---|---|
| `created` | 用户确认发送红包 | `pending_deposit` | 创建业务单后进入准备锁资 |
| `pending_deposit` | 客户端发起链上 createPacket | `depositing` | 已广播交易 |
| `depositing` | 链上确认成功 | `claimable` | 红包正式成立 |
| `depositing` | 链上失败 / 超时且确认失败 | `failed` | 创建失败 |
| `claimable` | 到达过期时间且未领取 | `expired` | 业务上标记过期 |
| `claimable` | 接收者发起领取 | `claiming` | 已广播领取交易 |
| `claiming` | 链上确认成功 | `claimed` | 领取成功 |
| `claiming` | 领取失败 | `claimable` 或 `failed` | 可恢复错误回到可领，不可恢复则失败 |
| `expired` | 发起退款 | `refunding` | 已广播退款交易 |
| `refunding` | 链上确认成功 | `refunded` | 退款成功 |
| `refunding` | 退款失败 | `expired` 或 `failed` | 可重试则回 expired |

### 重要规则

1. **只有 `claimable` 状态才允许发送红包消息卡片**
2. **消息投递失败不影响资金状态**
3. **资金状态不可因消息失败而回退**
4. **`claimed` 与 `refunded` 为终态**
5. **`expired` 不是资金终态，只是退款前中间态**

---

## 9. 红包 ID 体系

为了避免开发时混乱，必须区分 3 个 ID：

## 9.1 `redPacketId`
后端业务主键。

用途：

- 后端查询
- 客户端详情查询
- XMTP 消息载荷
- 日志排障
- 幂等关联

## 9.2 `packetId`
链上智能合约红包 ID。

用途：

- 链上 claim
- 链上 refund
- 链上查询

## 9.3 `messageId`
XMTP 红包消息 ID。

用途：

- 聊天消息去重
- 本地消息恢复
- 消息补发校验

## 9.4 关联规则

建议保存映射：

- `redPacketId -> packetId`
- `redPacketId -> messageId`
- `redPacketId -> createTxHash`
- `redPacketId -> claimTxHash`
- `redPacketId -> refundTxHash`

---

## 10. 业务字段补强

在原方案字段基础上，建议补充以下字段：

- `packetId`
- `createTxHash`
- `depositTxHash`
- `claimTxHash`
- `refundTxHash`
- `messageId`
- `messageSendStatus`
- `failureReason`
- `idempotencyKey`
- `version`
- `riskStatus`
- `lastSyncedAt`
- `claimAttemptCount`
- `refundAttemptCount`

说明：

- `createTxHash` 与 `depositTxHash` 对 MVP 可视为同一笔
- `messageSendStatus` 用于标记消息是否投递成功
- `version` 用于后续协议演进
- `riskStatus` 用于保留风控扩展位

---

## 11. 幂等设计

红包系统必须做强幂等。

## 11.1 创建红包幂等

幂等键建议：

- `idempotencyKey = senderUserId + conversationId + clientRequestId`

规则：

- 同一个客户端请求重复提交，只能创建一个 `redPacketId`
- 重试时直接返回已有业务单

## 11.2 创建链上交易幂等

后端或客户端重复触发创建时：

- 若已存在 `createTxHash`，禁止重复创建
- 若链上已确认成功，直接返回既有结果
- 若交易状态未知，进入查询而不是直接重发

## 11.3 消息发送幂等

- 每个 `redPacketId` 只能产生 1 条主红包卡片消息
- 若消息发送失败，可重试补发
- 补发时仍复用同一个 `redPacketId`
- 聊天层按 `redPacketId` 去重，而不是只按文字内容去重

## 11.4 领取幂等

- 同一个 `redPacketId` 同一接收者重复点击领取，只允许有一个有效领取过程
- 已存在 `claiming` 或 `claimed` 时，重复点击直接返回当前状态
- 若链上已确认领取，直接返回 `claimed`

## 11.5 退款幂等

- 同一个 `redPacketId` 只能存在一个有效退款过程
- 已存在 `refunding` 或 `refunded` 时，不再重复发起退款
- 后端定时任务必须按 `redPacketId` 做排他控制

---

## 12. 一致性设计

## 12.1 总原则

**资金状态优先于消息状态。**

也就是说：

- 先有链上锁资成功
- 再有红包聊天卡片
- 如果消息失败，允许补发
- 但不允许因为消息失败把红包资金状态回滚

## 12.2 正确主链路

1. 客户端创建业务单
2. 客户端发起链上 `createPacket`
3. 链上确认成功
4. 后端记录 `packetId` / `createTxHash`
5. 后端状态更新为 `claimable`
6. 后端发送 XMTP 红包消息
7. 客户端展示红包卡片

## 12.3 一致性异常场景

### 场景 A：链上创建成功，但 XMTP 消息发送失败

处理策略：

- 红包仍然有效
- 业务状态保持 `claimable`
- 记录 `messageSendStatus = failed`
- 后端进入消息补发任务
- 发送者详情页提示“红包已创建，消息发送中”或“红包已创建，卡片补发中”

### 场景 B：接收者领取成功，但详情页没及时刷新

处理策略：

- 链上已成功即视为 `claimed`
- 客户端下次打开详情页时重新拉取状态
- 聊天卡片允许被动刷新

### 场景 C：退款成功，但前端仍显示已过期未退款

处理策略：

- 下次状态同步时纠正为 `refunded`
- 会话卡片、详情页、本地缓存统一修正

---

## 13. 客户端交互方案

## 13.1 发红包页

输入项建议保留：

- 金额
- 币种
- 祝福语

额外展示：

- 预计锁资金额
- 预计 gas
- 接收者信息
- 当前链网络
- 固定 24 小时有效期

校验项：

- 钱包已解锁
- 支付密码已验证
- token 余额充足
- gas 余额充足
- 接收者钱包地址有效
- 网络正常

## 13.2 发送主流程

1. 点击红包入口
2. 进入 `RedPacketCreateView`
3. 填写金额、币种、祝福语
4. 校验参数
5. 调起支付密码验证
6. 调用后端创建业务单，拿到 `redPacketId`
7. 发起链上 `createPacket`
8. 等待确认
9. 成功后返回聊天页
10. 插入红包卡片

## 13.3 红包详情页

展示：

- 红包金额
- token
- 发送者
- 接收者
- 过期时间
- 当前状态
- 创建交易哈希
- 领取交易哈希
- 退款交易哈希
- 失败原因（如有）

操作：

- 领取
- 刷新
- 查看链上状态

## 13.4 接收者领取流程

1. 点击红包卡片
2. 打开详情页
3. 拉取红包详情
4. 校验当前用户是否为指定接收者
5. 校验是否已过期
6. 若可领取，则发起 `claim`
7. 进入 `claiming`
8. 确认成功后更新为 `claimed`

---

## 14. 后端接口建议

## 14.1 创建红包业务单

`POST /red-packets`

请求体建议：

```json
{
  "conversationId": "string",
  "receiverUserId": "string",
  "receiverWalletAddress": "string",
  "chainId": 11155111,
  "tokenAddress": "0x...",
  "amount": "1000000",
  "blessing": "恭喜发财",
  "clientRequestId": "string"
}
```

返回：

```json
{
  "redPacketId": "rp_xxx",
  "status": "created",
  "expiredAt": 1711111111
}
```

说明：

- MVP 阶段不由客户端传入过期时间
- 后端在创建业务单时按“当前时间 + 24 小时”生成 `expiredAt`
- 客户端后续发起链上 `createPacket` 时，应使用后端返回的 `expiredAt`

## 14.2 回写创建交易结果

`POST /red-packets/{redPacketId}/deposit-result`

用途：

- 回写 `packetId`
- 回写 `createTxHash`
- 回写确认结果
- 更新状态为 `claimable` / `failed`

## 14.3 查询红包详情

`GET /red-packets/{redPacketId}`

返回建议包含：

- 红包主信息
- 当前业务状态
- 当前链上状态
- 当前用户是否可领取
- 创建 / 领取 / 退款交易哈希
- 失败原因
- 消息发送状态

## 14.4 执行领取

`POST /red-packets/{redPacketId}/claim`

说明：

MVP 可有两种做法：

### 做法 A：客户端直接发链上交易，后端只记录结果
更轻，但客户端更复杂。

### 做法 B：后端先校验并返回 claim 准备信息，客户端再签名发起
更适合当前 App 结构。

MVP 建议先采用 **客户端发交易，后端回写结果**。

## 14.5 回写领取结果

`POST /red-packets/{redPacketId}/claim-result`

用于：

- 回写 `claimTxHash`
- 更新状态为 `claimed` 或恢复到 `claimable`

## 14.6 退款执行接口

`POST /internal/red-packets/{redPacketId}/refund`

仅内部任务调用。

用于：

- 发起退款
- 更新状态为 `refunding`
- 成功后改为 `refunded`

## 14.7 状态变更查询

`GET /red-packets/status/changes?since=timestamp`

用于：

- 冷启动恢复
- 聊天页补齐状态
- 会话列表刷新

---

## 15. XMTP 消息设计

## 15.1 新消息类型

建议保留原方案思路，新增：

- `MessageParser.MessageType.redPacket`

## 15.2 消息体建议

```json
{
  "type": "red_packet",
  "redPacketId": "rp_xxx",
  "conversationId": "dm_xxx",
  "senderWalletAddress": "0x...",
  "receiverWalletAddress": "0x...",
  "tokenAddress": "0x...",
  "tokenSymbol": "USDT",
  "amount": "10",
  "blessing": "恭喜发财",
  "expiredAt": 1711111111,
  "status": "claimable",
  "createdAt": 1711111000,
  "version": 1
}
```

## 15.3 消息投递规则

- 只有在 `claimable` 后才允许发红包消息
- 同一个 `redPacketId` 只允许一条主红包消息
- 本地消息恢复时，允许通过 `redPacketId` 再拉取详情补齐状态

## 15.4 展示规则

- 使用 `RedPacketBubble`
- 会话列表最后一条预览显示 `[红包]`
- 红包状态变化后，聊天卡片同步更新
- 冷启动后允许从历史消息 + 后端状态恢复

---

## 16. 到期退款方案

## 16.1 过期判定

过期规则必须以合约中的 `expiredAt` 为准。

后端只负责发现与触发，不负责定义规则。

MVP 补充规则：

- 红包有效期固定为 24 小时
- `expiredAt` 由后端在创建业务单时生成
- 一旦链上创建成功，后续展示、领取与退款均以链上记录的 `expiredAt` 为准

## 16.2 退款执行方式

后端定时任务：

1. 扫描业务状态为 `claimable` 且已到期的红包
2. 将状态更新为 `expired`
3. 发起 `refundExpired(packetId)`
4. 状态更新为 `refunding`
5. 链上确认成功后更新为 `refunded`

## 16.3 失败补偿

- 广播失败：回到 `expired`，等待重试
- 广播成功但结果未知：进入查询确认，不立刻重复广播
- 已确认 `refunded`：终止重试

---

## 17. 安全注意点

## 17.1 Reentrancy

虽然 ERC-20 一般风险较低，但仍建议：

- 使用 OpenZeppelin 标准库
- 对领取和退款做安全顺序处理
- 必要时加入防重入保护

## 17.2 金额检查

- 禁止 0 金额
- 注意 token decimals
- 所有金额统一使用最小单位存储

## 17.3 权限检查

- `claim` 必须校验 `msg.sender == receiver`
- `refundExpired` 必须校验红包已过期

## 17.4 时间检查

- 统一使用链上时间戳
- 不以客户端本地时间作为最终依据

## 17.5 Token 准入边界

本方案采用“合约无白名单、后端白名单控制”的模式，因此必须明确：

- 后端白名单只能约束平台正式业务流
- 不能阻止外部地址直接调用合约创建非白名单 token 的 packet
- 平台红包业务识别范围应以“后端已登记业务单并完成映射”的红包为准，而不是链上合约中的全部 packet

这意味着：

- 后端创建红包业务单时，必须校验 `chainId + tokenAddress` 是否在白名单内
- 平台后端只处理已登记的 `redPacketId -> packetId` 映射
- 平台客户端只展示和同步平台业务范围内的红包
- 非通过后端建单直接调用合约创建的 packet，不保证会被平台识别、展示、同步或编排退款

## 17.6 多 Token 风险控制

多 token 模式下，风险控制重点不再只是金额和权限，还包括 token 本身的兼容性。

因此建议：

- token 白名单配置必须由后端统一管理
- 白名单校验维度至少为 `chainId + tokenAddress`
- 每个接入 token 在上线前应完成授权、创建、领取、退款全链路测试
- 前端必须明确展示 token symbol、token address、decimals 与余额信息
- 测试用例至少覆盖两个不同 token，避免仅按单 token 假设实现
- MVP 仅支持平台验证通过的标准 ERC-20
- 不支持 fee-on-transfer、rebasing、带黑名单或冻结能力、以及其他非标准行为 token

## 17.7 合约范围控制

MVP 阶段不建议：

- 可升级代理
- 批量红包
- 随机金额
- 签名离线领取
- 复杂角色权限

---

## 18. 失败补偿清单

### 18.1 创建阶段

- 业务单创建成功，链上创建未发出：允许重试
- 链上创建已发出，结果未知：查链确认
- 链上创建成功，消息发送失败：补发消息

### 18.2 领取阶段

- 领取请求重复点击：按 `claiming / claimed` 返回当前状态
- 链上领取广播成功但回写失败：由链上同步任务修正
- 链上领取失败：恢复为 `claimable` 或标记 `failed`

### 18.3 退款阶段

- 任务重复扫描：通过状态机和排他锁防重
- 链上退款成功但业务未更新：同步任务修正为 `refunded`

---

## 19. 客户端新增对象建议

### View

- `RedPacketCreateView`
- `RedPacketDetailView`
- `RedPacketBubble`

### ViewModel

- `RedPacketCreateViewModel`
- `RedPacketDetailViewModel`

### DTO / Type

- `RedPacketMessageInfo`
- `RedPacketStatus`
- `RedPacketChainStatus`
- `CreateRedPacketRequest`
- `CreateRedPacketResponse`
- `RedPacketDetailResponse`
- `ClaimRedPacketRequest`
- `ClaimRedPacketResponse`
- `RefundRedPacketResponse`

---

## 20. 开发任务拆分建议

## 20.1 合约侧

1. 设计红包合约最小数据结构
2. 实现 `createPacket`
3. 实现 `claim`
4. 实现 `refundExpired`
5. 实现合约事件
6. 编写合约单元测试
7. 测试网部署与验证

## 20.2 后端侧

1. 红包业务表设计
2. token 白名单配置与校验
3. `redPacketId / packetId / messageId` 映射设计
4. 创建红包接口
5. 创建结果回写接口
6. 红包详情接口
7. 领取结果回写接口
8. 到期扫描任务
9. 状态同步任务
10. XMTP 红包消息发送与补发

## 20.3 客户端侧

1. 单聊入口接入
2. 红包创建页
3. 红包详情页
4. 红包卡片组件
5. 发送流程
6. 领取流程
7. 状态轮询 / 恢复
8. 会话列表 `[红包]` 预览接入

---

## 21. MVP 测试点建议

- 创建红包成功后链上可查到 packet
- 链上成功前不发送红包卡片
- 创建成功后聊天中出现红包卡片
- 非指定接收者无法领取
- 指定接收者领取成功后详情页与卡片都变为已领取
- 红包过期后不能领取
- 过期后退款成功，详情页与卡片显示已退款
- XMTP 消息发送失败时，红包仍保持有效并可补发卡片
- App 冷启动后仍能恢复红包状态
- 重复点击领取不会重复推进
- 到期扫描重复执行不会重复退款
- 链上状态与业务状态不一致时，可被同步任务修正
- 至少使用两种白名单 token 覆盖创建、领取、退款主链路

---

## 22. 最终结论

如果本项目正式采用**链上智能合约托管**，那么这套 MVP 方案是合理的，且明显比“纯后端记账红包”更适合钱包型聊天产品。

但为了控制复杂度，MVP 必须坚持以下限制：

- 只做单聊
- 只做固定金额
- 固定 24 小时有效期
- 只做指定接收者
- 只做单链多 ERC-20（仅限白名单 token）
- 不做 Relay / AA / Gas 代付
- 不做群红包和随机玩法

这样才能在保证可落地的同时，把风险控制在可开发、可测试、可验证的范围内。
