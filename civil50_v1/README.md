# Civil50 中国大陆民事咨询评测库

本地研究版 v1，2026-11-22。含 50 个来源不同的案件家族。制作及来源核对由 Codex 完成。10 案用于开发，40 案已单独存放，等待独立评审。可用作开发测试和案例复盘；正式评测尚未冻结。

[逐案阅读目录](private/目录.md) · [SQLite 数据库](private/civil50.sqlite3) · [来源台账](private/sources.csv) · [覆盖表](private/coverage.csv) · [校验结果](results/verification.json)

## 从哪里开始

- 阅读个案请打开逐案目录。每页列有开场、按条件披露的两条答复、可上传摘记、原始记录中的字符位置、参考结论、评分项及接口回放。
- 开发模型只接收 [开发题](development/tasks.jsonl) 经 CivRA `PublicTask.to_model_input()` 过滤后的内容，以及当前轮已获准披露的答复和附件。原始题行包含来源链接，也属于控制器输入。
- SQLite 供评审和离线分析使用。它收录全部 50 案的任务、来源全文记录、100 份附件正文、隐藏事实、流程、争点、评分、检索判断及本地条文。附件回执和逐步 API 日志在文件目录中。数据库、`private/` 和 `results/` 都含受控材料。
- [交通开发样本](private/cases/civil50-002/README.md)、[借贷开发样本](private/cases/civil50-015/README.md)、[买卖开发样本](private/cases/civil50-029/README.md)、[租赁开发样本](private/cases/civil50-041/README.md) 分别演示协商、调解、诉讼准备和咨询。

## 案件构成

| 生活场景 | 开发 | 封存候选 | 合计 |
|---|---:|---:|---:|
| 机动车交通事故 | 3 | 11 | 14 |
| 民间借贷 | 3 | 10 | 13 |
| 买卖合同 | 2 | 11 | 13 |
| 租赁 | 2 | 8 | 10 |
| 合计 | 10 | 40 | 50 |

终点按咨询 20、协商 10、调解 10、诉讼准备 10 分配。交通场景中 4 案的原案由为事故后的保险纠纷或财产保险合同纠纷。买卖场景中 1 案涉及网络购物与平台角色。台账保留上游案由。DLawBench 的三个场景在 CivRA 既有试点中已经出现，全部放入开发集。

40 个封存候选的首要难点分为部分法律覆盖 19、记录或金额冲突 7、关键事实待补 6、指定核账问题材料充分 4、专项保险法依据库外 4。这些标签限定于逐案评测问题。上游实际材料对短交数量、地方年度赔偿标准、事故日期冲突等细分情形的覆盖仍有缺口，本版没有通过改动原案补齐这些情形。

## 来源及真实程度

| 发布者 | 采用范围 | 已核对的内容 |
|---|---|---|
| YeFD / MileCut | 47 案取自仓库自带的 C3RD_mini，另选 7 条离线类案候选 | 已从固定提交按 JSON 指针重取记录并比较完整对象。保留 CaseId、案由、诉辩与查明材料、法院说理、裁判结果、上游法条字段。 |
| SKYLENAGE-AI / DLawBench | 从公开中文 JSONL 读取 30 行，选用 0006、0007、0020 三案 | 核对固定文件、行号、原始 ID 及作者的逐案 SHA-256。上游已将公开裁判改写、匿名化，区分当事人理解和裁判侧记录。本地任务各取其中两个争点，保留完整上游记录供复核。 |

每案在来源台账中登记发布者、固定提交、原文件哈希、JSON 指针或行号、提取文件哈希、检索日期及上游文本中出现的完整日期和语境。各案事件可能跨多个日期；未从金额或案号倒推时间。上游没有独立的裁判日期字段时留有说明。C3RD 的 CaseId 是数据标识。本版核实到发布者记录，尚未取得全部法院原文、原始借据、发票、病历或银行流水逐一独立核验。

50 案均有上游来源，独立合成案为 0。口语开场、咨询目标、路线偏好、问答脚本和评分标准属于评测设计。100 份 UTF-8 文本附件均在第一行标有“评测改编”，第二行区分案卷摘记与当事人自述，第三行给出供核对的内容。两份摘记可以检验不同问题，均源自同案记录，不能作为两份独立原始凭证计算证据强度。源文本中的请求、认定和执行结果需分别辨认，裁判给付金额本身无法证明钱已支付。

