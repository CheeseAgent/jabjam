# JabJam · 音乐拳击跟练视频生成器

选一首歌，生成一段可以在普通播放器打开的 MP4。跟练时面向屏幕，看方块沿左右轨道飞近，在它抵达击打线的音乐拍点空击。视频会在该拍点播放碎裂效果。

## 看懂八种动作

左右按跟练者面向屏幕时的方向判断。默认左轨青色、右轨橙色。

| 动作 | 左侧 JSON ID | 右侧 JSON ID | 看到什么、怎么跟 |
| --- | --- | --- | --- |
| 直拳 | `left_jab` | `right_jab` | 空中方块带直箭头，到线时用对应侧的手向前出拳。 |
| 摆拳 | `left_hook` | `right_hook` | 箭头朝画面中间横弯：左摆拳向右，右摆拳向左。 |
| 上勾拳 | `left_uppercut` | `right_uppercut` | J 形箭头从下向上挑，到线时跟着做上勾拳。 |
| 侧步 | `step_left` | `step_right` | 脚印沿地面靠近，按箭头向左或向右迈步，在拍点落脚。 |

## 在 GitHub Actions 生成视频

1. 打开 **Actions → Render follow-along MP4**。工作流进入默认分支后，可用 **Run workflow** 选择分支并填入课程 JSON 路径、画面上要显示的歌名、难度和最短拳间隔。歌名留空时自动读取歌曲标题。开发中的合并请求也会自动运行示例课程。
2. 默认课程 `courses/neon-round.json` 使用项目合成的 37 秒音乐，由现有 Godot 节拍分析与动作编排生成谱面。要精确指定每一拳的时间，参考 [八动作课程](courses/eight-moves.json)。
3. 运行完成后，在该次 Actions 的 **Artifacts** 下载保留 **1 天** 的 `jabjam-follow-along-…`。解压后播放 `jabjam.mp4`。包内还有四拳和八动作验收短片、成片对照图及资源报告。

构建依赖、排谱、渲染、编码和测试都可以在 GitHub 托管的 Linux runner 上完成。构建完成后，导出作业关闭容器网络。播放只需要成片，阿里云服务器无需参与。

## 试验版音乐感知谱面（V2）

自动模式现在根据四秒能量起伏动态调整每八拍的拳数：弱段落留白、普通段落稳定练习、强段落用短连拳穿插休息。真实主歌/副歌识别仍未实现，不保证每首歌精准。演示曲已增加强弱对比以方便试听。

导出成功会生成与 MP4 同名的 `.chart.json`，记录每段能量、所有实际出拳时间、BPM 和置信度。若听感持续偏早/偏晚，在 Actions 的 `beat_offset_ms` 中输入 -100 或 100（负值提前、正值延后，范围 ±250ms）。这个校准不能修正错误的 BPM、半速/倍速误判或变速歌曲。复杂歌曲仍需要进一步改造节拍追踪。

## 固定组合拳练习（padwork）

当音乐强度上升，拳组会从双拳热身过渡到常规三、四拳组合，再到五拳组合；每个级别都有多个经典套路，镜像重复练习两次后轮换。这是固定的训练乐句模板，不是每个拳点随机选动作，也不是已经实现真实歌曲的主副歌识别。视频会给出当前组合与第几拳的提示；Easy 自动练习不启用长组合。

## 导出入口

在装有 Godot 4.6.3 Standard、Python 3、Pillow、Noto CJK 字体、FFmpeg 和 ffprobe 的 Linux 环境中执行：

```sh
python3 video/export.py courses/neon-round.json build/neon-round.mp4 \
  --song-title "JabJam Demo Loop" --difficulty easy --min-gap 1.4
```

输出为横屏 H.264 / AAC MP4。音乐在本地分析；拳法、侧步、方块接近速度、配色、分辨率与帧率都由课程控制。课程字段、时间轴和测试口径见[视频导出指南](docs/video-export.md)。

## 写一份课程

**自动编排**时，把 `actions` 设为 `"auto"`。新增 `"movement_set": "padwork"`（与 `"difficulty": "normal"` 搭配）：教练从经典组合库中轮换 **直直摆、直直勾、直摆直、直直摆直、直直摆勾直、直勾直摆直** 等十余套拳组。每个套路先左起手、再右起手镜像重复两次练熟，才换下一套；音乐强度控制难度分组，组合之间留恢复拍。画面会显示组合名和当前拳序。默认 [neon-round.json](courses/neon-round.json) 已切换为此模式；旧的 `classic`、`mixed` 均保留。详情见 [视频导出指南](docs/video-export.md)。

**手排**时，在 `actions` 数组里写清每个动作及其相对音乐开头的秒数。下面是一份可直接导出的课程，用内置音乐先练左摆拳和右上勾拳，再向左侧步、向右回位：

```json
{
  "version": 1,
  "course": {"music": "builtin:demo", "difficulty": "normal"},
  "actions": [
    {"time": 4.0, "action": "left_hook"},
    {"time": 6.0, "action": "right_uppercut"},
    {"time": 8.0, "action": "step_left"},
    {"time": 10.0, "action": "step_right"}
  ]
}
```

换歌时，把 `course.music` 改为相对这份 JSON 的 MP3、WAV 或 Ogg Vorbis 文件路径。想放慢节奏，可设置 `course.min_gap` 或在调用时传 `--min-gap`（秒）。导出器取用户设置和下表规则中的较大值。手排动作过密时，错误信息会指出要调整的两个时刻。

| 相邻动作的最短间隔 | 入门 `easy` | 标准 `normal` |
| --- | ---: | ---: |
| 一般出拳 | 1.10 秒 | 0.45 秒 |
| 摆拳或上勾拳之后，或连续使用同一只手 | 1.35 秒 | 0.90 秒 |
| 侧步之前和之后 | 1.75 秒 | 1.50 秒 |

## 接手代码时从哪里改

| 要改的内容 | 入口 |
| --- | --- |
| 歌曲、时间点、课程动作顺序 | 照[八动作课程 JSON](courses/eight-moves.json)写一份课程即可。 |
| 动作 ID、中文名、左右侧和类型 | 修改 [movements.py](video/movements.py) 的 `MOVEMENTS` 表。改显示名称只需改 `label`，已有课程仍按原 ID 读取。 |
| 自动谱何时插入侧步、动作间隔 | 在 [choreography.py](video/choreography.py) 看 `arrange`（编排入口）、`mixed_round`（混合动作）及 `required_gap`（恢复间隔）。 |
| 箭头、脚印和落地波纹 | 图形在 [cue_art.py](video/cue_art.py)；轨道位置、移动和击碎效果在 [arena.py](video/arena.py)。 |
| 从配置到 MP4 的调用顺序 | 从 [export.py](video/export.py) 的 `export` 读起：读课程，准备音频和动作，绘制每一帧，交给 FFmpeg 编码。 |

新增一种动作时，先登记 ID，用一份手排课程验证图标、方向和间隔，再按需加入自动编排。下面的命令可以检查规则、导出八动作样片，并从成片抽帧生成对照图：

```sh
python3 tests/test_video_pacing.py
python3 video/export.py courses/eight-moves.json build/eight-moves.mp4
python3 tests/check_eight_moves.py build/eight-moves.mp4
```

## 早期交互原型

Godot 互动工程仍可以独立运行。导出器直接复用它的导歌及编排实现，成片播放与动作计分彼此独立。[原型运行指南](docs/development.md) · [游戏设计历史](docs/game-design-vision.md) · [引擎选型记录](docs/decisions/0001-game-engine-godot.md)
