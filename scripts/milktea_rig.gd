@tool
extends Node2D
## A rigid cutout puppet. The host supplies an absolute timeline state and phase.
const TurnShader = preload("res://scripts/coach_turn.gdshader")
const DIR := "res://assets/coaches/milktea/rig/"
var canvas_size := Vector2(480, 596)
var bones: Array = []
var joints := {}
var artwork := {}
var front_panels := {}
var surfaces := {}
var turns := {}
var shoulder := {}
var stride := 0.0
var depth_stride := 0.0
var stance_geometry := {}
var faces := {}
var face_sprite: Sprite2D
var poses := {}
var motions := {}
var textures := {}

@export_group("Pose preview")
@export_enum("idle", "left_jab", "right_jab", "left_hook", "right_hook", "left_uppercut", "right_uppercut", "step_left", "step_right", "step_forward", "step_backward", "duck", "celebrate") var preview_action := "idle":
	set(value):
		preview_action = value
		_preview()
@export_enum("left", "right") var preview_lead_foot := "left":
	set(value):
		preview_lead_foot = value
		_preview()
@export_enum("prepare", "strike", "recover") var preview_state := "strike":
	set(value):
		preview_state = value
		_preview()
@export_range(0.0, 1.0, 0.01) var preview_phase := 0.0:
	set(value):
		preview_phase = value
		_preview()

func _preview() -> void:
	if Engine.is_editor_hint() and face_sprite:
		if preview_action in ["idle", "celebrate"]:
			apply_pose(preview_action, "", preview_phase, 0, null, 0, preview_lead_foot)
		else:
			apply_pose(preview_state, preview_action, preview_phase, 0, null, 0, preview_lead_foot)

func _ready() -> void:
	var rig: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "rig.json"))
	var motion: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "motions.json"))
	assert(rig.format == "jabjam.cutout" and rig.version == 1)
	assert(motion.format == "jabjam.rig-motion" and (motion.version == 1 or motion.version == 2))
	bones = rig.bones
	canvas_size = _vector(rig.canvas)
	stride = float(motion.get("stride_px", 0))
	depth_stride = float(motion.get("depth_stride_px", 0))
	stance_geometry = motion.get("stance", {})
	turns = motion.get("turns", {})
	shoulder = rig.get("shoulder_projection", {})
	poses = motion.poses
	motions = motion.motions
	for bone: Dictionary in bones:
		var joint := Node2D.new()
		joint.name = bone.id
		var parent: Node2D = self if bone.parent == null else joints[bone.parent]
		parent.add_child(joint)
		joints[bone.id] = joint
		var art := Node2D.new()
		joint.add_child(art)
		artwork[bone.id] = art
		if bone.has("underlay"):
			_sprite(art, bone, bone.underlay, 1)
		var sprite := _sprite(art, bone, bone.texture, int(bone.z))
		if bone.has("surface"):
			var material := ShaderMaterial.new()
			material.shader = TurnShader
			material.set_shader_parameter("depth", float(bone.surface.depth))
			sprite.material = material
			surfaces[bone.id] = material
		if bone.has("front"):
			front_panels[bone.id] = _sprite(joint, bone, bone.front.texture, int(bone.z)+1)
		if bone.has("variants"):
			face_sprite = sprite
			for variant: String in bone.variants:
				faces[variant] = _texture(bone.variants[variant])
	apply_pose("idle", "", 0.0)
	_preview()

func _vector(pair: Array) -> Vector2:
	return Vector2(pair[0], pair[1])

func _texture(file: String) -> Texture2D:
	if not textures.has(file):
		var path := DIR + file
		# A clean runtime-only checkout has raw PNGs and no imported cache.
		# Packaged projects can instead load the imported texture.
		if FileAccess.file_exists(path):
			var image := Image.new()
			var error := image.load_png_from_buffer(FileAccess.get_file_as_bytes(path))
			assert(error == OK, "Invalid coach PNG: " + path)
			textures[file] = ImageTexture.create_from_image(image)
		else:
			textures[file] = load(path)
	return textures[file]

func _sprite(joint: Node2D, bone: Dictionary, file: String, depth: int) -> Sprite2D:
	var sprite := Sprite2D.new()
	sprite.texture = _texture(file)
	sprite.centered = false
	sprite.scale = Vector2.ONE * float(bone.scale)
	sprite.position = -_vector(bone.pivot) * float(bone.scale)
	sprite.z_as_relative = false
	sprite.z_index = depth
	joint.add_child(sprite)
	return sprite

func _opposite(id: String) -> String:
	if id.ends_with("_left"):
		return id.trim_suffix("_left") + "_right"
	if id.ends_with("_right"):
		return id.trim_suffix("_right") + "_left"
	return id