DLawBench 数据采用 CC BY 4.0。MileCut 仓库提供 MIT 声明，未见针对所收第三方裁判文本的单独再分发许可。本库按本地研究使用保留复核材料。原始上游副本仅在评审侧，可能保留原发布记录中的姓名。署名与使用条款见 [DLawBench 数据许可](licenses/DLawBench-data.txt) 和 [MileCut 许可](licenses/MileCut.txt)。上游项目见 [MileCut / C3RD](https://github.com/YeFD/MileCut#c3rd) 和 [DLawBench](https://github.com/SKYLENAGE-AI/DLawBench)。

## 评审与实测

- [争点表](private/issues.jsonl) 将任务、事实、材料版本、第三行、源字段、字符位置与评分项连接。源位置为 JSON 解码后的 Unicode 字符，起点计入、终点不计入。按明确追问披露相应内容；泛问只给预设的有限回答。
- [金标准草稿](private/gold.jsonl) 与 [评分权重](private/weights.json) 供评审使用。五维度权重依次为 20/15/20/20/25。每项 2 分为充分、1 分为部分，错误或漏答得 0 分并分别登记。维度内先按适用项满分归一，再按适用维度权重求加权平均。无法观察时记录 unobservable 并报告可观测率，完整总分待补证。伪造依据、付款、立案或查验原件属于严重错误。
- [本地法条快照](private/index_snapshot.json) 记录来源提交及向量索引文件哈希，从索引中直接提取 1,690 条原文与稳定 ID。上游裁判援引的历史法律保留在原记录中，库内法条作为有版本的对照。历史法律事实须结合当时法和时间效力规定逐案判断。[最高人民法院关于民法典时间效力的规定](https://www.court.gov.cn/zixun/xiangqing/282051.html)
- [检索标注](private/qrels.jsonl) 和 [离线类案池](private/case_candidates.jsonl) 仅供评审；候选不含 50 道题的原记录。标注非穷尽，未经判断的候选留待复核。三个案另有 [成对探针](private/paired_probes.json)，分别保留及移除指定法条，并对两种隔离视图做精确定位验证。运行没有修改 CivRA 工作索引。
- 独立上传检查创建了 50 个本地测试会话，保存并回读 100 个文件，逐一核对 SHA-256。[上传回执](results/upload-smoke.jsonl)
- 另建的 50 个会话使用 CivRA 真实 API 路由、案件存储、等待 ID 和文件 ID，由 ScriptedLLM 提供预定助手动作。50 案均完成接口流程，经历 100 次材料等待、100 次路线步骤完成确认、16 次修改后重新确认。留有逐案双方原话、请求与回执及运行时 trace。该批未生成真实法律答复或可验收的诉状，也未观察在线检索表现。[脚本回放汇总](results/protocol/summary.jsonl)
- 真实推理模型运行数为 0。此次委托交付本地数据，没有将案件提交给外部模型服务。真实模型调用、Token、回答得分和过程/终稿图均待实际评测。独立评审人尚未签署，40 道候选题都在受控草稿目录；单条 schema 的 final_test 值表示计划用途，正式 bundle 的 reviewed 发布门槛仍生效。
- 四项故障注入覆盖附件内容变更、附件缺失、法条 ID 与原文不匹配、只有正文追问而无真实等待。逐案素材及法条定位、配额、ID、分层、回执及脚本状态均经校验。[机器校验报告](results/verification.json)

## 本地使用

在本目录运行。SQLite 可用通用 SQLite 客户端直接打开。

```sh
sqlite3 -readonly private/civil50.sqlite3 'SELECT scenario, allocation, count(*) FROM cases GROUP BY scenario, allocation;'
../CivRA/.venv-evaluation/bin/python -B tools/verify.py
```

按离线素材重建结构化表与数据库的顺序为 `python3 tools/build.py`、`python3 tools/package_db.py`。如需重新对照发布文件，给校验器传入 `--milecut /path/to/MileCut --dlawbench /path/to/DLawBench`，检出来源台账所列提交。单独保存新回放批次，输出目录必须尚未存在。

```sh
../CivRA/.venv-evaluation/bin/python -B tools/replay.py --case civil50-002 --out results/new-protocol
```

真实模型运行器支持已配置的本地 CivRA 服务。服务端决定推理及 embedding 的外部提供方和费用，访问令牌从当前进程的 CIVRA_API_TOKEN 读取。运行器按服务返回的 wait 和 question ID 恢复，匹配不到的意图及实际步骤交付物由操作员核对；指定 `--api` 才走此分支。省略 `--case` 会对全部案件创建新会话。模型回答质量、工具可观测性与实际文书内容另行评分。

```sh
../CivRA/.venv-evaluation/bin/python -B tools/replay.py --api http://127.0.0.1:8000 --case civil50-002 --out results/new-model-run
```

后续正式验收还需要成员二复核法源版本和类案标注，成员三复核事实、金额和产物，成员四核对真实模型上下文与轨迹可观测性。已附原始结果 CSV 表头以供实跑填写。

**English handoff.** Fifty mainland Chinese civil case families from pinned public dataset releases, with 10 development cases and 40 held-out drafts. The reviewer database contains the upstream records, localized consultation materials, gated facts and scoring items. Provenance was checked against the publishers’ files. Court originals and authentic private exhibits have not been independently authenticated. Scripted API replays verify protocol behavior. Live model performance and independent gold review remain pending.
