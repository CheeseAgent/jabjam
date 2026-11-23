# 小奶茶 2D 教练交接

[24 秒角色近景](coach-preview/milktea-motion-review.mp4) · [同期跟练全景](coach-preview/milktea-rig.mp4) · [透明组装图](coach-preview/assembled.png) · [十个关键姿势](coach-preview/key-poses.jpg) · [关节、转体与步法对照](coach-preview/joint-rotations.jpg)

## 从哪里开始

| 工作 | 入口 |
| --- | --- |
| 在 Godot 里看完整动作 | 用项目指定的 Godot 4.6.3 打开仓库，打开 `scenes/coach_demo.tscn` 后按 F6。24 秒公有测试音轨与视频使用同一份八动作课程。 |
| 查看单个动作 | 打开 `scenes/milktea_rig.tscn`，选根节点。在 Inspector 的 Pose Preview 中选动作、阶段，拖动 Phase。 |
| 改绑定、查绘制顺序 | `assets/coaches/milktea/rig/rig.json`。每个关节是 Node2D，子 Sprite2D 以纹理锚点对齐。 |
| 改动作 | 同目录的 `motions.json`。Godot 和 Python 共同读取，不用导出逐动作序列帧。 |
| 替换部件 | 同目录 37 张独立 RGBA PNG。源图、切割与补绘程序在 `tools/coach_source/`。 |
| 重渲跟练 MP4 | `python3 video/export.py courses/coach-demo.json build/coach-demo.mp4`。示例仅使用仓库内的合成测试音轨。 |

身体、耳朵和四肢使用刚性切片，Node2D 层级即可表达父子旋转。以后需要弯曲耳廓或连续网格形变时，再评估 Skeleton2D 蒙皮。

## 造型来源和局部补绘范围

Pillow 对三个原文件的检查如下。前两张用于校对设计、比例和姿势。37 张运行时 PNG 全部来自第三张的像素及下列局部补绘。

| 上传文件 | 文件内容 | 模式 | 尺寸 |
| --- | --- | --- | --- |
| 1000054887.png | JPEG，多视角设定 | RGB | 1536 × 1152 |
| 1000054886.png | JPEG，动作参考 | RGB | 1536 × 864 |
| 1000054885.png | PNG，分解图 | RGBA，alpha 0–255 | 1448 × 1086 |

分解图原始文件是 `tools/coach_source/milktea.png`，SHA-256 为 `fc84c4fafdd20a460549b6382713a9699897d3c64d363ab2b19be1f59b4db4ee`。坐标以源图左上角为原点。构建脚本里的 `BOXES`、`CAPS`、`CUFF` 记录裁剪和修补区域，可以重新生成并逐张对比。

| 部位 | 原图和处理 | 绑定时的遮挡 |
| --- | --- | --- |
| 前臂、拳套 | 原图两者相连。沿珊瑚色袖口手工定边，向下延伸 y=636 的完整皮毛，重建袖口内看不见的腕端。 | 拳套绕腕轴转动，袖口盖住补绘区。左右分别从源图对应位置切出。 |
| 正面拳套 | 在左右原拳套上各描一张遮罩，单独保留圆鼓的拳面、拇指、高光与外轮廓。 | 直拳前伸时前臂缩短，袖口缩小，拳面在最前层放大并移到腕前，收回时重新与原拳套对齐。 |
| 耳根、呆毛 | 原图带闭合切口描边。局部取邻近毛色延伸至切口，保留朝外的一圈。 | 耳根伸入头后，呆毛底部贴在头顶。保留两张背面耳朵供后续角度使用。 |
| 肩、肘、膝、踝 | 分解图画有封口线。取局部毛色补去端线，重叠两段，在底层重建外侧墨线。 | 上臂藏在背心后。每条四肢的 `ink_*.png` 随对应关节转动，防止两截同时露出横线。 |
| 表情下的脸 | 原头已画眉眼和嘴。沿原五官分离开眼表情，用周围完整皮毛边缘插值补出被遮挡的脸。 | 保留脸型、头带、鼻子和腮红。开心、专注、星星眼用原图下方的表情零件重新对齐。 |
| 短裤、尾巴、鞋脚 | 保留原图鲸鱼背心、松紧带、褶皱、足趾和尾巴。 | 胯部覆盖大腿起点，尾巴在正面大多被身体遮住。 |

