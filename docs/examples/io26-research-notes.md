# Google I/O 2026 Keynote 复盘 — 字幕外细节查证报告

> 视频：https://www.youtube.com/watch?v=wYSncx9zLIU
> 主 keynote 日期：2026-05-19；本报告基于官方 blog.google 一手信源，非字幕已含内容。
> 信源优先级：blog.google / antigravity.google / one.google.com 等官方渠道。

---

## 一、Gemini 3.5 Flash & Antigravity 2.0 的关键数据

- **Gemini 3.5 Flash 基准成绩**：Terminal-Bench 2.1 76.2%，GDPval-AA 1656 Elo，MCP Atlas 83.6%；在 Artificial Analysis 智能 vs 输出速度图上位居右上象限，输出速度比其它前沿模型快 4 倍。  
  来源：https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/
- **Gemini 3.5 Pro**：Sundar 在博客上明确说"will be coming next month"（即 2026 年 6 月）。  
  来源：https://blog.google/innovation-and-ai/sundar-pichai-io-2026/
- **Antigravity 2.0 中 Flash 提速**："not just 4x but 12x faster than other frontier models"（Antigravity 内 Flash 比其它前沿模型快 12 倍）。  
  来源：https://blog.google/innovation-and-ai/sundar-pichai-io-2026/
- **Antigravity 配套发布**：Antigravity CLI（替代 Gemini CLI，已发布迁移指南）+ Antigravity SDK + 原生语音 + Android/Firebase/AI Studio 整合 + 子代理（subagents）/hooks/异步任务 等新原语。  
  来源：https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/ 第 47–55 条
- **Managed Agents（Gemini API）**：通过 Interactions API 单次 API 调用即可在 Linux 沙箱里跑 Antigravity agent；可通过 AGENTS.md / SKILL.md 注册自定义 agent。  
  来源：https://blog.google/innovation-and-ai/technology/developers-tools/managed-agents-gemini-api/

## 二、Google AI 订阅价格 / Plus / Pro / Ultra 详细变化

- **Ultra 顶级档降价**：从 $250/月 → $200/月，能力不变（20× Pro 用量）。  
- **新增 $100/月 Ultra 档**：5× Pro 用量 + 20TB 云存储 + Antigravity 优先访问 + Gemini 3.5 Flash + YouTube Premium individual。  
- **AI Pro 加送 YouTube Premium Lite 个人版**：价值 $8.99/月，部分国家在未来几天内推送。  
- **AI Pro / Ultra 现包含 Google Health Premium 和 Google Home Premium**，无额外费用。  
- **用量计费方式重大变化**：从"每日 prompt 上限"改为"compute-used"（按算力消耗计），每 5 小时刷新一次直至周上限；超出后自动降级到小模型，AI Pro/Ultra 用户可购买 Antigravity / Flow 的 pay-as-you-go 加油包，Gemini app 加油包即将推出。  
- **Plus / Pro 月费具体数字**：官方在 I/O 2026 博客中**未公开列出**（页面用 `<g1-localized-price>` 动态组件按地区渲染），需在 https://one.google.com/about/google-ai-plans/ 由用户所在地查看。  
  来源：https://blog.google/products-and-platforms/products/google-one/google-ai-subscriptions/

## 三、Gemini Spark 上线时间表与限制

- 本周（5 月 19 日当周）面向 trusted testers 推送。
- **下周开放 Beta**，**仅限美国 Google AI Ultra 订阅用户**（$100 和 $200 档均可）。
- 跑在 Google Cloud 专属虚拟机上，24/7 后台运行，使用 Gemini 3.5 + Antigravity harness。
- 集成路线：先与 Google 自家工具，**未来几周通过 MCP 接入第三方工具**。
- 后续路线图：可通过邮件/IM 直接驱动 Spark、自定义子代理、授权支付（可指定预算和商家）；夏天晚些时候在 Chrome 内运行（agentic browser）。
- Android 端通过新的 **Android Halo** UI 空间实时查看 Spark 任务进度（今年晚些时候上线）。
  来源：https://blog.google/innovation-and-ai/sundar-pichai-io-2026/ ；https://blog.google/innovation-and-ai/products/gemini-app/next-evolution-gemini-app/ ；https://blog.google/products-and-platforms/platforms/android/android-halo

