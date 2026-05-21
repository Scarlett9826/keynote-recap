# Google I/O 2026 主题演讲完整复盘

<div class="callout" markdown="1">

## 📌 整体概要

- **定调：正式进入 Agentic Gemini 时代，发布主角是完整 Agent 栈**
    - Sundar 宣布 Google 已进入「AI 价值兑现期」——核心转变是让 AI **从回答问题变为替用户执行任务**
    - 今年发布主角从单个模型上升到一整套 Agent 栈：**前端**（Spark / Information Agents / Daily Brief / Halo）+ **中台**（UCP / AP2 / Universal Cart / Search 生成式 UI）+ **底层**（Antigravity 2.0 + Managed Agents API）
    - 关键用户数据：月处理 Token **3,200T**（同比 7×）/ Gemini App 月活 **9 亿**（同比翻倍）/ AI Mode 月活破 **10 亿**（上线仅一年）/ 开发者月活 **850 万** / Nano Banana 累计生成 **500 亿**张图
    - **核心判断**：Google 不想在「哪个模型最聪明」上跟 OpenAI / Anthropic 比，正在做「AI 时代的 AWS」

- **模型层：Gemini 3.5 家族首发 + Google 首个全模态模型 Omni**
    - **Gemini 3.5 Flash**（今日可用）：能力整体超越上一代旗舰 3.1 Pro；速度比其他前沿模型 **4×**、Antigravity 内 **12×**；头部 Cloud 客户切 80% workload 可**年省 $1B**
    - **Gemini Omni Flash**（今日可用）：任意输入→任意输出的全模态模型；首发于 Gemini App / Google Flow / YouTube Shorts
    - **Gemini 3.5 Pro**：下月发布，定位高精度、长链路推理、复杂代码重构
    - **核心判断**：3.5 Flash 是「牺牲知识深度，换取执行能力」——Google 在打吞吐量战争，不是 benchmark 战争

- **面向普通用户：7×24 小时连接所有 Google 生态服务的 Agent**
    - **Gemini Spark**：首个 24/7 个人 AI Agent，跑在 Google Cloud 专用虚拟机上，**关电脑也跑**——下周仅对美国 AI Ultra 订阅者 Beta
    - **Information Agents**：Search 中后台运行的信息追踪 Agent，按问题紧急度自动设触发器，主动推送
    - **Daily Brief**：每日个性化摘要，综合邮箱 / 日历 / 任务，给优先级排序和行动建议（今日上线 US 付费用户）
    - **Android Halo**：手机顶部 Agent 实时进度指示 UI——不打断当前操作

- **面向开发者：Antigravity 升级成标准化开发范式，逐步取代 Gemini CLI 和 Code Assist**
    - **Antigravity 2.0 桌面应用**：Agent 编排中心，支持并行 subagent / hooks / async task / 生态集成
    - **Antigravity CLI**：命令行 Agent 开发——Gemini CLI 已发布迁移指南
    - **Managed Agents API**：一个 API 调用即可启动 Agent（含隔离 Linux 持久化环境）
    - **Google AI Studio 移动版 + 原生 Android 支持**：一句 prompt 构建 App，可直发 Google Play 测试轨道
    - 标志性 demo：**93 个 subagent / 12 小时 / 15K 模型调用 / 2.6B token / <$1,000 API 成本，写出可运行 OS**（含 Doom）

- **搜索：25 年来最大升级 + 把 Antigravity 嵌进搜索结果**
    - 全新智能搜索框：跨模态输入、智能扩展提示——今日起 rollout
    - **AI Overviews 与 AI Mode 融合**——同一条体验全球今日上线，AI Mode 升级到 Gemini 3.5
    - **Generative UI in Search**：每次查询动态调起 Antigravity harness，**实时生成可交互组件**——今夏对所有人**免费**
    - **Mini-app**：搜索生成持久化、状态化的微应用（如 Weekend Planner），跨 Gmail / Photos / Calendar / Maps，可分享共编
    - **核心判断**：传统网站流量结构会进一步往下走——这是 SEO 与内容产业的下一次结构性冲击

- **电商：Agent 可调用的完整 AI 购物链路**
    - **UCP（Universal Commerce Protocol）**：Agent 电商时代的 HTTP，开源标准——Walmart / Etsy / Wayfair / Best Buy 创始合作（NRF 已发），I/O 新增 Amazon / Meta / Microsoft / Salesforce / Stripe
    - **AP2（Agent Payments Protocol）**：Agent 付款授权协议——**品牌 + 商品 + 金额**三道护栏 + 防篡改数字授权书
    - **Universal Cart**：跨 Search / Gemini / YouTube / Gmail 的统一购物车，支持智能比价、兼容性检查、多商家合并结算
    - **核心判断**：UCP 不是产品而是协议——这是这次 I/O 最被低估的发布，谁定义协议谁就握住下一轮分发权

- **智能眼镜：今年秋季首发 Audio 款，沉浸式 XR 持续跳票**
    - 与 Warby Parker / Gentle Monster 合作两款样式——一个主打日常、一个主打潮流
    - Gemini 驱动 / 调度 Calendar / 实时翻译 / 看见即问 / 拍照 + AI 编辑 / 导航
    - **首次同时支持 Android + iOS**；价格未公布；与 XREAL 合作的 XR 款持续跳票
    - **核心判断**：没说价格、没说销量目标，是个谨慎的「软发布」——真正的 AR 时刻至少还要一年

- **付费：C 端付费逻辑重构，为 Agent 场景铺路**
    - 从「限定提问次数」转向「按实际 **Compute used** 计费」——按 prompt 复杂度、功能类型、上下文深度动态扣额，**每 5 小时重置**
    - 订阅档位：Plus / Pro / **新增 Ultra $100**（5× Pro 用量）/ Ultra **$200**（原 $250 降至 $200，对标 ChatGPT Pro）
    - Antigravity 用量、Spark 使用权、20TB 云存储、YouTube Premium、Health Premium、Home Premium 全部打包
    - **核心判断**：从订阅「AI 助手」变成订阅「Google 全家桶 + AI 配额」——对所有 AI 订阅产品的施压