原始纹理保留各自像素密度，以清单中的 scale 统一到 480 × 596 角色坐标。运行时有 20 个关节。27 张造型图含 4 套表情、2 张备用耳背和 2 张前景拳面，另有 10 张关节底层墨线。

## 站架、前后步和下潜（新增）

课程里设置 `picture.coach.lead_foot` 为 `"left"`（默认左脚前，正架）或 `"right"`（右脚前，反架）。`picture.coach.side` 仍只控制小奶茶出现在画面左边还是右边，不能拿来代替脚位；`show_stance_label` 默认为 `true`，在脚下显示“左脚前 · 正架”或“右脚前 · 反架”，可以设为 `false`。默认 rig 站架改为前后错位：前脚位置更靠近观众、脚掌略大，后脚稍向后；拳套仍表示课程动作定义的屏幕左右侧。

新谱面动作 ID：`step_forward`（前脚先迈、后脚跟进），`step_backward`（后脚先退、前脚跟进），`duck`（屈膝下潜、双手留在防守位，再站起）。侧步 `step_left/right` 不变。前后步通过独立的 `depth` 计数（-1 到 1）记录原曲任意时间的落点，侧步仍用原来的水平 `stance`。骨骼动作来自同一份 `motions.json`，Python/Pillow 和 Godot 同步；原音频时间不变。

有公开演示课 `courses/footwork-dodge.json`。验收顺序是：左右脚前各检查待机轮廓；前进/后退从首次落脚到后脚跟进观察地面脚印；下潜看髋关节、膝盖和头部的高度变化；来回拖动时间轴，验证无累积漂移。跑 `sh scripts/verify_all.sh --full` 后，还需人工抽帧检查前后脚没有穿模。

## 两种素材协议

| 课程设置 `picture.coach.renderer` | 配置入口 | 内容 |
| --- | --- | --- |
| `rig` | `assets/coaches/<skin>/rig/rig.json`、`motions.json` | `jabjam.cutout` v1 与 `jabjam.rig-motion` v2。独立纹理、关节、姿势曲线。加载器也支持 v1 三分量动作。 |
| `sprite` | `assets/coaches/<skin>/manifest.json` | 既有 v1 clips 逐帧皮肤包。已安装的逐帧包可直接切回。 |
| `vector` | 内置 | 没有外部美术包时可用的占位渲染器，也是未指定 renderer 时的默认值。 |

课程示例使用 `{"enabled": true, "renderer": "rig", "skin": "milktea", "side": "right", "scale": 1.0}`。`side` 控制教练站在画面的哪一侧。动作里的 `left` 和 `right` 始终指跟练者的屏幕左、右。课程省略教练时保持关闭。选择 `sprite` 需要安装完整 clips 包。

## 绑定和同步约定

- `bones` 按父先子后排列。`at` 是父节点坐标中的轴心位置（根节点相对画布），`angle` 是初始局部角度，`pivot` 是 PNG 像素坐标，`scale` 只缩放纹理。`z` 越大越靠近观众，相同深度按清单顺序绘制。`underlay` 跟随同一关节，绘制深度为 1。
- 每个姿势写相对绑定的 `[dx, dy, degrees]`，可选第四个数控制该部件的近大远小，默认 1。右侧动作镜像位移和角度，使用屏幕右侧自己的纹理。
- `motions.json` 的 `turns` 按姿势列出髋、胸的侧转角度。摆拳和上勾拳先向反方向蓄力，再由髋带胸转回来。落拍时胸口侧转 29°–35°，头部只跟随 29%。肩部用胸转角控制远近和投影位置。Godot 的 `coach_turn.gdshader` 和 Pillow 的 `turn_surface` 将同一个曲面投影用于背心及鲸鱼、头及表情。出拳用的仍是原图。
- `video/coach_timeline.py` 和 Godot 的 `scripts/coach.gd` 按歌曲绝对时间定位。直拳、摆拳、上勾拳和侧步的准备段分别为 0.30、0.60、0.64 和 0.42 秒。前脚落在谱面拍点上。拍点后一律保持 0.10 秒，出拳用 0.30 秒收回，侧步用 0.52 秒让后脚跟上。密集动作按间隔等比缩短相邻回收与准备段。步幅为 `stride_px`，单次侧步后双脚停在新位置，再向外连走时画面跟随。
- 每次出拳前 0.36 秒切换专注表情，落拍后保留 0.58 秒。相邻表情间隙短于或等于 0.12 秒时连续保持。收完最后一动后进入庆祝。上述时间统一在 `assets/coaches/timing.json` 调整。
- Godot 交互模式读取 `session.clock`，演示场景读取同一测试音轨的位置。暂停和回跳按时间重算。测试对比两端的阶段、脚位、表情、关节世界变换、拳面缩放及材质侧转角。
- 庆祝与表情属于教练表现层，现有 `video/movements.py` 动作 ID、课程出拳顺序及计分接口保持兼容。交互游戏仍使用原有四轨计分，八动作由演示场景和视频课程完整覆盖。