## 四、Universal Cart / UCP 商务侧

- **UCP（Universal Commerce Protocol）首发时间**：2026-01-11 NRF 2026 零售展，I/O 上扩展。
- **UCP 创始合作**：在 NRF 已签下沃尔玛、Etsy、Wayfair、Best Buy 等零售商，I/O 上扩展加入 Amazon / Meta / Microsoft / Salesforce / Stripe（详见 ads-commerce 博客）。
- **Universal Cart 全平台覆盖时间表**：今夏先上 Search 和 Gemini app，YouTube 与 Gmail 随后。
- 内置 Google Wallet，能识别支付方式权益、忠诚度信息和商家优惠，自动建议最优支付方式；提示商品兼容性问题并推荐替代品。
  来源：https://blog.google/products/ads-commerce/agentic-commerce-ai-tools-protocol-retailers-platforms/ ；https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/ 第 30-34 条

## 五、TPU v8t / v8i 基础设施细节

- **TPU 8t（训练）**：单 superpod 9,600 颗芯片、2 PB 共享 HBM、121 ExaFlops；ICI 带宽较上一代翻倍；3× 上一代单 pod 算力。
- **TPU 8t 网络**：搭配 **Virgo Network**（兆级数据中心 fabric） + JAX + Pathways，可在百万颗 TPU 单一逻辑集群上接近线性扩展；目标 goodput >97%。
- **TPU 8i（推理）**：288 GB HBM + 384 MB 片上 SRAM（3× 上一代）；ICI 带宽 19.2 Tb/s；新 **Boardfly 拓扑**将网络直径压缩 50%+；新增 Collectives Acceleration Engine（CAE）将片上延迟降低 5×。
- **Axion ARM CPU**：TPU 8t/8i 首次都用 Google 自研 Axion ARM-based CPU 作为 host，每服务器 host 数量翻倍，NUMA 架构。
- **能效**：相比上一代 Ironwood，性能/瓦特提升 2×；80% 性能/价格提升（8i）；配套**第 4 代液冷**冷却分配单元。
- **Capex**：2022 年 $31B → 2026 年 $180B–$190B（约 6 倍）。
- **多数据中心训练**：JAX + Pathways 让训练突破单数据中心边界，可跨多站点分布式训练，跨 100 万颗以上 TPU。
- **Sundar 透露内部 token 增长**：3 月内部 AI 开发工具每日 0.5 万亿 token，I/O 时已超 3 万亿 token/天。
  来源：https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/eighth-generation-tpu-agentic-era/ ；https://blog.google/innovation-and-ai/sundar-pichai-io-2026/
- **附属公告**：Blackstone 与 Google 成立合资公司建 TPU 云。  
  来源：https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/blackstone-tpu-cloud/

## 六、硬件 / 设备公告

### Fitbit Air（5/7 已发，I/O 周补充信息）
- 价格 **$99.99 起**，**5/19 起开始预订**，**5/26 全美正式上架**。
- 含 3 个月 Google Health Premium 试用；屏幕全无设计；电池续航最长一周；快充 5 分钟可用一天。
- 7×24 心率、心律 + Afib 警报、SpO2、睡眠分期等。
- **Stephen Curry 联名特别版**（Performance Loop 表带，rye brown / 橙色）**$129.99**，5/26 美国上架。
- 表带：Performance Loop（标配）/ Active / Elevated Modern，配件起价 $34.99。
  来源：https://blog.google/products-and-platforms/devices/fitbit/fitbit-air/

### Google Health App（前 Fitbit App 改名）
- 5/7 公布；I/O 周配合 Health Coach 全面推送。
  来源：https://blog.google/products-and-platforms/products/google-health/google-health-app/

