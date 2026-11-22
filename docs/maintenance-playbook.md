# JabJam · 小奶茶维护操作手册

目标：把维护动作限定在少数文件内，让能力较弱的模型只需阅读相关模块，也能通过自动化验证来交付安全的小步 PR。

## 开工协议

1. 从 `main` 派生**新的独立分支**，不要在主分支试验。先写清楚「输入—预期输出—修改范围—不改的东西」。
2. 阅读 `AGENTS.md` 和本页当前任务的表格；不要未经要求顺手重构相邻模块。
3. 记录修改前的快速验收结果；修改后运行同样的测试，加一个覆盖新行为的回归用例。
4. PR 描述必须包含：需求、变更文件、测试命令与结果、风险和回退方式。失败应原样报告，不得凭空宣称验证通过。
5. 新功能通过 PR 合入公开引擎后，私有渲染仓库另开 PR 更新固定的引擎 SHA，先跑真实歌曲烟雾测试；不要同步复制整个引擎。

出片时先选难度、歌词效果和连击预设。命令行、Actions 与课程字段见[视频导出指南](video-export.md#歌词与连击预设)。歌词编舞和歌词显示可以独立使用。若显示行数为零，先核对同名 LRC 是否有实际正文。

## 按任务最小修改

| 任务 | 优先编辑 | 必须检查 | 特别禁止 |
| --- | --- | --- | --- |
| 新增场景 | `assets/arenas/*`, `video/course.py`, `video/arena.py`, `.github/workflows/render-video.yml` | `tests/test_arena_scenes.py`, 一段示例 MP4 | 运行中途自动随机切背景；丢失兼容场景 ID |
| 更改场景背景图 | `assets/arenas/<scene>.jpg` | 抽帧对比轨道与 HUD，测试固定场景 | 改动拳法、节拍与教练 |
| 增加经典拳组 | `video/choreography.py` 的 `PADWORK_COMBOS` | `tests/test_video_pacing.py` + `--write-course` | 随机拆散组合或突破恢复间隔 |
| 给一首歌标副歌招牌组合 | 在课程 `course.chorus_starts` 填同一句副歌的各个起唱秒数，可选 `chorus_combo`；[示范与拳序](video-export.md#副歌招牌组合) | `--check` 核对标记数，再在导出的谱里检查每次的 `chorus_cue`、起手与拳数 | 直接套用其他录音版本的时间 |
| 修改课程/音轨参数 | `courses/*.json`；私有歌曲只在私有仓库 `courses/` | `video/export.py <course> --check`，真实音轨需试出片 | 在公开仓库添加私人音乐 |
| 修改踩点算法 | `scripts/chart_generator.gd`, `video/choreography.py` 及相关测试 | Godot + 编排回归、真实音轨人工校准 | 双重应用 `beat_offset_ms`、仅凭合成音频宣称真实歌曲正确 |
| 调整小奶茶动作姿势 | `assets/coaches/milktea/rig/motions.json`, `assets/coaches/timing.json` | `tests/test_cutout_rig.py`, `tests/test_coach_avatar.py`, 关键姿势抽帧 | 改稳定动作 ID/拍点时间；破坏收拳、蓄力、双脚跟进 |
| 修正骨骼/素材遮挡 | `rig.json`, 独立 PNG、必要时 `video/coach_rig.py`/`scripts/milktea_rig.gd` | Python-Godot 跨渲染器对照及手机画幅审片 | 在 Godot/Python 分别维护不同姿势数据 |
| 优化画面或字体 | `video/arena.py`, `video/cue_art.py` | 场景测试、编码短片、HUD 与命中帧检查 | 让视觉层改变编排顺序或曲目时间戳 |
| 私有出片工作流 | `jabjam-render` 的 `.github/workflows/render-video.yml` | 私有动作工作流和私人歌曲烟雾测试 | 拷贝私有音乐进公开仓库；把私有内容写到公开 Actions |

## 给新歌找逐行歌词

收到音频就可以开始准备。先看私有课程的 `course.lyric_starts`，再看音频旁边的同名 `.lrc`。同一版录音已经校准过就直接复用，换场景也能用。两处都没有时，小奶茶在能联网的调度端用**歌名和歌手**找时间轴，音频留在私有出片流程里。没有分享链接时，可以在百度搜 `歌名 歌手 site:music.163.com/song`，或换成下表中相应的平台域名，进入单曲页。

| 查找顺序 | 去哪里找、取什么 |
| --- | --- |
| 1. 酷狗音乐 | 搜歌名和歌手，进入对应专辑的**单曲页**。部分单曲页的歌词正文已经带 `[分:秒.小数]`，用普通网页请求就能读取。[酷狗搜索](https://www.kugou.com/yy/html/search.html) |
| 2. 网易云音乐 | 从歌曲分享链接或单曲页取数字 `id`，请求 `https://music.163.com/api/song/lyric?id=数字ID&lv=-1`。取 JSON 中的 `lrc.lyric`，里面是带时间的原文。[网易云音乐](https://music.163.com/) |
| 3. 酷我音乐 | 从酷我单曲链接取它自己的数字 ID，请求 `https://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId=数字ID`。在 `data.lrclist` 里按 `lineLyric` 识别演唱行，`time` 是从原曲起点计算的**秒**，可以直接整理成 `course.lyric_starts`。[酷我音乐](https://www.kuwo.cn/) |
| 4. QQ 音乐 | 用单曲页核对歌手、专辑和版本。如果已有桌面工具 LDDC，可选择 QQ 音乐源，搜索同一录音并保存「原文／逐行 LRC」。服务器只收到网页外壳或纯文本时，继续查下一项。[QQ 音乐](https://y.qq.com/) · [LDDC 使用指南](https://github.com/chenmozhijin/LDDC/wiki) |
| 5. AMLL 社区词库 | 直接请求 `https://api.amll.dev/v1/lrclib/search`，传 `track_name` 和 `artist_name`，从匹配项取 `syncedLyrics`。这个库返回的 `duration` 是最后一个歌词时间戳，歌曲尾奏可能更长。[AMLL 接口说明](https://amll.dev/reference/http-api/lrclib.html) |
| 6. LRCLIB | 网络可达时作为补充。用 `https://lrclib.net/api/search` 加相同的两个参数找候选，也可用 `/api/get` 加专辑名和原曲时长（秒）缩小范围。请求带标识客户端的 `User-Agent`，选 `syncedLyrics` 有值的版本。[LRCLIB 接口说明](https://lrclib.net/docs.txt) |

**调度端可以这样试一首歌。** 下面用 Python 3 和一个公开曲目 ID 检查网易云能否返回时间标签。把第一行里的数字换成目标歌曲的网易云 ID 即可再查。各站的歌曲 ID 只在本站使用。

```sh
python3 - 186016 <<'PY'
import json, re, sys
from urllib.request import urlopen

url = f"https://music.163.com/api/song/lyric?id={int(sys.argv[1])}&lv=-1"
try:
    with urlopen(url, timeout=10) as response:
        lrc = (json.load(response).get("lrc") or {}).get("lyric") or ""
except (OSError, ValueError) as error:
    sys.exit(f"网易云本次无法读取，请换源 ({error})")
print("时间标签数", len(re.findall(r"\[\d+:[0-5]\d(?:[.:]\d{1,3})?\]", lrc)))
PY
```

**选版本和交付**

1. 对照歌手、专辑、录音室／现场／剪辑版和原曲时长。抽听第一句、中间一句和末段一句。若开头对得上、后半首逐渐偏离，换一个版本。只保留实际唱出的句子，去掉带时间的制作名单、空行和重复译文。
2. 时间对齐后，在私有歌曲目录把 UTF-8 逐行歌词与音频同名保存，例如 `round.mp3` 配 `round.lrc`。只留句首也可以写成 `[00:15.42]句 01`，或把秒数填入 `course.lyric_starts`。在 Normal、Hard 或 Expert 自动喂靶课程上运行 `python3 -S video/export.py "$course_json" --check`（`course_json` 指向该课程），输出 `N timed lyric lines` 即表示已读入。[课程字段和时间示例](video-export.md#按歌词起拳)
3. 以调度端当次拿到的有效时间标签判断可用性。超时、空结果、只有纯文本或版本对不上就换源。找不到匹配的时间轴时，把候选文件留在歌曲目录之外，本次课程省略 `lyric_starts`，音频旁也不放同名 LRC，照常出片并说明「本次按节拍编排」。纯音乐也走这条路径。

## 不变量：务必保留

- `note.time` 是从原曲开头计算的秒；视频只负责按帧显示。默认渲染 FPS 取整也不能改变歌曲和可编辑谱面的事件时间。
- 直拳撞击时拳套放大并遮住同侧手臂；摆拳与上勾拳应有区分明显的蓄力；侧步是先前脚后后脚；重点表情覆盖落拍前后。测试已覆盖部分行为，但最终视觉仍须人工看样片。
- 自动谱 `actions: auto` 与手排谱 `actions: []` 的接口含义不同。维护课程 schema 时保留 `version: 1` 兼容性，除非单独设计并测试迁移。
- 弱模型不要直接改 Godot 与 Python 两端的核心节拍算法或变更骨骼协议版本；这种跨系统变更需要强模型审阅。
- 修改算法后记录至少一首真实歌曲的拍点偏差与试听结论；已有合成波形测试不能替代这种验收。

## 一键验收（PR #12 合入后）

在包含 Python/Pillow、Godot 4.6.3、FFmpeg 和 Noto CJK 字体的 Linux 环境中，或在该仓库 `video-export` Docker 镜像里：

```sh
# 典型小步功能的交付门槛：Python 契约 + Godot 轻量运行时
sh scripts/verify_all.sh --quick

# CI 门槛：加上 Godot 编辑器完整资源导入
sh scripts/verify_all.sh --ci

# 强模型/本地完整验收：再生成可解码的三种视频样片
sh scripts/verify_all.sh --full
```

对于纯课程 JSON 修改，可以先运行 `python3 -S video/export.py courses/eight-moves.json --check`；**这不等于通过渲染验收**。私有歌曲不能在公开 CI 测试。

## 三个常见故障的排查顺序

**「改了代码但视频没变」**：查私有仓库工作流的 `ENGINE_SHA` 与本次公开提交是否一致；在私有构建 artifact 中核对 `build-manifest.json`。不要直接改回私有旧 `video/` 文件。

**「踩点感觉不对」**：先核对源音频、`source_beats`、BPM/半拍误判和 `beat_offset_ms`，再查组合与显示帧取整。先验证单曲前、中、后几个关键拍，避免用全局偏移掩盖持续漂移。

**「小兔子打错方向／穿模」**：先按 `video/movements.py` 确认屏幕左/右，再查 `motions.json` 姿势和 `rig.json` 的 z-order、pivot、front 贴图；用 Godot 预览及 Python 抽帧交叉确认。

## 失败处理和交付说明模板

PR 正文建议写：`预期行为`、`只修改这些文件`、`自动验证（逐条列命令、pass/fail）`、`实际视频审片（看了哪几秒）`、`兼容性与回退 SHA`。失败时不合并，不强推，不删除测试，不自行替换无法访问的私有输入。

## 本轮尚未自动解决的事情

- 真正的主歌、副歌、变速音乐的稳定识别，以及真人参考逐拍数据集：需要单独采样、对齐和人工确认。
- 主分支保护策略依赖仓库管理员设置，不能以「CI 通过」推断 GitHub 已配置禁止绕过保护。
- 私有真实音乐回归不能由公开仓库的合成测试代替；私有工作流必须独立验证。
