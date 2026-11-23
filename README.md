# Civil50 中国大陆民事咨询评测库

Civil50 v1 用于测试 CivRA 在中国大陆民事纠纷中的咨询、证据核对、法条检索和路线交付能力。每案保存口语开场、按条件披露的事实、可上传材料、来源定位、争点评分及接口回放。数据版本为 2026 年 11 月 22 日的本地研究版。

[逐案目录](civil50_v1/private/目录.md) · [完整数据说明](civil50_v1/README.md) · [来源台账](civil50_v1/private/sources.csv) · [SQLite 数据库](civil50_v1/private/civil50.sqlite3)

## 案件构成

| 场景 | 开发 | 待独立评审 | 合计 |
| --- | ---: | ---: | ---: |
| 机动车交通事故 | 3 | 11 | 14 |
| 民间借贷 | 3 | 10 | 13 |
| 买卖合同 | 2 | 11 | 13 |
| 租赁 | 2 | 8 | 10 |
| **合计** | **10** | **40** | **50** |

评测终点分为咨询 20 案、协商 10 案、调解 10 案、诉讼准备 10 案。当前已有 100 份评测附件的上传校验和 50 案脚本模型接口回放。真实模型效果与正式测试集评分待评测。详见[机器校验结果](civil50_v1/results/verification.json)。

## 浏览与下载

| 目录 | 内容 |
| --- | --- |
| [开发题](civil50_v1/development/tasks.jsonl) | 10 道开发题的控制器输入 |
| [逐案评审](civil50_v1/private/目录.md) | 50 案的开场、追问披露、附件、参考结论和原始依据 |
| [待评审测试题](civil50_v1/private/heldout-draft) | 40 道按案件家族隔离的正式测试候选 |
| [评审数据](civil50_v1/private) | 原始上游记录、隐藏事实、评分草稿、检索标注和 1,690 条法条快照 |
| [回放与验收](civil50_v1/results) | 上传回执、逐案对话、API 轨迹和评分表 |
| [复现脚本](civil50_v1/tools) | 数据构建、SQLite 打包、验证、上传检查和回放 |
| [交通事故 PDF 示例](examples/traffic-accident/交通事故案_宋兴福诉单晓龙/阅读说明.md) | 逐件材料、询问手册、判决记录排印及文书草稿。[完整 ZIP](examples/traffic-accident/交通事故案_宋兴福诉单晓龙.zip) |

## 复现

克隆仓库后，在仓库根目录运行以下命令核验原始文件，并查看 SQLite 中的案件数量。

~~~sh
(cd civil50_v1 && shasum -a 256 -c SHA256SUMS)
sqlite3 -readonly civil50_v1/private/civil50.sqlite3 \
  'SELECT scenario, allocation, count(*) FROM cases GROUP BY scenario, allocation;'
~~~

本版记录的 CivRA 提交为 [2058d23](https://github.com/MillerSWJTU/CivRA/tree/2058d23791ffd1299d441758f41a1635edbc4bb2)。使用已安装 CivRA 开发依赖的 Python，向脚本传入 CivRA 本地路径。以下回放默认使用脚本模型，输出写入临时目录。

~~~sh
/path/to/CivRA/.venv-evaluation/bin/python -B civil50_v1/tools/verify.py \
  --civra /path/to/CivRA
/path/to/CivRA/.venv-evaluation/bin/python -B civil50_v1/tools/replay.py \
  --civra /path/to/CivRA --case civil50-002 --out /tmp/civil50-002-replay
~~~

模型输入由 CivRA 的 `PublicTask.to_model_input()` 生成，并在相应轮次追加允许披露的答复与附件。上游原文、隐藏事实及评分草稿供评审使用。

## 来源、贡献与使用范围

- **YeFD / MileCut 的 C3RD_mini** 提供 47 案及 7 条离线类案候选。[上游仓库](https://github.com/YeFD/MileCut#c3rd) · [仓库 MIT 声明](civil50_v1/licenses/MileCut.txt)
- **SKYLENAGE-AI / DLawBench** 提供 3 案，数据许可为 CC BY 4.0。[上游仓库](https://github.com/SKYLENAGE-AI/DLawBench) · [数据许可](civil50_v1/licenses/DLawBench-data.txt)
- **Civil50 整理工作**由 CivRA 评测任务发起，Codex 协助选案、核对上游来源、编制评测附件和追问脚本、建立评分与检索标注，并完成离线验证。来源台账保存固定提交、记录位置和校验和。[来源台账](civil50_v1/private/sources.csv)

原始记录核对到了上游发布版本。评测附件、模拟问答和 PDF 文书包含按记录改编的内容，法院签章原件和当事人原始凭证尚未逐案独立核验。完整仓库用于私有研究备份，原始记录可能保留姓名，MileCut 收录的第三方裁判文本再分发授权未单列。