- **基础设施：第八代 TPU 双芯片分工 + 年度 Capex $180-190B**
    - **TPU 8t（训练）**：9,600 chips/pod、2 PB HBM 共享、**121 ExaFlops/pod**、Virgo Network、单 pod 算力 3× 上一代
    - **TPU 8i（推理）**：288 GB HBM、384 MB SRAM、19.2 Tb/s ICI、Boardfly 拓扑、**性能/价格 +80%**、CAE 加速器延迟 -5×
    - 共同：首次以 Google 自研 **Axion ARM CPU** 为 host、**第 4 代液冷**、**Goodput >97%**
    - **Capex**：$31B（2022）→ $180-190B（2026），约 6×
    - **核心判断**：训练 / 推理彻底拆产线——Google 已把 AI 工作负载分成两条独立产线，按各自瓶颈做硬件优化

- **科学与安全：AGI 已在地平线**
    - **Gemini for Science**：AlphaEarth Foundations / WeatherNext（提前 3 天预报 Cat-5 飓风 Melissa）/ AlphaFold + AlphaGenome 服务数百万科学家 / Isomorphic Labs 已进 pre-clinical
    - **CodeMender**：自动发现并修复软件漏洞的代码安全 Agent，今日邀少数专家测 API
    - **SynthID**：累计水印 1000 亿张图/视频 + 6 万年音频；OpenAI / Kakao / ElevenLabs 加入；Search/Chrome 内可一键查内容来源
    - **Build with Gemini XPRIZE**：奖池 $200 万，9 月洛杉矶决赛

- **交付节奏：核心能力今日可用，部分功能分阶段推出**
    - **今日可用**：Gemini 3.5 Flash（全产品 + API）、Gemini Omni Flash、Antigravity 2.0、AIO+AI Mode 全球合并、Gemini App Neural Expressive 设计、Daily Brief、Stitch 实时协作、Google Flow 五项更新
    - **本周**：Gemini Spark trusted testers；Google AI Studio 移动端预注册
    - **下周**：Spark Beta（仅美国 AI Ultra 订阅者）
    - **今夏**：Information Agents、Search Generative UI（**免费**）、Docs Live、Ask YouTube、Universal Cart、Google Pics、Spark in Chrome
    - **今秋**：Audio 智能眼镜首发
    - **下月**：Gemini 3.5 Pro

</div>

---

## 一、Agent 体系（最大主线）：从「回答问题」到「替你执行」

> **定位**：今年 I/O 的发布主角，从单个模型上升到了整套 Agent 栈。**Agent = 跑在 Google Cloud 上的虚拟机 + Gemini 3.5 + Antigravity Harness + Workspace 集成**。这是 Google 与 OpenAI ChatGPT Agent / Anthropic Claude Code 路线的正面对决。

### 1.1 Gemini Spark — 24/7 个人 Agent

![Gemini Spark](frames/frame_31.jpg)

**定位**：面向消费者的"个人 AI Operator"，跑在 **Google Cloud 专属虚拟机**上，关电脑也持续运行。这是与 ChatGPT Agent / Operator 直接对标的产品。

**架构**：

| 层 | 组件 |
|---|---|
| 模型 | Gemini 3.5 Flash + Antigravity Harness |
| 执行环境 | Google Cloud 专属 VM（用户级隔离） |
| 数据源 | Gmail、Docs、Slides、Calendar 等 Workspace 一等公民 |
| 工具扩展 | 未来几周通过 **MCP** 接入 Canva、OpenTable、Instacart 等 |
| 入口 | Gemini app → 后续邮件 / IM / Chrome |

**现场展示的三类典型场景**：

- **跨数据源汇编邮件**：`/ghostwriter` 个人 skill 让邮件听起来像本人，从 Docs / Gmail / chat 抓素材
- **Block Party 多任务并发**：一个 prompt 触发 RSVP 表（实时同步 Gmail）+ Slides hype deck + 自动追跟未回复邻居——产物是 Sheets / Slides 这种**可继续编辑的工件**，不是聊天框文字
- **手机端语音 brain-dump**：一句话甩三个 thread（标记会议为粉色 / 给新邻居写信 / 整理学期末待办），Spark 自动拆成三个独立任务并发执行

![Spark email demo](frames/frame_32.jpg)

![Block party demo](frames/frame_33.jpg)

![Phone brain-dump](frames/frame_34.jpg)

**上线节奏 + 价格**（联网补充）：

| 时间 | 范围 |
|---|---|
| 本周 | trusted testers |
| **下周** | Beta，**仅美国** Google AI Ultra 订阅用户（$100 与 $200 档均可） |
| 今夏 | Spark in Chrome（agentic browser） |
| 今年晚些时候 | Android Halo（手机顶部进度 UI） |