func _project_art(bone: Dictionary, zoom: float) -> void:
	var art: Node2D = artwork[bone.id]
	if bone.has("front"):
		var front: Dictionary = bone.front
		var depth := clampf((zoom-1.0)/(float(front.zoom)-1.0), 0.0, 1.0)
		var panel: Sprite2D = front_panels[bone.id]
		panel.visible = depth > 0.0
		if panel.visible:
			var weight := 1.0 - (1.0-depth)/zoom
			var pivot := _vector(bone.pivot).lerp(_vector(front.pivot), weight)
			panel.scale = Vector2.ONE * float(bone.scale) * zoom
			panel.position = -pivot * panel.scale
			zoom = lerpf(1.0, front.cuff_scale, depth)
	art.scale = Vector2.ONE * zoom

func apply_pose(state: String, action: String, phase: float, stance := 0, focused: Variant = null, depth := 0, lead_foot := "left") -> void:
	var kind := state
	if action == "step_forward":
		kind = "advance"
	elif action == "step_backward":
		kind = "retreat"
	elif action == "duck":
		kind = "duck"
	elif action.begins_with("step_"):
		kind = "step"
	elif not action.is_empty():
		kind = action.get_slice("_", 1)
	var mirror := action.begins_with("right_") or action == "step_right" or (kind in ["advance", "retreat"] and lead_foot == "right")
	var keys: Array = motions[kind][state]
	var i := 1
	while i < keys.size()-1 and phase >= float(keys[i][0]):
		i += 1
	var amount := smoothstep(float(keys[i-1][0]), float(keys[i][0]), phase)
	var start: Dictionary = poses[keys[i-1][1]]
	var finish: Dictionary = poses[keys[i][1]]
	var sign_x := -1.0 if mirror else 1.0
	var turn0 := _vector(turns.get(keys[i-1][1], [0,0]))
	var turn1 := _vector(turns.get(keys[i][1], [0,0]))
	var yaw := turn0.lerp(turn1, amount) * (PI/180.0) * sign_x
	for bone: Dictionary in bones:
		var key := _opposite(bone.id) if mirror else str(bone.id)
		var a: Array = start.get(key, [0, 0, 0])
		var b: Array = finish.get(key, [0, 0, 0])
		var joint: Node2D = joints[bone.id]
		var offset := _vector(a).lerp(_vector(b), amount)
		if bone.has("surface"):
			var turn_angle := yaw.x if bone.surface.turn == "hips" else yaw.y
			surfaces[bone.id].set_shader_parameter("yaw", turn_angle*float(bone.surface.amount))
		var stagger := Vector2.ZERO
		if str(bone.id).begins_with("thigh_"):
			var is_lead := str(bone.id) == "thigh_" + lead_foot
			if is_lead:
				stagger.y = float(stance_geometry.get("lead_forward_px", 0))
				stagger.x = (-1.0 if lead_foot == "left" else 1.0) * float(stance_geometry.get("lead_spread_px", 0))
			else:
				stagger.y = -float(stance_geometry.get("rear_back_px", 0))
				stagger.x = (1.0 if lead_foot == "left" else -1.0) * float(stance_geometry.get("rear_spread_px", 0))
		if bone.parent == null:
			if stride > 0 and kind == "step" and stance == (1 if mirror else -1):
				offset.x = 0.0
			if kind in ["advance", "retreat"] and depth == (1 if kind == "advance" else -1):
				offset.y = 0.0
			joint.position = _vector(bone.at) + Vector2(sign_x * offset.x + stance*stride, offset.y + depth*depth_stride)
		else:
			joint.position = _vector(bone.at) + Vector2(sign_x * offset.x, offset.y) + stagger
		if bone.has("shoulder_side"):
			var near := -float(bone.shoulder_side) * sin(yaw.y)
			var perspective := 1.0 + near*float(shoulder.depth_scale)
			joint.position.x *= cos(yaw.y)*perspective
			joint.position.y += near*float(shoulder.drop_px)
			joint.scale = Vector2.ONE * perspective
		var zoom_a := float(a[3]) if a.size() == 4 else 1.0
		var zoom_b := float(b[3]) if b.size() == 4 else 1.0
		var zoom := lerpf(zoom_a, zoom_b, amount)
		if str(bone.id).begins_with("foot_"):
			zoom *= 1.05 if str(bone.id) == "foot_" + lead_foot else 0.98
		_project_art(bone, zoom)
		joint.rotation_degrees = float(bone.get("angle", 0)) + sign_x * lerpf(a[2], b[2], amount)
	var expression := "open"
	if focused:
		expression = "focus"
	elif state == "celebrate" and phase >= 0.10 and phase <= 0.90:
		expression = "happy"
	elif focused == null and not action.is_empty() and kind != "step":
		if state == "strike" or (state == "prepare" and phase >= 0.35) or (state == "recover" and phase < 0.5):
			expression = "focus"
	face_sprite.texture = faces[expression]
