# 单聊固定金额红包（MVP）

## 概述

将现有单聊、钱包、安全校验与 XMTP 消息能力扩展为「单聊固定金额红包」功能。

MVP 定义：

- 仅支持单聊
- 仅支持固定金额
- 仅支持指定接收者领取
- 发红包时先锁定资金
- 接收者点击红包卡片后领取
- 未领取红包到期后自动退款

---

## 目标

- 在单聊中新增“红包”入口与专属红包卡片
- 支持发起红包、查看红包、领取红包
- 保证红包状态与聊天卡片状态一致
- 复用现有钱包、支付密码、XMTP、单聊导航与消息恢复能力

---

## MVP 范围

### 包含

- 单聊红包入口
- 红包创建页
- 红包详情页
- 红包卡片消息
- 红包状态同步
- 后端红包创建 / 查询 / 领取 / 退款接口
- 到期自动退款任务

### 不包含

- 群红包
- 拼手气红包
- 口令红包
- 多接收者红包
- 红包转发继承领取资格
- 复杂运营玩法

---

## 依赖现有能力

### 客户端

- `SingleChatView`
- `SingleChatViewModel`
- `WalletService`
- `WalletPasswordService`
- `WalletPasswordView`
- `XMTPFacade`
- `MessageParser`

### 服务能力

- 钱包余额查询
- 链上交易发送与确认
- XMTP DM 消息发送
- 本地消息恢复
- 后端 API 请求能力

---

## 业务模型

### 红包核心字段

- `redPacketId`
- `conversationId`
- `senderUserId`
- `senderWalletAddress`
- `receiverUserId`
- `receiverWalletAddress`
- `sourceChain`
- `token`
- `amount`
- `blessing`
- `lockedFeeRate`
- `expiredAt`
- `claimTxHash`
- `refundTxHash`
- `status`
- `createdAt`
- `updatedAt`

### 红包状态

- `created`
- `waiting_deposit`
- `claimable`
- `claimed`
- `expired`
- `refunding`
- `refunded`
- `failed`

### 单聊资格规则

- 红包必须绑定单个 DM 会话
- 只有当前聊天指定接收者可以领取
- 非指定接收者不可领取
- 红包消息可被转发，但不会转移领取资格

---

## 客户端流程

### 1. 单聊入口

- 在 `SingleChatView` 附件面板新增“红包”入口
- 点击后进入 `RedPacketCreateView`

### 2. 发红包页

页面输入项：

- 金额
- 币种
- 过期时间
- 祝福语

页面校验：

- 钱包地址合法
- 余额充足
- 手续费可支付
- 网络可用
- 支付密码已设置并验证通过

### 3. 发起流程

1. 创建红包记录
2. 发起锁资 / deposit
3. 锁资成功后更新红包为 `claimable`
4. 发送 `red_packet` 消息到单聊
5. 聊天中插入红包卡片

### 4. 接收流程

1. 接收者在单聊看到红包卡片
2. 点击进入 `RedPacketDetailView`
3. 查询红包详情
4. 做资格校验与账户状态校验
5. 满足条件后执行领取
6. 领取成功后更新详情页与聊天卡片状态

### 5. 红包详情页

展示信息：

- 红包金额
- 代币类型
- 发送者
- 接收者
- 祝福语
- 当前状态
- 过期时间
- 领取结果 / 退款结果

可触发动作：

- 领取
- 刷新状态

---

## 聊天消息层

### 新消息类型

- `MessageParser.MessageType.redPacket`

### 新消息载荷

建议新增 `RedPacketMessageInfo`：

- `redPacketId`
- `conversationId`
- `senderWalletAddress`
- `receiverWalletAddress`
- `tokenSymbol`
- `amount`
- `blessing`
- `expiredAt`
- `status`
- `createdAt`

### 聊天展示要求

- 使用新的 `RedPacketBubble`
- 会话列表最后一条消息预览显示为 `[红包]`
- 红包状态变化后，聊天卡片与详情页同步更新
- 冷启动后可从历史消息和接口恢复红包状态

---

## 客户端新增对象

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
- `CreateRedPacketRequest`
- `CreateRedPacketResponse`
- `RedPacketDetailResponse`
- `ClaimRedPacketRequest`
- `ClaimRedPacketResponse`
- `RefundRedPacketRequest`
- `RefundRedPacketResponse`

---

## 后端接口

### 1. 创建红包

- 创建红包业务记录
- 返回 `redPacketId`
- 初始状态可为 `created` 或 `waiting_deposit`

### 2. 查询红包详情

- 返回红包主信息
- 返回当前状态
- 返回领取资格校验结果

### 3. 领取资格校验

校验项：

- 红包是否存在
- 状态是否为 `claimable`
- 是否已过期
- 是否已被领取
- 当前用户是否为指定接收者
- 接收者账户是否可用

### 4. 执行领取

- 发起 `claim`
- 成功后更新红包为 `claimed`
- 写入 `claimTxHash`

### 5. 执行退款

- 对过期且未领取红包执行退款
- 成功后更新红包为 `refunded`
- 写入 `refundTxHash`

### 6. 查询状态变更

- 用于客户端轮询或恢复状态
- 支持冷启动后拉取最新红包状态

---

## 资金处理主线

### 发起端

1. 用户创建红包
2. 后端生成红包记录
3. 发送者资金锁定到红包专用记录或托管地址
4. 锁资成功后红包进入 `claimable`
5. 红包消息发送到单聊

### 接收端

1. 接收者点击红包
2. 后端校验领取资格
3. 发起 `claim`
4. 领取成功后红包进入 `claimed`

### 到期退款

1. 后端任务扫描到期未领取红包
2. 发起退款
3. 红包进入 `refunding`
4. 成功后进入 `refunded`

---

## 状态同步

### 需要同步的对象

- 红包详情页
- 单聊红包卡片
- 会话列表预览
- 本地缓存 / 冷启动恢复

### 同步要求

- 红包状态更新后，详情页与卡片显示一致
- 卡片点击后展示的是最新状态
- 消息先到、状态后到时，客户端可以补齐状态
- App 重启后仍可恢复红包消息与红包状态

---

## 异常分支

### 发起失败

- 创建红包记录失败
- 余额不足
- 支付密码失败
- 锁资失败
- XMTP 消息发送失败

### 领取失败

- 红包不存在
- 红包状态不为 `claimable`
- 红包已过期
- 红包已被领取
- 非指定接收者
- 接收者账户不可用
- claim 链路失败

### 退款失败

- 到期扫描成功但退款广播失败
- 链上退款成功但状态回写失败

---

## 测试点

- 发送者成功创建红包，锁资成功，聊天中出现红包卡片
- 锁资失败时不发送红包卡片
- 接收者成功领取后，详情页和聊天卡片都显示已领取
- 非指定聊天对象无法领取
- 红包过期后不可领取
- 红包到期自动退款后显示已退款
- XMTP 消息先到、状态后到时卡片仍可正确回填
- App 重启后进入聊天，红包卡片状态可恢复
- 会话列表最后一条为红包时显示 `[红包]`
- 网络错误、支付密码失败、重复点击领取时不会产生重复推进

---

## 推荐 Mindmap 主干

- 单聊固定金额红包（MVP）
- 业务目标
- MVP 范围
- 依赖现有能力
- 红包核心模型
- 红包状态机
- 发起端流程
- 接收端流程
- 红包消息协议
- 客户端页面与组件
- 后端接口
- 锁资 / 领取 / 退款链路
- 状态同步
- 异常分支
- 测试点

