@tool
extends Node2D
## A rigid cutout puppet. The host supplies an absolute timeline state and phase.
const DIR := "res://assets/coaches/milktea/rig/"
var canvas_size := Vector2(480, 596)
var bones: Array = []
var joints := {}
var faces := {}
var face_sprite: Sprite2D
var poses := {}
var motions := {}
var textures := {}

@export_group("Pose preview")
@export_enum("idle", "left_jab", "right_jab", "left_hook", "right_hook", "left_uppercut", "right_uppercut", "step_left", "step_right", "celebrate") var preview_action := "idle":
	set(value):
		preview_action = value
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
			apply_pose(preview_action, "", preview_phase)
		else:
			apply_pose(preview_state, preview_action, preview_phase)

func _ready() -> void:
	var rig: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "rig.json"))
	var motion: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "motions.json"))
	assert(rig.format == "jabjam.cutout" and rig.version == 1)
	assert(motion.format == "jabjam.rig-motion" and motion.version == 1)
	bones = rig.bones
	canvas_size = _vector(rig.canvas)
	poses = motion.poses
	motions = motion.motions
	for bone: Dictionary in bones:
		var joint := Node2D.new()
		joint.name = bone.id
		var parent: Node2D = self if bone.parent == null else joints[bone.parent]
		parent.add_child(joint)
		joints[bone.id] = joint
		if bone.has("underlay"):
			_sprite(joint, bone, bone.underlay, 1)
		var sprite := _sprite(joint, bone, bone.texture, int(bone.z))
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

func apply_pose(state: String, action: String, phase: float) -> void:
	var kind := state
	if action.begins_with("step_"):
		kind = "step"
	elif not action.is_empty():
		kind = action.get_slice("_", 1)
	var mirror := action.begins_with("right_") or action == "step_right"
	var keys: Array = motions[kind][state]
	var i := 1
	while i < keys.size()-1 and phase >= float(keys[i][0]):
		i += 1
	var amount := smoothstep(float(keys[i-1][0]), float(keys[i][0]), phase)
	var start: Dictionary = poses[keys[i-1][1]]
	var finish: Dictionary = poses[keys[i][1]]
	var sign_x := -1.0 if mirror else 1.0
	for bone: Dictionary in bones:
		var key := _opposite(bone.id) if mirror else str(bone.id)
		var a: Array = start.get(key, [0, 0, 0])
		var b: Array = finish.get(key, [0, 0, 0])
		var joint: Node2D = joints[bone.id]
		var offset := _vector(a).lerp(_vector(b), amount)
		joint.position = _vector(bone.at) + Vector2(sign_x * offset.x, offset.y)
		joint.rotation_degrees = float(bone.get("angle", 0)) + sign_x * lerpf(a[2], b[2], amount)
	var expression := "open"
	if state == "celebrate" and phase >= 0.10 and phase <= 0.90:
		expression = "happy"
	elif state == "strike" and kind != "step":
		expression = "focus"
	face_sprite.texture = faces[expression]