### Google Health Coach（全球）
- **5/19 退出 preview**，**5/26 推送 100%**。
- **价格 $9.99/月 或 $99/年**（Google Health Premium，前称 Fitbit Premium）。
- **Google AI Pro / Ultra 订阅用户免费包含**。
- 首发支持 Fitbit + Pixel Watch，其它设备稍后；可同步医疗记录（美国）。
- 与 **Stephen Curry**（Google Performance Advisor）及 Google Consumer Health Advisory Panel 联合开发；基于 SHARP 评估框架。
  来源：https://blog.google/products-and-platforms/products/google-health/google-health-coach/

### Android XR — Audio Glasses
- **首批音频眼镜合作**：Gentle Monster、Warby Parker（外观款式）+ Samsung（与高通联合 Android XR 平台）。
- **上市时间**："later this fall"（2026 秋季）；同时支持 Android 与 iOS。
- 功能：Hey Google 唤醒、视野识物、Maps 转弯导航、电话/短信、Nano Banana 图像编辑（"给所有人加滑稽帽子"）、实时双向翻译、DoorDash 等多步任务后台执行、Uber / Mondly 等 app 语音操作。
- **价格**：官方**未公布**（属"sneak peek"）。
- Display Glasses（含视觉显示款）排在 Audio Glasses 之后，时间表官方**未明示**。
  来源：https://blog.google/products-and-platforms/platforms/android/android-xr-io-2026/
- **未在 100-things 单独列出/未查到的项目**：Project Aura、XREAL 是否在本次 keynote 提及。

### Android Halo（Android 上的 Spark 进度 UI）
- 5/19 同日博客；今年晚些时候上线。  
  来源：https://blog.google/products-and-platforms/platforms/android/android-halo

### Googlebook（Gemini Intelligence 笔记本）
- 5/12 单独发布。  
  来源：https://blog.google/products-and-platforms/platforms/android/meet-googlebook/

### Android Auto / Gemini in the car
- 5/12 已先行发布；I/O 周作为关联公告，详情：与车厂集成 Gemini，新一代 Android Auto。  
  来源：https://blog.google/products-and-platforms/platforms/android/android-in-cars-updates/

## 七、其它补查项目

### NotebookLM
- **Literature Insights**：在 Gemini for Science 框架下用 NotebookLM 构建，可结构化检索文献、生成报告/幻灯片/信息图/音视频概览。  
  来源：https://blog.google/innovation-and-ai/technology/research/gemini-for-science-io-2026/
- **电影级视频概览/10 信息图风格/EPUB/Classroom**：keynote 主博客和 100-things 清单**未单独罗列**，可能在 NotebookLM 专属博客（如有）单独发布；本次查证**未找到对应官方博客 URL**。

### CodeMender
- **未在 100-things 清单或 Pichai 博客中直接出现**；可能未在主 keynote 提及，或属于 deepmind.google 单独博客。**未查到官方 I/O 2026 关联页面**。

### Stitch（设计工具）
- 5/19 更新：实时设计与导引、文本/语音输入、可导入既有代码库与设计文件保证品牌一致。
- "已生成 1 亿 UI 画面"等累计统计**官方在 100-things 第 85 条未列出**，仅提到能力升级。  
  来源：https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-updates/ ；https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/ 第 85 条

### XPRIZE
- **Build with Gemini XPRIZE Hackathon**：奖池 **$2,000,000**，号称"史上最大黑客松奖池"。  
  来源：https://www.geminixprize.com/ ；https://blog.google/innovation-and-ai/technology/ai/google-io-2026-all-our-announcements/ 第 65 条