## 复验

```sh
sh scripts/verify.sh
python3 tests/test_coach_avatar.py
python3 tests/test_cutout_rig.py
python3 tests/test_video_pacing.py
python3 video/export.py courses/coach-demo.json build/coach-demo.mp4
python3 tests/check_coach_sample.py build/coach-demo.mp4
python3 tools/preview_coach_rig.py --video docs/coach-preview/milktea-motion-review.mp4
```

运行时使用现有 Godot / Pillow / FFmpeg 依赖。仅在重切原图时需要 NumPy、SciPy 和 Pillow，命令为 `python3 tools/coach_source/split_milktea.py --out build/rebuilt-rig`。`GODOT_BIN` 可指定运行比较测试使用的 Godot 二进制路径。

两段样片各有 576 帧，24 fps，H.264 + AAC。跟练全景为 1280 × 720，角色近景为 540 × 680。本次在完整解码后抽取全景 66 帧、近景 14 帧核对教练区域，最大单通道平均误差分别为 3.23/255 和 2.49/255 以内。覆盖准备、落拍、收拳后表情、后脚跟进、待机与庆祝。骨骼测试还测量拳面遮住同侧手臂的面积、蓄力定格帧数、侧转时鲸鱼的位移，以及支撑脚的滑动。

## 仍需人工判断

手机近景中，4 秒和 6 秒看左右直拳的透视及收拳后的表情，8–15 秒看摆拳与上勾拳蓄力时的肩线和背心鲸鱼，18 秒和 20.5 秒看两只脚的落地顺序。试听全景可以判断课程原尺寸下转体与表情是否足够明显。现有侧转以正面原画近似，如以后需要完整侧面或背身，应补相应视角美术，并复查腕口、呆毛下沿及踝部轮廓。动作参考中的部分左右标签朝向相同，实际绑定以跟练者屏幕侧为准。

## Real deployment topology (confirmed 2026-11-20)

- **小奶茶 is the user's life assistant running inside DSH on their personal Alibaba Cloud Chengdu server (2 CPU / 2 GB RAM)**; **DSF is the model used by that DSH instance**, not an independently deployed service or agent. The 小奶茶/DSH instance may coordinate maintenance and submit render jobs, but must NOT run heavy MP4 rendering on this low-resource server.
- **CheeseAgent/jabjam** is the public source of truth for app and render-engine code. The cutout coach was merged from PR #11 into `main` on 2026-11-21.
- **CheeseAgent/jabjam-render** is the PRIVATE GitHub Actions rendering repository; it holds private music, including the Try Everything test track. A workflow run there rendered successfully on 2026-11-20. Never migrate private music into the public project.
- **GitHub-hosted Actions** do CPU-intensive offline video encoding; 小奶茶's server-side DSH orchestrates jobs, checks status, and consumes artifacts as needed.
- Merging the public engine does **not automatically update jabjam-render**. Before releasing a production coach video, verify the private render workflow pins a tested public-engine SHA; never maintain duplicate choreography or avatar modules.
- The recommended integration is a private workflow that checks out a pinned public engine SHA and mounts private audio read-only into an offline render container. Track the source SHA and input hashes in a private artifact manifest; never publish private audio or course contents through public CI. See [Agent 维护操作手册](maintenance-playbook.md).
- First verify that the private-workflow interface and checkout/mount assumptions are compatible; do not overwrite the private repository or force-merge its history. Keep a safe legacy render fallback until the new pipeline passes one complete MP4 smoke test.
