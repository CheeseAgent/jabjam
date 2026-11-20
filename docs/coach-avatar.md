# 小奶茶 2D 教练交接

[24 秒跟练样片](coach-preview/milktea-rig.mp4) · [透明组装图](coach-preview/assembled.png) · [十个关键姿势](coach-preview/key-poses.jpg) · [肩肘腕与髋膝踝角度对照](coach-preview/joint-rotations.jpg)

## 从哪里开始

| 工作 | 入口 |
| --- | --- |
| 在 Godot 里看完整动作 | 用项目指定的 Godot 4.6.3 打开仓库，打开 `scenes/coach_demo.tscn` 后按 F6。24 秒公有测试音轨与视频使用同一份八动作课程。 |
| 查看单个动作 | 打开 `scenes/milktea_rig.tscn`，选根节点。在 Inspector 的 Pose Preview 中选动作、阶段，拖动 Phase。 |
| 改绑定、查绘制顺序 | `assets/coaches/milktea/rig/rig.json`。每个关节是 Node2D，子 Sprite2D 以纹理锚点对齐。 |
| 改动作 | 同目录的 `motions.json`。Godot 和 Python 共同读取，不用导出逐动作序列帧。 |
| 替换部件 | 同目录 35 张独立 RGBA PNG。源图、切割与补绘程序在 `tools/coach_source/`。 |
| 重渲跟练 MP4 | `python3 video/export.py courses/coach-demo.json build/coach-demo.mp4`。示例仅使用仓库内的合成测试音轨。 |

身体、耳朵和四肢使用刚性切片，Node2D 层级即可表达父子旋转。以后需要弯曲耳廓或连续网格形变时，再评估 Skeleton2D 蒙皮。

## 造型来源和局部补绘范围

Pillow 对三个原文件的检查如下。前两张用于校对设计、比例和姿势。35 张运行时 PNG 全部来自第三张的像素及下列局部补绘。

| 上传文件 | 文件内容 | 模式 | 尺寸 |
| --- | --- | --- | --- |
| 1000054887.png | JPEG，多视角设定 | RGB | 1536 × 1152 |
| 1000054886.png | JPEG，动作参考 | RGB | 1536 × 864 |
| 1000054885.png | PNG，分解图 | RGBA，alpha 0–255 | 1448 × 1086 |

分解图原始文件是 `tools/coach_source/milktea.png`，SHA-256 为 `fc84c4fafdd20a460549b6382713a9699897d3c64d363ab2b19be1f59b4db4ee`。坐标以源图左上角为原点。构建脚本里的 `BOXES`、`CAPS`、`CUFF` 记录裁剪和修补区域，可以重新生成并逐张对比。

| 部位 | 原图和处理 | 绑定时的遮挡 |
| --- | --- | --- |
| 前臂、拳套 | 原图两者相连。沿珊瑚色袖口手工定边，向下延伸 y=636 的完整皮毛，重建袖口内看不见的腕端。 | 拳套绕腕轴转动，袖口盖住补绘区。左右分别从源图对应位置切出。 |
| 耳根、呆毛 | 原图带闭合切口描边。局部取邻近毛色延伸至切口，保留朝外的一圈。 | 耳根伸入头后，呆毛底部贴在头顶。保留两张背面耳朵供后续角度使用。 |
| 肩、肘、膝、踝 | 分解图画有封口线。取局部毛色补去端线，重叠两段，在底层重建外侧墨线。 | 上臂藏在背心后。每条四肢的 `ink_*.png` 随对应关节转动，防止两截同时露出横线。 |
| 表情下的脸 | 原头已画眉眼和嘴。沿原五官分离开眼表情，用周围完整皮毛边缘插值补出被遮挡的脸。 | 保留脸型、头带、鼻子和腮红。开心、专注、星星眼用原图下方的表情零件重新对齐。 |
| 短裤、尾巴、鞋脚 | 保留原图鲸鱼背心、松紧带、褶皱、足趾和尾巴。 | 胯部覆盖大腿起点，尾巴在正面大多被身体遮住。 |

原始纹理保留各自像素密度，以清单中的 scale 统一到 480 × 596 角色坐标。运行时有 20 个关节。25 张造型图含 4 套表情和 2 张备用耳背，另有 10 张关节底层墨线。

## 两种素材协议

| 课程设置 `picture.coach.renderer` | 配置入口 | 内容 |
| --- | --- | --- |
| `rig` | `assets/coaches/<skin>/rig/rig.json`、`motions.json` | `jabjam.cutout` v1 与 `jabjam.rig-motion` v1。独立纹理、关节、姿势曲线。 |
| `sprite` | `assets/coaches/<skin>/manifest.json` | 既有 v1 clips 逐帧皮肤包。已安装的逐帧包可直接切回。 |
| `vector` | 内置 | 没有外部美术包时可用的占位渲染器，也是未指定 renderer 时的默认值。 |