### SynthID 数据
- **累计水印量**：100B+ 张图像/视频 + 60,000 年音频（Pichai 原话）。
- **SynthID Detector 在 Gemini app 已被使用 5000 万次**；扩展到 Search（今天）和 Chrome（未来几周）。
- **新加入 SynthID 的合作伙伴**：OpenAI、Kakao、ElevenLabs（Nvidia 去年加入）。
- **Content Credentials（C2PA）验证**：今天起上线 Gemini app，未来数月扩展到 Search 与 Chrome。
  来源：https://blog.google/innovation-and-ai/sundar-pichai-io-2026/ ；https://blog.google/innovation-and-ai/products/identifying-ai-generated-media-online/

### Project Genie
- 扩展给所有 18+ 的 **Ultra $200 全球订阅者**；新增 Street View 驱动的世界生成。  
  来源：https://blog.google/innovation-and-ai/models-and-research/google-deepmind/project-genie-expands/

## 八、Sundar Pichai 开场金句与背景数据

- **开场原话**（已与字幕一致）："We're now in the part of the AI cycle where people want to see the value in the products they use every day."  
  来源：https://blog.google/innovation-and-ai/sundar-pichai-io-2026/
- **关键增长数据**：
  - 月 token 处理量：2024.5 / 9.7T → 2025.5 / ~480T → **2026.5 / 3.2Q+**（同比 7 倍）。
  - 13 款产品 MAU 超 10 亿，5 款超 30 亿。
  - **AI Mode MAU 已破 10 亿**（Search 中），**AI Overviews MAU 25 亿**。
  - **Gemini app MAU**：去年 4 亿 → 今天 **9 亿+**（翻倍以上），日均请求量 **同比 7 倍+**。
  - 每月 850 万开发者基于 Google 模型构建；模型 API 每分钟约 190 亿 token。
  - 过去 12 个月，**375+ 个 Google Cloud 客户每个处理超 1 万亿 token**。
  - **Nano Banana 累计生成 500 亿+ 图像**。
  - 1 万亿 token/天的客户若把 80% 工作负载从其它前沿模型迁移到 3.5 Flash，每年可省 **>$10 亿**。
- **Sundar 头衔**：CEO of Google and Alphabet（同时为 Alphabet 董事会成员）。
- **Pichai 博客标题**：I/O 2026: Welcome to the agentic Gemini era。  
  来源：https://blog.google/innovation-and-ai/sundar-pichai-io-2026/

---

## 未查到 / 官方未公布 项目（透明声明）

为遵守"查不到不编造"原则，以下项目本次复查没有在官方一手页面找到对应数据：

1. **Google AI Plus / AI Pro 当前月费具体数字** — 官方页面用动态组件按地区渲染，未在 I/O 博客直写。
2. **Audio Glasses 的具体售价、Gentle Monster / Warby Parker 款式名称** — 官方仅给出"sneak peek"，"later this fall" 上市，价格未公布。
3. **Display Glasses 的发布时间表** — 官方仅说"both types"且 Audio 先行，Display 时间表未明示。
4. **NotebookLM 的具体新功能（电影级视频概览、10 种信息图风格、EPUB、Classroom 集成）** — 100-things 清单与 Pichai 博客中未单独罗列，可能在 NotebookLM 专属博客（本次未抓到对应 I/O 2026 URL）。
5. **CodeMender 是否在 keynote 出现 / API 是否当天开放** — 100-things 清单与 Pichai 博客均未提及，本次未找到 I/O 2026 关联官方页面。
6. **Stitch 累计 UI 生成量（1 亿张等数字）** — 100-things 第 85 条仅描述功能升级，未给累计数据。
7. **Gemini Omni 是否有专属发布博客的"标题"** — 已找到 deepmind.google 与 blog.google 两处入口，但 Gemini Omni Flash 单独博客的标题为"Introducing Gemini Omni"（作者 Koray Kavukcuoglu）。  
   来源：https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni/
8. **Project Aura / XREAL 是否在 Sundar keynote 提及** — Pichai 博客的"intelligent eyewear"段落未点名 Aura 或 XREAL，仅提到 Gentle Monster、Warby Parker、Samsung。