> 📎 **补充信源**：根据 [blog.google/.../sundar-pichai-io-2026](https://blog.google/innovation-and-ai/sundar-pichai-io-2026/) 与 [next-evolution-gemini-app](https://blog.google/innovation-and-ai/products/gemini-app/next-evolution-gemini-app/)，Spark 后续路线包括：邮件/IM 直接驱动、自定义 subagent、AP2 授权支付（指定预算和商家）、Chrome 内 agentic browser。

**风险设计**：付款、发邮件等高风险操作必须用户确认；用户可在设置查看 / 管控权限与已连接服务。

### 1.2 Information Agents in Search

![Search agents](frames/frame_40.jpg)

**定位**：搜索中可创建、定制、管理多个 7×24 后台运行的 AI Agent，在合适时机推送综合更新。**这是把搜索从"一次性问答"升级为"持续追踪任务"**。

**能力范围**：

- **扫描源**：全网（博客 / 新闻 / 社交贴）+ Google 实时数据（金融 / 购物 / 体育）
- **触发逻辑**：根据用户提问的紧急程度自动设置触发器（实时 / 定时 / 事件驱动）
- **场景示例**：
    - 「P/E < 15、现金流为正、低负债的大盘 biotech 股」→ 实时金融数据接入
    - 「我喜欢的运动员的球鞋联名/发售」→ 跨 blog、社交、Shopping Graph
    - 「公寓搜索」→ 跨网站、社交、论坛全网扫

**上线**：今夏，先面向 Google AI Pro 和 Ultra 订阅者。

### 1.3 Daily Brief

![Daily Brief](frames/frame_50.jpg)

**定位**：开箱即用的每日个性化摘要 Agent。综合邮箱 / 日历 / 任务，**优先级排序 + 给出下一步行动建议**。

**今日上线**，对 US Plus / Pro / Ultra 用户。"早餐前的助手"。

### 1.4 Android Halo

**定位**：让用户一眼看到 Agent 正在做什么，**不打断当前操作**。手机屏幕顶部的微妙状态指示，Agent 接受任务/进入 live 模式/发消息时显示进度。

**支持**：Gemini Spark + 其他兼容 Agent。**今年晚些时候**上线。

---

## 二、开发者平台：Antigravity 2.0 与 Managed Agents

### 2.1 Antigravity 2.0 桌面应用

**定位**：Agent 编排中心。从去年 11 月发布的"IDE + 实验性 agent"，2.0 翻转为 **agent-first**——核心是 agent 对话、agent 产出物、多 agent 编排，IDE 反而退到次要位置。

**新增能力**：

- **CLI**（**取代 Gemini CLI**——已发布迁移指南）+ **SDK** + 原生语音
- 与 Android / Firebase / Google AI Studio 集成
- **Agent Harness 三个新原语**：subagents（子代理）+ hooks（钩子）+ async task management（异步任务）
- 与 Gemini 3.5 Flash 协同优化，在 Antigravity 内 **12× 加速**（普通环境 4×）

> 📎 **补充信源**：根据 [blog.google/.../google-io-2026-all-our-announcements](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/)，Antigravity 同时取代 Gemini Code Assist——开发者被引导到 Antigravity + Managed Agents API。

### 2.2 标志性 Demo：12 小时写一个能跑 Doom 的操作系统

![OS task plan](frames/frame_26.jpg)

> "Over 12 hours, 93 subagents working in parallel made over 15,000 model requests and processed 2.6 billion tokens."

| 指标 | 值 |
|---|---|
| 时长 | **12 小时** |
| 并行 subagent | **93 个** |
| 模型调用 | **15,000+ 次** |
| 处理 token | **2.6B** |
| API 成本 | **< $1,000** |
| 成果 | 可运行 OS（命令行 + Doom 游戏 + 动画） |

> "This was not possible on Gemini 3.1 Pro, but thanks to the performance and cost efficiencies of Gemini 3.5 Flash, building an entirely functional operating system consumed less than $1,000 of API credits."

现场延伸 demo：让 agent 给 OS 加 video / keyboard 驱动让 Doom 跑起来。

![Doom demo](frames/frame_27.jpg)

Varun 顺带提到他们用同样模式造了**图片编辑套件、即时通讯 app、多用户协作平台**——意图明确：**多天工程压缩到几小时**。

### 2.3 Managed Agents API

**定位**：一个 API 调用即可启动 Agent，**开发者无需自建 Agent 框架**——直接复用 Antigravity 的 harness。

- 隔离 Linux 环境中推理、调用工具、执行代码
- **持久化环境**：后续调用恢复所有文件和状态
- 支持自定义 Agent（通过 markdown 定义指令和 skills，文件名 `AGENTS.md` / `SKILL.md`）

> 📎 **补充信源**：[blog.google/.../managed-agents-gemini-api](https://blog.google/innovation-and-ai/technology/developers-tools/managed-agents-gemini-api/)。本质是把 OS demo 的能力直接 API 化。

### 2.4 Google AI Studio 扩展

- **移动端 App**（本周预注册）：随时随地捕捉灵感，回桌面就有可用原型
- **Workspace 集成**：Agent 可原生调用 Workspace API
- **导出到 Antigravity**：一键从 AI Studio 到本地开发 + 生产
- **原生 Android 支持**：一句 prompt 构建 Android App，可直接发布到 Google Play 测试轨道

---

## 三、模型层：Gemini 3.5 谱系

### 3.1 Gemini 3.5 Flash — 主打"便宜 + 快 + 强执行"

![3.1 Pro vs 3.5 Flash 双柱状图：Coding 76.2% / GDPval Elo 1656 / MCP Atlas 83.6%](frames/frame_21.jpg)

**定位**：为 **agentic 工作流量身设计**——大量 API 请求 + 长链路任务 + 工具调用。**用执行能力弥补纯推理的不足**。

**性能对比**（vs 上一代旗舰 3.1 Pro）：

| 任务类别 | 3.5 Flash 表现 |
|---|---|
| 编码（Terminal-Bench 2.1）| **76.2%** vs 3.1 Pro 70.2% |
| 真实世界 Agentic（GDPval-AA Elo）| **1656** vs 3.1 Pro 1614 |
| 工具调用（MCP Atlas）| **83.6%** vs 3.1 Pro 73.2% |
| 输出速度 | 比其他前沿模型 **4×**，Antigravity 内 **12×** |

> 📎 **补充信源**：[blog.google/.../google-io-2026-all-our-announcements](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/)。在 Artificial Analysis 智能 vs 速度图上位居右上象限。

![Artificial Analysis Index vs Output Speed 散点图：3.5 Flash 在右上角孤立领跑（vs GPT-5.5 / Claude Opus 4.7 / Sonnet 4.6 / Haiku / 3 Flash）](frames/frame_22.jpg)

**主力产品默认模型**：

- Gemini App（全球所有用户的默认模型）
- AI Mode in Search（全球）
- Google Antigravity
- Gemini API（Google AI Studio + Android Studio）
- Gemini Enterprise Agent Platform

**成本叙事**：

![Cost saving](frames/frame_29.jpg)

> "If [top Cloud companies] shifted 80% of their workloads from other frontier models to 3.5 Flash, they would save over $1 billion annually."

Top Cloud 客户每天 ~1T tokens，混合用 Flash 替代 80% 前沿模型，**年省 $1B**。

### 3.2 Gemini 3.5 Pro

**下月（6 月）发布**。定位是"高精度、复杂任务"的通用主力——长链路推理、复杂代码重构、多文档研究。

### 3.3 内部 Token 用量是验证信号

![Daily Internal Tokens 增长曲线：3 月 1T → 5 月 2T，PPT 原版数据](frames/frame_23.jpg)

> "In March, we were processing half a trillion tokens a day internally for our developers [...] now, we are processing more than 3 trillion tokens a day."

**两个月内部 dev token 用量 6×**——这是 Antigravity + 3.5 Flash 形成的"内部先用、改进、再外发"反馈循环的直接证据。

---

## 四、世界模型：Gemini Omni / Omni Flash

**定位**：Demis 上场亲自发布。**from any input create anything**——从任意输入生成任意输出，从文本预测走向**对现实世界的模拟与生成**。这是迈向 AGI 的关键一步。

> "AGI is now on the horizon and it will be the most profound and impactful technology ever invented." —— Demis Hassabis

**首发模型：Gemini Omni Flash**（今日可用）。

**三大核心能力**：

- **对话式视频编辑**：每条指令基于上一条构建，角色保持一致，物理规律成立，场景记住之前发生的事
- **世界变换**：改变视频中的特定元素或整个环境（自拍变黑洞、夜晚散步加奇幻元素）
- **知识驱动生成**：基于 Gemini 的真实世界知识（不只是像素级模仿），如「make a claymation explainer of protein folding」

![Omni 「知识驱动生成」实例：演讲者输入 prompt「make a claymation explainer of protein folding」→ Omni 生成黏土风格氨基酸链科普视频帧（标题"AMINO ACIDS"，五彩黏土小球串联成肽链结构）](frames/frame_15.jpg)

**可用平台**：

| 平台 | 状态 |
|---|---|
| Gemini App（付费订阅） | 今日 |
| Google Flow | 今日 |
| YouTube Shorts | 今日 |
| 开发者 / 企业 API | 数周内 |
| 后续扩展 | 图像输出、音频输出 |

> 📎 **补充信源**：[Introducing Gemini Omni - Koray Kavukcuoglu](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni/)。Omni Pro 时间表官方未公布。

---

## 五、Search 重做：搜索框 25 年来最大升级

> **定位**：Search 是 Google 的"终极登月项目"。Liz Reid 这一节做了三件事：**搜索框重做 + AIO/AI Mode 合并 + Search Agent 化 + 把 Antigravity 嵌进搜索**。每件都不小。

### 5.1 全新智能搜索框

> "This is the biggest upgrade to our iconic Search box since its debut over 25 years ago."

新搜索框：

- 输入时**智能扩展**（不只是 autocomplete，会建议你没想到的限定条件）
- **跨模态**（文字 / 图片 / 文件 / 视频 同框）
- **今天起开始 rollout**

### 5.2 AIO + AI Mode 合并

![AIO + AI Mode merged](frames/frame_39.jpg)

> "I'm excited to share this new seamless AI Search experience is live today, across desktop and mobile worldwide."

之前 AI Overviews 和 AI Mode 是两个产品，现在融成同一条体验：从主结果页里的回答，平滑跟到 AI Mode 的深入对话，**上下文不丢**。AI Mode 升级到 Gemini 3.5。

![AI Mode queries 自上线每季度翻倍：Jul'25 → May'26 增长曲线（最右端 dotted line 标记 May 26 当下点位）](frames/frame_37.jpg)

| 指标 | 数字 |
|---|---|
| AI Mode MAU | **1B+**（一年内从零） |
| AI Mode queries 增长 | 自上线**每季度翻倍** |
| Search 总查询量 | 上季度创历史新高 |
| AI Overviews MAU | **2.5B** |

### 5.3 Generative UI in Search — 真正的杀手锏

![Generative UI](frames/frame_41.jpg)

> "Search invokes an agentic coding harness powered by Antigravity [...] This is the tech you saw Varun build a whole OS with, and we're bringing that power right into Search."

**搜索每次查询，背后都可能 spin up 一个临时 agent + 写代码 + 跑代码 + 输出 UI**。

现场 demo：搜「how do black holes affect space-time?」→ 结果页里**实时 build 一个交互可视化组件**（可拖参数、看引力波形）。再问「show me how two orbiting objects like binary black holes create gravitational waves」→ 再生成新组件。

![Black hole interactive](frames/frame_42.jpg)

**今夏对所有人免费**。

### 5.4 Mini-app — 状态化的搜索小工具

![Weekend planner](frames/frame_43.jpg)

![Ask YouTube 真实结果页：教 3 岁孩子从平衡车过渡到脚踏车](frames_official/sundar_keynote_Ask_YouTube_Results.webp)

> "Search has the ability to help you build entire custom stateful experiences: Tools, trackers, dashboards."

搜「周末和家人做什么」→ 搜索主动提议帮你 build 一个 **Weekend Planner**，连接 Gmail / Photos / Calendar / Maps，自动避开冲突时段、把家人日历都同步上、可分享给配偶继续编辑。一次搜索变成长期复用的微应用。

夏季对**订阅用户**开放（注：与 Generative UI 全民免费形成分层）。

---

## 六、Agent 电商基础设施：UCP / AP2 / Universal Cart

> **定位**：今年 I/O 的全新板块——**给 Agent 时代搭电商基础设施**。这是 Google 想做协议层（HTTP）而不是某个购物功能的明显信号。

### 6.1 Universal Commerce Protocol (UCP)

![UCP 24 家伙伴 logo 墙：Shopify / Etsy / Wayfair / Target / Walmart / Adyen / Amex / BestBuy / Carrefour / Chewy / Flipkart / GAP / Kroger / Lowe's / Macy's / Mastercard / PayPal / Sephora / Shopee / Stripe / Ulta / Visa / Worldpay / Zalando](frames_official/ucp_UCP_Partner_Log.webp)

**定位**：Agent 电商时代的 HTTP——给 Agent 购物用的通用协议（类似 MCP 之于工具调用）。**开源标准**。

**关键时间线**（联网补充）：

| 时间 | 事件 |
|---|---|
| **2026-01 NRF 零售展** | UCP 首发，签下 **Walmart、Etsy、Wayfair、Best Buy** 等零售商 |
| **2026-05 I/O** | 新增 **Amazon、Meta、Microsoft、Salesforce、Stripe** 加入标准制定 |
| 未来几个月 | 地域扩展到加拿大、澳大利亚、英国 |
| 未来几个月 | 垂直扩展到酒店预订、本地外卖 |
| 未来几个月 | 平台扩展到 YouTube |

> 📎 **补充信源**：[blog.google/.../agentic-commerce-ai-tools-protocol-retailers-platforms](https://blog.google/products/ads-commerce/agentic-commerce-ai-tools-protocol-retailers-platforms/)。

> "It may just be the first time we've all agreed on something!" —— Vidhya Srinivasan

把 Amazon / Meta / Microsoft / Google 凑在一张桌子上签同一个标准，这是少见的"竞争对手联盟"。

### 6.2 Agent Payments Protocol (AP2)

![AP2](frames/frame_46.jpg)

**定位**：解决「Agent 帮你买东西会不会乱花钱」的具体焦虑。

**三道护栏 + 三方可问责**：

| 维度 | 机制 |
|---|---|
| 边界 1：品牌 | 用户指定具体品牌 |
| 边界 2：商品 | 用户指定具体商品 |
| 边界 3：金额 | 设定支付上限（三个条件全满足才下单） |
| 隐私 | 隐私保护技术保障数据安全 |
| 可问责 | **Tamper-proof digital mandate**（防篡改数字授权书）—— 用户、商家、支付方看到同一份记录 |

**先在 Gemini Spark 落地**，后续扩展。

### 6.3 Universal Cart — 跨场景智能购物车

![Universal Cart](frames/frame_47.jpg)

**定位**：跨 Google 全产品的统一购物车——无论在 Search / Gemini / YouTube / Gmail 看到想买的，都能一键加入。

**智能能力**：

- 自动找折扣、查价格历史
- 跨支付卡权益对比（基于 Google Wallet）
- 缺货补货提醒
- **跨商品兼容性检查**（如：你买了主板 A 但已选 CPU B，主板 A 的 socket 不兼容 → 主动提示换主板）
- 多商家合并结算（UCP 标准 → Google 内 Google Pay 结账，或一键跳商家网站）

**今夏 US 上线**（Search + Gemini app 先行，YouTube / Gmail 跟进）。

---

## 七、Gemini App：Neural Expressive 重做

![Gemini App MAU 900M / 月（第七章开场关键数据）](frames/frame_48.jpg)

**定位**：完整的视觉 + 交互重做（而不是迭代）。**今天起全球 Android / iOS / Web 上线**。Sundar 开场公布 **Gemini App MAU 900M /月**——这是 Google 在消费者 AI 助手领域的核心信号。

**视觉革新**：

- 流体动画、鲜艳色彩、新字体排版、触觉反馈
- 蓝色渐变背景取代灰白界面
- 响应不再是「文字墙」——AI 实时设计定制化回复（图像、交互时间线、旁白视频、动态图形）

**交互革新**：

- Gemini Live 直接集成主界面——打字和语音无缝切换
- 重新设计的麦克风：点按即说，**按自己节奏表达不被打断**
- 即将推出区域方言（利物浦腔、印度哈里亚纳方言、巴西里约葡萄牙语等）

**新平台扩展**：

- **Gemini for Mac**：桌面应用上月发布，"100 天 100 功能"路线图
- **Gemini Omni 进 App**：订阅用户今日可用，Sashu 用 raw 视频做音乐预告 demo

![Gemini for Mac](frames/frame_51.jpg)

**Mac demo**：Finder 里多选文件 → 长按 Function 键口述邮件 → 多模态读完 PDF / 图片 → 生成带表格邮件 → 自动修正语音口误。

![Mac voice demo](frames/frame_52.jpg)

![Gemini Pro 在 Gemini App 内做罗马水利百科解读：原文段落 → 多模态翻译/释义 → 嵌入演示动图](frames/frame_49.jpg)

---

## 八、创意工具：Pics / Stitch / Flow

> **定位**：Suz Chambers 主讲的「Make」线。从 Nano Banana 时代的图像创作，全面扩展到图像编辑（Pics）、UI 设计（Stitch）、视频/音乐（Flow）。

### 8.1 Google Pics（Workspace 新品，今夏发布）

**定位**：Workspace 中的图像创作 / 编辑工具，基于 Nano Banana。

- **目标分割**：选中图中任何元素单独编辑
- **文字编辑**：图中文字直接修改、一键多语种翻译
- 所有输出自动加 SynthID 水印
- **今夏，US Ultra 订阅者**

### 8.2 Stitch（UI 设计，今日上线）

![Stitch](frames/frame_54.jpg)

- 过去一年全球用户生成 **1 亿张 UI 画面**（Sundar/Suz 提及，官方 100-things 未单列累计数）
- 新增：**实时语音协作**（说"把 header 字号变大"，UI 实时改）
- 一键导出代码 / 发布 Netlify / 与 Antigravity 打通

### 8.3 Google Flow（今日全部上线）

![Flow update](frames/frame_55.jpg)

5 项更新：

- **接入 Gemini Omni**：保留原始视频表演和动作，只改环境和特效
- **新 Agent**：一张图同时生成 16 段不同机位视频
- **大规模场景修改**：所有镜头从清晨变深夜，灯光 / 阴影 / 车灯自洽切换
- **Flow Tools**：在 Flow 中 vibe-code 自己的创意工具
- **Flow Music**：录一段钢琴 riff → 指定风格（如 R&B + 女声）→ 生成完整编曲

![Flow Music](frames/frame_56.jpg)

---

## 九、智能眼镜：从手机到眼镜的 Android XR

![Android XR：Compatible with Android + iOS（首次跨生态）](frames/frame_57.jpg)

> **定位**：Shahram Izadi 主讲。Android XR 上升为 **AI-powered operating system**。两条产品线：轻量化 AI 眼镜（今秋首发）+ 沉浸式 XR 眼镜（待定）。

### 9.1 Audio Glasses（今秋首发）

![Warby Parker × Google × Samsung 联合款 Audio Glasses 产品图](frames_official/audio_glasses_3_IO_Glasses_Product_WarbyParker.webp)

![Gentle Monster × Google × Samsung 联合款 Audio Glasses 产品图](frames_official/audio_glasses_1_IO_Glasses_Product_GentleMonste.webp)

**定位**：所有 Gemini 语音都**私密入耳**（不靠显示），Hands-free + Heads-up 全天助手。

**合作伙伴**：

| 角色 | 厂商 |
|---|---|
| 平台 + 工程 | **Samsung**（Android XR 平台 + Snapdragon 高通） |
| 时尚设计 | **Warby Parker**、**Gentle Monster** |
| 兼容设备 | **Android + iOS**（首次）|

> 📎 **补充信源**：[blog.google/.../android-xr-io-2026](https://blog.google/products-and-platforms/platforms/android/android-xr-io-2026/)。**价格未公布**（属"sneak peek"），秋季上市。

### 9.2 现场 Demo

Nishtha Bhatia 戴 Gentle Monster、Shahram 戴 Warby Parker：

- **Maps + Personal Intelligence**：「导我去上周和 Gianna 见面的地方」→ 调出 Maps 路线 + 提议中途取冷萃
- **多 app 后台执行**：「下我平时那杯」→ 自动调起 DoorDash app、走完所有选项、最终人工确认
- **跨 app 协作**：「我静音了消息，错过什么没」→ 总结家庭群聊后加日历，自动避开已有事件
- **Nano Banana on glasses**：「拍张观众照，转成卡通，加飞艇」→ 几秒后**手表上预览**

![Calendar demo](frames/frame_62.jpg)

![Audience selfie demo](frames/frame_63.jpg)

**设计意图**：眼镜（视觉 / 语音输入 + 耳机输出）+ 手表（glanceable 显示）+ 手机（计算与连接）= 三件设备的最小协作单元。

### 9.3 Display Glasses（更后）

带小型镜片显示的款式（Uber 接车信息、Live Translation），Trusted Tester Program **今年扩大**。具体上市时间表官方未明示。

---

## 十、健康生态重构：Fitbit → Google Health

> **定位**：本场配套发布会，本主题演讲未着重提及，但生态层面是大动作。Fitbit 品牌**整合进 Google Health 体系**——「硬件 + App + AI 教练」三位一体。

### 10.1 Google Health App（前 Fitbit App）

> 📎 **补充信源**：[blog.google/.../google-health-app](https://blog.google/products-and-platforms/products/google-health/google-health-app/)（5/7 公布）

- Fitbit App 正式更名为 **Google Health App**
- 4 个标签页：Today / Fitness / Sleep / Health
- 支持第三方 App（Peloton、MyFitnessPal）和医疗记录同步（美国）

### 10.2 Google Health Coach（5/19 退出 preview）

![Google Health Coach 三屏 App：Onboarding + 教练对话 + Premium 仪表盘](frames_official/health_coach_HealthApp-2-Onboarding.png)

> 📎 **补充信源**：[blog.google/.../google-health-coach](https://blog.google/products-and-platforms/products/google-health/google-health-coach/)

- 基于 Gemini 的 **24/7 AI 健康教练**，覆盖健身、睡眠、营养、心理健康

![Coach 消息细节](frames_official/health_coach_HealthApp-3-CoachMessages.webp)

- 支持语音、图片、文档多模态输入
- **价格：$9.99/月 或 $99/年**（Google Health Premium，前 Fitbit Premium）
- **Google AI Pro / Ultra 订阅用户免费包含**

![In-Workout 实时反馈](frames_official/health_coach_HealthApp-5-InWorkout.webp)

- **Stephen Curry 作为 Google Performance Advisor** 参与设计
- 上线：**5/19 退出 preview，5/26 推送 100%**

![食物 / 活动 Logging](frames_official/health_coach_HealthApp-6-Logging.webp)

### 10.3 Fitbit Air（最便宜的追踪器）

![Fitbit Air Hero：4 色腕带产品矩阵 + 户外瑜伽场景](frames_official/fitbit_air_fitbitair_hero.webp)

> 📎 **补充信源**：[blog.google/.../fitbit-air](https://blog.google/products-and-platforms/devices/fitbit/fitbit-air/)（5/7 已发）

- **$99.99 起**，无屏设计、一周续航、5 分钟快充一天
- 24/7 心率/血氧/HRV/房颤预警/睡眠分期
- **Stephen Curry 联名特别版 $129.99**
- 上市：**5/26**

![Stephen Curry × Fitbit Air 联名特别版](frames_official/fitbit_air_Fitbitair_SC_carousel1.webp)

---

## 十一、基建底座：第八代 TPU + Capex

### 11.1 TPU v8t / v8i —— 首次双芯片分工

![TPU 历代演进时间线：v4 / v5e / v5p / Trillium / Ironwood / 8 一字排开（2022→2026）](frames/frame_10.jpg)

![Two chips for the agentic era：TPU 8t / 8i 双芯片实物特写（铜色液冷管 + TPU 8i 芯片）](frames_official/tpu_two_chips_for_the_agentic_era_her.png)

![Ironwood vs TPU 8t 规格对比表：pod 9216→9600 / FP4 42.5→121 EFlops / scale-up 9.6→19.2 Tb/s](frames_official/tpu_TPU_8_Cloud_inline_1.webp)

> "For the first time, we have taken a dual-chip approach with specialized architectures for training and inference."

| 维度 | TPU 8t（训练） | TPU 8i（推理） |
|---|---|---|
| Superpod 规模 | **9,600 颗芯片** | — |
| HBM | **2 PB 共享** | **288 GB / 芯片** |
| 算力 | **121 ExaFlops / pod** | — |
| 片上 SRAM | — | **384 MB**（3× 上一代） |
| ICI 带宽 | 翻倍 | **19.2 Tb/s** |
| 网络拓扑 | **Virgo Network** | **Boardfly**（直径 -50%+） |
| 性能/价格 | — | **+80%** |
| 性能/瓦特 | **2× Ironwood** | **2× Ironwood** |
| 单 pod 算力 | **3× 上一代** | — |
| 关键加速器 | — | **Collectives Acceleration Engine（CAE）**（延迟 -5×） |

**共同特性**：

- 首次都用 Google 自研 **Axion ARM CPU** 作为 host（每服务器 host 数量翻倍，NUMA 架构）
- **第 4 代液冷**冷却分配单元（空气冷却已无法满足功率密度）
- 支持 **JAX、MaxText、PyTorch、SGLang、vLLM** 等主流框架
- 提供 **bare metal access**（无虚拟化开销）

> 📎 **补充信源**：[blog.google/.../eighth-generation-tpu-agentic-era](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/eighth-generation-tpu-agentic-era/)。

### 11.2 Jackson Pathways 训练基础设施

> "Our training is no longer constrained by the limits of a single massive data center."

- JAX + Pathways 让训练**突破单数据中心边界**
- **跨多站点分布式训练**，可扩到 **100 万+ TPU 单一逻辑集群**
- **Goodput > 97%**（业界领先）
- 数据中心单位电力算力是 5 年前的 **6 倍**

### 11.3 Capex

![Capex](frames/frame_09.jpg)

| 年份 | Capex |
|---|---|
| 2022 | **$31B** |
| 2026（预计）| **$180B - $190B**（约 **6×**） |

> 📎 **附属公告**：根据 [blog.google/.../blackstone-tpu-cloud](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/blackstone-tpu-cloud/)，Blackstone 与 Google 成立合资公司建 TPU 云。

### 11.4 现场速度演示

> "I'll create a Chrome Dino game [...] take a look at the tokens per second in the top right corner. The speed is pretty incredible, nearly 1,500 tokens per second."

**3.5 Flash on TPU 8i：~1500 tokens/sec**——几乎"写完 prompt 答案就出来了"。

---

## 十二、安全与科学

### 12.1 SynthID + Content Credentials

![SynthID](frames/frame_18.jpg)

| 数据 | 数字 |
|---|---|
| SynthID 累计水印 | **1000 亿** 张图/视频 + **6 万年** 音频 |
| SynthID Detector 在 Gemini app 使用次数 | **5000 万** |
| 新加入合作伙伴 | **OpenAI、Kakao、ElevenLabs**（Nvidia 去年加入） |

![Content Credentials](frames/frame_19.jpg)

> "You can simply circle to search or right-click in Chrome and ask 'was this generated with AI?'"

进入 **Search 和 Chrome**（数月内），可一键查内容来源（相机拍摄 / AI 生成 / Photos 编辑过）。

### 12.2 CodeMender — Code Security Agent

![CodeMender](frames/frame_64.jpg)

自动发现并修复软件漏洞的代码安全 agent。**今天邀请少数专家测试 CodeMender API**。

### 12.3 Gemini for Science

Demis 主讲的最后一节：

- **AlphaEarth Foundations**：地球数字孪生，用于森林砍伐 / 食物安全
- **WeatherNext**：AI 全球天气预报；Cat-5 飓风 Melissa **提前 3 天**预报，给牙买加争取疏散时间
- **AlphaFold / AlphaGenome**：已是数百万科学家日常工具
- **Isomorphic Labs**：分子建模做药物开发，**已进 pre-clinical 阶段**，方向包括免疫病和癌症

> "WeatherNext predicted a category 5 hurricane striking Jamaica three days early with greater accuracy than previous models."

> "Our mission is to reimagine the drug discovery process with the goal of one day solving all disease."

### 12.4 Build with Gemini XPRIZE

> 📎 **补充信源**：[geminixprize.com](https://www.geminixprize.com/)

- 奖池 **$2,000,000**（号称"史上最大黑客松奖池"）
- **9 月洛杉矶决赛**

---

## 十三、订阅价格体系：从「次数」到「算力」的根本性变化

> **定位**：本场最容易被科技媒体忽略但对所有 AI 公司都有指标意义的发布。**Gemini 网页版与 App 放弃了传统的"每日固定提问次数"，改为以 Compute-used（算力消耗）为核心的动态计费**。

### 13.1 用量模型革新

> 📎 **补充信源**：[blog.google/.../google-ai-subscriptions](https://blog.google/products-and-platforms/products/google-one/google-ai-subscriptions/)

| 维度 | 旧模型 | 新模型 |
|---|---|---|
| 计费单位 | 每日固定提问次数 | **Compute-used（算力消耗）** |
| 扣费依据 | 每条 prompt 一次 | **prompt 复杂度 + 功能类型 + 上下文深度** |
| 重置周期 | 每日 | **每 5 小时**，直到达到周上限 |
| 超额降级 | 拒绝服务 | **自动切换到中小模型**（Pro 用尽 → Flash） |
| 加油包 | 无 | AI Pro/Ultra 可购买 Antigravity / Flow pay-as-you-go 加油包 |

### 13.2 订阅层级

| 档位 | 价格 | 关键权益 |
|---|---|---|
| **AI Plus** | (官方未在 I/O 博客直写，按地区动态显示) | 入门 |
| **AI Pro** | (官方未在 I/O 博客直写) | + YouTube Premium Lite ($8.99/月价值，免广告 + 后台播放) + Health Premium + Home Premium |
| **AI Ultra $100/月**（新档） | **$100/月** | 5× Pro 用量 + 20TB 云存储 + Antigravity 优先 + YouTube Premium individual + Spark |
| **AI Ultra $200/月**（顶级，原 $250）| **$200/月** | 20× Pro 用量 + Spark + 全部 |

**限时优惠**：Ultra 订阅者获 **$100 Antigravity 额外额度**（5/25 截止）。

---

## 十四、一点观察（独立判断，非发布会原话）

### 1. 这是 Google 把 AI 从"功能"变成"基础设施"的转折点

发布会从头到尾都不是在讲单个模型有多强，而是在讲：**算力（TPU 双芯）、协议（UCP / AP2）、平台（Antigravity）、订阅（按算力计费）**——这四样东西全是基础设施级别的发布。Google 不想在"哪个模型最聪明"上跟 OpenAI / Anthropic 比，它想做"AI 时代的 AWS"。

### 2. Antigravity + Spark 是同一件事的两面

底层都是 subagents + hooks + async task management。开发者用 Antigravity，消费者用 Spark。**这种"统一 runtime + 双面市场"的架构，是 OpenAI 当下最缺的东西**——ChatGPT Agent 和 OpenAI API 之间还没有这种结构对称性。

### 3. Gemini 3.5 Flash 的定位是"agent 时代的默认 CPU"

它不是为了拿 benchmark 第一发布的，是为了**让 1T tokens/天的客户能算得过账**。Sundar 直接给出"年省 $1B"的口径，是说给 CFO 听的。这跟 Anthropic 把 Claude Opus 卖给"质量优先"客户的策略不同，**Google 在打吞吐量战争**。

### 4. UCP 是这次 I/O 最被低估的发布

把 Amazon / Meta / Microsoft / Salesforce / Stripe 凑到同一个开源标准上，这种事 Google 上一次做成是 25 年前的开放搜索。Vidhya 说 "first time we've all agreed on something" 不是夸张——Agent 电商的协议层一旦定型，谁定义协议谁就握住下一轮分发权。

### 5. Search 的 Generative UI 是 SEO 的下一次结构性冲击

把 Antigravity 嵌进搜索 + 免费对所有人 + 每次查询动态生成交互组件，意味着**用户可能再也不需要点出去**。"infinite range of human perspectives" 听起来美好，但实际是 Google 用 Gemini 把全网内容重新合成。**这次不是 AI Overviews 简单截胡，是把搜索结果页本身变成动态应用**。内容创作者要重新想分发逻辑。

### 6. 订阅价格是与 OpenAI 的正面对决

Ultra $250 → $200 不是降价，是**对标 ChatGPT Pro $200 的明确动作**——同价位但打包了 YouTube Premium + Workspace + Health + Spark。新增 $100 档承接中端流量。**计费从次数转算力，是一次对所有 AI 订阅产品的施压**——OpenAI 不跟，会显得粗放；跟，要重做计费系统。

### 7. 眼镜是一个谨慎的"软发布"

Audio Glasses 没说价格、没说销量目标、没说出货国家——这是 Google 在硬件上的**期望管理**。和 Samsung / Warby Parker / Gentle Monster 拼合作，意图是先用时尚品牌的设计感打住"科技产品丑"印象，再慢慢扩。**真正的 AR 时刻**至少还要一年（取决于 Display Glasses 量产时间表）。

### 8. AGI 已经从口号变成产品时间表

Demis 的 "AGI is now on the horizon"（"AGI is just a few years away"）+ Sundar 的 "we are firmly in our agentic Gemini era"——两个人措辞配合得很好。**当一家公司开始把 AGI 写进 keynote 副歌时，意味着他们认为下一轮叙事的主导权还在自己手里**。Demis 收尾的「foothills of the singularity」不是煽情，是对 OpenAI / Anthropic 的隔空喊话。

---

## 信源说明

**字幕原话**：所有引号内文本（包括 Sundar、Demis、Varun、Josh、Liz、Vidhya、Suz、Shahram 的直接引语），均为视频字幕逐字摘录。

**📎 补充信源**：以 `> 📎 **补充信源**` 标记的内容，来自字幕外的官方一手渠道交叉验证：

- [blog.google/.../sundar-pichai-io-2026](https://blog.google/innovation-and-ai/sundar-pichai-io-2026/) - Sundar Pichai 主旨博客
- [blog.google/.../google-io-2026-all-our-announcements](https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/) - I/O 2026 全部 100 项公告
- [blog.google/.../google-ai-subscriptions](https://blog.google/products-and-platforms/products/google-one/google-ai-subscriptions/) - 订阅价格体系
- [blog.google/.../eighth-generation-tpu-agentic-era](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/eighth-generation-tpu-agentic-era/) - 第八代 TPU 详细规格
- [blog.google/.../next-evolution-gemini-app](https://blog.google/innovation-and-ai/products/gemini-app/next-evolution-gemini-app/) - Gemini App 重做与 Spark
- [blog.google/.../agentic-commerce-ai-tools-protocol-retailers-platforms](https://blog.google/products/ads-commerce/agentic-commerce-ai-tools-protocol-retailers-platforms/) - UCP 与电商
- [blog.google/.../gemini-omni](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni/) - Gemini Omni 发布
- [blog.google/.../google-health-coach](https://blog.google/products-and-platforms/products/google-health/google-health-coach/) - Health Coach 价格细节
- [blog.google/.../fitbit-air](https://blog.google/products-and-platforms/devices/fitbit/fitbit-air/) - Fitbit Air
- [blog.google/.../android-xr-io-2026](https://blog.google/products-and-platforms/platforms/android/android-xr-io-2026/) - Android XR 与智能眼镜
- [geminixprize.com](https://www.geminixprize.com/) - Build with Gemini XPRIZE

**官方未公布 / 本次未查到**（透明声明）：

1. Google AI Plus / AI Pro 当前月费具体数字（按地区动态显示）
2. Audio Glasses 价格、Warby Parker / Gentle Monster 各自款式名
3. Display Glasses 上市时间表
4. NotebookLM 在 I/O 2026 的具体新功能列表
5. CodeMender API 是否当天对所有人开放
6. Stitch 累计 1 亿 UI 画面这一具体数字（仅口播提及，官方未单列）
7. Project Aura / XREAL 是否在 keynote 中点名

**我的判断**：整体概要中的「**核心判断**」分句、以及文末「十四、一点观察」整章，全部为本简报作者独立判断，不属于发布会原话。