课程示例使用 `{"enabled": true, "renderer": "rig", "skin": "milktea", "side": "right", "scale": 1.0}`。`side` 控制教练站在画面的哪一侧。动作里的 `left` 和 `right` 始终指跟练者的屏幕左、右。课程省略教练时保持关闭。选择 `sprite` 需要安装完整 clips 包。

## 绑定和同步约定

- `bones` 按父先子后排列。`at` 是父节点坐标中的轴心位置（根节点相对画布），`angle` 是初始局部角度，`pivot` 是 PNG 像素坐标，`scale` 只缩放纹理。`z` 越大越靠近观众，相同深度按清单顺序绘制。`underlay` 跟随同一关节，绘制深度为 1。
- 每个姿势写相对绑定的 `[dx, dy, degrees]`。动作曲线按阶段进度在关键姿势之间平滑插值。右侧复制左侧通道的位移和旋转并互换关节名，分别使用真实左右 PNG。鲸鱼、纹理与高光保持原朝向。
- MP4 由 `video/coach_timeline.py` 从歌曲绝对时间选择 idle / prepare / strike / recover。骨骼模式在末动作回收后给出一次 celebrate。准备 0.30 秒、命中 0.10 秒、回收 0.30 秒，窗口定义集中在 `assets/coaches/timing.json`。密集动作沿用原有的准备抢占规则。
- Godot 交互模式从已有 `session.clock` 取时间，演示场景读取同一测试音轨的播放位置。两端复用动作曲线、时间窗口、绘制顺序；暂停和回跳直接重算姿势。测试比较两端的状态、阶段进度和全部关节世界变换。
- 庆祝与表情属于教练表现层，现有 `video/movements.py` 动作 ID、课程出拳顺序及计分接口保持兼容。交互游戏仍使用原有四轨计分，八动作由演示场景和视频课程完整覆盖。

## 复验

```sh
sh scripts/verify.sh
python3 tests/test_coach_avatar.py
python3 tests/test_cutout_rig.py
python3 tests/test_video_pacing.py
python3 video/export.py courses/coach-demo.json build/coach-demo.mp4
python3 tests/check_coach_sample.py build/coach-demo.mp4
python3 tools/preview_coach_rig.py
```

运行时使用现有 Godot / Pillow / FFmpeg 依赖。仅在重切原图时需要 NumPy、SciPy 和 Pillow，命令为 `python3 tools/coach_source/split_milktea.py --out build/rebuilt-rig`。`GODOT_BIN` 可指定运行比较测试使用的 Godot 二进制路径。

样片有 576 帧，1280 × 720，24 fps，H.264 + AAC。已对八个落拍及相邻帧、待机与庆祝共 34 个实际解码画面核对教练区域。测试还检查 PNG 透明度、腕肘膝踝的双侧像素重叠、整身轮廓连通、十种姿势、左右手脚、兼容逐帧皮肤及乱序定位。

## 仍需人工判断

在手机上连看 8–15 秒的摆拳和上勾拳，检查当前正面刚性造型是否足以区分向内和向上的轨迹。用户提供的动作参考里有些左右标签对应相同朝向，工程以跟练者屏幕侧为准。大角度转体、拳套朝镜头的透视和转身后的全身背面需要额外视角美术。新增超出现有角度范围的姿势时，复查腕口、呆毛下沿及踝部轮廓。教练动作和美术仍待用户审片。

## Real deployment topology (confirmed 2026-11-20)

- **小奶茶 is the user's life assistant running inside DSH on their personal Alibaba Cloud Chengdu server (2 CPU / 2 GB RAM)**; **DSF is the model used by that DSH instance**, not an independently deployed service or agent. The 小奶茶/DSH instance may coordinate maintenance and submit render jobs, but must NOT run heavy MP4 rendering on this low-resource server.
- **CheeseAgent/jabjam** is the public source of truth for app and render-engine code. The cutout coach and draft PR #11 live here.
- **CheeseAgent/jabjam-render** is the PRIVATE GitHub Actions rendering repository; it holds private music, including the Try Everything test track. A workflow run there rendered successfully on 2026-11-20. Never migrate private music into the public project.
- **GitHub-hosted Actions** do CPU-intensive offline video encoding; 小奶茶's server-side DSH orchestrates jobs, checks status, and consumes artifacts as needed.
- The present PR **does not automatically update jabjam-render**. The two repositories have diverged; before a production coach video, align the private render workflow with a specific tested public-engine SHA. Avoid manually maintaining duplicate copies of choreography or avatar modules indefinitely.
- Recommended future integration: have the private workflow check out a pinned revision of the public engine separately from the private audio/lesson inputs, then mount the latter read-only into offline rendering. Build an explicit manifest of source SHA and course/audio hash for reproducibility, but never publish private audio or its contents through public CI.
- First verify that the private-workflow interface and checkout/mount assumptions are compatible; do not overwrite the private repository or force-merge its history. Keep a safe legacy render fallback until the new pipeline passes one complete MP4 smoke test.
