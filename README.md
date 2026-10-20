# Reflexus

本地研究桌面。平台负责启动子功能、导入材料、审阅和记下问题。搜索、转写、抓取由各自的项目完成。

## 启动

需要 Windows 和 Python 3.12。在仓库目录执行：

```powershell
pip install -r app/requirements.txt
python -m app
```

也可以双击桌面上的 Reflexus 快捷方式。它用 `pythonw` 打开窗口，工作目录是本仓库。

不打开窗口、只导入某个主题的收件箱：

```powershell
python -m app ingest 健身
```

## 窗口

左侧是主题列表。进入主题后，顶栏可以切换三页：

- 信息源：列出已接入的来源。点「B站」进入 B 站功能页，在那里写选片、开始转写、导入收件箱
- 审阅：换一条、采纳、丢弃、存疑、打开地址、就此提问
- 对话：问题会写入该主题的 `chat.md`。模型接口还没接上

## 本地笔记

每个主题在 `library/<主题>/`，这个目录不进入 Git。

| 文件 | 作用 |
| --- | --- |
| `topic.md` | 兴趣、关键词、未决问题，以及各子功能的选片 |
| `inbox/` | 子功能写入的 JSON |
| `items/` | 平台导入后的 Markdown |
| `memory.md` | 长期记忆，留给以后的对话 |
| `chat.md` | 已记下的问题 |
| `logs/` | 最近一次运行的输出 |

同一条材料用 `source` 加 `external_id` 识别。再次导入只更新原文，保留你的审阅状态和判断。

## 接入 B 站

清单在 `sources/bilibili.json`。平台执行其中的 `command`，工作目录是 `cwd`，并额外传入：

- `RESEARCH_TOPIC`
- `RESEARCH_TOPIC_DIR`
- `RESEARCH_INBOX`
- `RESEARCH_TOPIC_FILE`
- `PYTHONIOENCODING=utf-8`
- `PYTHONUNBUFFERED=1`

平台不在命令后面追加视频链接。选片写在 `topic.md` 的 `## bilibili` 一节，一行一个：

```text
https://www.bilibili.com/video/BVxxxx
```

或只使用下面两种中的一种，不要和链接混写：

```text
up https://space.bilibili.com/<mid> --since 2026-10-19 --until 2026-10-19
items D:\路径\清单.json --since 2026-10-19 --until 2026-10-19
```

转写程序结束后，平台导入 `inbox/*.json`。一份文件一条。字段见 `app/schema/item.example.json`：

- `source`：固定为 `bilibili`
- `external_id`：BV 号
- `title`、`url`
- `summary`：可空。空着就先不写摘要
- `body`：口播全文，不含标题行和时间戳
- `extra`：UP 主、分 P、时长等，平台原样保留

当前的 `D:\cursor\Reflexus\bilibili\convert.py` 还不会读这些环境变量，也不会把 JSON 写进收件箱。按钮已经会按上面的约定启动它。

## 目录

```text
app/            窗口、导入和启动
app/schema/     收件箱字段样例
sources/        子功能清单
library/        本地主题笔记，不提交
```
