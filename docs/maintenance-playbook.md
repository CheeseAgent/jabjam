# JabJam · 小奶茶维护操作手册

目标：把维护动作限定在少数文件内，让能力较弱的模型只需阅读相关模块，也能通过自动化验证来交付安全的小步 PR。

## 开工协议

1. 从 `main` 派生**新的独立分支**，不要在主分支试验。先写清楚「输入—预期输出—修改范围—不改的东西」。
2. 阅读 `AGENTS.md` 和本页当前任务的表格；不要未经要求顺手重构相邻模块。
3. 记录修改前的快速验收结果；修改后运行同样的测试，加一个覆盖新行为的回归用例。
4. PR 描述必须包含：需求、变更文件、测试命令与结果、风险和回退方式。失败应原样报告，不得凭空宣称验证通过。
5. 新功能通过 PR 合入公开引擎后，私有渲染仓库另开 PR 更新固定的引擎 SHA，先跑真实歌曲烟雾测试；不要同步复制整个引擎。

## 按任务最小修改

| 任务 | 优先编辑 | 必须检查 | 特别禁止 |
| --- | --- | --- | --- |
| 新增场景 | `assets/arenas/*`, `video/course.py`, `video/arena.py`, `.github/workflows/render-video.yml` | `tests/test_arena_scenes.py`, 一段示例 MP4 | 运行中途自动随机切背景；丢失兼容场景 ID |
| 更改场景背景图 | `assets/arenas/<scene>.jpg` | 抽帧对比轨道与 HUD，测试固定场景 | 改动拳法、节拍与教练 |
| 增加经典拳组 | `video/choreography.py` 的 `PADWORK_COMBOS` | `tests/test_video_pacing.py` + `--write-course` | 随机拆散组合或突破恢复间隔 |
| 修改课程/音轨参数 | `courses/*.json`；私有歌曲只在私有仓库 `courses/` | `video/export.py <course> --check`，真实音轨需试出片 | 在公开仓库添加私人音乐 |
| 修改踩点算法 | `scripts/chart_generator.gd`, `video/choreography.py` 及相关测试 | Godot + 编排回归、真实音轨人工校准 | 双重应用 `beat_offset_ms`、仅凭合成音频宣称真实歌曲正确 |
| 调整小奶茶动作姿势 | `assets/coaches/milktea/rig/motions.json`, `assets/coaches/timing.json` | `tests/test_cutout_rig.py`, `tests/test_coach_avatar.py`, 关键姿势抽帧 | 改稳定动作 ID/拍点时间；破坏收拳、蓄力、双脚跟进 |
| 修正骨骼/素材遮挡 | `rig.json`, 独立 PNG、必要时 `video/coach_rig.py`/`scripts/milktea_rig.gd` | Python-Godot 跨渲染器对照及手机画幅审片 | 在 Godot/Python 分别维护不同姿势数据 |
| 优化画面或字体 | `video/arena.py`, `video/cue_art.py` | 场景测试、编码短片、HUD 与命中帧检查 | 让视觉层改变编排顺序或曲目时间戳 |
| 私有出片工作流 | `jabjam-render` 的 `.github/workflows/render-video.yml` | 私有动作工作流和私人歌曲烟雾测试 | 拷贝私有音乐进公开仓库；把私有内容写到公开 Actions |

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
